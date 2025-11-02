from __future__ import annotations

import abc
import asyncio
from asyncio import Queue
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from loguru import logger


class AbstractWorker(abc.ABC):
    def __init__(
        self,
        input_queue: Queue,
        name: str | None = None,
    ) -> None:
        self.input_queue = input_queue
        self.name = name or self.__class__.__name__
        self.shutdown_received = False
        self._worker_task = None
        self.manager = None

    def signal_success(self) -> None:
        assert self.manager is not None, "Manager must be set to signal success"
        self.manager.signal_worker_success(self.name)

    def signal(self, signal: Any):
        assert self.manager is not None, "Manager must be set to signal"
        self.manager.signal_worker(self.name, signal)

    def register_manager_handler(self, manager: WorkerManager) -> None:
        self.manager = manager

    @abc.abstractmethod
    async def run(self) -> None:
        """
        The main loop of the worker. Subclasses must implement this.
        """

    async def start(self) -> None:
        logger.info("Starting worker {}", self.name)
        self._worker_task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        logger.info("Stopping worker {}", self.name)
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        else:
            logger.warning("Worker {} was not started", self.name)

    @property
    def is_running(self) -> bool:
        return self._worker_task is not None and not self._worker_task.done()


class WorkerManager:
    def __init__(self) -> None:
        self.workers = {}
        self.worker_signal_queues = defaultdict(lambda: deque(maxlen=100))
        self.worker_last_success = {}
        # Exponential moving average (EMA) of success intervals in seconds per worker
        self.worker_avg_success_interval_s = {}
        self._worker_prev_success_time = {}
        # Smoothing factor for EMA; higher = reacts faster. Tunable.
        self._ema_alpha = 0.3

    def add_worker(self, worker: AbstractWorker) -> None:
        worker_name = worker.name
        if worker_name in self.workers:
            raise ValueError(f"Worker with name {worker_name} already exists")
        self.workers[worker_name] = worker
        worker.register_manager_handler(self)

    def signal_worker(self, worker_name: str, signal: Any) -> None:
        if worker_name not in self.workers:
            raise ValueError(f"Worker with name {worker_name} not found")
        self.worker_signal_queues[worker_name].append(signal)

    def signal_worker_success(self, worker_name: str) -> None:
        now = datetime.now(timezone.utc)
        self.worker_last_success[worker_name] = now

        # Update running EMA of success interval
        prev = self._worker_prev_success_time.get(worker_name)
        if prev is not None:
            interval_s = (now - prev).total_seconds()
            current_ema = self.worker_avg_success_interval_s.get(worker_name)
            if current_ema is None:
                # Seed EMA with first measured interval
                self.worker_avg_success_interval_s[worker_name] = interval_s
            else:
                alpha = self._ema_alpha
                self.worker_avg_success_interval_s[worker_name] = (
                    alpha * interval_s + (1 - alpha) * current_ema
                )
        self._worker_prev_success_time[worker_name] = now

    async def start_all(self) -> None:
        start_tasks = [worker.start() for worker in self.workers.values()]
        await asyncio.gather(*start_tasks)

    async def stop_all(self) -> None:
        stop_tasks = [worker.stop() for worker in self.workers.values()]
        await asyncio.gather(*stop_tasks)

    async def start_worker(self, worker_name: str) -> None:
        worker = self.workers.get(worker_name)
        if worker is None:
            raise ValueError(f"Worker with name {worker_name} not found")
        await worker.start()

    async def stop_worker(self, worker_name: str) -> None:
        worker = self.workers.get(worker_name)
        if worker is None:
            raise ValueError(f"Worker with name {worker_name} not found")
        await worker.stop()

    def get_worker(self, worker_name: str) -> AbstractWorker | None:
        return self.workers.get(worker_name)

    def worker_running(self, worker_name: str) -> bool:
        worker = self.get_worker(worker_name)
        return worker is not None and worker.is_running

    def all_workers_running(self) -> bool:
        return all(worker.is_running for worker in self.workers.values())


worker_manager = WorkerManager()
