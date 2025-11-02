from datetime import datetime, timedelta, timezone
import io
import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from clepsy.entities import (
    DesktopInputAfkStartEvent,
    DesktopInputScreenshotEvent,
)
from clepsy.queues import event_bus


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
        await event_bus.publish(event)
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
        data_dict["screenshot"] = screenshot_image
        ts = datetime.fromisoformat(data_dict["timestamp"])  # may be naive or aware
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        data_dict["timestamp"] = ts

        # Create and validate the event
        desktop_check_event = DesktopInputScreenshotEvent.model_validate(data_dict)

        # Publish event
        await event_bus.publish(desktop_check_event)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
        ) from e
