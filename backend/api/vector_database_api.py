# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-01 11:25:34
from collections.abc import Mapping
from pathlib import Path
from datetime import datetime
from typing import Any

from models import (
    UserObject,
    model_serializer,
    UserVectorDatabase,
)
from api.utils import get_user_object_general, JResponse
from utilities.config import cache, Settings
from utilities.text_processing import split_text
from utilities.network import crawl_text_from_url
from utilities.file_processing import get_files_contents
from background_task.qdrant_tasks import search_points_sync
from celery_tasks import (
    embedding_and_upload,
    delete_point,
    create_collection,
    delete_collection,
)


def _hex_attr(model: Any, attr_name: str) -> str:
    return str(getattr(getattr(model, attr_name), "hex"))


def _normalize_embedding_provider(provider: str, model: str) -> tuple[str, str]:
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip()
    if normalized_provider == "text-embeddings-inference":
        return "custom", "text-embeddings-inference"
    return normalized_provider, normalized_model


def _iter_embedding_backend_models(backends: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    ordered_models: list[tuple[str, dict[str, Any]]] = []
    for model_key, model_settings in reversed(list(backends.items())):
        if isinstance(model_settings, Mapping):
            ordered_models.append((model_key, dict(model_settings)))
    return ordered_models


def _resolve_embedding_selection(
    provider: str | None,
    model: str | None,
    dimensions: int | None,
) -> tuple[str, str, int]:
    settings = Settings()
    raw_backends = settings.get("llm_settings.embedding_backends", {})
    embedding_backends = raw_backends if isinstance(raw_backends, Mapping) else {}

    normalized_provider = provider.strip().lower() if isinstance(provider, str) else ""
    normalized_model = model.strip() if isinstance(model, str) else ""

    if normalized_provider:
        normalized_provider, normalized_model = _normalize_embedding_provider(normalized_provider, normalized_model)
        selected_backend = embedding_backends.get(normalized_provider)
        if not isinstance(selected_backend, Mapping):
            raise ValueError(f"Embedding backend '{normalized_provider}' is not configured.")
        selected_models = selected_backend.get("models", {})
        if not isinstance(selected_models, Mapping) or not selected_models:
            raise ValueError(f"Embedding backend '{normalized_provider}' has no configured models.")
        if not normalized_model:
            normalized_model = _iter_embedding_backend_models(selected_models)[0][0]
    else:
        selected_backend = None
        selected_models = None
        for backend_key, backend_settings in embedding_backends.items():
            if not isinstance(backend_settings, Mapping):
                continue
            backend_models = backend_settings.get("models", {})
            if not isinstance(backend_models, Mapping) or not backend_models:
                continue
            normalized_provider = backend_key
            selected_backend = backend_settings
            selected_models = backend_models
            normalized_model = _iter_embedding_backend_models(backend_models)[0][0]
            break

        if selected_backend is None or selected_models is None:
            raise ValueError("No embedding models are configured. Configure them in Settings > Embedding models first.")

    model_settings = selected_models.get(normalized_model)
    if not isinstance(model_settings, Mapping):
        raise ValueError(f"Embedding model '{normalized_model}' is not configured for backend '{normalized_provider}'.")

    resolved_dimensions = dimensions if isinstance(dimensions, int) and dimensions > 0 else model_settings.get("dimensions")
    if not isinstance(resolved_dimensions, int) or resolved_dimensions <= 0:
        resolved_dimensions = 1536

    return normalized_provider, normalized_model, resolved_dimensions


class DatabaseAPI:
    name = "database"

    def get(self, payload):
        status, msg, database = get_user_object_general(
            UserVectorDatabase,
            vid=payload.get("vid", None),
        )
        if status != 200 or database is None:
            return JResponse(status=status, msg=msg)

        return JResponse(data=model_serializer(database))

    def update(self, payload):
        status, msg, database = get_user_object_general(
            UserVectorDatabase,
            vid=payload.get("vid", None),
        )
        if status != 200 or database is None:
            return JResponse(status=status, msg=msg)

        name = payload.get("name")
        if isinstance(name, str):
            database.name = name
        database.update_time = datetime.now()
        database.save()
        return JResponse()

    def list(self, payload):
        databases = UserVectorDatabase.select().order_by(UserVectorDatabase.create_time.desc())
        return JResponse(data=model_serializer(databases, many=True))

    def create(self, payload):
        try:
            embedding_provider, embedding_model, embedding_size = _resolve_embedding_selection(
                payload.get("embedding_provider"),
                payload.get("embedding_model"),
                payload.get("embedding_size"),
            )
        except ValueError as error:
            return JResponse(status=400, msg=str(error))

        database: UserVectorDatabase = UserVectorDatabase.create(
            name=payload.get("name", ""),
            embedding_size=embedding_size,
            embedding_model=embedding_model,
            embedding_provider=embedding_provider,
        )
        create_collection.delay(vid=database.vid.hex, size=database.embedding_size)
        # TODO: Get create result
        database.status = "VALID"
        database.save()
        return JResponse(data=model_serializer(database))

    def delete(self, payload):
        status, msg, database = get_user_object_general(
            UserVectorDatabase,
            vid=payload.get("vid", None),
        )
        if status != 200 or database is None:
            return JResponse(status=status, msg=msg)

        delete_collection.delay(vid=_hex_attr(database, "vid"))
        database.delete_instance(recursive=True)
        return JResponse()

    def search(self, payload):
        vid = payload.get("vid")
        query = payload.get("query", "")
        limit = int(payload.get("limit", 10))

        if not vid or not query:
            return JResponse(status=400, msg="vid and query are required")

        status, msg, database = get_user_object_general(
            UserVectorDatabase,
            vid=vid,
        )
        if status != 200 or database is None:
            return JResponse(status=status, msg=msg)

        try:
            from utilities.ai_utils import EmbeddingClient

            embedding_client = EmbeddingClient(
                provider=database.embedding_provider,
                model_id=database.embedding_model,
            )
            text_embedding = embedding_client.get(query)
            results = search_points_sync(
                vid=_hex_attr(database, "vid"),
                text_embedding=text_embedding,
                limit=limit,
            )
            return JResponse(data={"results": results or []})
        except Exception as e:
            return JResponse(status=500, msg=str(e))


class DatabaseObjectAPI:
    name = "database_object"

    def get(self, payload):
        status, msg, user_object = get_user_object_general(
            UserObject,
            oid=payload.get("oid", None),
        )
        if status != 200 or user_object is None:
            return JResponse(status=status, msg=msg)

        return JResponse(data=model_serializer(user_object))

    def create(self, payload):
        title = payload.get("title", "")
        source_url = payload.get("source_url", "")
        add_method = payload.get("add_method", "")
        files = payload.get("files", [])
        content = payload.get("content", "")
        process_rules = payload.get("process_rules", {})

        vector_database: UserVectorDatabase = UserVectorDatabase.get(vid=payload.get("vid"))
        object_oids = []
        if add_method == "files":
            for file in files:
                file_name = Path(file).name
                user_object = UserObject.create(
                    title=file_name,
                    info=payload.get("info", {}),
                    data_type=payload.get("data_type", "TEXT"),
                    vector_database=vector_database,
                    source_url="",
                    raw_data={"text": "", "file": file},
                    status="PR",
                )
                object_oids.append(user_object.oid)
        else:
            user_object = UserObject.create(
                title=title,
                info=payload.get("info", {}),
                data_type=payload.get("data_type", "TEXT"),
                vector_database=vector_database,
                source_url=source_url,
                raw_data={"text": content},
                status="PR",
            )
            object_oids.append(user_object.oid)

        user_objects = []
        if add_method == "url":
            user_object = UserObject.get(oid=object_oids[0])
            result = crawl_text_from_url(user_object.source_url)
            user_object.title = result["title"]
            user_object.raw_data = result
            user_object.save()
            user_objects.append(user_object)
        elif add_method == "text":
            user_object = UserObject.get(oid=object_oids[0])
            user_objects.append(user_object)
        elif add_method == "files":
            for user_object_oid in object_oids:
                user_object = UserObject.get(oid=user_object_oid)
                result = get_files_contents([user_object.raw_data["file"]])[0]
                user_object.raw_data["text"] = result
                user_object.save()
                user_objects.append(user_object)

        for user_object in user_objects:
            raw_data = user_object.raw_data if isinstance(user_object.raw_data, dict) else {}
            paragraphs = split_text(str(raw_data.get("text", "")), process_rules)
            segment_dicts = [paragraph for paragraph in paragraphs if isinstance(paragraph, dict)]
            embedding_and_upload.delay(
                vid=_hex_attr(vector_database, "vid"),
                object_id=_hex_attr(user_object, "oid"),
                input=[str(paragraph.get("text", "")) for paragraph in segment_dicts],
                embedding_provider=vector_database.embedding_provider,
                embedding_model=vector_database.embedding_model,
                embedding_dimensions=vector_database.embedding_size,
                embedding_type=user_object.data_type.lower(),
            )

            object_info = user_object.info if isinstance(user_object.info, dict) else {}
            object_info["word_counts"] = sum(int(paragraph.get("word_counts", 0)) for paragraph in segment_dicts)
            object_info["paragraph_counts"] = len(segment_dicts)
            object_info["process_rules"] = process_rules
            user_object.info = object_info
            raw_data["segments"] = segment_dicts
            user_object.raw_data = raw_data
            user_object.save()

        if add_method == "files":
            return JResponse(data=model_serializer(user_objects, many=True))
        else:
            return JResponse(data=model_serializer(user_objects[0]))

    def list(self, payload):
        page_num = int(payload.get("page", 1))
        page_size = min(int(payload.get("page_size", 10)), 100)
        sort_field = payload.get("sort_field", "create_time")
        sort_order = payload.get("sort_order", "descend")

        sort_field_obj = getattr(UserVectorDatabase, sort_field)
        if sort_order == "descend":
            sort_field_obj = sort_field_obj.desc()

        database_vid = payload.get("vid")
        user_objects = UserObject.select().join(UserVectorDatabase).where(UserVectorDatabase.vid == database_vid)

        user_objects_count = user_objects.count()
        offset = (page_num - 1) * page_size
        limit = page_size

        user_objects = user_objects.order_by(sort_field_obj).offset(offset).limit(limit)
        user_objects_list = model_serializer(user_objects, many=True)

        for user_object in user_objects_list:
            if user_object["status"] == "PR":
                user_object["progress"] = cache.get(f"qdrant-point-progress:{database_vid}:{user_object['oid']}")

        return JResponse(
            data={
                "objects": user_objects_list,
                "total": user_objects_count,
                "page_size": page_size,
                "page": page_num,
            }
        )

    def update(self, payload):
        status, msg, user_object = get_user_object_general(
            UserObject,
            oid=payload.get("oid"),
        )
        if status != 200 or user_object is None:
            return JResponse(status=status, msg=msg)

        title = payload.get("title")
        info = payload.get("info")
        if isinstance(title, str):
            user_object.title = title
        user_object.info = info if isinstance(info, dict) else {}
        user_object.update_time = datetime.now()
        user_object.save()
        return JResponse()

    def delete(self, payload):
        status, msg, user_object = get_user_object_general(
            UserObject,
            oid=payload.get("oid", None),
        )
        if status != 200 or user_object is None:
            return JResponse(status=status, msg=msg)
        delete_point.delay(
            vid=_hex_attr(user_object.vector_database, "vid"),
            object_id=_hex_attr(user_object, "oid"),
        )
        user_object.delete_instance(recursive=True)
        return JResponse()
