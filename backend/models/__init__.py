# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 12:42:01
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-17 16:08:07
from .base import (
    database,
    run_migrations,
    model_serializer,
    create_migrations,
)
from .user_models import User, Setting
from .database_models import (
    Status,
    UserObject,
    DatabaseStatus,
    UserVectorDatabase,
    UserRelationalTable,
    UserRelationalDatabase,
)
from .workflow_models import (
    Workflow,
    WorkflowTag,
    WorkflowTemplate,
    WorkflowRunRecord,
    WorkflowRunSchedule,
)


def create_tables():
    database.create_tables(
        [
            User,
            Setting,
            WorkflowTag,
            Workflow,
            Workflow.tags.get_through_model(),
            WorkflowRunRecord,
            WorkflowRunSchedule,
            WorkflowTemplate,
            WorkflowTemplate.tags.get_through_model(),
            UserObject,
            UserVectorDatabase,
            UserRelationalDatabase,
            UserRelationalTable,
        ]
    )


__all__ = [
    "User",
    "Status",
    "Setting",
    "database",
    "Workflow",
    "UserObject",
    "WorkflowTag",
    "create_tables",
    "DatabaseStatus",
    "run_migrations",
    "model_serializer",
    "WorkflowTemplate",
    "create_migrations",
    "WorkflowRunRecord",
    "UserVectorDatabase",
    "UserRelationalTable",
    "WorkflowRunSchedule",
    "UserRelationalDatabase",
]
