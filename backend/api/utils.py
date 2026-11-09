# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 14:21:40
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-01 18:34:20
from datetime import datetime
from typing import Any, Type, TypeVar

from models import (
    Workflow,
    WorkflowRunRecord,
)
from models.base import BaseModel
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


def run_workflow_common(
    workflow_data: dict[str, Any],
    workflow: Workflow,
    run_from=WorkflowRunRecord.RunFromTypes.WEB,
    workflow_version: str | int | None = None,
    parent_rid: str | None = None,
    record_id: str | None = None,
    submission_key: str | None = None,
) -> str:
    from celery_tasks import run_workflow
    from utilities.workflow_timeline import reset_run, initialize_timeline
    
    if (record_id is None) != (submission_key is None):
        raise ValueError("record_id and submission_key must be supplied together")
    if record_id is not None:
        from uuid import UUID
        record_id = UUID(record_id).hex
        if not isinstance(submission_key, str) or not submission_key:
            raise ValueError("Invalid workflow submission identity")
    workflow_data["wid"] = workflow.wid.hex
    reset_run(workflow_data)

    from utilities.workflow_stopping import register_child, request_stop, stop_requested
    from utilities.workflow_recovery import claim_execution
    claim_execution(workflow_data)
    with cache.transact(), WorkflowRunRecord._meta.database.atomic():
        if record_id is not None:
            existing = WorkflowRunRecord.get_or_none(WorkflowRunRecord.rid == record_id)
            if existing is not None:
                if existing.workflow_id != workflow.wid or existing.data.get("_task_agent_submission") != submission_key:
                    raise ValueError("Workflow submission identity conflict")
                # A committed record may already have been published, even if its response was lost.
                return existing.rid.hex
            workflow_data["_task_agent_submission"] = submission_key
        record: WorkflowRunRecord = WorkflowRunRecord.create(
            **({"rid": UUID(record_id)} if record_id else {}),
            workflow=workflow,
            data=workflow_data,
            status="RUNNING",
            run_from=run_from,
            schedule_time=datetime.now() if run_from == WorkflowRunRecord.RunFromTypes.SCHEDULE else None,
            workflow_version=workflow_version or workflow.version,
        )
        workflow_data["rid"] = record.rid.hex
        record.data = workflow_data
        record.save()
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
