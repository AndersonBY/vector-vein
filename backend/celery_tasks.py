# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2025-08-05
# Celery tasks module - exports all tasks from background_task modules

# Import all tasks from background_task modules
from background_task.general_tasks import (
    update_workflow_tool_call_data,
    summarize_conversation_title,
)

from background_task.qdrant_tasks import (
    q_create_collection as create_collection,
    q_delete_collection as delete_collection,
    q_add_point as add_point,
    q_delete_point as delete_point,
    q_search_point as search_point,
    embedding_and_upload,
)

from background_task.workflow_tasks import (
    run_workflow,
    batch_tasks,
)

# Export all tasks
__all__ = [
    'update_workflow_tool_call_data',
    'summarize_conversation_title',
    'create_collection',
    'delete_collection',
    'add_point',
    'delete_point',
    'search_point',
    'embedding_and_upload',
    'run_workflow',
    'batch_tasks',
]