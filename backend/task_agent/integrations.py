"""Skills and MCP selection, freezing, public projection, and host bindings."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from vv_agent.skills import SkillEntry, render_skills_xml

from .mcp_library import MCPLibrary, MCPLibraryError
from .skills import SkillLibraryError
from .store import BusinessStore

MAX_SELECTED_SKILLS = 20
MAX_SELECTED_MCP_TOOLS = 64

_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_MCP_TOOL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

SKILL_RUNTIME_HEADER = (
    "\n\nAvailable skills metadata (Agent Skills format):\n"
    "When a task matches one of the skills below, call `activate_skill` with its exact name as `skill_name` "
    "to load the full instructions before using its bundled references or assets.\n"
)


def validate_skill_ids_format(skill_ids: Any) -> list[str]:
    if (
        not isinstance(skill_ids, list)
        or len(skill_ids) > MAX_SELECTED_SKILLS
        or not all(isinstance(item, str) and bool(_SKILL_ID_RE.fullmatch(item)) for item in skill_ids)
        or len(set(skill_ids)) != len(skill_ids)
    ):
        raise SkillLibraryError(
            "invalid_skill_selection",
            f"Select at most {MAX_SELECTED_SKILLS} distinct skills",
        )
    return list(skill_ids)


def validate_mcp_tool_ids_format(mcp_tool_ids: Any) -> list[str]:
    if (
        not isinstance(mcp_tool_ids, list)
        or len(mcp_tool_ids) > MAX_SELECTED_MCP_TOOLS
        or not all(isinstance(item, str) and bool(_MCP_TOOL_ID_RE.fullmatch(item)) for item in mcp_tool_ids)
        or len(set(mcp_tool_ids)) != len(mcp_tool_ids)
    ):
        raise MCPLibraryError(
            "invalid_mcp_tool_selection",
            f"Select at most {MAX_SELECTED_MCP_TOOLS} distinct MCP tools",
            dispatch_uncertain=False,
        )
    return list(mcp_tool_ids)


def selected_skills(task_root: Path, store: BusinessStore, skill_ids: Any) -> list[dict[str, Any]]:
    ids = validate_skill_ids_format(skill_ids)
    if not ids:
        return []
    skills_root = (Path(task_root).resolve() / "skills").resolve()
    descriptors: list[dict[str, Any]] = []
    seen_names: dict[str, str] = {}
    for sid in ids:
        record = store.get_skill(sid)
        if record is None:
            raise SkillLibraryError("skill_not_found", f"Selected skill '{sid}' was not found")
        if not record.get("enabled", True):
            raise SkillLibraryError("skill_disabled", f"Selected skill '{sid}' is disabled")
        name = record["name"]
        if name in seen_names:
            raise SkillLibraryError(
                "duplicate_skill_name",
                f"Selected skills '{seen_names[name]}' and '{sid}' share the same skill name '{name}'",
            )
        seen_names[name] = sid
        bundle_path = Path(record["bundle_path"]).resolve()
        skill_md_path = Path(record.get("skill_md_path") or (bundle_path / "SKILL.md")).resolve()
        if (
            not bundle_path.is_relative_to(skills_root)
            or not skill_md_path.is_relative_to(bundle_path)
            or not skill_md_path.is_file()
        ):
            raise SkillLibraryError("skill_unavailable", f"Selected skill '{sid}' bundle is unavailable")
        descriptors.append(
            {
                "skill_id": record["skill_id"],
                "version": int(record["version"]),
                "name": name,
                "description": record["description"],
                "bundle_path": str(bundle_path),
                "location": str(skill_md_path),
                "bundle_digest": record["bundle_digest"],
                "allowed_tools": record.get("allowed_tools"),
                "compatibility": record.get("compatibility"),
                "metadata": dict(record.get("metadata") or {}),
                "file_count": int(record.get("file_count", len(record.get("files", [])))),
                "total_bytes": int(record.get("total_bytes", 0)),
            }
        )
    return descriptors




_CREDENTIAL_ENV_TOKENS = {"key", "api_key", "apikey", "token", "secret", "password", "passwd", "credential", "credentials", "auth", "bearer"}
_CREDENTIAL_HEADER_NAMES = {"authorization", "proxy-authorization", "x-api-key", "api-key", "x-auth-token", "x-access-token"}
_CREDENTIAL_HEADER_SUFFIXES = ("-api-key", "-token", "-secret", "-password", "-authorization", "-credential")
_CREDENTIAL_QUERY_NAMES = {"token", "access_token", "api_key", "apikey", "key", "secret", "password", "auth", "auth_token", "signature", "sig"}
_CREDENTIAL_QUERY_SUFFIXES = ("_token", "_key", "_secret", "_password", "_signature")


def _is_credential_env_key(name: str) -> bool:
    low = name.strip().lower()
    if low in _CREDENTIAL_ENV_TOKENS:
        return True
    parts = [p for p in re.split(r"[_-]+", low) if p]
    return bool(parts) and parts[-1] in _CREDENTIAL_ENV_TOKENS


def _is_credential_header_key(name: str) -> bool:
    low = name.strip().lower()
    return low in _CREDENTIAL_HEADER_NAMES or low.endswith(_CREDENTIAL_HEADER_SUFFIXES)


def _is_credential_query_key(name: str) -> bool:
    low = name.strip().lower()
    return low in _CREDENTIAL_QUERY_NAMES or low.endswith(_CREDENTIAL_QUERY_SUFFIXES)


def mcp_schema_digest(schema: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(schema or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def mcp_endpoint_fingerprint(record: dict[str, Any]) -> str:
    transport = record.get("transport", "")
    config = record.get("config") or {}
    secrets = record.get("secrets") or {}
    if transport == "stdio":
        env = secrets.get("env") or {}
        bound_env = {
            k: ("<credential>" if _is_credential_env_key(k) else v)
            for k, v in sorted(env.items())
        }
        payload: dict[str, Any] = {
            "transport": "stdio",
            "command": config.get("command", ""),
            "args": list(config.get("args") or []),
            "cwd": config.get("cwd"),
            "env": bound_env,
        }
    else:
        raw_url = secrets.get("url") or ""
        try:
            parsed = urlsplit(raw_url)
            base_url = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", ""))
            query_items = [
                (k, "<credential>" if _is_credential_query_key(k) else v)
                for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            ]
        except ValueError:
            base_url = ""
            query_items = []
        headers = secrets.get("headers") or {}
        bound_headers = {
            k.lower(): ("<credential>" if _is_credential_header_key(k) else v)
            for k, v in sorted(headers.items(), key=lambda item: item[0].lower())
        }
        payload = {
            "transport": transport,
            "base_url": base_url,
            "query": query_items,
            "headers": bound_headers,
        }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def selected_mcp_tools(task_root: Path, store: BusinessStore, mcp_tool_ids: Any) -> list[dict[str, Any]]:
    ids = validate_mcp_tool_ids_format(mcp_tool_ids)
    if not ids:
        return []
    library = MCPLibrary(task_root, store=store)
    tool_lookup: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for record in store.list_mcp_servers():
        for tool in record.get("tools") or []:
            ns_name = tool.get("namespaced_name")
            if isinstance(ns_name, str) and ns_name:
                tool_lookup[ns_name] = (record, tool)

    descriptors: list[dict[str, Any]] = []
    for tool_id in ids:
        found = tool_lookup.get(tool_id)
        if found is None:
            raise MCPLibraryError(
                "mcp_tool_not_found",
                f"Selected MCP tool '{tool_id}' was not found",
                dispatch_uncertain=False,
            )
        server_record, tool_record = found
        if not server_record.get("enabled", True):
            raise MCPLibraryError(
                "server_disabled",
                f"MCP server '{server_record['server_id']}' for tool '{tool_id}' is disabled",
                dispatch_uncertain=False,
            )
        if library._is_discovery_stale(server_record):
            raise MCPLibraryError(
                "discovery_stale",
                f"MCP server '{server_record['server_id']}' connection settings changed; test it before selecting '{tool_id}'",
                dispatch_uncertain=False,
            )
        if not tool_record.get("enabled", True):
            raise MCPLibraryError(
                "tool_disabled",
                f"Selected MCP tool '{tool_id}' is disabled",
                dispatch_uncertain=False,
            )
        status = server_record.get("status") or {}
        input_schema = deepcopy(tool_record.get("input_schema") or {"type": "object", "properties": {}})
        descriptors.append(
            {
                "namespaced_name": tool_record["namespaced_name"],
                "server_id": server_record["server_id"],
                "server_name": server_record["name"],
                "transport": server_record["transport"],
                "name": tool_record["name"],
                "title": tool_record.get("title") or tool_record["name"],
                "description": tool_record.get("description", ""),
                "annotations": dict(tool_record.get("annotations") or {}),
                "input_schema": input_schema,
                "schema_digest": tool_record.get("schema_digest") or mcp_schema_digest(input_schema),
                "endpoint_fingerprint": mcp_endpoint_fingerprint(server_record),
                "connection_fingerprint": status.get("tested_fingerprint", ""),
            }
        )
    return descriptors


def public_mcp_tools_catalog(task_root: Path, store: BusinessStore) -> list[dict[str, Any]]:
    library = MCPLibrary(task_root, store=store)
    items: list[dict[str, Any]] = []
    for server in library.catalog():
        for tool in server.get("tools", []):
            items.append(
                {
                    "namespaced_name": tool["namespaced_name"],
                    "name": tool["name"],
                    "title": tool.get("title") or tool["name"],
                    "description": tool.get("description", ""),
                    "annotations": dict(tool.get("annotations") or {}),
                    "enabled": True,
                    "server_id": server["server_id"],
                    "server_name": server["name"],
                    "transport": server["transport"],
                }
            )
    return items


def compact_task_view(task: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip bulky schemas and internal filesystem paths from public task config_snapshot views."""
    if task is None:
        return None
    view = dict(task)
    snapshot = view.get("config_snapshot")
    if not isinstance(snapshot, dict):
        return view
    compact_snapshot = dict(snapshot)
    if isinstance(compact_snapshot.get("skills"), list):
        compact_snapshot["skills"] = [
            {
                "skill_id": item["skill_id"],
                "version": item["version"],
                "name": item["name"],
                "description": item["description"],
                "bundle_digest": item.get("bundle_digest", ""),
                "allowed_tools": item.get("allowed_tools"),
                "compatibility": item.get("compatibility"),
                "metadata": dict(item.get("metadata") or {}),
                "file_count": item.get("file_count", 0),
                "total_bytes": item.get("total_bytes", 0),
            }
            for item in compact_snapshot["skills"]
            if isinstance(item, dict)
        ]
    if isinstance(compact_snapshot.get("mcp_tools"), list):
        compact_snapshot["mcp_tools"] = [
            {
                "namespaced_name": item["namespaced_name"],
                "server_id": item["server_id"],
                "server_name": item.get("server_name", item["server_id"]),
                "transport": item.get("transport", ""),
                "name": item["name"],
                "title": item.get("title") or item["name"],
                "description": item.get("description", ""),
                "annotations": dict(item.get("annotations") or {}),
                "schema_digest": item.get("schema_digest", ""),
            }
            for item in compact_snapshot["mcp_tools"]
            if isinstance(item, dict)
        ]
    view["config_snapshot"] = compact_snapshot
    return view


def validate_frozen_integrations(task_root: Path, snapshot: dict[str, Any], saved_snapshot: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    """Verify frozen skills, MCP tools, and agent capability flags against the saved task snapshot."""
    expected_skills = (saved_snapshot or {}).get("skills", [])
    expected_mcp = (saved_snapshot or {}).get("mcp_tools", [])
    if snapshot.get("skills", []) != expected_skills:
        raise ValueError("Task skills do not match the saved task")
    if snapshot.get("mcp_tools", []) != expected_mcp:
        raise ValueError("Task MCP tools do not match the saved task")
    if saved_snapshot is not None:
        req_profile = snapshot.get("agent_profile") if isinstance(snapshot.get("agent_profile"), dict) else {}
        saved_profile = saved_snapshot.get("agent_profile") if isinstance(saved_snapshot.get("agent_profile"), dict) else {}
        if req_profile != saved_profile:
            raise ValueError("Task agent configuration does not match the saved task")

    skills_root = (Path(task_root).resolve() / "skills").resolve()
    available_skills: list[dict[str, Any]] = []
    skill_roots: list[str] = []
    for item in expected_skills:
        if not isinstance(item, dict):
            raise ValueError("Invalid frozen skill descriptor")
        raw_bundle = item.get("bundle_path")
        raw_location = item.get("location")
        if not isinstance(raw_bundle, str) or not isinstance(raw_location, str):
            raise ValueError("Frozen skill descriptor is missing bundle path")
        bundle_path = Path(raw_bundle).resolve()
        location_path = Path(raw_location).resolve()
        if (
            not bundle_path.is_relative_to(skills_root)
            or bundle_path == skills_root
            or not location_path.is_relative_to(bundle_path)
            or location_path.name not in {"SKILL.md", "skill.md"}
        ):
            raise ValueError("Frozen skill path escapes managed storage")
        available_skills.append(
            {
                "name": item["name"],
                "description": item["description"],
                "location": str(location_path),
                **({"allowed_tools": item["allowed_tools"]} if item.get("allowed_tools") else {}),
                **({"compatibility": item["compatibility"]} if item.get("compatibility") else {}),
                **({"metadata": dict(item["metadata"])} if item.get("metadata") else {}),
            }
        )
        skill_roots.append(str(bundle_path))
    return available_skills, skill_roots


def render_frozen_skills_prompt(snapshot: dict[str, Any]) -> str:
    skills = snapshot.get("skills") or []
    if not skills:
        return ""
    entries = [
        SkillEntry(
            name=item["name"],
            description=item["description"],
            location=item.get("location"),
        )
        for item in skills
        if isinstance(item, dict) and item.get("name") and item.get("description")
    ]
    if not entries:
        return ""
    return SKILL_RUNTIME_HEADER + render_skills_xml(entries)
