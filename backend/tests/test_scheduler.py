from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from models import Workflow, WorkflowRunSchedule
from utilities.workflow import scheduler as scheduler_module


class _FakeOrderField:
    def desc(self) -> "_FakeOrderField":
        return self


class _FakeQuery:
    def __init__(self, record: object | None):
        self._record = record

    def where(self, *args: object) -> "_FakeQuery":
        return self

    def order_by(self, *args: object) -> "_FakeQuery":
        return self

    def first(self) -> object | None:
        return self._record


class _FakeWorkflowRunRecordModel:
    RunFromTypes = SimpleNamespace(SCHEDULE="SCHEDULE")
    workflow = object()
    run_from = object()
    start_time = _FakeOrderField()
    record: object | None = None

    @classmethod
    def select(cls) -> _FakeQuery:
        return _FakeQuery(cls.record)


class _FakeSchedule(WorkflowRunSchedule):
    save_calls: int

    def __init__(self, cron_expression: str = "45 14 * * *", timezone_name: str = "Asia/Shanghai") -> None:
        workflow = Workflow(
            wid=uuid4(),
            title="Test workflow",
            brief="",
            data={"nodes": [], "edges": [], "meta": {"source": "desktop"}},
            version=7,
            status="VALID",
        )
        super().__init__(
            sid=uuid4(),
            cron_expression=cron_expression,
            data={"timezone": timezone_name},
            workflow=workflow,
            status="VALID",
        )
        self.save_calls = 0

    def save(self, *args: object, **kwargs: object) -> int:
        self.save_calls += 1
        return 1


def test_parse_cron_expression_supports_ranges_steps_and_aliases() -> None:
    parsed = scheduler_module.parse_cron_expression("*/15 9-17 * jan,mar mon-fri")

    assert parsed["minute"] == {0, 15, 30, 45}
    assert parsed["hour"] == set(range(9, 18))
    assert parsed["day_of_month_is_any"] is True
    assert parsed["month"] == {1, 3}
    assert parsed["day_of_week"] == {1, 2, 3, 4, 5}


def test_parse_cron_expression_normalizes_sunday_alias() -> None:
    parsed = scheduler_module.parse_cron_expression("0 0 * * 0,7")

    assert parsed["day_of_week"] == {0}


def test_parse_cron_expression_requires_five_fields() -> None:
    with pytest.raises(ValueError, match="5 fields"):
        scheduler_module.parse_cron_expression("* * * *")


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("61 * * * *", False),
        ("*/0 * * * *", False),
        ("*/5 * * * *", True),
    ],
)
def test_validate_cron_expression_rejects_invalid_values(expression: str, expected: bool) -> None:
    assert scheduler_module.validate_cron_expression(expression) is expected


def test_cron_matches_datetime_uses_or_between_day_of_month_and_day_of_week() -> None:
    current_time = datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc)
    assert current_time.weekday() == 4  # Friday

    assert scheduler_module.cron_matches_datetime("0 9 13 * 2", current_time) is True


def test_cron_matches_datetime_uses_day_of_week_when_day_of_month_is_any() -> None:
    friday = datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc)
    assert friday.weekday() == 4  # Friday => cron weekday 5

    assert scheduler_module.cron_matches_datetime("0 9 * * 5", friday) is True
    assert scheduler_module.cron_matches_datetime("0 9 * * 2", friday) is False


def test_cron_matches_datetime_uses_day_of_month_when_day_of_week_is_any() -> None:
    thirteenth = datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc)
    fourteenth = datetime(2026, 2, 14, 9, 0, tzinfo=timezone.utc)

    assert scheduler_module.cron_matches_datetime("0 9 13 * *", thirteenth) is True
    assert scheduler_module.cron_matches_datetime("0 9 13 * *", fourteenth) is False


def test_get_next_run_time_returns_next_matching_minute() -> None:
    next_run = scheduler_module.get_next_run_time(
        "41 14 * * *",
        "Asia/Shanghai",
        from_time=datetime(2026, 3, 30, 6, 40, tzinfo=timezone.utc),
    )

    assert next_run == datetime(2026, 3, 30, 14, 41, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_get_next_run_time_skips_current_minute_even_if_it_matches() -> None:
    next_run = scheduler_module.get_next_run_time(
        "40 14 * * *",
        "Asia/Shanghai",
        from_time=datetime(2026, 3, 30, 6, 40, tzinfo=timezone.utc),
    )

    assert next_run == datetime(2026, 3, 31, 14, 40, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_get_next_run_time_falls_back_to_default_timezone_for_invalid_zone() -> None:
    from_time = datetime(2026, 3, 30, 6, 40, tzinfo=timezone.utc)

    assert scheduler_module.get_next_run_time("41 14 * * *", "invalid/timezone", from_time=from_time) == (
        scheduler_module.get_next_run_time("41 14 * * *", "Asia/Shanghai", from_time=from_time)
    )


def test_try_run_schedule_triggers_workflow_and_updates_state(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = scheduler_module.WorkflowScheduler()
    schedule = _FakeSchedule()
    run_calls: list[dict[str, Any]] = []

    def fake_run_workflow_common(
        *,
        workflow_data: dict[str, Any],
        workflow: Workflow,
        run_from: str,
        workflow_version: str | int | None,
        message: object | None = None,
    ) -> str:
        run_calls.append(
            {
                "workflow_data": workflow_data,
                "workflow": workflow,
                "run_from": run_from,
                "workflow_version": workflow_version,
                "message": message,
            }
        )
        workflow_data["mutated"] = True
        return "rid-1"

    monkeypatch.setattr(scheduler_module, "WorkflowRunRecord", _FakeWorkflowRunRecordModel)
    monkeypatch.setattr(scheduler_module, "run_workflow_common", fake_run_workflow_common)
    _FakeWorkflowRunRecordModel.record = None

    current_utc = datetime(2026, 3, 30, 6, 45, tzinfo=timezone.utc)
    scheduler._try_run_schedule(schedule, current_utc)

    local_time = current_utc.astimezone(ZoneInfo("Asia/Shanghai")).replace(second=0, microsecond=0)
    assert len(run_calls) == 1
    assert run_calls[0]["run_from"] == "SCHEDULE"
    assert run_calls[0]["workflow_version"] == 7
    assert run_calls[0]["workflow"] is schedule.workflow
    assert schedule.workflow.data == {"nodes": [], "edges": [], "meta": {"source": "desktop"}}
    assert schedule.schedule_time == local_time
    assert schedule.update_time is not None
    assert schedule.save_calls == 1
    assert scheduler._last_triggered[schedule.sid.hex] == local_time.strftime("%Y-%m-%dT%H:%M%z")


def test_try_run_schedule_deduplicates_current_minute(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = scheduler_module.WorkflowScheduler()
    schedule = _FakeSchedule()
    current_utc = datetime(2026, 3, 30, 6, 45, tzinfo=timezone.utc)
    minute_key = current_utc.astimezone(ZoneInfo("Asia/Shanghai")).replace(second=0, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M%z"
    )
    scheduler._last_triggered[schedule.sid.hex] = minute_key
    run_calls: list[str] = []

    monkeypatch.setattr(scheduler_module, "WorkflowRunRecord", _FakeWorkflowRunRecordModel)
    monkeypatch.setattr(
        scheduler_module,
        "run_workflow_common",
        lambda **kwargs: run_calls.append("called") or "rid-2",
    )
    _FakeWorkflowRunRecordModel.record = None

    scheduler._try_run_schedule(schedule, current_utc)

    assert run_calls == []
    assert schedule.save_calls == 0


def test_try_run_schedule_skips_when_record_already_exists_for_same_minute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduler = scheduler_module.WorkflowScheduler()
    schedule = _FakeSchedule()
    run_calls: list[str] = []

    monkeypatch.setattr(scheduler_module, "WorkflowRunRecord", _FakeWorkflowRunRecordModel)
    monkeypatch.setattr(
        scheduler_module,
        "run_workflow_common",
        lambda **kwargs: run_calls.append("called") or "rid-3",
    )

    local_time = datetime(2026, 3, 30, 14, 45, tzinfo=ZoneInfo("Asia/Shanghai"))
    _FakeWorkflowRunRecordModel.record = SimpleNamespace(start_time=local_time)
    scheduler._try_run_schedule(schedule, datetime(2026, 3, 30, 6, 45, tzinfo=timezone.utc))

    assert run_calls == []
    assert schedule.save_calls == 0
    assert scheduler._last_triggered[schedule.sid.hex] == local_time.strftime("%Y-%m-%dT%H:%M%z")


def test_try_run_schedule_ignores_invalid_expression(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = scheduler_module.WorkflowScheduler()
    schedule = _FakeSchedule(cron_expression="invalid cron")
    run_calls: list[str] = []

    monkeypatch.setattr(scheduler_module, "WorkflowRunRecord", _FakeWorkflowRunRecordModel)
    monkeypatch.setattr(
        scheduler_module,
        "run_workflow_common",
        lambda **kwargs: run_calls.append("called") or "rid-4",
    )

    scheduler._try_run_schedule(schedule, datetime(2026, 3, 30, 6, 45, tzinfo=timezone.utc))

    assert run_calls == []
    assert schedule.save_calls == 0
