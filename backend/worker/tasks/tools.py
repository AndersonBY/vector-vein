# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-18 15:22:49
from utilities.workflow import Workflow
from worker.tasks import task


@task
def programming_function(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    code = workflow.get_node_field_value(node_id, "code")
    language = workflow.get_node_field_value(node_id, "language")
    fields = workflow.get_node_fields(node_id)
    parameters = {}
    for field in fields:
        if field in ("code", "language", "output"):
            continue
        parameter = workflow.get_node_field_value(node_id, field)
        parameter_type = workflow.get_node(node_id).get_field(field).get("type")
        if parameter_type == "str":
            parameters[field] = str(parameter)
        elif parameter_type == "int":
            parameters[field] = int(parameter)
        elif parameter_type == "float":
            parameters[field] = float(parameter)
        elif parameter_type == "bool":
            parameters[field] = bool(parameter)
        else:
            parameters[field] = parameter

    if language == "python":
        exec(code, globals())
        result = main(**parameters)
    else:
        result = "Not implemented"
    workflow.update_node_field_value(node_id, "output", result)
    return workflow.data
