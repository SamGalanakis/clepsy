import dramatiq
from dramatiq.brokers.redis import RedisBroker

from clepsy.config import config


# Configure Redis/Valkey broker and set as default
broker = RedisBroker(url=config.valkey_url)


asyncio_middleware = dramatiq.middleware.AsyncIO()

broker.add_middleware(asyncio_middleware)

dramatiq.set_broker(broker)
