"""MCP server library, secret-preserving storage, schema validation, and official SDK transports."""
from __future__ import annotations

import asyncio
import base64
import binascii
from contextlib import asynccontextmanager
from copy import deepcopy
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import threading
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import anyio
import httpx2
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from mcp.client.client import Client
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
import mcp_types as types
from vv_agent import FunctionTool
from vv_agent.tools.argument_validation import assert_valid_tool_schema, validate_tool_arguments
from vv_agent.tools.metadata import ToolMetadata
from vv_agent.tools.registry import ToolNotFoundError, ToolRegistry

from .service import TaskConflict, required_id
from .store import BusinessStore, now

TRANSPORTS = {"stdio", "streamable_http", "sse"}
DEFAULT_TIMEOUT_SECONDS = 30.0
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 300.0
MAX_SERVER_NAME_LEN = 160
MAX_SERVER_DESC_LEN = 2000
MAX_COMMAND_LEN = 1024
MAX_ARGS_COUNT = 64
MAX_ARG_LEN = 2048
MAX_URL_LEN = 2048
MAX_ENV_COUNT = 64
MAX_HEADERS_COUNT = 64
MAX_SECRET_KEY_LEN = 128
MAX_SECRET_VALUE_LEN = 8192
MAX_DISCOVERED_TOOLS = 128
MAX_DISCOVERY_PAGES = 32
MAX_TOOL_SCHEMA_BYTES = 64 * 1024
MAX_TOTAL_SCHEMA_BYTES = 1024 * 1024
MAX_TOOL_NAME_LEN = 128
MAX_TOOL_DESC_LEN = 4096
MAX_CALL_CONTENT_BYTES = 256 * 1024
MAX_INTERNAL_MEDIA_BYTES = 5 * 1024 * 1024

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_HEADER_KEY_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]{1,128}$")
_FORBIDDEN_HEADERS = {"host", "content-length", "transfer-encoding", "connection"}
_SAFE_IDENT_RE = re.compile(r"[^a-z0-9]+")
_MCP_LOGGER_PREFIXES = (
    "mcp",
    "client",
    "httpx",
    "httpx2",
    "httpcore",
    "httpcore2",
)


class MCPLibraryError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        dispatch_uncertain: bool = False,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.dispatch_uncertain = dispatch_uncertain
        self.details = dict(details or {})
        super().__init__(message)


def _has_control_chars(value: str, *, allow_newlines: bool = False) -> bool:
    for ch in value:
        code = ord(ch)
        if code == 0 or code == 127:
            return True
        if code < 32 and (not allow_newlines or ch not in "\r\n\t"):
            return True
    return False


def _validate_url(raw_url: str) -> tuple[str, str, list[str]]:
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise MCPLibraryError("invalid_url", "Server URL is required")
    url = raw_url.strip()
    if len(url) > MAX_URL_LEN or _has_control_chars(url) or any(ch.isspace() for ch in url):
        raise MCPLibraryError("invalid_url", "Server URL contains invalid characters or exceeds maximum length")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise MCPLibraryError("invalid_url", "Server URL is malformed") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise MCPLibraryError("invalid_url", "Server URL must be an http or https URL")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise MCPLibraryError(
            "url_userinfo_forbidden",
            "URL userinfo is not allowed; configure credentials via headers or query parameters",
        )
    if parsed.fragment:
        raise MCPLibraryError("invalid_url", "Server URL must not include a URL fragment")
    del port

    query_secrets: list[str] = []
    masked_pairs: list[tuple[str, str]] = []
    if parsed.query:
        for key, val in parse_qsl(parsed.query, keep_blank_values=True):
            if val:
                query_secrets.append(val)
                unquoted = unquote(val)
                if unquoted and unquoted != val:
                    query_secrets.append(unquoted)
            masked_pairs.append((key, "***" if val else ""))
        masked_query = urlencode(masked_pairs, doseq=True)
    else:
        masked_query = ""
    display_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, masked_query, ""))
    return url, display_url, query_secrets


def _secret_candidates(secrets: dict[str, Any], *, extra_secrets: list[str] | None = None) -> list[str]:
    values: set[str] = set()
    for mapping_key in ("env", "headers"):
        mapping = secrets.get(mapping_key)
        if isinstance(mapping, dict):
            for raw_val in mapping.values():
                if isinstance(raw_val, str) and raw_val.strip():
                    val = raw_val.strip()
                    values.add(val)
                    if val.lower().startswith(("bearer ", "basic ")):
                        token = val.split(" ", 1)[1].strip()
                        if token:
                            values.add(token)
    raw_url = secrets.get("url")
    if isinstance(raw_url, str) and raw_url.strip():
        try:
            _, _, query_vals = _validate_url(raw_url)
            for item in query_vals:
                if item:
                    values.add(item)
        except MCPLibraryError:
            pass
    for item in extra_secrets or []:
        if isinstance(item, str) and item.strip():
            values.add(item.strip())
    return sorted((v for v in values if len(v) >= 2), key=len, reverse=True)


def _contains_secret(value: Any, secret_list: list[str]) -> bool:
    if not secret_list:
        return False
    if isinstance(value, str):
        return any(secret in value for secret in secret_list)
    if isinstance(value, list):
        return any(_contains_secret(item, secret_list) for item in value)
    if isinstance(value, dict):
        return any(
            _contains_secret(str(k), secret_list) or _contains_secret(v, secret_list)
            for k, v in value.items()
        )
    return False


def redact_mcp_text(text: Any, secrets: dict[str, Any] | None = None, *, extra_secrets: list[str] | None = None) -> str:
    raw = str(text or "")
    for secret in _secret_candidates(secrets or {}, extra_secrets=extra_secrets):
        raw = raw.replace(secret, "[REDACTED]")
    raw = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", raw, flags=re.I)
    raw = re.sub(r"\b(Bearer|Basic)\s+[^\s,'\"}\]]+", r"\1 [REDACTED]", raw, flags=re.I)
    raw = re.sub(
        r"([?&](?:api[_-]?key|token|access[_-]?token|auth|key|secret|password|sig|signature)=)[^&#\s\"']+",
        r"\1[REDACTED]",
        raw,
        flags=re.I,
    )
    return raw[:1500]


def redact_mcp_value(value: Any, secrets: dict[str, Any] | None = None, *, extra_secrets: list[str] | None = None) -> Any:
    if isinstance(value, str):
        result = value
        for secret in _secret_candidates(secrets or {}, extra_secrets=extra_secrets):
            result = result.replace(secret, "[REDACTED]")
        result = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", result, flags=re.I)
        result = re.sub(r"\b(Bearer|Basic)\s+[^\s,'\"}\]]+", r"\1 [REDACTED]", result, flags=re.I)
        return result
    if isinstance(value, list):
        return [redact_mcp_value(item, secrets, extra_secrets=extra_secrets) for item in value]
    if isinstance(value, dict):
        return {
            redact_mcp_value(str(k), secrets, extra_secrets=extra_secrets): redact_mcp_value(v, secrets, extra_secrets=extra_secrets)
            for k, v in value.items()
        }
    return value


_LOG_GUARD_LOCK = threading.RLock()
_ACTIVE_LOG_SECRETS: dict[int, dict[str, Any]] = {}
_NEXT_LOG_SCOPE_ID = 0
_GUARDED_LOG_HANDLERS: set[logging.Handler] = set()


class _ActiveCredentialFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        with _LOG_GUARD_LOCK:
            active = tuple(_ACTIVE_LOG_SECRETS.values())
        candidates = {value for config in active for value in _secret_candidates(config)}
        if not candidates:
            return True
        try:
            message = record.getMessage()
            redacted = redact_mcp_text(message, extra_secrets=list(candidates))
            if redacted != message:
                record.msg, record.args = redacted, ()
            if record.exc_info:
                import traceback
                trace = ''.join(traceback.format_exception(*record.exc_info))
                safe_trace = redact_mcp_text(trace, extra_secrets=list(candidates))
                if safe_trace != trace:
                    record.exc_info, record.exc_text = None, safe_trace
            if record.exc_text:
                record.exc_text = redact_mcp_text(record.exc_text, extra_secrets=list(candidates))
        except Exception:
            return False
        return True


_ACTIVE_CREDENTIAL_FILTER = _ActiveCredentialFilter()


@asynccontextmanager
async def _quiet_mcp_loggers(secrets: dict[str, Any] | None = None):
    """Protect transport namespaces and active credentials through public logging APIs."""
    global _NEXT_LOG_SCOPE_ID
    with _LOG_GUARD_LOCK:
        _NEXT_LOG_SCOPE_ID += 1
        scope_id = _NEXT_LOG_SCOPE_ID
        _ACTIVE_LOG_SECRETS[scope_id] = deepcopy(secrets or {})
        handlers = [*logging.getLogger().handlers, logging.lastResort]
        for prefix in _MCP_LOGGER_PREFIXES:
            logger = logging.getLogger(prefix)
            # Transport diagnostics can include authentication data before our error mapping.
            # Stop propagation at these SDK namespaces, including records from child loggers.
            if not any(isinstance(handler, logging.NullHandler) for handler in logger.handlers):
                logger.addHandler(logging.NullHandler())
            logger.propagate = False
            handlers.extend(logger.handlers)
        for handler in handlers:
            if handler is not None and handler not in _GUARDED_LOG_HANDLERS:
                handler.addFilter(_ACTIVE_CREDENTIAL_FILTER)
                _GUARDED_LOG_HANDLERS.add(handler)
    try:
        yield
    finally:
        with _LOG_GUARD_LOCK:
            _ACTIVE_LOG_SECRETS.pop(scope_id, None)
            if not _ACTIVE_LOG_SECRETS:
                for handler in _GUARDED_LOG_HANDLERS:
                    handler.removeFilter(_ACTIVE_CREDENTIAL_FILTER)
                _GUARDED_LOG_HANDLERS.clear()


def _check_no_external_refs(node: Any) -> None:
    if not isinstance(node, dict):
        return
    for key in ("$ref", "$dynamicRef"):
        value = node.get(key)
        if value is not None and (not isinstance(value, str) or not value.startswith("#")):
            raise MCPLibraryError(
                "external_schema_ref_forbidden",
                "External schema references are not allowed",
            )
    # Traverse schema positions, not property names or literal const/default/example data.
    for key in ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas"):
        children = node.get(key)
        if isinstance(children, dict):
            for child in children.values():
                _check_no_external_refs(child)
    for key in (
        "additionalProperties", "unevaluatedProperties", "propertyNames", "items",
        "additionalItems", "unevaluatedItems", "contains", "not", "if", "then", "else",
        "contentSchema",
    ):
        _check_no_external_refs(node.get(key))
    for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
        children = node.get(key)
        if isinstance(children, list):
            for child in children:
                _check_no_external_refs(child)
    dependencies = node.get("dependencies")
    if isinstance(dependencies, dict):
        for child in dependencies.values():
            _check_no_external_refs(child)


def validate_mcp_input_schema(schema: Any, *, secrets: dict[str, Any] | None = None) -> tuple[dict[str, Any], int]:
    if not isinstance(schema, dict):
        raise MCPLibraryError("invalid_tool_schema", "Tool inputSchema must be a JSON object")
    if schema.get("type") != "object":
        raise MCPLibraryError("invalid_tool_schema", "Tool inputSchema root must have type 'object'")
    _check_no_external_refs(schema)
    secret_list = _secret_candidates(secrets or {})
    if secret_list and _contains_secret(schema, secret_list):
        raise MCPLibraryError(
            "secret_in_tool_schema",
            "Discovered tool schema contains a configured secret value and was rejected",
        )
    normalized = deepcopy(schema)
    if "properties" in normalized and not isinstance(normalized["properties"], dict):
        raise MCPLibraryError("invalid_tool_schema", "Tool inputSchema 'properties' must be an object")
    normalized.setdefault("properties", {})
    if "required" in normalized:
        req = normalized["required"]
        if not isinstance(req, list) or not all(isinstance(item, str) for item in req):
            raise MCPLibraryError("invalid_tool_schema", "Tool inputSchema 'required' must be a list of strings")
    try:
        serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise MCPLibraryError("invalid_tool_schema", "Tool inputSchema is not JSON serializable") from exc
    byte_len = len(serialized.encode("utf-8"))
    if byte_len > MAX_TOOL_SCHEMA_BYTES:
        raise MCPLibraryError("tool_schema_too_large", f"Tool inputSchema exceeds {MAX_TOOL_SCHEMA_BYTES} bytes")
    try:
        Draft202012Validator.check_schema(normalized)
        assert_valid_tool_schema(normalized)
    except (SchemaError, Exception) as exc:
        raise MCPLibraryError("invalid_tool_schema", "Tool inputSchema failed JSON Schema 2020-12 validation") from exc
    return normalized, byte_len


def namespace_mcp_tool_name(server_id: str, remote_tool_name: str, used_names: set[str] | None = None) -> str:
    """Deterministically generate a <=64-char model-facing tool name from exact case-sensitive identity."""
    if not isinstance(server_id, str) or not server_id or not isinstance(remote_tool_name, str) or not remote_tool_name:
        raise MCPLibraryError("invalid_tool_name", "Server ID and tool name are required")
    clean_server = _SAFE_IDENT_RE.sub("_", server_id.lower()).strip("_") or "srv"
    clean_tool = _SAFE_IDENT_RE.sub("_", remote_tool_name.lower()).strip("_") or "tool"
    s_part = clean_server[:18].rstrip("_") or "srv"
    t_part = clean_tool[:24].rstrip("_") or "tool"
    digest = hashlib.sha256(f"{len(server_id)}:{server_id}\0{len(remote_tool_name)}:{remote_tool_name}".encode("utf-8")).hexdigest()[:12]
    candidate = f"mcp__{s_part}__{t_part}__{digest}"
    assert len(candidate) <= 64
    if used_names is not None:
        if candidate in used_names:
            raise MCPLibraryError("tool_namespace_collision", "Deterministic MCP tool namespace collision detected")
        used_names.add(candidate)
    return candidate


class MCPToolRegistry(ToolRegistry):
    """ToolRegistry subclass that preserves open-object JSON Schemas for MCP tools via public APIs."""

    def get_schema(self, name: str) -> dict[str, Any]:
        try:
            executor = self.get_executor(name)
        except ToolNotFoundError:
            return super().get_schema(name)
        if isinstance(getattr(executor, "metadata", None), dict) and executor.metadata.get("preserve_open_schema") is True:
            return deepcopy(executor.openai_schema(None))
        return super().get_schema(name)


def build_mcp_function_tool(
    tool_descriptor: dict[str, Any],
    on_invoke: Any,
    *,
    needs_approval: bool = True,
    timeout_seconds: float | None = None,
) -> FunctionTool:
    """Build a vv-agent FunctionTool while preserving open-object JSON Schema semantics."""
    preserved_schema = deepcopy(tool_descriptor["input_schema"])
    validate_mcp_input_schema(preserved_schema)
    fn_tool = FunctionTool(
        name=tool_descriptor["namespaced_name"],
        description=tool_descriptor.get("description") or f"MCP tool {tool_descriptor['name']}",
        params_json_schema=deepcopy(preserved_schema),
        on_invoke=on_invoke,
        strict_json_schema=False,
        needs_approval=needs_approval,
        timeout_seconds=timeout_seconds,
        tool_metadata=ToolMetadata(side_effect="external", idempotency="unknown"),
        metadata={
            "server_id": tool_descriptor["server_id"],
            "remote_tool_name": tool_descriptor["name"],
            "title": tool_descriptor.get("title") or tool_descriptor["name"],
            "preserve_open_schema": True,
        },
    )
    fn_tool.params_json_schema = preserved_schema
    return fn_tool


_FIXED_ERROR_MESSAGES = {
    "authentication_failed": "MCP server rejected authentication credentials",
    "timeout": "MCP server operation timed out",
    "executable_not_found": "Configured MCP server executable or working directory was not found",
    "connection_failed": "Could not connect to the MCP server",
    "protocol_error": "MCP server returned a protocol or execution error",
}


def _classify_transport_error(
    exc: BaseException,
    *,
    secrets: dict[str, Any] | None = None,
    dispatched: bool = False,
    last_http_status: int | None = None,
) -> MCPLibraryError:
    del secrets
    if isinstance(exc, MCPLibraryError):
        return exc
    current: BaseException | None = exc
    seen: set[int] = set()
    http_status: int | None = None
    is_timeout = False
    is_not_found = False
    is_connect = False

    while current is not None and id(current) not in seen and len(seen) < 16:
        seen.add(id(current))
        if isinstance(current, BaseExceptionGroup):
            for sub in current.exceptions:
                classified = _classify_transport_error(
                    sub,
                    dispatched=dispatched,
                    last_http_status=last_http_status,
                )
                if classified.code != "connection_failed":
                    return classified
        if isinstance(current, (TimeoutError, asyncio.TimeoutError, httpx2.TimeoutException)):
            is_timeout = True
        elif isinstance(current, FileNotFoundError):
            is_not_found = True
        elif isinstance(current, httpx2.HTTPStatusError):
            http_status = current.response.status_code
        elif isinstance(current, MCPError):
            msg_low = str(current).lower()
            if "401" in msg_low or "403" in msg_low or "unauthorized" in msg_low or "forbidden" in msg_low:
                http_status = 401
        elif isinstance(current, (httpx2.TransportError, ConnectionError, OSError)):
            is_connect = True
        current = current.__cause__ or (current.__context__ if not getattr(current, "__suppress_context__", False) else None)

    effective_status = http_status or last_http_status
    if effective_status in {401, 403}:
        return MCPLibraryError(
            "authentication_failed",
            _FIXED_ERROR_MESSAGES["authentication_failed"],
            dispatch_uncertain=dispatched,
        )
    if is_timeout:
        return MCPLibraryError(
            "timeout",
            _FIXED_ERROR_MESSAGES["timeout"],
            dispatch_uncertain=dispatched,
        )
    if is_not_found and not dispatched:
        return MCPLibraryError(
            "executable_not_found",
            _FIXED_ERROR_MESSAGES["executable_not_found"],
            dispatch_uncertain=False,
        )
    if is_connect:
        return MCPLibraryError(
            "connection_failed",
            _FIXED_ERROR_MESSAGES["connection_failed"],
            dispatch_uncertain=dispatched,
        )
    return MCPLibraryError(
        "protocol_error",
        _FIXED_ERROR_MESSAGES["protocol_error"],
        dispatch_uncertain=dispatched,
    )


def _connection_fingerprint(transport: str, config: dict[str, Any], secrets: dict[str, Any]) -> str:
    payload = {
        "transport": transport,
        "command": config.get("command") if transport == "stdio" else None,
        "args": config.get("args") if transport == "stdio" else None,
        "cwd": config.get("cwd") if transport == "stdio" else None,
        "env": secrets.get("env") if transport == "stdio" else None,
        "url": secrets.get("url") if transport != "stdio" else None,
        "headers": secrets.get("headers") if transport != "stdio" else None,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@asynccontextmanager
async def open_mcp_client(record: dict[str, Any], *, status_tracker: list[int] | None = None):
    """Open an official MCP v2 Client over stdio, streamable_http, or sse with owned cleanup."""
    transport_kind = record["transport"]
    config = record.get("config") or {}
    secrets = record.get("secrets") or {}
    timeout = float(config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)

    async def _on_response(response: httpx2.Response) -> None:
        if status_tracker is not None and response.status_code >= 400:
            status_tracker.append(response.status_code)

    event_hooks = {"response": [_on_response]} if status_tracker is not None else None

    async with _quiet_mcp_loggers(secrets):
        if transport_kind == "stdio":
            command = config.get("command", "")
            args = list(config.get("args") or [])
            cwd = config.get("cwd") or None
            if cwd is not None:
                cwd_path = Path(cwd)
                if not cwd_path.is_dir():
                    raise MCPLibraryError("executable_not_found", _FIXED_ERROR_MESSAGES["executable_not_found"])
            env_vars = dict(secrets.get("env") or {})
            params = StdioServerParameters(
                command=command,
                args=args,
                env=env_vars,
                cwd=cwd,
            )
            with open(os.devnull, "w", encoding="utf-8") as errlog:
                transport_cm = stdio_client(params, errlog=errlog)
                client = Client(
                    transport_cm,
                    read_timeout_seconds=timeout,
                    cache=None,
                )
                async with client:
                    yield client
        elif transport_kind == "streamable_http":
            url = secrets.get("url") or ""
            if not url:
                raise MCPLibraryError("invalid_url", "Server URL is not configured")
            headers = dict(secrets.get("headers") or {})
            http_timeout = httpx2.Timeout(timeout, read=timeout)
            async with httpx2.AsyncClient(
                headers=headers,
                timeout=http_timeout,
                trust_env=False,
                event_hooks=event_hooks,
            ) as http_client:
                transport_cm = streamable_http_client(url, http_client=http_client)
                client = Client(
                    transport_cm,
                    read_timeout_seconds=timeout,
                    cache=None,
                )
                async with client:
                    yield client
        elif transport_kind == "sse":
            url = secrets.get("url") or ""
            if not url:
                raise MCPLibraryError("invalid_url", "Server URL is not configured")
            headers = dict(secrets.get("headers") or {})

            def client_factory(
                headers: dict[str, str] | None = None,
                timeout: httpx2.Timeout | None = None,
                auth: httpx2.Auth | None = None,
            ) -> httpx2.AsyncClient:
                return httpx2.AsyncClient(
                    headers=headers,
                    timeout=timeout or httpx2.Timeout(timeout),
                    auth=auth,
                    trust_env=False,
                    event_hooks=event_hooks,
                )

            transport_cm = sse_client(
                url,
                headers=headers,
                timeout=timeout,
                sse_read_timeout=timeout,
                httpx_client_factory=client_factory,
            )
            client = Client(
                transport_cm,
                read_timeout_seconds=timeout,
                cache=None,
            )
            async with client:
                yield client
        else:
            raise MCPLibraryError("invalid_transport", f"Unsupported MCP transport: {transport_kind}")


async def discover_mcp_server_tools_async(
    record: dict[str, Any],
    *,
    previous_tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Connect to the MCP server, negotiate protocol, and list all tools with pagination/schema limits."""
    server_id = record["server_id"]
    config = record.get("config") or {}
    secrets = record.get("secrets") or {}
    secret_list = _secret_candidates(secrets)
    timeout = float(config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
    previous_enabled = {
        item["name"]: bool(item.get("enabled", True))
        for item in (previous_tools or record.get("tools") or [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }

    status_tracker: list[int] = []
    try:
        with anyio.fail_after(timeout):
            async with open_mcp_client(record, status_tracker=status_tracker) as client:
                seen_cursors: set[str] = set()
                seen_raw_names: set[str] = set()
                used_namespaced: set[str] = set()
                discovered: list[dict[str, Any]] = []
                total_schema_bytes = 0
                cursor: str | None = None
                pages = 0

                while True:
                    pages += 1
                    if pages > MAX_DISCOVERY_PAGES:
                        raise MCPLibraryError(
                            "pagination_limit_exceeded",
                            f"MCP tool discovery exceeded {MAX_DISCOVERY_PAGES} pages",
                        )
                    page = await client.list_tools(cursor=cursor, cache_mode="bypass")
                    for tool in page.tools:
                        raw_name = getattr(tool, "name", "")
                        if not isinstance(raw_name, str) or not raw_name.strip() or len(raw_name) > MAX_TOOL_NAME_LEN or _has_control_chars(raw_name):
                            raise MCPLibraryError("invalid_tool_name", "Discovered tool has an invalid or overly long name")
                        raw_name = raw_name.strip()
                        if secret_list and _contains_secret(raw_name, secret_list):
                            raise MCPLibraryError(
                                "secret_in_tool_name",
                                "Discovered tool name contains a configured secret value and was rejected",
                            )
                        if raw_name in seen_raw_names:
                            raise MCPLibraryError("duplicate_tool_name", f"Duplicate tool name returned by server: {raw_name}")
                        seen_raw_names.add(raw_name)
                        if len(discovered) + 1 > MAX_DISCOVERED_TOOLS:
                            raise MCPLibraryError(
                                "too_many_tools",
                                f"MCP server returned more than {MAX_DISCOVERED_TOOLS} tools",
                            )
                        raw_schema = getattr(tool, "input_schema", None)
                        validated_schema, schema_bytes = validate_mcp_input_schema(raw_schema, secrets=secrets)
                        total_schema_bytes += schema_bytes
                        if total_schema_bytes > MAX_TOTAL_SCHEMA_BYTES:
                            raise MCPLibraryError(
                                "tool_schema_too_large",
                                f"Total tool schemas exceed {MAX_TOTAL_SCHEMA_BYTES} bytes",
                            )
                        raw_desc = getattr(tool, "description", None) or ""
                        if not isinstance(raw_desc, str):
                            raw_desc = str(raw_desc)
                        if len(raw_desc.encode("utf-8")) > MAX_TOOL_DESC_LEN * 4:
                            raise MCPLibraryError("tool_metadata_too_large", f"Tool '{raw_name}' description exceeds limit")
                        description = redact_mcp_value(raw_desc[:MAX_TOOL_DESC_LEN], secrets)

                        annotations = getattr(tool, "annotations", None)
                        title = (
                            getattr(tool, "title", None)
                            or (getattr(annotations, "title", None) if annotations is not None else None)
                            or raw_name
                        )
                        title = redact_mcp_value(str(title)[:256], secrets)
                        annotations_dict: dict[str, Any] = {}
                        if annotations is not None:
                            for hint_key in ("read_only_hint", "destructive_hint", "idempotent_hint", "open_world_hint"):
                                hint_val = getattr(annotations, hint_key, None)
                                if isinstance(hint_val, bool):
                                    annotations_dict[hint_key] = hint_val

                        namespaced = namespace_mcp_tool_name(server_id, raw_name, used_namespaced)
                        discovered.append(
                            {
                                "name": raw_name,
                                "namespaced_name": namespaced,
                                "title": title,
                                "description": description,
                                "input_schema": validated_schema,
                                "annotations": annotations_dict,
                                "enabled": previous_enabled.get(raw_name, True),
                            }
                        )

                    next_cursor = page.next_cursor
                    if not next_cursor:
                        break
                    if not isinstance(next_cursor, str) or len(next_cursor) > 1024 or next_cursor in seen_cursors:
                        raise MCPLibraryError("invalid_pagination_cursor", "MCP server returned a repeating or invalid pagination cursor")
                    seen_cursors.add(next_cursor)
                    cursor = next_cursor

                server_info = client.server_info
                return {
                    "protocol_version": client.protocol_version,
                    "server_info": (
                        {
                            "name": redact_mcp_text(getattr(server_info, "name", ""), secrets)[:160],
                            "version": redact_mcp_text(getattr(server_info, "version", ""), secrets)[:80],
                        }
                        if server_info is not None
                        else None
                    ),
                    "tools": discovered,
                }
    except BaseException as exc:
        raise _classify_transport_error(
            exc,
            secrets=secrets,
            dispatched=False,
            last_http_status=status_tracker[-1] if status_tracker else None,
        ) from None


def _decode_bounded_base64(raw_b64: str, max_bytes: int) -> tuple[bytes | None, int]:
    if not isinstance(raw_b64, str) or not raw_b64.strip():
        return b"", 0
    compact = "".join(raw_b64.split())
    estimated_bytes = (len(compact) * 3) // 4
    if estimated_bytes > max_bytes:
        return None, estimated_bytes
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError):
        return None, estimated_bytes
    if len(decoded) > max_bytes:
        return None, len(decoded)
    return decoded, len(decoded)


def _format_call_tool_result(
    result: types.CallToolResult,
    secrets: dict[str, Any] | None = None,
    *,
    include_internal_media: bool = False,
) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    internal_media: list[dict[str, Any]] = []
    text_parts: list[str] = []
    total_bytes = 0
    total_media_bytes = 0
    truncated = False

    for item in getattr(result, "content", None) or []:
        block_type = getattr(item, "type", "")
        if block_type == "text":
            raw_text = redact_mcp_value(str(getattr(item, "text", "")), secrets)
            encoded = raw_text.encode("utf-8", errors="replace")
            remaining = MAX_CALL_CONTENT_BYTES - total_bytes
            if remaining <= 0:
                truncated = True
                break
            if len(encoded) > remaining:
                raw_text = encoded[:remaining].decode("utf-8", errors="replace")
                truncated = True
                total_bytes += remaining
            else:
                total_bytes += len(encoded)
            blocks.append({"type": "text", "text": raw_text})
            text_parts.append(raw_text)
        elif block_type in {"image", "audio"}:
            mime_type = redact_mcp_text(getattr(item, "mime_type", None) or getattr(item, "mimeType", ""), secrets)[:128]
            raw_data = str(getattr(item, "data", "") or "")
            decoded, byte_len = _decode_bounded_base64(raw_data, MAX_INTERNAL_MEDIA_BYTES - total_media_bytes)
            retained = decoded is not None and len(decoded) > 0
            if retained and decoded is not None:
                total_media_bytes += len(decoded)
                if include_internal_media:
                    internal_media.append(
                        {
                            "kind": block_type,
                            "mime_type": mime_type,
                            "byte_length": len(decoded),
                            "sha256": hashlib.sha256(decoded).hexdigest(),
                            "data_base64": base64.b64encode(decoded).decode("ascii"),
                        }
                    )
            else:
                if byte_len > 0:
                    truncated = True
            blocks.append(
                {
                    "type": block_type,
                    "mime_type": mime_type,
                    "byte_length": byte_len,
                    "retained": retained,
                    "omitted": not retained,
                }
            )
        elif block_type == "resource_link":
            uri = redact_mcp_text(getattr(item, "uri", ""), secrets)[:512]
            name = redact_mcp_text(getattr(item, "name", ""), secrets)[:256]
            blocks.append({"type": "resource_link", "uri": uri, "name": name, "fetched": False})
        elif block_type == "resource":
            resource = getattr(item, "resource", None)
            uri = redact_mcp_text(getattr(resource, "uri", ""), secrets)[:512] if resource else ""
            mime_type = redact_mcp_text(
                (getattr(resource, "mime_type", None) or getattr(resource, "mimeType", "")) if resource else "",
                secrets,
            )[:128]
            res_text = getattr(resource, "text", None) if resource else None
            res_blob = getattr(resource, "blob", None) if resource else None
            if isinstance(res_text, str):
                clean_text = redact_mcp_value(res_text, secrets)
                encoded = clean_text.encode("utf-8", errors="replace")
                remaining = MAX_CALL_CONTENT_BYTES - total_bytes
                if remaining <= 0:
                    truncated = True
                    break
                if len(encoded) > remaining:
                    clean_text = encoded[:remaining].decode("utf-8", errors="replace")
                    truncated = True
                    total_bytes += remaining
                else:
                    total_bytes += len(encoded)
                blocks.append({"type": "resource", "uri": uri, "mime_type": mime_type, "text": clean_text})
                text_parts.append(clean_text)
            elif isinstance(res_blob, str) and res_blob:
                decoded, byte_len = _decode_bounded_base64(res_blob, MAX_INTERNAL_MEDIA_BYTES - total_media_bytes)
                retained = decoded is not None and len(decoded) > 0
                if retained and decoded is not None:
                    total_media_bytes += len(decoded)
                    if include_internal_media:
                        internal_media.append(
                            {
                                "kind": "resource_blob",
                                "uri": uri,
                                "mime_type": mime_type,
                                "byte_length": len(decoded),
                                "sha256": hashlib.sha256(decoded).hexdigest(),
                                "data_base64": base64.b64encode(decoded).decode("ascii"),
                            }
                        )
                else:
                    if byte_len > 0:
                        truncated = True
                blocks.append(
                    {
                        "type": "resource",
                        "uri": uri,
                        "mime_type": mime_type,
                        "byte_length": byte_len,
                        "retained": retained,
                        "omitted_binary": not retained,
                    }
                )
            else:
                blocks.append({"type": "resource", "uri": uri, "omitted_binary": True})
        else:
            blocks.append({"type": str(block_type or "unknown")[:64]})

    structured = getattr(result, "structured_content", None)
    if structured is not None:
        redacted_structured = redact_mcp_value(structured, secrets)
        try:
            serialized_struct = json.dumps(redacted_struct := redacted_structured, ensure_ascii=False)
            if len(serialized_struct.encode("utf-8")) > MAX_CALL_CONTENT_BYTES:
                redacted_struct = None
                truncated = True
        except (TypeError, ValueError):
            redacted_struct = None
    else:
        redacted_struct = None

    formatted: dict[str, Any] = {
        "is_error": bool(getattr(result, "is_error", False)),
        "text": "\n".join(text_parts),
        "content": blocks,
        "structured_content": redacted_struct,
        "truncated": truncated,
    }
    if include_internal_media:
        formatted["internal_media"] = internal_media
    return formatted


async def call_mcp_server_tool_async(
    record: dict[str, Any],
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    timeout_seconds: float | None = None,
    on_dispatched: Any = None,
    include_internal_media: bool = False,
) -> dict[str, Any]:
    """Connect and invoke one tool on the MCP server, tracking pre-dispatch vs post-dispatch failures."""
    if not isinstance(tool_name, str) or not tool_name.strip() or len(tool_name) > MAX_TOOL_NAME_LEN or _has_control_chars(tool_name):
        raise MCPLibraryError("invalid_tool_name", "Tool name is required")
    if arguments is not None and not isinstance(arguments, dict):
        raise MCPLibraryError("invalid_tool_arguments", "Tool arguments must be a JSON object")

    config = record.get("config") or {}
    secrets = record.get("secrets") or {}
    timeout = float(timeout_seconds or config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
    dispatched = False
    status_tracker: list[int] = []

    try:
        with anyio.fail_after(timeout):
            async with open_mcp_client(record, status_tracker=status_tracker) as client:
                dispatched = True
                if callable(on_dispatched):
                    on_dispatched()
                with anyio.fail_after(timeout):
                    raw_result = await client.call_tool(
                        tool_name.strip(),
                        dict(arguments or {}),
                        read_timeout_seconds=timeout,
                    )
                return _format_call_tool_result(
                    raw_result,
                    secrets,
                    include_internal_media=include_internal_media,
                )
    except BaseException as exc:
        raise _classify_transport_error(
            exc,
            secrets=secrets,
            dispatched=dispatched,
            last_http_status=status_tracker[-1] if status_tracker else None,
        ) from None


def _validate_secret_keys(
    existing: dict[str, str],
    incoming: Any,
    clear_keys: Any,
    *,
    key_pattern: re.Pattern[str],
    max_count: int,
    label: str,
    lower_forbidden: set[str] | None = None,
    case_insensitive: bool = False,
) -> dict[str, str]:
    merged = dict(existing)
    if clear_keys is not None:
        if not isinstance(clear_keys, list) or not all(isinstance(k, str) for k in clear_keys):
            raise MCPLibraryError(f"invalid_{label}", f"clear_{label}_keys must be a list of strings")
        for key in clear_keys:
            trimmed = key.strip()
            merged.pop(trimmed, None)
            if case_insensitive or lower_forbidden is not None:
                for existing_k in [k for k in merged if k.lower() == trimmed.lower()]:
                    merged.pop(existing_k, None)

    if incoming is not None:
        if not isinstance(incoming, dict):
            raise MCPLibraryError(f"invalid_{label}", f"{label} must be a key-value object")
        for raw_k, raw_v in incoming.items():
            if not isinstance(raw_k, str) or not raw_k.strip():
                raise MCPLibraryError(f"invalid_{label}", f"{label} key must be a non-empty string")
            key = raw_k.strip()
            if len(key) > MAX_SECRET_KEY_LEN or not key_pattern.fullmatch(key) or _has_control_chars(key):
                raise MCPLibraryError(f"invalid_{label}", f"Invalid {label} key: {key!r}")
            if lower_forbidden is not None and key.lower() in lower_forbidden:
                raise MCPLibraryError(f"invalid_{label}", f"Header {key!r} is managed by the transport and cannot be overridden")
            if raw_v is None or raw_v == "":
                # Blank or null in incoming edit leaves existing saved secret intact; use clear_*_keys to remove.
                continue
            if not isinstance(raw_v, str):
                raise MCPLibraryError(f"invalid_{label}", f"{label} value for {key!r} must be a string")
            if len(raw_v) > MAX_SECRET_VALUE_LEN or _has_control_chars(raw_v):
                raise MCPLibraryError(f"invalid_{label}", f"{label} value for {key!r} is invalid or exceeds length limit")
            if case_insensitive or lower_forbidden is not None:
                for existing_k in [k for k in merged if k.lower() == key.lower() and k != key]:
                    merged.pop(existing_k, None)
            merged[key] = raw_v

    if len(merged) > max_count:
        raise MCPLibraryError(f"invalid_{label}", f"At most {max_count} {label} entries are allowed")
    return merged


class MCPLibrary:
    """Manage local MCP server configurations, secret-preserving edits, and official SDK discovery."""

    def __init__(self, task_root: Path, *, store: BusinessStore | None = None):
        self.task_root = Path(task_root).resolve()
        self.task_root.mkdir(parents=True, exist_ok=True)
        self.store = store or BusinessStore(self.task_root / "tasks.db")

    @staticmethod
    def _is_discovery_stale(record: dict[str, Any]) -> bool:
        status = record.get("status") or {}
        if status.get("stale") is True:
            return True
        tested_fp = status.get("tested_fingerprint")
        if not tested_fp:
            return bool(record.get("tools"))
        current_fp = _connection_fingerprint(record["transport"], record.get("config") or {}, record.get("secrets") or {})
        return tested_fp != current_fp

    def list(self, search: str = "") -> list[dict[str, Any]]:
        if not isinstance(search, str) or len(search) > 256:
            raise ValueError("Invalid search")
        return [self._summary_view(item) for item in self.store.list_mcp_servers(search)]

    def get(self, server_id: str) -> dict[str, Any]:
        sid = required_id(server_id, "server ID")
        record = self.store.get_mcp_server(sid)
        if record is None:
            raise KeyError(sid)
        return self._detail_view(record)

    def catalog(self) -> list[dict[str, Any]]:
        """Return enabled MCP servers and their validated, non-stale enabled tools for Agent selection."""
        result: list[dict[str, Any]] = []
        for record in self.store.list_mcp_servers():
            if not record["enabled"] or self._is_discovery_stale(record):
                continue
            enabled_tools = [
                self._public_tool(record["server_id"], tool)
                for tool in record.get("tools", [])
                if tool.get("enabled", True)
            ]
            summary = self._summary_view(record)
            summary["tools"] = enabled_tools
            result.append(summary)
        return result

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Invalid MCP server payload")
        sid = required_id(payload.get("server_id") or f"mcp_{os.urandom(6).hex()}", "server ID")
        existing = self.store.get_mcp_server(sid)

        expected_updated_at = payload.get("expected_updated_at")
        if expected_updated_at is not None and not isinstance(expected_updated_at, str):
            raise ValueError("Invalid expected_updated_at")
        if existing is not None and expected_updated_at is not None and expected_updated_at != existing["updated_at"]:
            raise TaskConflict("The MCP server changed. Refresh before saving.")
        if existing is None and expected_updated_at is not None:
            raise KeyError(sid)

        enabled = payload.get("enabled", existing["enabled"] if existing else True)
        if not isinstance(enabled, bool):
            raise ValueError("Invalid enabled flag")

        # Restrict the quick toggle branch strictly to toggle-only requests.
        toggle_only_keys = {"server_id", "enabled", "expected_updated_at"}
        if existing is not None and "enabled" in payload and set(payload.keys()) <= toggle_only_keys:
            if existing["enabled"] == enabled:
                return self._detail_view(existing)
            timestamp = now()
            with self.store.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT * FROM task_mcp_servers WHERE server_id=?", (sid,)).fetchone()
                if row is None:
                    raise KeyError(sid)
                if expected_updated_at is not None and row["updated_at"] != expected_updated_at:
                    raise TaskConflict("The MCP server changed. Refresh before saving.")
                connection.execute(
                    "UPDATE task_mcp_servers SET enabled=?, updated_at=? WHERE server_id=?",
                    (int(enabled), timestamp, sid),
                )
            return self.get(sid)

        raw_name = payload.get("name", existing["name"] if existing else None)
        if not isinstance(raw_name, str) or not raw_name.strip() or len(raw_name.strip()) > MAX_SERVER_NAME_LEN or _has_control_chars(raw_name):
            raise MCPLibraryError("invalid_name", "Server name is required and must be at most 160 characters")
        name = raw_name.strip()

        raw_desc = payload.get("description", existing["description"] if existing else "")
        if not isinstance(raw_desc, str) or len(raw_desc) > MAX_SERVER_DESC_LEN or _has_control_chars(raw_desc, allow_newlines=True):
            raise MCPLibraryError("invalid_description", "Server description is invalid or exceeds 2000 characters")
        description = raw_desc.strip()

        transport = payload.get("transport", existing["transport"] if existing else None)
        if not isinstance(transport, str) or transport not in TRANSPORTS:
            raise MCPLibraryError("invalid_transport", "Transport must be 'stdio', 'streamable_http', or 'sse'")

        prev_config = existing["config"] if existing else {}
        prev_secrets = existing["secrets"] if existing else {}

        raw_timeout = payload.get("timeout_seconds", prev_config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        if isinstance(raw_timeout, bool) or not isinstance(raw_timeout, (int, float)) or not math.isfinite(raw_timeout):
            raise MCPLibraryError("invalid_timeout", "timeout_seconds must be a finite number")
        timeout_seconds = float(raw_timeout)
        if not MIN_TIMEOUT_SECONDS <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise MCPLibraryError(
                "invalid_timeout",
                f"timeout_seconds must be between {MIN_TIMEOUT_SECONDS:g} and {MAX_TIMEOUT_SECONDS:g} seconds",
            )

        new_config: dict[str, Any] = {"timeout_seconds": timeout_seconds}
        new_secrets: dict[str, Any] = {}

        if transport == "stdio":
            raw_cmd = payload.get("command", prev_config.get("command") if existing and existing["transport"] == "stdio" else None)
            if not isinstance(raw_cmd, str) or not raw_cmd.strip() or len(raw_cmd.strip()) > MAX_COMMAND_LEN or _has_control_chars(raw_cmd):
                raise MCPLibraryError("invalid_command", "Stdio command executable is required")
            command = raw_cmd.strip()

            raw_args = payload.get("args", prev_config.get("args", []) if existing and existing["transport"] == "stdio" else [])
            if not isinstance(raw_args, list) or len(raw_args) > MAX_ARGS_COUNT:
                raise MCPLibraryError("invalid_args", f"Stdio args must be a list of at most {MAX_ARGS_COUNT} strings")
            args: list[str] = []
            for item in raw_args:
                if not isinstance(item, str) or len(item) > MAX_ARG_LEN or _has_control_chars(item):
                    raise MCPLibraryError("invalid_args", "Each stdio argument must be a valid string without control characters")
                args.append(item)

            raw_cwd = payload.get("cwd", prev_config.get("cwd", "") if existing and existing["transport"] == "stdio" else "")
            if raw_cwd is None or raw_cwd == "":
                cwd = None
            elif isinstance(raw_cwd, str) and not _has_control_chars(raw_cwd):
                cwd_path = Path(raw_cwd.strip()).expanduser()
                if not cwd_path.is_absolute():
                    raise MCPLibraryError("invalid_cwd", "Working directory must be an absolute path when specified")
                cwd = str(cwd_path)
            else:
                raise MCPLibraryError("invalid_cwd", "Working directory is invalid")

            prev_env = prev_secrets.get("env", {}) if existing and existing["transport"] == "stdio" else {}
            env = _validate_secret_keys(
                prev_env,
                payload.get("env"),
                payload.get("clear_env_keys"),
                key_pattern=_ENV_KEY_RE,
                max_count=MAX_ENV_COUNT,
                label="env",
            )
            new_config.update(command=command, args=args, cwd=cwd)
            new_secrets["env"] = env
        else:
            prev_url = prev_secrets.get("url", "") if existing and existing["transport"] in {"streamable_http", "sse"} else ""
            raw_url = payload.get("url")
            if raw_url is None or (isinstance(raw_url, str) and not raw_url.strip()):
                if not prev_url:
                    raise MCPLibraryError("invalid_url", "Server URL is required")
                full_url, display_url, _ = _validate_url(prev_url)
            else:
                full_url, display_url, _ = _validate_url(raw_url)

            prev_headers = prev_secrets.get("headers", {}) if existing and existing["transport"] in {"streamable_http", "sse"} else {}
            headers = _validate_secret_keys(
                prev_headers,
                payload.get("headers"),
                payload.get("clear_header_keys"),
                key_pattern=_HEADER_KEY_RE,
                max_count=MAX_HEADERS_COUNT,
                label="header",
                lower_forbidden=_FORBIDDEN_HEADERS,
                case_insensitive=True,
            )
            new_config.update(display_url=display_url, url_configured=True)
            new_secrets.update(url=full_url, headers=headers)

        tools = deepcopy(existing["tools"]) if existing else []
        if "enabled_tool_names" in payload and payload["enabled_tool_names"] is not None:
            tools = self._apply_enabled_tools(tools, payload["enabled_tool_names"])

        status = deepcopy(existing["status"]) if existing else {}
        if existing is not None:
            old_fp = _connection_fingerprint(existing["transport"], prev_config, prev_secrets)
            new_fp = _connection_fingerprint(transport, new_config, new_secrets)
            if old_fp != new_fp:
                status["stale"] = True
                if status.get("last_test_status") == "ok":
                    status["last_test_status"] = "stale"

        timestamp = now()
        created_at = existing["created_at"] if existing else timestamp

        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current_row = connection.execute("SELECT * FROM task_mcp_servers WHERE server_id=?", (sid,)).fetchone()
            current = self.store._mcp_server(current_row)
            if current is not None:
                if expected_updated_at is not None and current["updated_at"] != expected_updated_at:
                    raise TaskConflict("The MCP server changed. Refresh before saving.")
                if (
                    current["name"] == name
                    and current["description"] == description
                    and current["transport"] == transport
                    and current["enabled"] == enabled
                    and current["config"] == new_config
                    and current["secrets"] == new_secrets
                    and current["tools"] == tools
                    and current["status"] == status
                ):
                    return self._detail_view(current)
            elif expected_updated_at is not None:
                raise KeyError(sid)

            connection.execute(
                """INSERT INTO task_mcp_servers(server_id, name, description, transport, enabled, config, secrets, tools, status, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(server_id) DO UPDATE SET
                   name=excluded.name,
                   description=excluded.description,
                   transport=excluded.transport,
                   enabled=excluded.enabled,
                   config=excluded.config,
                   secrets=excluded.secrets,
                   tools=excluded.tools,
                   status=excluded.status,
                   updated_at=excluded.updated_at""",
                (
                    sid,
                    name,
                    description,
                    transport,
                    int(enabled),
                    json.dumps(new_config, ensure_ascii=False),
                    json.dumps(new_secrets, ensure_ascii=False),
                    json.dumps(tools, ensure_ascii=False),
                    json.dumps(status, ensure_ascii=False),
                    created_at,
                    timestamp,
                ),
            )
            saved = self.store._mcp_server(
                connection.execute("SELECT * FROM task_mcp_servers WHERE server_id=?", (sid,)).fetchone()
            )
        return self._detail_view(saved)

    def set_tool_enabled(
        self,
        server_id: str,
        *,
        tool_name: str | None = None,
        enabled: bool | None = None,
        enabled_tool_names: list[str] | None = None,
        expected_updated_at: str | None = None,
    ) -> dict[str, Any]:
        sid = required_id(server_id, "server ID")
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM task_mcp_servers WHERE server_id=?", (sid,)).fetchone()
            record = self.store._mcp_server(row)
            if record is None:
                raise KeyError(sid)
            if expected_updated_at is not None and record["updated_at"] != expected_updated_at:
                raise TaskConflict("The MCP server changed. Refresh before updating tools.")
            tools = deepcopy(record["tools"])
            if enabled_tool_names is not None:
                tools = self._apply_enabled_tools(tools, enabled_tool_names)
            elif tool_name is not None:
                if not isinstance(enabled, bool):
                    raise ValueError("Invalid enabled flag")
                matched = False
                for item in tools:
                    if item["name"] == tool_name or item.get("namespaced_name") == tool_name:
                        item["enabled"] = enabled
                        matched = True
                if not matched:
                    raise KeyError(tool_name)
            else:
                raise ValueError("Specify tool_name or enabled_tool_names")

            if tools != record["tools"]:
                connection.execute(
                    "UPDATE task_mcp_servers SET tools=?, updated_at=? WHERE server_id=?",
                    (json.dumps(tools, ensure_ascii=False), now(), sid),
                )
            updated = self.store._mcp_server(
                connection.execute("SELECT * FROM task_mcp_servers WHERE server_id=?", (sid,)).fetchone()
            )
        return self._detail_view(updated)

    def delete(self, server_id: str, *, expected_updated_at: str | None = None) -> dict[str, Any]:
        sid = required_id(server_id, "server ID")
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT * FROM task_mcp_servers WHERE server_id=?", (sid,)).fetchone()
            if existing is None:
                raise KeyError(sid)
            if expected_updated_at is not None and existing["updated_at"] != expected_updated_at:
                raise TaskConflict("The MCP server changed. Refresh before deleting.")
            connection.execute("DELETE FROM task_mcp_servers WHERE server_id=?", (sid,))
        return {"deleted": True, "server_id": sid}

    def test(self, server_id: str) -> dict[str, Any]:
        """Connect to the saved MCP server, discover and validate tools, and update cached tool list."""
        sid = required_id(server_id, "server ID")
        record = self.store.get_mcp_server(sid)
        if record is None:
            raise KeyError(sid)
        snapshot_updated_at = record["updated_at"]
        tested_fp = _connection_fingerprint(record["transport"], record.get("config") or {}, record.get("secrets") or {})

        try:
            discovered = anyio.run(
                lambda: discover_mcp_server_tools_async(record, previous_tools=record.get("tools"))
            )
        except MCPLibraryError as exc:
            completed_at = now()
            with self.store.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current_row = connection.execute("SELECT * FROM task_mcp_servers WHERE server_id=?", (sid,)).fetchone()
                current = self.store._mcp_server(current_row)
                if current is None or current["updated_at"] != snapshot_updated_at:
                    raise TaskConflict("The MCP server configuration changed while the test was running.") from None
                status = {
                    **dict(current.get("status") or {}),
                    "last_test_at": completed_at,
                    "last_test_status": "error",
                    "last_error": {"code": exc.code, "message": redact_mcp_text(exc.message, current.get("secrets"))},
                }
                connection.execute(
                    "UPDATE task_mcp_servers SET status=? WHERE server_id=?",
                    (json.dumps(status, ensure_ascii=False), sid),
                )
            raise

        completed_at = now()
        status = {
            "last_test_at": completed_at,
            "last_test_status": "ok",
            "last_success_at": completed_at,
            "protocol_version": discovered["protocol_version"],
            "server_info": discovered["server_info"],
            "last_error": None,
            "stale": False,
            "tested_fingerprint": tested_fp,
        }
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current_row = connection.execute("SELECT * FROM task_mcp_servers WHERE server_id=?", (sid,)).fetchone()
            current = self.store._mcp_server(current_row)
            if current is None or current["updated_at"] != snapshot_updated_at:
                raise TaskConflict("The MCP server configuration changed while the test was running.")
            connection.execute(
                "UPDATE task_mcp_servers SET tools=?, status=?, updated_at=? WHERE server_id=?",
                (
                    json.dumps(discovered["tools"], ensure_ascii=False),
                    json.dumps(status, ensure_ascii=False),
                    completed_at,
                    sid,
                ),
            )
            saved = self.store._mcp_server(
                connection.execute("SELECT * FROM task_mcp_servers WHERE server_id=?", (sid,)).fetchone()
            )
        return self._detail_view(saved)

    discover = test

    def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
        on_dispatched: Any = None,
        include_internal_media: bool = False,
    ) -> dict[str, Any]:
        """Execute a single bounded tool call on a saved MCP server after verifying discovery & schema."""
        sid = required_id(server_id, "server ID")
        record = self.store.get_mcp_server(sid)
        if record is None:
            raise KeyError(sid)
        if not record["enabled"]:
            raise MCPLibraryError("server_disabled", "MCP server is disabled", dispatch_uncertain=False)
        if self._is_discovery_stale(record):
            raise MCPLibraryError(
                "discovery_stale",
                "MCP server connection settings changed; run connection test before calling tools",
                dispatch_uncertain=False,
            )
        matched_tool: dict[str, Any] | None = None
        for item in record.get("tools") or []:
            if item.get("namespaced_name") == tool_name or item.get("name") == tool_name:
                matched_tool = item
                break
        if matched_tool is None:
            raise MCPLibraryError(
                "unknown_tool",
                f"Tool '{tool_name}' is not in the server's discovered tool list",
                dispatch_uncertain=False,
            )
        if not matched_tool.get("enabled", True):
            raise MCPLibraryError(
                "tool_disabled",
                f"MCP tool '{tool_name}' is disabled",
                dispatch_uncertain=False,
            )
        if arguments is not None and not isinstance(arguments, dict):
            raise MCPLibraryError(
                "invalid_tool_arguments",
                "Tool arguments must be a JSON object",
                dispatch_uncertain=False,
            )
        schema = matched_tool.get("input_schema") or {"type": "object", "properties": {}}
        issues = validate_tool_arguments(schema, dict(arguments or {}))
        if issues:
            raise MCPLibraryError(
                "invalid_tool_arguments",
                "Tool arguments do not match the discovered input schema",
                dispatch_uncertain=False,
                details={"issues": issues},
            )
        return anyio.run(
            lambda: call_mcp_server_tool_async(
                record,
                matched_tool["name"],
                arguments,
                timeout_seconds=timeout_seconds,
                on_dispatched=on_dispatched,
                include_internal_media=include_internal_media,
            )
        )

    @staticmethod
    def _apply_enabled_tools(tools: list[dict[str, Any]], enabled_names: Any) -> list[dict[str, Any]]:
        if not isinstance(enabled_names, list) or not all(isinstance(x, str) for x in enabled_names):
            raise MCPLibraryError("invalid_tools", "enabled_tool_names must be a list of strings")
        known = {item["name"] for item in tools} | {item.get("namespaced_name") for item in tools}
        unknown = [name for name in enabled_names if name not in known]
        if unknown:
            raise MCPLibraryError("unknown_tool", f"Unknown MCP tool: {unknown[0]}")
        enabled_set = set(enabled_names)
        updated = deepcopy(tools)
        for item in updated:
            item["enabled"] = item["name"] in enabled_set or item.get("namespaced_name") in enabled_set
        return updated

    @staticmethod
    def _public_tool(server_id: str, tool: dict[str, Any], *, include_schema: bool = True) -> dict[str, Any]:
        view: dict[str, Any] = {
            "server_id": server_id,
            "name": tool["name"],
            "namespaced_name": tool.get("namespaced_name") or namespace_mcp_tool_name(server_id, tool["name"]),
            "title": tool.get("title") or tool["name"],
            "description": tool.get("description", ""),
            "annotations": dict(tool.get("annotations") or {}),
            "enabled": bool(tool.get("enabled", True)),
        }
        if include_schema:
            view["input_schema"] = deepcopy(tool.get("input_schema") or {"type": "object", "properties": {}})
        return view

    def _summary_view(self, record: dict[str, Any]) -> dict[str, Any]:
        config = record.get("config") or {}
        secrets = record.get("secrets") or {}
        status = record.get("status") or {}
        tools = record.get("tools") or []
        transport = record["transport"]
        stale = self._is_discovery_stale(record)

        env_keys = sorted((secrets.get("env") or {}).keys()) if transport == "stdio" else []
        header_keys = sorted((secrets.get("headers") or {}).keys()) if transport != "stdio" else []
        view: dict[str, Any] = {
            "server_id": record["server_id"],
            "name": record["name"],
            "description": record["description"],
            "transport": transport,
            "enabled": bool(record["enabled"]),
            "timeout_seconds": float(config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
            "env_keys": env_keys,
            "has_env": bool(env_keys),
            "header_keys": header_keys,
            "has_headers": bool(header_keys),
            "tool_count": len(tools),
            "enabled_tool_count": sum(1 for item in tools if item.get("enabled", True)),
            "discovery_stale": stale,
            "last_test_at": status.get("last_test_at"),
            "last_test_status": "stale" if stale and status.get("last_test_status") == "ok" else status.get("last_test_status"),
            "last_success_at": status.get("last_success_at"),
            "protocol_version": status.get("protocol_version"),
            "server_info": deepcopy(status.get("server_info")),
            "last_error": deepcopy(status.get("last_error")),
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        }
        if transport == "stdio":
            view["command"] = config.get("command", "")
            view["args"] = list(config.get("args") or [])
            view["cwd"] = config.get("cwd")
        else:
            view["display_url"] = config.get("display_url", "")
            view["url_configured"] = bool(secrets.get("url"))
        return view

    def _detail_view(self, record: dict[str, Any]) -> dict[str, Any]:
        summary = self._summary_view(record)
        summary["tools"] = [
            self._public_tool(record["server_id"], tool, include_schema=True)
            for tool in record.get("tools") or []
        ]
        return summary
