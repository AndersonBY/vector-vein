# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 16:56:55
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-08-07 18:02:57
import time
import uuid
import inspect
import traceback
import threading
from pathlib import Path
from threading import Thread, Lock

from diskcache import Deque, Cache

from utilities.config import config
from utilities.workflow import Workflow
from utilities.general import mprint_with_name
from worker.tasks import chain, on_finish, TaskError, TaskRetry, task
from worker.tasks import (
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
from worker.types import Task


mprint = mprint_with_name(name="Workflow Task Server")

task_functions = {}
task_modules = [
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
]
for module in task_modules:
    functions = {}
    module_name = module.__name__.split(".")[-1]
    for name, obj in inspect.getmembers(module):
        if (
            callable(obj)
            and not inspect.isclass(obj)
            and not inspect.ismethod(obj)
            and obj.__class__.__name__ == "Task"
        ):
            functions[name] = obj
    task_functions[module_name] = functions


@task
def merge_results(workflow_data_list: list, node_ids: list):
    """Merge results from multiple workflows.

    Args:
        workflow_data_list (list): _description_
        node_ids (list): _description_

    Returns:
        _type_: merged workflow data
    """
    merged_data = Workflow(workflow_data_list[0]).data
    for workflow_data, node_id in zip(workflow_data_list[1:], node_ids[1:]):
        current_workflow = Workflow(workflow_data)
        merged_workflow = Workflow(merged_data)
        node = current_workflow.get_node(node_id=node_id)
        if node is None:
            continue
        node_fields = current_workflow.get_node_fields(node_id=node_id)
        for field in node_fields:
            field_value = current_workflow.get_node_field_value(node_id=node_id, field=field)
            merged_workflow.update_node_field_value(node_id=node_id, field=field, value=field_value)
        merged_data = merged_workflow.data
    return merged_data


@task
def batch_tasks(workflow_data: dict, tasks: list[Task]):
    """手动构造的并发运行任务

    Args:
        workflow_data (dict): 上一个节点传入的 workflow data
        tasks (list): 任务列表，格式如下
            [
                {"node_id": "fbe608e8-853e-4a8b-a9de-e07071f6e058", "task_name": "llms.chat_glm"},
                {"node_id": "6c18de8a-78f9-4124-af57-634b6440a1d1", "task_name": "llms.moonshot"},
                {"node_id": "ed1bbd53-d9b6-4176-aa1c-09e040bbcffd", "task_name": "llms.open_ai"},
            ],
    Returns:
        _type_: merged workflow data
    """
    results = {}
    threads = []
    has_failed_task = False
    error_tasks = []
    result_lock = threading.Lock()

    def run_task(task: Task):
        nonlocal has_failed_task
        module, function = task["task_name"].split(".")
        # 执行任务并获取结果
        try:
            task_result = task_functions[module][function](workflow_data, task["node_id"])
            # 使用锁来确保结果合并时的线程安全
            with result_lock:
                results[task["node_id"]] = task_result
        except Exception as e:
            has_failed_task = True
            with result_lock:
                error_tasks.append(task)
            mprint.error(f"Error in task {task['task_name']} -> {task['node_id']}: {e}")
            mprint.error(traceback.format_exc())
            workflow = Workflow(workflow_data)
            workflow.report_workflow_status(500, task["task_name"])

        return None

    # 为每个任务创建一个守护线程
    for task_item in tasks:
        thread = threading.Thread(target=run_task, args=(task_item,), daemon=True)
        threads.append(thread)
        thread.start()

    # 等待所有线程完成或任何一个任务失败
    while True:
        if has_failed_task:
            break
        all_threads_finished = True
        for thread in threads:
            if thread.is_alive():
                all_threads_finished = False
                break
        if all_threads_finished:
            break
        time.sleep(0.1)

    if has_failed_task:
        mprint.error(error_tasks)
        raise Exception("Some tasks failed")

    sorted_task_results = [results[task["node_id"]] for task in tasks]
    merged_result = merge_results(sorted_task_results, [task["node_id"] for task in tasks])
    return merged_result


class WorkflowServer:
    def __init__(self, cache_dir: str | Path | None = None, num_workers: int = 2):
        if cache_dir is None:
            cache_dir = Path(config.data_path) / "cache"
        self.cache_dir = Path(cache_dir)
        self.workflow_tasks_queue_directory = self.cache_dir / "workflow_task"
        self.num_workers = num_workers
        self.threads = []
        self.shutdown_event = False

        # 主任务队列
        self.main_queue = Deque(directory=self.workflow_tasks_queue_directory)

        # 延迟任务队列
        self.delayed_tasks_directory = self.cache_dir / "delayed_tasks"
        self.delayed_tasks_cache = Cache(directory=self.delayed_tasks_directory)
        self.delayed_tasks_lock = Lock()

    def start(self):
        # 启动 worker 线程
        for index in range(self.num_workers):
            thread = Thread(target=self.run, args=(index,), daemon=True)
            thread.start()
            self.threads.append(thread)

        # 启动调度器线程
        scheduler_thread = Thread(target=self.scheduler, daemon=True)
        scheduler_thread.start()
        self.threads.append(scheduler_thread)

    def stop(self):
        mprint("Stopping...")
        self.shutdown_event = True
        for thread in self.threads:
            if thread and thread.is_alive():
                thread.join()
        self.threads = []

    def scheduler(self):
        mprint("Scheduler thread started.")
        while not self.shutdown_event:
            try:
                current_time = time.time()
                with self.delayed_tasks_lock:
                    keys = sorted(self.delayed_tasks_cache.iterkeys())
                    for key in keys:
                        try:
                            scheduled_time_str, task_id = str(key).split("_", 1)
                            scheduled_time = float(scheduled_time_str)
                            if scheduled_time <= current_time:
                                task_data = self.delayed_tasks_cache.pop(key)
                                self.main_queue.append(task_data)
                                mprint(f"Task {task_id} moved from delayed queue to main queue.")
                            else:
                                # 由于 keys 是排序的，一旦遇到未来的任务，可以停止检查
                                break
                        except Exception as e:
                            mprint.error(f"Error processing delayed task key {key}: {e}")
                time.sleep(0.5)
            except Exception:
                mprint.error(f"Scheduler error: {traceback.format_exc()}")
                time.sleep(1)
        mprint("Scheduler thread stopped.")

    def schedule_retry(self, task_data: dict, retry_delay: int):
        scheduled_time = time.time() + retry_delay
        task_id = uuid.uuid4().hex
        key = f"{scheduled_time:.6f}_{task_id}"
        with self.delayed_tasks_lock:
            self.delayed_tasks_cache[key] = task_data
        mprint(
            f"Scheduled task {task_id} to retry at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(scheduled_time))}."
        )

    def run_task(self, task_data: dict):
        workflow = Workflow(task_data)

        tasks = workflow.get_layer_sorted_task_order()
        func_list = []
        for task_item in tasks:
            if isinstance(task_item, list):  # 如果当前任务是一个列表，则并行执行里面的任务
                group_tasks = batch_tasks.s(task_item)
                func_list.append(group_tasks)
            else:  # 如果当前任务是一个字典，则表示它是一个单一任务
                # 检查是否是链中的第一个任务
                module, function = task_item["task_name"].split(".")
                func_list.append(task_functions[module][function].s(task_item["node_id"]))
        task_chain = chain(*func_list, on_finish.s())
        task_chain(workflow.data)

    def run(self, worker_index: int):
        mprint(f"Worker {worker_index} started.")
        task_data = dict()
        while not self.shutdown_event:
            try:
                if len(self.main_queue) > 0:
                    task_data = self.main_queue.pop()
                    if not isinstance(task_data, dict):
                        continue
                    mprint(f"Worker {worker_index} received workflow request.")
                    self.run_task(task_data)
                    mprint(f"Worker {worker_index} finished workflow request.")
                else:
                    time.sleep(1)
            except TaskRetry as e:
                mprint.error(f"Scheduling retry for task function: {e.func_name}")
                self.schedule_retry(e.task, e.retry_delay)
            except TaskError as e:
                mprint.error(traceback.format_exc())
                mprint.error(f"workflow worker error: {e}")
                for module_name, functions in task_functions.items():
                    if e.task_name in functions:
                        mprint.error(f"error_module: {module_name}")
                        break
                else:
                    module_name = "unknown"
                    mprint.error(f"Unknown error: {e.task_name}")
                assert isinstance(task_data, dict)
                if workflow := Workflow(task_data):
                    workflow.report_workflow_status(500, f"{module_name}.{e.task_name}")
            except Exception:
                mprint.error(f"Unexpected error: {traceback.format_exc()}")
                time.sleep(1)
        mprint("Stopped.")
