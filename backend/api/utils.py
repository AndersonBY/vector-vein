# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 14:21:40
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-01 18:34:20
from pathlib import Path
from typing import TypeVar, Type, Tuple, Union, Dict, Any

from diskcache import Deque

from models import (
    Message,
    Workflow,
    model_serializer,
    WorkflowRunRecord,
)
from models.base import BaseModel
from utilities.config import config


T = TypeVar("T", bound=BaseModel)


def get_user_object_general(ObjectClass: Type[T], **kwargs) -> Tuple[int, str, Union[T, Dict[str, Any]]]:
    if len(kwargs) == 0:
        return 500, "wrong args", {}
    try:
        object = ObjectClass.get(*[getattr(ObjectClass, key) == value for key, value in kwargs.items()])
    except ObjectClass.DoesNotExist:  # type: ignore
        return 404, "not exist", {}
    return 200, "", object


def get_history_messages(
    start_message: Message,
    count: int | None = 10,
    all_children: bool = True,
) -> list[dict] | list[list[dict]]:
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
    history = []

    while start_message:
        if all_children:
            if start_message.parent is not None:
                siblings = model_serializer(
                    Message.select()
                    .where(Message.parent == start_message.parent)
                    .order_by(Message.create_time.desc()),
                    many=True,
                )
            else:
                siblings = [model_serializer(start_message)]

            valid_siblings = []
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
                history.insert(0, valid_siblings)
            start_message = start_message.parent
        else:
            if start_message.parent is not None:
                latest_child = model_serializer(
                    Message.select()
                    .where(Message.parent == start_message.parent)
                    .order_by(Message.create_time.desc())
                    .first()
                )
            else:
                latest_child = model_serializer(start_message)
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
            start_message = start_message.parent

        if count is not None and len(history) >= count:
            break

    return history


def run_workflow_common(
    workflow_data: dict,
    workflow: Workflow,
    message=None,
    run_from=WorkflowRunRecord.RunFromTypes.WEB,
    workflow_version: int | None = None,
) -> str:
    workflow_data["wid"] = workflow.wid.hex

    source_message = message.mid.hex if message else message

    record: WorkflowRunRecord = WorkflowRunRecord.create(
        workflow=workflow,
        data=workflow_data,
        status="RUNNING",
        run_from=run_from,
        source_message=source_message,
        workflow_version=workflow_version or workflow.version,
    )
    workflow_data["rid"] = record.rid.hex

    worker_queue = Deque(directory=Path(config.data_path) / "cache" / "workflow_task")
    worker_queue.appendleft(workflow_data)

    return record.rid.hex


class JResponse(dict):
    def __init__(self, status=200, data=None, msg="", **kwargs):
        if data is None:
            data = {}
        response_data = {"status": status, "msg": msg, "data": data}
        super().__init__(response_data, **kwargs)
