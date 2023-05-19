# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 16:56:55
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-18 15:19:37
import queue
import inspect

from utilities.workflow import Workflow
from utilities.print_utils import mprint, mprint_error
from worker.tasks import chain, on_finish
from worker.tasks import (
    llms,
    tools,
    output,
    vector_db,
    web_crawlers,
    control_flows,
    file_processing,
    text_processing,
)


task_functions = {}
task_modules = [
    llms,
    tools,
    output,
    vector_db,
    web_crawlers,
    control_flows,
    file_processing,
    text_processing,
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


def main_worker(task_queue: queue.Queue, vdb_queues: dict):
    """
    Main worker. Run in a separate thread.

    Args:
        task_queue (queue.Queue): Workflow run task queue
        vdb_queue (queue.Queue): Vector database related request queue
    """
    while True:
        task_data = task_queue.get()
        mprint("worker receive task")
        try:
            data: dict = task_data.get("data")
            workflow = Workflow(data)
            sorted_tasks = workflow.get_sorted_task_order()
            func_list = []
            for task in sorted_tasks:
                module, function = task["task_name"].split(".")
                if module == "vector_db":
                    func_list.append(task_functions[module][function].s(task["node_id"], vdb_queues))
                else:
                    func_list.append(task_functions[module][function].s(task["node_id"]))
            task_chain = chain(*func_list, on_finish.s())
            task_chain(workflow.data)
        except Exception as e:
            import traceback

            mprint_error(traceback.format_exc())
            mprint_error(f"main_worker error: {e}")
            workflow.report_workflow_status(500)
        task_queue.task_done()


def main_vector_database(vdb_queues: dict):
    """
    Vector database worker. Run in a separate thread.
    Qdrant local version uses SQLite which does not support multi-threading.

    Args:
        vdb_queue (queue.Queue): Vector database related request queue
    """
    from utilities.qdrant_utils import (
        add_point,
        delete_point,
        search_point,
        create_collection,
        delete_collection,
    )

    qrant_utils_functions = {
        "add_point": add_point,
        "delete_point": delete_point,
        "search_point": search_point,
        "create_collection": create_collection,
        "delete_collection": delete_collection,
    }
    vdb_request_queue = vdb_queues["request"]
    vdb_response_queue = vdb_queues["response"]
    while True:
        request = vdb_request_queue.get()
        function_name: dict = request.get("function_name")
        parameters: dict = request.get("parameters")
        mprint(f"vector_database receive request {function_name}")
        try:
            function = qrant_utils_functions[function_name]
            response = function(**parameters)
            if function_name == "search_point":
                vdb_response_queue.put(response)
        except Exception as e:
            mprint_error(f"main_vector_database error: {e}")
        vdb_request_queue.task_done()
