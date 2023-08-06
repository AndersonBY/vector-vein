# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-08-07 00:53:15
import uuid
from pathlib import Path
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
from api.utils import get_user_object_general
from utilities.files import copy_file
from utilities.static_file_server import StaticFileServer


class WorkflowAPI:
    name = "workflow"

    def get(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        workflow = model_serializer(workflow, manytomany=True)
        response = {"status": 200, "msg": "success", "data": workflow}
        return response

    def create(self, payload):
        title = payload.get("title", "").encode("utf16", errors="surrogatepass").decode("utf16")
        brief = payload.get("brief", "").encode("utf16", errors="surrogatepass").decode("utf16")
        images = payload.get("images", [])
        tags = payload.get("tags", [])
        data = payload.get("data", {"nodes": [], "edges": []})
        language = payload.get("language", "zh-CN")

        workflow: Workflow = Workflow.create(
            title=title,
            brief=brief,
            data=data,
            language=language,
            images=images,
        )
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
        workflow = model_serializer(workflow, manytomany=True)
        response = {"status": 200, "msg": "success", "data": workflow}
        return response

    def update(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        data = payload.get("data", None)
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
        workflow.title = title
        workflow.brief = brief

        # Copy images to static folder and store in url format
        copied_images = []
        for image in images:
            if image.startswith("http://localhost"):
                continue
            image_ext = Path(image).resolve().suffix
            image_name = uuid.uuid4().hex + image_ext
            copied_image_path = Path(self.data_path) / "static" / "images" / image_name
            copy_file(image, copied_image_path)
            image_url = StaticFileServer.get_file_url(f"images/{image_name}")
            copied_images.append(image_url)
        workflow.images = copied_images
        workflow.data = data
        workflow.update_time = datetime.now()
        workflow.save()
        response = {"status": 200, "msg": "success", "data": model_serializer(workflow, manytomany=True)}
        return response

    def delete(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        workflow.delete_instance()
        response = {"status": 200, "msg": "success", "data": {}}
        return response

    def list(self, payload):
        tags = payload.get("tags", [])
        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field = payload.get("sort_field", "update_time")
        sort_order = payload.get("sort_order", "descend")
        sort_field = getattr(Workflow, sort_field)
        search_text = payload.get("search_text", "")
        if sort_order == "descend":
            sort_field = sort_field.desc()
        workflows = Workflow.select()
        if tags is not None and len(tags) > 0:
            workflows = (
                workflows.join(Workflow.tags.get_through_model())
                .where(Workflow.tags.get_through_model().workflowtag_id.in_(tags))
                .distinct()
            )
        if len(search_text) > 0:
            workflows = workflows.select().where(
                (fn.Lower(Workflow.title).contains(search_text.lower()))
                | (fn.Lower(Workflow.brief).contains(search_text.lower()))
            )
        workflows_count = workflows.count()
        offset = (page_num - 1) * page_size
        limit = page_size
        workflows = workflows.order_by(sort_field).offset(offset).limit(limit)
        workflows_list = model_serializer(workflows, many=True, manytomany=True)
        response_data = {
            "workflows": workflows_list,
            "total": workflows_count,
            "page_size": page_size,
            "page": page_num,
        }
        if payload.get("need_fast_access", False):
            fast_access_workflows = Workflow.select().where(Workflow.is_fast_access).order_by(sort_field)
            response_data["fast_access_workflows"] = model_serializer(
                fast_access_workflows, many=True, manytomany=True
            )
        response = {
            "status": 200,
            "msg": "success",
            "data": response_data,
        }
        return response

    def run(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response

        workflow_data = payload.get("data", {})
        workflow_data["wid"] = workflow.wid.hex

        record = WorkflowRunRecord.create(
            workflow=workflow,
            data=workflow_data,
            status="RUNNING",
        )
        workflow_data["rid"] = record.rid.hex
        self.worker_queue.put({"data": workflow_data})
        response = {"status": 200, "msg": "success", "data": {"rid": record.rid.hex}}
        return response

    def check_status(self, payload):
        rid = payload.get("rid", None)
        if rid is None:
            response = {"status": 400, "msg": "rid is None", "data": {}}
            return response

        record_qs = WorkflowRunRecord.select().join(Workflow).where(WorkflowRunRecord.rid == rid)
        if not record_qs.exists():
            response = {"status": 404, "msg": "record not found", "data": {}}
            return response

        record = record_qs.first()
        if record.status == "FINISHED":
            workflow_serializer_data = model_serializer(record.workflow, manytomany=True)
            workflow_serializer_data["data"] = record.data
            response = {"status": 200, "msg": record.status, "data": workflow_serializer_data}
        elif record.status in ("RUNNING", "QUEUED"):
            response = {"status": 202, "msg": record.status, "data": {}}
        else:
            response = {"status": 500, "msg": record.status, "data": {}}
        return response

    def add_to_fast_access(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response

        workflow.is_fast_access = True
        workflow.save()
        response = {"status": 200, "msg": "success", "data": {}}
        return response

    def delete_from_fast_access(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response

        workflow.is_fast_access = False
        workflow.save()
        response = {"status": 200, "msg": "success", "data": {}}
        return response


class WorkflowTemplateAPI:
    name = "workflow_template"

    def get(self, payload):
        status, msg, workflow_template = get_user_object_general(
            WorkflowTemplate,
            tid=payload.get("tid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        workflow_template = model_serializer(workflow_template, manytomany=True)
        response = {"status": 200, "msg": "success", "data": workflow_template}
        return response

    def add(self, payload):
        status, msg, workflow_template = get_user_object_general(
            WorkflowTemplate,
            tid=payload.get("tid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        workflow_template.used_count += 1
        workflow_template.save()
        workflow = Workflow.objects.create(
            title=workflow_template.title,
            brief=workflow_template.brief,
            language=workflow_template.language,
            data=workflow_template.data,
        )
        workflow = model_serializer(workflow, manytomany=True)
        response = {"status": 200, "msg": "success", "data": workflow}
        return response

    def list(self, payload):
        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field = payload.get("sort_field", "update_time")
        sort_order = payload.get("sort_order", "descend")
        sort_field = "-" + sort_field if sort_order == "descend" else sort_field
        workflow_templates = WorkflowTemplate.select()
        workflow_templates_count = workflow_templates.count()
        offset = (page_num - 1) * page_size
        limit = page_size
        workflow_templates = workflow_templates.order_by(sort_field).offset(offset).limit(limit)
        workflow_templates_list = model_serializer(workflow_templates, many=True, manytomany=True)
        response_data = {
            "templates": workflow_templates_list,
            "total": workflow_templates_count,
            "page_size": page_size,
            "page": page_num,
        }
        response = {"status": 200, "msg": "success", "data": response_data}
        return response


class WorkflowRunRecordAPI:
    name = "workflow_run_record"

    def get(self, payload):
        status, msg, workflow = get_user_object_general(
            WorkflowRunRecord,
            rid=payload.get("rid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        workflow = model_serializer(workflow, manytomany=True)
        response = {"status": 200, "msg": "success", "data": workflow}
        return response

    def list(self, payload):
        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field = payload.get("sort_field", "start_time")
        sort_order = payload.get("sort_order", "descend")
        sort_field = getattr(WorkflowRunRecord, sort_field)
        wid = payload.get("wid", "")
        status = payload.get("status", [])
        if sort_order == "descend":
            sort_field = sort_field.desc()
        records = WorkflowRunRecord.select().join(Workflow).order_by(sort_field)
        if len(wid) > 0:
            records = records.where(WorkflowRunRecord.workflow == wid)
        if status:
            records = records.filter(status__in=status)
        records_count = records.count()
        offset = (page_num - 1) * page_size
        limit = page_size
        records = records.offset(offset).limit(limit)
        records_list = model_serializer(records, many=True, manytomany=True)
        response = {
            "status": 200,
            "msg": "success",
            "data": {
                "records": records_list,
                "total": records_count,
                "page_size": page_size,
                "page": page_num,
            },
        }
        return response


class WorkflowTagAPI:
    name = "workflow_tag"

    def get(self, payload):
        status, msg, workflow_tag = get_user_object_general(
            WorkflowTag,
            tid=payload.get("tid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        workflow_tag = model_serializer(workflow_tag)
        response = {"status": 200, "msg": "success", "data": workflow_tag}
        return response

    def list(self, payload):
        response = {"status": 200, "msg": "success", "data": model_serializer(WorkflowTag.select(), many=True)}
        return response


# TODO: Implement this
class WorkflowRunScheduleAPI:
    name = "workflow_schedule_trigger"

    def update(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response
        workflow_data = payload.get("data", {})
        workflow.data = workflow_data
        workflow.save()
        workflow_data["wid"] = workflow.wid.hex
        cron_expression = ""

        run_schedule_qs = WorkflowRunSchedule.select().join(Workflow).where(Workflow.id == workflow.id)
        if run_schedule_qs.exists():
            run_schedule = run_schedule_qs.first()
            run_schedule.cron_expression = cron_expression
            run_schedule.data = workflow_data
            run_schedule.save()
        else:
            run_schedule = WorkflowRunSchedule.create(
                workflow=workflow,
                cron_expression=cron_expression,
                data=workflow_data,
            )
        # minute, hour, day_of_month, month_of_year, day_of_week = cron_expression.split(" ")
        # timezone = pytz.timezone(payload.get("timezone", "Asia/Shanghai"))
        # TODO: Add to scheduler
        response = {"status": 200, "msg": "success", "data": {}}
        return response

    def delete(request):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=request.data.get("wid", None),
        )
        if status != 200:
            response = {"status": status, "msg": msg, "data": {}}
            return response

        run_schedule_qs = WorkflowRunSchedule.select().join(Workflow).where(Workflow.id == workflow.id)
        if not run_schedule_qs.exists():
            response = {"status": 404, "msg": "run schedule not found", "data": {}}
            return response

        run_schedule = run_schedule_qs.first()
        # TODO: Remove from scheduler
        run_schedule.delete()
        response = {"status": 200, "msg": "success", "data": {}}
        return response
