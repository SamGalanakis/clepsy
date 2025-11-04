from datetime import datetime, timedelta, timezone
import io
import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image
from rq import Queue

from clepsy.entities import (
    DesktopInputAfkStartEvent,
    DesktopInputScreenshotEvent,
)
from clepsy.infra.rq_setup import get_connection
from clepsy.infra.streams import xadd_source_event
from clepsy.jobs.desktop import process_desktop_screenshot_job


router = APIRouter(prefix="/desktop")


@router.post("/afk-input")
async def receive_afk_start(
    timestamp: datetime,
    time_since_last_user_activity: timedelta,
) -> None:
    try:
        event = DesktopInputAfkStartEvent(
            timestamp=timestamp,
            time_since_last_user_activity=time_since_last_user_activity,
        )
        # Inline write to Valkey stream (no need to queue a tiny write)
        payload_json = json.dumps(
            {
                "timestamp": (
                    event.timestamp
                    if event.timestamp.tzinfo
                    else event.timestamp.replace(tzinfo=timezone.utc)
                ).isoformat(),
                "time_since_last_user_activity": str(time_since_last_user_activity),
            }
        )
        _ = xadd_source_event(
            event_type="desktop_afk_event",
            timestamp=event.timestamp
            if event.timestamp.tzinfo
            else event.timestamp.replace(tzinfo=timezone.utc),
            payload_json=payload_json,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/screenshot-input")
async def receive_data(
    screenshot: UploadFile = File(...),
    data: str = Form(...),
) -> dict | None:
    """
    Receive desktop check data with screenshot and metadata.

    The multipart form should contain:
    - screenshot: an image file
    - data: a JSON string with metadata
    """
    try:
        # Read screenshot image
        image_bytes = await screenshot.read()
        with io.BytesIO(image_bytes) as image_stream:
            screenshot_image = Image.open(image_stream)
            screenshot_image.load()

        # Clean up read file resources to avoid the "after boundary" warning
        await screenshot.close()
        if screenshot_image.size[0] < 800 or screenshot_image.size[1] < 800:
            error_msg = f"Screenshot size too small: {screenshot_image.size}"
            raise HTTPException(
                status_code=400,
                detail=error_msg,
            )

        # Parse JSON data safely
        try:
            data_dict = json.loads(data)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON data",
            ) from exc

        # Add screenshot and convert timestamp
        # We'll pass raw bytes to the RQ job and reconstruct the image server-side
        ts = datetime.fromisoformat(data_dict["timestamp"])  # may be naive or aware
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        data_dict["timestamp"] = ts
        # Validate minimal fields now to catch bad requests early
        DesktopInputScreenshotEvent.model_validate(
            {**data_dict, "screenshot": screenshot_image}
        )

        q = Queue("default", connection=get_connection())  # type: ignore[arg-type]
        q.enqueue(
            process_desktop_screenshot_job,
            data_dict,
            image_bytes,
            job_timeout=300,  # allow OCR/VLM time
            result_ttl=0,  # we don't need the return value persisted
            failure_ttl=24 * 3600,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
        ) from e
