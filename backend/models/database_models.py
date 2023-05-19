# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 12:20:55
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-17 11:52:53
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


class UserVectorDatabase(BaseModel):
    vid = UUIDField(default=uuid.uuid4, unique=True)
    user = ForeignKeyField(User, null=True, on_delete="SET NULL")
    STATUS_CHOICES = (
        ("INVALID", "无效"),
        ("EXPIRED", "已过期"),
        ("DELETING", "删除中"),
        ("DELETED", "已删除"),
        ("VALID", "有效"),
        ("ERROR", "错误"),
        ("CREATING", "创建中"),
    )
    status = CharField(choices=STATUS_CHOICES, default="CREATING")
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
