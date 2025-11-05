from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from clepsy.config import config


# Configure Redis/Valkey broker and set as default
broker = RedisBroker(url=config.valkey_url)


dramatiq.set_broker(broker)
