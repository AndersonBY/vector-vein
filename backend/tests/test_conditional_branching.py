from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import worker.tasks as worker_tasks_module
from utilities.workflow import Workflow
import utilities.workflow.workflow as workflow_module


MODULE_PATH = Path(__file__).resolve().parents[1] / "worker" / "tasks" / "condition_logic.py"
SPEC = importlib.util.spec_from_file_location("condition_logic", MODULE_PATH)
condition_logic = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(condition_logic)

resolve_conditional_branch = condition_logic.resolve_conditional_branch


def make_field(value="", *, field_type="input", is_output=False):
    field = {
        "required": True,
        "placeholder": "",
        "show": False,
        "value": value,
        "name": "",
        "display_name": "",
        "type": "str",
        "list": False,
        "field_type": field_type,
    }
    if is_output:
        field["is_output"] = True
        field["field_type"] = ""
    return field


class FakeWorkflow:
    def __init__(self, template):
        self.template = template

    def get_node_field_value(self, node_id, field, default=None):
        return self.template.get(field, {}).get("value", default)

    def is_node_field_output(self, node_id, field):
        return self.template.get(field, {}).get("is_output", False)


def make_node(node_id: str) -> dict:
    return {
        "id": node_id,
        "type": "Text",
        "category": "textProcessing",
        "data": {
            "task_name": "text_processing.concat",
            "template": {},
        },
    }


def test_legacy_desktop_conditional_keeps_single_output_value() -> None:
    workflow = FakeWorkflow(
        {
            "field_type": make_field("string", field_type="select"),
            "left_field": make_field("ready"),
            "operator": make_field("equal", field_type="select"),
            "right_field": make_field("ready"),
            "true_output": make_field("go"),
            "false_output": make_field("stop"),
            "output": make_field(is_output=True),
        }
    )

    handle, value, active_handles = resolve_conditional_branch(workflow, "conditional-node")

    assert handle == ""
    assert value == "go"
    assert active_handles == []


def test_multibranch_conditional_uses_first_matching_case() -> None:
    workflow = FakeWorkflow(
        {
            "field_type": make_field("string", field_type="select"),
            "left_field": make_field("alpha-beta"),
            "branches": make_field(
                [
                    {
                        "display_name": "contains beta",
                        "operator": "include",
                        "right_field_key": "case_1_right_field",
                        "output_value_key": "case_1_value",
                        "output_handle": "case_1_output",
                    },
                    {
                        "display_name": "starts with gamma",
                        "operator": "starts_with",
                        "right_field_key": "case_2_right_field",
                        "output_value_key": "case_2_value",
                        "output_handle": "case_2_output",
                    },
                ]
            ),
            "case_1_right_field": make_field("beta"),
            "case_1_value": make_field("branch-1"),
            "case_1_output": make_field(is_output=True),
            "case_2_right_field": make_field("gamma"),
            "case_2_value": make_field("branch-2"),
            "case_2_output": make_field(is_output=True),
            "default_value_key": make_field("default_value"),
            "default_output_handle": make_field("default_output"),
            "default_value": make_field("fallback"),
            "default_output": make_field(is_output=True),
            "output": make_field(is_output=True),
        }
    )

    handle, value, active_handles = resolve_conditional_branch(workflow, "conditional-node")

    assert handle == "case_1_output"
    assert value == "branch-1"
    assert active_handles == ["case_1_output", "case_2_output", "default_output"]


def test_mark_branch_skipped_marks_descendants_but_keeps_direct_merge_node() -> None:
    workflow = Workflow(
        {
            "wid": "wf-1",
            "rid": "run-1",
            "nodes": [
                make_node("conditional"),
                make_node("active-node"),
                make_node("skipped-node"),
                make_node("skipped-child"),
                make_node("merge-node"),
            ],
            "edges": [
                {
                    "source": "conditional",
                    "sourceHandle": "case_1_output",
                    "target": "active-node",
                    "targetHandle": "input",
                },
                {
                    "source": "conditional",
                    "sourceHandle": "case_2_output",
                    "target": "skipped-node",
                    "targetHandle": "input",
                },
                {
                    "source": "skipped-node",
                    "sourceHandle": "output",
                    "target": "skipped-child",
                    "targetHandle": "input",
                },
                {
                    "source": "conditional",
                    "sourceHandle": "case_1_output",
                    "target": "merge-node",
                    "targetHandle": "input_a",
                },
                {
                    "source": "conditional",
                    "sourceHandle": "case_2_output",
                    "target": "merge-node",
                    "targetHandle": "input_b",
                },
            ],
        }
    )

    workflow.mark_branch_skipped("conditional", "case_2_output")

    assert workflow.is_node_skipped("skipped-node") is True
    assert workflow.is_node_skipped("skipped-child") is True
    assert workflow.is_node_skipped("active-node") is False
    assert workflow.is_node_skipped("merge-node") is False


def test_skipped_task_still_reports_finished_node(monkeypatch) -> None:
    executed: list[str] = []
    reported: list[str] = []

    class _FakeWorkflow:
        def __init__(self, workflow_data):
            self.workflow_data = workflow_data

        def report_node_status(self, node_id):
            reported.append(node_id)

    monkeypatch.setattr("utilities.workflow.Workflow", _FakeWorkflow)

    @worker_tasks_module.task
    def _dummy_task(workflow_data: dict, node_id: str):
        executed.append(node_id)
        return workflow_data

    result = _dummy_task({"rid": "run-1", "skipped_nodes": ["node-1"]}, "node-1")

    assert result["skipped_nodes"] == ["node-1"]
    assert executed == []
    assert reported == ["node-1"]


def test_report_workflow_status_updates_cached_record_status(monkeypatch) -> None:
    cache_updates: dict[str, int] = {}

    class _FakeWorkflowRunRecordModel:
        rid = object()
        RunFromTypes = SimpleNamespace(CHAT="CHAT")

        @staticmethod
        def get(*args, **kwargs):
            return SimpleNamespace(
                status="RUNNING",
                data={"nodes": []},
                run_from="WEB",
                source_message=None,
                end_time=None,
                save=lambda: 1,
            )

    monkeypatch.setattr(workflow_module, "WorkflowRunRecord", _FakeWorkflowRunRecordModel)
    monkeypatch.setattr(
        workflow_module,
        "cache",
        SimpleNamespace(set=lambda key, value, ttl: cache_updates.__setitem__(key, value)),
    )

    workflow = Workflow(
        {
            "wid": "wf-1",
            "rid": "run-1",
            "nodes": [],
            "edges": [],
        }
    )

    assert workflow.report_workflow_status(200) is True
    assert cache_updates["workflow:record:run-1"] == 200
