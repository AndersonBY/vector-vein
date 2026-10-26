"""Validated, bounded HTTP requests for the workflow tools node."""
import json
import math
import re

import httpx

from utilities.network import new_httpx_client
from utilities.workflow_errors import WorkflowInputError


MAX_RESPONSE_BYTES = 5 * 1024 * 1024
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def _reject_constant(value):
    raise ValueError("Nonfinite JSON number")


def _json(value, field):
    if isinstance(value, str):
        try:
            return json.loads(value, parse_constant=_reject_constant)
        except (ValueError, TypeError):
            raise WorkflowInputError(f"{field} must contain valid JSON") from None
    return value


def _object(value, field):
    value = _json(value, field)
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise WorkflowInputError(f"{field} must be a JSON object")
    return value


def _scalar(value):
    return value is None or isinstance(value, (str, bool, int)) or isinstance(value, float) and math.isfinite(value)


def perform_http_request(*, url, method="GET", headers="{}", query_params="{}", body_type="none", body="", timeout=30, follow_redirects=False, fail_on_http_error=True):
    if not isinstance(url, str):
        raise WorkflowInputError("url must be an HTTP(S) URL")
    try:
        target = httpx.URL(url)
        if target.scheme not in ("http", "https") or not target.host:
            raise ValueError()
    except (ValueError, httpx.InvalidURL):
        raise WorkflowInputError("url must be an HTTP(S) URL") from None
    if not isinstance(method, str) or method not in METHODS:
        raise WorkflowInputError("Unsupported HTTP method")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 300 or not math.isfinite(timeout):
        raise WorkflowInputError("timeout must be a finite number between 1 and 300 seconds")
    if not isinstance(follow_redirects, bool) or not isinstance(fail_on_http_error, bool):
        raise WorkflowInputError("HTTP options must be booleans")
    headers = _object(headers, "headers").copy()
    for key, value in headers.items():
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) or not isinstance(value, str) or any(ord(char) < 32 or ord(char) >= 127 for char in value):
            raise WorkflowInputError("headers must contain valid names and string values without control characters")
    params = _object(query_params, "query_params")
    if any(not all(_scalar(item) for item in value) if isinstance(value, list) else not _scalar(value) for value in params.values()):
        raise WorkflowInputError("query_params values must be scalars or lists of scalars")
    # Append parameters so query values already present in the URL survive.
    extra_query = str(httpx.QueryParams(params)).encode("ascii")
    if extra_query:
        target = target.copy_with(query=target.query + (b"&" if target.query else b"") + extra_query)
    kwargs = {}
    if body_type == "json":
        try:
            kwargs["content"] = json.dumps(_json(body, "body"), allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            raise WorkflowInputError("body must contain valid JSON") from None
        if not any(key.lower() == "content-type" for key in headers):
            headers["Content-Type"] = "application/json"
    elif body_type == "text":
        if not isinstance(body, str):
            raise WorkflowInputError("text body must be a string")
        kwargs["content"] = body.encode("utf-8")
    elif body_type == "form":
        form = _object(body, "body")
        if any(not _scalar(value) for value in form.values()):
            raise WorkflowInputError("form body values must be scalars")
        kwargs["data"] = form
    elif body_type != "none":
        raise WorkflowInputError("Unsupported body type")
    try:
        with new_httpx_client(is_async=False) as client:
            with client.stream(method, target, headers=headers, timeout=timeout, follow_redirects=follow_redirects, **kwargs) as response:
                content = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise RuntimeError("HTTP response exceeds the 5 MiB limit")
                    content.extend(chunk)
                # iter_bytes already decompresses the payload; do not decode Content-Encoding twice.
                decoded = httpx.Response(response.status_code, content=bytes(content), default_encoding=response.encoding or "utf-8")
                try:
                    parsed = decoded.json(parse_constant=_reject_constant)
                except (ValueError, UnicodeError):
                    parsed = None
                return {"status_code": response.status_code, "response_headers": dict(response.headers), "response_body": decoded.text, "response_json": parsed}
    except httpx.HTTPError as exc:
        raise RuntimeError(f"HTTP request failed ({type(exc).__name__})") from None
