# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-13 15:45:13
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-09-23 23:17:14
from worker.tasks import task
from utilities.workflow import Workflow
from utilities.text_splitter import TokenTextSplitter
from utilities.embeddings import get_embedding_from_open_ai
from models import UserObject, UserVectorDatabase


@task
def add_data(
    workflow_data: dict,
    node_id: str,
    vdb_queues: dict,
):
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
    if split_method == "general":
        text_splitter = TokenTextSplitter(chunk_size=chunk_length, chunk_overlap=30, model_name="gpt-3.5-turbo")
        paragraphs = text_splitter.create_documents([text])
    for paragraph_id, paragraph in enumerate(paragraphs):
        paragraph_embedding = get_embedding_from_open_ai(paragraph, workflow.setting)
        vdb_request_queue.put(
            {
                "function_name": "add_point",
                "parameters": dict(
                    vid=database_vid,
                    point={
                        "object_id": object_id,
                        "text": paragraph,
                        "embedding_type": user_object.data_type.lower(),
                        "embedding": paragraph_embedding,
                        "extra_data": {"paragraph_id": paragraph_id},
                    },
                ),
            }
        )

    return workflow.data


@task
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
def search_data(
    workflow_data: dict,
    node_id: str,
    vdb_queues: dict,
):
    vdb_request_queue = vdb_queues["request"]
    vdb_response_queue = vdb_queues["response"]
    workflow = Workflow(workflow_data)
    search_text = workflow.get_node_field_value(node_id, "search_text")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    if isinstance(search_text, str):
        search_texts = [search_text]
    elif isinstance(search_text, list):
        search_texts = search_text

    results = []
    for text in search_texts:
        text_embedding = get_embedding_from_open_ai(text, workflow.setting)
        vdb_request_queue.put(
            {
                "function_name": "search_point",
                "parameters": dict(
                    vid=workflow.get_node_field_value(node_id, "database"),
                    text_embedding=text_embedding,
                    limit=workflow.get_node_field_value(node_id, "count"),
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
