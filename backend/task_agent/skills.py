"""Versioned local Skills library with immutable application-owned revision bundles."""
from __future__ import annotations

import hashlib
from itertools import islice
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import unicodedata
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from vv_agent.skills.errors import SkillError, SkillParseError, SkillValidationError
from vv_agent.skills.parser import parse_frontmatter, read_skill
from vv_agent.skills.validator import validate_with_diagnostics

from .files import DOCUMENT_TYPES, PREVIEW_TEXT_TYPES
from .service import TaskConflict, required_id
from .store import BusinessStore, now

MAX_SKILL_FILES = 128
MAX_SKILL_ARCHIVE_MEMBERS = 512
MAX_SKILL_Walk_ENTRIES = 512
MAX_SKILL_FILE_BYTES = 2 * 1024 * 1024
MAX_SKILL_TOTAL_BYTES = 10 * 1024 * 1024
MAX_SKILL_MD_BYTES = 256 * 1024
MAX_PREVIEW_BYTES = 131072
MAX_LOCAL_SKILL_ENTRIES = 512
MAX_LOCAL_SKILL_SCAN_BYTES = 4 * 1024 * 1024
ARCHIVE_SUFFIXES = {".zip", ".skill"}

_WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    "conin$",
    "conout$",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
    *("com\u00b9" for _ in (1,)),
    "com\u00b2",
    "com\u00b3",
    "lpt\u00b9",
    "lpt\u00b2",
    "lpt\u00b3",
}
_FORBIDDEN_SEGMENT_CHARS = set('<>:"/\\|?*')


class SkillLibraryError(ValueError):
    def __init__(self, code: str, message: str, *, diagnostics: list[str] | None = None):
        self.code = code
        self.message = message
        self.diagnostics = list(diagnostics or [])
        super().__init__(message)


def _is_reparse_or_symlink(path: Path, *, missing_ok: bool = False) -> bool:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return False if missing_ok else True
    except OSError:
        return True
    try:
        if stat.S_ISLNK(st.st_mode):
            return True
        if getattr(st, "st_reparse_tag", 0) != 0:
            return True
        file_attrs = getattr(st, "st_file_attributes", 0)
        if file_attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            return True
        if hasattr(path, "is_junction") and path.is_junction():
            return True
    except OSError:
        return True
    return False


def _has_reparse_ancestor(path: Path, stop_at: Path | None = None) -> bool:
    current = path
    stop_resolved = stop_at.resolve() if stop_at is not None else None
    while True:
        if _is_reparse_or_symlink(current, missing_ok=True):
            return True
        if stop_resolved is not None and current == stop_resolved:
            break
        if current.parent == current:
            break
        current = current.parent
    return False


def _validate_segment(segment: str) -> None:
    if not segment or segment in {".", ".."}:
        raise SkillLibraryError("invalid_path", "Skill path contains traversal or empty segments")
    if segment[-1] in {".", " "} or segment[0] == " " or segment.strip(" .") != segment.lstrip(" "):
        raise SkillLibraryError("invalid_path", f"Skill path segment has trailing dot or space: {segment!r}")
    if any(ch in _FORBIDDEN_SEGMENT_CHARS or ord(ch) < 32 or ord(ch) == 127 for ch in segment):
        raise SkillLibraryError("invalid_path", f"Skill path segment contains forbidden characters: {segment!r}")
    if segment.casefold() == ".vv-agent":
        raise SkillLibraryError("invalid_path", "Private runtime directories are not allowed in skills")
    # Check both raw and NFKC-normalized stem against Windows DOS device names (with or without extensions).
    for candidate in (segment, unicodedata.normalize("NFKC", segment)):
        stem = candidate.split(".", 1)[0].strip(" .").casefold()
        if stem in _WINDOWS_RESERVED_NAMES or re.fullmatch(r"(?:com|lpt)[0-9]", stem):
            raise SkillLibraryError("invalid_path", f"Reserved device name is not allowed in skill path: {segment!r}")


def _validate_relative_posix_path(raw_path: str) -> str:
    if not isinstance(raw_path, str) or not raw_path or "\0" in raw_path:
        raise SkillLibraryError("invalid_path", "Invalid skill resource path")
    if "\\" in raw_path or ":" in raw_path or raw_path.startswith("/") or raw_path.endswith("/"):
        raise SkillLibraryError("invalid_path", "Skill paths must be canonical relative POSIX paths")
    if "//" in raw_path:
        raise SkillLibraryError("invalid_path", "Skill path contains empty segment")
    raw_parts = raw_path.split("/")
    for part in raw_parts:
        _validate_segment(part)
    pure = PurePosixPath(raw_path)
    normalized = pure.as_posix()
    if normalized != raw_path or len(pure.parts) != len(raw_parts):
        raise SkillLibraryError("invalid_path", "Non-canonical skill path")
    return normalized


def _canonical_fold_key(rel_posix: str) -> str:
    return "/".join(unicodedata.normalize("NFKC", part).casefold() for part in rel_posix.split("/"))


def _read_bounded_file(path: Path, max_file_bytes: int, remaining_total_bytes: int) -> bytes:
    limit = min(max_file_bytes, remaining_total_bytes)
    chunks: list[bytes] = []
    read_bytes = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(min(65536, limit + 1 - read_bytes))
            if not chunk:
                break
            read_bytes += len(chunk)
            if read_bytes > max_file_bytes:
                raise SkillLibraryError("file_too_large", f"Skill file '{path.name}' exceeds {max_file_bytes} bytes")
            if read_bytes > remaining_total_bytes:
                raise SkillLibraryError("bundle_too_large", f"Skill bundle exceeds {MAX_SKILL_TOTAL_BYTES} bytes")
            chunks.append(chunk)
    return b"".join(chunks)


def _validate_utf8_frontmatter(raw_bytes: bytes) -> tuple[dict[str, Any], str, str]:
    if len(raw_bytes) > MAX_SKILL_MD_BYTES:
        raise SkillLibraryError("file_too_large", "SKILL.md exceeds maximum size")
    try:
        content = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SkillLibraryError("invalid_encoding", "SKILL.md must be valid UTF-8") from exc
    try:
        metadata, body = parse_frontmatter(content)
    except SkillParseError as exc:
        raise SkillLibraryError("invalid_frontmatter", str(exc), diagnostics=[str(exc)]) from exc
    return metadata, body, content


def _collect_directory_entries(source_dir: Path) -> list[tuple[str, bytes]]:
    if _has_reparse_ancestor(source_dir):
        raise SkillLibraryError("symlink_rejected", "Skill source directory cannot be a symlink or reparse point")
    try:
        resolved_root = source_dir.resolve(strict=True)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise SkillLibraryError("invalid_source", "Skill source directory is unavailable") from exc
    if not resolved_root.is_dir():
        raise SkillLibraryError("invalid_source", "Skill source is not a directory")

    entries: list[tuple[str, bytes]] = []
    seen_casefold: set[str] = set()
    total_bytes = 0
    walked_items = 0

    for base, dirs, files in os.walk(resolved_root, topdown=True, followlinks=False):
        base_path = Path(base)
        if _is_reparse_or_symlink(base_path):
            raise SkillLibraryError("symlink_rejected", "Symlinks or reparse points are not permitted in skill bundles")
        walked_items += len(dirs) + len(files)
        if walked_items > MAX_SKILL_Walk_ENTRIES:
            raise SkillLibraryError("too_many_files", f"Skill directory contains too many entries (limit {MAX_SKILL_Walk_ENTRIES})")

        kept_dirs: list[str] = []
        for d in sorted(dirs):
            dir_path = base_path / d
            if _is_reparse_or_symlink(dir_path):
                raise SkillLibraryError("symlink_rejected", f"Symlink or reparse directory rejected: {d}")
            if d in {"__pycache__", ".git", "node_modules"}:
                continue
            rel_dir = dir_path.relative_to(resolved_root).as_posix()
            _validate_relative_posix_path(rel_dir)
            kept_dirs.append(d)
        dirs[:] = kept_dirs

        for name in sorted(files):
            file_path = base_path / name
            if _is_reparse_or_symlink(file_path):
                raise SkillLibraryError("symlink_rejected", f"Symlink or reparse file rejected: {name}")
            if not file_path.is_file():
                raise SkillLibraryError("invalid_file", f"Unsupported special file in skill bundle: {name}")
            rel_posix = _validate_relative_posix_path(file_path.relative_to(resolved_root).as_posix())
            folded = _canonical_fold_key(rel_posix)
            if folded in seen_casefold:
                raise SkillLibraryError("duplicate_entry", f"Colliding skill file path: {rel_posix}")
            seen_casefold.add(folded)
            if len(entries) + 1 > MAX_SKILL_FILES:
                raise SkillLibraryError("too_many_files", f"Skill bundle exceeds {MAX_SKILL_FILES} files")
            stat_size = file_path.stat().st_size
            if stat_size > MAX_SKILL_FILE_BYTES:
                raise SkillLibraryError("file_too_large", f"Skill file '{rel_posix}' exceeds {MAX_SKILL_FILE_BYTES} bytes")
            if total_bytes + stat_size > MAX_SKILL_TOTAL_BYTES:
                raise SkillLibraryError("bundle_too_large", f"Skill bundle exceeds {MAX_SKILL_TOTAL_BYTES} bytes")
            data = _read_bounded_file(file_path, MAX_SKILL_FILE_BYTES, MAX_SKILL_TOTAL_BYTES - total_bytes)
            total_bytes += len(data)
            if total_bytes > MAX_SKILL_TOTAL_BYTES:
                raise SkillLibraryError("bundle_too_large", f"Skill bundle exceeds {MAX_SKILL_TOTAL_BYTES} bytes")
            entries.append((rel_posix, data))

    return entries


def _collect_archive_entries(archive_path: Path) -> list[tuple[str, bytes]]:
    if _has_reparse_ancestor(archive_path):
        raise SkillLibraryError("symlink_rejected", "Archive path cannot be a symlink or reparse point")
    if not archive_path.is_file():
        raise SkillLibraryError("invalid_source", "Skill archive does not exist")
    if archive_path.stat().st_size > MAX_SKILL_TOTAL_BYTES:
        raise SkillLibraryError("bundle_too_large", "Skill archive exceeds size limit")

    try:
        zf = zipfile.ZipFile(archive_path, "r")
    except (zipfile.BadZipFile, OSError) as exc:
        raise SkillLibraryError("invalid_archive", "Invalid ZIP or .skill archive") from exc

    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_SKILL_ARCHIVE_MEMBERS:
            raise SkillLibraryError(
                "too_many_files",
                f"Skill archive exceeds {MAX_SKILL_ARCHIVE_MEMBERS} member headers",
            )
        raw_files: list[tuple[str, zipfile.ZipInfo]] = []
        seen_raw_exact: set[str] = set()

        for info in infos:
            raw_name = info.filename
            if not raw_name or "\0" in raw_name:
                raise SkillLibraryError("invalid_path", "Archive entry has an empty or invalid filename")
            if "\\" in raw_name or ":" in raw_name or raw_name.startswith("/"):
                raise SkillLibraryError("invalid_path", f"Archive entry has unsafe path: {raw_name}")
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(unix_mode):
                raise SkillLibraryError("symlink_rejected", f"Archive symlink entry rejected: {raw_name}")
            if info.is_dir() or raw_name.endswith("/"):
                trimmed = raw_name[:-1] if raw_name.endswith("/") else raw_name
                if not trimmed or "/" in trimmed and any(not seg for seg in trimmed.split("/")):
                    raise SkillLibraryError("invalid_path", f"Archive directory has invalid path: {raw_name}")
                _validate_relative_posix_path(trimmed)
                continue
            rel_posix = _validate_relative_posix_path(raw_name)
            if rel_posix in seen_raw_exact:
                raise SkillLibraryError("duplicate_entry", f"Duplicate archive entry: {rel_posix}")
            seen_raw_exact.add(rel_posix)
            raw_files.append((rel_posix, info))

        if not raw_files:
            raise SkillLibraryError("missing_skill_md", "Archive contains no files")

        root_has_skill_md = any(path in {"SKILL.md", "skill.md"} for path, _ in raw_files)
        strip_prefix = ""
        if not root_has_skill_md:
            top_segments = {PurePosixPath(path).parts[0] for path, _ in raw_files if len(PurePosixPath(path).parts) > 1}
            if len(top_segments) == 1 and all(len(PurePosixPath(path).parts) > 1 for path, _ in raw_files):
                candidate_prefix = next(iter(top_segments)) + "/"
                if any(path[len(candidate_prefix):] in {"SKILL.md", "skill.md"} for path, _ in raw_files):
                    strip_prefix = candidate_prefix

        entries: list[tuple[str, bytes]] = []
        seen_casefold: set[str] = set()
        total_bytes = 0

        for rel_posix, info in sorted(raw_files, key=lambda item: item[0]):
            if strip_prefix and rel_posix.startswith(strip_prefix):
                rel_posix = _validate_relative_posix_path(rel_posix[len(strip_prefix):])
            parts = PurePosixPath(rel_posix).parts
            if any(part in {"__pycache__", ".git", "node_modules"} for part in parts[:-1]):
                continue
            folded = _canonical_fold_key(rel_posix)
            if folded in seen_casefold:
                raise SkillLibraryError("duplicate_entry", f"Colliding archive entry path: {rel_posix}")
            seen_casefold.add(folded)
            if len(entries) + 1 > MAX_SKILL_FILES:
                raise SkillLibraryError("too_many_files", f"Skill bundle exceeds {MAX_SKILL_FILES} files")
            if info.file_size > MAX_SKILL_FILE_BYTES:
                raise SkillLibraryError("file_too_large", f"Archive entry '{rel_posix}' exceeds {MAX_SKILL_FILE_BYTES} bytes")
            if total_bytes + info.file_size > MAX_SKILL_TOTAL_BYTES:
                raise SkillLibraryError("bundle_too_large", f"Skill bundle exceeds {MAX_SKILL_TOTAL_BYTES} bytes")

            chunks: list[bytes] = []
            read_bytes = 0
            with zf.open(info, "r") as handle:
                while True:
                    chunk = handle.read(65536)
                    if not chunk:
                        break
                    read_bytes += len(chunk)
                    if read_bytes > MAX_SKILL_FILE_BYTES:
                        raise SkillLibraryError("file_too_large", f"Archive entry '{rel_posix}' exceeds {MAX_SKILL_FILE_BYTES} bytes")
                    if total_bytes + read_bytes > MAX_SKILL_TOTAL_BYTES:
                        raise SkillLibraryError("bundle_too_large", f"Skill bundle exceeds {MAX_SKILL_TOTAL_BYTES} bytes")
                    chunks.append(chunk)
            total_bytes += read_bytes
            entries.append((rel_posix, b"".join(chunks)))

        return entries


def _manifest_for_entries(entries: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for rel_posix, data in sorted(entries, key=lambda item: item[0]):
        name = PurePosixPath(rel_posix).name
        suffix = PurePosixPath(rel_posix).suffix.lower()
        manifest.append(
            {
                "path": rel_posix,
                "relative_path": rel_posix,
                "name": name,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "can_open": suffix in DOCUMENT_TYPES,
            }
        )
    return manifest


class SkillsLibrary:
    """Manage local versioned Skills stored under task_root / 'skills'."""

    def __init__(self, task_root: Path, *, store: BusinessStore | None = None):
        self.task_root = Path(task_root).resolve()
        self.skills_root = self.task_root / "skills"
        self.skills_root.mkdir(parents=True, exist_ok=True)
        self.store = store or BusinessStore(self.task_root / "tasks.db")

    def list(self, search: str = "") -> list[dict[str, Any]]:
        if not isinstance(search, str) or len(search) > 256:
            raise ValueError("Invalid search")
        return [self._summary_view(item) for item in self.store.list_skills(search)]

    def local_skills(self) -> dict[str, Any]:
        """Read immediate Skill folders in common Agent homes without executing or importing them."""
        roots = []
        candidates: dict[str, dict[str, Any]] = {}
        remaining_entries = MAX_LOCAL_SKILL_ENTRIES
        remaining_bytes = MAX_LOCAL_SKILL_SCAN_BYTES
        truncated = False
        for agent in (".agents", ".codex", ".claude"):
            source = Path.home() / agent / "skills"
            root = {"id": agent, "label": f"~/{agent}/skills", "path": str(source), "status": "ready", "count": 0}
            roots.append(root)
            try:
                # Resolve common installation links once; bundle links remain subject to normal import validation.
                resolved_source = source.resolve(strict=True)
                if not resolved_source.is_dir():
                    root["status"] = "unavailable"
                    continue
                if remaining_entries <= 0 or remaining_bytes <= 0:
                    root["status"] = "limited"
                    truncated = True
                    continue
                with os.scandir(resolved_source) as entries:
                    children = list(islice(entries, remaining_entries + 1))
                if len(children) > remaining_entries:
                    truncated = True
                    root["status"] = "limited"
                children = sorted(children[:remaining_entries], key=lambda item: item.name.casefold())
                remaining_entries -= len(children)
            except FileNotFoundError:
                root["status"] = "missing"
                continue
            except (OSError, RuntimeError):
                root["status"] = "unavailable"
                continue

            for child in children:
                if child.name.startswith("."):
                    continue
                item = None
                try:
                    folder = Path(child.path).resolve(strict=True)
                    if not folder.is_dir():
                        continue
                    skill_md = next((folder / name for name in ("SKILL.md", "skill.md") if (folder / name).is_file()), None)
                    if skill_md is None:
                        continue
                    key = os.path.normcase(str(folder))
                    if key in candidates:
                        if agent not in candidates[key]["sources"]:
                            candidates[key]["sources"].append(agent)
                            root["count"] += 1
                        continue
                    item = {"path": str(folder), "name": child.name, "description": "", "sources": [agent], "error_code": ""}
                    candidates[key] = item
                    root["count"] += 1
                    if _is_reparse_or_symlink(skill_md) or _has_reparse_ancestor(folder):
                        item["error_code"] = "symlink_rejected"
                        continue
                    if remaining_bytes <= 0:
                        truncated = True
                        root["status"] = "limited"
                        item["error_code"] = "bundle_too_large"
                        break
                    size = skill_md.stat().st_size
                    if size > MAX_SKILL_MD_BYTES:
                        item["error_code"] = "file_too_large"
                        continue
                    if size > remaining_bytes:
                        truncated = True
                        root["status"] = "limited"
                        item["error_code"] = "bundle_too_large"
                        break
                    try:
                        raw = _read_bounded_file(skill_md, MAX_SKILL_MD_BYTES, remaining_bytes)
                    except SkillLibraryError:
                        remaining_bytes -= min(MAX_SKILL_MD_BYTES, remaining_bytes)
                        raise
                    remaining_bytes -= len(raw)
                    metadata, _, _ = _validate_utf8_frontmatter(raw)
                    if not all(isinstance(metadata.get(field), str) and metadata[field].strip() for field in ("name", "description")):
                        item["error_code"] = "invalid_frontmatter"
                        continue
                    item["name"] = metadata["name"].strip()[:128]
                    item["description"] = metadata["description"].strip()[:1024]
                except SkillLibraryError as error:
                    item["error_code"] = error.code
                except (OSError, RuntimeError):
                    # A removed/unreadable folder cannot prevent discovery in the remaining roots.
                    if item is not None:
                        item["error_code"] = "invalid_source"

        return {"roots": roots, "skills": list(candidates.values()), "truncated": truncated}

    def get(self, skill_id: str) -> dict[str, Any]:
        sid = required_id(skill_id, "skill ID")
        skill = self.store.get_skill(sid)
        if skill is None:
            raise KeyError(sid)
        return self._detail_view(skill)

    def get_revision(self, skill_id: str, version: int) -> dict[str, Any]:
        sid = required_id(skill_id, "skill ID")
        if type(version) is not int or version < 1:
            raise ValueError("Invalid skill version")
        revision = self.store.get_skill_revision(sid, version)
        if revision is None:
            raise KeyError(f"{sid}@{version}")
        return revision

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Invalid skill payload")
        sid = required_id(payload.get("skill_id"), "skill ID")
        existing = self.store.get_skill(sid)
        expected_updated_at = payload.get("expected_updated_at")
        if expected_updated_at is not None and not isinstance(expected_updated_at, str):
            raise ValueError("Invalid expected_updated_at")

        enabled = payload.get("enabled", existing["enabled"] if existing else True)
        if not isinstance(enabled, bool):
            raise ValueError("Invalid enabled flag")

        if "content" not in payload or payload.get("content") is None:
            if existing is None:
                raise ValueError("Skill content is required")
            if expected_updated_at is not None and expected_updated_at != existing["updated_at"]:
                raise TaskConflict("The skill changed. Refresh before saving.")
            if existing["enabled"] == enabled:
                return self._detail_view(existing)
            timestamp = now()
            with self.store.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT * FROM task_skills WHERE skill_id=?", (sid,)).fetchone()
                if row is None:
                    raise KeyError(sid)
                if expected_updated_at is not None and row["updated_at"] != expected_updated_at:
                    raise TaskConflict("The skill changed. Refresh before saving.")
                data = json.loads(row["data"])
                data["enabled"] = enabled
                connection.execute(
                    "UPDATE task_skills SET enabled=?, data=?, updated_at=? WHERE skill_id=?",
                    (int(enabled), json.dumps(data, ensure_ascii=False), timestamp, sid),
                )
            return self.get(sid)

        raw_content = payload.get("content")
        if not isinstance(raw_content, str) or not raw_content.strip():
            raise SkillLibraryError("invalid_frontmatter", "SKILL.md content is required")

        content_bytes = raw_content.encode("utf-8")
        entries: list[tuple[str, bytes]] = []
        if existing is not None and payload.get("preserve_resources", True) is True:
            prev_bundle = Path(existing["bundle_path"])
            if prev_bundle.is_dir():
                for rel_posix, data in _collect_directory_entries(prev_bundle):
                    if rel_posix.casefold() != "skill.md":
                        entries.append((rel_posix, data))
        entries.append(("SKILL.md", content_bytes))
        return self._commit_entries(
            sid,
            entries,
            enabled=enabled,
            expected_updated_at=expected_updated_at,
            source_kind=existing.get("source_kind", "manual") if existing else "manual",
        )

    def import_path(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Invalid skill import payload")
        sid = required_id(payload.get("skill_id") or f"skill_{uuid.uuid4().hex[:12]}", "skill ID")
        raw_source = payload.get("path")
        if not isinstance(raw_source, str) or not raw_source.strip() or "\0" in raw_source:
            raise SkillLibraryError("invalid_source", "Import path is required")
        if ":" in raw_source[2:] if (len(raw_source) >= 2 and raw_source[1] == ":") else (":" in raw_source):
            raise SkillLibraryError("invalid_path", "Alternate data streams cannot be imported")

        source = Path(raw_source).expanduser()
        if not source.is_absolute():
            raise SkillLibraryError("invalid_source", "Import path must be an absolute path")
        if _has_reparse_ancestor(source):
            raise SkillLibraryError("symlink_rejected", "Import source cannot be or traverse a symlink or reparse point")
        try:
            exists = source.exists()
        except OSError as exc:
            raise SkillLibraryError("invalid_source", "Import path is unavailable") from exc
        if not exists:
            raise FileNotFoundError(raw_source)

        existing = self.store.get_skill(sid)
        expected_updated_at = payload.get("expected_updated_at")
        if expected_updated_at is not None and not isinstance(expected_updated_at, str):
            raise ValueError("Invalid expected_updated_at")
        enabled = payload.get("enabled", existing["enabled"] if existing else True)
        if not isinstance(enabled, bool):
            raise ValueError("Invalid enabled flag")

        if source.is_dir():
            entries = _collect_directory_entries(source)
            source_kind = "directory"
        elif source.is_file():
            if source.name in {"SKILL.md", "skill.md"}:
                entries = _collect_directory_entries(source.parent)
                source_kind = "directory"
            elif source.suffix.lower() in ARCHIVE_SUFFIXES:
                entries = _collect_archive_entries(source)
                source_kind = "archive"
            else:
                raise SkillLibraryError("invalid_source", "Import path must be a skill directory, SKILL.md, .zip, or .skill archive")
        else:
            raise SkillLibraryError("invalid_source", "Unsupported import source")

        return self._commit_entries(
            sid,
            entries,
            enabled=enabled,
            expected_updated_at=expected_updated_at,
            source_kind=source_kind,
        )

    def delete(self, skill_id: str, *, expected_updated_at: str | None = None) -> dict[str, Any]:
        sid = required_id(skill_id, "skill ID")
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT * FROM task_skills WHERE skill_id=?", (sid,)).fetchone()
            if existing is None:
                raise KeyError(sid)
            if expected_updated_at is not None and existing["updated_at"] != expected_updated_at:
                raise TaskConflict("The skill changed. Refresh before deleting.")
            connection.execute("DELETE FROM task_skills WHERE skill_id=?", (sid,))
        return {"deleted": True, "skill_id": sid}

    def files(self, skill_id: str, *, version: int | None = None) -> dict[str, Any]:
        bundle_root, record = self._resolve_bundle(skill_id, version=version)
        files = []
        for index, item in enumerate(record.get("files", [])):
            if index >= MAX_SKILL_FILES:
                break
            target = (bundle_root / item["relative_path"]).resolve()
            if not target.is_relative_to(bundle_root) or not target.is_file():
                continue
            stat_res = target.stat()
            files.append(
                {
                    "path": item["relative_path"],
                    "relative_path": item["relative_path"],
                    "name": item["name"],
                    "size": stat_res.st_size,
                    "modified_at": stat_res.st_mtime,
                    "can_open": target.suffix.lower() in DOCUMENT_TYPES,
                }
            )
        return {
            "skill_id": record["skill_id"],
            "version": record["version"],
            "name": record["name"],
            "description": record["description"],
            "files": files,
            "limited": len(record.get("files", [])) > MAX_SKILL_FILES,
        }

    def preview(self, skill_id: str, relative_path: str, *, version: int | None = None) -> dict[str, Any]:
        bundle_root, _ = self._resolve_bundle(skill_id, version=version)
        normalized = _validate_relative_posix_path(relative_path)
        lexical = bundle_root / normalized
        if _has_reparse_ancestor(lexical, stop_at=bundle_root):
            raise SkillLibraryError("symlink_rejected", "Skill resource cannot be a symlink or reparse point")
        target = lexical.resolve()
        if target == bundle_root or not target.is_relative_to(bundle_root):
            raise SkillLibraryError("invalid_path", "Path escapes skill bundle")
        if os.name == "nt" and ":" in str(target)[len(target.anchor):]:
            raise SkillLibraryError("invalid_path", "Alternate data streams cannot be browsed")
        if not target.is_file():
            raise FileNotFoundError(normalized)

        suffix = target.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            from utilities.attachment_preview import attachment_image_url
            return {"kind": "image", "url": attachment_image_url({"path": str(target), "thumbnail": False}), "path": normalized}
        if suffix in PREVIEW_TEXT_TYPES or target.name in {"SKILL.md", "skill.md"}:
            with target.open("rb") as handle:
                content = handle.read(MAX_PREVIEW_BYTES + 1)
            return {
                "kind": "text",
                "text": content[:MAX_PREVIEW_BYTES].decode("utf-8", errors="replace"),
                "truncated": len(content) > MAX_PREVIEW_BYTES,
                "markdown": suffix == ".md",
                "path": normalized,
            }
        return {"kind": "unsupported", "path": normalized}

    def _resolve_bundle(self, skill_id: str, *, version: int | None = None) -> tuple[Path, dict[str, Any]]:
        sid = required_id(skill_id, "skill ID")
        if version is not None:
            record = self.get_revision(sid, version)
        else:
            record = self.store.get_skill(sid)
            if record is None:
                raise KeyError(sid)
        bundle_root = Path(record["bundle_path"]).resolve()
        if not bundle_root.is_relative_to(self.skills_root.resolve()) or not bundle_root.is_dir():
            raise FileNotFoundError(sid)
        return bundle_root, record

    def open_directory(self, skill_id: str, *, version: int | None = None) -> dict[str, bool]:
        bundle_root, _ = self._resolve_bundle(skill_id, version=version)
        if _has_reparse_ancestor(bundle_root, self.skills_root):
            raise SkillLibraryError("symlink_rejected", "Managed Skill directory cannot traverse a link")
        if os.name == "nt":
            os.startfile(bundle_root)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(bundle_root)])
        return {"opened": True}

    def _commit_entries(
        self,
        skill_id: str,
        entries: list[tuple[str, bytes]],
        *,
        enabled: bool,
        expected_updated_at: str | None,
        source_kind: str,
    ) -> dict[str, Any]:
        skill_md_entries = [(path, data) for path, data in entries if path in {"SKILL.md", "skill.md"}]
        if not skill_md_entries:
            raise SkillLibraryError("missing_skill_md", "Missing required file: SKILL.md", diagnostics=["Missing required file: SKILL.md"])
        _, skill_md_bytes = skill_md_entries[0]
        metadata, _, content = _validate_utf8_frontmatter(skill_md_bytes)

        raw_name = metadata.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise SkillLibraryError(
                "invalid_frontmatter",
                "Missing or empty 'name' in SKILL.md frontmatter",
                diagnostics=["Missing required field in frontmatter: name"],
            )

        staging_base = self.skills_root / ".staging"
        staging_base.mkdir(parents=True, exist_ok=True)
        staging_root = staging_base / f"tmp_{uuid.uuid4().hex}"
        safe_leaf = (
            _validate_relative_posix_path(raw_name.strip())
            if "/" not in raw_name.strip() and "\\" not in raw_name.strip() and ":" not in raw_name.strip()
            else "skill"
        )
        staged_bundle = staging_root / safe_leaf

        try:
            staged_bundle.mkdir(parents=True, exist_ok=False)
            normalized_entries: list[tuple[str, bytes]] = []
            seen_canonical_fold: set[str] = set()
            total_bytes = 0
            for rel_posix, data in sorted(entries, key=lambda item: item[0]):
                validated_rel = _validate_relative_posix_path(rel_posix)
                canonical_rel = "SKILL.md" if validated_rel in {"SKILL.md", "skill.md"} else validated_rel
                folded = _canonical_fold_key(canonical_rel)
                if folded in seen_canonical_fold:
                    raise SkillLibraryError("duplicate_entry", f"Colliding skill file path: {canonical_rel}")
                seen_canonical_fold.add(folded)
                if len(normalized_entries) + 1 > MAX_SKILL_FILES:
                    raise SkillLibraryError("too_many_files", f"Skill bundle exceeds {MAX_SKILL_FILES} files")
                if len(data) > MAX_SKILL_FILE_BYTES:
                    raise SkillLibraryError("file_too_large", f"Skill file '{canonical_rel}' exceeds {MAX_SKILL_FILE_BYTES} bytes")
                total_bytes += len(data)
                if total_bytes > MAX_SKILL_TOTAL_BYTES:
                    raise SkillLibraryError("bundle_too_large", f"Skill bundle exceeds {MAX_SKILL_TOTAL_BYTES} bytes")
                dest = (staged_bundle / canonical_rel).resolve()
                if not dest.is_relative_to(staged_bundle.resolve()):
                    raise SkillLibraryError("invalid_path", f"Skill file escapes bundle: {canonical_rel}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                normalized_entries.append((canonical_rel, data))

            diagnostics = validate_with_diagnostics(staged_bundle, validation_mode="strict")
            if diagnostics.errors:
                raise SkillLibraryError(
                    "invalid_skill",
                    "; ".join(diagnostics.errors),
                    diagnostics=diagnostics.errors,
                )
            try:
                loaded = read_skill(staged_bundle, validation_mode="strict")
            except (SkillValidationError, SkillParseError, SkillError) as exc:
                raise SkillLibraryError("invalid_skill", str(exc), diagnostics=[str(exc)]) from exc

            manifest = _manifest_for_entries(normalized_entries)
            bundle_digest = hashlib.sha256(
                json.dumps([(item["path"], item["sha256"]) for item in manifest], separators=(",", ":")).encode("utf-8")
            ).hexdigest()

            published_rev_parent: Path | None = None
            try:
                with self.store.connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    existing_row = connection.execute("SELECT * FROM task_skills WHERE skill_id=?", (skill_id,)).fetchone()
                    existing = self.store._skill(existing_row)
                    if existing is not None:
                        if expected_updated_at is not None and expected_updated_at != existing["updated_at"]:
                            raise TaskConflict("The skill changed. Refresh before saving.")
                        if existing.get("bundle_digest") == bundle_digest and existing["enabled"] == enabled:
                            return self._detail_view(existing)
                    elif expected_updated_at is not None:
                        raise KeyError(skill_id)

                    max_rev_row = connection.execute(
                        "SELECT coalesce(max(version), 0) AS max_v FROM task_skill_revisions WHERE skill_id=?",
                        (skill_id,),
                    ).fetchone()
                    next_version = int(max_rev_row["max_v"]) + 1
                    rev_parent = (self.skills_root / skill_id / f"rev_{next_version}").resolve()
                    final_dir = (rev_parent / loaded.properties.name).resolve()
                    if not rev_parent.is_relative_to(self.skills_root.resolve()) or not final_dir.is_relative_to(rev_parent):
                        raise SkillLibraryError("invalid_path", "Resolved skill bundle path escapes storage")
                    if rev_parent.exists():
                        raise TaskConflict("Skill revision directory already exists")
                    rev_parent.mkdir(parents=True, exist_ok=False)
                    published_rev_parent = rev_parent
                    shutil.move(str(staged_bundle), str(final_dir))

                    timestamp = now()
                    created_at = existing["created_at"] if existing else timestamp
                    record_data = {
                        "skill_id": skill_id,
                        "name": loaded.properties.name,
                        "description": loaded.properties.description,
                        "license": loaded.properties.license,
                        "compatibility": loaded.properties.compatibility,
                        "allowed_tools": loaded.properties.allowed_tools,
                        "metadata": dict(loaded.properties.metadata or {}),
                        "warnings": list(loaded.warnings or []),
                        "instructions": loaded.instructions,
                        "content": content,
                        "source_kind": source_kind,
                        "bundle_path": str(final_dir),
                        "skill_md_path": str(final_dir / "SKILL.md"),
                        "bundle_digest": bundle_digest,
                        "files": manifest,
                        "file_count": len(manifest),
                        "total_bytes": sum(item["size"] for item in manifest),
                    }

                    connection.execute(
                        "INSERT INTO task_skill_revisions(skill_id, version, bundle_path, data, created_at) VALUES(?,?,?,?,?)",
                        (skill_id, next_version, str(final_dir), json.dumps(record_data, ensure_ascii=False), timestamp),
                    )
                    connection.execute(
                        """INSERT INTO task_skills(skill_id, name, description, enabled, version, data, created_at, updated_at)
                           VALUES(?,?,?,?,?,?,?,?)
                           ON CONFLICT(skill_id) DO UPDATE SET
                           name=excluded.name,
                           description=excluded.description,
                           enabled=excluded.enabled,
                           version=excluded.version,
                           data=excluded.data,
                           updated_at=excluded.updated_at""",
                        (
                            skill_id,
                            loaded.properties.name,
                            loaded.properties.description,
                            int(enabled),
                            next_version,
                            json.dumps(record_data, ensure_ascii=False),
                            created_at,
                            timestamp,
                        ),
                    )
                    saved = self.store._skill(
                        connection.execute("SELECT * FROM task_skills WHERE skill_id=?", (skill_id,)).fetchone()
                    )
                published_rev_parent = None
                return self._detail_view(saved)
            except BaseException:
                if (
                    published_rev_parent is not None
                    and published_rev_parent.is_relative_to(self.skills_root.resolve())
                    and published_rev_parent != self.skills_root.resolve()
                ):
                    shutil.rmtree(published_rev_parent, ignore_errors=True)
                raise
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)

    @staticmethod
    def _summary_view(skill: dict[str, Any]) -> dict[str, Any]:
        return {
            "skill_id": skill["skill_id"],
            "name": skill["name"],
            "description": skill["description"],
            "enabled": bool(skill["enabled"]),
            "version": skill["version"],
            "source_kind": skill.get("source_kind", "manual"),
            "license": skill.get("license"),
            "compatibility": skill.get("compatibility"),
            "allowed_tools": skill.get("allowed_tools"),
            "metadata": dict(skill.get("metadata") or {}),
            "warnings": list(skill.get("warnings") or []),
            "file_count": skill.get("file_count", len(skill.get("files", []))),
            "total_bytes": skill.get("total_bytes", 0),
            "created_at": skill["created_at"],
            "updated_at": skill["updated_at"],
        }

    def _detail_view(self, skill: dict[str, Any]) -> dict[str, Any]:
        return {
            **self._summary_view(skill),
            "content": skill.get("content", ""),
            "instructions": skill.get("instructions", ""),
            "files": [
                {
                    "path": item["path"],
                    "relative_path": item["relative_path"],
                    "name": item["name"],
                    "size": item["size"],
                    "can_open": item.get("can_open", False),
                }
                for item in skill.get("files", [])
            ],
        }
