"""Headless workflow CLI sharing the desktop database and execution engine."""
from __future__ import annotations

import argparse
import io
import contextlib
import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from bootstrap import APP_ROOT


def read_json(file: Path):
    return json.loads(file.read_text(encoding="utf-8-sig"))


def version():
    file = APP_ROOT / "version.txt"
    if file.exists():
        return file.read_text(encoding="utf-8").strip()
    match = re.search(r'^version\s*=\s*"([^"]+)"', (APP_ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else "unknown"


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--version", action="version", version=version())
    result.add_argument("--workspace", type=Path, default=APP_ROOT, help="Desktop installation or isolated workspace directory")
    result.add_argument("--settings", type=Path, help="External vv-llm settings for this process; never copied into the database")
    result.add_argument("--output-dir", type=Path, help="Artifact directory for this process")
    result.add_argument("--result-file", type=Path, help="Also save the command JSON result")
    groups = result.add_subparsers(dest="group", required=True)
    groups.add_parser("init", help="Initialize the workspace without opening a GUI")
    commands = groups.add_parser("workflow").add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("--search", default="")
    listing.add_argument("--limit", type=int, default=20)
    get = commands.add_parser("get")
    get.add_argument("wid")
    create = commands.add_parser("create")
    create.add_argument("--file", type=Path, required=True)
    create.add_argument("--title")
    update = commands.add_parser("update")
    update.add_argument("wid")
    update.add_argument("--file", type=Path, required=True)
    update.add_argument("--title")
    update.add_argument("--expected-version", type=int, help="Refuse to overwrite a different saved version")
    patch = commands.add_parser("patch")
    patch.add_argument("wid")
    patch.add_argument("--inputs", type=Path, required=True, help="JSON array of node_id/field_name/value records")
    patch.add_argument("--expected-version", type=int)
    validate = commands.add_parser("validate")
    validate.add_argument("--file", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("wid")
    run.add_argument("--inputs", type=Path)
    run.add_argument("--full", action="store_true", help="Include all intermediate node values")
    status = commands.add_parser("status")
    status.add_argument("rid")
    status.add_argument("--full", action="store_true")
    records = commands.add_parser("records")
    records.add_argument("wid")
    records.add_argument("--limit", type=int, default=20)
    return result


def validate_data(data: dict):
    from utilities.workflow import Workflow
    from background_task.workflow_tasks import task_functions
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list) or not isinstance(data.get("edges"), list):
        raise ValueError("Workflow must contain nodes and edges arrays")
    nodes = {node["id"]: node for node in data["nodes"]}
    if len(nodes) != len(data["nodes"]):
        raise ValueError("Node IDs must be unique")
    for node in nodes.values():
        module, function = node["data"]["task_name"].split(".")
        if function not in task_functions.get(module, {}):
            raise ValueError(f"Unknown task: {module}.{function}")
    targets = set()
    for edge in data["edges"]:
        if edge.get("ignored"):
            continue
        for side in ("source", "target"):
            if edge[side] not in nodes or edge[side + "Handle"] not in nodes[edge[side]]["data"]["template"]:
                raise ValueError("Edge references an unknown node or field")
        target = (edge["target"], edge["targetHandle"])
        if target in targets:
            raise ValueError("A field may have only one incoming edge")
        targets.add(target)
    Workflow(deepcopy(data)).dag.topological_sort()


def apply_inputs(data, inputs):
    if not isinstance(inputs, list):
        raise ValueError("Inputs must be an array")
    nodes = {node["id"]: node for node in data["nodes"]}
    for item in inputs:
        node = nodes.get(item["node_id"])
        if node is None or item["field_name"] not in node["data"]["template"]:
            raise ValueError("Input references an unknown node or field")
        node["data"]["template"][item["field_name"]]["value"] = item["value"]


def initialize():
    from models import create_tables, database
    from utilities.config import config, Settings
    from peewee_migrate import Router
    Path(config.data_path).mkdir(parents=True, exist_ok=True)
    router = Router(database, migrate_dir=str(APP_ROOT / "migrations"))
    if not database.table_exists("workflow"):
        create_tables()
        router.run(fake=True)
    else:
        router.run()
        create_tables()
    Settings()


def checked(response):
    if response.get("status") != 200:
        raise ValueError(response.get("msg", "Command failed"))
    return response["data"]


def record_result(record, full=False):
    result = {"rid": record.rid.hex, "wid": record.workflow.wid.hex, "status": record.status,
              "workflow_version": record.workflow_version, "outputs": {}}
    for node in record.data.get("nodes", []):
        fields = {name: item.get("value") for name, item in node["data"]["template"].items() if item.get("is_output")}
        if fields:
            result["outputs"][node["id"]] = fields
    if full:
        result["data"] = record.data
    if record.status == "FAILED":
        result["error_task"] = record.data.get("error_task", "")
    return result


def execute(args):
    from api.workflow_api import WorkflowAPI
    from models import Workflow as WorkflowModel, WorkflowRunRecord
    from utilities.workflow import WorkflowData
    from celery_worker import app
    from background_task.workflow_tasks import run_workflow
    api = WorkflowAPI()
    if args.group == "init":
        return {"workspace": str(Path.cwd()), "version": version()}, 0
    if args.command == "list":
        data = checked(api.list({"search_text": args.search, "page_size": args.limit}))
        return {"total": data["total"], "workflows": [{k: row[k] for k in ("wid", "title", "version", "status")} for row in data["workflows"]]}, 0
    if args.command == "validate":
        spec = read_json(args.file)
        validate_data(spec.get("data", spec))
        return {"valid": True}, 0
    if args.command == "create":
        spec = read_json(args.file)
        data = spec.get("data", spec)
        validate_data(data)
        payload = {"title": args.title or spec.get("title") or args.file.stem, "brief": spec.get("brief", ""), "data": data}
        created = checked(api.create(payload))
        return {k: created[k] for k in ("wid", "title", "version")}, 0
    if args.command == "status":
        record = WorkflowRunRecord.get_or_none(WorkflowRunRecord.rid == args.rid)
        if record is None:
            raise ValueError("Run record not found")
        return record_result(record, args.full), 0
    if args.command == "records":
        query = WorkflowRunRecord.select().join(WorkflowModel).where(WorkflowModel.wid == args.wid).order_by(WorkflowRunRecord.start_time.desc()).limit(args.limit)
        return {"runs": [{"rid": record.rid.hex, "status": record.status, "workflow_version": record.workflow_version, "start_time": record.start_time.isoformat()} for record in query]}, 0
    saved = checked(api.get({"wid": args.wid}))
    if args.command == "get":
        return saved, 0
    if args.command in ("update", "patch"):
        if args.expected_version is not None and saved["version"] != args.expected_version:
            raise ValueError("Saved workflow version changed")
        payload = {key: saved[key] for key in ("title", "brief", "images", "language")}
        payload.update(wid=args.wid, tags=[tag["tid"] for tag in saved.get("tags", [])], refresh_tool_data=False)
        if args.command == "update":
            spec = read_json(args.file)
            data = spec.get("data", spec)
            payload["title"] = args.title or spec.get("title") or saved["title"]
            payload["brief"] = spec.get("brief", saved["brief"])
        else:
            data = deepcopy(saved["data"])
            apply_inputs(data, read_json(args.inputs))
        validate_data(data)
        payload["data"] = data
        updated = checked(api.update(payload))
        return {key: updated[key] for key in ("wid", "title", "version")}, 0
    data = deepcopy(saved["data"])
    if args.inputs:
        apply_inputs(data, read_json(args.inputs))
    validate_data(data)
    data["related_workflows"] = WorkflowData(data).related_workflows
    model = WorkflowModel.get_by_id(args.wid)
    record = WorkflowRunRecord.create(workflow=model, workflow_version=model.version, data=data, status="RUNNING", run_from=WorkflowRunRecord.RunFromTypes.CLI)
    data.update(wid=model.wid.hex, rid=record.rid.hex)
    print(json.dumps({"event": "run_started", "rid": record.rid.hex}), file=sys.stderr, flush=True)
    app.conf.update(task_always_eager=True, task_eager_propagates=False)
    try:
        # The same Celery chain runs synchronously; a separate broker worker is unnecessary.
        run_workflow.run(data).get(propagate=True)
    except (Exception, KeyboardInterrupt) as exc:
        record = WorkflowRunRecord.get_by_id(record.rid)
        if record.status != "FAILED":
            record.status = "FAILED"
            record.end_time = datetime.now()
            record.data = {**record.data, "error_type": type(exc).__name__}
            record.save()
    record = WorkflowRunRecord.get_by_id(record.rid)
    return record_result(record, args.full), 0 if record.status == "FINISHED" else 1


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    for name in ("workspace", "settings", "output_dir", "result_file", "file", "inputs"):
        value = getattr(args, name, None)
        if value is not None:
            setattr(args, name, value.resolve())
    args.workspace.mkdir(parents=True, exist_ok=True)
    if args.settings:
        os.environ["VECTORVEIN_LLM_SETTINGS_FILE"] = str(args.settings)
    if args.output_dir:
        os.environ["VECTORVEIN_OUTPUT_DIR"] = str(args.output_dir)
    os.chdir(args.workspace)
    code = 2
    try:
        with contextlib.redirect_stdout(sys.stderr):
            initialize()
            result, code = execute(args)
    except Exception as exc:
        # Provider errors may contain credentials; only configuration errors expose a message.
        result = {"error": type(exc).__name__}
        if type(exc).__name__ == "ValidationError":
            result["message"] = "Configuration validation failed; check the selected settings and schema"
        elif isinstance(exc, (ValueError, FileNotFoundError)):
            result["message"] = str(exc)
    finally:
        if "utilities.config" in sys.modules:
            from utilities.config import cache, config
            from models import database
            cache.close()
            database.close()
            config.close()
    encoded = json.dumps(result, ensure_ascii=False, default=str, indent=2)
    if args.result_file:
        args.result_file.parent.mkdir(parents=True, exist_ok=True)
        args.result_file.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
