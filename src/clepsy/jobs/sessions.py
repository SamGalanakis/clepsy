from __future__ import annotations
# ruff: noqa: I001

import dramatiq
from clepsy.infra import dramatiq_setup as _dramatiq_setup  # noqa: F401
from loguru import logger

from clepsy.modules.sessions.tasks import run_sessionization
from clepsy.jobs.actor_init import actor_init


@dramatiq.actor
async def run_sessionization_job() -> None:
    """Dramatiq async actor for sessionization."""
    logger.info("[Dramatiq] run_sessionization_job starting")

    try:
        # Ensure DB adapters/converters are registered in this worker process
        await actor_init()
        await run_sessionization()
    except Exception:
        logger.exception("[Dramatiq] run_sessionization_job failed")
        raise
