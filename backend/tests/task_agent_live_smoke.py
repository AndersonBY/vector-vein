"""Opt-in real-model acceptance. Reads an external settings file; never copies credentials."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--model", default="deepseek-v4.1-flash")
    args = parser.parse_args()
    settings_path = Path(args.settings).resolve()
    workspace = Path(args.workspace).resolve()
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError("Live checks require a new empty workspace")
    workspace.mkdir(parents=True, exist_ok=True)
    raw = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    matches = [(backend, key) for backend, value in raw["backends"].items() for key, model in value.get("models", {}).items()
               if key == args.model and model.get("id", key) == args.model]
    if len(matches) != 1:
        raise ValueError("The requested model is not uniquely configured")
    backend, model = matches[0]
    secrets = [endpoint.get("api_key", "") for endpoint in raw.get("endpoints", []) if len(endpoint.get("api_key", "")) >= 8]

    class RedactedStream:
        def __init__(self, stream):
            self.stream = stream
        def write(self, value):
            for secret in secrets:
                value = value.replace(secret, "[REDACTED]")
            return self.stream.write(value)
        def flush(self):
            return self.stream.flush()
        def __getattr__(self, name):
            return getattr(self.stream, name)

    sys.stdout = RedactedStream(sys.stdout)
    sys.stderr = RedactedStream(sys.stderr)
    os.chdir(workspace)
    os.environ["VECTORVEIN_LLM_SETTINGS_FILE"] = str(settings_path)
    os.environ["VECTORVEIN_OUTPUT_DIR"] = str(workspace / "exports")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cli import initialize
    from task_agent.service import TaskAgentService
    from models import WorkflowRunRecord
    from celery_worker import CeleryWorkerManager
    from task_agent_workflow_fixture import create_workflow
    initialize()
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.ERROR)
    report = {"model": args.model, "tasks": [], "approvals": 0, "questions": 0, "workflow_feedback": 0, "restart_during_feedback": False}
    service = TaskAgentService(workspace)
    worker = None

    def wait(tid, workflow_tool=None):
        nonlocal service
        deadline = time.monotonic() + 420
        seen = set()
        while time.monotonic() < deadline:
            detail = service.get_task(tid)
            state = detail["state"]
            report["last_state"] = {"task_id": tid, "status": detail["task"]["status"], "phase": state.get("phase"), "watermark": state.get("projectionWatermark")}
            pending = state.get("pendingInteraction")
            if pending and pending["kind"] == "approval":
                entry = next(item for item in detail["timeline"] if item.get("request_id") == pending["requestId"] and item["kind"] == "approval_requested")
                if not workflow_tool or entry["tool_name"] != workflow_tool:
                    raise AssertionError("Unexpected approval; test will not authorize it")
                service.approve({"task_id": tid, "turn_id": detail["task"]["current_turn_id"], "request_id": pending["requestId"], "decision": "allow"})
                report["approvals"] += 1
            elif pending and pending["kind"] == "user":
                identity = pending["interactionId"]
                if identity not in seen:
                    if report["questions"] >= 3:
                        raise AssertionError("Unexpected repeated questions")
                    target = {key: pending[key] for key in ("sessionId", "turnId", "generation", "interactionId", "operationId", "attempt", "requestDigest")}
                    service.act({"task_id": tid, "turn_id": detail["task"]["current_turn_id"], "action_id": "answer_" + str(report["questions"]),
                                 "action": {"kind": "respond", "target": target, "answer": {"kind": "text", "text": "请使用 Markdown 格式。"}}})
                    seen.add(identity)
                    report["questions"] += 1
            for run in detail.get("workflow_runs", []):
                for feedback in run["feedback"]:
                    if not report["restart_during_feedback"]:
                        service.stop()
                        service = TaskAgentService(workspace)
                        reopened = service.get_task(tid)
                        assert reopened["workflow_runs"][0]["run_id"] == run["run_id"]
                        report["restart_during_feedback"] = True
                    response = {"task_id": tid, "run_id": feedback["run_id"], "generation": feedback["generation"], "action_id": "review_" + str(feedback["generation"]),
                                "answers": [{"node_id": question["node_id"], "content": "审核通过。合计 176 元。"} for question in feedback["questions"]]}
                    service.workflow_feedback(response)
                    service.workflow_feedback(response)
                    report["workflow_feedback"] += 1
            if detail["task"]["status"] == "COMPLETED":
                tools = [item for item in detail["timeline"] if item["kind"] == "tool"]
                report["tasks"].append({"task_id": tid, "status": "COMPLETED", "wire_model_id": detail["task"]["config_snapshot"]["model_id"], "tools": [item["tool_name"] for item in tools],
                                        "tool_errors": [item.get("error_code") for item in tools if item.get("status") == "error"]})
                return detail
            if detail["task"]["status"] in {"FAILED", "INTERRUPTED"}:
                raise AssertionError("Live task ended with status " + detail["task"]["status"])
            time.sleep(0.5)
        raise TimeoutError("Live task exceeded the test deadline")

    try:
        source = workspace / "sales.csv"
        source.write_text("product,quantity,unit_price\nA,3,12\nB,4,20\nC,2,30\n", encoding="utf-8")
        service.save_profile({"agent_id": "core", "name": "Live core check", "instructions": "严格按要求使用工具，回复简短。", "max_cycles": 10})
        service.create_task({"input_id": "live_core", "turn_input_id": "start", "agent_id": "core", "model_provider": backend, "model": model,
                             "attachments": [str(source)], "goal": "读取附件 sales.csv，计算每项金额和总金额。必须先用 ask_user 询问报告格式；收到回答后用 write_file 生成 outputs/live-summary.md，写出计算结果。不要在询问前生成文件，完成后给出文件链接。"})
        detail = wait("live_core")
        assert report["questions"] >= 1
        summary = service._task_workspace("live_core") / "outputs" / "live-summary.md"
        assert summary.is_file() and "176" in summary.read_text(encoding="utf-8")
        assert {"read_file", "ask_user", "write_file"}.issubset(report["tasks"][0]["tools"])
        print("Core live-model task passed", flush=True)
        workflow = create_workflow()
        worker = CeleryWorkerManager(concurrency=1)
        worker.start()
        service.save_profile({"agent_id": "workflow", "name": "Live workflow check", "instructions": "必须调用选中的工作流完成交付。只调用一次工作流，应用负责审批和人工反馈。收到工作流结果后检查文件并简短回复链接。", "max_cycles": 8,
                              "allow_file_writes": False, "workflow_ids": [workflow.wid.hex]})
        service.create_task({"input_id": "live_workflow", "turn_input_id": "start", "agent_id": "workflow", "model_provider": backend, "model": model,
                             "goal": "调用 Local report workflow 工作流，text 参数为‘销售汇总：A 为 36 元，B 为 80 元，C 为 60 元，合计 176 元。’，等待我在应用中确认并填写审核反馈后交付它生成的文件。不要再通过 ask_user 提问。"})
        detail = wait("live_workflow", "workflow_" + workflow.wid.hex)
        assert report["approvals"] == 1 and report["workflow_feedback"] == 1 and report["restart_during_feedback"]
        assert WorkflowRunRecord.select().count() == 1
        assert len(detail["workflow_runs"]) == 1 and detail["workflow_runs"][0]["status"] == "FINISHED"
        copies = list((service._task_workspace("live_workflow") / "outputs" / "workflows").rglob("*.md"))
        assert len(copies) == 1 and "176" in copies[0].read_text(encoding="utf-8")
        service.stop()
        service = TaskAgentService(workspace)
        assert service.get_task("live_workflow")["task"]["status"] == "COMPLETED"
        report["workflow_runs"] = WorkflowRunRecord.select().count()
        report["passed"] = True
    finally:
        service.stop()
        if worker is not None:
            worker.stop()
        # No secret values, or provider configuration objects, enter the report.
        leaked = []
        for path in workspace.rglob("*"):
            if path.is_file() and path.stat().st_size < 64 * 1024 * 1024:
                try:
                    content = path.read_bytes()
                except OSError:
                    continue
                if any(secret.encode() in content for secret in secrets):
                    leaked.append(path.relative_to(workspace).as_posix())
        report["credential_scan"] = "passed" if not leaked else "failed"
        if leaked:
            report["credential_files"] = leaked
            report["passed"] = False
        (workspace / "live-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), flush=True)
        if leaked:
            raise AssertionError("Credentials were found in test artifacts")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # SDK/config exceptions may contain credentials; only report the exception class.
        print(json.dumps({"passed": False, "error_type": type(error).__name__}), flush=True)
        sys.exit(1)
