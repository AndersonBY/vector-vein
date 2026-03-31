# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 12:43:52
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-15 01:45:12
import json
import uuid
from collections.abc import Iterable, Iterator
from pathlib import Path
from datetime import date, datetime
from typing import Any, Protocol, TypeAlias, TypeVar, overload, List, Optional

from playhouse.shortcuts import model_to_dict
from peewee import (
    Model,
    TextField,
    ModelSelect,
    SqliteDatabase,
)

from utilities.config import config


database = SqliteDatabase(Path(config.data_path) / "my_database.db")

SerializedModel: TypeAlias = dict[str, Any]
SerializedModelList: TypeAlias = list[SerializedModel]

_RelatedModel = TypeVar("_RelatedModel")
_FieldValue = TypeVar("_FieldValue")


class ModelField(Protocol[_FieldValue]):
    @overload
    def __get__(self, instance: None, owner: type[Any] | None = None) -> Any: ...

    @overload
    def __get__(self, instance: object, owner: type[Any] | None = None) -> _FieldValue: ...

    def __set__(self, instance: object, value: _FieldValue) -> None: ...

    def asc(self) -> Any: ...

    def desc(self) -> Any: ...

    def contains(self, value: Any) -> Any: ...

    def in_(self, value: Any) -> Any: ...

    def __eq__(self, other: Any) -> Any: ...

    def __ne__(self, other: Any) -> Any: ...


class ManyToManyRelation(Protocol[_RelatedModel]):
    def clear(self) -> Any: ...

    def add(self, value: _RelatedModel | Iterable[_RelatedModel]) -> Any: ...

    def __iter__(self) -> Iterator[_RelatedModel]: ...


class ManyToManyDescriptor(Protocol[_RelatedModel]):
    @overload
    def __get__(self, instance: None, owner: type[Any] | None = None) -> Any: ...

    @overload
    def __get__(self, instance: object, owner: type[Any] | None = None) -> ManyToManyRelation[_RelatedModel]: ...

    def get_through_model(self) -> Any: ...


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
) -> SerializedModel: ...


@overload
def model_serializer(
    obj: Iterable[BaseModel] | ModelSelect,
    many: bool = True,
    manytomany: bool = False,
    fields: Optional[List[str]] = None,
) -> SerializedModelList: ...


def model_serializer(
    obj: BaseModel | Iterable[BaseModel] | ModelSelect,
    many: bool = False,
    manytomany: bool = False,
    fields: Optional[List[str]] = None,
) -> SerializedModel | SerializedModelList:
    iterable_obj = obj
    if fields:
        if many:
            iterable_obj = list(obj)
            if not iterable_obj:
                return []
            model_class = iterable_obj[0].__class__
        else:
            model_class = obj.__class__
        fields = get_model_fields(model_class, fields)

    if many:
        results = []
        for o in iterable_obj:
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
