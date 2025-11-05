from __future__ import annotations

# ruff: noqa: I001
from datetime import datetime, timedelta, timezone
from typing import Optional

from dateutil.parser import isoparse
import dramatiq
from loguru import logger

import clepsy.entities as E
from clepsy.aggregator_worker import do_aggregation, do_empty_aggregation
from clepsy.config import config
from clepsy.entities import TimeSpan
from clepsy.infra.streams import xrange_source_events
from clepsy.infra import dramatiq_setup as _dramatiq_setup  # noqa: F401


def current_window(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(tz=timezone.utc)
    interval = config.aggregation_interval
    start = now - timedelta(seconds=now.timestamp() % interval.total_seconds())
    end = start + interval
    return start, end


def map_source_event(row) -> E.AggregationInputEvent:
    """Map a raw stream row to a typed AggregationInputEvent with Pydantic.

    Producers (desktop/mobile/afk) emit payloads we control, so we can
    directly validate the JSON into our models.
    """
    etype = row["event_type"]
    payload_json = row["payload_json"]
    match etype:
        case "desktop_screenshot_ocr":
            return E.ProcessedDesktopCheckScreenshotEventOCR.model_validate_json(
                payload_json
            )
        case "desktop_screenshot_vlm":
            return E.ProcessedDesktopCheckScreenshotEventVLM.model_validate_json(
                payload_json
            )
        case "mobile_app_usage":
            return E.MobileAppUsageEvent.model_validate_json(payload_json)
        case "desktop_afk_event":
            return E.DesktopInputAfkStartEvent.model_validate_json(payload_json)
        case _:
            raise ValueError(f"Unexpected etype {etype}")


@dramatiq.actor
async def aggregate_window(
    start_iso: str | None = None, end_iso: str | None = None
) -> None:
    """Dramatiq async actor: aggregate a specific time window.

    - If start/end are not provided, compute the current window.
    - Reads events from Valkey Streams and runs aggregation.
    """
    start: datetime
    end: datetime
    if start_iso and end_iso:
        start = isoparse(start_iso)
        end = isoparse(end_iso)
    else:
        start, end = current_window()

    logger.info("[Dramatiq] aggregate_window start={} end={}", start, end)

    # Query durable source events and run the existing aggregation pipeline.

    rows = xrange_source_events(start=start, end=end)

    window_span = TimeSpan(start_time=start, end_time=end)
    if not rows:
        logger.info("[Dramatiq] No source events in window; running empty aggregation")
        await do_empty_aggregation()
        return

    input_logs: list[E.AggregationInputEvent] = []
    for row in rows:
        mapped = map_source_event(row)
        if mapped is not None:
            input_logs.append(mapped)

    if not input_logs:
        logger.info(
            "[Dramatiq] No mappable source events in window; running empty aggregation"
        )
        await do_empty_aggregation()
        return

    await do_aggregation(input_logs=input_logs, aggregation_time_span=window_span)
