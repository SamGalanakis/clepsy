from __future__ import annotations

# ruff: noqa: I001
import json
from datetime import datetime, timezone
from typing import Any

import dramatiq
from loguru import logger
from clepsy.infra import dramatiq_setup as _dramatiq_setup  # noqa: F401
from clepsy.jobs.actor_init import actor_init

from clepsy.db.db import get_db_connection
from clepsy.db.queries import select_user_settings
from clepsy.infra.streams import xadd_source_event
from clepsy.entities import DesktopInputScreenshotEvent
from clepsy.modules.aggregator.desktop_source.worker import process_desktop_check
from clepsy.entities import (
    ProcessedDesktopCheckScreenshotEventOCR,
    ProcessedDesktopCheckScreenshotEventVLM,
)
from clepsy.modules.pii.sanitize import sanitize_text
from clepsy.utils import retrieve_image_from_redis
from uuid import UUID


def ensure_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def build_desktop_event_from_payload(
    data: dict[str, Any],
) -> DesktopInputScreenshotEvent | None:
    """Build a desktop event from payload, retrieving image from Redis.

    Returns None if the image has expired or is missing from Redis.
    """
    # Coerce timestamp to aware datetime
    ts = data.get("timestamp")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    if ts is None:
        raise ValueError("timestamp is required")
    ts = ensure_aware(ts)

    # Retrieve image from Redis using event UUID

    event_id = UUID(data["id"])
    screenshot = retrieve_image_from_redis(event_id)

    if screenshot is None:
        logger.warning(
            "Dropping desktop screenshot event {event_id}: image expired or missing from Redis",
            event_id=event_id,
        )
        return None

    data = {**data, "timestamp": ts, "screenshot": screenshot}
    return DesktopInputScreenshotEvent.model_validate(data)


def processed_event_to_payload(evt) -> tuple[str, datetime, dict[str, Any]]:
    """Map processed desktop event to a (event_type, event_time, payload_json) triple.

    Uses Pydantic's model_dump to serialize the event with proper mode='json' for ISO timestamps.
    """
    match evt:
        case ProcessedDesktopCheckScreenshotEventOCR():
            return "desktop_screenshot_ocr", evt.timestamp, evt.model_dump(mode="json")
        case ProcessedDesktopCheckScreenshotEventVLM():
            return "desktop_screenshot_vlm", evt.timestamp, evt.model_dump(mode="json")
        case _:
            raise TypeError(f"Unexpected processed desktop event type: {type(evt)}")


@dramatiq.actor
async def process_desktop_screenshot_job(data: dict[str, Any]) -> None:
    """Dramatiq async actor: process a desktop screenshot event and publish to stream.

    Retrieves the image from Redis using the event UUID.
    Performs OCR/VLM processing and publishes a compact payload to the Valkey stream.
    """
    # Ensure DB adapters/converters are registered in this worker process
    await actor_init()

    # Retrieve image from Redis; skip if expired
    desktop_evt = build_desktop_event_from_payload(data)
    if desktop_evt is None:
        # Image expired/missing - log already emitted by build_desktop_event_from_payload
        return

    async with get_db_connection(include_uuid_func=False) as conn:
        user_settings = await select_user_settings(conn)
        if not user_settings:
            raise RuntimeError("Missing user settings")

    # Run the processing (may use OCR/VLM and small LLM passes)
    processed = await process_desktop_check(desktop_evt, user_settings=user_settings)

    # Sanitize PII in text-bearing fields before publishing (synchronously)
    match processed:
        case ProcessedDesktopCheckScreenshotEventOCR():
            sanitized = sanitize_text(processed.image_text)
            processed = processed.model_copy(update={"image_text": sanitized})
        case ProcessedDesktopCheckScreenshotEventVLM():
            sanitized = sanitize_text(processed.llm_description)
            processed = processed.model_copy(update={"llm_description": sanitized})

    event_type, event_time, payload = processed_event_to_payload(processed)
    payload_json = json.dumps(payload)

    # Publish to Valkey stream
    _ = xadd_source_event(
        event_type=event_type, timestamp=event_time, payload_json=payload_json
    )
    logger.debug("Published desktop processed event to stream: {}", event_type)
