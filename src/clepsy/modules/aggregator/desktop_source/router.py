# ruff: noqa: I001
import io
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from loguru import logger
from PIL import Image

from clepsy.entities import (
    DesktopInputAfkStartEvent,
    DesktopInputScreenshotEvent,
)
from clepsy.infra.streams import xadd_source_event
from clepsy.jobs.desktop import process_desktop_screenshot_job
from clepsy import utils
from clepsy.config import config

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
                # Encode as seconds to align with Pydantic's timedelta parsing
                "time_since_last_user_activity": time_since_last_user_activity.total_seconds(),
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
        if screenshot_image.size[0] < 200 or screenshot_image.size[1] < 200:
            error_msg = f"Screenshot size too small: {screenshot_image.size}"
            logger.warning(error_msg)
            raise HTTPException(
                status_code=400,
                detail=error_msg,
            )

        utils.resize_image_with_thumbnail(
            image=screenshot_image,
            target_height=config.screenshot_max_size_ocr[0],
            target_width=config.screenshot_max_size_ocr[1],
            inplace=True,
        )

        try:
            data_dict = json.loads(data)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON data in screenshot input: {}", exc)
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON data",
            ) from exc

        # Prepare timestamp for validation and messaging
        # 1) Parse incoming timestamp and ensure it's timezone-aware in UTC
        ts = datetime.fromisoformat(data_dict["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ts_utc = ts.astimezone(timezone.utc)

        # 2) Early validate with Pydantic using an aware datetime
        DesktopInputScreenshotEvent.model_validate(
            {**data_dict, "timestamp": ts_utc, "screenshot": screenshot_image}
        )

        # 3) For the background job payload, serialize as ISO8601 naive (UTC)
        #    This avoids timezone-aware datetimes inside Dramatiq messages
        message_dict = {
            **data_dict,
            "timestamp": ts_utc.replace(tzinfo=None).isoformat(),
        }

        # Encode image as base64 (PNG) to keep Dramatiq message JSON-serializable
        image_b64 = utils.pil_image_to_base64(screenshot_image, img_format="PNG")

        # Send to Dramatiq actor with JSON-safe payload and base64 image
        process_desktop_screenshot_job.send(message_dict, image_b64)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing screenshot input", exc_info=e)
        raise HTTPException(
            status_code=500,
        ) from e
