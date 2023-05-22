# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-22 21:27:40
import markdown2

from utilities.workflow import Workflow
from utilities.text_splitter import TokenTextSplitter
from worker.tasks import task


@task
def template_compose(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    template = workflow.get_node_field_value(node_id, "template")
    fields = workflow.get_node_fields(node_id)
    for field in fields:
        if field in ("output", "template"):
            continue
        # Varialble format: {{field}}
        template = template.replace(f"{{{{{field}}}}}", workflow.get_node_field_value(node_id, field))
    workflow.update_node_field_value(node_id, "output", template)
    return workflow.data


@task
def markdown_to_html(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    markdown = workflow.get_node_field_value(node_id, "markdown")
    html = markdown2.markdown(markdown, extras=["fenced-code-blocks"])
    workflow.update_node_field_value(node_id, "html", html)
    return workflow.data


@task
def text_splitters(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    text = workflow.get_node_field_value(node_id, "text")
    split_method = workflow.get_node_field_value(node_id, "split_method")
    chunk_length = workflow.get_node_field_value(node_id, "chunk_length")
    if split_method == "general":
        text_splitter = TokenTextSplitter(chunk_size=chunk_length, chunk_overlap=30, model_name="gpt-3.5-turbo")
        paragraphs = text_splitter.create_documents([text])
    workflow.update_node_field_value(node_id, "output", paragraphs)
    return workflow.data


@task
def list_render(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    list = workflow.get_node_field_value(node_id, "list")
    output_type = workflow.get_node_field_value(node_id, "output_type")
    if output_type == "text":
        output_text = "\n".join(list)
    elif output_type == "list":
        output_text = list
    workflow.update_node_field_value(node_id, "output", output_text)
    return workflow.data


@task
def text_in_out(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    text = workflow.get_node_field_value(node_id, "text")
    workflow.update_node_field_value(node_id, "output", text)
    return workflow.data
