# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-23 02:09:08
import markdown2

from utilities.workflow import Workflow
from utilities.text_splitter import TokenTextSplitter
from worker.tasks import task


@task
def template_compose(
    workflow_data: dict,
    node_id: str,
):
    """
    Compose template with input fields. If any input field or template is a list, the template will be composed multiple times.
    If there are multiple input fields are list, they must have the same length.

    For example, if input fields are:
    {
        "template": ["{{a}} {{b}}", "{{a}} {{b}}"],
        "a": ["a1", "a2"],
        "b": ["b1", "b2"]
    }
    The output will be:
    ["a1 b1", "a2 b2"]

    If input fields are:
    {
        "template": "{{a}} {{b}}",
        "a": ["a1", "a2"],
        "b": "b",
    }
    The output will be:
    ["a1 b", "a2 b"]

    Args:
        workflow_data (dict): _description_
        node_id (str): _description_

    Raises:
        ValueError: _description_

    Returns:
        _type_: _description_
    """
    workflow = Workflow(workflow_data)
    template = workflow.get_node_field_value(node_id, "template")
    fields = workflow.get_node_fields(node_id)

    # Check if input fields has list
    fields_has_list = False
    list_length = 1
    for field in fields:
        if field == "output":
            continue
        field_value = workflow.get_node_field_value(node_id, field)
        if not isinstance(field_value, list):
            continue
        fields_has_list = True
        if list_length == 0:
            list_length = len(field_value)
        elif list_length != len(field_value):
            raise ValueError("Input fields have different list length")

    # Build a dict of filed values
    fields_values: dict[str, list] = {"output": []}
    for field in fields:
        if field == "output":
            continue
        field_value = workflow.get_node_field_value(node_id, field)
        if not isinstance(field_value, list):
            fields_values[field] = [field_value] * list_length
        else:
            fields_values[field] = field_value

    # Compose template
    for index, template in enumerate(fields_values["template"]):
        for field in fields:
            if field == "output":
                continue
            template = template.replace(f"{{{{{field}}}}}", fields_values[field][index])
        fields_values["output"].append(template)
    workflow.update_node_field_value(node_id, "template", fields_values["template"])

    print(fields_values)

    if not fields_has_list:
        fields_values["output"] = fields_values["output"][0]
    workflow.update_node_field_value(node_id, "output", fields_values["output"])
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
