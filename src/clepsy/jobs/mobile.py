from __future__ import annotations
# ruff: noqa: I001

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


@dramatiq.actor
def persist_mobile_app_usage_job(event_dict: dict) -> None:
    """Dramatiq async actor: anonymize (if needed) and publish mobile app usage event to stream."""

    if notification_text := event_dict["notification_text"]:
        event_dict["notification_text"] = sanitize_text(notification_text)
    evt = MobileAppUsageEvent.model_validate(event_dict)

    etype = "mobile_app_usage"
    etime = ensure_aware(datetime.fromisoformat(event_dict["timestamp"]))
    _ = xadd_source_event(
        event_type=etype, timestamp=etime, payload_json=evt.model_dump_json()
    )
    logger.debug("Published mobile app usage source_event to stream")
