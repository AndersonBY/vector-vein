# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 12:20:55
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-17 11:52:37
import uuid
import datetime

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

from models.base import BaseModel, JSONField
from models.user_models import User


class WorkflowTag(BaseModel):
    """工作流标签"""

    tid = UUIDField(primary_key=True, default=uuid.uuid4)
    title = CharField(max_length=128)
    is_public = BooleanField(default=False)
    slug_url = CharField(max_length=128, null=True)
    brief = TextField(null=True)
    language = CharField(max_length=16, null=True)
    color = CharField(max_length=16, default="#28c5e5")
    user = ForeignKeyField(User, null=True, backref="workflow_tags")
    STATUS_CHOICES = (
        ("IN", "无效"),
        ("VA", "有效"),
    )
    status = CharField(max_length=16, choices=STATUS_CHOICES, default="VA")
    create_time = DateTimeField(default=datetime.datetime.now)
    update_time = DateTimeField(default=datetime.datetime.now)

    def __str__(self):
        return f"{self.title}|{self.tid.hex}"


class Workflow(BaseModel):
    """用户工作流"""

    wid = UUIDField(primary_key=True, default=uuid.uuid4)
    user = ForeignKeyField(User, null=True, backref="workflows")
    STATUS_CHOICES = (
        ("INVALID", "无效"),
        ("EXPIRED", "已过期"),
        ("DELETED", "已删除"),
        ("VALID", "有效"),
    )
    status = CharField(max_length=16, choices=STATUS_CHOICES, default="VALID")

    title = CharField(max_length=512)
    data = JSONField(default=dict)
    brief = TextField(default="")
    images = JSONField(default=list)
    language = CharField(max_length=16, null=True)
    tags = ManyToManyField(WorkflowTag, backref="workflows")
    version = CharField(max_length=128, null=True)
    is_fast_access = BooleanField(default=False)

    create_time = DateTimeField(default=datetime.datetime.now)
    update_time = DateTimeField(default=datetime.datetime.now)
    expire_time = DateTimeField(null=True)

    def __str__(self):
        return self.wid.hex


class WorkflowRunRecord(BaseModel):
    """用户工作流运行记录"""

    rid = UUIDField(primary_key=True, default=uuid.uuid4)
    user = ForeignKeyField(User, null=True, backref="workflow_run_records")
    workflow = ForeignKeyField(Workflow, null=True, backref="run_records")
    STATUS_CHOICES = (
        ("NOT_STARTED", "未开始"),
        ("QUEUED", "排队中"),
        ("RUNNING", "运行中"),
        ("FINISHED", "已完成"),
        ("FAILED", "失败"),
    )
    status = CharField(max_length=16, choices=STATUS_CHOICES, default="QUEUED")
    data = JSONField(default=dict)
    schedule_time = DateTimeField(null=True)
    start_time = DateTimeField(default=datetime.datetime.now)
    end_time = DateTimeField(null=True)
    used_credits = IntegerField(default=0)

    def __str__(self):
        return self.rid.hex


class WorkflowRunSchedule(BaseModel):
    """用户工作流运行调度"""

    sid = UUIDField(primary_key=True, default=uuid.uuid4)
    user = ForeignKeyField(User, null=True, backref="workflow_run_schedules")
    workflow = ForeignKeyField(Workflow, null=True, backref="run_schedules")
    STATUS_CHOICES = (
        ("INVALID", "无效"),
        ("DELETED", "已删除"),
        ("VALID", "有效"),
    )
    status = CharField(max_length=16, choices=STATUS_CHOICES, default="VALID")
    data = JSONField(default=dict)
    cron_expression = CharField(max_length=128, null=True)
    schedule_time = DateTimeField(null=True)
    create_time = DateTimeField(default=datetime.datetime.now)
    update_time = DateTimeField(default=datetime.datetime.now)

    def __str__(self):
        return self.sid.hex


class WorkflowTemplate(BaseModel):
    """用户工作流模板"""

    tid = UUIDField(primary_key=True, default=uuid.uuid4)
    user = ForeignKeyField(User, null=True, backref="workflow_templates")
    STATUS_CHOICES = (
        ("INVALID", "无效"),
        ("DELETED", "已删除"),
        ("VALID", "有效"),
    )
    status = CharField(max_length=16, choices=STATUS_CHOICES, default="VALID")

    title = CharField(max_length=512)
    brief = TextField(default="")
    language = CharField(max_length=16, null=True)
    tags = ManyToManyField(WorkflowTag, backref="templates")
    data = JSONField(default=dict)
    images = JSONField(default=list)
    share_to_community = BooleanField(default=False)
    version = CharField(max_length=32, default="1.0.0")
    used_count = IntegerField(default=0)
    is_official = BooleanField(default=False)
    official_order = IntegerField(default=0)

    create_time = DateTimeField(default=datetime.datetime.now)
    update_time = DateTimeField(default=datetime.datetime.now)

    def __str__(self):
        return self.tid.hex
