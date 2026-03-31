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

        当不获取全部子节点消息时，将只获取最新的(create_time)子节点消息。
        同时返回结果是list[dict]，每个dict是一个消息的信息。

        当获取全部子节点消息时，返回结果是list[list[dict]]，每个list[dict]是一个父节点消息的全部子节点消息。

    Returns:
        list[dict] | list[list[dict]]: _description_
    """
    history: SerializedModelList | list[SerializedModelList]
    history = []
    current_message: Message | None = start_message

    while current_message:
        if all_children:
            if current_message.parent is not None:
                siblings = model_serializer(
                    Message.select().where(Message.parent == current_message.parent).order_by(Message.create_time.asc()),
                    many=True,
                )
            else:
                siblings = [model_serializer(current_message)]

            valid_siblings: SerializedModelList = []
            for sibling in siblings:
                if any(
                    (
                        sibling["content_type"] != Message.ContentTypes.TEXT,
                        "text" not in sibling["content"],
                        sibling["content"].get("text", "").strip(),
                    )
                ):
                    sibling["create_time"] = int(sibling["create_time"])
                    sibling["update_time"] = int(sibling["update_time"])
                    valid_siblings.append(sibling)
            if valid_siblings:
                cast(list[SerializedModelList], history).insert(0, valid_siblings)
            current_message = cast(Message | None, current_message.parent)
        else:
            if current_message.parent is not None:
                latest_child = model_serializer(
                    Message.select()
                    .where(Message.parent == current_message.parent)
                    .order_by(Message.create_time.desc())
                    .first()
                )
            else:
                latest_child = model_serializer(current_message)
            if any(
                (
                    latest_child["content_type"] != Message.ContentTypes.TEXT,
                    "text" not in latest_child["content"],
                    latest_child["content"].get("text", "").strip(),
                )
            ):
                latest_child["create_time"] = int(latest_child["create_time"])
                latest_child["update_time"] = int(latest_child["update_time"])
                history.insert(0, latest_child)
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
) -> str:
    from celery_tasks import run_workflow
    
    workflow_data["wid"] = workflow.wid.hex

    source_message = message.mid.hex if message is not None else None

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
