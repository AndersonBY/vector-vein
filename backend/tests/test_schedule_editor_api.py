from datetime import datetime

import pytest
from peewee import SqliteDatabase

from api import workflow_api
from models import Workflow, WorkflowRunSchedule


@pytest.fixture
def schedule_api(monkeypatch):
    db = SqliteDatabase(":memory:")
    with db.bind_ctx([Workflow, WorkflowRunSchedule]):
        db.create_tables([Workflow, WorkflowRunSchedule])
        workflow = Workflow.create(title="Visual schedule fixture", data={"nodes": [], "edges": []})

        def get_object(model, **keys):
            value = keys.get("sid") or keys.get("wid")
            item = model.get_or_none(model._meta.primary_key == value)
            return (200, "", item) if item else (404, "missing", None)

        monkeypatch.setattr(workflow_api, "get_user_object_general", get_object)
        monkeypatch.setattr(workflow_api, "_latest_schedule_record", lambda _workflow: None)
        yield workflow_api.WorkflowRunScheduleAPI(), workflow
    db.close()


def test_visual_recurrence_round_trip_preserves_timezone_and_can_be_cleared(schedule_api, monkeypatch):
    api, workflow = schedule_api
    rule = {"unit": "week", "interval": 2, "anchor_date": "2026-11-06"}
    created = api.update({"wid": workflow.wid.hex, "cron_expression": "30 9 * * 1,5", "timezone": "America/New_York", "recurrence": rule})
    assert created["status"] == 200
    sid = created["data"]["sid"]
    schedule = WorkflowRunSchedule.get_by_id(sid)
    assert schedule.data["timezone"] == "America/New_York"
    assert schedule.data["recurrence"] == rule
    previews = []

    def next_run(cron, zone, *, recurrence=None):
        previews.append((cron, zone, recurrence))
        return datetime.fromisoformat("2026-11-16T09:30:00-05:00")

    monkeypatch.setattr(workflow_api, "get_next_run_time", next_run)
    detail = api.get({"sid": sid})
    listing = api.list({})
    assert detail["data"]["data"]["recurrence"] == rule
    assert listing["data"]["schedules"][0]["data"]["timezone"] == "America/New_York"
    assert previews == [("30 9 * * 1,5", "America/New_York", rule)] * 2
    assert api.update({"sid": sid, "cron_expression": "0 10 * * *", "recurrence": None})["status"] == 200
    schedule = WorkflowRunSchedule.get_by_id(sid)
    assert schedule.data["timezone"] == "America/New_York"
    assert schedule.data["recurrence"] is None


@pytest.mark.parametrize("patch", [{"timezone": "invalid/zone"}, {"timezone": 123}, {"cron_expression": True},
    {"recurrence": {"unit": "week", "interval": 0, "anchor_date": "2026-11-06"}}])
def test_invalid_visual_schedule_does_not_create_or_change_a_record(schedule_api, patch):
    api, workflow = schedule_api
    payload = {"wid": workflow.wid.hex, "cron_expression": "0 9 * * *", **patch}
    assert api.update(payload)["status"] == 400
    assert WorkflowRunSchedule.select().count() == 0
    saved = api.update({"wid": workflow.wid.hex, "cron_expression": "0 9 * * *", "timezone": "Asia/Shanghai"})
    sid = saved["data"]["sid"]
    assert api.update({**payload, "sid": sid})["status"] == 400
    record = WorkflowRunSchedule.get_by_id(sid)
    assert record.cron_expression == "0 9 * * *"
    assert record.data["timezone"] == "Asia/Shanghai"


def test_legacy_expression_edits_do_not_keep_an_unrelated_interval(schedule_api):
    api, workflow = schedule_api
    rule = {"unit": "week", "interval": 2, "anchor_date": "2026-11-06"}
    result = api.update({"wid": workflow.wid.hex, "cron_expression": "0 9 * * 1", "recurrence": rule})
    sid = result["data"]["sid"]
    assert api.update({"sid": sid, "cron_expression": "0 9 * * 1"})["status"] == 200
    assert WorkflowRunSchedule.get_by_id(sid).data["recurrence"] == rule
    assert api.update({"sid": sid, "cron_expression": "0 9 * * *"})["status"] == 200
    assert WorkflowRunSchedule.get_by_id(sid).data["recurrence"] is None
