from __future__ import annotations

import asyncio
from datetime import timedelta

from loguru import logger

from clepsy.modules.goals.calculate_goals import (
    update_current_progress_job as _update_current_progress_job,
    update_previous_full_period_goal_result_job as _update_previous_full_period_goal_result_job,
)


def run_update_current_progress_job(goal_id: int, ttl_seconds: float) -> None:
    """RQ Job wrapper: update current progress for a goal if stale.

    Parameters:
    - goal_id: The goal identifier
    - ttl_seconds: freshness window in seconds; if the latest progress row is newer than this, skip
    """
    try:
        logger.info(
            "[RQ] run_update_current_progress_job goal_id={} ttl_seconds={}",
            goal_id,
            ttl_seconds,
        )
        asyncio.run(
            _update_current_progress_job(
                goal_id=goal_id, ttl=timedelta(seconds=ttl_seconds)
            )
        )
    except Exception:
        logger.exception("[RQ] run_update_current_progress_job failed")
        raise


def run_update_previous_full_period_result_job(goal_id: int) -> None:
    """RQ Job wrapper: compute and upsert the previous full period result for a goal."""
    try:
        logger.info(
            "[RQ] run_update_previous_full_period_result_job goal_id={}", goal_id
        )
        asyncio.run(_update_previous_full_period_goal_result_job(goal_id=goal_id))
    except Exception:
        logger.exception("[RQ] run_update_previous_full_period_result_job failed")
        raise
