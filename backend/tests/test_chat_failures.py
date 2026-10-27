import asyncio
import json
from types import SimpleNamespace

import pytest
from peewee import SqliteDatabase
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from models import Agent, Conversation, Message, User
from api.agent_api import MessageAPI
from api.utils import get_history_messages
from chat_server import server as chat
from utilities.chat_responses import failure_response, persist_response


@pytest.fixture
def pending():
    database = SqliteDatabase(":memory:")
    with database.bind_ctx([User, Agent, Conversation, Message]):
        database.create_tables([User, Agent, Conversation, Message])
        conversation = Conversation.create(title="test", model_provider="openai", model="custom")
        user = Message.create(conversation=conversation, author_type="U", content_type="TXT",
            status="S", content={"text": "question"})
        assistant = Message.create(conversation=conversation, parent=user, author_type="A",
            content_type="TXT", content={"text": ""})
        yield assistant
    database.close()


def request(assistant):
    return {"ai_message_mid": assistant.mid.hex, "history_messages": [], "need_title": False,
        "user_timezone": "UTC", "conversation": {"cid": assistant.conversation.cid.hex,
        "settings": {}, "model_provider": "openai", "model": "custom", "tool_call_data": {}}}


class Socket:
    def __init__(self):
        self.frames = []
        self.closed = asyncio.Event()

    async def send(self, value):
        self.frames.append(json.loads(value))
        if self.frames[-1].get("end"):
            assert Message.get_by_id(self.frames[-1]["mid"]).status == self.frames[-1]["status"]

    async def wait_closed(self):
        await self.closed.wait()

    async def close(self, *args):
        self.closed.set()


def test_fail_notice_keeps_partial_and_is_idempotent(pending):
    api = MessageAPI()
    payload = {"mid": pending.mid.hex, "cid": pending.conversation.cid.hex,
        "code": "CHAT_CONNECTION_CLOSED", "content": {"text": "partial", "reasoning_content": "thought"}}
    result = api.fail_notice(payload)
    assert result["data"]["status"] == "F"
    assert result["data"]["content"] == payload["content"]
    assert api.fail_notice({**payload, "content": {"text": ""}})["data"] == result["data"]
    assert api.done_notice({"mid": pending.mid.hex})["data"]["status"] == "F"
    assert api.fail_notice({**payload, "code": "arbitrary"})["status"] == 400
    other = Conversation.create(title="other", model_provider="openai", model="custom")
    assert api.fail_notice({**payload, "cid": other.cid.hex})["status"] == 404
    assert api.fail_notice({**payload, "mid": pending.parent.mid.hex})["status"] == 404


@pytest.mark.parametrize("content_type,status", [("TXT", "S"), ("WKF", "W")])
def test_stale_notices_cannot_replace_terminal_success_or_tool_handoff(pending, content_type, status):
    saved = persist_response(pending, {"content_type": content_type, "content": {"text": "done"},
        "metadata": {"selected_workflow": {"wid": "workflow"}}})
    api = MessageAPI()
    result = api.fail_notice({"mid": saved.mid.hex, "cid": saved.conversation.cid.hex,
        "code": "CHAT_TIMEOUT", "content": {"text": "partial"}})
    assert result["data"]["status"] == status
    assert result["data"]["content"]["text"] == "done"
    assert api.done_notice({"mid": saved.mid.hex})["data"]["status"] == status


def test_done_notice_with_missing_or_corrupt_legacy_cache(pending, monkeypatch):
    from api import agent_api
    for cached in (None, "not-json", "null", '{}'):
        monkeypatch.setattr(agent_api, "cache", SimpleNamespace(get=lambda _: cached))
        assert MessageAPI().done_notice({"mid": pending.mid.hex})["data"]["status"] == "P"


@pytest.mark.parametrize("nested", [False, True])
def test_provider_error_body_uses_readable_redacted_message(monkeypatch, nested):
    import httpx2
    from openai import APIStatusError
    from utilities import config

    monkeypatch.setattr(config, "Settings", lambda: SimpleNamespace(data={"api_key": "endpoint-secret"}))
    body = {"message": " Provider unavailable endpoint-secret api_key=inline-secret " + "x" * 2000,
            "type": "server_error", "code": "unavailable"}
    error = APIStatusError("Error code: 503 - raw provider dictionary", body={"error": body} if nested else body,
        response=httpx2.Response(503, request=httpx2.Request("POST", "https://provider.invalid")))
    message = failure_response("CHAT_REQUEST_FAILED", error=error)["metadata"]["error"]["message"]
    assert message.startswith("Provider unavailable")
    assert "Error code:" not in message
    assert "endpoint-secret" not in message and "inline-secret" not in message
    assert len(message) == 1500


@pytest.mark.parametrize("body", [None, {}, {"message": " "}, {"message": {"unexpected": "object"}}])
def test_provider_error_without_message_uses_redacted_exception(body):
    error = RuntimeError("Connection failed api_key=inline-secret")
    error.body = body
    assert failure_response("CHAT_REQUEST_FAILED", error=error)["metadata"]["error"]["message"] == (
        "Connection failed api_key=[REDACTED]")


def test_history_keeps_empty_failed_assistants_and_omits_provider_partial(pending):
    saved = persist_response(pending, failure_response("CHAT_TIMEOUT"))
    groups = get_history_messages(saved, count=None)
    assert groups[-1][0]["mid"] == saved.mid.hex
    assert groups[-1][0]["status"] == "F"
    saved.content = {"text": "unfinished answer"}
    saved.save()
    history = get_history_messages(saved, count=None, all_children=False)
    assert [message["author_type"] for message in history] == ["U"]


def test_server_failure_redacts_and_persists_partial_before_terminal(pending, monkeypatch):
    from utilities import config
    monkeypatch.setattr(config, "Settings", lambda: SimpleNamespace(data={"llm_settings": {
        "endpoints": [{"api_key": "configured-endpoint-secret"}]}}))
    async def scenario():
        websocket = Socket()
        server = chat.WebSocketServer()
        calls = []
        async def fail(socket, data, state):
            calls.append("generate")
            state.update(text="partial", reasoning_content="reason")
            raise RuntimeError("provider error configured-endpoint-secret api_key=private-secret " + "x" * 2000)
        monkeypatch.setattr(server, "_generate_response", fail)
        await server.process_message(websocket, json.dumps(request(pending)), pending.conversation.cid.hex)
        terminal = websocket.frames[-1]
        assert terminal["status"] == "F"
        assert terminal["content"] == "partial"
        assert terminal["reasoning_content"] == "reason"
        assert terminal["error"]["code"] == "CHAT_REQUEST_FAILED"
        assert "private-secret" not in terminal["error"]["message"]
        assert "configured-endpoint-secret" not in terminal["error"]["message"]
        assert len(terminal["error"]["message"]) <= 1500
        assert terminal["selected_workflow"] == {}
        await server.process_message(websocket, json.dumps(request(pending)), pending.conversation.cid.hex)
        assert websocket.frames[-1] == terminal
        assert calls == ["generate"]
    asyncio.run(scenario())


def test_invalid_conversation_cannot_start_generation(pending, monkeypatch):
    async def scenario():
        websocket = Socket()
        server = chat.WebSocketServer()
        async def forbidden(*args):
            pytest.fail("invalid conversation generated")
        monkeypatch.setattr(server, "_generate_response", forbidden)
        from uuid import uuid4
        await server.process_message(websocket, json.dumps(request(pending)), uuid4().hex)
        assert websocket.closed.is_set()
        assert Message.get_by_id(pending.mid).status == "P"
    asyncio.run(scenario())


def test_real_websocket_disconnect_cancels_stalled_provider_and_preserves_partial(pending, monkeypatch):
    async def scenario():
        server = chat.WebSocketServer()
        cancelled = asyncio.Event()
        async def stalled(socket, data, state):
            state.update(text="partial", reasoning_content="thought")
            await socket.send(json.dumps({"content": "partial"}))
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        monkeypatch.setattr(server, "_generate_response", stalled)
        async def handler(socket):
            await server.handle_chat(socket, pending.conversation.cid.hex)
        async with serve(handler, "127.0.0.1", 0) as listener:
            port = listener.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as websocket:
                await websocket.send(json.dumps(request(pending)))
                assert json.loads(await websocket.recv())["content"] == "partial"
            await asyncio.wait_for(cancelled.wait(), 1)
        saved = Message.get_by_id(pending.mid)
        assert saved.status == "F"
        assert saved.content == {"text": "partial", "reasoning_content": "thought"}
        assert saved.metadata["error"]["code"] == "CHAT_CONNECTION_CLOSED"
    asyncio.run(scenario())


def test_initial_and_inactivity_timeouts_do_not_limit_active_stream():
    async def scenario():
        server = chat.WebSocketServer()
        server.CHAT_IDLE_TIMEOUT = 0.2
        with pytest.raises(TimeoutError):
            await server._initial_response(asyncio.sleep(1))
        async def active():
            for index in range(5):
                await asyncio.sleep(0.06)
                yield index
        assert [item async for item in server._stream_chunks(active())] == list(range(5))
        async def stalled():
            yield "first"
            await asyncio.sleep(1)
        with pytest.raises(TimeoutError):
            [item async for item in server._stream_chunks(stalled())]
    asyncio.run(scenario())


@pytest.mark.parametrize("mode,expected", [("success", "S"), ("tools", "W"), ("failure", "F"), ("timeout", "F"), ("initial_timeout", "F")])
def test_actual_generation_persists_success_tools_and_partial_failures(pending, monkeypatch, mode, expected):
    async def scenario():
        closed = []
        class Http:
            async def aclose(self):
                closed.append("http")
        async def chunks():
            try:
                tool = SimpleNamespace(index=0, id="call", function=SimpleNamespace(name="run", arguments='{"value":1}'))
                yield SimpleNamespace(content="answer", reasoning_content="thought", tool_calls=[tool] if mode == "tools" else [],
                    model_dump=lambda: {"content": "answer", "reasoning_content": "thought"})
                if mode == "failure":
                    raise RuntimeError("provider transport failed")
                if mode == "timeout":
                    await asyncio.sleep(10)
            finally:
                closed.append("response")
        class Client:
            async def create_stream(self, **kwargs):
                from vv_llm.types import NOT_GIVEN
                assert kwargs["reasoning_effort"] == ("high" if mode in ("success", "tools") else NOT_GIVEN)
                if mode == "initial_timeout":
                    await asyncio.sleep(10)
                return chunks()
        monkeypatch.setattr(chat, "Settings", lambda: SimpleNamespace(get=lambda key, default=None: default))
        monkeypatch.setattr(chat, "vv_llm_settings", SimpleNamespace(load=lambda _: None,
            get_backend=lambda **_: SimpleNamespace(models={"custom": SimpleNamespace(native_multimodal=False, function_call_available=True)})))
        monkeypatch.setattr(chat, "new_llm_http_client", lambda **_: Http())
        monkeypatch.setattr(chat, "create_async_chat_client", lambda **_: Client())
        monkeypatch.setattr(chat, "get_tool_related_workflow", lambda *args: {"wid": "workflow"})
        monkeypatch.setattr(chat, "get_tool_call_data", lambda *args, **kwargs: [])
        server = chat.WebSocketServer()
        server.CHAT_IDLE_TIMEOUT = 0.1
        websocket = Socket()
        payload = request(pending)
        if mode in ("success", "tools"):
            payload["conversation"]["settings"]["reasoning_effort"] = "high"
        await server.process_message(websocket, json.dumps(payload), pending.conversation.cid.hex)
        saved = Message.get_by_id(pending.mid)
        assert saved.status == expected
        assert saved.content["text"] == ("" if mode == "initial_timeout" else "answer")
        assert saved.content["reasoning_content"] == ("" if mode == "initial_timeout" else "thought")
        assert websocket.frames[-1]["status"] == expected
        assert "http" in closed
        if mode != "initial_timeout":
            assert "response" in closed
        if mode == "tools":
            assert saved.content_type == "WKF"
            assert saved.metadata["selected_workflow"]["params"] == {"value": 1}
        elif mode in ("failure", "timeout", "initial_timeout"):
            assert saved.content_type == "TXT"
            assert "selected_workflow" not in saved.metadata
            assert saved.metadata["error"]["code"] == ("CHAT_TIMEOUT" if mode != "failure" else "CHAT_REQUEST_FAILED")
    asyncio.run(scenario())
