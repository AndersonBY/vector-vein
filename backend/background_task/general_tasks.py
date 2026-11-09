# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2025-08-04
# General Celery tasks (non-Qdrant tasks)

from celery_worker import app, timer

from models import Workflow, WorkflowTemplate
from utilities.general import mprint_with_name
from utilities.ai_utils import (
    ToolCallData,
)

mprint = mprint_with_name(name="General Tasks")


@app.task(bind=True)
@timer
def update_workflow_tool_call_data(
    self,
    workflow_wid: str | None = None,
    template_tid: str | None = None,
    force: bool = False,
):
    """Update workflow tool call data"""
    mprint(f"Updating tool call data for workflow: {workflow_wid} or template: {template_tid}")
    try:
        if workflow_wid:
            workflow = Workflow.get(Workflow.wid == workflow_wid)
        elif template_tid:
            workflow = WorkflowTemplate.get(WorkflowTemplate.tid == template_tid)
        else:
            return False

        tool_call_data = ToolCallData(workflow)
        tool_call_data.update_title(force=force)
        tool_call_data.update_parameters()
        tool_call_data.save()

        mprint(f"Updated tool call data for {'workflow' if workflow_wid else 'template'}: {workflow_wid or template_tid}")
        return True
    except Exception as e:
        mprint.error(f"Failed to update tool call data: {e}")
        self.retry(countdown=60, max_retries=3)
        return False
