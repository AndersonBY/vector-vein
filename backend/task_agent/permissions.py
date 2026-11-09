"""Task-scoped tool approval decisions, applied before execution by vv-agent."""
from __future__ import annotations

from pathlib import Path

PERMISSION_MODES = ("ask", "auto", "full")
READ_ONLY_FILE_TOOLS = {"find_files", "file_info", "read_file", "search_files", "read_image"}
FILE_TOOLS = READ_ONLY_FILE_TOOLS | {"write_file", "edit_file"}


def validate_permission_mode(value):
    if value not in PERMISSION_MODES:
        raise ValueError("Invalid task permission mode")
    return value


def outside_workspace(workspace: Path, raw) -> bool:
    if not isinstance(raw, str):
        return True
    try:
        path = Path(raw).expanduser()
        target = (path if path.is_absolute() else workspace / path).resolve()
        return not target.is_relative_to(workspace.resolve())
    except (OSError, ValueError):
        return True


def requires_approval(mode, name, context, arguments):
    if mode == "full":
        return False
    if name in FILE_TOOLS:
        raw = arguments.get("path", ".")
        metadata = {**(getattr(context, "task_metadata", None) or {}), **(getattr(getattr(context, "ctx", None), "metadata", None) or {})}
        roots = list(metadata.get("workspace_roots") or [str(context.workspace)])
        if name in READ_ONLY_FILE_TOOLS and isinstance(metadata.get("skill_roots"), list):
            roots.extend(str(item) for item in metadata["skill_roots"] if isinstance(item, str) and item)
        # Relative paths always start at cwd, never independently at each additional root.
        if isinstance(raw, str):
            candidate = Path(raw).expanduser()
            raw = str(candidate if candidate.is_absolute() else context.workspace / candidate)
        outside = not any(not outside_workspace(Path(root), raw) for root in roots)
        return (mode == "auto" and name in {"write_file", "edit_file"}) or outside
    if name == "bash":
        return True
    return False