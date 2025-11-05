from __future__ import annotations

# ruff: noqa: I001
from datetime import timedelta

import dramatiq
from clepsy.infra import dramatiq_setup as _dramatiq_setup  # noqa: F401
from loguru import logger

from clepsy.modules.goals.calculate_goals import (
    update_current_progress_job as _update_current_progress_job,
    update_previous_full_period_goal_result_job as _update_previous_full_period_goal_result_job,
)


@dramatiq.actor
async def run_update_current_progress_job(goal_id: int, ttl_seconds: float) -> None:
    """Dramatiq async actor: update current progress for a goal if stale.

    Parameters:
    - goal_id: The goal identifier
    - ttl_seconds: freshness window in seconds; if the latest progress row is newer than this, skip
    """
    try:
        logger.info(
            "[Dramatiq] run_update_current_progress_job goal_id={} ttl_seconds={}",
            goal_id,
            ttl_seconds,
        )
        await _update_current_progress_job(
            goal_id=goal_id, ttl=timedelta(seconds=ttl_seconds)
        )
    except Exception:
        logger.exception("[Dramatiq] run_update_current_progress_job failed")
        raise


@dramatiq.actor
async def run_update_previous_full_period_result_job(goal_id: int) -> None:
    """Dramatiq async actor: compute and upsert the previous full period result for a goal."""
    try:
        logger.info(
            "[Dramatiq] run_update_previous_full_period_result_job goal_id={}", goal_id
        )
        await _update_previous_full_period_goal_result_job(goal_id=goal_id)
    except Exception:
        logger.exception("[Dramatiq] run_update_previous_full_period_result_job failed")
        raise
