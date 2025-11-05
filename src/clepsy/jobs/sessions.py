from __future__ import annotations
# ruff: noqa: I001

import asyncio
import inspect
import dramatiq
from clepsy.infra import dramatiq_setup as _dramatiq_setup  # noqa: F401
from loguru import logger

from clepsy.modules.sessions.tasks import run_sessionization


@dramatiq.actor
async def run_sessionization_job() -> None:
    """Dramatiq async actor for sessionization."""
    logger.info("[Dramatiq] run_sessionization_job starting")
    try:
        if inspect.iscoroutinefunction(run_sessionization):
            await run_sessionization()  # type: ignore[misc]
        else:
            # Avoid blocking event loop
            await asyncio.to_thread(run_sessionization)
    except Exception:
        logger.exception("[Dramatiq] run_sessionization_job failed")
        raise
