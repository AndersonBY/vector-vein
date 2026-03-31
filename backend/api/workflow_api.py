# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-01 18:31:32
from copy import deepcopy
from datetime import datetime

from peewee import fn

from models import (
    Workflow,
    WorkflowTag,
    model_serializer,
    WorkflowTemplate,
    WorkflowRunRecord,
    WorkflowRunSchedule,
)
from api.utils import (
    JResponse,
    run_workflow_common,
    get_user_object_general,
)
from utilities.config import cache
from utilities.workflow import WorkflowData, validate_cron_expression, get_next_run_time
from utilities.file_processing import static_file_server
from celery_tasks import update_workflow_tool_call_data


def copy_images(images):
    """Copy images to static folder and store in url format"""
    copied_images = []
    for image in images:
        if image.startswith("http://localhost"):
            continue
        image_url = static_file_server.get_static_file_url(image, "images")
        copied_images.append(image_url)
    return copied_images


def _serialize_workflow_summary(workflow: Workflow | None):
    if workflow is None:
        return None
    return {
        "wid": workflow.wid.hex,
        "title": workflow.title,
        "status": workflow.status,
        "version": workflow.version,
        "update_time": int(workflow.update_time.timestamp() * 1000) if workflow.update_time else None,
    }


def _latest_schedule_record(workflow: Workflow | None):
    if workflow is None:
        return None
    record = (
        WorkflowRunRecord.select()
        .where(
            WorkflowRunRecord.workflow == workflow,
            WorkflowRunRecord.run_from == WorkflowRunRecord.RunFromTypes.SCHEDULE,
        )
        .order_by(WorkflowRunRecord.start_time.desc())
        .first()
    )
    if record is None:
        return None
    return model_serializer(record)


class WorkflowAPI:
    name = "workflow"

    def get(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200 or not isinstance(workflow, Workflow):
            return JResponse(status=status, msg=msg)

        workflow = model_serializer(workflow, manytomany=True)
        return JResponse(msg="success", data=workflow)

    def create(self, payload):
        title = payload.get("title", "").encode("utf16", errors="surrogatepass").decode("utf16")
        brief = payload.get("brief", "").encode("utf16", errors="surrogatepass").decode("utf16")
        images = payload.get("images", [])
        tags = payload.get("tags", [])
        data = payload.get("data", {"nodes": [], "edges": []})
        language = payload.get("language", "zh-CN")
        tool_call_data = payload.get("tool_call_data", {})

        workflow: Workflow = Workflow.create(
            title=title,
            brief=brief,
            data=data,
            language=language,
            images=copy_images(images),
            version="1",
        )
        tool_call_data["workflow_id"] = workflow.wid.hex
        workflow.tool_call_data = tool_call_data
        workflow.save()
        for tag in tags:
            tag_qs = WorkflowTag.select().where(WorkflowTag.title == tag["title"])
            if tag_qs.exists():
                workflow.tags.add(tag_qs.first())
            else:
                tag_obj = WorkflowTag.create(
                    title=tag["title"],
                    language=tag.get("language", "zh-CN"),
                    color=tag.get("color", "#28c5e5"),
                )
                workflow.tags.add(tag_obj)
        return JResponse(data=model_serializer(workflow, manytomany=True))

    def update(self, payload):
        wid = payload.get("wid", None)
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=wid,
        )
        if status != 200 or not isinstance(workflow, Workflow):
            return JResponse(status=status, msg=msg)

        data = payload.get("data", {})
        title = payload.get("title", "").encode("utf16", errors="surrogatepass").decode("utf16")
        brief = payload.get("brief", "").encode("utf16", errors="surrogatepass").decode("utf16")
        images = payload.get("images", [])
        tags = payload.get("tags", [])
        workflow.tags.clear()
        for tag in tags:
            tag_qs = WorkflowTag.select().where(WorkflowTag.tid == tag)
            if tag_qs.exists():
                workflow.tags.add(tag_qs.first())
            else:
                tag_obj = WorkflowTag.create(title=tag)
                workflow.tags.add(tag_obj)

        title_changed = workflow.title != title

        workflow.title = title
        workflow.brief = brief

        related_workflows = WorkflowData(data).related_workflows
        if wid in related_workflows.keys():
            return JResponse(status=400, msg="workflow can not be related to itself")
        data["related_workflows"] = related_workflows

        workflow.images = copy_images(images)
        workflow.data = data
        workflow.update_time = datetime.now()
        workflow.version = int(workflow.version or 1) + 1
        workflow.save()

        update_workflow_tool_call_data.delay(workflow_wid=workflow.wid.hex, force=title_changed)

        return JResponse(data=model_serializer(workflow, manytomany=True))

    def delete(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200 or not isinstance(workflow, Workflow):
            return JResponse(status=status, msg=msg)

        workflow.status = "DELETED"
        workflow.is_fast_access = False
        workflow.update_time = datetime.now()
        workflow.save()

        (
            WorkflowRunSchedule.update(status="DELETED", update_time=datetime.now())
            .where(WorkflowRunSchedule.workflow == workflow)
            .execute()
        )
        return JResponse(data={"wid": workflow.wid.hex})

    def list(self, payload):
        tags = payload.get("tags", [])
        # Ensure tags is always a list, never None
        if tags is None:
            tags = []
        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field = payload.get("sort_field", "update_time")
        sort_order = payload.get("sort_order", "descend")
        sort_field = getattr(Workflow, sort_field, Workflow.update_time)
        search_text = payload.get("search_text", "")
        # Ensure search_text is always a string, never None
        if search_text is None:
            search_text = ""
        workflow_related = payload.get("workflow_related", "")
        only_deleted = payload.get("only_deleted", False)
        if workflow_related:
            status, msg, workflow = get_user_object_general(Workflow, wid=workflow_related)
            if status != 200 or not isinstance(workflow, Workflow):
                return JResponse(status=status, msg=msg)
            related_workflow_ids = list(WorkflowData(workflow.data).related_workflows.keys())
            workflows = Workflow.select().where(Workflow.wid.in_(related_workflow_ids))
        else:
            workflows = Workflow.select()
        if only_deleted:
            workflows = workflows.where(Workflow.status == "DELETED")
        else:
            workflows = workflows.where(Workflow.status != "DELETED")
        if tags and len(tags) > 0:
            workflows = workflows.join(Workflow.tags.get_through_model()).where(Workflow.tags.get_through_model().workflowtag_id.in_(tags)).distinct()
        if search_text and len(search_text) > 0:
            workflows = workflows.select().where((fn.Lower(Workflow.title).contains(search_text.lower())) | (fn.Lower(Workflow.brief).contains(search_text.lower())))
        workflows_count = workflows.count()
        offset = (page_num - 1) * page_size
        limit = page_size
        if sort_order == "descend":
            sort_field = sort_field.desc()
        workflows = workflows.order_by(sort_field).offset(offset).limit(limit)
        workflows_list = model_serializer(workflows, many=True, manytomany=True)
        response_data = {
            "workflows": workflows_list,
            "total": workflows_count,
            "page_size": page_size,
            "page": page_num,
            "fast_access_workflows": [],
        }
        if payload.get("need_fast_access", False):
            fast_access_workflows = Workflow.select().where(Workflow.is_fast_access, Workflow.status == "VALID").order_by(sort_field)
            response_data["fast_access_workflows"] = model_serializer(fast_access_workflows, many=True, manytomany=True)

        return JResponse(data=response_data)

    def trash_list(self, payload):
        payload = {**payload, "only_deleted": True, "need_fast_access": False}
        return self.list(payload)

    def trash_restore(self, payload):
        status, msg, workflow = get_user_object_general(Workflow, wid=payload.get("wid", None))
        if status != 200 or not isinstance(workflow, Workflow):
            return JResponse(status=status, msg=msg)
        workflow.status = "VALID"
        workflow.update_time = datetime.now()
        workflow.save()
        (
            WorkflowRunSchedule.update(status="VALID", update_time=datetime.now())
            .where(WorkflowRunSchedule.workflow == workflow)
            .execute()
        )
        return JResponse(data=model_serializer(workflow, manytomany=True))

    def trash_purge(self, payload):
        status, msg, workflow = get_user_object_general(Workflow, wid=payload.get("wid", None))
        if status != 200 or not isinstance(workflow, Workflow):
            return JResponse(status=status, msg=msg)

        workflow.tags.clear()
        workflow.delete_instance(recursive=True, delete_nullable=True)
        return JResponse()

    def run(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200 or not isinstance(workflow, Workflow):
            return JResponse(status=status, msg=msg)

        workflow_data = payload.get("data", {})

        record_rid = run_workflow_common(
            workflow_data=workflow_data,
            workflow=workflow,
            run_from=WorkflowRunRecord.RunFromTypes.WEB,
            workflow_version=payload.get("version", workflow.version),
        )

        return JResponse(data={"rid": record_rid})

    def check_status(self, payload):
        rid = payload.get("rid", None)
        if rid is None:
            return JResponse(status=400, msg="rid is None")

        record_status = cache.get(f"workflow:record:{rid}")
        finished_nodes = cache.get(f"workflow:record:finished_nodes:{rid}", [])
        if record_status == 202:
            return JResponse(status=202, data={"finished_nodes": finished_nodes})
        elif record_status == 404:
            return JResponse(status=404, msg="record not found")

        record_qs = WorkflowRunRecord.select().join(Workflow).where(WorkflowRunRecord.rid == rid)
        if not record_qs.exists():
            cache.set(f"workflow:record:{rid}", 404, 60 * 60)
            return JResponse(status=404, msg="record not found")

        record = record_qs.first()
        if record.status == "FINISHED":
            workflow_serializer_data = model_serializer(record.workflow, manytomany=True)
            workflow_serializer_data["data"] = record.data
            workflow_serializer_data["version"] = record.workflow_version
            response = {"status": 200, "msg": record.status, "data": workflow_serializer_data}
            cache.set(f"workflow:record:{rid}", 200, 60 * 60)
        elif record.status in ("RUNNING", "QUEUED"):
            response = {"status": 202, "msg": record.status, "data": {"finished_nodes": finished_nodes}}
        else:
            workflow_serializer_data = model_serializer(record.workflow, manytomany=True)
            workflow_serializer_data["data"] = record.data
            response = {"status": 500, "msg": record.status, "data": workflow_serializer_data}
            cache.set(f"workflow:record:{rid}", 500, 60 * 60)
        return JResponse(**response)

    def add_to_fast_access(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200 or not isinstance(workflow, Workflow):
            return JResponse(status=status, msg=msg)

        workflow.is_fast_access = True
        workflow.save()
        return JResponse()

    def delete_from_fast_access(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200 or not isinstance(workflow, Workflow):
            return JResponse(status=status, msg=msg)

        workflow.is_fast_access = False
        workflow.save()
        return JResponse()

    def update_tool_call_data(self, payload):
        wid = payload.get("wid", None)
        status, msg, workflow = get_user_object_general(Workflow, wid=wid)
        if status != 200 or not isinstance(workflow, Workflow):
            return JResponse(status=status, msg=msg)

        tool_call_data = payload.get("tool_call_data", {})
        workflow.tool_call_data = tool_call_data
        workflow.save()
        return JResponse()


class WorkflowTemplateAPI:
    name = "workflow_template"

    def get(self, payload):
        status, msg, workflow_template = get_user_object_general(
            WorkflowTemplate,
            tid=payload.get("tid", None),
        )
        if status != 200 or not isinstance(workflow_template, WorkflowTemplate):
            return JResponse(status=status, msg=msg)

        workflow_template = model_serializer(workflow_template, manytomany=True)
        return JResponse(data=workflow_template)

    def add(self, payload):
        status, msg, workflow_template = get_user_object_general(
            WorkflowTemplate,
            tid=payload.get("tid", None),
        )
        if status != 200 or not isinstance(workflow_template, WorkflowTemplate):
            return JResponse(status=status, msg=msg)

        workflow_template.used_count += 1
        workflow_template.save()
        workflow = Workflow.create(
            title=workflow_template.title,
            brief=workflow_template.brief,
            language=workflow_template.language,
            data=workflow_template.data,
        )
        workflow = model_serializer(workflow, manytomany=True)
        return JResponse(data=workflow)

    def list(self, payload):
        page_num = int(payload.get("page", 1))
        page_size = min(int(payload.get("page_size", 10)), 100)
        sort_field = payload.get("sort_field", "update_time")
        sort_order = payload.get("sort_order", "descend")

        sort_field_obj = getattr(WorkflowTemplate, sort_field)
        if sort_order == "descend":
            sort_field_obj = sort_field_obj.desc()

        workflow_templates = WorkflowTemplate.select()
        workflow_templates_count = workflow_templates.count()
        offset = (page_num - 1) * page_size
        limit = page_size

        workflow_templates = workflow_templates.order_by(sort_field_obj).offset(offset).limit(limit)
        workflow_templates_list = model_serializer(workflow_templates, many=True, manytomany=True)

        response_data = {
            "templates": workflow_templates_list,
            "total": workflow_templates_count,
            "page_size": page_size,
            "page": page_num,
        }
        return JResponse(data=response_data)


class WorkflowRunRecordAPI:
    name = "workflow_run_record"

    def get(self, payload):
        status, msg, record = get_user_object_general(
            WorkflowRunRecord,
            rid=payload.get("rid", None),
        )
        if status != 200 or not isinstance(record, WorkflowRunRecord):
            return JResponse(status=status, msg=msg)

        record = model_serializer(record, manytomany=True)
        return JResponse(data=record)

    def list(self, payload):
        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field = payload.get("sort_field", "start_time")
        sort_order = payload.get("sort_order", "descend")
        sort_field = getattr(WorkflowRunRecord, sort_field, WorkflowRunRecord.start_time)
        wid = payload.get("wid", "")
        status = payload.get("status", [])
        run_from = payload.get("run_from", [])
        need_workflow = payload.get("need_workflow", False)
        if sort_order == "descend":
            sort_field = sort_field.desc()
        records = WorkflowRunRecord.select().join(Workflow).order_by(sort_field)
        if len(wid) > 0:
            records = records.where(WorkflowRunRecord.workflow == wid)
        if status:
            records = records.where(WorkflowRunRecord.status.in_(status))
        if run_from:
            if isinstance(run_from, list):
                records = records.where(WorkflowRunRecord.run_from.in_(run_from))
            else:
                records = records.where(WorkflowRunRecord.run_from == run_from)
        records_count = records.count()
        offset = (page_num - 1) * page_size
        limit = page_size
        records = records.offset(offset).limit(limit)
        records_list = model_serializer(records, many=True, manytomany=True)

        if need_workflow:
            for record in records_list:
                workflow = Workflow.get_or_none(Workflow.wid == record["workflow"])
                record["workflow"] = _serialize_workflow_summary(workflow)

        return JResponse(
            data={
                "records": records_list,
                "total": records_count,
                "page_size": page_size,
                "page": page_num,
            }
        )

    def delete(self, payload):
        status, msg, record = get_user_object_general(
            WorkflowRunRecord,
            rid=payload.get("rid", None),
        )
        if status != 200 or not isinstance(record, WorkflowRunRecord):
            return JResponse(status=status, msg=msg)

        record.delete_instance()
        return JResponse()

    def rerun(self, payload):
        status, msg, record = get_user_object_general(
            WorkflowRunRecord,
            rid=payload.get("rid", None),
        )
        if status != 200 or not isinstance(record, WorkflowRunRecord):
            return JResponse(status=status, msg=msg)
        workflow = record.workflow
        if workflow is None or workflow.status == "DELETED":
            return JResponse(status=404, msg="workflow not found")

        record_rid = run_workflow_common(
            workflow_data=deepcopy(record.data),
            workflow=workflow,
            run_from=payload.get("run_from", WorkflowRunRecord.RunFromTypes.WEB),
            workflow_version=payload.get("version", record.workflow_version),
        )
        return JResponse(data={"rid": record_rid})


class WorkflowTagAPI:
    name = "workflow_tag"

    def get(self, payload):
        status, msg, workflow_tag = get_user_object_general(
            WorkflowTag,
            tid=payload.get("tid", None),
        )
        if status != 200 or not isinstance(workflow_tag, WorkflowTag):
            return JResponse(status=status, msg=msg)

        workflow_tag = model_serializer(workflow_tag)
        return JResponse(data=workflow_tag)

    def list(self, payload):
        public_only = payload.get("public_only", False)
        user_only = payload.get("user_only", False)
        public_tags = WorkflowTag.select().where(WorkflowTag.is_public)

        if public_only:
            all_tags = public_tags
        else:
            personal_tags = WorkflowTag.select().where(WorkflowTag.user == payload.get("user"))
            if user_only:
                all_tags = personal_tags
            else:
                all_tags = public_tags.union(personal_tags).order_by(WorkflowTag.title)

        return JResponse(data=model_serializer(all_tags, many=True))

    def create(self, payload):
        title = payload.get("title", "")
        user = payload.get("user")
        tag, created = WorkflowTag.get_or_create(title=title, user=user)
        return JResponse(data={"tid": tag.tid.hex})

    def delete(self, payload):
        status, msg, tag = get_user_object_general(
            WorkflowTag,
            tid=payload.get("tid"),
        )
        if status != 200 or not isinstance(tag, WorkflowTag):
            return JResponse(status=status, msg=msg)
        tag.delete_instance()
        return JResponse()

    def update(self, payload):
        tags = payload.get("data", [])
        for tag_data in tags:
            tid = tag_data.get("tid")
            tag_qs = WorkflowTag.select().where(WorkflowTag.tid == tid, WorkflowTag.user == payload.get("user"))
            if not tag_qs.exists():
                continue
            tag = tag_qs.first()
            if not isinstance(tag, WorkflowTag):
                continue
            tag.title = tag_data.get("title", tag.title)
            tag.color = tag_data.get("color", tag.color)
            tag.save()
        return JResponse()

    def search(self, payload):
        title = payload.get("title", "")
        user = payload.get("user")
        public_tags = WorkflowTag.select().where(WorkflowTag.is_public, WorkflowTag.title.contains(title))
        personal_tags = WorkflowTag.select().where(WorkflowTag.user == user, WorkflowTag.title.contains(title))
        all_tags = public_tags.union(personal_tags)
        return JResponse(data=model_serializer(all_tags, many=True))


class WorkflowRunScheduleAPI:
    name = "workflow_schedule_trigger"

    def get(self, payload):
        sid = payload.get("sid")
        if sid:
            status, msg, run_schedule = get_user_object_general(WorkflowRunSchedule, sid=sid)
        else:
            status, msg, workflow = get_user_object_general(Workflow, wid=payload.get("wid"))
            if status != 200 or not isinstance(workflow, Workflow):
                return JResponse(status=status, msg=msg)
            run_schedule = (
                WorkflowRunSchedule.select()
                .where(WorkflowRunSchedule.workflow == workflow, WorkflowRunSchedule.status != "DELETED")
                .first()
            )
            if run_schedule is None:
                return JResponse(status=404, msg="run schedule not found")
            status, msg = 200, ""
        if status != 200 or not isinstance(run_schedule, WorkflowRunSchedule):
            return JResponse(status=status, msg=msg)

        data = model_serializer(run_schedule)
        data["workflow"] = _serialize_workflow_summary(run_schedule.workflow)
        data["latest_record"] = _latest_schedule_record(run_schedule.workflow)
        data["next_run_at"] = None
        if run_schedule.cron_expression:
            next_run_at = get_next_run_time(
                run_schedule.cron_expression,
                run_schedule.data.get("timezone", "Asia/Shanghai") if isinstance(run_schedule.data, dict) else "Asia/Shanghai",
            )
            if next_run_at is not None:
                data["next_run_at"] = int(next_run_at.timestamp() * 1000)
        return JResponse(data=data)

    def list(self, payload):
        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field_name = payload.get("sort_field", "update_time")
        sort_field = getattr(WorkflowRunSchedule, sort_field_name, WorkflowRunSchedule.update_time)
        sort_order = payload.get("sort_order", "descend")
        wid = payload.get("wid", "")

        schedules = (
            WorkflowRunSchedule.select(WorkflowRunSchedule, Workflow)
            .join(Workflow)
            .where(WorkflowRunSchedule.status != "DELETED", Workflow.status != "DELETED")
        )
        if wid:
            schedules = schedules.where(WorkflowRunSchedule.workflow == wid)
        if sort_order == "descend":
            sort_field = sort_field.desc()

        total = schedules.count()
        schedules = schedules.order_by(sort_field).offset((page_num - 1) * page_size).limit(page_size)

        schedule_list = []
        for schedule in schedules:
            item = model_serializer(schedule)
            item["workflow"] = _serialize_workflow_summary(schedule.workflow)
            item["latest_record"] = _latest_schedule_record(schedule.workflow)
            item["next_run_at"] = None
            if schedule.cron_expression:
                next_run_at = get_next_run_time(
                    schedule.cron_expression,
                    schedule.data.get("timezone", "Asia/Shanghai") if isinstance(schedule.data, dict) else "Asia/Shanghai",
                )
                if next_run_at is not None:
                    item["next_run_at"] = int(next_run_at.timestamp() * 1000)
            schedule_list.append(item)

        return JResponse(
            data={
                "schedules": schedule_list,
                "total": total,
                "page_size": page_size,
                "page": page_num,
            }
        )

    def update(self, payload):
        sid = payload.get("sid")
        wid = payload.get("wid")
        cron_expression = (payload.get("cron_expression") or payload.get("schedule") or "").strip()
        if not validate_cron_expression(cron_expression):
            return JResponse(status=400, msg="invalid cron expression")

        if sid:
            status, msg, run_schedule = get_user_object_general(WorkflowRunSchedule, sid=sid)
            if status != 200 or not isinstance(run_schedule, WorkflowRunSchedule):
                return JResponse(status=status, msg=msg)
            workflow = run_schedule.workflow
            if workflow is None:
                return JResponse(status=404, msg="workflow not found")
        else:
            status, msg, workflow = get_user_object_general(Workflow, wid=wid)
            if status != 200 or not isinstance(workflow, Workflow):
                return JResponse(status=status, msg=msg)
            run_schedule = (
                WorkflowRunSchedule.select()
                .where(WorkflowRunSchedule.workflow == workflow)
                .order_by(WorkflowRunSchedule.create_time.desc())
                .first()
            )
            if run_schedule is None:
                run_schedule = WorkflowRunSchedule.create(workflow=workflow)

        schedule_data = run_schedule.data if isinstance(run_schedule.data, dict) else {}
        schedule_data.update(
            {
                "timezone": payload.get("timezone", schedule_data.get("timezone", "Asia/Shanghai")),
                "source": "desktop",
            }
        )

        if payload.get("data"):
            schedule_data["workflow_data"] = payload.get("data")

        run_schedule.workflow = workflow
        run_schedule.status = "VALID"
        run_schedule.cron_expression = cron_expression
        run_schedule.data = schedule_data
        run_schedule.update_time = datetime.now()
        run_schedule.save()

        return JResponse(
            data={
                "sid": run_schedule.sid.hex,
                "workflow": _serialize_workflow_summary(workflow),
                "cron_expression": cron_expression,
            }
        )

    def delete(self, payload):
        sid = payload.get("sid")
        if sid:
            status, msg, run_schedule = get_user_object_general(WorkflowRunSchedule, sid=sid)
        else:
            status, msg, workflow = get_user_object_general(Workflow, wid=payload.get("wid", None))
            if status != 200 or not isinstance(workflow, Workflow):
                return JResponse(status=status, msg=msg)
            run_schedule = (
                WorkflowRunSchedule.select()
                .where(WorkflowRunSchedule.workflow == workflow, WorkflowRunSchedule.status != "DELETED")
                .first()
            )
            if run_schedule is None:
                return JResponse(status=404, msg="run schedule not found")
            status, msg = 200, ""
        if status != 200 or not isinstance(run_schedule, WorkflowRunSchedule):
            return JResponse(status=status, msg=msg)

        run_schedule.status = "DELETED"
        run_schedule.update_time = datetime.now()
        run_schedule.save()
        return JResponse()
        return JResponse()
