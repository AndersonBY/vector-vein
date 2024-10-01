# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-13 15:43:01
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-15 14:32:42
import time
from functools import wraps
from typing import Callable, TypeVar, Optional, overload, Any, Union

from utilities.general import mprint
from utilities.workflow import Workflow


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
    def __init__(self, func: Callable, max_retries: int = 300, retry_delay: int = 1):
        self.func: Callable = func
        self.func_name: str = func.__name__
        self.max_retries: int = max_retries
        self.retry_delay: int = retry_delay
        self.retry_count: int = 0

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def s(self, *args, **kwargs):
        return (self, args, kwargs)

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


def task(
    func: Optional[F] = None, *, max_retries: int = 300, retry_delay: int = 1
) -> Union[Task, Callable[[F], Task]]:
    if func is None:
        return lambda f: Task(f, max_retries=max_retries, retry_delay=retry_delay)
    return Task(func, max_retries=max_retries, retry_delay=retry_delay)


class Chain:
    def __init__(self, *tasks):
        self.tasks: tuple[tuple[Task, list, dict]] = tasks

    def __call__(self, initial_data):
        result = initial_data
        for task, args, kwargs in self.tasks:
            while True:
                try:
                    result = task(result, *args, **kwargs)
                    break
                except TaskRetry as e:
                    if task.retry_count >= task.max_retries:
                        raise TaskError("Max retries exceeded", task.func.__name__)
                    mprint(
                        f"Retrying task {task.func.__name__}. Attempt {task.retry_count}/{task.max_retries} after {e.retry_delay} seconds."
                    )
                    raise e  # 将 TaskRetry 异常抛出，交由外部调度
                except Exception as e:
                    raise TaskError(str(e), task.func.__name__)
        return result


def chain(*tasks):
    return Chain(*tasks)


def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        elapsed_time = end_time - start_time
        if len(args) > 1:
            node_id = args[1]
        else:
            node_id = kwargs.get("node_id")
        mprint(f"<Node:{node_id}> Function {func.__name__} took {elapsed_time} seconds to run.")
        if node_id is not None and isinstance(result, dict):
            if "node_run_time" not in result:
                result["node_run_time"] = {}
            result["node_run_time"][node_id] = elapsed_time
        return result

    return wrapper


@task
def on_finish(workflow_data: dict):
    workflow = Workflow(workflow_data)
    workflow.clean_workflow_data()
    workflow.report_workflow_status(200)
    return True


def on_error(*args, **kwargs):
    mprint.error(f"workflow error: {args}, {kwargs}")
    workflow_data = args[-1]
    workflow = Workflow(workflow_data)
    workflow.report_workflow_status(500)
    return True
