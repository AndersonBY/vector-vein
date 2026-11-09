"""Read-only virtual knowledge paths. Pure helpers never open a store or index."""
from collections import Counter
import hashlib
import json
import re
import unicodedata

from .storage import KnowledgeError, identifier


_FIELDS = "id,kb_id,parent_id,kind,name,status,generation,active_token,updated_at"


def mount_aliases(mounts) -> dict[str, str]:
    if not isinstance(mounts, list) or len(mounts) > 20:
        raise KnowledgeError("invalid_scope", "Select at most 20 knowledge mounts.")
    names = {}
    for mount in mounts:
        if not isinstance(mount, dict) or set(mount) != {"kb_id", "name"} or not isinstance(mount["name"], str):
            raise KnowledgeError("invalid_scope", "Invalid frozen knowledge mounts.")
        key = identifier(mount["kb_id"])
        if key in names:
            raise KnowledgeError("invalid_scope", "Knowledge mounts must be unique.")
        normalized = unicodedata.normalize("NFKC", mount["name"])
        slug = "".join(char if char.isalnum() or char in "-_" else "-" for char in normalized)
        names[key] = re.sub("-+", "-", slug).strip("-_")[:120] or "knowledge"
    counts = Counter(name.casefold() for name in names.values())
    aliases = {key: name if counts[name.casefold()] == 1 else f"{name}--{key}" for key, name in names.items()}
    # A user name can itself resemble another mount's generated suffix.
    if len({alias.casefold() for alias in aliases.values()}) != len(aliases):
        aliases = {key: f"{name}--{key}" for key, name in names.items()}
    return {alias: key for key, alias in sorted(aliases.items(), key=lambda pair: (pair[1].casefold(), pair[0]))}


def _path(value):
    if (not isinstance(value, str) or not value or len(value) > 8192 or "\\" in value or ":" in value
            or re.search(r"%[0-9a-fA-F]{2}", value) or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise KnowledgeError("invalid_path", "Use a literal path inside .knowledge without traversal or encoded separators.")
    path = value[:-1] if value.endswith("/") else value
    parts = path.split("/")
    if parts[0] != ".knowledge" or any(part in {"", ".", ".."} for part in parts):
        raise KnowledgeError("invalid_path", "Use a literal path inside .knowledge without traversal or encoded separators.")
    return path, parts


def validate_arguments(arguments):
    if not isinstance(arguments, dict):
        raise KnowledgeError("invalid_input", "Invalid knowledge file request.")
    action = arguments.get("action")
    if not isinstance(action, str) or action not in {"list", "stat", "read"}:
        raise KnowledgeError("read_only", "Knowledge paths are read-only; use list, stat or read.")
    allowed = {"action", "path"}
    if action == "list":
        allowed |= {"offset", "limit", "recursive"}
    if action == "read":
        allowed |= {"offset", "limit", "expected_version"}
    if set(arguments) - allowed:
        raise KnowledgeError("invalid_input", "Invalid knowledge file request fields.")
    args = dict(arguments)
    args["path"] = _path(args.get("path", ".knowledge"))[0]
    if action != "stat":
        maximum = 5000 if action == "list" else 262144
        offset = args.setdefault("offset", 0)
        limit = args.setdefault("limit", 1000 if action == "list" else 65536)
        if (type(offset) is not int or not 0 <= offset <= (10000 if action == "list" else 4_000_000)
                or type(limit) is not int or not 1 <= limit <= maximum):
            raise KnowledgeError("invalid_input", "Knowledge file pagination is outside its supported bounds.")
    if action == "list" and type(args.setdefault("recursive", True)) is not bool:
        raise KnowledgeError("invalid_input", "Recursive must be a boolean.")
    if "expected_version" in args and (not isinstance(args["expected_version"], str) or not 1 <= len(args["expected_version"]) <= 256):
        raise KnowledgeError("invalid_input", "Expected version must be a nonempty version string.")
    return args


def _version(row):
    stamp = [row["kb_id"], row["id"], row["path"], row["generation"], row["active_token"], row["updated_at"]]
    return hashlib.sha256(json.dumps(stamp, ensure_ascii=False).encode("utf-8")).hexdigest()


def _entry(row):
    result = {"path": row["path"], "name": row["name"], "kind": row["kind"], "kb_id": row["kb_id"],
              "status": row["status"], "modified_at": row["updated_at"]}
    if row["kind"] == "file":
        result.update(document_id=row["id"], version=_version(row))
    else:
        result["size"] = 0
    return result


def _resolve(db, aliases, bases, path):
    _, parts = _path(path)
    if len(parts) == 1:
        return {"id": None, "kb_id": None, "parent_id": None, "kind": "folder", "name": ".knowledge",
                "status": "ready", "generation": 0, "active_token": None, "updated_at": None, "path": ".knowledge"}
    alias = parts[1]
    kb_id = aliases.get(alias)
    if kb_id is None:
        raise KnowledgeError("not_found", "The knowledge path is unavailable in this task's mounts.", 404)
    row = {"id": None, "kb_id": kb_id, "parent_id": None, "kind": "folder", "name": alias,
           "status": "ready", "generation": 0, "active_token": None, "updated_at": bases[kb_id],
           "path": ".knowledge/" + alias}
    for name in parts[2:]:
        if row["kind"] != "folder":
            raise KnowledgeError("not_found", "The knowledge path no longer exists.", 404)
        child = db.execute(f"SELECT {_FIELDS} FROM items WHERE kb_id=? AND parent_id IS ? AND name=?",
                           (kb_id, row["id"], name)).fetchone()
        if child is None:
            raise KnowledgeError("not_found", "The knowledge path no longer exists.", 404)
        row = {**dict(child), "path": row["path"] + "/" + child["name"]}
    return row


def _list(db, aliases, bases, source, args):
    if source["kind"] != "folder":
        raise KnowledgeError("invalid_path", "List requires a knowledge directory.")
    if source["kb_id"] is None:
        roots = [{"id": None, "kb_id": key, "parent_id": None, "kind": "folder", "name": alias,
                  "status": "ready", "generation": 0, "active_token": None, "updated_at": bases[key],
                  "path": ".knowledge/" + alias} for alias, key in aliases.items()]
        min_depth = 0
    else:
        roots, min_depth = [source], 1
    if not roots:
        return {"entries": [], "total": 0, "next_offset": None, "truncated": False}
    columns = _FIELDS.split(",") + ["path"]
    values = [value for root in roots for value in [*(root[key] for key in columns), 0]]
    seed = ",".join("(" + ",".join("?" for _ in range(len(columns) + 1)) + ")" for _ in roots)
    # Only authorized roots enter the recursive query; children must retain their KB.
    cte = f"""WITH RECURSIVE tree({','.join(columns)},depth) AS (
        VALUES {seed}
        UNION ALL
        SELECT {','.join('i.' + key for key in _FIELDS.split(','))},t.path||'/'||i.name,t.depth+1
        FROM items i JOIN tree t ON i.kb_id=t.kb_id AND i.parent_id IS t.id
        WHERE t.kind='folder' AND (? OR t.depth<?)
    ) """
    params = [*values, args["recursive"], min_depth]
    where = " WHERE depth>=?"
    total = db.execute(cte + "SELECT count(*) FROM tree" + where, [*params, min_depth]).fetchone()[0]
    rows = db.execute(cte + "SELECT * FROM tree" + where + " ORDER BY path COLLATE NOCASE,path,id LIMIT ? OFFSET ?",
                      [*params, min_depth, args["limit"], args["offset"]])
    entries = [_entry(row) for row in rows]
    next_offset = args["offset"] + len(entries)
    more = next_offset < total
    return {"entries": entries, "total": total, "next_offset": next_offset if more and next_offset <= 10000 else None,
            "truncated": more}


def virtual_operation(service, mounts, arguments):
    args = validate_arguments(arguments)
    aliases = mount_aliases(mounts)
    with service._lock:
        service._assert_owner()
        service.selected_bases(list(aliases.values()))
        db = service._db
        bases = {row["id"]: row["updated_at"] for row in db.execute(
            "SELECT id,updated_at FROM bases WHERE id IN (" + ",".join("?" for _ in aliases) + ")", list(aliases.values()))}
        source = _resolve(db, aliases, bases, args["path"])
        if args["action"] == "list":
            return _list(db, aliases, bases, source, args)
        entry = _entry(source)
        if args["action"] == "stat":
            if source["kind"] == "file":
                entry["size"] = db.execute("SELECT length(CAST(extracted_text AS BLOB)) FROM items WHERE id=? AND kb_id=?",
                                           (source["id"], source["kb_id"])).fetchone()[0]
            return entry
        if source["kind"] != "file":
            raise KnowledgeError("invalid_path", "Read requires a knowledge document.")
        version = entry["version"]
        if args.get("expected_version", version) != version:
            raise KnowledgeError("stale_source", "The source changed. Stat it again and restart reading from offset zero.", 409)
        row = db.execute("SELECT length(extracted_text) AS total,substr(extracted_text,?,?) AS text FROM items WHERE id=? AND kb_id=?",
                         (args["offset"] + 1, args["limit"], source["id"], source["kb_id"])).fetchone()
        if not row["total"]:
            if source["status"] in {"queued", "indexing"}:
                raise KnowledgeError("indexing", "The source is still being extracted. Retry after indexing progresses.")
            raise KnowledgeError("source_unavailable", "Extracted text is unavailable for this source. Check indexing status.")
        next_offset = args["offset"] + len(row["text"])
        return {"path": args["path"], "text": row["text"], "offset": args["offset"], "total": row["total"],
                "next_offset": next_offset if next_offset < row["total"] else None, "version": version}
