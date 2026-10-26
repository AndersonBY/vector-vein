"""Local files explicitly produced by a workflow run; never scan inputs or folders."""
import os
import math
from pathlib import Path
import re
import subprocess
import sys
import time


def local_path(value):
    if not isinstance(value, (str, os.PathLike)):
        return None
    value = os.fspath(value)
    if not value or "\x00" in value or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) and not re.match(r"^[a-zA-Z]:[\\/]", value):
        return None
    path = Path(value)
    return Path(os.path.abspath(path)) if path.is_absolute() else None


def _key(path):
    return os.path.normcase(os.path.abspath(path))


def register_artifact(workflow_data, node_id, path):
    """Metadata is best effort and must never change a producer's result."""
    try:
        value = os.fspath(path)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) and not re.match(r"^[a-zA-Z]:[\\/]", value):
            return
        path = local_path(os.path.abspath(value))
        if path is None or not path.is_file():
            return
        node = next(node for node in workflow_data.get("nodes", []) if node.get("id") == node_id)
        artifacts = node.setdefault("data", {}).setdefault("artifacts", [])
        if not any(isinstance(item, dict) and local_path(item.get("path")) is not None and _key(item["path"]) == _key(path) for item in artifacts):
            artifacts.append({"path": str(path), "name": path.name, "created_at": int(time.time() * 1000)})
    except Exception:
        pass


def _paths(value):
    if isinstance(value, list):
        for item in value:
            yield from _paths(item)
    elif isinstance(value, str):
        yield value


def get_run_artifacts(snapshot):
    rows = {}
    timeline = snapshot.get("node_timeline", {})
    timeline = timeline if isinstance(timeline, dict) else {}
    nodes = snapshot.get("nodes", [])
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        metadata = node.get("data", {})
        if not isinstance(metadata, dict):
            continue
        artifacts = metadata.get("artifacts", [])
        if not isinstance(artifacts, list):
            artifacts = []
        if "artifacts" not in metadata:
            progress = timeline.get(node.get("id"), {}) if isinstance(node.get("id"), str) else {}
            executed = metadata.get("status", node.get("status")) == 200 or isinstance(progress, dict) and progress.get("status") == "SUCCEEDED"
            kind = node.get("type")
            field = {"Document": "output", "ProgrammingFunction": "files", "DocumentConvert": "output"}.get(kind) if isinstance(kind, str) else None
            if executed and field:
                template = metadata.get("template", {})
                output = template.get(field, {}) if isinstance(template, dict) else {}
                value = output.get("value") if isinstance(output, dict) else None
                artifacts = [{"path": path} for path in _paths(value)]
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            path = local_path(artifact.get("path"))
            if path is None:
                continue
            key = _key(path)
            if key not in rows:
                try:
                    exists = path.is_file()
                    size = path.stat().st_size if exists else None
                    parent_exists = path.parent.is_dir()
                except OSError:
                    exists, size, parent_exists = False, None, False
                created = artifact.get("created_at")
                name = artifact.get("name")
                rows[key] = {"path": str(path), "name": name[:500] if isinstance(name, str) and name else path.name,
                             "size": size, "exists": exists, "parent_exists": parent_exists,
                             "created_at": created if type(created) is int or isinstance(created, float) and math.isfinite(created) else None, "sources": []}
            kind = node.get("type") if isinstance(node.get("type"), str) else ""
            title = metadata.get("title")
            source = {"node_id": node.get("id") if isinstance(node.get("id"), str) else "", "node_type": kind[:200], "title": title[:200] if isinstance(title, str) else ""}
            if source not in rows[key]["sources"]:
                rows[key]["sources"].append(source)
    return list(rows.values())


def open_run_artifact(snapshot, requested_path, action):
    if action not in ("open", "folder") or local_path(requested_path) is None:
        return 400, "Invalid artifact request"
    artifact = next((row for row in get_run_artifacts(snapshot) if _key(row["path"]) == _key(requested_path)), None)
    if artifact is None:
        return 404, "Artifact not found in this run"
    if not artifact["exists" if action == "open" else "parent_exists"]:
        return 404, "Artifact file or folder no longer exists"
    target = artifact["path"] if action == "open" else str(Path(artifact["path"]).parent)
    try:
        if sys.platform == "win32":
            os.startfile(target)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", target], shell=False)
    except Exception:
        return 500, "Unable to open artifact"
    return 200, ""
