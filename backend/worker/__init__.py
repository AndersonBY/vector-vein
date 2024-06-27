# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 16:56:55
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-15 18:44:25
import queue
import inspect
import traceback

from utilities.general import mprint
from utilities.workflow import Workflow
from worker.tasks import chain, on_finish
from worker.tasks import (
    llms,
    tools,
    output,
    triggers,
    vector_db,
    web_crawlers,
    relational_db,
    control_flows,
    file_processing,
    text_processing,
    image_generation,
    media_processing,
)


task_functions = {}
task_modules = [
    llms,
    tools,
    output,
    triggers,
    vector_db,
    web_crawlers,
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


def workflow_worker(task_queue: queue.Queue):
    """
    Main worker. Run in a separate thread.

    Args:
        task_queue (queue.Queue): Workflow run task queue
        vdb_queue (queue.Queue): Vector database related request queue
    """
    mprint("Task worker start")
    while True:
        task_data = task_queue.get()
        mprint("worker receive workflow request")
        try:
            data: dict = task_data.get("data")
            workflow = Workflow(data)
            sorted_tasks = workflow.get_sorted_task_order()
            func_list = []
            for task in sorted_tasks:
                module, function = task["task_name"].split(".")
                func_list.append(task_functions[module][function].s(task["node_id"]))
            task_chain = chain(*func_list, on_finish.s())
            task_chain(workflow.data)
        except Exception as e:
            mprint.error(traceback.format_exc())
            mprint.error(f"workflow worker error: {e}")
            mprint.error(f"error_task: {e.task_name}")
            for module_name, functions in task_functions.items():
                if e.task_name in functions:
                    mprint.error(f"error_module: {module_name}")
                    break
            workflow.report_workflow_status(500, f"{module_name}.{e.task_name}")
        task_queue.task_done()
