# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-04-29 14:43:29
from utilities.workflow import Workflow
from utilities.files import get_files_contents
from worker.tasks import task, timer


@task
@timer
def file_loader(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    files = workflow.get_node_field_value(node_id, "files")
    results = get_files_contents(files)
    result = results[0]
    workflow.update_node_field_value(node_id, "output", result)
    return workflow.data
