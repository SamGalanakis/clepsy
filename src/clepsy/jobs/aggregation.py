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
from clepsy.infra.streams import xrange_source_events
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
    async with get_db_connection() as conn:
        previous_aggregation = await select_latest_aggregation(conn)
    if previous_aggregation:
        previous_aggregation_end_time = previous_aggregation.end_time

        if previous_aggregation_end_time - current_time < config.aggregation_interval:
            logger.info("Aggregation too close to previous aggregation")
            next_aggregation_time = (
                previous_aggregation_end_time + config.aggregation_interval
            )
            logger.info(
                "[Dramatiq] Next aggregation scheduled at {}",
                next_aggregation_time,
            )

            await update_scheduled_job_next_run_at(
                conn,
                schedule_id=schedule_id,
                next_run_at=next_aggregation_time,
            )
            return
        else:
            start = previous_aggregation_end_time
            end = start + config.aggregation_interval

    else:
        end = current_time - config.aggregation_grace_period
        start = end - config.aggregation_interval

    effective_end = end + config.aggregation_grace_period

    schedule_update = E.ScheduleUpdate(
        schedule_id=schedule_id, next_run_at=effective_end + config.aggregation_interval
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
