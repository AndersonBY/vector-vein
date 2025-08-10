# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-01 11:25:34
from pathlib import Path
from datetime import datetime

from models import (
    UserObject,
    model_serializer,
    UserVectorDatabase,
)
from api.utils import get_user_object_general, JResponse
from utilities.config import cache
from utilities.text_processing import split_text
from utilities.network import crawl_text_from_url
from utilities.file_processing import get_files_contents
from celery_tasks import (
    embedding_and_upload,
    delete_point,
    create_collection,
    delete_collection,
)


class DatabaseAPI:
    name = "database"

    def get(self, payload):
        status, msg, database = get_user_object_general(
            UserVectorDatabase,
            vid=payload.get("vid", None),
        )
        if status != 200 or isinstance(database, dict):
            return JResponse(status=status, msg=msg)

        return JResponse(data=model_serializer(database))

    def update(self, payload):
        status, msg, database = get_user_object_general(
            UserVectorDatabase,
            vid=payload.get("vid", None),
        )
        if status != 200 or isinstance(database, dict):
            return JResponse(status=status, msg=msg)

        database.name = payload.get("name", database.name)
        database.update_time = datetime.now()
        database.save()
        return JResponse()

    def list(self, payload):
        databases = UserVectorDatabase.select().order_by(UserVectorDatabase.create_time.desc())
        return JResponse(data=model_serializer(databases, many=True))

    def create(self, payload):
        database: UserVectorDatabase = UserVectorDatabase.create(
            name=payload.get("name", ""),
            embedding_size=payload.get("embedding_size", 1536),
            embedding_model=payload.get("embedding_model", "text-embedding-ada-002"),
            embedding_provider=payload.get("embedding_provider", "openai"),
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
        if status != 200 or isinstance(database, dict):
            return JResponse(status=status, msg=msg)

        delete_collection.delay(vid=database.vid.hex)
        database.delete_instance(recursive=True)
        return JResponse()


class DatabaseObjectAPI:
    name = "database_object"

    def get(self, payload):
        status, msg, user_object = get_user_object_general(
            UserObject,
            oid=payload.get("oid", None),
        )
        if status != 200 or isinstance(user_object, dict):
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
            paragraphs = split_text(user_object.raw_data["text"], process_rules)
            embedding_and_upload.delay(
                vid=vector_database.vid.hex,
                object_id=user_object.oid.hex,
                input=[paragraph["text"] for paragraph in paragraphs],
                embedding_provider=vector_database.embedding_provider,
                embedding_model=vector_database.embedding_model,
                embedding_dimensions=vector_database.embedding_size,
                embedding_type=user_object.data_type.lower(),
            )

            user_object.info["word_counts"] = sum([paragraph["word_counts"] for paragraph in paragraphs])
            user_object.info["paragraph_counts"] = len(paragraphs)
            user_object.info["process_rules"] = process_rules
            user_object.raw_data["segments"] = paragraphs
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
        if status != 200 or isinstance(user_object, dict):
            return JResponse(status=status, msg=msg)

        user_object.title = payload.get("title", "")
        user_object.info = payload.get("info", {})
        user_object.update_time = datetime.now()
        user_object.save()
        return JResponse()

    def delete(self, payload):
        status, msg, user_object = get_user_object_general(
            UserObject,
            oid=payload.get("oid", None),
        )
        if status != 200 or isinstance(user_object, dict):
            return JResponse(status=status, msg=msg)
        delete_point.delay(vid=user_object.vector_database.vid.hex, object_id=user_object.oid.hex)
        user_object.delete_instance(recursive=True)
        return JResponse()
