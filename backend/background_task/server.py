# @Author: Bi Ying
# @Date:   2024-06-06 15:54:30
# This is a simple simulation of a background task handler like Celery.
import time
import traceback
from pathlib import Path
from threading import Thread, Event

from diskcache import Deque
from qdrant_client import QdrantClient

from utilities.config import config, cache
from utilities.general import mprint_with_name


mprint = mprint_with_name(name="Background Task Server")
qdrant_mprint = mprint_with_name(name="Qdrant Task Server")


class BackgroundTaskServer:
    def __init__(self, cache_dir: str | Path | None = None, num_workers: int = 2):
        if cache_dir is None:
            cache_dir = Path(config.data_path) / "cache"
        self.cache_dir = Path(cache_dir)
        self.task_queue_directory = self.cache_dir / "background_task"
        self.qdrant_tasks_queue_directory = self.cache_dir / "qdrant_task"
        self.num_workers = num_workers
        self.threads: list[Thread] = []
        self.stop_event = Event()

    def start(self):
        for worker_num in range(self.num_workers):
            thread = Thread(
                target=self.run, args=(self.stop_event, self.task_queue_directory, worker_num), daemon=True
            )
            thread.start()
            self.threads.append(thread)

        # Qdrant local mode can only have one client.
        # All qdrant tasks should be processed in the same thread.
        # https://github.com/qdrant/qdrant-client
        qdrant_thread = Thread(
            target=self.run_qdrant_task_server, args=(self.stop_event, self.qdrant_tasks_queue_directory), daemon=True
        )
        qdrant_thread.start()
        self.threads.append(qdrant_thread)

    def stop(self):
        mprint("Stopping...")
        self.stop_event.set()
        for thread in self.threads:
            if thread:
                thread.join(timeout=5)
        self.threads = []
        mprint("Stopped.")

    @staticmethod
    def run(stop_event: Event, task_queue_directory: str | Path | None = None, worker_num: int = 0):
        from background_task.tasks import get_task

        task_queue = Deque(directory=task_queue_directory)
        sleep_time = 1
        task_name = ""

        mprint(f"Worker {worker_num} started.")
        while not stop_event.is_set():
            try:
                if len(task_queue) > 0:
                    task = task_queue.pop()
                    if not isinstance(task, dict):
                        continue
                    task_name, task_id, args, kwargs = task["task_name"], task["task_id"], task["args"], task["kwargs"]
                    task_func = get_task(task_name)
                    if not task_func:
                        continue
                    task_result = task_func(*args, **kwargs)
                    cache.set(f"task_result_{task_id}", task_result, expire=60 * 10)
                    mprint(f"Task {task_id} {task_name} completed in worker {worker_num}.")
                    sleep_time = 0.01
                else:
                    sleep_time = 1
            except Exception as e:
                mprint.error(traceback.format_exc())
                mprint.error(f"Error running task {task_name} in worker {worker_num}: {e}")

            time.sleep(sleep_time)

    @staticmethod
    def run_qdrant_task_server(stop_event: Event, qdrant_tasks_queue_directory: str | Path | None = None):
        from background_task.tasks import get_task

        qdrant_path = Path(config.data_path) / "qdrant_db"
        qdrant_client = QdrantClient(path=qdrant_path.absolute().as_posix())
        qdrant_tasks_queue = Deque(directory=qdrant_tasks_queue_directory)
        sleep_time = 1
        task_name = ""

        qdrant_mprint("Started.")
        while not stop_event.is_set():
            try:
                if len(qdrant_tasks_queue) > 0:
                    task = qdrant_tasks_queue.pop()
                    if not isinstance(task, dict):
                        continue
                    task_name, task_id, args, kwargs = task["task_name"], task["task_id"], task["args"], task["kwargs"]
                    task_func = get_task(task_name)
                    if not task_func:
                        continue
                    task_result = task_func(qdrant_client, *args, **kwargs)
                    cache.set(f"task_result_{task_id}", task_result, expire=60 * 10)
                    qdrant_mprint(f"Task {task_id} {task_name} completed.")
                    sleep_time = 0.01
                else:
                    sleep_time = 1
            except Exception as e:
                qdrant_mprint.error(traceback.format_exc())
                qdrant_mprint.error(f"Error running task {task_name}: {e}")

            time.sleep(sleep_time)
