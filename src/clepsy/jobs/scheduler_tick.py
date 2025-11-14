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
IMMEDIATE_RETRY_DELAY = timedelta(seconds=1)


def compute_next_run(job: DBScheduledJob, *, now: datetime) -> datetime:
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
        next_run = now + IMMEDIATE_RETRY_DELAY

    return next_run


async def schedule_follow_up_tick(
    *, now: datetime, immediate: bool, hint: datetime | None
) -> None:
    candidates: list[datetime] = [ensure_utc(now) + DEFAULT_POLL_INTERVAL]
    if immediate:
        candidates.append(ensure_utc(now) + IMMEDIATE_RETRY_DELAY)
    if hint is not None:
        candidates.append(ensure_utc(hint))

    try:
        async with get_db_connection(start_transaction=False) as conn:
            upcoming = await db_queries.select_next_scheduled_run_after(conn, now=now)
    except Exception:
        logger.exception("[SchedulerTick] failed to fetch next scheduled run")
        upcoming = None

    if upcoming is not None:
        candidates.append(ensure_utc(upcoming))

    next_tick_at = min(candidates)
    now_utc = ensure_utc(now)
    if next_tick_at <= now_utc + timedelta(milliseconds=10):
        scheduler_tick.send()
        logger.debug("[SchedulerTick] scheduled immediate follow-up tick")
        return

    scheduler_tick.send_with_options(eta=datetime_to_eta(next_tick_at))
    logger.debug("[SchedulerTick] scheduled next tick at {}", next_tick_at.isoformat())


@dramatiq.actor
async def scheduler_tick(now_iso: str | None = None) -> None:
    """Central scheduler tick.

    Reads the database for due schedules, safely advances their run cursor, and
    dispatches them for execution. Afterwards schedules the next tick based on
    the soonest upcoming run (with a fallback poll interval).
    """

    await actor_init()

    now = coerce_to_utc(now_iso)
    logger.debug("[SchedulerTick] evaluating schedules at {}", now.isoformat())

    immediate_retry = False

    try:
        async with get_db_connection(start_transaction=True) as conn:
            timed_out_jobs = await db_queries.release_timed_out_scheduled_jobs(
                conn,
                timeout_threshold=now - config.scheduled_job_timeout,
                now=now,
            )
    except Exception:
        logger.exception("[SchedulerTick] failed to release timed-out schedules")
        timed_out_jobs = []
        immediate_retry = True
    else:
        if timed_out_jobs:
            immediate_retry = True
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

    try:
        async with get_db_connection(start_transaction=False) as conn:
            due_jobs: list[DBScheduledJob] = await db_queries.select_due_scheduled_jobs(
                conn, now=now
            )
    except Exception:
        logger.exception("[SchedulerTick] failed to fetch due schedules")
        await schedule_follow_up_tick(now=now, immediate=True, hint=None)
        return

    next_hint: datetime | None = None

    if not due_jobs:
        logger.debug("[SchedulerTick] no due schedules found")
    else:
        for job in due_jobs:
            logger.info(
                "[SchedulerTick] schedule {} ({}) due at {} (running={}/{})",
                job.schedule_key,
                job.job_type.value,
                ensure_utc(job.next_run_at).isoformat(),
                job.running_count,
                job.max_concurrent,
            )

            try:
                new_next_run = compute_next_run(job, now=now)
            except ValueError:
                logger.exception(
                    "[SchedulerTick] failed to compute next run for {}",
                    job.schedule_key,
                )
                immediate_retry = True
                continue

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
                immediate_retry = True
                continue

            if not started:
                logger.debug(
                    "[SchedulerTick] schedule {} was claimed by another worker",
                    job.schedule_key,
                )
                immediate_retry = True
                continue

            run_scheduled_job.send(job.model_dump(mode="json"))

            if next_hint is None or new_next_run < next_hint:
                next_hint = new_next_run

    await schedule_follow_up_tick(now=now, immediate=immediate_retry, hint=next_hint)
