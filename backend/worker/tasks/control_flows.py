# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-16 02:49:26
from utilities.workflow import Workflow
from worker.tasks import task


@task
def empty(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    return workflow.data


@task
def conditional(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    field_type = workflow.get_node_field_value(node_id, "field_type")
    left_field = workflow.get_node_field_value(node_id, "left_field")
    right_field = workflow.get_node_field_value(node_id, "right_field")
    operator = workflow.get_node_field_value(node_id, "operator")
    true_output = workflow.get_node_field_value(node_id, "true_output")
    false_output = workflow.get_node_field_value(node_id, "false_output")
    if field_type == "string":
        left_field = str(left_field)
        right_field = str(right_field)
    elif field_type == "number":
        left_field = float(left_field)
        right_field = float(right_field)

    if operator == "equal":
        result = left_field == right_field
    elif operator == "not_equal":
        result = left_field != right_field
    elif operator == "greater_than":
        result = left_field > right_field
    elif operator == "less_than":
        result = left_field < right_field
    elif operator == "greater_than_or_equal":
        result = left_field >= right_field
    elif operator == "less_than_or_equal":
        result = left_field <= right_field
    elif operator == "include":
        result = right_field in left_field
    elif operator == "not_include":
        result = right_field not in left_field
    elif operator == "is_empty":
        result = left_field == ""
    elif operator == "is_not_empty":
        result = left_field != ""
    elif operator == "starts_with":
        result = left_field.startswith(right_field)
    elif operator == "ends_with":
        result = left_field.endswith(right_field)
    else:
        result = False

    if result:
        workflow.update_node_field_value(node_id, "output", true_output)
    else:
        workflow.update_node_field_value(node_id, "output", false_output)

    return workflow.data
