from datetime import datetime, timedelta, timezone

from croniter import croniter
from croniter.croniter import CroniterBadCronError
from dateutil.parser import isoparse
import dramatiq
from loguru import logger

from clepsy.config import config
from clepsy.db import get_db_connection, queries as db_queries
from clepsy.entities import DBScheduledJob
from clepsy.jobs.actor_init import actor_init
from clepsy.jobs.scheduled_job_dispatch import run_scheduled_job
from clepsy.utils import datetime_to_eta, ensure_utc


def coerce_to_utc(now_iso: str | None) -> datetime:
    if now_iso is None:
        return datetime.now(tz=timezone.utc)

    parsed = isoparse(now_iso)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


MAX_CATCH_UP_STEPS = 256
DEFAULT_POLL_INTERVAL = timedelta(seconds=30)


def compute_next_run(job: DBScheduledJob, *, now: datetime) -> datetime | None:
    """Compute the next run time from cron expression.

    Returns None if the job has no cron expression (self-managed scheduling).
    """
    if job.cron_expr is None:
        return None

    base = ensure_utc(job.next_run_at)
    try:
        iterator = croniter(job.cron_expr, base)
        next_run = ensure_utc(iterator.get_next(datetime))
    except CroniterBadCronError as exc:
        raise ValueError(
            f"Invalid cron expression '{job.cron_expr}' for schedule {job.schedule_key}"
        ) from exc

    steps = 0
    while next_run <= now and steps < MAX_CATCH_UP_STEPS:
        next_run = ensure_utc(iterator.get_next(datetime))
        steps += 1

    if next_run <= now:
        # If we're behind, schedule for the next poll interval
        next_run = now + DEFAULT_POLL_INTERVAL

    return next_run


async def schedule_follow_up_tick(*, now: datetime) -> None:
    """Schedule the next tick using a static polling interval.

    We use a simple polling approach rather than trying to be smart about
    immediate retries, which can cause contention and rapid-fire retries.
    Jobs manage their own next_run_at, so we just need to check periodically.
    """
    # Always use the default poll interval for simplicity and reliability
    next_tick_at = ensure_utc(now) + DEFAULT_POLL_INTERVAL

    scheduler_tick.send_with_options(eta=datetime_to_eta(next_tick_at))
    logger.debug("[SchedulerTick] scheduled next tick at {}", next_tick_at.isoformat())


@dramatiq.actor
async def scheduler_tick() -> None:
    """Central scheduler tick.

    Reads the database for due schedules, safely advances their run cursor, and
    dispatches them for execution. Afterwards schedules the next tick using a
    static polling interval (30 seconds). Jobs manage their own next_run_at,
    so we just need to check periodically.
    """

    await actor_init()
    now = datetime.now(tz=timezone.utc)
    logger.debug("[SchedulerTick] evaluating schedules at {}", now.isoformat())

    # Read entire table once (no lock needed for read)
    try:
        async with get_db_connection(start_transaction=False) as conn:
            all_jobs: list[DBScheduledJob] = await db_queries.select_all_scheduled_jobs(
                conn
            )
    except Exception:
        logger.exception("[SchedulerTick] failed to fetch scheduled jobs")
        await schedule_follow_up_tick(now=now)
        return

    # Do all logic in Python
    timeout_threshold = now - config.scheduled_job_timeout
    timed_out_jobs: list[DBScheduledJob] = []
    due_jobs: list[DBScheduledJob] = []

    for job in all_jobs:
        # Check for timed out jobs
        if (
            job.running_count > 0
            and job.last_started_at is not None
            and ensure_utc(job.last_started_at) <= timeout_threshold
            and job.status != "disabled"
        ):
            timed_out_jobs.append(job)

        # Check for due jobs
        if (
            job.enabled
            and ensure_utc(job.next_run_at) <= now
            and job.running_count < job.max_concurrent
            and job.status != "disabled"
        ):
            due_jobs.append(job)

    # Release timed out jobs (write transaction only if needed)
    if timed_out_jobs:
        try:
            async with get_db_connection(start_transaction=True) as conn:
                for job in timed_out_jobs:
                    last_started = (
                        ensure_utc(job.last_started_at).isoformat()
                        if job.last_started_at
                        else "unknown"
                    )
                    logger.warning(
                        "[SchedulerTick] schedule {} timed out after {} (last_started={})",
                        job.schedule_key,
                        config.scheduled_job_timeout,
                        last_started,
                    )
                # Update all timed-out jobs in one query
                await db_queries.release_timed_out_scheduled_jobs(
                    conn,
                    timeout_threshold=timeout_threshold,
                    now=now,
                )
        except Exception:
            logger.exception("[SchedulerTick] failed to release timed-out schedules")

    # Process due jobs
    if not due_jobs:
        logger.debug("[SchedulerTick] no due schedules found")
    else:
        for job in due_jobs:
            logger.info(
                "[SchedulerTick] schedule {} ({}) due at {} (running={}/{})",
                job.schedule_key,
                job.job_type.value,
                job.next_run_at.isoformat(),
                job.running_count,
                job.max_concurrent,
            )

            new_next_run: datetime | None = None
            if job.cron_expr is not None:
                try:
                    new_next_run = compute_next_run(job, now=now)
                except ValueError:
                    logger.exception(
                        "[SchedulerTick] failed to compute next run for {}",
                        job.schedule_key,
                    )
                    continue
            else:
                # Job manages its own next_run_at, don't update it
                logger.debug(
                    "[SchedulerTick] schedule {} has no cron expression, will not update next_run_at",
                    job.schedule_key,
                )

            try:
                async with get_db_connection(start_transaction=True) as conn:
                    started = await db_queries.mark_scheduled_job_started(
                        conn,
                        schedule_id=job.id,
                        expected_next_run_at=job.next_run_at,
                        started_at=now,
                        new_next_run_at=new_next_run,
                    )
            except Exception:
                logger.exception(
                    "[SchedulerTick] failed to mark schedule {} started",
                    job.schedule_key,
                )
                continue

            if not started:
                logger.debug(
                    "[SchedulerTick] schedule {} was claimed by another worker",
                    job.schedule_key,
                )
                continue

            run_scheduled_job.send(job.model_dump(mode="json"))

    await schedule_follow_up_tick(now=now)
