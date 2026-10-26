# @Author: Bi Ying
# @Date:   2024-06-06 23:52:55
import time
import json
import socket
import asyncio
from contextlib import suppress
from uuid import UUID

from models import Message
from utilities.chat_responses import PENDING, failure_response, persist_response, terminal_frame
from threading import Thread
from datetime import datetime
from zoneinfo import ZoneInfo

from websockets.asyncio.server import serve, ServerConnection
from websockets.exceptions import ConnectionClosed
from vv_llm.types import (
    NotGiven,
    NOT_GIVEN,
    BackendType,
)
from vv_llm.chat_clients import create_async_chat_client
from vv_llm.settings import settings as vv_llm_settings
from vv_llm.chat_clients.utils import ToolCallContentProcessor, format_messages

from tts_server.server import tts_server
from utilities.config import Settings, cache
from utilities.general import mprint_with_name
from utilities.network.llm_client import new_llm_http_client
from celery_tasks import summarize_conversation_title
from .utils import get_tool_call_data, get_tool_related_workflow


TOOL_CALL_INCREMENTAL_BACKENDS = (
    BackendType.OpenAI,
    BackendType.Moonshot,
    BackendType.Anthropic,
    BackendType.DeepSeek,
    BackendType.MiniMax,
)

TOOL_CALL_INCREMENTAL_MODELS = (
    "qwen3-235b-a22b",
    "qwen3-235b-a22b-thinking",
    "qwen3-32b",
    "qwen3-32b-thinking",
    "qwen3-30b-a3b",
    "qwen3-30b-a3b-thinking",
    "qwen3-14b",
    "qwen3-14b-thinking",
    "qwen3-8b",
    "qwen3-8b-thinking",
    "qwen3-4b",
    "qwen3-4b-thinking",
    "qwen3-1.7b",
    "qwen3-1.7b-thinking",
    "qwen3-0.6b",
    "qwen3-0.6b-thinking",
    "mixtral-8x7b",
)

mprint = mprint_with_name(name="WebSocket Server")


class WebSocketServer:
    CHAT_IDLE_TIMEOUT = 180

    def __init__(self, host="localhost", start_port=8765):
        self.host = host
        self.port = self.find_available_port(start_port)
        self.server = None
        self.thread = None
        self.loop = None
        self.handlers = {
            "/ws/chat": self.handle_chat,
            "/ws/workflow_node": self.handle_workflow_node,
        }

    def find_available_port(self, start_port):
        port = start_port
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((self.host, port))
                    return port
                except OSError:
                    port += 1

    async def handler(self, websocket: ServerConnection):
        request_path = websocket.request.path if websocket.request else ""
        mprint(f"WebSocket request path: {request_path}")
        base_path = "/" + request_path.split("/")[1] + "/" + request_path.split("/")[2]
        param = request_path.split("/")[3]

        handler = self.handlers.get(base_path)
        if handler:
            await handler(websocket, param)
        else:
            mprint(f"No handler found for path: {request_path}")
            await websocket.close(1008, "Path not supported")

    async def handle_workflow_node(self, websocket: ServerConnection, param: str):
        record_id, node_id = param.split("_")
        queue_key = f"workflow_record{record_id}_node{node_id}:data_queue"
        data_queue = []
        assert isinstance(data_queue, list)
        current_length = len(data_queue)

        start_time = time.time()
        while time.time() - start_time < 3 * 60:
            latest_data_queue = cache.get(queue_key, [])
            assert isinstance(latest_data_queue, list)
            while len(latest_data_queue) > current_length:
                data = latest_data_queue[current_length]
                current_length += 1
                await websocket.send(json.dumps(data, ensure_ascii=False))
                if data == '{"end": true}':
                    break
            await asyncio.sleep(0.1)

    async def handle_chat(self, websocket: ServerConnection, param: str):
        async for message in websocket:
            await self.process_message(websocket, message, param)

    async def process_message(self, websocket: ServerConnection, message: str | bytes, param: str):
        try:
            request = json.loads(message)
            mid = UUID(str(request["ai_message_mid"]))
            cid = UUID(param)
            assistant = Message.get_or_none((Message.mid == mid) & (Message.author_type == "A"))
            if assistant is None or assistant.conversation.cid != cid:
                raise ValueError("Invalid chat message")
            supplied_cid = request.get("conversation", {}).get("cid")
            if supplied_cid is not None and UUID(str(supplied_cid)) != cid:
                raise ValueError("Invalid conversation")
        except (ValueError, KeyError, TypeError, AttributeError):
            await websocket.close(1008, "Invalid chat message")
            return
        if assistant.status not in PENDING:
            if assistant.status in ("S", "W", "F"):
                await websocket.send(json.dumps(terminal_frame(assistant), ensure_ascii=False))
            else:
                await websocket.close(1008, "Chat message already processed")
            return
        # Only one websocket may generate a pending assistant message.
        claimed = Message.update(status="G").where((Message.mid == mid) & (Message.status == "P")).execute()
        if not claimed:
            return
        state = {"text": "", "reasoning_content": ""}
        generation = asyncio.create_task(self._generate_response(websocket, request, state))
        disconnected = asyncio.create_task(websocket.wait_closed())
        try:
            done, _ = await asyncio.wait((generation, disconnected), return_when=asyncio.FIRST_COMPLETED)
            if generation in done:
                response = await generation
            else:
                generation.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await generation
                response = failure_response("CHAT_CONNECTION_CLOSED", state,
                    model=request.get("conversation", {}).get("model"))
            assistant = persist_response(assistant, response)
            with suppress(Exception):
                await websocket.send(json.dumps(terminal_frame(assistant), ensure_ascii=False))
        except asyncio.CancelledError:
            persist_response(assistant, failure_response("CHAT_CONNECTION_CLOSED", state,
                model=request.get("conversation", {}).get("model")))
            raise
        except Exception as exc:
            code = ("CHAT_TIMEOUT" if isinstance(exc, TimeoutError) else
                "CHAT_CONNECTION_CLOSED" if isinstance(exc, ConnectionClosed) else "CHAT_REQUEST_FAILED")
            assistant = persist_response(assistant, failure_response(code, state, error=exc,
                model=request.get("conversation", {}).get("model")))
            with suppress(Exception):
                await websocket.send(json.dumps(terminal_frame(assistant), ensure_ascii=False))
        finally:
            generation.cancel()
            disconnected.cancel()
            await asyncio.gather(generation, disconnected, return_exceptions=True)
            provider = getattr(state.get("client"), "__dict__", {}).get("raw_client")
            if provider is not None and hasattr(provider, "close"):
                with suppress(Exception):
                    await provider.close()
            for resource in (state.get("response"), state.get("http_client")):
                if resource is not None and hasattr(resource, "aclose"):
                    with suppress(Exception):
                        await resource.aclose()

    async def _initial_response(self, awaitable):
        return await asyncio.wait_for(awaitable, timeout=self.CHAT_IDLE_TIMEOUT)

    async def _stream_chunks(self, response):
        iterator = response.__aiter__()
        while True:
            try:
                yield await asyncio.wait_for(anext(iterator), timeout=self.CHAT_IDLE_TIMEOUT)
            except StopAsyncIteration:
                return

    async def _generate_response(self, websocket, request_data, state):
        user_settings = Settings()
        vv_llm_settings.load(user_settings.get("llm_settings"))

        settings = request_data["conversation"]["settings"]
        ai_message_mid = request_data["ai_message_mid"]
        history_messages = request_data["history_messages"]
        need_title = request_data["need_title"] and user_settings.get("agent.auto_title", False)
        user_timezone = request_data["user_timezone"]
        backend = request_data["conversation"]["model_provider"].lower()
        model = request_data["conversation"]["model"]
        mprint(f"Agent chat start: {backend} {model}")

        if backend.startswith("_local__"):
            backend = BackendType.Local
        else:
            backend = BackendType(backend)

        thinking = NOT_GIVEN
        temperature = NOT_GIVEN
        max_tokens = None

        reasoning_effort: NotGiven | str = NOT_GIVEN
        extra_body: dict = {}

        model_settings = vv_llm_settings.get_backend(backend=backend)
        native_multimodal = model_settings.models[model].native_multimodal

        system_prompt = settings.get("system_prompt") or ""
        if system_prompt:
            current_time = datetime.now().astimezone(ZoneInfo(user_timezone)).strftime("%Y-%m-%d %H:%M:%S %Z")
            system_prompt = system_prompt.replace("{{time}}", current_time)
            system_message = [
                {
                    "role": "system",
                    "content": system_prompt,
                }
            ]
        else:
            system_message = []

        user_messages = format_messages(messages=history_messages, backend=backend, native_multimodal=native_multimodal)
        messages = [*system_message, *user_messages]

        if need_title:
            title_backend, title_model = user_settings.get("agent.auto_title_model", ["openai", "gpt-5-nano"])
            if title_backend.startswith("_local__"):
                title_backend = BackendType.Local
            else:
                title_backend = BackendType(title_backend.lower())
            summarize_conversation_title.delay(ai_message_mid, history_messages, title_backend, title_model)

        state["http_client"] = new_llm_http_client(is_async=True)
        client = create_async_chat_client(backend=backend, model=model, http_client=state["http_client"])
        state["client"] = client

        tool_call_data = request_data["conversation"]["tool_call_data"]
        if tool_call_data.get("workflows") or tool_call_data.get("templates"):
            response = await self._initial_response(client.create_stream(
                messages=messages,
                stream_options={"include_usage": True},
                tools=get_tool_call_data(tool_call_data, simple=False),
                temperature=temperature,
                max_tokens=max_tokens,
                thinking=thinking,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body,
            ))
        else:
            response = await self._initial_response(client.create_stream(
                messages=messages,
                stream_options={"include_usage": True},
                temperature=temperature,
                max_tokens=max_tokens,
                thinking=thinking,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body,
            ))
        state["response"] = response
        mprint("Agent chat response created")
        full_content = ""
        full_reasoning_content = ""
        tool_calls = {}
        selected_workflow = {}
        workflow_invoke_step = ""
        start_generate_time = time.time()
        async for chunk in self._stream_chunks(response):
            if time.time() - start_generate_time > 1:
                mprint("Agent chat chunk generate time use: ", time.time() - start_generate_time)
            start_generate_time = time.time()

            full_content += chunk.content if chunk.content is not None else ""
            full_reasoning_content += chunk.reasoning_content if chunk.reasoning_content is not None else ""
            state["text"] = full_content
            state["reasoning_content"] = full_reasoning_content
            if chunk.tool_calls and len(chunk.tool_calls) > 0:
                workflow_invoke_step = "generating_params"
                piece = chunk.tool_calls[0]
                index = piece.index
                if index is None:
                    index = 0
                tool_calls[index] = tool_calls.get(index, {"id": None, "function": {"arguments": "", "name": ""}, "type": "function"})
                if piece.id:
                    tool_calls[index]["id"] = piece.id
                if piece.function:
                    if piece.function.name:
                        tool_calls[index]["function"]["name"] = piece.function.name
                    if (backend in TOOL_CALL_INCREMENTAL_BACKENDS or model in TOOL_CALL_INCREMENTAL_MODELS) and model_settings.models[model].function_call_available:
                        # OpenAI/Moonshot/Anthropic/DeepSeek/Minimax is incremental and needs to be concatenated
                        if piece.function.arguments:
                            tool_calls[index]["function"]["arguments"] += piece.function.arguments
                    else:
                        tool_calls[index]["function"]["arguments"] = piece.function.arguments

            await websocket.send(
                json.dumps(
                    {**chunk.model_dump(), "workflow_invoke_step": workflow_invoke_step},
                    ensure_ascii=False,
                )
            )

        if tool_calls:
            function_name = tool_calls[0]["function"]["name"]
            selected_workflow = get_tool_related_workflow(
                request_data["conversation"],
                tool_call_data,
                function_name,
            )
            if selected_workflow:
                selected_workflow["params"] = json.loads(tool_calls[0]["function"]["arguments"])
                if isinstance(selected_workflow["params"], str):
                    # 有时候loads一次还不够？
                    selected_workflow["params"] = json.loads(selected_workflow["params"])
                selected_workflow["tool_call_id"] = tool_calls[0]["id"]
                selected_workflow["function_name"] = function_name
            await websocket.send(
                json.dumps(
                    {
                        "workflow_invoke_step": "wait_for_invoke",
                        "selected_workflow": selected_workflow,
                    },
                    ensure_ascii=False,
                )
            )
            full_content = ToolCallContentProcessor(full_content).non_tool_content

        conversation_title = cache.get(f"conversation-title:{ai_message_mid}", None)

        if settings.get("agent_audio_reply") and len(full_content) > 0:
            provider, voice = settings.get("agent_audio_voice", ["openai", "onyx"])
            tts_server.stream(text=full_content, provider=provider, voice=voice, skip_code_block=True)

        response_data = {
            "conversation_title": conversation_title,
            "content_type": "TXT" if len(tool_calls) == 0 else "WKF",
            "content": {
                "text": full_content,
                "reasoning_content": full_reasoning_content,
            },
            "metadata": {
                "selected_workflow": selected_workflow,
            },
            "model": model,
        }
        return response_data

    def start(self):
        self.thread = Thread(target=self._run_server, daemon=True)
        self.thread.start()

    def _run_server(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self._start_server())
            mprint(f"Started at ws://{self.host}:{self.port}")
            self.loop.run_forever()
        finally:
            pending = [task for task in asyncio.all_tasks(self.loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.close()
            self.loop = None
            self.server = None

    async def _start_server(self):
        self.server = await serve(self.handler, self.host, self.port)

    async def _shutdown_server(self):
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    def stop(self):
        mprint("Stopping...")
        if self.loop is not None:
            shutdown_future = asyncio.run_coroutine_threadsafe(self._shutdown_server(), self.loop)
            try:
                shutdown_future.result(timeout=5)
            except Exception as e:
                mprint.warning(f"WebSocket server shutdown timed out: {e}")
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                mprint.warning("WebSocket server thread did not stop within timeout")
            else:
                self.thread = None
        mprint("Stopped.")
