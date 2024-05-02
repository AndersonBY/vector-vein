# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-13 15:45:13
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-05-02 19:36:59
from worker.tasks import task, timer
from utilities.settings import Settings
from utilities.workflow import Workflow
from utilities.text import split_text
from utilities.embeddings import get_embedding_from_open_ai
from models import UserObject, UserVectorDatabase


@task
@timer
def add_data(
    workflow_data: dict,
    node_id: str,
    vdb_queues: dict,
):
    settings = Settings()
    vdb_request_queue = vdb_queues["request"]
    workflow = Workflow(workflow_data)
    text = workflow.get_node_field_value(node_id, "text")
    content_title = workflow.get_node_field_value(node_id, "content_title")
    source_url = workflow.get_node_field_value(node_id, "source_url")
    database_vid = workflow.get_node_field_value(node_id, "database")
    database = UserVectorDatabase.get(vid=database_vid)
    user_object = UserObject.create(
        title=content_title,
        info=dict(),
        data_type=workflow.get_node_field_value(node_id, "data_type").upper(),
        vector_database=database,
        source_url=source_url,
        raw_data={
            "text": text,
            "title": content_title,
            "source_url": source_url,
        },
        embeddings=list(),
    )
    object_id = user_object.oid.hex
    workflow.update_node_field_value(node_id, "object_id", object_id)

    split_method = workflow.get_node_field_value(node_id, "split_method")
    chunk_length = workflow.get_node_field_value(node_id, "chunk_length")
    chunk_overlap = workflow.get_node_field_value(node_id, "chunk_overlap")
    delimiter = workflow.get_node_field_value(node_id, "delimiter")

    process_rules = {
        "split_method": split_method,
        "chunk_length": chunk_length,
        "chunk_overlap": chunk_overlap,
        "delimiter": delimiter,
    }

    paragraphs = split_text(text=text, rules=process_rules, flat=False)
    for paragraph in paragraphs:
        paragraph_embedding = get_embedding_from_open_ai(paragraph["text"], settings.data)
        vdb_request_queue.put(
            {
                "function_name": "add_point",
                "parameters": dict(
                    vid=database_vid,
                    point={
                        "object_id": user_object.oid.hex,
                        "text": paragraph["text"],
                        "embedding_type": user_object.data_type.lower(),
                        "embedding": paragraph_embedding,
                        "extra_data": {"paragraph_id": paragraph["index"]},
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

    return workflow.data


@task
@timer
def delete_data(
    workflow_data: dict,
    node_id: str,
    vdb_queues: dict,
):
    vdb_request_queue = vdb_queues["request"]
    workflow = Workflow(workflow_data)
    object_id = workflow.get_node_field_value(node_id, "object_id")
    database_vid = workflow.get_node_field_value(node_id, "database")
    user_object = UserObject.get(oid=object_id)
    vdb_request_queue.put(
        {
            "function_name": "delete_point",
            "parameters": dict(vid=database_vid, object_id=object_id),
        }
    )
    user_object.delete_instance()
    workflow.update_node_field_value(node_id, "delete_success", True)
    return workflow.data


@task
@timer
def search_data(
    workflow_data: dict,
    node_id: str,
    vdb_queues: dict,
):
    settings = Settings()
    vdb_request_queue = vdb_queues["request"]
    vdb_response_queue = vdb_queues["response"]
    workflow = Workflow(workflow_data)
    search_text = workflow.get_node_field_value(node_id, "search_text")
    output_type = workflow.get_node_field_value(node_id, "output_type")
    database_vid = workflow.get_node_field_value(node_id, "database")
    count = workflow.get_node_field_value(node_id, "count")

    if isinstance(search_text, str):
        search_texts = [search_text]
    elif isinstance(search_text, list):
        search_texts = search_text

    results = []
    for text in search_texts:
        text_embedding = get_embedding_from_open_ai(text, settings.data)
        vdb_request_queue.put(
            {
                "function_name": "search_point",
                "parameters": dict(
                    vid=database_vid,
                    text_embedding=text_embedding,
                    limit=count,
                ),
            }
        )
        search_results = vdb_response_queue.get()
        vdb_response_queue.task_done()

        if output_type == "text":
            results.append("\n".join([result["text"] for result in search_results]))
        elif output_type == "list":
            results.append([result["text"] for result in search_results])

    workflow.update_node_field_value(node_id, "output", results if isinstance(search_text, list) else results[0])
    return workflow.data
