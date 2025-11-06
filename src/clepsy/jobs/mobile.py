from __future__ import annotations
# ruff: noqa: I001

import json
from datetime import datetime, timezone

import dramatiq
from loguru import logger
from clepsy.infra import dramatiq_setup as _dramatiq_setup  # noqa: F401

from clepsy.entities import MobileAppUsageEvent
from clepsy.modules.pii.sanitize import sanitize_text
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


@dramatiq.actor
def persist_mobile_app_usage_job(event_dict: dict) -> None:
    """Dramatiq async actor: anonymize (if needed) and publish mobile app usage event to stream."""
    evt = MobileAppUsageEvent.model_validate(event_dict)

    if evt.notification_text:
        evt.notification_text = sanitize_text(evt.notification_text)

    etype, etime, payload_json = serialize_mobile_event(evt)
    _ = xadd_source_event(event_type=etype, timestamp=etime, payload_json=payload_json)
    logger.debug("Published mobile app usage source_event to stream")
