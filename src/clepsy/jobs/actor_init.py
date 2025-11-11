import asyncio

from loguru import logger

from clepsy.db import db_setup


class ActorInit:
    """One-time async initializer for Dramatiq worker DB setup.

    Usage:
        from clepsy.jobs.actor_init import actor_init
        await actor_init()

    Thread/process-safe within a single worker via asyncio.Lock.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.done = False

    async def __call__(self) -> None:
        if self.done:
            return
        async with self._lock:
            if self.done:
                return
            await db_setup()
            self.done = True
            logger.info("[Dramatiq] actor DB init completed")


# Export a singleton callable
actor_init = ActorInit()

__all__ = ["actor_init"]
