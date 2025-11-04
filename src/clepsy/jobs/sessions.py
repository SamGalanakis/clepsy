from __future__ import annotations

from loguru import logger

from clepsy.modules.sessions.tasks import run_sessionization


def run_sessionization_job() -> None:
    """RQ Job wrapper for sessionization."""
    logger.info("[RQ] run_sessionization_job starting")
    # Note: run_sessionization is async; if it is, we need to run it in an event loop.
    try:
        import asyncio

        if asyncio.iscoroutinefunction(run_sessionization):
            asyncio.run(run_sessionization())
        else:
            run_sessionization()  # type: ignore[misc]
    except Exception:
        logger.exception("[RQ] run_sessionization_job failed")
        raise
