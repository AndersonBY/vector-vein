# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2025-08-05
# Celery worker configuration and manager

import time
from pathlib import Path
from functools import wraps
from threading import Thread

from celery import Celery

from utilities.config import config
from utilities.general import mprint_with_name

mprint = mprint_with_name(name="Celery Worker")

# Set up Celery app configuration
data_path = Path(config.data_path)
broker_db_path = data_path / "celerybroker.sqlite"
results_db_path = data_path / "celeryresults.sqlite"
data_path.mkdir(parents=True, exist_ok=True)

broker_url = f"sqla+sqlite:///{broker_db_path.resolve()}"
result_backend = f"db+sqlite:///{results_db_path.resolve()}"

# Create Celery app
app = Celery(
    "vectorvein_tasks", 
    broker=broker_url, 
    backend=result_backend, 
    include=[
        "background_task.general_tasks", 
        "background_task.qdrant_tasks",
        "background_task.workflow_tasks",
        # Include all worker task modules to register them
        "worker.tasks",
        "worker.tasks.llms",
        "worker.tasks.tools",
        "worker.tasks.output",
        "worker.tasks.triggers",
        "worker.tasks.vector_db",
        "worker.tasks.web_crawlers",
        "worker.tasks.media_editing",
        "worker.tasks.relational_db",
        "worker.tasks.control_flows",
        "worker.tasks.file_processing",
        "worker.tasks.text_processing",
        "worker.tasks.image_generation",
        "worker.tasks.media_processing",
    ]
)

# Celery configuration
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    result_expires=3600 * 24,  # Task results expire after 24 hours
    result_extended=True,  # Return detailed task result information
    # Desktop-specific optimizations
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks to prevent memory leaks
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit
    # Task routing - ensure all tasks use default queue
    task_default_queue='celery',
    task_routes={
        'background_task.general_tasks.*': {'queue': 'celery'},
        'background_task.qdrant_tasks.*': {'queue': 'celery'},
        'background_task.workflow_tasks.*': {'queue': 'celery'},
        'workflow.*': {'queue': 'celery'},
    }
)

# Timer decorator for performance monitoring
def timer(func):
    """Timer decorator for task performance monitoring"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        result = func(self, *args, **kwargs)
        execution_time = time.time() - start_time
        mprint(f"Task {func.__name__} completed in {execution_time:.2f}s")
        return result
    return wrapper


class CeleryWorkerManager:
    """Manages Celery worker lifecycle for desktop application"""
    
    def __init__(self, concurrency=2):
        self.concurrency = concurrency
        self.celery_worker = None
        self.thread = None
        
    def start(self):
        """Start Celery worker in a separate thread"""
        if self.celery_worker is None:
            mprint(f"Starting Celery worker with concurrency={self.concurrency}")
            try:
                import platform
                # Use 'solo' pool for Windows, 'threads' for others
                if platform.system() == 'Windows':
                    pool_type = 'solo'  # Windows compatibility
                    actual_concurrency = 1
                else:
                    pool_type = 'threads'  # Better performance on Unix
                    actual_concurrency = self.concurrency
                
                mprint(f"Using pool type: {pool_type} with concurrency: {actual_concurrency}")
                
                # Configure worker
                self.celery_worker = app.Worker(
                    loglevel='INFO',
                    concurrency=actual_concurrency,
                    pool=pool_type,
                    # Don't specify queues here - let it use all defined queues
                )
                self.thread = Thread(target=self.celery_worker.start, daemon=True)
                self.thread.start()
                
                # Give it a moment to start
                import time
                time.sleep(1)
                
                mprint("Celery worker started successfully")
                mprint(f"Registered tasks: {list(app.tasks.keys())}")
            except Exception as e:
                mprint.error(f"Failed to start Celery worker: {e}")
                import traceback
                mprint.error(traceback.format_exc())
                self.celery_worker = None
                
    def stop(self):
        """Stop Celery worker"""
        if self.celery_worker:
            try:
                mprint("Stopping Celery worker...")
                self.celery_worker.stop()
                if self.thread and self.thread.is_alive():
                    self.thread.join(timeout=5)
                mprint("Celery worker stopped")
            except Exception as e:
                mprint.error(f"Error stopping Celery worker: {e}")
            finally:
                self.celery_worker = None
                self.thread = None