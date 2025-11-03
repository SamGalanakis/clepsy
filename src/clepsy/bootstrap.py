from loguru import logger

from clepsy import utils
from clepsy.aggregator_worker import AggregatorWorker
from clepsy.auth.auth import hash_password as _hash
from clepsy.config import config
from clepsy.db import db_setup
from clepsy.db.db import get_db_connection
from clepsy.db.queries import create_user_auth, select_user_auth, select_user_settings
from clepsy.entities import (
    DesktopInputScreenshotEvent,
    MobileAppUsageEvent,
    ProcessedDesktopCheckScreenshotEventOCR,
    ProcessedDesktopCheckScreenshotEventVLM,
)
from clepsy.modules.aggregator.desktop_source.worker import DesktopCheckWorker
from clepsy.queues import (
    aggregator_input_queue,
    desktop_processing_queue,
    event_bus,
)
from clepsy.workers import worker_manager


async def init():
    async with get_db_connection(include_uuid_func=False) as conn:
        try:
            await select_user_settings(conn)
            # Ensure user_auth is initialized on first boot
            auth_row = await select_user_auth(conn)
            if auth_row is None:
                bootstrap_pw = utils.get_bootstrap_password()
                await create_user_auth(conn, _hash(bootstrap_pw))

        except ValueError:
            logger.warning("User settings not found or database issue")

    await db_setup()

    await event_bus.subscribe(
        event_type=DesktopInputScreenshotEvent.event_type,
        queue=desktop_processing_queue,
    )
    await event_bus.subscribe(
        event_type=ProcessedDesktopCheckScreenshotEventOCR.event_type,
        queue=aggregator_input_queue,
    )

    await event_bus.subscribe(
        event_type=ProcessedDesktopCheckScreenshotEventVLM.event_type,
        queue=aggregator_input_queue,
    )

    await event_bus.subscribe(
        event_type=MobileAppUsageEvent.event_type,
        queue=aggregator_input_queue,
    )

    desktop_check_worker = DesktopCheckWorker(
        event_bus=event_bus,
        input_queue=desktop_processing_queue,
        max_parallelism=3,
    )
    aggregator_worker = AggregatorWorker(
        input_queue=aggregator_input_queue, interval=config.aggregation_interval
    )

    worker_manager.add_worker(desktop_check_worker)
    worker_manager.add_worker(aggregator_worker)

    async def event_logging_hook(event):
        logger.trace(f"Event received: {event.event_type}")

    event_bus.register_hook_all_events(event_logging_hook)
