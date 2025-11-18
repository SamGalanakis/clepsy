# ruff: noqa: I001
from datetime import datetime, timezone
from time import perf_counter

import dramatiq
from loguru import logger

import clepsy.entities as E
from clepsy.aggregator_worker import do_empty_aggregation, do_aggregation
from clepsy.config import config
from clepsy.entities import TimeSpan
from clepsy.infra import dramatiq_setup as _dramatiq_setup  # noqa: F401
from clepsy.infra.streams import xrange_source_events, get_oldest_source_event_timestamp
from clepsy.jobs.actor_init import actor_init
from clepsy.db import get_db_connection
from clepsy.db.queries import (
    select_latest_aggregation,
    update_scheduled_job_next_run_at,
)


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


async def aggregate_window(schedule_id: int) -> None:
    current_time = datetime.now(tz=timezone.utc)

    oldest_source_event_timestamp = get_oldest_source_event_timestamp()

    async with get_db_connection() as conn:
        previous_aggregation = await select_latest_aggregation(conn)

    if not previous_aggregation:
        # First run: start at the oldest event (if available)
        if oldest_source_event_timestamp:
            start = oldest_source_event_timestamp
        else:
            # No events yet, start from current_time - interval - grace_period
            start = (
                current_time
                - config.aggregation_interval
                - config.aggregation_grace_period
            )
    else:
        # Subsequent runs: start where previous aggregation ended
        start = previous_aggregation.end_time
        # If oldest source event is newer than previous aggregation end,
        # skip empty periods and start from where events actually begin
        # (This handles cases where the server was down and events only resumed recently)
        if oldest_source_event_timestamp and oldest_source_event_timestamp > start:
            logger.info(
                "Skipping empty period: previous_aggregation.end_time={}, oldest_source_event={}",
                start,
                oldest_source_event_timestamp,
            )
            start = oldest_source_event_timestamp
        # Note: If oldest_source_event_timestamp < start, this means there are older events
        # that should have been processed. This shouldn't happen in normal operation, but
        # if it does (e.g., backfill), we'll process from previous_aggregation.end_time
        # and those older events will remain unprocessed until manually handled.

    # Windows are always fixed length: [start, start + interval)
    end = start + config.aggregation_interval

    # Check if we can safely process this window
    # We need current_time >= start + interval + grace_period to ensure we're lagging by at least grace_period
    if (
        current_time - start
        < config.aggregation_interval + config.aggregation_grace_period
    ):
        logger.info(
            "Aggregation too close to real-time. start={}, end={}, current_time={}, required_lag={}",
            start,
            end,
            current_time,
            config.aggregation_interval + config.aggregation_grace_period,
        )
        # Schedule next run at: start + interval + grace_period
        # This ensures we're always lagging by interval + grace_period
        next_aggregation_time = (
            start + config.aggregation_interval + config.aggregation_grace_period
        )
        logger.info(
            "[Dramatiq] Next aggregation scheduled at {}",
            next_aggregation_time,
        )

        async with get_db_connection() as update_conn:
            await update_scheduled_job_next_run_at(
                update_conn,
                schedule_id=schedule_id,
                next_run_at=next_aggregation_time,
            )
        return

    effective_end = end + config.aggregation_grace_period
    schedule_update = E.ScheduleUpdate(
        schedule_id=schedule_id,
        next_run_at=end + config.aggregation_interval + config.aggregation_grace_period,
    )

    logger.info(
        "[Dramatiq] aggregate_window start={} end={} (grace={})",
        start,
        end,
        config.aggregation_grace_period,
    )

    fetch_started = perf_counter()
    # Query durable source events with grace on the upper bound to capture late arrivals.
    # We'll filter strictly by event timestamp within [start, end) afterwards.
    rows = xrange_source_events(start=start, end=effective_end)
    logger.debug(
        "[aggregate_window] fetched {row_count} rows in {duration:.2f}s",
        row_count=len(rows),
        duration=perf_counter() - fetch_started,
    )

    window_span = TimeSpan(start_time=start, end_time=end)
    if not rows:
        logger.info("[Dramatiq] No source events in window; running empty aggregation")
        await do_empty_aggregation(schedule_update=schedule_update)
        return

    input_logs: list[E.AggregationInputEvent] = []
    transform_started = perf_counter()
    for row in rows:
        mapped = map_source_event(row)
        evt_ts = mapped.timestamp
        if evt_ts.tzinfo is None:
            evt_ts = evt_ts.replace(tzinfo=timezone.utc)
        if start <= evt_ts < end:
            input_logs.append(mapped)

    if not input_logs:
        logger.info(
            "[Dramatiq] No mappable source events in window; running empty aggregation"
        )
        await do_empty_aggregation(schedule_update=schedule_update)
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
        schedule_update=schedule_update,
    )


@dramatiq.actor
async def aggregate_window_job(schedule_id: int) -> None:
    await actor_init()
    await aggregate_window(schedule_id=schedule_id)
