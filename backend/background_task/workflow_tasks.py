# @Author: Bi Ying
# @Date:   2025-08-05
# Workflow Celery tasks

import time
import inspect
import traceback
import threading

from celery_worker import app, timer

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

    merged_data = Workflow(workflow_data_list[0]).data

    # Merge node_run_time from all results
    merged_run_times = {}
    for workflow_data in workflow_data_list:
        if isinstance(workflow_data, dict) and "node_run_time" in workflow_data:
            merged_run_times.update(workflow_data["node_run_time"])

    for workflow_data, node_id in zip(workflow_data_list[1:], node_ids[1:]):
        current_workflow = Workflow(workflow_data)
        merged_workflow = Workflow(merged_data)
        node = current_workflow.get_node(node_id=node_id)
        if node is None:
            continue

        # Copy the run_time from the node if it exists
        if hasattr(node, "run_time") and node.run_time >= 0:
            merged_node = merged_workflow.get_node(node_id=node_id)
            if merged_node:
                merged_node.run_time = node.run_time

        node_fields = current_workflow.get_node_fields(node_id=node_id)
        for field in node_fields:
            field_value = current_workflow.get_node_field_value(node_id=node_id, field=field)
            merged_workflow.update_node_field_value(node_id=node_id, field=field, value=field_value)
        merged_data = merged_workflow.data

    # Ensure all run times are preserved in the merged data
    if merged_run_times:
        merged_data["node_run_time"] = merged_run_times

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
    has_failed_task = False
    error_tasks = []
    result_lock = threading.Lock()

    def run_task(task: Dict[str, Any]):
        nonlocal has_failed_task
        module, function = task["task_name"].split(".")
        node_id = task["node_id"]

        # Record start time
        start_time = time.time()

        try:
            task_result = task_functions[module][function](workflow_data, node_id)

            # Record end time and calculate elapsed time
            end_time = time.time()
            elapsed_time = end_time - start_time

            # Add node_run_time to the result
            if isinstance(task_result, dict):
                if "node_run_time" not in task_result:
                    task_result["node_run_time"] = {}
                task_result["node_run_time"][node_id] = elapsed_time

                # Also update the node's run_time field in the workflow data
                workflow_obj = Workflow(task_result)
                node = workflow_obj.get_node(node_id=node_id)
                if node:
                    node.run_time = elapsed_time
                    task_result = workflow_obj.data

            mprint(f"<Node:{node_id}> Task {function} in batch took {elapsed_time:.2f} seconds")

            with result_lock:
                results[node_id] = task_result
        except Exception as e:
            has_failed_task = True
            with result_lock:
                error_tasks.append(task)
            mprint.error(f"Error in task {task['task_name']} -> {node_id}: {e}")
            mprint.error(f"Error type: {type(e).__name__}")
            mprint.error(traceback.format_exc())

            # Try to save partial result with error info
            if isinstance(workflow_data, dict):
                if "node_run_time" not in workflow_data:
                    workflow_data["node_run_time"] = {}
                # Mark failed node with 0 runtime
                workflow_data["node_run_time"][node_id] = 0

            # Only report workflow status if we have a valid workflow
            try:
                workflow = Workflow(workflow_data)
                workflow.report_workflow_status(500, task["task_name"])
            except Exception as e:
                mprint.error(f"Error in report_workflow_status: {e}")
                pass
        return None

    # Create a daemon thread for each task
    for task_item in tasks:
        thread = threading.Thread(target=run_task, args=(task_item,), daemon=True)
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete or any task to fail
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
            # Get run time from the node_run_time dict if available
            if "node_run_time" in merged_result and node_id in merged_result["node_run_time"]:
                node.run_time = merged_result["node_run_time"][node_id]
            elif hasattr(node, "run_time") and node.run_time < 0:
                # If still -1, try to calculate from task execution
                node.run_time = 0  # Default to 0 if we couldn't measure it

    merged_result = merged_workflow.data
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
                module, function = task_item["task_name"].split(".")
                # Create signature with node_id as second parameter
                # workflow_data will be passed from previous task result
                func_list.append(task_functions[module][function].s(node_id=task_item["node_id"]))

        # Build and execute the task chain
        task_chain = chain(*func_list, on_finish.s())
        result = task_chain(workflow.data)

        mprint(f"Workflow {workflow_data.get('wid', 'unknown')} completed successfully")
        return result

    except TaskRetry as e:
        mprint.error(f"Scheduling retry for task function: {e.func_name}")
        # Retry with exponential backoff
        retry_delay = min(e.retry_delay * (2**self.request.retries), 300)  # Max 5 minutes
        raise self.retry(countdown=retry_delay)

    except TaskError as e:
        mprint.error(traceback.format_exc())
        mprint.error(f"Workflow task error: {e}")

        # Find the error module
        module_name = "unknown"
        for module, functions in task_functions.items():
            if e.task_name in functions:
                module_name = module
                break

        # Report error status
        if workflow := Workflow(workflow_data):
            workflow.report_workflow_status(500, f"{module_name}.{e.task_name}")

        raise

    except Exception:
        mprint.error(f"Unexpected error in workflow: {traceback.format_exc()}")

        # Report generic error
        if workflow := Workflow(workflow_data):
            workflow.report_workflow_status(500, "unknown.error")

        # Retry with exponential backoff for unexpected errors
        if self.request.retries < self.max_retries:
            retry_delay = min(60 * (2**self.request.retries), 300)
            raise self.retry(countdown=retry_delay)

        raise
