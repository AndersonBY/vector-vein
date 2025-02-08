# @Author: Bi Ying
# @Date:   2024-06-06 23:52:55
import time
import json
import socket
import asyncio
from threading import Thread
from datetime import datetime
from zoneinfo import ZoneInfo

from websockets.asyncio.server import serve, ServerConnection
from vectorvein.types.enums import BackendType
from vectorvein.chat_clients import create_async_chat_client
from vectorvein.settings import settings as vectorvein_settings
from vectorvein.chat_clients.utils import ToolCallContentProcessor, format_messages

from tts_server.server import tts_server
from utilities.config import Settings, cache
from utilities.general import mprint_with_name
from utilities.network import new_httpx_client
from background_task.tasks import summarize_conversation_title
from .utils import get_tool_call_data, get_tool_related_workflow


TOOL_CALL_INCREMENTAL_BACKENDS = (
    BackendType.OpenAI,
    BackendType.Moonshot,
    BackendType.Anthropic,
    BackendType.DeepSeek,
    BackendType.MiniMax,
)

mprint = mprint_with_name(name="WebSocket Server")


class WebSocketServer:
    def __init__(self, host="localhost", start_port=8765):
        self.host = host
        self.port = self.find_available_port(start_port)
        self.server = None
        self.thread = None
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
        user_settings = Settings()
        vectorvein_settings.load(user_settings.get("llm_settings"))

        request_data = json.loads(message)
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

        model_settings = vectorvein_settings.get_backend(backend=backend)
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

        user_messages = format_messages(
            messages=history_messages, backend=backend, native_multimodal=native_multimodal
        )
        messages = [*system_message, *user_messages]

        if need_title:
            title_backend, title_model = user_settings.get("agent.auto_title_model", ["openai", "gpt-4o-mini"])
            if title_backend.startswith("_local__"):
                title_backend = BackendType.Local
            else:
                title_backend = BackendType(title_backend.lower())
            summarize_conversation_title.delay(ai_message_mid, history_messages, title_backend, title_model)

        client = create_async_chat_client(backend=backend, model=model, http_client=new_httpx_client(is_async=True))

        tool_call_data = request_data["conversation"]["tool_call_data"]
        if tool_call_data.get("workflows") or tool_call_data.get("templates"):
            tools_params = {"tools": get_tool_call_data(tool_call_data, simple=False), "tool_choice": "auto"}
        else:
            tools_params = {}

        response = await client.create_stream(messages=messages, **tools_params)
        mprint("Agent chat response created")
        full_content = ""
        full_reasoning_content = ""
        tool_calls = {}
        selected_workflow = {}
        workflow_invoke_step = ""
        start_generate_time = time.time()
        async for chunk in response:
            if time.time() - start_generate_time > 1:
                mprint("Agent chat chunk generate time use: ", time.time() - start_generate_time)
            start_generate_time = time.time()

            full_content += chunk.content if chunk.content is not None else ""
            full_reasoning_content += chunk.reasoning_content if chunk.reasoning_content is not None else ""
            if chunk.tool_calls and len(chunk.tool_calls) > 0:
                workflow_invoke_step = "generating_params"
                piece = chunk.tool_calls[0]
                index = piece.index
                if index is None:
                    index = 0
                tool_calls[index] = tool_calls.get(
                    index, {"id": None, "function": {"arguments": "", "name": ""}, "type": "function"}
                )
                if piece.id:
                    tool_calls[index]["id"] = piece.id
                if piece.function:
                    if piece.function.name:
                        tool_calls[index]["function"]["name"] = piece.function.name
                    if (
                        backend in TOOL_CALL_INCREMENTAL_BACKENDS
                        and model_settings.models[model].function_call_available
                    ):
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
            mprint("Agent chat tool_calls", tool_calls)
            function_name = tool_calls[0]["function"]["name"]
            mprint("Agent chat function_name", function_name)
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
        cache.set(
            f"chat_response:{ai_message_mid}",
            json.dumps(response_data, ensure_ascii=False),
            expire=60 * 60,
        )

        await websocket.send(
            json.dumps(
                {
                    "title": conversation_title,
                    "role": "assistant",
                    "content": full_content,
                    "reasoning_content": full_reasoning_content,
                    "selected_workflow": selected_workflow,
                    "model": model,
                    "end": True,
                },
                ensure_ascii=False,
            )
        )

    def start(self):
        self.thread = Thread(target=self._run_server, daemon=True)
        self.thread.start()

    def _run_server(self):
        mprint(f"Started at ws://{self.host}:{self.port}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._serve())
        loop.run_forever()

    async def _serve(self):
        async with serve(self.handler, self.host, self.port) as server:
            await server.serve_forever()

    def stop(self):
        mprint("Stopping...")
        if self.thread:
            self.thread.join()
            self.thread = None
        mprint("Stopped.")
