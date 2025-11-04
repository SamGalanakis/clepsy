from __future__ import annotations
# ruff: noqa: I001

import asyncio
import json
from datetime import datetime, timezone

from loguru import logger

from clepsy.config import config
from clepsy.entities import MobileAppUsageEvent
from clepsy.modules.pii.pii import DEFAULT_PII_ENTITY_TYPES, anonymize_text
from clepsy.infra.streams import xadd_source_event


def ensure_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def serialize_mobile_event(event: MobileAppUsageEvent) -> tuple[str, datetime, str]:
    payload = {
        "app_label": event.app_label,
        "package_name": event.package_name,
        "activity_name": event.activity_name,
        "media_metadata": event.media_metadata,
        "notification_text": event.notification_text,
        "timestamp": ensure_aware(event.timestamp).isoformat(),
    }
    return "mobile_app_usage", event.timestamp, json.dumps(payload)


def persist_mobile_app_usage_job(event_dict: dict) -> None:
    """RQ job to anonymize (if needed) and persist a mobile app usage event as a source_event."""

    async def inner():
        # Pydantic validation
        evt = MobileAppUsageEvent.model_validate(event_dict)

        if evt.notification_text:
            evt.notification_text = await asyncio.to_thread(
                anonymize_text,
                text=evt.notification_text,
                entity_types=DEFAULT_PII_ENTITY_TYPES,
                threshold=config.gliner_pii_threshold,
            )

        etype, etime, payload_json = serialize_mobile_event(evt)
        _ = xadd_source_event(
            event_type=etype, timestamp=etime, payload_json=payload_json
        )
        logger.debug("Published mobile app usage source_event to stream")

    asyncio.run(inner())
