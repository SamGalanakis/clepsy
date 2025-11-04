from __future__ import annotations

from functools import lru_cache

# Valkey is a drop-in replacement for redis-py
import valkey as redis  # type: ignore

from clepsy.config import config


@lru_cache(maxsize=1)
def get_connection() -> "redis.Redis":
    """Get a process-wide Valkey/Redis connection.

    Uses VALKEY_URL from config. This client is API-compatible with redis-py
    and works with RQ.
    """
    # Prefer from_url to honor URL options
    return redis.from_url(config.valkey_url, decode_responses=False)  # type: ignore[attr-defined]
