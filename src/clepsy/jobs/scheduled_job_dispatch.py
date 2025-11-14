from typing import Awaitable, cast

import dramatiq
from loguru import logger

from clepsy.db import get_db_connection, queries as db_queries
from clepsy.entities import DBScheduledJob, JobType, ScheduleStatus
from clepsy.jobs import scheduler_tick
from clepsy.jobs.actor_init import actor_init
from clepsy.jobs.aggregation import aggregate_window
from clepsy.jobs.goals import (
    run_update_current_progress_job,
    run_update_previous_full_period_result_job,
)
from clepsy.jobs.sessions import run_sessionization_job


async def dispatch_job(job_type: JobType, payload: dict | None = None) -> None:
    """Execute a scheduled job within the current Dramatiq worker.

    Uses structural pattern matching to ensure exhaustive handling of registered
    job types. Raises a ValueError if the requested job type is unknown.
    """

    data = dict(payload or {})

    match job_type:
        case JobType.GOAL_UPDATE_CURRENT_PROGRESS:
            await cast(Awaitable[None], run_update_current_progress_job.fn(**data))
        case JobType.GOAL_UPDATE_PREVIOUS_PERIOD:
            await cast(
                Awaitable[None],
                run_update_previous_full_period_result_job.fn(**data),
            )
        case JobType.AGGREGATION_WINDOW:
            await cast(Awaitable[None], aggregate_window.fn(**data))
        case JobType.SESSIONIZATION:
            await cast(Awaitable[None], run_sessionization_job.fn(**data))
        case _ as unknown:
            raise ValueError(f"Unhandled job type {unknown!r}")


@dramatiq.actor
async def run_scheduled_job(job_dict: dict) -> None:
    job = DBScheduledJob.model_validate(job_dict)
    await actor_init()

    status_on_completion: ScheduleStatus | None = None

    try:
        await dispatch_job(job.job_type, job.payload)
    except Exception:
        status_on_completion = ScheduleStatus.ERROR
        logger.exception(
            "[RunScheduledJob] job {} ({}) failed",
            job.id,
            job.job_type.value,
        )
        raise
    finally:
        try:
            async with get_db_connection() as conn:
                await db_queries.decrement_scheduled_job_running_count(
                    conn,
                    schedule_id=job.id,
                    new_status=status_on_completion,
                )
        except Exception:
            logger.exception(
                "[RunScheduledJob] failed to finalize schedule {}",
                job.schedule_key,
            )
        scheduler_tick.scheduler_tick.send()
