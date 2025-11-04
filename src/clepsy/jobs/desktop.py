from __future__ import annotations
# ruff: noqa: I001

import asyncio
import io
import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from PIL import Image

from clepsy.db.db import get_db_connection
from clepsy.db.queries import select_user_settings
from clepsy.infra.streams import xadd_source_event
from clepsy.entities import DesktopInputScreenshotEvent
from clepsy.modules.aggregator.desktop_source.worker import process_desktop_check


def _ensure_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _deserialize_screenshot(image_bytes: bytes) -> Image.Image:
    with io.BytesIO(image_bytes) as bio:
        img = Image.open(bio)
        img.load()
        return img


def _build_desktop_event_from_payload(
    data: dict[str, Any], image_bytes: bytes
) -> DesktopInputScreenshotEvent:
    # Coerce timestamp to aware datetime
    ts = data.get("timestamp")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    if ts is None:
        raise ValueError("timestamp is required")
    ts = _ensure_aware(ts)

    data = {**data, "timestamp": ts, "screenshot": _deserialize_screenshot(image_bytes)}
    return DesktopInputScreenshotEvent.model_validate(data)


def _processed_event_to_payload(evt) -> tuple[str, datetime, dict[str, Any]]:
    """Map processed desktop event to a (event_type, event_time, payload_json) triple.

    event_type: one of 'desktop_screenshot_ocr' | 'desktop_screenshot_vlm'
    payload carries active_window, timestamp, and either image_text or llm_description, plus flags.
    """
    from clepsy.entities import (
        ProcessedDesktopCheckScreenshotEventOCR,
        ProcessedDesktopCheckScreenshotEventVLM,
    )

    if isinstance(evt, ProcessedDesktopCheckScreenshotEventOCR):
        payload = {
            "active_window": {
                "title": evt.active_window.title,
                "app_name": evt.active_window.app_name,
                "is_active": evt.active_window.is_active,
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
    elif isinstance(evt, ProcessedDesktopCheckScreenshotEventVLM):
        payload = {
            "active_window": {
                "title": evt.active_window.title,
                "app_name": evt.active_window.app_name,
                "is_active": evt.active_window.is_active,
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
    else:  # pragma: no cover - defensive
        raise TypeError(f"Unexpected processed desktop event type: {type(evt)}")


def process_desktop_screenshot_job(data: dict[str, Any], image_bytes: bytes) -> None:
    """RQ job: process a desktop screenshot event and persist a durable source_event row.

    This replaces in-memory publish/subscribe. It performs OCR/VLM processing using
    the same logic as the prior DesktopCheckWorker, then stores a pared-down payload
    needed for aggregation in the source_events table.
    """

    async def _inner():
        desktop_evt = _build_desktop_event_from_payload(data, image_bytes)
        async with get_db_connection(include_uuid_func=False) as conn:
            user_settings = await select_user_settings(conn)
            if not user_settings:
                raise RuntimeError("Missing user settings")

        # Run the processing (may use OCR/VLM and small LLM passes)
        processed = await process_desktop_check(
            desktop_evt, user_settings=user_settings
        )

        event_type, event_time, payload = _processed_event_to_payload(processed)
        payload_json = json.dumps(payload)

        # Publish to Valkey stream rather than DB
        _ = xadd_source_event(
            event_type=event_type, timestamp=event_time, payload_json=payload_json
        )
        logger.debug("Published desktop processed event to stream: {}", event_type)

    asyncio.run(_inner())


def persist_desktop_afk_event_job(event_dict: dict) -> None:
    """Persist a desktop AFK start event as a source_event.

    This is currently not used by aggregation, but kept for future use and parity with prior API.
    """

    async def _inner():
        # Validate and normalize timestamp
        ts = event_dict.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        if ts is None:
            ts = datetime.now(tz=timezone.utc)
        ts = _ensure_aware(ts)

        payload_json = json.dumps(
            {
                "timestamp": ts.isoformat(),
                "time_since_last_user_activity": str(
                    event_dict.get("time_since_last_user_activity")
                ),
            }
        )
        _ = xadd_source_event(
            event_type="desktop_afk_event", timestamp=ts, payload_json=payload_json
        )
        logger.debug("Published desktop AFK source_event to stream")

    asyncio.run(_inner())
