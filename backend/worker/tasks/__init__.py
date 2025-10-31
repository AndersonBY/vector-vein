# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-13 15:43:01
# @Last Modified by:   Bi Ying
# @Last Modified time: 2025-08-05
import time
from functools import wraps
from typing import Callable, TypeVar, Optional, overload, Any, Union

from celery_worker import app
from celery import chain as celery_chain, group, chord

from utilities.workflow import Workflow
from utilities.general import mprint_with_name


mprint = mprint_with_name(name="Workflow Task Server")


F = TypeVar("F", bound=Callable[..., Any])


class TaskError(Exception):
    def __init__(self, message, task_name):
        super().__init__(message)
        self.task_name = task_name


class TaskRetry(Exception):
    def __init__(self, func_name: str, task: dict, retry_delay: int):
        super().__init__("Task needs to be retried")
        self.func_name = func_name
        self.task = task  # 任务数据
        self.retry_delay = retry_delay  # 重试延迟时间（秒）


class Task:
    """
    Task wrapper that bridges old Task system with Celery.
    This maintains backward compatibility while using Celery underneath.
    """

    def __init__(self, func: Callable, max_retries: int = 300, retry_delay: int = 1):
        self.func: Callable = func
        self.func_name: str = func.__name__
        self.max_retries: int = max_retries
        self.retry_delay: int = retry_delay
        self.retry_count: int = 0

        # Get module name for Celery task naming
        module_name = func.__module__.split(".")[-1] if hasattr(func, "__module__") else "unknown"
        celery_task_name = f"tasks.{module_name}.{func.__name__}"

        # Wrap original function to always report node status after execution
        def _wrapped(*args, **kwargs):
            result = func(*args, **kwargs)
            try:
                # Try best-effort to report node finished for UI progress
                node_id = kwargs.get("node_id")
                if node_id is None and len(args) >= 2 and isinstance(args[1], str):
                    node_id = args[1]
                if node_id:
                    from utilities.workflow import Workflow
                    wf = Workflow(result if isinstance(result, dict) else (args[0] if args else {}))
                    wf.report_node_status(node_id)
            except Exception as _e:
                # Do not break task result on progress reporting failures
                mprint.error(f"report_node_status failed after task {celery_task_name}: {_e}")
            return result

        # Create the actual Celery task
        self.celery_task = app.task(name=celery_task_name)(_wrapped)

    def __call__(self, *args, **kwargs):
        # Direct call - use the Celery task synchronously
        return self.celery_task(*args, **kwargs)

    def s(self, *args, **kwargs):
        # Signature for chaining - return Celery signature
        return self.celery_task.s(*args, **kwargs)

    def si(self, *args, **kwargs):
        # Immutable signature for chaining
        return self.celery_task.si(*args, **kwargs)

    def delay(self, *args, **kwargs):
        # Async execution
        return self.celery_task.delay(*args, **kwargs)

    def apply_async(self, *args, **kwargs):
        # Async execution with more control
        return self.celery_task.apply_async(*args, **kwargs)

    def retry(self, workflow_data: dict, node_id: str, retry_delay: int | None = None):
        if retry_delay is not None:
            self.retry_delay = retry_delay
        task_data = workflow_data.copy()
        task_data["node_id"] = node_id
        self.retry_count += 1
        raise TaskRetry(self.func_name, task_data, self.retry_delay)


@overload
def task(func: Callable[..., Any]) -> Task: ...


@overload
def task(*, max_retries: int = 300, retry_delay: int = 1) -> Callable[[Callable[..., Any]], Task]: ...


def task(func: Optional[F] = None, *, max_retries: int = 300, retry_delay: int = 1) -> Union[Task, Callable[[F], Task]]:
    """
    Decorator that creates a Task instance wrapping a Celery task.
    Maintains backward compatibility with existing code.
    """
    if func is None:
        return lambda f: Task(f, max_retries=max_retries, retry_delay=retry_delay)
    return Task(func, max_retries=max_retries, retry_delay=retry_delay)


class Chain:
    """
    Compatibility wrapper for Celery chain.
    Converts Task objects to Celery signatures.
    """

    def __init__(self, *tasks):
        self.tasks: tuple = tasks

    def __call__(self, initial_data):
        # Convert tasks to Celery signatures
        celery_tasks = []
        for item in self.tasks:
            if isinstance(item, tuple) and len(item) == 3:
                task, args, kwargs = item
                if isinstance(task, Task):
                    # Use the Task's signature method
                    celery_tasks.append(task.s(*args, **kwargs))
                else:
                    # Assume it's already a Celery task
                    celery_tasks.append(item)
            elif isinstance(item, Task):
                celery_tasks.append(item.s())
            else:
                celery_tasks.append(item)

        # Create and execute Celery chain
        chain_result = celery_chain(*celery_tasks)
        return chain_result(initial_data)


def chain(*tasks):
    """Create a chain of tasks that will be executed sequentially."""
    # Convert Task objects to their signatures
    celery_tasks = []
    for item in tasks:
        if isinstance(item, tuple) and len(item) == 3:
            task_obj, args, kwargs = item
            if isinstance(task_obj, Task):
                celery_tasks.append(task_obj.s(*args, **kwargs))
            else:
                celery_tasks.append(item)
        elif isinstance(item, Task):
            celery_tasks.append(item.s())
        elif hasattr(item, "s"):  # Already a Celery task or signature
            celery_tasks.append(item)
        else:
            celery_tasks.append(item)

    return celery_chain(*celery_tasks)


def timer(func):
    """Timer decorator for performance monitoring."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Preserve input node_run_time if it exists
        input_run_times = {}
        if len(args) > 0 and isinstance(args[0], dict) and "node_run_time" in args[0]:
            input_run_times = args[0]["node_run_time"].copy()
        if len(args) > 1:
            node_id = args[1]
        else:
            node_id = kwargs.get("node_id")
        mprint(f"<Node:{node_id}> Function {func.__name__} took {elapsed_time} seconds to run.")
        if node_id is not None and isinstance(result, dict):
            # Store in node_run_time dict - merge with input run times
            if "node_run_time" not in result:
                result["node_run_time"] = {}
            # Merge with input run times first
            result["node_run_time"].update(input_run_times)
            # Then add current node's run time
            result["node_run_time"][node_id] = elapsed_time
            
            # Also update the node's run_time field directly
            from utilities.workflow import Workflow
            try:
                workflow = Workflow(result)
                node = workflow.get_node(node_id=node_id)
                if node:
                    node.run_time = elapsed_time
                    result = workflow.data
            except Exception:
                # If we can't update the node, at least we have it in node_run_time
                pass
        return result

    return wrapper


# Create on_finish as a proper Celery task
@app.task(name="tasks.on_finish")
def on_finish(workflow_data: dict):
    workflow = Workflow(workflow_data)
    
    # Ensure all nodes have their run_time set from node_run_time dict if available
    if isinstance(workflow_data, dict) and "node_run_time" in workflow_data:
        for node_id, run_time in workflow_data["node_run_time"].items():
            node = workflow.get_node(node_id=node_id)
            if node and (not hasattr(node, 'run_time') or node.run_time < 0):
                node.run_time = run_time
    
    workflow.clean_workflow_data()
    workflow.report_workflow_status(200)
    return workflow.data  # Return the updated data instead of just True


def on_error(*args, **kwargs):
    mprint.error(f"workflow error: {args}, {kwargs}")
    workflow_data = args[-1]
    workflow = Workflow(workflow_data)
    workflow.report_workflow_status(500)
    return True


# Export all components
__all__ = [
    "task",
    "Task",
    "TaskError",
    "TaskRetry",
    "chain",
    "group",
    "chord",
    "timer",
    "on_finish",
    "on_error",
]

# Import all task modules to register them with Celery
from . import (
    llms,
    tools,
    output,
    triggers,
    vector_db,
    web_crawlers,
    media_editing,
    relational_db,
    control_flows,
    file_processing,
    text_processing,
    image_generation,
    media_processing,
)
