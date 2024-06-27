# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-20 13:53:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-25 22:13:25
import re
import json

import tiktoken

from utilities.general import mprint
from utilities.media_processing import ImageProcessor


chatgpt_encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
gpt_4o_encoding = tiktoken.encoding_for_model("gpt-4o")

tool_use_re = re.compile(r"<\|▶\|>(.*?)<\|◀\|>", re.DOTALL)


def get_assistant_role_key(backend: str) -> str:
    if backend == "gemini":
        return "model"
    else:
        return "assistant"


def get_content_key(backend: str) -> str:
    if backend == "gemini":
        return "parts"
    else:
        return "content"


def convert_type(value, value_type):
    if value_type == "string":
        return str(value)
    elif value_type == "number":
        try:
            return float(value)
        except ValueError:
            return value
    elif value_type == "integer":
        try:
            return int(value)
        except ValueError:
            return value
    elif value_type == "boolean":
        return value.lower() in ("true", "1", "t")
    else:
        return value  # 如果类型未知，返回原始值


def get_token_counts(text: str, model: str = "gpt-3.5-turbo") -> int:
    if not isinstance(text, str):
        text = str(text)
    if model == "gpt-3.5-turbo":
        return len(chatgpt_encoding.encode(text))
    elif model == "gpt-4o":
        return len(gpt_4o_encoding.encode(text))
    elif model.startswith("abab"):
        return int(len(text) / 1.33)
    else:
        return len(chatgpt_encoding.encode(text))


def cutoff_messages(
    messages: list,
    max_count: int = 16000,
    backend: str = "openai",
    model: str = "gpt-3.5-turbo",
) -> list:
    """
    给定一个消息列表和最大长度，将消息列表截断到最大长度。
    如果列表中第一个元素的role是'system'，则始终保留该元素。
    超过长度时从列表开始处（第二个元素起）依次删除消息，直到总长度小于等于最大长度。
    如果最后一条消息超过了最大长度，那么将最后一条消息截断到最大长度。

    Args:
        messages (list): 消息列表，每条消息是一个包含'role'和'content'的字典。
        max_count (int, optional): 允许的最大长度。默认值为16000。

    Returns:
        list: 截断后的消息列表。
    """

    if len(messages) == 0:
        return messages

    messages_length = 0
    content_key = get_content_key(backend)

    # 先检查并保留第一条system消息（如果有）
    system_message = None
    if messages[0]["role"] == "system":
        system_message = messages[0]
        system_message_length = get_token_counts(system_message[content_key], model)
        if system_message_length > max_count:
            # 如果第一条system消息超过最大长度，截断它
            system_message[content_key] = system_message[content_key][-max_count:]
            return [system_message]
        else:
            messages_length += system_message_length
            messages = messages[1:]  # 移除第一个元素，以处理其余消息

    if system_message:
        system_message = [system_message]
    else:
        system_message = []

    for index, message in enumerate(reversed(messages)):
        if not message[content_key]:
            continue
        messages_length += get_token_counts(message[content_key], model)
        if messages_length < max_count:
            continue
        if index == 0:
            # 一条消息就超过长度则将该消息内容进行截断，保留该消息最后的一部分
            if backend == "gemini":
                message[content_key] = [{"text": message[content_key][-max_count:]}]
            else:
                content = message[content_key][max_count - messages_length :]
            return system_message + [
                {
                    "role": message["role"],
                    content_key: content,
                }
            ]
        return system_message + messages[-index:]
    return system_message + messages


def format_image_message(image: str, backend: str = "openai") -> dict:
    image_processor = ImageProcessor(image_source=image)
    if backend == "openai":
        return {
            "type": "image_url",
            "image_url": {"url": image_processor.data_url},
        }
    elif backend == "anthropic":
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_processor.mime_type,
                "data": image_processor.base64_image,
            },
        }
    elif backend == "gemini":
        return {
            "inline_data": {
                "mime_type": image_processor.mime_type,
                "data": image_processor.base64_image,
            }
        }


def format_messages(messages: list, backend: str = "openai", native_multimodal: bool = False) -> list:
    """将 VectorVein 的 Message 序列化后的格式转换为不同模型支持的格式

    Args:
        messages (list): VectorVein messages list.
        backend (str, optional): Messages format target backend. Defaults to "openai".
        native_multimodal (bool, optional): Use native multimodal ability. Defaults to False.

    Returns:
        list: _description_
    """

    backend = backend.lower()
    formatted_messages = []
    for message in messages:
        content = message["content"]["text"]
        if message["content_type"] == "TXT":
            role = "user" if message["author_type"] == "U" else get_assistant_role_key(backend)
            if not message.get("attachments"):
                if backend == "gemini":
                    formatted_message = {"role": role, "parts": [{"text": content}]}
                else:
                    formatted_message = {"role": role, "content": content}
                formatted_messages.append(formatted_message)
                continue

            images_extensions = ("jpg", "jpeg", "png", "bmp")
            has_images = any(attachment.endswith(images_extensions) for attachment in message["attachments"])

            content += "\n# Attachments:\n"
            content += "\n".join([f"- {attachment}" for attachment in message["attachments"]])

            if native_multimodal and has_images:
                if backend == "gemini":
                    parts = [{"text": content}]
                    for attachment in message["attachments"]:
                        parts.append(format_image_message(image=attachment, backend=backend))
                    formatted_message = {"role": role, "parts": parts}
                else:
                    formatted_message = {
                        "role": role,
                        "content": [
                            {"type": "text", "text": content},
                            *[
                                format_image_message(image=attachment, backend=backend)
                                for attachment in message["attachments"]
                            ],
                        ],
                    }
                formatted_messages.append(formatted_message)
            else:
                if backend == "gemini":
                    formatted_message = {"role": role, "parts": [{"text": content}]}
                else:
                    formatted_message = {"role": role, "content": content}
                formatted_messages.append(formatted_message)
        elif message["content_type"] == "WKF" and message["status"] in ("S", "R"):
            # TODO: 目前只考虑单个 tool_call 的情况
            if backend in ("openai", "zhipuai", "mistral"):
                tool_call_message = {
                    "content": None,
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": message["metadata"]["selected_workflow"]["tool_call_id"],
                            "type": "function",
                            "function": {
                                "name": message["metadata"]["selected_workflow"]["function_name"],
                                "arguments": json.dumps(message["metadata"]["selected_workflow"]["params"]),
                            },
                        }
                    ],
                }
            elif backend == "anthropic":
                tool_call_message = {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": message["metadata"]["selected_workflow"]["tool_call_id"],
                            "name": message["metadata"]["selected_workflow"]["function_name"],
                            "input": message["metadata"]["selected_workflow"]["params"],
                        },
                    ],
                }
                if content:
                    tool_call_message["content"].insert(
                        0,
                        {
                            "type": "text",
                            "text": content,
                        },
                    )
            elif backend == "gemini":
                tool_call_message = {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "name": message["metadata"]["selected_workflow"]["function_name"],
                                "args": message["metadata"]["selected_workflow"]["params"],
                            }
                        },
                    ],
                }
                if content:
                    tool_call_message["parts"].insert(
                        0,
                        {
                            "text": content,
                        },
                    )
            else:
                tool_call_message = {
                    "content": json.dumps(
                        {
                            "name": message["metadata"]["selected_workflow"]["function_name"],
                            "arguments": json.dumps(message["metadata"]["selected_workflow"]["params"]),
                        },
                        ensure_ascii=False,
                    ),
                    "role": "assistant",
                }
            formatted_messages.append(tool_call_message)

            if backend in ("openai", "zhipuai", "mistral"):
                tool_call_result_message = {
                    "role": "tool",
                    "tool_call_id": message["metadata"]["selected_workflow"]["tool_call_id"],
                    "name": message["metadata"]["selected_workflow"]["function_name"],
                    "content": message["metadata"].get("workflow_result", ""),
                }
            elif backend == "anthropic":
                tool_call_result_message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message["metadata"]["selected_workflow"]["tool_call_id"],
                            "content": message["metadata"].get("workflow_result", ""),
                        }
                    ],
                }
            elif backend == "gemini":
                tool_call_result_message = {
                    "role": "function",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": message["metadata"]["selected_workflow"]["function_name"],
                                "response": {
                                    "name": message["metadata"]["selected_workflow"]["function_name"],
                                    "content": message["metadata"].get("workflow_result", ""),
                                },
                            }
                        }
                    ],
                }
            else:
                tool_call_result_message = {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "function": message["metadata"]["selected_workflow"]["function_name"],
                            "result": message["metadata"].get("workflow_result", ""),
                        },
                        ensure_ascii=False,
                    ),
                }
            formatted_messages.append(tool_call_result_message)

            if content and backend not in ("mistral", "anthropic", "gemini"):
                formatted_messages.append({"role": "assistant", "content": content})
        else:
            continue

    return formatted_messages


def generate_tool_use_system_prompt(tools: list, format_type: str = "json") -> str:
    if format_type == "json":
        return (
            "You have access to the following tools. Use them if required and wait for the tool call result. Stop output after calling a tool.\n\n"
            f"# Tools\n{tools}\n\n"
            "# Requirements when using tools\n"
            "Must starts with <|▶|> and ends with <|◀|>\n"
            "Must be valid JSON format and pay attention to escape characters.\n"
            '## Output format\n<|▶|>{"name": "<function name:str>", "arguments": <arguments:dict>}<|◀|>\n\n'
            '## Example output\n<|▶|>{"name": "get_current_weather", "arguments": {"location": "San Francisco, CA"}}<|◀|>'
        )
    elif format_type == "xml":
        return (
            "You have access to the following tools. Use them if required and wait for the tool call result. Stop output after calling a tool.\n\n"
            f"# Tools\n{tools}\n\n"
            "# Requirements when using tools\n"
            "Must starts with <|▶|> and ends with <|◀|>\n"
            "Must be valid XML format.\n"
            "## Output format\n<|▶|><invoke><tool_name>[function name:str]</tool_name><parameters><parameter_1_name>[parameter_1_value]</parameter_1_name><parameter_2_name>[parameter_2_value]</parameter_2_name>...</parameters></invoke><|◀|>\n\n"
            "## Example output\n<|▶|><invoke><tool_name>calculator</tool_name><parameters><first_operand>1984135</first_operand><second_operand>9343116</second_operand><operator>*</operator></parameters></invoke><|◀|>"
        )


def extract_tool_calls(content: str) -> dict:
    if "<|▶|>" not in content or "<|◀|>" not in content:
        return {}
    tool_calls_matches = tool_use_re.findall(content)
    if tool_calls_matches:
        tool_call_data = {}
        for match in tool_calls_matches:
            try:
                tool_call_data = json.loads(match)
            except json.JSONDecodeError:
                mprint.error(f"Failed to parse tool call data:\nContent: {content}\nMatch: {match}")

        if not tool_call_data:
            return {}

        arguments = json.dumps(tool_call_data["arguments"], ensure_ascii=False)
        return {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "fc1",
                    "function": {
                        "arguments": arguments,
                        "name": tool_call_data["name"],
                    },
                    "type": "function",
                }
            ]
        }
    else:
        return {}
