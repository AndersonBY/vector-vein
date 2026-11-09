"""Bounded task-workspace browsing; paths never grant access outside this task."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .service import required_id
from .projects import task_roots, validate_saved_roots, project_view

TEXT_TYPES = {".txt", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".css", ".html", ".xml", ".log", ".sql"}
DOCUMENT_TYPES = TEXT_TYPES | {".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
PREVIEW_TEXT_TYPES = TEXT_TYPES | {".vue", ".jsx", ".tsx", ".mjs", ".cjs", ".scss", ".less", ".toml", ".rs", ".go", ".c", ".h", ".cpp", ".hpp", ".sh", ".ps1"}


def _reserved_knowledge(relative):
    if not isinstance(relative, str):
        return False
    # Reserve every spelling before physical resolution, including malformed escapes.
    from urllib.parse import unquote
    raw = unquote(relative).replace("\\", "/")
    return any(part.rstrip(" .").casefold() == ".knowledge" for part in raw.split("/"))


def _knowledge(service, tid, args, *, project_id=None):
    if project_id is not None or tid is None:
        raise ValueError("Knowledge files require a task")
    task = service.store.get_task(required_id(tid, "task ID"))
    if task is None:
        raise KeyError(tid)
    from .knowledge import validate_frozen_knowledge
    mounts = validate_frozen_knowledge(task["config_snapshot"], task["config_snapshot"])
    if not mounts:
        raise ValueError("No knowledge bases mounted")
    from knowledge_base import knowledge_service
    from knowledge_base.virtual import virtual_operation
    return virtual_operation(knowledge_service(), mounts, args)


def workspace_roots(service, tid, *, project_id=None):
    if project_id is not None:
        if tid is not None:
            raise ValueError("Choose one workspace scope")
        project = service.store.get_project(required_id(project_id, "project ID"))
        if project is None:
            raise KeyError(project_id)
        return project, [Path(root) for root in project["roots"]]
    tid = required_id(tid, "task ID")
    task = service.store.get_task(tid)
    if task is None:
        raise KeyError(tid)
    return task["config_snapshot"].get("project"), task_roots(service.task_root, tid, task["config_snapshot"])


def workspace_file(service, tid, relative=None, *, project_id=None):
    if _reserved_knowledge(relative):
        raise ValueError("Knowledge files have no local workspace path")
    project, roots = workspace_roots(service, tid, project_id=project_id)
    if relative is None:
        return roots[0]
    if not isinstance(relative, str) or not relative or "\0" in relative:
        raise ValueError("Invalid workspace path")
    raw = relative.replace("\\", "/")
    selected = None
    if project and raw.startswith("project-files/"):
        parts = raw.split("/", 2)
        if len(parts) != 3 or not parts[1].isdigit() or int(parts[1]) >= len(roots):
            raise ValueError("Invalid workspace root")
        selected = roots[int(parts[1])]
        raw = parts[2]
        if Path(raw).is_absolute() or ":" in raw:
            raise ValueError("Invalid workspace path")
    path = Path(raw)
    if any(part.casefold() == ".vv-agent" for part in path.parts):
        raise ValueError("Private tool artifacts cannot be browsed")
    if not project and (path.is_absolute() or ":" in relative or "\\" in relative or ".." in path.parts):
        raise ValueError("Invalid workspace path")
    lexical = path if path.is_absolute() else (selected or roots[0]) / path
    if project:
        candidates = [selected] if selected else [root for root in roots if lexical.is_relative_to(root)]
        if not candidates:
            raise ValueError("Path escapes workspace")
        for root in candidates:
            validate_saved_roots([str(root)])
    target = lexical.resolve()
    allowed = [selected] if selected else roots
    if not any(target != root and target.is_relative_to(root) for root in allowed):
        raise ValueError("Path escapes workspace")
    if os.name == "nt" and ":" in str(target)[len(target.anchor):]:
        raise ValueError("Alternate data streams cannot be browsed")
    if not target.is_file():
        raise FileNotFoundError(relative)
    return target


def list_files(service, tid, root_id=None, *, project_id=None):
    project, roots = workspace_roots(service, tid, project_id=project_id)
    root_id = "0" if root_id is None else str(root_id)
    if not root_id.isdigit() or int(root_id) >= len(roots):
        raise ValueError("Invalid workspace root")
    root_id = str(int(root_id))
    root = roots[int(root_id)]
    if project:
        validate_saved_roots([str(root)])
    folders = project_view(project)["folders"] if project else []
    files = []
    visited = 0
    limited = False
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in {"node_modules", "__pycache__"} and not Path(base, d).is_symlink() and Path(base, d).resolve().is_relative_to(root))
        for name in sorted(names):
            if _reserved_knowledge(name):
                continue
            visited += 1
            if visited > 1000:
                limited = True
                break
            path = Path(base, name)
            if path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            reference = f"project-files/{root_id}/{relative}" if project else relative
            try:
                target = path.resolve()
                if not target.is_relative_to(root.resolve()):
                    continue
                stat = target.stat()
            except (OSError, ValueError):
                continue
            files.append({"path": reference, "relative_path": relative, "root_id": root_id, "name": name, "size": stat.st_size, "modified_at": stat.st_mtime,
                          "is_input": relative.startswith("inputs/"), "can_open": target.suffix.lower() in DOCUMENT_TYPES})
        if limited:
            break
    if tid is not None and project_id is None and root_id == "0":
        task = service.store.get_task(required_id(tid, "task ID"))
        if task is not None and task["config_snapshot"].get("knowledge_bases"):
            listing = _knowledge(service, tid, {"action": "list", "path": ".knowledge", "limit": 1000, "recursive": True})
            entries = [entry for entry in listing["entries"] if entry["kind"] == "file"]
            remaining = max(0, 1000 - len(files))
            files.extend({"path": entry["path"], "relative_path": entry["path"], "root_id": "0",
                          "name": entry["name"], "size": entry.get("size"), "modified_at": entry["modified_at"],
                          "can_open": False, "read_only": True} for entry in entries[:remaining])
            limited = limited or bool(listing.get("truncated") or listing.get("next_offset") is not None
                                      or len(entries) > remaining)
    return {"files": files, "limited": limited, "roots": folders, "root_id": root_id}


def preview_file(service, tid, relative, *, project_id=None):
    if _reserved_knowledge(relative):
        result = _knowledge(service, tid, {"action": "read", "path": relative, "limit": 131072}, project_id=project_id)
        return {"kind": "text", "text": result["text"], "path": relative, "read_only": True,
                "markdown": relative.lower().endswith(".md"),
                "truncated": result.get("next_offset") is not None or result["total"] > len(result["text"])}
    path = workspace_file(service, tid, relative, project_id=project_id)
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        from utilities.attachment_preview import attachment_image_url
        return {"kind": "image", "url": attachment_image_url({"path": str(path), "thumbnail": False}), "path": relative}
    if suffix in PREVIEW_TEXT_TYPES:
        with path.open("rb") as source:
            content = source.read(131073)
        return {"kind": "text", "text": content[:131072].decode("utf-8", errors="replace"),
                "truncated": len(content) > 131072, "markdown": suffix == ".md", "path": relative}
    return {"kind": "unsupported", "path": relative}


def open_file(service, tid, relative, reveal=False, *, project_id=None):
    path = workspace_file(service, tid, relative, project_id=project_id)
    if not reveal and path.suffix.lower() not in DOCUMENT_TYPES:
        raise ValueError("Only document files can be opened")
    if os.name == "nt":
        if reveal:
            subprocess.Popen(["explorer.exe", "/select,", str(path)], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.startfile(path)
    else:
        import sys
        args = (["open", "-R", str(path)] if reveal else ["open", str(path)]) if sys.platform == "darwin" else ["xdg-open", str(path.parent if reveal else path)]
        subprocess.Popen(args)
    return {"opened": True}
