from __future__ import annotations
# ruff: noqa: I001

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler import AsyncScheduler, ConflictPolicy, TaskDefaults
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.executors.async_ import AsyncJobExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from clepsy import utils
from clepsy.config import config
from clepsy.entities import GoalPeriod
from clepsy.jobs.aggregation import aggregate_window
from clepsy.jobs.sessions import run_sessionization_job
from clepsy.jobs.goals import run_update_previous_full_period_result_job
from clepsy.infra.valkey_client import get_connection

logger = logging.getLogger("apscheduler")

# Persistent datastore for APScheduler v4
_data_store = SQLAlchemyDataStore(
    engine_or_url=config.ap_scheduler_db_connection_string
)

task_defaults = TaskDefaults(
    job_executor="async",
    misfire_grace_time=timedelta(days=365),
    max_running_jobs=5,
    metadata={},
)


# Module-level scheduler instance (use as async context manager in main.py)
scheduler = AsyncScheduler(
    data_store=_data_store,
    max_concurrent_jobs=10,
    job_executors={"async": AsyncJobExecutor()},
    logger=logger,
    task_defaults=task_defaults,
)


def build_scheduler() -> AsyncScheduler:
    """Return the module-level scheduler (kept for compatibility)."""
    return scheduler


# Task IDs for persisted schedules (avoid pickling callables)
TASK_ID_SESSIONIZATION = "tasks.sessionization"
TASK_ID_AGGREGATION = "tasks.aggregation"
TASK_ID_GOAL_PREV_FULL_PERIOD = "tasks.goal_prev_full_period"


async def init_schedules(sched: AsyncScheduler) -> None:
    """Register core recurring schedules on an initialized scheduler.

    Must be called after entering the scheduler's async context manager.
    Uses a Redis lock to ensure only one worker initializes schedules.
    """

    conn = get_connection()
    lock_key = "scheduler:init_lock"
    lock_acquired = False

    try:
        # Try to acquire lock with 10 second timeout (first worker wins)
        lock_acquired = conn.set(lock_key, "1", nx=True, ex=10)

        if not lock_acquired:
            logger.info("Another worker is initializing schedules, skipping...")
            return

        logger.info("Acquired scheduler init lock, registering schedules...")

        # Register resolvable task IDs to avoid pickling callables
        await sched.configure_task(  # type: ignore[attr-defined]
            func_or_task_id=TASK_ID_SESSIONIZATION, func=run_sessionization_job.send
        )
        await sched.configure_task(  # type: ignore[attr-defined]
            func_or_task_id=TASK_ID_AGGREGATION, func=aggregate_window.send
        )
        await sched.configure_task(  # type: ignore[attr-defined]
            func_or_task_id=TASK_ID_GOAL_PREV_FULL_PERIOD,
            func=run_update_previous_full_period_result_job.send,
        )

        await sched.add_schedule(  # type: ignore[attr-defined]
            TASK_ID_SESSIONIZATION,
            trigger=IntervalTrigger(
                seconds=int(config.session_window_length.total_seconds())
            ),
            id="sessionization",
            conflict_policy=ConflictPolicy.replace,
        )
        await sched.add_schedule(  # type: ignore[attr-defined]
            TASK_ID_AGGREGATION,
            trigger=IntervalTrigger(
                seconds=int(config.aggregation_interval.total_seconds())
            ),
            id="aggregation",
            conflict_policy=ConflictPolicy.replace,
        )

        logger.info("Successfully registered schedules")
    finally:
        # Release lock if we acquired it
        if lock_acquired:
            conn.delete(lock_key)


# ---- Goal cron helpers (reused from main branch with adjustments) ----
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


def cron_trigger_for_period(
    *, period: GoalPeriod, min_first_start_time: datetime
) -> CronTrigger:
    """Create a CronTrigger that fires when a period ends.

    - DAY: fires daily at 00:00 (the moment the previous day ends)
    - WEEK: fires Mondays at 00:00 (weeks start Monday, so previous week ends then)
    - MONTH: fires on the 1st of each month at 00:00 (previous month just ended)

    The first occurrence will be strictly after `min_first_start_time`.
    The cron's timezone is taken from `min_first_start_time` (or UTC if naive).
    """
    tz = min_first_start_time.tzinfo or dt_timezone.utc

    start_after = (
        min_first_start_time
        if min_first_start_time.tzinfo
        else min_first_start_time.replace(tzinfo=tz)
    )
    start_after = start_after + timedelta(seconds=1)

    match period:
        case GoalPeriod.DAY:
            return CronTrigger(
                hour=0, minute=0, second=0, timezone=tz, start_time=start_after
            )
        case GoalPeriod.WEEK:
            return CronTrigger(
                day_of_week="mon",
                hour=0,
                minute=0,
                second=0,
                timezone=tz,
                start_time=start_after,
            )
        case GoalPeriod.MONTH:
            return CronTrigger(
                day=1, hour=0, minute=0, second=0, timezone=tz, start_time=start_after
            )
        case _:
            raise ValueError(f"Unsupported GoalPeriod: {period}")


def cron_trigger_given_period_and_created_at(
    *, period: GoalPeriod, created_at: datetime
) -> CronTrigger:
    next_period_range = get_next_period_range(relative_to=created_at, period=period)
    return cron_trigger_for_period(
        period=period, min_first_start_time=next_period_range[1] - timedelta(seconds=1)
    )


async def schedule_goal_previous_period_update(
    *, goal_id: int, period: GoalPeriod, timezone_str: str | None, created_at: datetime
) -> None:
    """Schedule periodic updates for a goal's previous full period result.

    Uses the goal's period and timezone to align execution at period boundaries.
    """
    tzinfo = None
    if timezone_str:
        try:
            tzinfo = ZoneInfo(timezone_str)
        except ZoneInfoNotFoundError:  # noqa: BLE001
            tzinfo = dt_timezone.utc
    else:
        tzinfo = dt_timezone.utc

    created_at_tz = created_at.astimezone(tzinfo)
    trig = cron_trigger_given_period_and_created_at(
        period=period, created_at=created_at_tz
    )
    sched = build_scheduler()
    # Ensure task is configured (idempotent)
    await sched.configure_task(  # type: ignore[attr-defined]
        func_or_task_id=TASK_ID_GOAL_PREV_FULL_PERIOD,
        func=run_update_previous_full_period_result_job.send,
    )
    await sched.add_schedule(  # type: ignore[attr-defined]
        TASK_ID_GOAL_PREV_FULL_PERIOD,
        trigger=trig,
        id=f"goal_prev_full_period:{goal_id}",
        args=(goal_id,),
        conflict_policy=ConflictPolicy.replace,
    )


async def unschedule_goal_previous_period_update(*, goal_id: int) -> None:
    sched = build_scheduler()
    schedule_id = f"goal_prev_full_period:{goal_id}"
    # Best-effort removal; ignore if not found
    try:
        await sched.remove_schedule(schedule_id)  # type: ignore[attr-defined]
    except (LookupError, ValueError, AttributeError):  # noqa: BLE001
        pass
