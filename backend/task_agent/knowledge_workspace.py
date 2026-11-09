"""Route ordinary file tools to task-scoped, read-only knowledge text without materializing it."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import partial
from pathlib import PurePosixPath
import hashlib
import posixpath
import re

import regex

from vv_agent.tools.handlers import workspace_io
from vv_agent.tools.handlers.search import FILE_TYPE_EXTENSIONS
from vv_agent.tools.handlers.sensitive_paths import is_sensitive_path
from vv_agent.types import ToolExecutionResult, ToolResultStatus, ToolResultCursor
from vv_agent.workspace.matching import RegexBudget, check_matching_budget, compile_glob, compile_pattern, matching_request

from vv_agent.workspace.streaming import scan_text

from . import knowledge

_TOOLS = ("find_files", "read_file", "search_files", "file_info", "write_file", "edit_file")
_READ_LIMIT = 262144
_LIST_LIMIT = 15000  # Three pages: bridge offsets 0, 5000, 10000.
_SEARCH_CHARS = 8_000_000
_ERRORS = {
    "knowledge_readonly": ".knowledge is read-only. Write derived outputs to the task workspace instead.",
    "invalid_path": "Invalid knowledge path. Parent traversal is not allowed inside .knowledge.",
    "invalid_arguments": "Unsupported knowledge tool arguments. Check the declared parameters.",
    "stale_source": "The knowledge source changed while reading. Start a fresh read and discard partial pages.",
    "not_found": "This knowledge source is unavailable. Refresh find_files(path='.knowledge').",
    "indexing": "The knowledge document is still being indexed. Retry when extraction is complete.",
    "source_unavailable": "Extracted text is unavailable. Check the document's indexing status.",
    "service_unavailable": "The knowledge service is unavailable. Retry when the desktop service is ready.",
    "knowledge_unavailable": "Knowledge access is unavailable. Check this task's mounted knowledge bases.",
    "regex_timeout": "Knowledge search exceeded the regex/glob budget. Narrow the path or simplify the pattern.",
}


class _VfsError(RuntimeError):
    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or _ERRORS[code])


def normalize_knowledge_path(raw_path, workspace) -> str | None:
    """Lexical routing only. Never follow a physical symlink to discover the namespace."""
    if not isinstance(raw_path, str):
        return None
    raw = raw_path.replace("\\", "/")
    root = str(workspace).replace("\\", "/").rstrip("/")
    windows = bool(re.match(r"^[A-Za-z]:", root)) or root.startswith("//")
    if raw.startswith("//?/"):
        raw = raw[4:]
        if raw.startswith("UNC/"):
            raw = "//" + raw[4:]
    absolute = raw.startswith("/") or bool(re.match(r"^[A-Za-z]:", raw))
    root_parts = [part for part in posixpath.normpath(root).split("/") if part not in ("", ".")]
    prefix = []
    parts = raw.split("/")
    for index, part in enumerate(parts):
        marker = part.rstrip(" .").split(":", 1)[0].casefold() == ".knowledge"
        same_root = ([p.casefold() for p in prefix] == [p.casefold() for p in root_parts]
                     if windows else prefix == root_parts)
        if marker and (not prefix or absolute and (same_root or prefix == ["workspace"])):
            tail = parts[index + 1:]
            if part.casefold() != ".knowledge" or any(p == ".." for p in tail):
                raise ValueError(_ERRORS["invalid_path"])
            if any("\0" in p or ":" in p or p.rstrip(" .") != p for p in tail if p not in ("", ".")):
                raise ValueError(_ERRORS["invalid_path"])
            return "/".join([".knowledge", *(p for p in tail if p not in ("", "."))])
        if part in ("", "."):
            continue
        if part == "..":
            if prefix and prefix[-1] != "..":
                prefix.pop()
            elif not absolute:
                prefix.append(part)
        else:
            prefix.append(part)
    return None


def _error(code, message=None):
    return ToolExecutionResult("", message or _ERRORS[code], status_code=ToolResultStatus.ERROR, error_code=code)


def _integer(args, key, default, minimum=0, maximum=None):
    value = args.get(key, default)
    if type(value) is not int or value < minimum or maximum is not None and value > maximum:
        raise _VfsError("invalid_arguments", f"{key} is outside the supported integer range.")
    return value


class _KnowledgeBackend:
    """One tool call owns one backend; only per-call metadata is retained."""
    def __init__(self, task_id, mounts):
        self.task_id, self.mounts = task_id, mounts
        self.stats = {}

    def rpc(self, action, path, **args):
        try:
            return knowledge._bridge_request("vfs", {
                "task_id": self.task_id, "mounts": deepcopy(self.mounts),
                "arguments": {"action": action, "path": path, **args},
            })
        except Exception as error:
            code = getattr(error, "code", None)
            raise _VfsError(code if isinstance(code, str) and code in _ERRORS else "knowledge_unavailable") from None

    def stat(self, path):
        if path not in self.stats:
            self.stats[path] = self.rpc("stat", path)
        return self.stats[path]

    def is_file(self, path):
        return self.stat(path)["kind"] == "file"

    def _read_bytes_chunks(self, path):
        info = self.stat(path)
        if info["kind"] != "file":
            raise _VfsError("invalid_arguments", "Choose a document path; use find_files for a directory.")
        version = info["version"]
        offset, total = 0, None
        while True:
            page = self.rpc("read", path, offset=offset, limit=_READ_LIMIT, expected_version=version)
            text = page["text"]
            if page["version"] != version or total is not None and page["total"] != total:
                raise _VfsError("stale_source")
            total = page["total"]
            end = offset + len(text)
            if (page["path"] != path or page["offset"] != offset or len(text) > _READ_LIMIT or end > total
                    or page["next_offset"] != (end if end < total else None) or end == offset and end < total):
                raise _VfsError("knowledge_unavailable")
            yield text.encode("utf-8")
            if page["next_offset"] is None:
                break
            offset = end
        # Reject a replacement that occurred after the last page was read.
        if self.rpc("stat", path).get("version") != version:
            raise _VfsError("stale_source")

    def entries(self, path, scan_limit):
        entries, offset = [], 0
        while True:
            page = self.rpc("list", path, offset=offset, limit=min(5000, scan_limit - len(entries)), recursive=True)
            entries.extend(page["entries"])
            next_offset = page["next_offset"]
            if next_offset is None or next_offset > 10000 or len(entries) >= scan_limit:
                return entries, bool(page["truncated"])
            if type(next_offset) is not int or next_offset <= offset:
                raise _VfsError("knowledge_unavailable")
            offset = next_offset
            check_matching_budget()


def _filtered_entries(backend, path, args, scan_limit, *, allow_file=False):
    explicit_file = allow_file and backend.is_file(path)
    if explicit_file:
        entries, truncated = [backend.stat(path)], False
    else:
        entries, truncated = backend.entries(path, scan_limit)
    pattern = args.get("glob", "**/*")
    matcher = RegexBudget(compile_glob(pattern))
    filtered, sensitive = [], 0
    for entry in entries:
        check_matching_budget()
        candidate = entry["path"]
        relative = candidate.removeprefix(path + "/") if candidate != path else PurePosixPath(candidate).name
        if not matcher.match(relative):
            continue
        # The mount namespace itself is explicitly selected, not a hidden disk directory.
        if not explicit_file and not args.get("include_hidden", False) and any(p.startswith(".") for p in relative.split("/")):
            continue
        if not args.get("include_sensitive", False) and is_sensitive_path(candidate):
            sensitive += 1
            continue
        filtered.append(entry)
    return filtered, truncated, sensitive


def _find(backend, path, args):
    maximum = _integer(args, "max_results", 100, 1, 5000)
    offset = _integer(args, "offset", 0, maximum=10000)
    scan_limit = min(_integer(args, "scan_limit", 50000, 1), _LIST_LIMIT)
    order = args.get("sort", "modified_desc")
    if order not in ("modified_desc", "path_asc"):
        raise _VfsError("invalid_arguments")
    entries, incomplete, sensitive = _filtered_entries(backend, path, args, scan_limit)
    entries.sort(key=lambda entry: entry["path"])
    if order == "modified_desc":
        entries.sort(key=lambda entry: entry.get("modified_at") or "", reverse=True)
    shown = entries[offset:offset + maximum]
    more = offset + len(shown) < len(entries)
    payload = {"files": [entry["path"] + ("/" if entry["kind"] == "folder" else "") for entry in shown],
               "count": len(entries), "returned_count": len(shown), "truncated": more or incomplete,
               "max_results": maximum, "offset": offset, "sort": order,
               "next_offset": offset + len(shown) if more and offset + len(shown) <= 10000 else None}
    if sensitive:
        payload["sensitive_files_omitted"] = sensitive
    if incomplete:
        payload.update(count_is_estimate=True, scan_limit=scan_limit,
                       message="Knowledge listing is incomplete. Narrow path/glob; listing stopped at the scan or paging limit.")
    return ToolExecutionResult("", workspace_io.to_json(payload), metadata={"knowledge_entries": shown})


def _read(backend, path, args, workspace):
    cursor = None
    if "cursor" in args:
        raw = args["cursor"]
        if not isinstance(raw, dict) or any(key in args for key in ("start_line", "end_line", "start_char")):
            raise _VfsError("invalid_arguments")
        cursor = ToolResultCursor.from_dict({**raw, "path": normalize_knowledge_path(raw.get("path"), workspace)})
        if cursor.path != path:
            return _error("invalid_arguments", "Cursor path does not match the requested knowledge document.")
    start = _integer(args, "start_line", 1, 1)
    end = _integer(args, "end_line", start, 1) if "end_line" in args else None
    char = _integer(args, "start_char", 0)
    page = workspace_io._ReadPage(start, max(start, end) if end is not None else None,
                                  cursor.offset_chars if cursor else None, bool(args.get("show_line_numbers")), start_char=char)
    scanned = scan_text(backend, path, page.consume)
    version = backend.stat(path)["version"]
    digest = hashlib.sha256((version + ":" + scanned.sha256).encode()).hexdigest()
    if cursor and cursor.sha256 != digest:
        return _error("stale_source")
    if cursor and cursor.offset_chars > page.offset:
        return _error("invalid_arguments", "Cursor offset is outside the knowledge document.")
    if not scanned.valid_utf8:
        return _error("source_unavailable")
    content = "".join(page.output)
    hint = f"\nNext page: use the returned cursor, or read_file(start_line={page.next_line}, start_char={page.next_char}) on the same path." if page.truncated else ""
    content += hint
    return ToolExecutionResult("", content, truncated=True if page.truncated else None,
        truncation_reason="read_limit" if page.truncated else None,
        original_bytes=page.original_bytes + len(hint.encode()) if page.truncated else None,
        visible_bytes=len(content.encode()) if page.truncated else None,
        cursor=ToolResultCursor("read_file", path, page.next_offset, digest) if page.truncated else None,
        metadata={"knowledge_version": version, **({"read_page": {"next_line": page.next_line,
                  "next_start_char": page.next_char}} if page.truncated else {})})


def _info(backend, path):
    entry = backend.stat(path)
    payload = {"path": entry["path"], "exists": True, "is_file": entry["kind"] == "file",
               "is_dir": entry["kind"] == "folder", "size": entry.get("size", 0), "modified_at": entry["modified_at"]}
    if payload["is_file"]:
        payload["suffix"] = PurePosixPath(path).suffix
    return ToolExecutionResult("", workspace_io.to_json(payload), metadata={"knowledge_entry": entry})


def _search(backend, path, args):
    pattern = args.get("pattern", "")
    mode = args.get("output_mode", "files_with_matches")
    if not isinstance(pattern, str) or not pattern.strip() or mode not in ("content", "count", "files_with_matches"):
        raise _VfsError("invalid_arguments")
    multiline = bool(args.get("multiline", False))
    offset = _integer(args, "offset", 0)
    head = _integer(args, "head_limit", 250)
    before, after = (_integer(args, key, 0) for key in ("b", "a"))
    if "c" in args:
        before = after = _integer(args, "c", 0)
    file_type = args.get("type")
    if isinstance(file_type, str):
        file_type = file_type.strip().lower()
    types = {**FILE_TYPE_EXTENSIONS, **{ext: ("." + ext,) for ext in ("pdf", "docx", "xlsx", "pptx", "csv", "tsv")}}
    if file_type is not None and file_type not in types:
        raise _VfsError("invalid_arguments", "Unsupported file type. Use a filename glob to select extracted documents.")
    insensitive = not args["case_sensitive"] if "case_sensitive" in args else not any(char.isupper() for char in pattern)
    flags = (regex.IGNORECASE if insensitive else 0) | (regex.MULTILINE | regex.DOTALL if multiline else 0)
    compiled = compile_pattern(re.escape(pattern) if args.get("literal") else pattern, flags)
    matcher = RegexBudget(compiled)
    entries, incomplete, sensitive = _filtered_entries(backend, path, args, _LIST_LIMIT, allow_file=True)
    files = sorted((entry for entry in entries if entry["kind"] == "file"), key=lambda entry: entry["path"])
    shown, total_items, used, chars = [], 0, 0, 0
    searched = matches = matching_files = 0
    unavailable = []
    unavailable_count = warning_chars = 0
    capped = content_truncated = False

    def collect(item):
        nonlocal total_items, used, capped, content_truncated
        check_matching_budget()
        total_items += 1
        if total_items <= offset or capped:
            return
        if isinstance(item, dict) and len(item["text"]) > 4000:
            item = {**item, "text": item["text"][:4000], "text_truncated": True}
            content_truncated = True
        size = len(workspace_io.to_json(item))
        if head and len(shown) >= head or len(shown) >= 200 or used + size > 20000:
            capped = True
            return
        shown.append(item)
        used += size

    for entry in files:
        check_matching_budget()
        filename = entry["path"]
        if file_type is not None and PurePosixPath(filename).suffix.lower() not in types[file_type] and PurePosixPath(filename).name.lower() not in types[file_type]:
            continue
        chunks = []
        try:
            for chunk in backend._read_bytes_chunks(filename):
                text = chunk.decode("utf-8")
                chars += len(text)
                if chars > _SEARCH_CHARS:
                    incomplete = True
                    break
                chunks.append(text)
        except _VfsError as error:
            if error.code not in ("indexing", "source_unavailable"):
                raise
            unavailable_count += 1
            warning = {"path": filename, "error_code": error.code}
            size = len(workspace_io.to_json(warning))
            if len(unavailable) < 20 and warning_chars + size <= 4000:
                unavailable.append(warning)
                warning_chars += size
            incomplete = True
            continue
        if chars > _SEARCH_CHARS:
            break
        text = "".join(chunks)
        searched += 1
        if multiline:
            count, line, previous = 0, 1, 0
            for match in matcher.finditer(text):
                count += 1
                if mode == "content":
                    line += text.count("\n", previous, match.start())
                    previous = match.start()
                    collect({"path": filename, "line": line, "text": match.group(0), "is_match": True})
            if count:
                matches += count
                matching_files += 1
                if mode == "files_with_matches":
                    collect(filename)
                elif mode == "count":
                    collect((filename, count))
            continue
        lines = text.splitlines()
        hit_lines, count = set(), 0
        for number, line in enumerate(lines):
            for _ in matcher.finditer(line):
                hit_lines.add(number)
                count += 1
        if not count:
            continue
        matches += count
        matching_files += 1
        if mode == "files_with_matches":
            collect(filename)
        elif mode == "count":
            collect((filename, count))
        else:
            intervals = []
            for number in sorted(hit_lines):
                start, end = max(0, number - before), min(len(lines), number + after + 1)
                if intervals and start <= intervals[-1][1]:
                    intervals[-1][1] = max(intervals[-1][1], end)
                else:
                    intervals.append([start, end])
            for start, end in intervals:
                for number in range(start, end):
                    collect({"path": filename, "line": number + 1, "text": lines[number], "is_match": number in hit_lines})
    more = offset + len(shown) < total_items
    metadata = {"output_mode": mode, "pattern": pattern, "path": path, "glob": args.get("glob", "**/*"),
                "type": file_type, "literal": bool(args.get("literal")), "offset": offset, "head_limit": head,
                "summary": {"files_searched": searched, "files_with_matches": matching_files, "total_matches": matches},
                "total_result_items": total_items, "returned_count": len(shown), "truncated": incomplete or more or content_truncated, "content_truncated": content_truncated,
                "structured_truncated": more, "head_limited": bool(head and total_items - offset > head),
                "count_is_estimate": incomplete, "next_offset": offset + len(shown) if more and shown else None}
    if sensitive:
        metadata["sensitive_files_omitted"] = sensitive
    if unavailable_count:
        metadata.update(warnings=unavailable, unavailable_count=unavailable_count,
                        warnings_truncated=unavailable_count > len(unavailable))
    if mode == "content":
        metadata["matches"] = shown
        rows = [f"{row['path']}:{str(row['line']) + ': ' if args.get('n', True) else ' '}{row['text']}" for row in shown]
    elif mode == "count":
        metadata["file_counts"] = dict(shown)
        rows = [f"{name}: {count}" for name, count in shown]
    else:
        metadata["files"] = shown
        rows = shown
    header = f"Found {matches} matches in {matching_files} files."
    if incomplete:
        header += " Search is incomplete; narrow the path or check source indexing status."
    if more or content_truncated:
        header += " Output is truncated; continue with offset/head_limit or read_file for full source text."
    return ToolExecutionResult("", "\n".join([header, *rows]), metadata=metadata)


def register_knowledge_handlers(registry, task_root, task_id, snapshot, workspace):
    """Wrap this registry only; local handlers and their approval policies remain intact."""
    del task_root  # The authenticated owner bridge revalidates the saved task on every RPC.
    mounts = deepcopy(snapshot.get("knowledge_bases", []))

    def invoke(name, original, context, arguments):
        try:
            path = normalize_knowledge_path(arguments.get("path", "."), workspace)
        except ValueError:
            return _error("invalid_path")
        if path is None:
            result = original(context, arguments)
            raw = str(arguments.get("path", ".")).replace("\\", "/")
            is_root = posixpath.normpath(raw) in (".", posixpath.normpath(str(workspace).replace("\\", "/")))
            if name == "find_files" and is_root and mounts and isinstance(result, ToolExecutionResult) and result.status_code == ToolResultStatus.SUCCESS:
                import json
                payload = json.loads(result.content)
                files = payload.get("files", [])
                kept = [value for value in files if normalize_knowledge_path(value, workspace) is None]
                if kept != files:
                    payload["files"] = kept
                    payload["returned_count"] = len(kept)
                    payload["count"] = max(len(kept), payload.get("count", len(files)) - len(files) + len(kept))
                    payload["count_is_estimate"] = True
                    payload["next_offset"] = payload.get("offset", 0) + len(files) if payload.get("truncated") else None
                payload["virtual_directories"] = [".knowledge/"]
                payload["message"] = (payload.get("message", "") + " Read-only mounts: .knowledge/. Use find_files/read_file/search_files with that explicit path; local pagination is unchanged.").strip()
                return replace(result, content=workspace_io.to_json(payload))
            return result
        if name in ("write_file", "edit_file"):
            return _error("knowledge_readonly")
        try:
            schema = registry.get_schema(name)["function"]["parameters"]
            if set(arguments) - set(schema["properties"]):
                raise _VfsError("invalid_arguments")
            if not mounts:
                raise _VfsError("knowledge_unavailable")
            backend = _KnowledgeBackend(task_id, mounts)
            with matching_request():
                if name == "read_file":
                    return _read(backend, path, arguments, workspace)
                if name == "file_info":
                    return _info(backend, path)
                if name == "find_files":
                    return _find(backend, path, arguments)
                return _search(backend, path, arguments)
        except _VfsError as error:
            return _error(error.code, str(error))
        except TimeoutError:
            return _error("regex_timeout")
        except (ValueError, regex.error):
            return _error("invalid_arguments")
        except Exception:
            return _error("knowledge_unavailable")

    description = (" .knowledge/ is a read-only virtual mount of this task's knowledge bases. "
                   "Use find_files(path='.knowledge') to discover logical document paths, then read_file/file_info on those paths. "
                   "read_file/search_files use extracted text, including PDF/DOCX contents, not raw binary files. "
                   "Search mounted text explicitly with path='.knowledge'; workspace-root searches remain local. "
                   "Multiline searches return captured spans with source line numbers. "
                   "Shell commands cannot access this virtual mount.")
    for name in _TOOLS:
        if not registry.has_tool(name):
            continue
        executor = registry.get_executor(name)
        original = executor.handler
        wrapped = partial(invoke, name, original)
        executor.handler = wrapped
        registry.get(name).handler = wrapped
        if name in ("find_files", "read_file", "search_files", "file_info"):
            schema = deepcopy(registry.get_schema(name))
            schema["function"]["description"] += description
            registry.register_schema(name, schema)
            executor.description = schema["function"]["description"]
