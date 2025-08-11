# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2025-08-04
# General Celery tasks (non-Qdrant tasks)

from celery_worker import app, timer
from vectorvein.types import BackendType
from vectorvein.chat_clients.utils import format_messages

from models import Workflow, WorkflowTemplate
from utilities.general import mprint_with_name
from utilities.config import cache
from utilities.ai_utils import (
    ToolCallData,
    conversation_title_generator,
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


@app.task(bind=True)
@timer
def summarize_conversation_title(
    self,
    message_id: str,
    messages: list,
    backend: BackendType = BackendType.OpenAI,
    model: str = "gpt-4o-mini",
):
    """Summarize conversation title"""
    try:
        formatted_messages = format_messages(messages=messages, backend=backend)
        conversation_title = conversation_title_generator(formatted_messages, backend=backend, model=model)
        if conversation_title:
            conversation_title = conversation_title[:40]
        cache.set(f"conversation-title:{message_id}", conversation_title, expire=60 * 60)

        mprint(f"Generated conversation title for message: {message_id}")
        return conversation_title
    except Exception as e:
        mprint.error(f"Failed to generate conversation title: {e}")
        self.retry(countdown=60, max_retries=3)
        return None
