# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 12:43:52
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-15 01:45:12
import json
import uuid
from pathlib import Path
from datetime import date, datetime
from typing import overload, List, Dict, Union, Optional

from playhouse.shortcuts import model_to_dict
from peewee import (
    Model,
    TextField,
    ModelSelect,
    SqliteDatabase,
)

from utilities.config import config


database = SqliteDatabase(Path(config.data_path) / "my_database.db")


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
    if isinstance(obj, datetime):
        return int(obj.timestamp() * 1000)
    elif isinstance(obj, date):
        return int(datetime.combine(obj, datetime.min.time()).timestamp() * 1000)
    elif isinstance(obj, uuid.UUID):
        return obj.hex
    raise TypeError(f"Type {type(obj)} not serializable")


def get_model_fields(model, field_names):
    return [getattr(model, field_name) for field_name in field_names if hasattr(model, field_name)]


@overload
def model_serializer(
    obj: BaseModel, many: bool = False, manytomany: bool = False, fields: Optional[List[str]] = None
) -> Dict: ...


@overload
def model_serializer(
    obj: Union[List[BaseModel], ModelSelect],
    many: bool = True,
    manytomany: bool = False,
    fields: Optional[List[str]] = None,
) -> List[Dict]: ...


def model_serializer(
    obj: Union[BaseModel, List[BaseModel], ModelSelect],
    many: bool = False,
    manytomany: bool = False,
    fields: Optional[List[str]] = None,
) -> Union[Dict, List[Dict]]:
    if fields:
        if many and obj:
            model_class = obj[0].__class__
        else:
            model_class = obj.__class__
        fields = get_model_fields(model_class, fields)

    if many:
        results = []
        for o in obj:
            dict_obj = model_to_dict(o, manytomany=manytomany, recurse=False, only=fields)
            serialized_obj = json.dumps(dict_obj, default=json_serializer)
            results.append(json.loads(serialized_obj))
        return results
    else:
        dict_obj = model_to_dict(obj, manytomany=manytomany, recurse=False, only=fields)
        serialized_obj = json.dumps(dict_obj, default=json_serializer)
        return json.loads(serialized_obj)


def run_migrations(fake: bool = False):
    from peewee_migrate import Router

    router = Router(database, migrate_dir="./migrations")
    router.run(fake=fake)


def create_migrations(name: str = "auto"):
    from peewee_migrate import Router

    router = Router(database, migrate_dir="./migrations")
    router.create(name, auto=True)
