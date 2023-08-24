# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-13 15:43:01
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-08-24 17:48:44
from utilities.workflow import Workflow
from utilities.print_utils import mprint_error


class Task:
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def s(self, *args, **kwargs):
        return (self, args, kwargs)


def task(func):
    return Task(func)


class Chain:
    def __init__(self, *tasks):
        self.tasks = tasks

    def __call__(self, initial_data):
        result = initial_data
        for task, args, kwargs in self.tasks:
            try:
                result = task(result, *args, **kwargs)
            except Exception as e:
                e.task_name = task.func.__name__
                raise e
        return result


def chain(*tasks):
    return Chain(*tasks)


@task
def on_finish(workflow_data: dict):
    workflow = Workflow(workflow_data)
    workflow.update_original_workflow_data()
    workflow.clean_workflow_data()
    workflow.report_workflow_status(200)
    return True


def on_error(*args, **kwargs):
    mprint_error(f"workflow error: {args}, {kwargs}")
    workflow_data = args[-1]
    workflow = Workflow(workflow_data)
    workflow.report_workflow_status(500)
    return True
