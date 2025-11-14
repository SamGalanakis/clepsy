from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiosqlite
from loguru import logger

from clepsy import utils
from clepsy.config import config
from clepsy.db import get_db_connection
from clepsy.db.queries import delete_scheduled_job_by_key, upsert_scheduled_job
from clepsy.entities import GoalPeriod, JobType, ScheduledJob
from clepsy.infra.valkey_client import get_connection
from clepsy.jobs.scheduler_tick import scheduler_tick


AGGREGATION_SCHEDULE_KEY = "aggregation_window"
SESSIONIZATION_SCHEDULE_KEY = "sessions_sessionization"
GOAL_PREV_PERIOD_KEY_PREFIX = "goal_prev_period:"
SCHEDULER_INIT_LOCK_KEY = "scheduler:init_lock"


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def align_interval_forward(now: datetime, interval: timedelta) -> datetime:
    if interval.total_seconds() <= 0:
        raise ValueError("Interval must be positive")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    seconds = int(interval.total_seconds())
    remainder = int(now.timestamp()) % seconds
    if remainder == 0:
        aligned = now
    else:
        aligned = now + timedelta(seconds=seconds - remainder)
    return aligned.replace(microsecond=0)


def cron_expr_for_interval(interval: timedelta) -> str:
    total_seconds = int(interval.total_seconds())
    if total_seconds <= 0:
        raise ValueError("Interval must be positive")

    total_minutes, remainder = divmod(total_seconds, 60)
    if total_minutes <= 1 or remainder != 0:
        return "* * * * *"
    return f"*/{total_minutes} * * * *"


def cron_expr_for_goal_period(period: GoalPeriod) -> str:
    match period:
        case GoalPeriod.DAY:
            return "0 0 * * *"
        case GoalPeriod.WEEK:
            return "0 0 * * 1"
        case GoalPeriod.MONTH:
            return "0 0 1 * *"
        case _:
            raise ValueError(f"Unsupported GoalPeriod: {period}")


def get_next_period_range(
    *, relative_to: datetime, period: GoalPeriod
) -> tuple[datetime, datetime]:
    match period:
        case GoalPeriod.DAY:
            start = utils.datetime_to_end_of_day(relative_to)
            end = start + timedelta(days=1)
        case GoalPeriod.WEEK:
            start = utils.datetime_to_end_of_week(relative_to)
            end = start + timedelta(weeks=1)
        case GoalPeriod.MONTH:
            start = utils.datetime_to_end_of_month(relative_to)
            end = utils.datetime_to_end_of_month(start + timedelta(days=1))
        case _:
            raise ValueError(f"Unsupported GoalPeriod: {period}")
    return start, end


def resolve_timezone(timezone_str: str | None) -> ZoneInfo:
    if timezone_str:
        try:
            return ZoneInfo(timezone_str)
        except ZoneInfoNotFoundError:  # noqa: BLE001
            logger.warning("Unknown timezone '{}'; defaulting to UTC", timezone_str)
    return ZoneInfo("UTC")


async def ensure_core_schedules(now: datetime) -> None:
    aggregation_job = ScheduledJob(
        schedule_key=AGGREGATION_SCHEDULE_KEY,
        job_type=JobType.AGGREGATION_WINDOW,
        cron_expr=cron_expr_for_interval(config.aggregation_interval),
        next_run_at=align_interval_forward(now, config.aggregation_interval),
    )

    session_job = ScheduledJob(
        schedule_key=SESSIONIZATION_SCHEDULE_KEY,
        job_type=JobType.SESSIONIZATION,
        cron_expr=cron_expr_for_interval(config.session_window_length),
        next_run_at=align_interval_forward(now, config.session_window_length),
    )

    async with get_db_connection(
        start_transaction=True, transaction_type="IMMEDIATE"
    ) as conn:
        await upsert_scheduled_job(conn, job=aggregation_job)
        await upsert_scheduled_job(conn, job=session_job)


async def initialize_scheduler() -> None:
    lock_conn = get_connection(decode_responses=True)
    lock_acquired = False

    try:
        lock_acquired = lock_conn.set(SCHEDULER_INIT_LOCK_KEY, "1", nx=True, ex=30)
        if not lock_acquired:
            logger.info("Another worker is initializing scheduler; skipping core setup")
            return

        now = utc_now()
        logger.info("Initializing scheduler core schedules at {}", now.isoformat())
        await ensure_core_schedules(now)

        # Kick the scheduler tick loop once; it will reschedule itself.
        scheduler_tick.send()
    finally:
        if lock_acquired:
            lock_conn.delete(SCHEDULER_INIT_LOCK_KEY)


async def schedule_goal_previous_period_update(
    *,
    goal_id: int,
    period: GoalPeriod,
    timezone_str: str | None,
    created_at: datetime,
    conn: aiosqlite.Connection,
) -> None:
    tzinfo = resolve_timezone(timezone_str)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    reference = datetime.now(tzinfo)
    created_at_local = created_at.astimezone(tzinfo)
    if created_at_local > reference:
        reference = created_at_local

    next_boundary, _ = get_next_period_range(relative_to=reference, period=period)
    next_run_utc = next_boundary.astimezone(timezone.utc)

    payload = {
        "goal_id": goal_id,
    }

    job = ScheduledJob(
        schedule_key=f"{GOAL_PREV_PERIOD_KEY_PREFIX}{goal_id}",
        job_type=JobType.GOAL_UPDATE_PREVIOUS_PERIOD,
        cron_expr=cron_expr_for_goal_period(period),
        next_run_at=next_run_utc,
        payload=payload,
    )

    await upsert_scheduled_job(conn, job=job)


async def unschedule_goal_previous_period_update(
    *, goal_id: int, conn: aiosqlite.Connection | None = None
) -> None:
    schedule_key = f"{GOAL_PREV_PERIOD_KEY_PREFIX}{goal_id}"

    if conn is None:
        async with get_db_connection(start_transaction=True) as owned_conn:
            await delete_scheduled_job_by_key(owned_conn, schedule_key=schedule_key)
    else:
        await delete_scheduled_job_by_key(conn, schedule_key=schedule_key)


__all__ = [
    "initialize_scheduler",
    "schedule_goal_previous_period_update",
    "unschedule_goal_previous_period_update",
]
