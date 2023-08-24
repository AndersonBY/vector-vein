# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 14:21:40
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-08-24 16:52:39
from functools import cached_property

from models import Workflow


def get_user_object_general(ObjectClass, **kwargs):
    if len(kwargs) == 0:
        return 500, "wrong args", {}
    try:
        object = ObjectClass.get(*[getattr(ObjectClass, key) == value for key, value in kwargs.items()])
    except ObjectClass.DoesNotExist:
        return 404, "not exist", {}
    return 200, "", object


class WorkflowData:
    def __init__(self, workflow_data: dict):
        self.workflow_data = workflow_data

    @cached_property
    def related_workflows(self) -> dict:
        related_workflows = {}
        for node in self.workflow_data["nodes"]:
            if node["type"] == "WorkflowInvoke":
                workflow_id = node["data"]["template"]["workflow_id"]["value"]
                _, _, workflow = get_user_object_general(Workflow, wid=workflow_id)
                related_workflows.update(workflow.data.get("related_workflows", {}))
                related_workflows[workflow_id] = workflow.data

        return related_workflows

    def replace_workflow_invoke_nodes_ids(self, id_map: dict):
        for node in self.workflow_data["nodes"]:
            if node["type"] != "WorkflowInvoke":
                continue
            workflow_id = node["data"]["template"]["workflow_id"]["value"]
            if workflow_id not in id_map:
                continue
            node["data"]["template"]["workflow_id"]["value"] = id_map[workflow_id]
        return self.workflow_data
