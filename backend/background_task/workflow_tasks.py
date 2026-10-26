# @Author: Bi Ying
# @Date:   2025-08-05
# Workflow Celery tasks

import time
import inspect
import threading
from copy import deepcopy

from celery_worker import app, timer

from utilities.workflow import Workflow
from utilities.general import mprint_with_name
from utilities.workflow_errors import WorkflowExecutionError, add_failure, node_failure
from worker.tasks import chain, on_finish, TaskRetry, task
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
from typing import Dict, Any

mprint = mprint_with_name(name="Workflow Tasks")


# Build task functions registry - collect all registered Celery tasks
def get_task_functions():
    """Dynamically get task functions from Celery app registry."""
    task_funcs = {}

    # Import all task modules to ensure they're registered
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

    # Collect tasks from each module
    for module in task_modules:
        module_name = module.__name__.split(".")[-1]
        task_funcs[module_name] = {}

        for name, obj in inspect.getmembers(module):
            # Check if it's a Task instance (our wrapped Celery task)
            if hasattr(obj, "__class__") and obj.__class__.__name__ == "Task":
                task_funcs[module_name][name] = obj

    return task_funcs


# Initialize task functions
task_functions = get_task_functions()


@task
def merge_results(workflow_data_list: list, node_ids: list):
    """Merge results from multiple workflows.

    Args:
        workflow_data_list (list): List of workflow data
        node_ids (list): List of node IDs

    Returns:
        dict: merged workflow data
    """
    if not workflow_data_list:
        return {}

    merged_data = deepcopy(workflow_data_list[0])
    nodes = {node["id"]: node for node in merged_data["nodes"]}
    for data, node_id in zip(workflow_data_list, node_ids):
        node = next((node for node in data["nodes"] if node["id"] == node_id), None)
        if node is not None:
            nodes[node_id] = deepcopy(node)
        merged_data.setdefault("node_run_time", {}).update(data.get("node_run_time", {}))
        for skipped in data.get("skipped_nodes", []):
            if skipped not in merged_data.setdefault("skipped_nodes", []):
                merged_data["skipped_nodes"].append(skipped)
        for failure in data.get("failures", []):
            add_failure(merged_data, failure)
    merged_data["nodes"] = list(nodes.values())
    merged_data.pop("_batch_collecting", None)
    return merged_data


@app.task(bind=True, name="workflow.batch_tasks")
@timer
def batch_tasks(self, workflow_data: dict, tasks: list[Dict[str, Any]]):
    """Run multiple tasks concurrently

    Args:
        workflow_data (dict): Previous node's workflow data
        tasks (list): Task list with format like:
            [
                {"node_id": "fbe608e8-853e-4a8b-a9de-e07071f6e058", "task_name": "llms.chat_glm"},
                {"node_id": "6c18de8a-78f9-4124-af57-634b6440a1d1", "task_name": "llms.moonshot"},
                {"node_id": "ed1bbd53-d9b6-4176-aa1c-09e040bbcffd", "task_name": "llms.open_ai"},
            ],
    Returns:
        dict: merged workflow data
    """
    results = {}
    threads = []
    error_tasks = []
    result_lock = threading.Lock()

    def run_task(task: Dict[str, Any]):
        task_data = deepcopy(workflow_data)
        task_data["_batch_collecting"] = True
        node_id = task["node_id"]
        is_skipped = node_id in workflow_data.get("skipped_nodes", [])

        # Record start time
        start_time = time.time()

        try:
            module, function = task["task_name"].split(".")
            task_result = task_functions[module][function](task_data, node_id)

            # Record end time and calculate elapsed time
            end_time = time.time()
            elapsed_time = end_time - start_time

            # Add node_run_time to the result
            if isinstance(task_result, dict) and not is_skipped:
                if "node_run_time" not in task_result:
                    task_result["node_run_time"] = {}
                task_result["node_run_time"][node_id] = elapsed_time

                # Also update the node's run_time field in the workflow data
                workflow_obj = Workflow(task_result)
                node = workflow_obj.get_node(node_id=node_id)
                if node:
                    node.run_time = elapsed_time
                    task_result = workflow_obj.data

            if is_skipped:
                mprint(f"<Node:{node_id}> Task {function} skipped in batch.")
            else:
                mprint(f"<Node:{node_id}> Task {function} in batch took {elapsed_time:.2f} seconds")

            with result_lock:
                results[node_id] = task_result
        except Exception as exc:
            workflow = Workflow(task_data)
            workflow.set_node_status(node_id, 500)
            elapsed_time = time.time() - start_time
            task_data.setdefault("node_run_time", {})[node_id] = elapsed_time
            node = workflow.get_node(node_id)
            if node:
                node.run_time = elapsed_time
            if not task_data.get("failures"):
                add_failure(task_data, node_failure(exc, task_data, node_id, task["task_name"]))
            with result_lock:
                error_tasks.append(task)
                results[node_id] = task_data
            mprint.error(f"Task {task['task_name']} -> {node_id} failed: {type(exc).__name__}")
        return None

    # Create a daemon thread for each task
    for task_item in tasks:
        thread = threading.Thread(target=run_task, args=(task_item,), daemon=True)
        threads.append(thread)
        thread.start()

    # Drain active nodes before failing the batch; no background writes after failure.
    for thread in threads:
        thread.join()

    # Collect results in the correct order
    sorted_task_results = []
    sorted_node_ids = []
    for _task in tasks:
        node_id = _task["node_id"]
        if node_id in results:
            sorted_task_results.append(results[node_id])
            sorted_node_ids.append(node_id)

    # Merge results with proper run time tracking
    if sorted_task_results:
        merged_result = merge_results(sorted_task_results, sorted_node_ids)
    else:
        merged_result = workflow_data

    # Ensure all nodes in this batch have their run times set
    merged_workflow = Workflow(merged_result)
    for _task in tasks:
        node_id = _task["node_id"]
        node = merged_workflow.get_node(node_id=node_id)
        if node and node_id in results:
            if node_id in merged_result.get("skipped_nodes", []):
                continue
            # Get run time from the node_run_time dict if available
            if "node_run_time" in merged_result and node_id in merged_result["node_run_time"]:
                node.run_time = merged_result["node_run_time"][node_id]
            elif hasattr(node, "run_time") and node.run_time < 0:
                # If still -1, try to calculate from task execution
                node.run_time = 0  # Default to 0 if we couldn't measure it

    merged_result = merged_workflow.data
    for task_item in tasks:
        merged_workflow.report_node_status(task_item["node_id"])
    if error_tasks:
        workflow_data.update(merged_result)
        merged_workflow.report_workflow_status(500, error_tasks[0]["task_name"])
        raise WorkflowExecutionError(merged_result.get("failures", []))
    return merged_result


@app.task(bind=True, name="workflow.run", max_retries=3)
@timer
def run_workflow(self, workflow_data: dict):
    """Run a workflow task

    Args:
        workflow_data (dict): Workflow data including nodes, edges, etc.

    Returns:
        dict: Updated workflow data after execution
    """
    dispatch_task = None
    try:
        mprint(f"Starting workflow execution: {workflow_data.get('wid', 'unknown')}")
        workflow = Workflow(workflow_data)

        tasks = workflow.get_layer_sorted_task_order()
        func_list = []

        for task_item in tasks:
            if isinstance(task_item, list):  # Parallel tasks
                group_tasks = batch_tasks.s(task_item)
                func_list.append(group_tasks)
            else:  # Single task
                dispatch_task = task_item
                module, function = task_item["task_name"].split(".")
                # Create signature with node_id as second parameter
                # workflow_data will be passed from previous task result
                func_list.append(task_functions[module][function].s(node_id=task_item["node_id"]))
                dispatch_task = None

        # Build and execute the task chain
        task_chain = chain(*func_list, on_finish.s())
        result = task_chain(workflow.data)

        mprint(f"Workflow {workflow_data.get('wid', 'unknown')} dispatched")
        return result

    except TaskRetry as e:
        mprint.error(f"Scheduling retry for task function: {e.func_name}")
        # Retry with exponential backoff
        retry_delay = min(e.retry_delay * (2**self.request.retries), 300)  # Max 5 minutes
        raise self.retry(countdown=retry_delay)

    except Exception as exc:
        # Dispatch failures carry the same evidence as node failures; never replay an unknown side effect.
        workflow = Workflow(workflow_data)
        if not workflow_data.get("failures"):
            node_id = dispatch_task["node_id"] if dispatch_task else ""
            task_name = dispatch_task["task_name"] if dispatch_task else "workflow.run"
            if node_id:
                workflow.set_node_status(node_id, 500)
            add_failure(workflow_data, node_failure(exc, workflow_data, node_id, task_name))
        workflow.report_workflow_status(500, dispatch_task["task_name"] if dispatch_task else "workflow.run")
        raise
