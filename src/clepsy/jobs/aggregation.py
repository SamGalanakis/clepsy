# ruff: noqa: I001
from datetime import datetime, timezone
from time import perf_counter

import dramatiq
from loguru import logger

import clepsy.entities as E
from clepsy.aggregator_worker import do_aggregation, do_empty_aggregation
from clepsy.config import config
from clepsy.entities import TimeSpan
from clepsy.infra import dramatiq_setup as _dramatiq_setup  # noqa: F401
from clepsy.infra.streams import xrange_source_events
from clepsy.jobs.actor_init import actor_init
from clepsy.db import get_db_connection


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


async def aggregate_window() -> None:
    async with get_db_connection():
        pass
    end = datetime.now(tz=timezone.utc)
    start = end - config.aggregation_interval

    logger.info(
        "[Dramatiq] aggregate_window start={} end={} (grace={})",
        start,
        end,
        config.aggregation_grace_period,
    )

    fetch_started = perf_counter()
    # Query durable source events with grace on the upper bound to capture late arrivals.
    # We'll filter strictly by event timestamp within [start, end) afterwards.
    effective_end = end + config.aggregation_grace_period
    rows = xrange_source_events(start=start, end=effective_end)
    logger.debug(
        "[aggregate_window] fetched {row_count} rows in {duration:.2f}s",
        row_count=len(rows),
        duration=perf_counter() - fetch_started,
    )

    window_span = TimeSpan(start_time=start, end_time=end)
    if not rows:
        logger.info("[Dramatiq] No source events in window; running empty aggregation")
        await do_empty_aggregation()
        return

    input_logs: list[E.AggregationInputEvent] = []
    transform_started = perf_counter()
    for row in rows:
        mapped = map_source_event(row)
        if mapped is not None:
            # Filter strictly by event time within [start, end)
            evt_ts = mapped.timestamp
            if evt_ts.tzinfo is None:
                evt_ts = evt_ts.replace(tzinfo=timezone.utc)
            if start <= evt_ts < end:
                input_logs.append(mapped)

    if not input_logs:
        logger.info(
            "[Dramatiq] No mappable source events in window; running empty aggregation"
        )
        await do_empty_aggregation()
        return

    # Ensure deterministic ordering by event timestamp
    input_logs.sort(key=lambda e: e.timestamp)
    logger.debug(
        "[aggregate_window] prepared {log_count} logs in {duration:.2f}s",
        log_count=len(input_logs),
        duration=perf_counter() - transform_started,
    )

    aggregation_started = perf_counter()
    await do_aggregation(input_logs=input_logs, aggregation_time_span=window_span)
    logger.info(
        "[aggregate_window] aggregation completed in {duration:.2f}s",
        duration=perf_counter() - aggregation_started,
    )


@dramatiq.actor
async def aggregate_window_job(
    start_iso: str | None = None, end_iso: str | None = None
) -> None:
    await actor_init()
    await aggregate_window(start_iso=start_iso, end_iso=end_iso)
