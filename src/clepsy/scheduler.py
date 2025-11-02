from datetime import datetime, timedelta, timezone
import logging

from apscheduler import AsyncScheduler, ConflictPolicy, TaskDefaults
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.executors.async_ import AsyncJobExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from clepsy import utils
from clepsy.config import config
from clepsy.entities import GoalPeriod
from clepsy.modules.goals.calculate_goals import (
    update_previous_full_period_goal_result_job,
)
from clepsy.modules.sessions.tasks import run_sessionization


logger = logging.getLogger("apscheduler")

data_store = SQLAlchemyDataStore(engine_or_url=config.ap_scheduler_db_connection_string)
max_concurrent_jobs = 10

task_defaults = TaskDefaults(
    job_executor="async",
    misfire_grace_time=timedelta(days=365),
    max_running_jobs=5,
    metadata={},
)

scheduler = AsyncScheduler(
    data_store=data_store,
    max_concurrent_jobs=max_concurrent_jobs,
    job_executors={"async": AsyncJobExecutor()},
    logger=logger,
)


async def init_schedules():
    await scheduler.add_schedule(
        func_or_task_id=run_sessionization,
        trigger=IntervalTrigger(seconds=config.session_window_length.total_seconds()),
        id="run_sessionization",
        conflict_policy=ConflictPolicy.replace,
    )

    await scheduler.configure_task(
        func_or_task_id="update_previous_full_period_goal_result",
        func=update_previous_full_period_goal_result_job,
    )


def get_next_period_range(
    relative_to: datetime, period: GoalPeriod
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


def cron_trigger_given_period_and_created_at(
    period: GoalPeriod, created_at: datetime
) -> CronTrigger:
    next_period_range = get_next_period_range(relative_to=created_at, period=period)
    return cron_trigger_for_period(
        period=period, min_first_start_time=next_period_range[1] - timedelta(seconds=1)
    )


def cron_trigger_for_period(
    period: GoalPeriod, min_first_start_time: datetime
) -> CronTrigger:
    """Create a CronTrigger that fires when a period ends.

    - DAY: fires daily at 00:00 (the moment the previous day ends)
    - WEEK: fires Mondays at 00:00 (weeks start Monday, so previous week ends then)
    - MONTH: fires on the 1st of each month at 00:00 (previous month just ended)

    The first occurrence will be strictly after `min_first_start_time`.
    The cron's timezone is taken from `min_first_start_time` (or UTC if naive).
    """
    tz = min_first_start_time.tzinfo or timezone.utc

    # Ensure first fire is strictly after the provided timestamp
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
            # Monday 00:00 (end of previous week)
            return CronTrigger(
                day_of_week="mon",
                hour=0,
                minute=0,
                second=0,
                timezone=tz,
                start_time=start_after,
            )
        case GoalPeriod.MONTH:
            # First of month 00:00 (end of previous month)
            return CronTrigger(
                day=1, hour=0, minute=0, second=0, timezone=tz, start_time=start_after
            )
        case _:
            raise ValueError(f"Unsupported GoalPeriod: {period}")
