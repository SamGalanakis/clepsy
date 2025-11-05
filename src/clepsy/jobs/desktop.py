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
from clepsy.utils import base64_to_pil_image


def ensure_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def deserialize_screenshot(image_b64: str):
    return base64_to_pil_image(image_b64)


def build_desktop_event_from_payload(
    data: dict[str, Any], image_b64: str
) -> DesktopInputScreenshotEvent:
    # Coerce timestamp to aware datetime
    ts = data.get("timestamp")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    if ts is None:
        raise ValueError("timestamp is required")
    ts = ensure_aware(ts)

    data = {**data, "timestamp": ts, "screenshot": deserialize_screenshot(image_b64)}
    return DesktopInputScreenshotEvent.model_validate(data)


def processed_event_to_payload(evt) -> tuple[str, datetime, dict[str, Any]]:
    """Map processed desktop event to a (event_type, event_time, payload_json) triple.

    event_type: one of 'desktop_screenshot_ocr' | 'desktop_screenshot_vlm'
    payload carries active_window, timestamp, and either image_text or llm_description, plus flags.
    """
    match evt:
        case ProcessedDesktopCheckScreenshotEventOCR():
            payload = {
                "active_window": {
                    "title": evt.active_window.title,
                    "app_name": evt.active_window.app_name,
                    "bbox": {
                        "left": evt.active_window.bbox.left,
                        "top": evt.active_window.bbox.top,
                        "width": evt.active_window.bbox.width,
                        "height": evt.active_window.bbox.height,
                    },
                },
                "timestamp": evt.timestamp.isoformat(),
                "image_text": evt.image_text,
                "image_text_post_processed_by_llm": evt.image_text_post_processed_by_llm,
            }
            return "desktop_screenshot_ocr", evt.timestamp, payload
        case ProcessedDesktopCheckScreenshotEventVLM():
            payload = {
                "active_window": {
                    "title": evt.active_window.title,
                    "app_name": evt.active_window.app_name,
                    "bbox": {
                        "left": evt.active_window.bbox.left,
                        "top": evt.active_window.bbox.top,
                        "width": evt.active_window.bbox.width,
                        "height": evt.active_window.bbox.height,
                    },
                },
                "timestamp": evt.timestamp.isoformat(),
                "llm_description": evt.llm_description,
            }
            return "desktop_screenshot_vlm", evt.timestamp, payload
        case _:
            raise TypeError(f"Unexpected processed desktop event type: {type(evt)}")


@dramatiq.actor
async def process_desktop_screenshot_job(data: dict[str, Any], image_b64: str) -> None:
    """Dramatiq async actor: process a desktop screenshot event and publish to stream.

    Performs OCR/VLM processing and publishes a compact payload to the Valkey stream.
    """
    # Ensure DB adapters/converters are registered in this worker process
    await actor_init()
    desktop_evt = build_desktop_event_from_payload(data, image_b64)
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
