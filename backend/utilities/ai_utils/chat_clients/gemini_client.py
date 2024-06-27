# @Author: Bi Ying
# @Date:   2024-06-17 23:47:49
import json

import httpx

from utilities.config import Settings
from .base_client import BaseChatClient, BaseAsyncChatClient
from .utils import cutoff_messages


MODEL_MAX_INPUT_LENGTH = {
    "gemini-1.5-pro": 1048576,
    "gemini-1.5-flash": 1048576,
}


class GeminiChatClient(BaseChatClient):
    DEFAULT_MODEL: str = "gemini-1.5-pro"

    def __init__(
        self,
        model: str = "gemini-1.5-pro",
        stream: bool = True,
        temperature: float = 0.7,
        context_length_control: str = "latest",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.context_length_control = context_length_control
        settings = Settings()
        self.api_base = settings.get("gemini_api_base")
        self.api_key = settings.get("gemini_api_key")

    def create_completion(
        self,
        messages: list = list,
        model: str | None = None,
        stream: bool | None = None,
        temperature: float | None = None,
        max_tokens: int = 2000,
        tools: list | None = None,
        tool_choice: str | None = None,
    ):
        if model is not None:
            self.model = model
        if stream is not None:
            self.stream = stream
        if temperature is not None:
            self.temperature = temperature

        if messages[0].get("role") == "system":
            system_prompt = messages[0]["content"]
            messages = messages[1:]
        else:
            system_prompt = ""

        if self.context_length_control == "latest":
            messages = cutoff_messages(
                messages, max_count=MODEL_MAX_INPUT_LENGTH[self.model], backend="gemini", model=self.model
            )

        if tools:
            tools_params = {"tools": [{"function_declarations": [tool["function"] for tool in tools]}]}
        else:
            tools_params = {}

        request_body = {
            "contents": messages,
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": max_tokens,
            },
            **tools_params,
        }
        if system_prompt:
            request_body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        headers = {"Content-Type": "application/json"}

        params = {"key": self.api_key}

        if self.stream:
            url = f"{self.api_base}/models/{self.model}:streamGenerateContent"
            params["alt"] = "sse"

            def generator():
                result = {"content": ""}
                with httpx.stream("POST", url, headers=headers, params=params, json=request_body) as response:
                    for chunk in response.iter_lines():
                        message = {"content": ""}
                        if not chunk.startswith("data:"):
                            continue
                        data = json.loads(chunk[5:])
                        chunk_content = data["candidates"][0]["content"]["parts"][0]
                        if "text" in chunk_content:
                            message["content"] = chunk_content["text"]
                            result["content"] += message["content"]
                        elif "functionCall" in chunk_content:
                            message["tool_calls"] = [
                                {
                                    "index": 0,
                                    "id": 0,
                                    "function": {
                                        "arguments": json.dumps(
                                            chunk_content["functionCall"]["args"], ensure_ascii=False
                                        ),
                                        "name": chunk_content["functionCall"]["name"],
                                    },
                                    "type": "function",
                                }
                            ]

                        result["usage"] = message["usage"] = {
                            "prompt_tokens": data["usageMetadata"]["promptTokenCount"],
                            "completion_tokens": data["usageMetadata"]["candidatesTokenCount"],
                            "total_tokens": data["usageMetadata"]["totalTokenCount"],
                        }
                        yield message

            return generator()
        else:
            url = f"{self.api_base}/models/{self.model}:generateContent"
            response = httpx.post(url, json=request_body, headers=headers, params=params, timeout=None).json()
            result = {
                "content": "",
                "usage": {
                    "prompt_tokens": response["usageMetadata"]["promptTokenCount"],
                    "completion_tokens": response["usageMetadata"]["candidatesTokenCount"],
                    "total_tokens": response["usageMetadata"]["totalTokenCount"],
                },
            }
            tool_calls = []
            for part in response["candidates"][0]["content"]["parts"]:
                if "text" in part:
                    result["content"] += part["text"]
                elif "functionCall" in part:
                    tool_calls.append(part["functionCall"])

            if tool_calls:
                result["tool_calls"] = tool_calls

            return result


class AsyncGeminiChatClient(BaseAsyncChatClient):
    DEFAULT_MODEL: str = "gemini-1.5-pro"

    def __init__(
        self,
        model: str = "gemini-1.5-pro",
        stream: bool = True,
        temperature: float = 0.7,
        context_length_control: str = "latest",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.context_length_control = context_length_control
        settings = Settings()
        self.api_base = settings.get("gemini_api_base")
        self.api_key = settings.get("gemini_api_key")

    async def create_completion(
        self,
        messages: list = list,
        model: str | None = None,
        stream: bool | None = None,
        temperature: float | None = None,
        max_tokens: int = 2000,
        tools: list | None = None,
        tool_choice: str | None = None,
    ):
        if model is not None:
            self.model = model
        if stream is not None:
            self.stream = stream
        if temperature is not None:
            self.temperature = temperature

        if messages[0].get("role") == "system":
            system_prompt = messages[0]["content"]
            messages = messages[1:]
        else:
            system_prompt = ""

        if self.context_length_control == "latest":
            messages = cutoff_messages(
                messages, max_count=MODEL_MAX_INPUT_LENGTH[self.model], backend="gemini", model=self.model
            )

        if tools:
            tools_params = {"tools": [{"function_declarations": [tool["function"] for tool in tools]}]}
        else:
            tools_params = {}

        request_body = {
            "contents": messages,
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": max_tokens,
            },
            **tools_params,
        }
        if system_prompt:
            request_body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        headers = {"Content-Type": "application/json"}

        params = {"key": self.api_key}

        if self.stream:
            url = f"{self.api_base}/models/{self.model}:streamGenerateContent"
            params["alt"] = "sse"

            async def generator():
                result = {"content": ""}
                client = httpx.AsyncClient()
                async with client.stream("POST", url, headers=headers, params=params, json=request_body) as response:
                    async for chunk in response.aiter_lines():
                        message = {"content": ""}
                        if not chunk.startswith("data:"):
                            continue
                        data = json.loads(chunk[5:])
                        chunk_content = data["candidates"][0]["content"]["parts"][0]
                        if "text" in chunk_content:
                            message["content"] = chunk_content["text"]
                            result["content"] += message["content"]
                        elif "functionCall" in chunk_content:
                            message["tool_calls"] = [
                                {
                                    "index": 0,
                                    "id": 0,
                                    "function": {
                                        "arguments": json.dumps(
                                            chunk_content["functionCall"]["args"], ensure_ascii=False
                                        ),
                                        "name": chunk_content["functionCall"]["name"],
                                    },
                                    "type": "function",
                                }
                            ]

                        result["usage"] = message["usage"] = {
                            "prompt_tokens": data["usageMetadata"]["promptTokenCount"],
                            "completion_tokens": data["usageMetadata"]["candidatesTokenCount"],
                            "total_tokens": data["usageMetadata"]["totalTokenCount"],
                        }
                        yield message

            return generator()
        else:
            url = f"{self.api_base}/models/{self.model}:generateContent"
            async with httpx.AsyncClient(headers=headers, params=params, timeout=None) as client:
                response = await client.post(url, json=request_body)
                response = response.json()
                result = {
                    "content": "",
                    "usage": {
                        "prompt_tokens": response["usageMetadata"]["promptTokenCount"],
                        "completion_tokens": response["usageMetadata"]["candidatesTokenCount"],
                        "total_tokens": response["usageMetadata"]["totalTokenCount"],
                    },
                }
                tool_calls = []
                for part in response["candidates"][0]["content"]["parts"]:
                    if "text" in part:
                        result["content"] += part["text"]
                    elif "functionCall" in part:
                        tool_calls.append(part["functionCall"])

                if tool_calls:
                    result["tool_calls"] = tool_calls

                return result
