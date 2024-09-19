# @Author: Bi Ying
# @Date:   2024-06-06 16:04:26
import uuid
from pathlib import Path

from diskcache import Deque
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Filter,
    Distance,
    MatchValue,
    PointStruct,
    VectorParams,
    FilterSelector,
    FieldCondition,
)
from vectorvein.types.enums import BackendType
from vectorvein.chat_clients.utils import format_messages

from models import Workflow, WorkflowTemplate, UserObject
from utilities.general import mprint
from utilities.config import config, cache
from utilities.ai_utils import (
    ToolCallData,
    EmbeddingClient,
    conversation_title_generator,
)

tasks_registry = {}

tasks_queue = Deque(directory=Path(config.data_path) / "cache" / "background_task")
qdrant_tasks_queue = Deque(directory=Path(config.data_path) / "cache" / "qdrant_task")


def background_task(func):
    tasks_registry[func.__name__] = func

    def wrapper(*args, **kwargs):
        task_id = uuid.uuid4().hex
        task = {"task_name": func.__name__, "task_id": task_id, "args": args, "kwargs": kwargs}
        if is_qdrant_task(func.__name__):
            qdrant_tasks_queue.appendleft(task)
        else:
            tasks_queue.appendleft(task)
        mprint(f"Task {task_id} {func.__name__} added to queue.")
        return task["task_id"]

    wrapper.delay = wrapper  # Alias for .delay()
    return wrapper


def get_task(task_name):
    return tasks_registry.get(task_name)


def is_qdrant_task(task_name):
    return task_name.startswith("q_")


@background_task
def update_workflow_tool_call_data(
    workflow_wid: str | None = None,
    template_tid: str | None = None,
    force: bool = False,
):
    if workflow_wid:
        workflow = Workflow.get(Workflow.wid == workflow_wid)
    elif template_tid:
        workflow = WorkflowTemplate.get(WorkflowTemplate.tid == template_tid)
    else:
        return False

    tool_call_data = ToolCallData(workflow)
    tool_call_data.update_title(force=force)
    tool_call_data.update_parameters()
    tool_call_data.save()


@background_task
def summarize_conversation_title(
    message_id: str,
    messasges: list,
    backend: BackendType = BackendType.OpenAI,
    model: str = "gpt-4o-mini",
):
    formatted_messages = format_messages(messages=messasges, backend=backend)
    conversation_title = conversation_title_generator(formatted_messages, backend=backend, model=model)[:40]
    cache.set(f"conversation-title:{message_id}", conversation_title, expire=60 * 60)


@background_task
def q_create_collection(client: QdrantClient, vid: str, size: int = 768):
    try:
        client.recreate_collection(
            collection_name=f"{vid}_text_collection",
            vectors_config=VectorParams(size=size, distance=Distance.COSINE),
            on_disk_payload=True,
        )
        return True
    except Exception as e:
        mprint.error(e)
        return False


@background_task
def q_delete_collection(client: QdrantClient, vid: str):
    try:
        client.delete_collection(f"{vid}_text_collection")
        return True
    except Exception as e:
        mprint.error(e)
        return False


@background_task
def q_add_point(client: QdrantClient, vid: str, point: dict):
    try:
        client.upsert(
            collection_name=f"{vid}_text_collection",
            points=[
                PointStruct(
                    id=uuid.uuid4().hex,
                    payload={
                        "object_id": point.get("object_id"),
                        "text": point.get("text"),
                        "embedding_type": point.get("embedding_type"),
                        "extra_data": point.get("extra_data"),
                    },
                    vector=point.get("embedding"),
                ),
            ],
        )
        if point.get("chunk_index") == point.get("chunk_count") - 1:
            user_object: UserObject = UserObject.get(UserObject.oid == point.get("object_id"))
            user_object.status = "VA"
            user_object.save()
        cache.set(
            f"qdrant-point-progress:{vid}:{point.get('object_id')}",
            {"chunk_index": point.get("chunk_index"), "chunk_count": point.get("chunk_count")},
            expire=60 * 60,
        )
        return True
    except Exception as e:
        mprint.error(e)
        return False


@background_task
def embedding_and_upload(
    vid: str,
    object_id: str,
    input: str | list,
    embedding_provider: str,
    embedding_model: str,
    embedding_type: str,
    embedding_dimensions: int | None = None,
    extra_data: dict | None = None,
):
    input = input if isinstance(input, list) else [input]
    if extra_data is None:
        extra_data = {}

    embedding_client = EmbeddingClient(
        provider=embedding_provider, model_id=embedding_model, dimensions=embedding_dimensions
    )
    for index, text in enumerate(input):
        embedding = embedding_client.get(text)
        q_add_point.delay(
            vid=vid,
            point={
                "object_id": object_id,
                "text": text,
                "embedding": embedding,
                "embedding_type": embedding_type,
                "extra_data": extra_data,
                "chunk_index": index,
                "chunk_count": len(input),
            },
        )
    return True


@background_task
def q_delete_point(client: QdrantClient, vid: str, object_id: str):
    try:
        client.delete(
            collection_name=f"{vid}_text_collection",
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="object_id",
                            match=MatchValue(value=object_id),
                        ),
                    ],
                )
            ),
        )
        return True
    except Exception as e:
        mprint.error(e)
        return False


@background_task
def q_search_point(
    client: QdrantClient,
    vid: str,
    text_embedding: list,
    limit: int = 5,
):
    text_hits = client.search(
        collection_name=f"{vid}_text_collection",
        query_vector=text_embedding,
        limit=limit,
    )
    return [hit.payload for hit in text_hits]
