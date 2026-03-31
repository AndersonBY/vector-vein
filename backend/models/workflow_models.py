# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 12:20:55
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-07 02:37:36
import uuid
from datetime import datetime
from typing import Any, cast

from peewee import (
    CharField,
    TextField,
    UUIDField,
    BooleanField,
    IntegerField,
    DateTimeField,
    ForeignKeyField,
    ManyToManyField,
)

from models.base import BaseModel, JSONField, ManyToManyDescriptor, ModelField
from models.user_models import User


class WorkflowTag(BaseModel):
    """工作流标签"""

    tid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4))
    title = cast(ModelField[str], CharField(max_length=128))
    is_public = cast(ModelField[bool], BooleanField(default=False))
    slug_url = cast(ModelField[str | None], CharField(max_length=128, null=True))
    brief = cast(ModelField[str | None], TextField(null=True))
    language = cast(ModelField[str | None], CharField(max_length=16, null=True))
    color = cast(ModelField[str], CharField(max_length=16, default="#28c5e5"))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, backref="workflow_tags"))
    STATUS_CHOICES = (
        ("IN", "无效"),
        ("VA", "有效"),
    )
    status = cast(ModelField[str], CharField(max_length=16, choices=STATUS_CHOICES, default="VA"))
    create_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    update_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))

    def __str__(self):
        return f"{self.title}|{self.tid.hex}"


class Workflow(BaseModel):
    """用户工作流"""

    wid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, backref="workflows"))
    STATUS_CHOICES = (
        ("INVALID", "无效"),
        ("EXPIRED", "已过期"),
        ("DELETED", "已删除"),
        ("VALID", "有效"),
    )
    status = cast(ModelField[str], CharField(max_length=16, choices=STATUS_CHOICES, default="VALID"))

    title = cast(ModelField[str], CharField(max_length=512))
    data = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    brief = cast(ModelField[str], TextField(default=""))
    images = cast(ModelField[list[Any]], JSONField(default=list))
    language = cast(ModelField[str | None], CharField(max_length=16, null=True))
    tags = cast(ManyToManyDescriptor["WorkflowTag"], ManyToManyField(WorkflowTag, backref="workflows"))
    version = cast(ModelField[int], IntegerField(default=1))
    is_fast_access = cast(ModelField[bool], BooleanField(default=False))

    create_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    update_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    expire_time = cast(ModelField[datetime | None], DateTimeField(null=True))

    tool_call_data = cast(ModelField[dict[str, Any]], JSONField(default=dict))

    def __str__(self):
        return self.wid.hex


class WorkflowRunRecord(BaseModel):
    """用户工作流运行记录"""

    class RunFromTypes:
        WEB = "WEB"
        SCHEDULE = "SCHEDULE"
        API = "API"
        WORKFLOW = "WORKFLOW"
        CHAT = "CHAT"

    rid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, backref="workflow_run_records"))
    workflow = cast(ModelField[Workflow | None], ForeignKeyField(Workflow, null=True, backref="run_records"))
    workflow_version = cast(ModelField[int], IntegerField(default=1))
    STATUS_CHOICES = (
        ("NOT_STARTED", "未开始"),
        ("QUEUED", "排队中"),
        ("RUNNING", "运行中"),
        ("FINISHED", "已完成"),
        ("FAILED", "失败"),
    )
    status = cast(ModelField[str], CharField(max_length=16, choices=STATUS_CHOICES, default="QUEUED"))
    data = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    schedule_time = cast(ModelField[datetime | None], DateTimeField(null=True))
    start_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    end_time = cast(ModelField[datetime | None], DateTimeField(null=True))
    used_credits = cast(ModelField[int], IntegerField(default=0))

    run_from = cast(
        ModelField[str],
        CharField(max_length=16, choices=RunFromTypes.__dict__.items(), default=RunFromTypes.WEB),
    )
    source_message = cast(ModelField[uuid.UUID | None], UUIDField(null=True))

    def __str__(self):
        return self.rid.hex


class WorkflowRunSchedule(BaseModel):
    """用户工作流运行调度"""

    sid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, backref="workflow_run_schedules"))
    workflow = cast(ModelField[Workflow | None], ForeignKeyField(Workflow, null=True, backref="run_schedules"))
    STATUS_CHOICES = (
        ("INVALID", "无效"),
        ("DELETED", "已删除"),
        ("VALID", "有效"),
    )
    status = cast(ModelField[str], CharField(max_length=16, choices=STATUS_CHOICES, default="VALID"))
    data = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    cron_expression = cast(ModelField[str | None], CharField(max_length=128, null=True))
    schedule_time = cast(ModelField[datetime | None], DateTimeField(null=True))
    create_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    update_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))

    def __str__(self):
        return self.sid.hex


class WorkflowTemplate(BaseModel):
    """用户工作流模板"""

    tid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, backref="workflow_templates"))
    STATUS_CHOICES = (
        ("INVALID", "无效"),
        ("DELETED", "已删除"),
        ("VALID", "有效"),
    )
    status = cast(ModelField[str], CharField(max_length=16, choices=STATUS_CHOICES, default="VALID"))

    title = cast(ModelField[str], CharField(max_length=512))
    brief = cast(ModelField[str], TextField(default=""))
    language = cast(ModelField[str | None], CharField(max_length=16, null=True))
    tags = cast(ManyToManyDescriptor[WorkflowTag], ManyToManyField(WorkflowTag, backref="templates"))
    data = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    images = cast(ModelField[list[Any]], JSONField(default=list))
    share_to_community = cast(ModelField[bool], BooleanField(default=False))
    version = cast(ModelField[str], CharField(max_length=32, default="1.0.0"))
    used_count = cast(ModelField[int], IntegerField(default=0))
    is_official = cast(ModelField[bool], BooleanField(default=False))
    official_order = cast(ModelField[int], IntegerField(default=0))

    create_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    update_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))

    tool_call_data = cast(ModelField[dict[str, Any]], JSONField(default=dict))

    def __str__(self):
        return self.tid.hex
