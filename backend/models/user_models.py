# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 12:43:18
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-15 22:53:41
import uuid
from datetime import datetime
from typing import Any, cast

from peewee import (
    UUIDField,
    DateTimeField,
    ForeignKeyField,
)

from models.base import BaseModel, JSONField, ModelField


class User(BaseModel):
    """用户"""

    uid = cast(ModelField[uuid.UUID], UUIDField(primary_key=True, default=uuid.uuid4))
    create_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    update_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))

    def __str__(self):
        return self.uid.hex


class Setting(BaseModel):
    """设置"""

    user = cast(ModelField[User | None], ForeignKeyField(User, backref="setting", null=True))
    data = cast(ModelField[dict[str, Any]], JSONField(default=dict))
    create_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
    update_time = cast(ModelField[datetime], DateTimeField(default=datetime.now))
