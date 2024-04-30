# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-04-29 19:29:46
import re
import json
import random

from utilities.workflow import Workflow
from worker.tasks import task, timer


@task
@timer
def empty(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    return workflow.data


@task
@timer
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


@task
@timer
def random_choice(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    input_list = workflow.get_node_field_value(node_id, "input")
    if isinstance(input_list[0], list):
        output = []
        for item in input_list:
            output.append(random.choice(item))
    else:
        output = random.choice(input_list)
    workflow.update_node_field_value(node_id, "output", output)
    return workflow.data


@task
@timer
def json_process(
    workflow_data: dict,
    node_id: str,
):
    def _try_parse_json(input_data):
        try:
            return json.loads(input_data)
        except json.JSONDecodeError:
            pattern = r"```.*?\n(.*?)\n```"
            json_block_search = re.search(pattern, input_data, re.DOTALL)
            if not json_block_search:
                raise ValueError("Invalid JSON format")
            parsed_data = json.loads(json_block_search.group(1))
            return parsed_data

    workflow = Workflow(workflow_data)
    raw_input = workflow.get_node_field_value(node_id, "input")

    if isinstance(raw_input, str):
        parsed_input = _try_parse_json(raw_input)
    else:
        parsed_input = raw_input

    if isinstance(parsed_input, dict):
        input_list = [parsed_input]
    elif isinstance(parsed_input, list):
        input_list = parsed_input
    else:
        input_list = parsed_input

    parsed_input_data = []
    for input_item in input_list:
        if not isinstance(input_item, str):
            parsed_input_data.append(input_item)
            continue
        parsed_input_data.append(_try_parse_json(input_item))

    process_mode = workflow.get_node_field_value(node_id, "process_mode")
    key = workflow.get_node_field_value(node_id, "key")
    default_value = workflow.get_node_field_value(node_id, "default_value")
    keys = workflow.get_node_field_value(node_id, "keys", [])

    input_fields_has_list = isinstance(parsed_input, list) or isinstance(key, list)
    output = []
    output_keys = {k: [] for k in keys}
    if not isinstance(key, list):
        key = [key]

    if len(key) < len(parsed_input_data):
        key = key * len(parsed_input_data)
    elif len(key) > len(parsed_input_data):
        parsed_input_data = parsed_input_data * len(key)

    if process_mode == "get_value":
        for i in range(len(parsed_input_data)):
            output.append(parsed_input_data[i].get(key[i], default_value))
    elif process_mode == "get_multiple_values":
        for input_item in parsed_input_data:
            for k in keys:
                output_keys[k].append(input_item.get(k, default_value))
    elif process_mode == "list_values":
        for i in range(len(parsed_input_data)):
            output.append(list(parsed_input_data[i].values()))
    elif process_mode == "list_keys":
        for i in range(len(parsed_input_data)):
            output.append(list(parsed_input_data[i].keys()))

    if process_mode != "get_multiple_values":
        if not input_fields_has_list:
            output = output[0]
        workflow.update_node_field_value(node_id, "output", output)
    else:
        for k in keys:
            if not input_fields_has_list:
                output_keys[k] = output_keys[k][0]
            workflow.update_node_field_value(node_id, f"output-{k}", output_keys[k])

    return workflow.data
