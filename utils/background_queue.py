"""
Background task queue for async Qdrant updates.
"""

import asyncio
import logging
from queue import Queue
from threading import Thread, current_thread
from typing import Dict, Any, Callable
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BackgroundTaskQueue:
    """
    Background task queue for non-blocking operations.

    Purpose:
    - Update Qdrant metadata without blocking user response
    - Process enrichment data asynchronously
    - Queue multiple tasks

    Flow:
    User Request → Get Data → Return Response (FAST)
                                    ↓
                            Queue Background Task
                                    ↓
                            Worker processes task (SLOW)
    """

    def __init__(self, max_workers: int = 2):
        """
        Initialize background task queue.

        Args:
            max_workers: Number of worker threads (default: 2)
        """
        self.task_queue = Queue()
        self.workers = []
        self.running = False
        self.max_workers = max_workers

        # statistics
        self.stats = {
            'tasks_queued': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_processing_time': 0.0
        }

        logger.info(f"BackgroundTaskQueue initialized ({max_workers} workers)")

    def start(self):
        """Start background workers"""
        if self.running:
            logger.warning("Workers already running")
            return

        self.running = True

        for i in range(self.max_workers):
            worker = Thread(
                target=self._worker_loop,
                name=f"BackgroundWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

        logger.info(f"Started {self.max_workers} background workers")

    def stop(self):
        """Stop background workers"""
        self.running = False
        logger.info("Stopping background workers...")

    def add_task(self, task_name: str, func: Callable, *args, **kwargs):
        """
        Add task to queue (NON-BLOCKING).

        Args:
            task_name: Human-readable task name
            func: Function to execute
            *args, **kwargs: Function arguments
        """
        task = {
            'name': task_name,
            'func': func,
            'args': args,
            'kwargs': kwargs,
            'queued_at': datetime.now(timezone.utc).isoformat()
        }

        self.task_queue.put(task)
        self.stats['tasks_queued'] += 1

        logger.debug(f"Queued task: {task_name} (queue size: {self.task_queue.qsize()})")

    def _worker_loop(self):
        """Worker loop - processes tasks from queue"""
        worker_name = current_thread().name
        logger.info(f"Worker {worker_name} started")

        while self.running:
            try:
                # get task with timeout
                task = self.task_queue.get(timeout=1.0)

                # execute task
                task_name = task['name']
                logger.info(f"Executing background task: {task_name}")

                start_time = datetime.now(timezone.utc)

                try:
                    # execute function
                    func = task['func']
                    result = func(*task['args'], **task['kwargs'])

                    # if async function, run it
                    if asyncio.iscoroutine(result):
                        asyncio.run(result)

                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                    self.stats['tasks_completed'] += 1
                    self.stats['total_processing_time'] += duration

                    logger.info(f"Task '{task_name}' completed in {duration:.2f}s")

                except Exception as e:
                    self.stats['tasks_failed'] += 1
                    logger.error(f"Task '{task_name}' failed: {e}")
                    import traceback
                    traceback.print_exc()

                finally:
                    self.task_queue.task_done()

            except Exception:
                # timeout or queue empty
                continue

        logger.info(f"Worker {worker_name} stopped")

    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.task_queue.qsize()

    def get_stats(self) -> Dict[str, Any]:
        """Get task statistics"""
        avg_time = (
            self.stats['total_processing_time'] / self.stats['tasks_completed']
            if self.stats['tasks_completed'] > 0 else 0
        )

        return {
            **self.stats,
            'queue_size': self.get_queue_size(),
            'workers': len(self.workers),
            'running': self.running,
            'avg_processing_time': round(avg_time, 2)
        }


# global background queue (singleton)
GLOBAL_BACKGROUND_QUEUE = BackgroundTaskQueue(max_workers=2)
GLOBAL_BACKGROUND_QUEUE.start()

logger.info("Global background queue started")