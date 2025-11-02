import asyncio
from asyncio import Lock, Queue
from collections import defaultdict
from itertools import chain
from typing import Awaitable, Callable, Dict, Generic, List, TypeVar

from loguru import logger

from clepsy.entities import Event, ShutdownEvent


# Define a TypeVar that can be Event or any subclass of Event
T = TypeVar("T", bound=Event)


class EventBus(Generic[T]):
    def __init__(self):
        self.event_queue: Queue[T] = Queue()
        self.subscriber_dict: Dict[str, List[Queue[T]]] = defaultdict(list)
        self.lock = Lock()
        self._running = False
        self.hooks = defaultdict(list)

    def get_current_subscribers(self) -> set[Queue[T]]:
        return set(chain.from_iterable(self.subscriber_dict.values()))

    async def start(self):
        """Start processing events."""
        self._running = True
        print("Event bus started")
        while True:
            event = await self.event_queue.get()
            async with self.lock:
                subscribed_queues = self.subscriber_dict.get(event.event_type, [])
                if not subscribed_queues and event.event_type != "shutdown":
                    logger.warning(f"No subscribers for event type {event.event_type}")
            # Broadcast event to all subscribers
            await asyncio.gather(
                *(queue.put(event) for queue in subscribed_queues),
                return_exceptions=True,  # Prevent one failing queue from stopping others
            )

            # Shutdown on specific event type
            if event.event_type == "shutdown":
                print("Event bus shutting down")
                self._running = False
                break

    def is_running(self) -> bool:
        """Check if the event bus is currently running"""
        return self._running

    def has_subscribers(self, event_type: str) -> bool:
        """Check if there are any subscribers for a given event type"""
        return bool(self.subscriber_dict.get(event_type, []))

    async def subscribe(self, event_type: str, queue: Queue[T]):
        """Subscribe a new queue to an event type."""
        async with self.lock:
            self.subscriber_dict[event_type].append(queue)

    def all_event_types(self) -> set[str]:
        return set(self.subscriber_dict.keys())

    async def shutdown(self):
        """Shutdown the event bus."""
        shutdown_event = ShutdownEvent()
        event_bus_shutdown = self.publish(shutdown_event)
        broardcast_shutdown = self.direct_broadcast(shutdown_event)
        await asyncio.gather(event_bus_shutdown, broardcast_shutdown)
        self._running = False

    async def direct_broadcast(self, event: T):
        """Broadcast an event to all subscribers regardless of event type."""
        await asyncio.gather(
            *(queue.put(event) for queue in self.get_current_subscribers()),
            return_exceptions=True,
        )

    def get_all_event_types(self) -> set[str]:
        return set(self.subscriber_dict.keys())

    async def unsubscribe(self, event_type: str, queue: Queue[T]):
        """Unsubscribe a queue from an event type."""
        async with self.lock:
            if (
                event_type in self.subscriber_dict
                and queue in self.subscriber_dict[event_type]
            ):
                self.subscriber_dict[event_type].remove(queue)
                # Clean up if no more subscribers for this event type
                if not self.subscriber_dict[event_type]:
                    del self.subscriber_dict[event_type]

    def register_hook(self, event_type: str, hook: Callable[[Event], Awaitable[None]]):
        self.hooks[event_type].append(hook)

    def register_hook_all_events(self, hook: Callable[[Event], Awaitable[None]]):
        for event_type in self.get_all_event_types():
            self.register_hook(event_type, hook)

    async def publish(self, event: T):
        """Publish an event to the main event queue."""
        await self.event_queue.put(event)
        await self.call_hooks(event)

    async def call_hooks(self, event: Event):
        hooks = self.hooks[event.event_type]
        await asyncio.gather(*[hook(event) for hook in hooks])
