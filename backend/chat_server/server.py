# @Author: Bi Ying
# @Date:   2024-06-06 23:52:55
import re
import time
import json
import asyncio
from threading import Thread

import websockets

from utilities.general import mprint
from utilities.config import Settings, cache
from utilities.media_processing import TTSClient
from utilities.ai_utils import create_async_chat_client, tool_use_re, format_messages
from background_task.tasks import summarize_conversation_title
from .utils import get_tool_call_data, get_tool_related_workflow, MULTIMOAL_MODELS


class WebSocketServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    async def handler(self, websocket, path):
        conversation_id = re.match(r"^/ws/chat/(.+)/$", path)
        if not conversation_id:
            mprint("Invalid conversation ID")
            await websocket.close()
            return

        conversation_id = conversation_id.group(1)
        mprint(f"Connected to conversation: {conversation_id}")

        async for message in websocket:
            await self.process_message(websocket, conversation_id, message)

    async def process_message(self, websocket, conversation_id, message):
        user_settings = Settings()

        request_data = json.loads(message)
        settings = request_data["conversation"]["settings"]
        ai_message_mid = request_data["ai_message_mid"]
        history_messages = request_data["history_messages"]
        need_title = request_data["need_title"] and user_settings.get("agent.auto_title", False)
        backend = request_data["conversation"]["model_provider"].lower()
        model = request_data["conversation"]["model"].lower()
        mprint(f"Agent chat start: {backend} {model}")

        native_multimodal = settings.get("native_multimodal", False) and model in MULTIMOAL_MODELS

        system_message = {
            "role": "system",
            "content": settings.get("system_prompt"),
        }
        user_messages = format_messages(
            messages=history_messages, backend=backend, native_multimodal=native_multimodal
        )
        messages = [system_message, *user_messages]

        if need_title:
            title_backend, title_model = user_settings.get("agent.auto_title_model", ["OpenAI", "gpt-35-turbo"])
            summarize_conversation_title.delay(ai_message_mid, history_messages, title_backend, title_model)

        client = create_async_chat_client(backend=backend, model=model)

        tool_call_data = request_data["conversation"]["tool_call_data"]
        if tool_call_data.get("workflows") or tool_call_data.get("templates"):
            tools_params = {"tools": get_tool_call_data(tool_call_data, simple=False)}
        else:
            tools_params = {}

        mprint("Agent chat tools_params", tools_params)
        response = await client.create_completion(messages=messages, **tools_params)
        mprint("Agent chat response created")
        full_content = ""
        tool_calls = {}
        selected_workflow = {}
        workflow_invoke_step = ""
        start_generate_time = time.time()
        async for chunk in response:
            if time.time() - start_generate_time > 1:
                mprint("Agent chat chunk generate time use: ", time.time() - start_generate_time)
            start_generate_time = time.time()

            full_content += chunk["content"] if chunk.get("content") is not None else ""
            if chunk.get("tool_calls", []) and len(chunk.get("tool_calls", [])) > 0:
                workflow_invoke_step = "generating_params"
                piece = chunk["tool_calls"][0]
                index = piece["index"]
                if index is None:
                    index = 0
                tool_calls[index] = tool_calls.get(
                    index, {"id": None, "function": {"arguments": "", "name": ""}, "type": "function"}
                )
                if piece["id"]:
                    tool_calls[index]["id"] = piece["id"]
                if piece["function"]["name"]:
                    tool_calls[index]["function"]["name"] = piece["function"]["name"]
                if backend in ("openai", "moonshot", "anthropic"):
                    # OpenAI/Moonshot/Anthropic is incremental and needs to be concatenated
                    if piece["function"]["arguments"]:
                        tool_calls[index]["function"]["arguments"] += piece["function"]["arguments"]
                else:
                    tool_calls[index]["function"]["arguments"] = piece["function"]["arguments"]

            await websocket.send(
                json.dumps(
                    {**chunk, "workflow_invoke_step": workflow_invoke_step},
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
            full_content = re.sub(tool_use_re, "", full_content).strip()

        conversation_title = cache.get(f"conversation-title:{ai_message_mid}", None)

        if settings.get("agent_audio_reply") and len(full_content) > 0:
            provider, voice = settings.get("agent_audio_voice", ["openai", "onyx"])
            tts_client = TTSClient(provider=provider)
            tts_client.stream(text=full_content, voice=voice, non_block=True)

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
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        mprint(f"WebSocket server started at ws://{self.host}:{self.port}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.server = websockets.serve(self.handler, self.host, self.port)
        loop.run_until_complete(self.server)
        loop.run_forever()

    def stop(self):
        if self.thread:
            mprint("Stopping WebSocket server")
            self.thread.join()
            self.thread = None
