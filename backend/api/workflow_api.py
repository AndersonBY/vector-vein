# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-01 18:31:32
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
from utilities.workflow import WorkflowData
from utilities.file_processing import static_file_server
from background_task.tasks import update_workflow_tool_call_data


def copy_images(images):
    """Copy images to static folder and store in url format"""
    copied_images = []
    for image in images:
        if image.startswith("http://localhost"):
            continue
        image_url = static_file_server.get_static_file_url(image, "images")
        copied_images.append(image_url)
    return copied_images


class WorkflowAPI:
    name = "workflow"

    def get(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
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
        workflow = model_serializer(workflow, manytomany=True)
        return JResponse(data=workflow)

    def update(self, payload):
        wid = payload.get("wid", None)
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=wid,
        )
        if status != 200:
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
        workflow.save()

        update_workflow_tool_call_data.delay(workflow_wid=workflow.wid.hex, force=title_changed)

        return JResponse(data=model_serializer(workflow, manytomany=True))

    def delete(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            return JResponse(status=status, msg=msg)
        workflow.delete_instance()
        return JResponse()

    def list(self, payload):
        tags = payload.get("tags", [])
        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field = payload.get("sort_field", "update_time")
        sort_order = payload.get("sort_order", "descend")
        sort_field = getattr(Workflow, sort_field)
        search_text = payload.get("search_text", "")
        workflow_related = payload.get("workflow_related", "")
        if workflow_related:
            status, msg, workflow = get_user_object_general(Workflow, wid=workflow_related)
            if status != 200:
                return JResponse(status=status, msg=msg)
            related_workflow_ids = list(WorkflowData(workflow.data).related_workflows.keys())
            workflows = Workflow.select().where(Workflow.wid.in_(related_workflow_ids))
        else:
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
        if sort_order == "descend":
            sort_field = sort_field.desc()
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

        return JResponse(data=response_data)

    def run(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            JResponse(status=status, msg=msg)

        workflow_data = payload.get("data", {})

        record_rid = run_workflow_common(
            workflow_data=workflow_data,
            workflow=workflow,
            run_from=WorkflowRunRecord.RunFromTypes.WEB,
        )

        return JResponse(data={"rid": record_rid})

    def check_status(self, payload):
        rid = payload.get("rid", None)
        if rid is None:
            return JResponse(status=400, msg="rid is None")

        record_qs = WorkflowRunRecord.select().join(Workflow).where(WorkflowRunRecord.rid == rid)
        if not record_qs.exists():
            response = {"status": 404, "msg": "record not found", "data": {}}
            return JResponse(status=404, msg="record not found")

        record = record_qs.first()
        if record.status == "FINISHED":
            workflow_serializer_data = model_serializer(record.workflow, manytomany=True)
            workflow_serializer_data["data"] = record.data
            response = {"status": 200, "msg": record.status, "data": workflow_serializer_data}
        elif record.status in ("RUNNING", "QUEUED"):
            response = {"status": 202, "msg": record.status, "data": {}}
        else:
            workflow_serializer_data = model_serializer(record.workflow, manytomany=True)
            workflow_serializer_data["data"] = record.data
            response = {"status": 500, "msg": record.status, "data": workflow_serializer_data}
        return JResponse(**response)

    def add_to_fast_access(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            JResponse(status=status, msg=msg)

        workflow.is_fast_access = True
        workflow.save()
        return JResponse()

    def delete_from_fast_access(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            JResponse(status=status, msg=msg)

        workflow.is_fast_access = False
        workflow.save()
        return JResponse()

    def update_tool_call_data(self, payload):
        wid = payload.get("wid", None)
        status, msg, workflow = get_user_object_general(Workflow, wid=wid)
        if status != 200:
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
        if status != 200:
            JResponse(status=status, msg=msg)
        workflow_template = model_serializer(workflow_template, manytomany=True)
        return JResponse(data=workflow_template)

    def add(self, payload):
        status, msg, workflow_template = get_user_object_general(
            WorkflowTemplate,
            tid=payload.get("tid", None),
        )
        if status != 200:
            JResponse(status=status, msg=msg)
        workflow_template.used_count += 1
        workflow_template.save()
        workflow = Workflow.objects.create(
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
        status, msg, workflow = get_user_object_general(
            WorkflowRunRecord,
            rid=payload.get("rid", None),
        )
        if status != 200:
            JResponse(status=status, msg=msg)
        workflow = model_serializer(workflow, manytomany=True)
        return JResponse(data=workflow)

    def list(self, payload):
        page_num = payload.get("page", 1)
        page_size = min(payload.get("page_size", 10), 100)
        sort_field = payload.get("sort_field", "start_time")
        sort_order = payload.get("sort_order", "descend")
        sort_field = getattr(WorkflowRunRecord, sort_field)
        wid = payload.get("wid", "")
        status = payload.get("status", [])
        need_workflow = payload.get("need_workflow", False)
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

        if need_workflow:
            for record in records_list:
                workflow = Workflow.get(Workflow.wid == record["workflow"])
                record["workflow"] = {
                    "title": workflow.title,
                    "wid": workflow.wid.hex,
                }

        return JResponse(
            data={
                "records": records_list,
                "total": records_count,
                "page_size": page_size,
                "page": page_num,
            }
        )


class WorkflowTagAPI:
    name = "workflow_tag"

    def get(self, payload):
        status, msg, workflow_tag = get_user_object_general(
            WorkflowTag,
            tid=payload.get("tid", None),
        )
        if status != 200:
            JResponse(status=status, msg=msg)
        workflow_tag = model_serializer(workflow_tag)
        return JResponse(data=workflow_tag)

    def list(self, payload):
        return JResponse(data=model_serializer(WorkflowTag.select(), many=True))


# TODO: Implement this
class WorkflowRunScheduleAPI:
    name = "workflow_schedule_trigger"

    def update(self, payload):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=payload.get("wid", None),
        )
        if status != 200:
            JResponse(status=status, msg=msg)
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
        return JResponse()

    def delete(request):
        status, msg, workflow = get_user_object_general(
            Workflow,
            wid=request.data.get("wid", None),
        )
        if status != 200:
            JResponse(status=status, msg=msg)

        run_schedule_qs = WorkflowRunSchedule.select().join(Workflow).where(Workflow.id == workflow.id)
        if not run_schedule_qs.exists():
            response = {"status": 404, "msg": "run schedule not found", "data": {}}
            return response

        run_schedule = run_schedule_qs.first()
        # TODO: Remove from scheduler
        run_schedule.delete()
        return JResponse()
