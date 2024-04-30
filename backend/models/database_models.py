# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 12:20:55
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-04-30 02:23:51
import uuid
import datetime

from peewee import (
    UUIDField,
    CharField,
    IntegerField,
    DateTimeField,
    ForeignKeyField,
)

from models.base import BaseModel, JSONField
from models.user_models import User


class DatabaseStatus:
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"
    DELETING = "DELETING"
    DELETED = "DELETED"
    VALID = "VALID"
    ERROR = "ERROR"
    CREATING = "CREATING"


class UserVectorDatabase(BaseModel):
    vid = UUIDField(default=uuid.uuid4, unique=True)
    user = ForeignKeyField(User, null=True, on_delete="SET NULL")
    STATUS_CHOICES = (
        (DatabaseStatus.INVALID, "无效"),
        (DatabaseStatus.EXPIRED, "已过期"),
        (DatabaseStatus.DELETING, "删除中"),
        (DatabaseStatus.DELETED, "已删除"),
        (DatabaseStatus.VALID, "有效"),
        (DatabaseStatus.ERROR, "错误"),
        (DatabaseStatus.CREATING, "创建中"),
    )
    status = CharField(choices=STATUS_CHOICES, default=DatabaseStatus.CREATING)
    name = CharField()
    info = JSONField(default=dict)
    embedding_size = IntegerField(default=1536)
    embedding_model = CharField(default="text-embedding-ada-002")

    create_time = DateTimeField(default=datetime.datetime.now)
    update_time = DateTimeField(default=datetime.datetime.now)
    expire_time = DateTimeField(null=True)

    def __str__(self):
        return str(self.vid)

    class Meta:
        table_name = "user_vector_database"


class UserObject(BaseModel):
    oid = UUIDField(default=uuid.uuid4, unique=True)
    user = ForeignKeyField(User, null=True, on_delete="SET NULL")
    title = CharField()
    info = JSONField(default=dict)
    slug_url = CharField(null=True)
    TYPE_CHOICES = (
        ("TEXT", "文本"),
        ("IMAGE", "图片"),
        ("AUDIO", "音频"),
        ("VIDEO", "视频"),
        ("OTHER", "其他"),
    )
    data_type = CharField(choices=TYPE_CHOICES)
    STATUS_CHOICES = (
        ("IN", "无效"),
        ("PR", "处理中"),
        ("VA", "有效"),
    )
    status = CharField(choices=STATUS_CHOICES, default="VA")
    vector_database = ForeignKeyField(UserVectorDatabase, on_delete="CASCADE")
    create_time = DateTimeField(default=datetime.datetime.now)
    update_time = DateTimeField(default=datetime.datetime.now)

    source_url = CharField(null=True)
    suffix = CharField(null=True)
    raw_data = JSONField(default=dict)
    embeddings = JSONField(default=list)

    def __str__(self):
        return str(self.oid)

    class Meta:
        table_name = "user_object"


class UserRelationalDatabase(BaseModel):
    rid = UUIDField(primary_key=True, default=uuid.uuid4)
    user = ForeignKeyField(User, null=True, on_delete="SET NULL")

    STATUS_CHOICES = (
        (DatabaseStatus.INVALID, "无效"),
        (DatabaseStatus.EXPIRED, "已过期"),
        (DatabaseStatus.DELETING, "删除中"),
        (DatabaseStatus.DELETED, "已删除"),
        (DatabaseStatus.VALID, "有效"),
        (DatabaseStatus.ERROR, "错误"),
        (DatabaseStatus.CREATING, "创建中"),
    )
    status = CharField(choices=STATUS_CHOICES, default=DatabaseStatus.CREATING)

    name = CharField(max_length=512)
    info = JSONField(default=dict)

    create_time = DateTimeField(default=datetime.datetime.now)
    update_time = DateTimeField(default=datetime.datetime.now)
    expire_time = DateTimeField(null=True)

    database_path = CharField(max_length=1024, null=True)
    database_file_last_modified = DateTimeField(null=True)

    def __str__(self):
        return str(self.rid)

    class Meta:
        table_name = "user_relational_database"


class Status:
    INVALID = "IN"
    PROCESSING = "PR"
    VALID = "VA"
    DELETED = "DE"
    EXPIRED = "EX"


class UserRelationalTable(BaseModel):
    tid = UUIDField(primary_key=True, default=uuid.uuid4)
    database = ForeignKeyField(UserRelationalDatabase, on_delete="CASCADE")
    user = ForeignKeyField(User, null=True, on_delete="SET NULL")
    name = CharField(max_length=512)
    info = JSONField(default=dict)

    STATUS_CHOICES = (
        (Status.INVALID, "无效"),
        (Status.PROCESSING, "处理中"),
        (Status.VALID, "有效"),
        (Status.DELETED, "已删除"),
        (Status.EXPIRED, "已过期"),
    )
    status = CharField(choices=STATUS_CHOICES, default=Status.VALID)

    schema = JSONField(default=dict)
    current_rows = IntegerField(default=0)
    max_rows = IntegerField(default=20000)

    create_time = DateTimeField(default=datetime.datetime.now)
    update_time = DateTimeField(default=datetime.datetime.now)

    def __str__(self):
        return str(self.tid)

    class Meta:
        table_name = "user_relational_table"
