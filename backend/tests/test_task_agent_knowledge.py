"""Task authority and real FunctionTool execution against the private bridge."""
from copy import deepcopy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest
import uvicorn
from vv_agent.tools.outputs import ToolOutputError, ToolOutputJson

from task_agent import knowledge
from task_agent.config import build_model_snapshot
from task_agent.host import DesktopTaskAgentHost
from task_agent.service import TaskAgentService
from task_agent.store import BusinessStore, now

KB_A, KB_B, DOCUMENT, FOLDER = "a" * 32, "b" * 32, "d" * 32, "e" * 32
SETTINGS = {"VERSION": "2", "endpoints": [{"id": "test", "api_base": "http://127.0.0.1:1/v1", "api_key": "synthetic"}],
            "backends": {"local": {"models": {"test": {"id": "test", "endpoints": ["test"], "function_call_available": True}}}}}


def snapshot(ids=(KB_A,)):
    value = build_model_snapshot(SETTINGS, "local", "test")
    value["agent_profile"] = {"knowledge_base_ids": list(ids), "allow_shell": False,
                              "allow_file_writes": False, "allow_sub_agents": True, "permission_mode": "ask"}
    value["knowledge_bases"] = [{"kb_id": identity, "name": "Sources"} for identity in ids]
    return value


def save_task(root, identity="task", frozen=None):
    frozen = snapshot() if frozen is None else frozen
    stamp = now()
    store = BusinessStore(root / "tasks.db")
    store.create_task(dict(tid=identity, thread_id=identity, title="Test", goal="Test", status="PENDING",
                           current_turn_id=f"{identity}/turn/1", model_provider="local", model="test",
                           reasoning_effort="default", config_snapshot=frozen, created_at=stamp, updated_at=stamp))
    return store


class Sources:
    def __init__(self):
        self.present = {KB_A, KB_B}
        self.calls = []

    def selected_bases(self, ids):
        if not set(ids).issubset(self.present):
            raise ValueError("deleted base /private/data")
        return [{"kb_id": identity, "name": "Sources"} for identity in ids]

    def dispatch(self, operation, payload):
        self.calls.append((operation, payload))
        return {"results": [{"kb_id": payload["kb_ids"][0], "document_id": DOCUMENT,
                             "chunk_id": "c" * 32, "path": "manual/guide.txt", "text": "source evidence"}],
                "warnings": []}

    def browse(self, kb_ids, folder_id=None, offset=0, limit=50):
        from knowledge_base import KnowledgeError
        if folder_id is not None and (folder_id != FOLDER or KB_A not in kb_ids):
            raise KnowledgeError("invalid_scope", "Unlisted folder at C:/private/secret")
        self.calls.append(("browse", {"kb_ids": kb_ids, "folder_id": folder_id, "offset": offset, "limit": limit}))
        rows = ([{"id": DOCUMENT, "kb_id": KB_A, "parent_id": FOLDER, "kind": "file", "name": "guide.txt",
                  "path": "manual/guide.txt", "status": "ready", "chunk_count": 310, "error_code": ""}]
                if folder_id else [{"id": FOLDER if identity == KB_A else "f" * 32, "kb_id": identity,
                                    "parent_id": None, "kind": "folder", "name": "manual", "path": "manual",
                                    "status": "ready", "chunk_count": 0, "error_code": ""} for identity in kb_ids])
        return {"bases": [{"kb_id": identity, "name": "Sources", "document_count": 3,
                           "keyword_documents": 3, "semantic_documents": 3, "status_counts": {"ready": 3}}
                          for identity in kb_ids],
                "items": rows[offset:offset + limit], "total": len(rows), "offset": offset, "limit": limit,
                "next_offset": offset + limit if offset + limit < len(rows) else None}

    def read_document(self, kb_ids, document_id, offset=0, limit=12000):
        self.calls.append(("read", {"kb_ids": kb_ids, "document_id": document_id}))
        if document_id != DOCUMENT or KB_A not in kb_ids:
            raise ValueError("not found /private/path")
        return {"kb_id": KB_A, "document_id": DOCUMENT, "path": "manual/guide.txt", "text": "source evidence"[offset:offset + limit]}


@pytest.fixture
def owner(tmp_path, monkeypatch):
    import knowledge_base
    from task_agent import service
    sources = Sources()
    monkeypatch.setattr(knowledge_base, "knowledge_service", lambda: sources)
    monkeypatch.setattr(knowledge_base, "selected_bases", sources.selected_bases)
    monkeypatch.setattr(service, "task_agent_service", lambda: SimpleNamespace(task_root=tmp_path))
    save_task(tmp_path)
    save_task(tmp_path, "other", snapshot((KB_B,)))
    app = FastAPI()
    knowledge.install_knowledge_routes(app)
    knowledge.start_knowledge_bridge("http://127.0.0.1:9876")
    yield SimpleNamespace(root=tmp_path, sources=sources, app=app)
    knowledge.stop_knowledge_bridge()


def payload(**changes):
    return {"task_id": "task", "mounts": snapshot()["knowledge_bases"], "arguments": {"query": "source"}, **changes}


def client(owner, host="127.0.0.1"):
    return TestClient(owner.app, base_url="http://127.0.0.1", client=(host, 1234))


def post(owner, body, *, token=None, host="127.0.0.1", operation="search", **headers):
    with client(owner, host) as conn:
        return conn.post(knowledge._PATH + "/" + operation, json=body,
                         headers={"Authorization": "Bearer " + (token or knowledge._token), **headers})


def test_bridge_dispatch_is_bound_to_saved_task_and_requested_scope(owner):
    result = post(owner, payload())
    assert result.status_code == 200
    assert result.json()["results"][0]["path"] == "manual/guide.txt"
    assert owner.sources.calls == [("search", {"query": "source", "kb_ids": [KB_A]})]
    narrowed = snapshot((KB_A, KB_B))
    save_task(owner.root, "both", narrowed)
    assert post(owner, payload(task_id="both", mounts=narrowed["knowledge_bases"],
                               arguments={"query": "source", "kb_ids": [KB_B]})).status_code == 200
    assert owner.sources.calls[-1][1]["kb_ids"] == [KB_B]


@pytest.mark.parametrize("changes", [
    {"task_id": "missing"}, {"task_id": "other"}, {"task_id": "../../tasks"},
    {"mounts": [{"kb_id": KB_B, "name": "Sources"}]},
    {"arguments": {"query": "source", "kb_ids": [KB_B]}},
    {"arguments": {"query": "source", "kb_ids": []}},
    {"arguments": {"query": "source", "kb_ids": [KB_A, KB_A]}},
    {"arguments": {"query": "source", "path": "C:/private"}},
    {"arguments": {"query": "source", "limit": True}},
    {"arguments": {"query": "source", "limit": 21}},
])
def test_bridge_rejects_scope_forgery_and_arbitrary_paths(owner, changes):
    result = post(owner, payload(**changes))
    assert result.status_code == 400
    assert owner.sources.calls == []
    assert "/private" not in result.text


@pytest.mark.parametrize("options", [{"token": "wrong"}, {"host": "192.0.2.1"}, {"origin": "http://malicious.invalid"}])
def test_bridge_requires_private_auth_and_loopback(owner, options):
    assert post(owner, payload(), **options).status_code == 403
    assert owner.sources.calls == []


def test_bridge_rejects_nonloopback_host_and_stopped_credentials(owner):
    with TestClient(owner.app, base_url="http://remote.invalid", client=("127.0.0.1", 1)) as conn:
        assert conn.post(knowledge._PATH + "/search", json=payload(),
                         headers={"Authorization": "Bearer " + knowledge._token}).status_code == 403
    token = knowledge._token
    knowledge.stop_knowledge_bridge()
    assert post(owner, payload(), token=token).status_code == 403
    with pytest.raises(ValueError, match="stopping"):
        knowledge._dispatch(owner.root, "search", payload())
    assert owner.sources.calls == []


def test_missing_base_and_read_scope_fail_safely(owner):
    owner.sources.present.remove(KB_A)
    result = post(owner, payload())
    assert result.status_code == 400
    assert "/private" not in result.text
    assert owner.sources.calls == []
    owner.sources.present.add(KB_A)
    assert post(owner, payload(arguments={"document_id": DOCUMENT}), operation="read").status_code == 200
    assert post(owner, payload(arguments={"document_id": "../../secret"}), operation="read").status_code == 400
    assert post(owner, payload(arguments={"document_id": "f" * 32}), operation="read").status_code == 400


@pytest.mark.parametrize("url", ["https://127.0.0.1:1", "http://example.com:1", "http://localhost:1",
                                 "http://127.0.0.1:1/path", "http://user:secret@127.0.0.1:1",
                                 "http://127.0.0.1:1?token=secret"])
def test_bridge_endpoint_cannot_redirect_credentials(url):
    with pytest.raises(ValueError):
        knowledge.start_knowledge_bridge(url)


@pytest.mark.parametrize("mutate", [
    lambda s: s["knowledge_bases"].append({"kb_id": KB_B, "name": "Sources"}),
    lambda s: s["agent_profile"]["knowledge_base_ids"].append(KB_B),
    lambda s: s["knowledge_bases"][0].update(name="forged"),
    lambda s: s.update(knowledge_bases=[]),
])
def test_host_rejects_tampered_snapshot_at_all_admission_points(owner, mutate):
    forged = snapshot()
    mutate(forged)
    host = DesktopTaskAgentHost(owner.root, settings_loader=lambda: SETTINGS)
    cwd = str(owner.root / "workspaces" / "task")
    request = SimpleNamespace(thread_id="task", cwd=cwd, metadata={"model_snapshot": forged})
    assert not host.authorize("connection", "thread/start",
                              {"agentKey": "desktop-task", "inputId": "task", "cwd": cwd, "metadata": request.metadata})
    with pytest.raises(ValueError):
        host.resolve_agent(request)
    with pytest.raises(ValueError):
        host.build_run_config(request)


def test_no_mount_no_tool_and_mounted_child_inherits_bound_function_tools(owner):
    from vv_agent.session.delegation import configured_agent
    for identity, frozen in (("task", snapshot()), ("bare", snapshot(()))):
        if identity == "bare":
            save_task(owner.root, identity, frozen)
        request = SimpleNamespace(thread_id=identity, cwd=str(owner.root / "workspaces" / identity),
                                  metadata={"model_snapshot": frozen})
        host = DesktopTaskAgentHost(owner.root, settings_loader=lambda: SETTINGS)
        agent = host.resolve_agent(request)
        config = host.build_run_config(request)
        child = configured_agent(SimpleNamespace(agent=agent), "worker", agent.sub_agents["worker"])
        expected = set(knowledge.KNOWLEDGE_TOOLS) if frozen["knowledge_bases"] else set()
        assert {t.name for t in agent.tools} == expected
        assert {t.name for t in child.tools} == expected
        assert set(knowledge.KNOWLEDGE_TOOLS).intersection(config.tool_policy.allowed_tools) == expected
        if expected:
            assert "untrusted source data" in agent.instructions
            assert "untrusted source data" in child.instructions
            assert knowledge.KNOWLEDGE_TOOLS == ["knowledge_search", "knowledge_read", "knowledge_list"]
            assert all(left is right for left, right in zip(child.tools, agent.tools))
            for instructions in (agent.instructions, child.instructions):
                assert "find_files(path='.knowledge/')" in instructions and "read-only virtual" in instructions
                assert "empty search result does not prove" in instructions
            assert all(t.needs_approval is False and str(t.tool_metadata.side_effect) == "read" for t in agent.tools)
            assert knowledge._token not in repr([t.to_openai_schema() for t in agent.tools])


def test_real_function_tools_execute_over_loopback_and_fail_closed(owner):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(owner.app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    try:
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        knowledge.start_knowledge_bridge(f"http://127.0.0.1:{port}")
        tools = knowledge.knowledge_tools(owner.root, "task", snapshot())
        result = tools[0].invoke(None, {"query": "source", "mode": "keyword"})
        assert isinstance(result, ToolOutputJson)
        assert result.data["results"][0]["document_id"] == DOCUMENT
        assert tools[1].invoke(None, {"document_id": DOCUMENT, "offset": 1, "limit": 3}).data["text"] == "our"
        listed = tools[2].invoke(None, {})
        assert listed.data["items"][0]["id"] == FOLDER
        nested = tools[2].invoke(None, {"folder_id": FOLDER, "offset": 0, "limit": 1})
        assert nested.data["items"][0]["id"] == DOCUMENT
        wildcard = tools[0].invoke(None, {"query": "*", "mode": "keyword"})
        assert isinstance(wildcard, ToolOutputError)
        assert wildcard.error_code == "invalid_query"
        assert "knowledge_list" in wildcard.message
        assert isinstance(tools[0].invoke(None, {"query": "source", "kb_ids": [KB_B]}), ToolOutputError)
        # The child process consumes the runtime secret without passing it to tool arguments.
        code = """
import os, sys
sys.path.insert(0, sys.argv[1])
from task_agent import knowledge
assert knowledge._ENV not in os.environ
tools = knowledge.knowledge_tools(__import__('pathlib').Path(sys.argv[2]), 'task', __import__('json').loads(sys.argv[3]))
assert tools[0].invoke(None, {'query': 'source'}).data['results'][0]['document_id'] == 'd' * 32
assert tools[2].invoke(None, {}).data['items'][0]['id'] == 'e' * 32
assert 'qdrant_client' not in sys.modules
"""
        child = subprocess.run([sys.executable, "-c", code, str(Path(__file__).resolve().parents[1]),
                                str(owner.root), json.dumps(snapshot())], capture_output=True, text=True, timeout=15)
        assert child.returncode == 0, child.stderr
        assert knowledge._token not in child.stdout + child.stderr
        knowledge.stop_knowledge_bridge()
        assert isinstance(tools[0].invoke(None, {"query": "source"}), ToolOutputError)
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_profile_validation_and_task_mounts_are_metadata_only(tmp_path, monkeypatch):
    import knowledge_base
    from task_agent import service as service_module
    lookups = []
    def select(ids):
        lookups.append(list(ids))
        if KB_B in ids:
            raise ValueError("missing base")
        return [{"kb_id": identity, "name": "Frozen name"} for identity in ids]
    monkeypatch.setattr(knowledge_base, "selected_bases", select)
    monkeypatch.setattr(knowledge_base, "knowledge_service", lambda: pytest.fail("Agent validation must not open index owner"))
    monkeypatch.setattr(service_module, "current_llm_settings", lambda: deepcopy(SETTINGS))
    monkeypatch.setattr("task_agent.workflows.selected_workflows", lambda ids: [])
    class Process:
        def start(self): pass
        def request(self, method, params):
            if method == "thread/start":
                return {"threadId": params["inputId"]}
            if method == "turn/start":
                return {"turnId": "task/turn/1"}
            return {}
        def stop(self): pass
    service = TaskAgentService(tmp_path, data_path=tmp_path, process=Process())
    monkeypatch.setattr(service, "_start_watching", lambda: None)
    monkeypatch.setattr(service, "get_task", lambda tid: service.store.get_task(tid))
    try:
        assert service.get_profile("general")["knowledge_base_ids"] == []
        profile = {"agent_id": "research", "name": "Research", "instructions": "Read sources", "knowledge_base_ids": [KB_A]}
        service.save_profile(profile)
        task = service.create_task({"input_id": "task", "agent_id": "research", "goal": "Find source", "model_provider": "local", "model": "test"})
        frozen = task["config_snapshot"]
        assert frozen["knowledge_bases"] == [{"kb_id": KB_A, "name": "Frozen name"}]
        assert frozen["agent_profile"]["knowledge_base_ids"] == [KB_A]
        service.save_profile({**profile, "knowledge_base_ids": []})
        assert service.store.get_task("task")["config_snapshot"] == frozen
        assert lookups == [[KB_A], [KB_A]]
        with pytest.raises(ValueError):
            service.save_profile({**profile, "knowledge_base_ids": [KB_B]})
        with pytest.raises(ValueError):
            service.save_profile({**profile, "knowledge_base_ids": [KB_A, KB_A]})
    finally:
        service.stop()


def test_bridge_network_errors_are_safe(owner, monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("SYNTHETIC_PRIVATE_TOKEN C:/private/qdrant")
    monkeypatch.setattr(knowledge, "_bridge_request", fail)
    tool = knowledge.knowledge_tools(owner.root, "task", snapshot())[0]
    output = tool.to_tool_execution_result(tool.invoke(None, {"query": "source"}))
    assert output.error_code == "knowledge_unavailable"
    assert "SYNTHETIC_PRIVATE_TOKEN" not in output.content and "C:/private" not in output.content


@pytest.mark.parametrize("real_backend", [False, True], ids=["scoped-fixture", "real-qdrant"])
def test_native_appserver_child_retrieves_via_loopback_owner(owner, monkeypatch, real_backend):
    """Real AppServer/SDK delegation; all model responses are deterministic localhost SSE."""
    from task_agent.client import AppServerProcess
    mounted_id, document_id, logical_path = KB_A, DOCUMENT, "manual/guide.txt"
    actual_service = None
    calls = owner.sources.calls
    if real_backend:
        import knowledge_base
        class Embedder:
            def get(self, value):
                return [1.0, 0.5, 0.2] if isinstance(value, str) else [[1.0, 0.5, 0.2] for text in value]
        actual_service = knowledge_base.KnowledgeService(
            owner.root / "knowledge-base", start_worker=False, embedder_factory=lambda base: Embedder(),
            reranker_factory=lambda: None)
        base = actual_service.create("Mounted manual", "deterministic", "local", embedding_dimensions=3, chunk_size=64, chunk_overlap=8)
        foreign = actual_service.create("Unmounted manual", "deterministic", "local", embedding_dimensions=3, chunk_size=64, chunk_overlap=8)
        folder = actual_service.create_folder(base["id"], "manual")
        nested = actual_service.create_folder(base["id"], "nested", folder["id"])
        document = actual_service.add_text(base["id"], "guide.txt", "source evidence from the nested manual", nested["id"])
        hidden = actual_service.add_text(foreign["id"], "secret.txt", "source evidence UNMOUNTED_PRIVATE_MARKER")
        assert actual_service.run_pending() == 2
        mounted_id, document_id, logical_path = base["id"], document["id"], "manual/nested/guide.txt"
        calls = []
        dispatch, read, browse = actual_service.dispatch, actual_service.read_document, actual_service.browse
        def tracked_dispatch(operation, arguments):
            calls.append((operation, arguments))
            result = dispatch(operation, arguments)
            assert all(hit["kb_id"] == mounted_id and hit["document_id"] == document_id for hit in result["results"])
            return result
        def tracked_read(kb_ids, document_id, **arguments):
            calls.append(("read", {"kb_ids": kb_ids, "document_id": document_id}))
            return read(kb_ids, document_id, **arguments)
        def tracked_browse(kb_ids, **arguments):
            calls.append(("browse", {"kb_ids": kb_ids, **arguments}))
            return browse(kb_ids, **arguments)
        monkeypatch.setattr(actual_service, "browse", tracked_browse)
        monkeypatch.setattr(actual_service, "dispatch", tracked_dispatch)
        monkeypatch.setattr(actual_service, "read_document", tracked_read)
        monkeypatch.setattr(knowledge_base, "knowledge_service", lambda: actual_service)
        from knowledge_base import virtual
        original_virtual = virtual.virtual_operation
        def tracked_virtual(service, mounts, arguments):
            calls.append(("vfs", {"kb_ids": [item["kb_id"] for item in mounts], **arguments}))
            result = original_virtual(service, mounts, arguments)
            assert "UNMOUNTED_PRIVATE_MARKER" not in json.dumps(result)
            return result
        monkeypatch.setattr(virtual, "virtual_operation", tracked_virtual)

    class Model(BaseHTTPRequestHandler):
        requests = []
        errors = []

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            Model.requests.append(body)
            names = {tool["function"]["name"] for tool in body.get("tools", [])}
            results = [message for message in body["messages"] if message["role"] == "tool"]
            if not set(knowledge.KNOWLEDGE_TOOLS).issubset(names):
                Model.errors.append("Knowledge tools missing from native model call")
            if "create_sub_task" in names:
                name, args = "create_sub_task", {"agent_id": "worker", "task_description": "Find the source evidence and cite its path.", "wait_for_completion": True}
                done = bool(results)
            elif real_backend:
                from knowledge_base.virtual import mount_aliases
                alias = next(iter(mount_aliases(frozen["knowledge_bases"])))
                virtual_path = ".knowledge/" + alias + "/" + logical_path
                if not results:
                    name, args, done = "find_files", {"path": ".knowledge/"}, False
                elif len(results) == 1:
                    name, args, done = "search_files", {"path": ".knowledge/", "pattern": "source", "output_mode": "content"}, False
                else:
                    name, args, done = "read_file", {"path": virtual_path}, len(results) >= 3
            elif not results:
                name, args, done = "knowledge_list", {}, False
            elif len(results) == 1:
                name, args, done = "knowledge_search", {"query": "source", "mode": "hybrid"}, False
            else:
                name, args, done = "knowledge_read", {"document_id": document_id, "limit": 100}, len(results) >= 3
            delta = {"role": "assistant", "content": f"Verified source {document_id} at {logical_path}"} if done else {
                "role": "assistant", "tool_calls": [{"index": 0, "id": f"call-{len(Model.requests)}",
                    "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
            chunks = [
                {"id": "mock", "object": "chat.completion.chunk", "created": 1, "model": "test",
                 "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                {"id": "mock", "object": "chat.completion.chunk", "created": 1, "model": "test",
                 "choices": [{"index": 0, "delta": {}, "finish_reason": "stop" if done else "tool_calls"}],
                 "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25}},
            ]
            encoded = ("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *args): pass

    model = ThreadingHTTPServer(("127.0.0.1", 0), Model)
    model_thread = threading.Thread(target=model.serve_forever, daemon=True)
    model_thread.start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(owner.app, host="127.0.0.1", port=port, log_level="error"))
    bridge_thread = threading.Thread(target=server.run, daemon=True)
    bridge_thread.start()
    settings = deepcopy(SETTINGS)
    settings["endpoints"][0]["api_base"] = f"http://127.0.0.1:{model.server_port}/v1"
    frozen = snapshot((mounted_id,))
    if real_backend:
        frozen["knowledge_bases"] = actual_service.selected_bases([mounted_id])
    frozen.update(build_model_snapshot(settings, "local", "test"))
    save_task(owner.root, "native", frozen)
    code = """
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from task_agent.host import DesktopTaskAgentHost
from vv_agent.app_server import AppServer, StdioJsonlTransport
from vv_agent.session.sqlite import SQLiteStore
root = Path(sys.argv[2])
host = DesktopTaskAgentHost(root, settings_loader=lambda: json.loads(sys.argv[3]))
store = SQLiteStore(str(root / 'sessions.db'))
server = AppServer(transport=StdioJsonlTransport(), host=host, store=store)
try:
    server.run_forever()
finally:
    host.shutdown()
    server.kernel.close()
    store.connection.close()
assert 'qdrant_client' not in sys.modules
"""
    process = AppServerProcess(owner.root, timeout=20, command=[
        sys.executable, "-X", "utf8", "-c", code, str(Path(__file__).resolve().parents[1]), str(owner.root), json.dumps(settings)])
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        knowledge.start_knowledge_bridge(f"http://127.0.0.1:{port}")
        process.start()
        process.request("thread/start", {"inputId": "native", "agentKey": "desktop-task",
                        "cwd": str(owner.root / "workspaces" / "native"), "metadata": {"model_snapshot": frozen}})
        process.request("turn/start", {"threadId": "native", "inputId": "first", "expectedTurnId": None,
                        "input": [{"type": "text", "text": "Delegate retrieval to worker and verify the source."}]})
        deadline = time.monotonic() + 65
        state = {}
        while time.monotonic() < deadline:
            state = process.request("thread/read", {"threadId": "native"})
            turns = state.get("turns", [])
            if turns and turns[-1].get("status") in {"completed", "failed"}:
                break
            assert state.get("state", {}).get("status") != "approval_wait", state
            time.sleep(.05)
        assert not Model.errors, Model.errors
        if real_backend:
            assert calls and all(call[0] == "vfs" for call in calls), calls
            assert {call[1]["action"] for call in calls} == {"list", "stat", "read"}
        else:
            assert [call[0] for call in calls] == ["browse", "search", "read"], json.dumps(
                {"state": state, "requests": Model.requests, "stderr": process.stderr_diagnostics}, ensure_ascii=False)
        assert len(Model.requests) == 6
        assert "create_sub_task" not in {tool["function"]["name"] for tool in Model.requests[1]["tools"]}
        assert knowledge._token not in json.dumps(Model.requests)
        assert all(call[1]["kb_ids"] == [mounted_id] for call in calls)
        assert knowledge._token not in json.dumps(state)
        assert state["turns"][-1]["status"] == "completed", state
        parent_result = json.dumps([message for message in Model.requests[-1]["messages"] if message["role"] == "tool"])
        assert document_id in parent_result and logical_path in parent_result
        if real_backend:
            model_data = json.dumps(Model.requests)
            assert "UNMOUNTED_PRIVATE_MARKER" not in model_data
            assert hidden["id"] not in model_data and foreign["id"] not in model_data
            assert (actual_service.root / "vectors").is_dir()
    finally:
        process.stop()
        server.should_exit = True
        bridge_thread.join(timeout=5)
        model.shutdown()
        model.server_close()
        model_thread.join(timeout=5)
        if actual_service is not None:
            actual_service.close()


@pytest.mark.parametrize("operation,arguments", [
    ("search", {"query": "x" * 4001}),
    ("read", {"document_id": DOCUMENT, "offset": 4_000_001}),
    ("read", {"document_id": DOCUMENT, "limit": 12001}),
])
def test_backend_limits_are_enforced_before_dispatch(owner, operation, arguments):
    assert post(owner, payload(arguments=arguments), operation=operation).status_code == 400
    assert owner.sources.calls == []


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "0.0.0.0", "localhost", "::", "lan-interface"])
def test_desktop_server_hosts_keep_bridge_numeric_loopback_and_no_public_kb(owner, host):
    from fastapi_server import FastAPIServer
    from threading import Event
    if host == "lan-interface":
        host = socket.gethostbyname(socket.gethostname())
        if knowledge.ipaddress.ip_address(host).is_loopback:
            pytest.skip("No local LAN interface available")
    server = FastAPIServer.__new__(FastAPIServer)
    server.host, server.port, server.actual_port = host, 0, None
    server.thread = server.server = None
    server.server_started_event = Event()
    server.fastapi_app = owner.app
    server.setup_database_retirement()
    try:
        server.start()
        knowledge._loopback_url(knowledge._endpoint)
        with httpx.Client(trust_env=False) as conn:
            base = knowledge._endpoint
            assert conn.post(base + knowledge._PATH + "/search", json=payload(),
                             headers={"Authorization": "Bearer " + knowledge._token}).status_code == 200
            assert conn.post(base + "/api/knowledge_base/search", json={"query": "private"}).status_code == 404
            assert conn.post(base + "/api/knowledge_base/import_files", json={"paths": ["C:/private"]}).status_code == 404
            retired = conn.get(base + "/api/database/list")
            assert retired.status_code == 410
            assert "desktop Knowledge bases" in retired.json()["detail"]
    finally:
        server.stop()
    assert knowledge._endpoint is None


def test_specific_lan_bind_gets_separate_owned_loopback_listener(owner):
    sockets = []
    primary = SimpleNamespace(getsockname=lambda: ("192.0.2.100", 8787))
    endpoint = knowledge.knowledge_loopback_listener(primary, sockets)
    assert len(sockets) == 1
    assert endpoint.startswith("http://127.0.0.1:")
    server = uvicorn.Server(uvicorn.Config(owner.app, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=sockets), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        knowledge.start_knowledge_bridge(endpoint)
        output = knowledge.knowledge_tools(owner.root, "task", snapshot())[0].invoke(None, {"query": "source"})
        assert isinstance(output, ToolOutputJson)
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        for listener in sockets:
            listener.close()


def test_real_metadata_validation_in_subprocess_never_starts_qdrant(tmp_path):
    from knowledge_base import KnowledgeService
    root = tmp_path / "knowledge-base"
    service = KnowledgeService(root, start_worker=False)
    try:
        base = service.create("Sources", "synthetic", "synthetic")
    finally:
        service.close()
    code = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import knowledge_base
knowledge_base._root = lambda: Path(sys.argv[2])
from task_agent.knowledge import selected_bases
assert selected_bases([sys.argv[3]]) == [{'kb_id': sys.argv[3], 'name': 'Sources'}]
assert knowledge_base._singleton is None
assert 'qdrant_client' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", code, str(Path(__file__).resolve().parents[1]), str(root), base["id"]],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert not (root / "vectors").exists()


def test_bridge_real_backend_read_and_deleted_mount(owner, monkeypatch):
    import knowledge_base
    service = knowledge_base.KnowledgeService(owner.root / "knowledge-base", start_worker=False)
    monkeypatch.setattr(knowledge_base, "knowledge_service", lambda: service)
    try:
        base = service.create("Sources", "synthetic", "synthetic")
        other = service.create("Other", "synthetic", "synthetic")
        document = service.add_text(base["id"], "guide.txt", "source evidence")
        foreign = service.add_text(other["id"], "private.txt", "other base secret")
        frozen = snapshot((base["id"],))
        save_task(owner.root, "real", frozen)
        request = payload(task_id="real", mounts=frozen["knowledge_bases"], arguments={"document_id": document["id"]})
        response = post(owner, request, operation="read")
        assert response.status_code == 200
        assert response.json()["document_id"] == document["id"]
        assert response.json()["path"] == "guide.txt"
        assert response.json()["text"] == "source evidence"
        folder = service.create_folder(base["id"], "manual")
        nested = service.add_text(base["id"], "nested.txt", "nested source", folder["id"])
        foreign_folder = service.create_folder(other["id"], "private")
        root = post(owner, {**request, "arguments": {}}, operation="browse")
        assert root.status_code == 200
        assert {item["id"] for item in root.json()["items"]} == {document["id"], folder["id"]}
        assert root.json()["bases"][0]["document_count"] == 2
        assert root.json()["bases"][0]["keyword_documents"] == 0
        page = post(owner, {**request, "arguments": {"folder_id": folder["id"]}}, operation="browse")
        assert page.status_code == 200
        assert page.json()["items"][0]["id"] == nested["id"]
        assert page.json()["items"][0]["path"] == "manual/nested.txt"
        for response in (root, page):
            assert knowledge._token not in response.text and str(service.root) not in response.text
            assert other["id"] not in response.text and foreign["id"] not in response.text
            for item in response.json()["items"]:
                assert set(item) == {"id", "kb_id", "parent_id", "kind", "name", "path", "knowledge_path", "status", "chunk_count", "error_code"}
                assert item["knowledge_path"] == ".knowledge/Sources/" + item["path"]
        denied = post(owner, {**request, "arguments": {"folder_id": foreign_folder["id"]}}, operation="browse")
        assert denied.status_code == 400 and denied.json()["error_code"] == "knowledge_unavailable"
        response = post(owner, {**request, "arguments": {"document_id": foreign["id"]}}, operation="read")
        assert response.status_code == 400
        assert "other base secret" not in response.text
        service.delete(base["id"], service.get(base["id"])["updated_at"])
        assert post(owner, request, operation="read").status_code == 400
        assert post(owner, {**request, "arguments": {}}, operation="browse").status_code == 400
    finally:
        service.close()


@pytest.mark.parametrize("inherited", ["not json", "[]", "null", '{"url":42,"token":[]}'])
def test_malformed_inherited_bridge_settings_do_not_break_unmounted_tasks(tmp_path, inherited):
    code = """
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from task_agent.knowledge import knowledge_tools, _ENV
assert _ENV not in os.environ
assert knowledge_tools(Path(sys.argv[2]), 'bare', {}) == []
"""
    env = {**os.environ, knowledge._ENV: inherited}
    result = subprocess.run([sys.executable, "-c", code, str(Path(__file__).resolve().parents[1]), str(tmp_path)],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr

@pytest.mark.parametrize("query", ["*", "***", "???", "___", "...", "💫", " ", ""])
def test_symbol_queries_are_actionable_locally_and_through_authenticated_bridge(owner, monkeypatch, query):
    from knowledge_base.query import INVALID_QUERY_MESSAGE
    remote_calls = []
    monkeypatch.setattr(knowledge, "_bridge_request", lambda *args: remote_calls.append(args))
    tool = knowledge.knowledge_tools(owner.root, "task", snapshot())[0]
    output = tool.invoke(None, {"query": query, "mode": "keyword"})
    assert isinstance(output, ToolOutputError)
    assert output.error_code == "invalid_query"
    assert output.message == INVALID_QUERY_MESSAGE
    assert remote_calls == []
    response = post(owner, payload(arguments={"query": query, "mode": "keyword"}))
    assert response.status_code == 400
    assert response.json() == {"error_code": "invalid_query", "msg": INVALID_QUERY_MESSAGE}
    assert owner.sources.calls == []


def test_argument_validation_uses_shared_query_helper(owner, monkeypatch):
    seen = []
    original = knowledge.validate_query
    monkeypatch.setattr(knowledge, "validate_query", lambda query: seen.append(query) or original(query))
    response = post(owner, payload(arguments={"query": "  中文配额  "}))
    assert response.status_code == 200
    assert seen == ["  中文配额  "]
    assert owner.sources.calls[-1][1]["query"] == "中文配额"


def test_browse_pages_root_and_folder_with_explicit_mount_subset(owner):
    frozen = snapshot((KB_A, KB_B))
    save_task(owner.root, "both", frozen)
    request = payload(task_id="both", mounts=frozen["knowledge_bases"], arguments={"offset": 0, "limit": 1})
    first = post(owner, request, operation="browse")
    assert first.status_code == 200
    data = first.json()
    assert data["total"] == 2 and data["next_offset"] == 1
    assert [base["kb_id"] for base in data["bases"]] == [KB_A, KB_B]
    assert all(base["status_counts"] == {"ready": 3} for base in data["bases"])
    second = post(owner, {**request, "arguments": {"offset": data["next_offset"], "limit": 1}}, operation="browse").json()
    assert second["next_offset"] is None
    assert second["items"][0]["id"] != data["items"][0]["id"]
    child = post(owner, {**request, "arguments": {"kb_ids": [KB_A], "folder_id": data["items"][0]["id"]}}, operation="browse")
    assert child.status_code == 200
    assert child.json()["items"][0]["id"] == DOCUMENT
    assert child.json()["items"][0]["chunk_count"] == 310
    assert owner.sources.calls[-1][1]["kb_ids"] == [KB_A]
    assert post(owner, {**request, "arguments": {"offset": 10000, "limit": 50}}, operation="browse").status_code == 200


@pytest.mark.parametrize("arguments", [
    {"offset": -1}, {"offset": 10001}, {"offset": True}, {"offset": "1"},
    {"limit": 0}, {"limit": 51}, {"limit": True}, {"limit": 1.2},
    {"folder_id": "C:/private/token"}, {"folder_id": 1}, {"query": "*"},
    {"path": "/private/token"}, {"kb_ids": []}, {"kb_ids": [KB_B]}, {"kb_ids": [KB_A, KB_A]},
])
def test_browse_rejects_invalid_values_and_unmounted_scope_before_dispatch(owner, monkeypatch, arguments):
    calls = []
    monkeypatch.setattr(knowledge, "_bridge_request", lambda *args: calls.append(args))
    output = knowledge.knowledge_tools(owner.root, "task", snapshot())[2].invoke(None, arguments)
    assert isinstance(output, ToolOutputError)
    assert output.error_code == "knowledge_unavailable"
    assert calls == []
    response = post(owner, payload(arguments=arguments), operation="browse")
    assert response.status_code == 400 and response.json()["error_code"] == "knowledge_unavailable"
    assert owner.sources.calls == []
    assert "/private" not in response.text and knowledge._token not in response.text


@pytest.mark.parametrize("options", [{"token": "wrong"}, {"host": "192.0.2.1"}, {"origin": "http://malicious.invalid"}])
def test_browse_requires_authenticated_private_bridge(owner, options):
    assert post(owner, payload(arguments={}), operation="browse", **options).status_code == 403
    assert owner.sources.calls == []


def test_browse_rechecks_saved_mounts_for_parent_and_child_on_every_call(owner, monkeypatch):
    from vv_agent.session.delegation import configured_agent
    request = SimpleNamespace(thread_id="task", cwd=str(owner.root / "workspaces" / "task"), metadata={"model_snapshot": snapshot()})
    host = DesktopTaskAgentHost(owner.root, settings_loader=lambda: SETTINGS)
    agent = host.resolve_agent(request)
    child = configured_agent(SimpleNamespace(agent=agent), "worker", agent.sub_agents["worker"])
    monkeypatch.setattr(knowledge, "_bridge_request", lambda operation, body: knowledge._dispatch(owner.root, operation, body))
    for bound in (agent, child):
        tool = next(tool for tool in bound.tools if tool.name == "knowledge_list")
        result = tool.invoke(None, {})
        assert result.data["bases"][0]["kb_id"] == KB_A
        assert isinstance(tool.invoke(None, {"kb_ids": [KB_B]}), ToolOutputError)
    original = deepcopy(owner.sources.calls)
    store = BusinessStore(owner.root / "tasks.db")
    store.update_task("task", config_snapshot=json.dumps(snapshot(())))
    for bound in (agent, child):
        tool = next(tool for tool in bound.tools if tool.name == "knowledge_list")
        assert isinstance(tool.invoke(None, {}), ToolOutputError)
    assert post(owner, payload(arguments={}), operation="browse").status_code == 400
    assert owner.sources.calls == original
    assert knowledge.knowledge_tools(owner.root, "task", snapshot(())) == []
    assert post(owner, payload(mounts=[], arguments={}), operation="browse").status_code == 400
    with store.connect() as connection:
        connection.execute("DELETE FROM tasks WHERE tid=?", ("task",))
    assert isinstance(agent.tools[2].invoke(None, {}), ToolOutputError)
    assert post(owner, payload(arguments={}), operation="browse").status_code == 400


def test_browse_deleted_mount_and_foreign_folder_do_not_become_global_listing(owner):
    response = post(owner, payload(arguments={"folder_id": "f" * 32}), operation="browse")
    assert response.status_code == 400
    assert response.json()["error_code"] == "knowledge_unavailable"
    assert "/private" not in response.text
    owner.sources.present.remove(KB_A)
    response = post(owner, payload(arguments={}), operation="browse")
    assert response.status_code == 400
    assert owner.sources.calls == []
    assert "/private" not in response.text


def test_list_schema_and_order_remain_compatible(owner):
    tools = knowledge.knowledge_tools(owner.root, "task", snapshot())
    assert [tool.name for tool in tools] == ["knowledge_search", "knowledge_read", "knowledge_list"]
    schema = tools[2].params_json_schema
    assert schema["required"] == [] and schema["additionalProperties"] is False
    assert schema["properties"]["limit"]["maximum"] == 50
    assert schema["properties"]["offset"]["maximum"] == 10000
    assert schema["properties"]["folder_id"] == tools[0].params_json_schema["properties"]["folder_id"]
    assert tools[2].needs_approval is False and str(tools[2].tool_metadata.side_effect) == "read"


@pytest.mark.parametrize("code,expected", [
    ("invalid_query", "invalid_query"), ("not_found", "not_found"), ("service_unavailable", "service_unavailable"),
    ("invalid_scope", "knowledge_unavailable"), ("invalid_input", "knowledge_unavailable"),
    ("provider_error", "knowledge_unavailable"),
])
def test_route_exposes_only_safe_domain_codes_with_fixed_messages(owner, monkeypatch, code, expected):
    from knowledge_base import KnowledgeError
    def fail(*args, **kwargs):
        raise KnowledgeError(code, "SYNTHETIC_PRIVATE_TOKEN C:/private/source")
    monkeypatch.setattr(owner.sources, "browse", fail)
    response = post(owner, payload(arguments={}), operation="browse")
    assert response.status_code == 400
    assert response.json()["error_code"] == expected
    assert "SYNTHETIC_PRIVATE_TOKEN" not in response.text and "C:/private" not in response.text


@pytest.mark.parametrize("status,body,expected", [
    (400, {"error_code": "invalid_query", "msg": "SYNTHETIC_PRIVATE_TOKEN C:/private/source"}, "invalid_query"),
    (404, {"error_code": "not_found", "msg": "SYNTHETIC_PRIVATE_TOKEN C:/private/source"}, "not_found"),
    (503, {"error_code": "service_unavailable", "msg": "SYNTHETIC_PRIVATE_TOKEN C:/private/source"}, "service_unavailable"),
    (400, {"error_code": "invalid_scope", "msg": "SYNTHETIC_PRIVATE_TOKEN C:/private/source"}, "knowledge_unavailable"),
    (400, {"error_code": ["invalid_query"], "msg": "SYNTHETIC_PRIVATE_TOKEN"}, "knowledge_unavailable"),
    (400, ["invalid_query", "SYNTHETIC_PRIVATE_TOKEN"], "knowledge_unavailable"),
    (400, "SYNTHETIC_PRIVATE_TOKEN C:/private/source", "knowledge_unavailable"),
    (403, {"error_code": "invalid_query", "msg": "SYNTHETIC_PRIVATE_TOKEN"}, "knowledge_unavailable"),
])
def test_bridge_error_codes_are_rebuilt_without_trusting_remote_messages(owner, monkeypatch, status, body, expected):
    client_type = httpx.Client
    def response(request):
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=body)
    def local_client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return client_type(transport=httpx.MockTransport(response), **kwargs)
    monkeypatch.setattr(knowledge.httpx, "Client", local_client)
    tool = knowledge.knowledge_tools(owner.root, "task", snapshot())[2]
    output = tool.to_tool_execution_result(tool.invoke(None, {}))
    assert output.error_code == expected
    assert "SYNTHETIC_PRIVATE_TOKEN" not in output.content and "C:/private" not in output.content
    assert knowledge._token not in output.content
    if expected == "invalid_query":
        from knowledge_base.query import INVALID_QUERY_MESSAGE
        assert INVALID_QUERY_MESSAGE in output.content
