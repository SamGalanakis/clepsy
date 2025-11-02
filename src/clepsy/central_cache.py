from aiocache import cached, caches

from clepsy.db import get_db_connection
from clepsy.db.queries import (
    UserSettings,
    select_source_by_token_hash,
    select_user_settings,
)
from clepsy.entities import DBDeviceSource


def is_none(value: object) -> bool:
    return value is None


user_settings_ttl = 30  # seconds
device_source_ttl = 300  # 5 minutes - sources don't change often


caches.set_config(
    {
        "default": {"cache": "aiocache.SimpleMemoryCache"}  # or Redis, see below
    }
)

central_cache = caches.get("default")


@cached(
    ttl=user_settings_ttl,
    key="user_settings",
    alias="default",
    skip_cache_func=is_none,
)
async def get_user_settings_cached() -> UserSettings | None:
    async with get_db_connection() as conn:
        user_settings = await select_user_settings(conn)
    return user_settings


async def invalidate_user_settings_cache() -> None:
    """Invalidate the cached user settings value without clearing the whole cache."""
    delete_fn = getattr(central_cache, "delete", None)
    if delete_fn is not None:
        await delete_fn("user_settings")


@cached(
    ttl=device_source_ttl,
    key_builder=lambda f, token_hash: f"device_source:{token_hash}",
    alias="default",
    skip_cache_func=is_none,
)
async def get_device_source_by_token_cached(token_hash: str) -> DBDeviceSource | None:
    async with get_db_connection() as conn:
        source = await select_source_by_token_hash(conn, token_hash)
    return source


async def invalidate_device_source_cache(token_hash: str) -> None:
    """Invalidate a specific device source from cache."""
    delete_fn = getattr(central_cache, "delete", None)
    if delete_fn is not None:
        await delete_fn(f"device_source:{token_hash}")
