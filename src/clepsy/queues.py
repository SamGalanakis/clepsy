from asyncio import Queue

from clepsy.entities import (
    AggregationInputEvent,
    DesktopInputEvent,
    ShutdownEvent,
)
from clepsy.event_bus import EventBus


event_bus = EventBus()


desktop_processing_queue: Queue[DesktopInputEvent | ShutdownEvent] = Queue()


aggregator_input_queue: Queue[AggregationInputEvent | ShutdownEvent] = Queue()
