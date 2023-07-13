# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-07-14 01:28:49
from pathlib import Path

from models import (
    Setting,
    UserObject,
    model_serializer,
    UserVectorDatabase,
)
from api.utils import get_user_object_general
from utilities.files import get_files_contents
from utilities.web_crawler import crawl_text_from_url
from utilities.text_splitter import general_split_text
from utilities.embeddings import get_embedding_from_open_ai


class DatabaseAPI:
    name = "database"

    def get(self, payload):
        status, msg, database = get_user_object_general(
            UserVectorDatabase,
            vid=payload.get("vid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        database = model_serializer(database)
        response = {"status": 200, "msg": "success", "data": database}
        return response

    def list(self, payload):
        databases = UserVectorDatabase.select().order_by("create_time")
        databases_list = model_serializer(databases, many=True)
        response = {"status": 200, "msg": "success", "data": databases_list}
        return response

    def create(self, payload):
        embedding_model = payload.get("embedding_model", "text-embedding-ada-002")
        database: UserVectorDatabase = UserVectorDatabase.create(
            name=payload.get("name", ""),
            embedding_model=embedding_model,
        )
        self.vdb_queues["request"].put(
            {
                "function_name": "create_collection",
                "parameters": dict(vid=database.vid.hex, size=database.embedding_size),
            }
        )
        # TODO: Get create result
        database.status = "VALID"
        database.save()
        database = model_serializer(database)
        response = {"status": 200, "msg": "success", "data": database}
        return response

    def delete(self, payload):
        status, msg, database = get_user_object_general(
            UserVectorDatabase,
            vid=payload.get("vid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        self.vdb_queues["request"].put(
            {
                "function_name": "delete_collection",
                "parameters": dict(vid=database.vid.hex),
            }
        )
        database.delete_instance()
        response = {"status": 200, "msg": "success", "data": {}}
        return response


class DatabaseObjectAPI:
    name = "database_object"

    def get(self, payload):
        status, msg, user_object = get_user_object_general(
            UserObject,
            oid=payload.get("oid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        user_object = model_serializer(user_object)
        response = {"status": 200, "msg": "success", "data": user_object}
        return response

    def create(self, payload):
        title = payload.get("title", "")
        source_url = payload.get("source_url", "")
        add_method = payload.get("add_method", "")
        files = payload.get("files", [])
        content = payload.get("content", "")
        process_rules = payload.get("process_rules", {})

        vector_database = UserVectorDatabase.get(vid=payload.get("vid"))
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

        setting = Setting.select().order_by(Setting.create_time.desc()).first()
        for user_object in user_objects:
            paragraphs = general_split_text(user_object.raw_data["text"], process_rules)
            for paragraph in paragraphs:
                paragraph_embedding = get_embedding_from_open_ai(paragraph["text"], setting.data)
                self.vdb_queues["request"].put(
                    {
                        "function_name": "add_point",
                        "parameters": dict(
                            vid=vector_database.vid.hex,
                            point={
                                "object_id": user_object.oid.hex,
                                "text": paragraph["text"],
                                "embedding_type": user_object.data_type.lower(),
                                "embedding": paragraph_embedding,
                            },
                        ),
                    }
                )

            user_object.info["word_counts"] = sum([paragraph["word_counts"] for paragraph in paragraphs])
            user_object.info["paragraph_counts"] = len(paragraphs)
            user_object.info["process_rules"] = process_rules
            user_object.raw_data["segments"] = paragraphs
            user_object.status = "VA"
            user_object.save()
        user_object = model_serializer(user_object)
        response = {"status": 200, "msg": "success", "data": user_object}
        return response

    def list(self, payload):
        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field = payload.get("sort_field", "create_time")
        sort_order = payload.get("sort_order", "descend")
        sort_field = f"-{sort_field}" if sort_order == "descend" else sort_field
        user_objects = (
            UserObject.select().join(UserVectorDatabase).where(UserVectorDatabase.vid == payload.get("vid", None))
        )
        user_objects_count = user_objects.count()
        offset = (page_num - 1) * page_size
        limit = page_size
        user_objects = user_objects.order_by(sort_field).offset(offset).limit(limit)
        user_objects_list = model_serializer(user_objects, many=True)
        response = {
            "status": 200,
            "msg": "success",
            "data": {
                "objects": user_objects_list,
                "total": user_objects_count,
                "page_size": page_size,
                "page": page_num,
            },
        }
        return response

    def delete(self, payload):
        status, msg, user_object = get_user_object_general(
            UserObject,
            oid=payload.get("oid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        self.vdb_queues["request"].put(
            {
                "function_name": "delete_point",
                "parameters": dict(vid=user_object.vector_database.vid.hex, object_id=user_object.oid.hex),
            }
        )
        user_object.delete_instance()
        response = {"status": 200, "msg": "success", "data": {}}
        return response
