# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-28 14:29:34
from utilities.workflow import Workflow
from utilities.file_processing import get_files_contents, remove_markdown_image, remove_url_and_email
from worker.tasks import task, timer


@task
@timer
def file_loader(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    files = workflow.get_node_field_value(node_id, "files")
    need_remove_image: bool = workflow.get_node_field_value(node_id, "remove_image", True)
    need_remove_url_and_email: bool = workflow.get_node_field_value(node_id, "remove_url_and_email", True)

    if isinstance(files, str):
        files = [files]

    results = get_files_contents(files)
    output = []
    for result in results:
        if need_remove_image:
            result = remove_markdown_image(result, 0)
        if need_remove_url_and_email:
            result = remove_url_and_email(result)
        output.append(result)

    if len(files) == 1:
        output = output[0]

    workflow.update_node_field_value(node_id, "output", output)
    return workflow.data


@task
@timer
def file_upload(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    files = workflow.get_node_field_value(node_id, "files")
    if isinstance(files, str):
        files = [files]
    if len(files) == 1:
        workflow.update_node_field_value(node_id, "output", files[0])
    else:
        workflow.update_node_field_value(node_id, "output", files)
    return workflow.data
