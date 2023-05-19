# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-16 19:02:28
from utilities.workflow import Workflow
from utilities.files import get_files_contents
from worker.tasks import task


@task
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
