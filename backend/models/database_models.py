# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 12:20:55
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-15 01:39:23
import uuid
import datetime
from typing import Any, cast

from peewee import (
    UUIDField,
    CharField,
    IntegerField,
    DateTimeField,
    ForeignKeyField,
)

from models.base import BaseModel, JSONField, ModelField
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
    vid = cast(ModelField[uuid.UUID], UUIDField(default=uuid.uuid4, unique=True))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, on_delete="SET NULL"))
    STATUS_CHOICES = (
        (DatabaseStatus.INVALID, "无效"),
        (DatabaseStatus.EXPIRED, "已过期"),
        (DatabaseStatus.DELETING, "删除中"),
        (DatabaseStatus.DELETED, "已删除"),
        (DatabaseStatus.VALID, "有效"),
        (DatabaseStatus.ERROR, "错误"),
        (DatabaseStatus.CREATING, "创建中"),
    )
    status = cast(ModelField[str], CharField(choices=STATUS_CHOICES, default=DatabaseStatus.CREATING))
    name = cast(ModelField[str], CharField())
    info = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    embedding_size = cast(ModelField[int], IntegerField(default=1536))
    embedding_model = cast(ModelField[str], CharField(default="text-embedding-ada-002"))
    embedding_provider = cast(ModelField[str], CharField(default="openai"))

    create_time = cast(ModelField[datetime.datetime], DateTimeField(default=datetime.datetime.now))
    update_time = cast(ModelField[datetime.datetime], DateTimeField(default=datetime.datetime.now))
    expire_time = cast(ModelField[datetime.datetime | None], DateTimeField(null=True))

    def __str__(self):
        return str(self.vid)

    class Meta:
        table_name = "user_vector_database"


class UserObject(BaseModel):
    oid = cast(ModelField[uuid.UUID], UUIDField(default=uuid.uuid4, unique=True))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, on_delete="SET NULL"))
    title = cast(ModelField[str], CharField())
    info = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    slug_url = cast(ModelField[str | None], CharField(null=True))
    TYPE_CHOICES = (
        ("TEXT", "文本"),
        ("IMAGE", "图片"),
        ("AUDIO", "音频"),
        ("VIDEO", "视频"),
        ("OTHER", "其他"),
    )
    data_type = cast(ModelField[str], CharField(choices=TYPE_CHOICES))
    STATUS_CHOICES = (
        ("IN", "无效"),
        ("PR", "处理中"),
        ("VA", "有效"),
    )
    status = cast(ModelField[str], CharField(choices=STATUS_CHOICES, default="VA"))
    vector_database = cast(ModelField[UserVectorDatabase], ForeignKeyField(UserVectorDatabase, on_delete="CASCADE"))
    create_time = cast(ModelField[datetime.datetime], DateTimeField(default=datetime.datetime.now))
    update_time = cast(ModelField[datetime.datetime], DateTimeField(default=datetime.datetime.now))

    source_url = cast(ModelField[str | None], CharField(null=True))
    suffix = cast(ModelField[str | None], CharField(null=True))
    raw_data = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    embeddings = cast(ModelField[list[Any]], JSONField(default=list))

    def __str__(self):
        return str(self.oid)

    class Meta:
        table_name = "user_object"


class UserRelationalDatabase(BaseModel):
    rid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, on_delete="SET NULL"))

    STATUS_CHOICES = (
        (DatabaseStatus.INVALID, "无效"),
        (DatabaseStatus.EXPIRED, "已过期"),
        (DatabaseStatus.DELETING, "删除中"),
        (DatabaseStatus.DELETED, "已删除"),
        (DatabaseStatus.VALID, "有效"),
        (DatabaseStatus.ERROR, "错误"),
        (DatabaseStatus.CREATING, "创建中"),
    )
    status = cast(ModelField[str], CharField(choices=STATUS_CHOICES, default=DatabaseStatus.CREATING))

    name = cast(ModelField[str], CharField(max_length=512))
    info = cast(ModelField[dict[str, Any]], JSONField(default=dict))

    create_time = cast(ModelField[datetime.datetime], DateTimeField(default=datetime.datetime.now))
    update_time = cast(ModelField[datetime.datetime], DateTimeField(default=datetime.datetime.now))
    expire_time = cast(ModelField[datetime.datetime | None], DateTimeField(null=True))

    database_path = cast(ModelField[str | None], CharField(max_length=1024, null=True))
    database_file_last_modified = cast(ModelField[datetime.datetime | None], DateTimeField(null=True))

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
    tid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4))
    database = cast(ModelField[UserRelationalDatabase], ForeignKeyField(UserRelationalDatabase, on_delete="CASCADE"))
    user = cast(ModelField[User | None], ForeignKeyField(User, null=True, on_delete="SET NULL"))
    name = cast(ModelField[str], CharField(max_length=512))
    info = cast(ModelField[dict[str, Any]], JSONField(default=dict))

    STATUS_CHOICES = (
        (Status.INVALID, "无效"),
        (Status.PROCESSING, "处理中"),
        (Status.VALID, "有效"),
        (Status.DELETED, "已删除"),
        (Status.EXPIRED, "已过期"),
    )
    status = cast(ModelField[str], CharField(choices=STATUS_CHOICES, default=Status.VALID))

    schema = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    current_rows = cast(ModelField[int], IntegerField(default=0))
    max_rows = cast(ModelField[int], IntegerField(default=20000))

    create_time = cast(ModelField[datetime.datetime], DateTimeField(default=datetime.datetime.now))
    update_time = cast(ModelField[datetime.datetime], DateTimeField(default=datetime.datetime.now))

    def __str__(self):
        return str(self.tid)

    class Meta:
        table_name = "user_relational_table"
