from __future__ import annotations

from functools import lru_cache

import valkey as redis  # type: ignore

from clepsy.config import config


@lru_cache(maxsize=2)
def get_connection(*, decode_responses: bool) -> "redis.Redis":
    """Get a process-wide Valkey/Redis connection for the given response mode."""

    return redis.from_url(config.valkey_url, decode_responses=decode_responses)  # type: ignore[attr-defined]
