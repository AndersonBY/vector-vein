# @Author: Bi Ying
# @Date:   2024-06-06 23:52:55
import time
import json
import socket
import asyncio
from threading import Thread

from websockets.asyncio.server import serve, ServerConnection
from vectorvein.types.enums import BackendType
from vectorvein.chat_clients import create_async_chat_client
from vectorvein.settings import settings as vectorvein_settings
from vectorvein.chat_clients.utils import ToolCallContentProcessor, format_messages

from tts_server.server import tts_server
from utilities.general import mprint
from utilities.config import Settings, cache
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


class WebSocketServer:
    def __init__(self, host="localhost", start_port=8765):
        self.host = host
        self.port = self.find_available_port(start_port)
        self.server = None
        self.thread = None

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
        async for message in websocket:
            await self.process_message(websocket, message)

    async def process_message(self, websocket: ServerConnection, message: str | bytes):
        user_settings = Settings()
        vectorvein_settings.load(user_settings.get("llm_settings"))

        request_data = json.loads(message)
        settings = request_data["conversation"]["settings"]
        ai_message_mid = request_data["ai_message_mid"]
        history_messages = request_data["history_messages"]
        need_title = request_data["need_title"] and user_settings.get("agent.auto_title", False)
        backend = request_data["conversation"]["model_provider"].lower()
        model = request_data["conversation"]["model"]
        mprint(f"[WebSocket Server] Agent chat start: {backend} {model}")

        if backend.startswith("_local__"):
            backend = BackendType.Local
        else:
            backend = BackendType(backend)

        model_settings = vectorvein_settings.get_backend(backend=backend)
        native_multimodal = model_settings.models[model].native_multimodal

        system_message = {
            "role": "system",
            "content": settings.get("system_prompt"),
        }
        user_messages = format_messages(
            messages=history_messages, backend=backend, native_multimodal=native_multimodal
        )
        messages = [system_message, *user_messages]

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
        mprint("[WebSocket Server] Agent chat response created")
        full_content = ""
        tool_calls = {}
        selected_workflow = {}
        workflow_invoke_step = ""
        start_generate_time = time.time()
        async for chunk in response:
            if time.time() - start_generate_time > 1:
                mprint("[WebSocket Server] Agent chat chunk generate time use: ", time.time() - start_generate_time)
            start_generate_time = time.time()

            full_content += chunk.content if chunk.content is not None else ""
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
                    if backend in TOOL_CALL_INCREMENTAL_BACKENDS:
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
            mprint("[WebSocket Server] Agent chat tool_calls", tool_calls)
            function_name = tool_calls[0]["function"]["name"]
            mprint("[WebSocket Server] Agent chat function_name", function_name)
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
        mprint(f"[WebSocket Server] Started at ws://{self.host}:{self.port}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._serve())
        loop.run_forever()

    async def _serve(self):
        async with serve(self.handler, self.host, self.port) as server:
            await server.serve_forever()

    def stop(self):
        mprint("[WebSocket Server] Stopping...")
        if self.thread:
            self.thread.join()
            self.thread = None
        mprint("[WebSocket Server] Stopped.")
