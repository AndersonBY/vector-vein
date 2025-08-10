# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-13 15:45:13
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-25 18:27:50
import time

from worker.tasks import task, timer
from utilities.config import cache
from utilities.workflow import Workflow
from utilities.general import mprint_with_name
from utilities.ai_utils import EmbeddingClient
from utilities.text_processing import split_text, remove_markdown_image
from celery_tasks import (
    embedding_and_upload,
    delete_point,
    search_point,
)
from models import UserObject, UserVectorDatabase


mprint = mprint_with_name(name="Vector Database Tasks")


@task
@timer
def add_data(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    raw_text = workflow.get_node_field_value(node_id, "text")
    raw_content_title = workflow.get_node_field_value(node_id, "content_title")
    raw_source_url = workflow.get_node_field_value(node_id, "source_url")

    split_method = workflow.get_node_field_value(node_id, "split_method")
    chunk_length = workflow.get_node_field_value(node_id, "chunk_length")
    chunk_overlap = workflow.get_node_field_value(node_id, "chunk_overlap", 30)
    delimiter = workflow.get_node_field_value(node_id, "delimiter", "\\n")
    remove_url_and_email = workflow.get_node_field_value(node_id, "remove_url_and_email", True)
    process_rules = {
        "split_method": split_method,
        "chunk_length": chunk_length,
        "chunk_overlap": chunk_overlap,
        "delimiter": delimiter,
        "remove_url_and_email": remove_url_and_email,
    }

    data_type = workflow.get_node_field_value(node_id, "data_type")
    wait_for_processing = workflow.get_node_field_value(node_id, "wait_for_processing", False)

    if isinstance(raw_text, str):
        texts = [raw_text]
    else:
        texts = raw_text
    if isinstance(raw_content_title, str):
        content_titles = [raw_content_title]
    else:
        content_titles = raw_content_title
    if isinstance(raw_source_url, str):
        source_urls = [raw_source_url]
    else:
        source_urls = raw_source_url

    if not (len(texts) == len(content_titles) == len(source_urls)):
        max_length = max(len(texts), len(content_titles), len(source_urls))
        if len(texts) == 1:
            texts = texts * max_length
        if len(content_titles) == 1:
            content_titles = content_titles * max_length
        if len(source_urls) == 1:
            source_urls = source_urls * max_length

    database_vid = workflow.get_node_field_value(node_id, "database")
    vector_database = UserVectorDatabase.get(vid=database_vid)

    data_count = len(texts)
    object_ids = []
    content_length = 0
    for index, (text, content_title, source_url) in enumerate(zip(texts, content_titles, source_urls)):
        mprint(f"Adding data {index + 1}/{data_count} to database {database_vid}")
        text = remove_markdown_image(text)
        content_length += len(text)

        user_object = UserObject.create(
            title=content_title,
            info=dict(),
            data_type=data_type.upper(),
            vector_database=vector_database,
            source_url=source_url,
            raw_data={
                "text": text,
                "title": content_title,
                "source_url": source_url,
            },
            embeddings=list(),
        )
        object_id = user_object.oid.hex
        object_ids.append(object_id)

        paragraphs = split_text(text=text, rules=process_rules, flat=False)
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

    all_objects_processed = False
    sleep_interval = content_length // 10000 + 1
    while not all_objects_processed and wait_for_processing:
        time.sleep(sleep_interval)
        user_objects = UserObject.select().where(UserObject.oid.in_(object_ids))
        all_objects_processed = all(user_object.status != "PR" for user_object in user_objects)
        mprint.debug(f"Waiting for all objects to be processed: {object_ids}")
        mprint.debug(f"Next check in {sleep_interval} seconds")

    if all(
        (
            isinstance(raw_text, str),
            isinstance(raw_content_title, str),
            isinstance(raw_source_url, str),
        )
    ):
        workflow.update_node_field_value(node_id, "object_id", object_ids[0])
    else:
        workflow.update_node_field_value(node_id, "object_id", object_ids)

    return workflow.data


@task
@timer
def delete_data(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    object_id = workflow.get_node_field_value(node_id, "object_id")
    database_vid = workflow.get_node_field_value(node_id, "database")
    user_object = UserObject.get(oid=object_id)
    delete_point.delay(vid=database_vid, object_id=object_id)
    user_object.delete_instance(recursive=True)
    workflow.update_node_field_value(node_id, "delete_success", True)
    return workflow.data


@task
@timer
def search_data(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    search_text = workflow.get_node_field_value(node_id, "search_text")
    output_type = workflow.get_node_field_value(node_id, "output_type")
    database_vid = workflow.get_node_field_value(node_id, "database")
    vector_database: UserVectorDatabase = UserVectorDatabase.get(vid=database_vid)
    count = workflow.get_node_field_value(node_id, "count")

    if isinstance(search_text, str):
        search_texts = [search_text]
    elif isinstance(search_text, list):
        search_texts = search_text
    else:
        raise ValueError(f"Unsupported search_text type: {type(search_text)}")

    embedding_client = EmbeddingClient(
        provider=vector_database.embedding_provider, model_id=vector_database.embedding_model
    )

    results = []
    for text in search_texts:
        text_embedding = embedding_client.get(text)
        task_id = search_point.delay(
            vid=database_vid,
            text_embedding=text_embedding,
            limit=count,
        )
        search_results = cache.get(f"task_result_{task_id}", None)
        while search_results is None:
            time.sleep(0.1)
            search_results = cache.get(f"task_result_{task_id}", None)

        if output_type == "text":
            results.append("\n".join([result["text"] for result in search_results]))
        elif output_type == "list":
            results.append([result["text"] for result in search_results])

    workflow.update_node_field_value(node_id, "output", results if isinstance(search_text, list) else results[0])
    return workflow.data
