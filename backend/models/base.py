# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 12:43:52
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-18 00:19:34
import json
import uuid
from datetime import date, datetime

from playhouse.shortcuts import model_to_dict
from peewee import (
    Model,
    TextField,
    SqliteDatabase,
)

database = SqliteDatabase("./data/my_database.db")


class JSONField(TextField):
    """Custom field to store JSON data as text in SQLite"""

    def db_value(self, value):
        if value is not None:
            return json.dumps(value)
        return None

    def python_value(self, value):
        if value is not None:
            return json.loads(value)
        return None


class BaseModel(Model):
    class Meta:
        database = database


def json_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return int(obj.timestamp() * 1000)
    elif isinstance(obj, uuid.UUID):
        return obj.hex
    raise TypeError(f"Type {type(obj)} not serializable")


def model_serializer(obj, many=False, manytomany=False):
    if many:
        results = []
        for o in obj:
            dict_obj = model_to_dict(o, manytomany=manytomany)
            serialized_obj = json.dumps(dict_obj, default=json_serializer)
            results.append(json.loads(serialized_obj))
        return results
    else:
        dict_obj = model_to_dict(obj, manytomany=manytomany)
        serialized_obj = json.dumps(dict_obj, default=json_serializer)
        return json.loads(serialized_obj)
