from time import perf_counter

import dramatiq
from loguru import logger

from clepsy.db import get_db_connection, queries as db_queries
from clepsy.entities import DBScheduledJob, JobType, ScheduleStatus
from clepsy.jobs import scheduler_tick
from clepsy.jobs.actor_init import actor_init
from clepsy.jobs.aggregation import aggregate_window
from clepsy.jobs.goals import (
    run_update_current_progress,
    run_update_previous_full_period_result,
)
from clepsy.jobs.sessions import run_sessionization


async def dispatch_job(job_type: JobType, payload: dict | None = None) -> None:
    """Execute a scheduled job within the current Dramatiq worker.

    Uses structural pattern matching to ensure exhaustive handling of registered
    job types. Raises a ValueError if the requested job type is unknown.
    """

    data = dict(payload or {})
    logger.debug(
        "Dispatching {job_type} with payload {payload}",
        job_type=job_type,
        payload=payload,
    )
    started_at = perf_counter()
    match job_type:
        case JobType.GOAL_UPDATE_CURRENT_PROGRESS:
            await run_update_current_progress(**data)
        case JobType.GOAL_UPDATE_PREVIOUS_PERIOD:
            await run_update_previous_full_period_result(**data)
        case JobType.AGGREGATION_WINDOW:
            await aggregate_window(**data)
        case JobType.SESSIONIZATION:
            if data:
                logger.warning(
                    "[Dispatch] SESSIONIZATION job received unexpected payload %s",
                    data,
                )
            await run_sessionization()
        case _ as unknown:
            raise ValueError(f"Unhandled job type {unknown!r}")

    logger.debug(
        "Dispatched {job_type} finished in  {duration:.2f}s",
        job_type=job_type,
        duration=perf_counter() - started_at,
    )


@dramatiq.actor
async def run_scheduled_job(job_dict: dict) -> None:
    job = DBScheduledJob.model_validate(job_dict)
    await actor_init()

    status_on_completion: ScheduleStatus | None = None
    started_at = perf_counter()
    logger.info(
        "[RunScheduledJob] job {job_id} ({job_type}) starting",
        job_id=job.id,
        job_type=job.job_type.value,
    )

    try:
        await dispatch_job(job.job_type, job.payload)
    except Exception:
        status_on_completion = ScheduleStatus.ERROR
        logger.exception(
            "[RunScheduledJob] job {job_id} ({job_type}) failed after {duration:.2f}s",
            job_id=job.id,
            job_type=job.job_type.value,
            duration=perf_counter() - started_at,
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

    logger.info(
        "[RunScheduledJob] job {job_id} ({job_type}) completed in {duration:.2f}s",
        job_id=job.id,
        job_type=job.job_type.value,
        duration=perf_counter() - started_at,
    )
