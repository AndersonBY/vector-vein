# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 14:21:40
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-01 18:34:20
from datetime import datetime
from typing import Any, Literal, Type, TypeVar, cast, overload

from models import (
    Message,
    Workflow,
    model_serializer,
    WorkflowRunRecord,
)
from models.base import BaseModel, SerializedModelList
from utilities.general import mprint_with_name
from utilities.config import cache


mprint = mprint_with_name(name="Workflow Runner")


T = TypeVar("T", bound=BaseModel)


def get_user_object_general(ObjectClass: Type[T], **kwargs) -> tuple[int, str, T | None]:
    if len(kwargs) == 0:
        return 500, "wrong args", None
    try:
        object = ObjectClass.get(*[getattr(ObjectClass, key) == value for key, value in kwargs.items()])
    except ObjectClass.DoesNotExist:
        return 404, "not exist", None
    return 200, "", object


@overload
def get_history_messages(
    start_message: Message,
    count: int | None = 10,
    all_children: Literal[True] = True,
) -> list[SerializedModelList]: ...


@overload
def get_history_messages(
    start_message: Message,
    count: int | None = 10,
    all_children: Literal[False] = False,
) -> SerializedModelList: ...


def get_history_messages(
    start_message: Message,
    count: int | None = 10,
    all_children: bool = True,
) -> SerializedModelList | list[SerializedModelList]:
    """_summary_

    Args:
        start_message (Message): 起始消息。将从该消息开始向上遍历父消息。
        count (int | None, optional): 消息数量，如果是 None 则返回全部消息。Defaults to 10.
        all_children (bool, optional): 对于同一个父节点的消息，是否获取全部子节点消息。Defaults to True.

        当不获取全部子节点消息时，只返回起始消息所在的父链，不替换为其它版本。
        同时返回结果是list[dict]，每个dict是一个消息的信息。

        当获取全部子节点消息时，返回结果是list[list[dict]]，每个list[dict]是一个父节点消息的全部子节点消息。

    Returns:
        list[dict] | list[list[dict]]: _description_
    """
    history: SerializedModelList | list[SerializedModelList]
    history = []
    current_message: Message | None = start_message
    seen = set()

    while current_message and current_message.mid not in seen and current_message.conversation_id == start_message.conversation_id:
        seen.add(current_message.mid)
        if all_children:
            siblings = model_serializer(
                Message.select().where((Message.parent == current_message.parent_id) &
                    (Message.author_type == current_message.author_type) &
                    (Message.conversation == start_message.conversation_id)).order_by(Message.create_time.asc(), Message.mid.asc()),
                many=True,
            )

            valid_siblings: SerializedModelList = []
            for sibling in siblings:
                if any(
                    (
                        sibling["content_type"] != Message.ContentTypes.TEXT,
                        "text" not in sibling["content"],
                        sibling["content"].get("text", "").strip(),
                        sibling["author_type"] == Message.AuthorTypes.ASSISTANT and
                        sibling["status"] in (Message.StatusTypes.FAILED, Message.StatusTypes.STOPPED),
                    )
                ):
                    sibling["create_time"] = int(sibling["create_time"])
                    sibling["update_time"] = int(sibling["update_time"])
                    valid_siblings.append(sibling)
            if valid_siblings:
                cast(list[SerializedModelList], history).insert(0, valid_siblings)
            current_message = cast(Message | None, current_message.parent)
        else:
            path_message = model_serializer(current_message)
            if not (path_message["author_type"] == Message.AuthorTypes.ASSISTANT and
                path_message["status"] == Message.StatusTypes.FAILED) and any(
                (
                    path_message["content_type"] != Message.ContentTypes.TEXT,
                    "text" not in path_message["content"],
                    path_message["content"].get("text", "").strip(),
                )
            ):
                path_message["create_time"] = int(path_message["create_time"])
                path_message["update_time"] = int(path_message["update_time"])
                history.insert(0, path_message)
            current_message = cast(Message | None, current_message.parent)

        if count is not None and len(history) >= count:
            break

    return history


def run_workflow_common(
    workflow_data: dict[str, Any],
    workflow: Workflow,
    message: Message | None = None,
    run_from=WorkflowRunRecord.RunFromTypes.WEB,
    workflow_version: str | int | None = None,
    parent_rid: str | None = None,
) -> str:
    from celery_tasks import run_workflow
    from utilities.workflow_timeline import reset_run, initialize_timeline
    
    workflow_data["wid"] = workflow.wid.hex
    reset_run(workflow_data)

    source_message = message.mid.hex if message is not None else None

    from utilities.workflow_stopping import register_child, request_stop, stop_requested
    from utilities.workflow_recovery import claim_execution
    claim_execution(workflow_data)
    with cache.transact(), WorkflowRunRecord._meta.database.atomic():
        record: WorkflowRunRecord = WorkflowRunRecord.create(
            workflow=workflow,
            data=workflow_data,
            status="RUNNING",
            run_from=run_from,
            schedule_time=datetime.now() if run_from == WorkflowRunRecord.RunFromTypes.SCHEDULE else None,
            source_message=source_message,
            workflow_version=workflow_version or workflow.version,
        )
        workflow_data["rid"] = record.rid.hex
        record.data = workflow_data
        record.save()
        if message is not None:
            message.metadata = {**message.metadata, "record_id": record.rid.hex, "recordStatus": "RUNNING"}
            message.status = Message.StatusTypes.RUNNING_WORKFLOW
            message.save()
        if parent_rid:
            register_child(parent_rid, record.rid.hex)
            if stop_requested({"rid": parent_rid}):
                request_stop(record.rid.hex)
                return record.rid.hex
    initialize_timeline(workflow_data)

    # Pre-mark status so UI can reflect queued state immediately
    try:
        cache.set(f"workflow:record:{record.rid.hex}", 202, 60 * 60)
        cache.set(f"workflow:record:finished_nodes:{record.rid.hex}", [], 60 * 60)
    except Exception:
        pass

    # Use Celery to run the workflow task
    try:
        async_res = run_workflow.delay(workflow_data)
        mprint(f"Queued workflow.run rid={record.rid.hex} task_id={getattr(async_res, 'id', 'unknown')}")
    except Exception as e:
        mprint.error(f"Failed to enqueue workflow task: {e}")
        raise

    return record.rid.hex


class JResponse(dict):
    def __init__(self, status=200, data=None, msg="", **kwargs):
        if data is None:
            data = {}
        response_data = {"status": status, "msg": msg, "data": data}
        super().__init__(response_data, **kwargs)
