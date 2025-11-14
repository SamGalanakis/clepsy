from __future__ import annotations

# ruff: noqa: I001
from datetime import timedelta

import dramatiq
from clepsy.infra import dramatiq_setup as _dramatiq_setup  # noqa: F401
from clepsy.jobs.actor_init import actor_init
from loguru import logger

from clepsy.modules.goals.calculate_goals import (
    update_current_progress_job,
    update_previous_full_period_goal_result_job,
)


async def run_update_current_progress(goal_id: int, ttl_seconds: float) -> None:
    """Update current progress for a goal if stale."""

    logger.info(
        "[Goals] run_update_current_progress goal_id={} ttl_seconds={}",
        goal_id,
        ttl_seconds,
    )
    await update_current_progress_job(
        goal_id=goal_id,
        ttl=timedelta(seconds=ttl_seconds),
    )


async def run_update_previous_full_period_result(goal_id: int) -> None:
    """Compute and upsert the previous full period result for a goal."""

    logger.info(
        "[Goals] run_update_previous_full_period_result goal_id={}",
        goal_id,
    )
    await update_previous_full_period_goal_result_job(goal_id=goal_id)


@dramatiq.actor
async def run_update_current_progress_job(goal_id: int, ttl_seconds: float) -> None:
    try:
        await actor_init()
        await run_update_current_progress(goal_id=goal_id, ttl_seconds=ttl_seconds)
    except Exception:
        logger.exception("[Dramatiq] run_update_current_progress_job failed")
        raise


@dramatiq.actor
async def run_update_previous_full_period_result_job(goal_id: int) -> None:
    try:
        await actor_init()
        await run_update_previous_full_period_result(goal_id=goal_id)
    except Exception:
        logger.exception("[Dramatiq] run_update_previous_full_period_result_job failed")
        raise
