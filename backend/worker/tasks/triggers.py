# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-23 14:22:23
from utilities.workflow import Workflow
from worker.tasks import task


@task
def button_trigger(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    return workflow.data
