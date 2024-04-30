# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-20 13:53:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-04-30 15:13:17
import re
import json
import xml.etree.ElementTree as ET

import tiktoken


chatgpt_encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

DEFAULT_ROLE_KEY = "role"
ROLE_KEY_MAP = {
    "minimax": "sender_type",
}
DEFAULT_CONTENT_KEY = "content"
CONTENT_KEY_MAP = {
    "minimax": "text",
}

tool_use_re = re.compile(r"<\|▶\|>(.*?)<\|◀\|>", re.DOTALL)


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
    if model == "gpt-3.5-turbo":
        return len(chatgpt_encoding.encode(text))
    else:
        return len(chatgpt_encoding.encode(text))


def cutoff_messages(messages: list, max_count: int = 16000, backend: str = "openai") -> list:
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

    role_key = ROLE_KEY_MAP.get(backend, DEFAULT_ROLE_KEY)
    content_key = CONTENT_KEY_MAP.get(backend, DEFAULT_CONTENT_KEY)

    if len(messages) == 0:
        return messages

    messages_length = 0

    # 先检查并保留第一条system消息（如果有）
    system_message = None
    if messages[0][role_key] == "system":
        system_message = messages[0]
        system_message_length = get_token_counts(system_message["content"])
        if system_message_length > max_count:
            # 如果第一条system消息超过最大长度，截断它
            system_message["content"] = system_message["content"][-max_count:]
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
        messages_length += get_token_counts(message[content_key])
        if messages_length < max_count:
            continue
        if index == 0:
            # 一条消息就超过长度则将该消息内容进行截断，保留该消息最后的一部分
            content = message[content_key][max_count - messages_length :]
            return system_message + [
                {
                    role_key: message[role_key],
                    content_key: content,
                }
            ]
        return system_message + messages[-index:]
    return system_message + messages


def _format_messages_openai(messages: list, backend: str = "openai"):
    formatted_messages = []
    for message in messages:
        content = message["content"]["text"]
        if message["content_type"] == "TXT":
            if message.get("attachments"):
                content += "\n# Attachments:\n"
                content += "\n".join([f"- {attachment}" for attachment in message["attachments"]])
            formatted_message = {
                "role": "user" if message["author_type"] == "U" else "assistant",
                "content": content,
            }
            formatted_messages.append(formatted_message)
        elif message["content_type"] == "WKF" and message["status"] in ("S", "R"):
            # TODO: 目前只考虑单个 tool_call 的情况
            if backend in ("openai", "zhipuai"):
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

            if backend in ("openai", "zhipuai"):
                tool_call_result_message = {
                    "role": "tool",
                    "tool_call_id": message["metadata"]["selected_workflow"]["tool_call_id"],
                    "name": message["metadata"]["selected_workflow"]["function_name"],
                    "content": message["metadata"].get("workflow_result", ""),
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

            if content and backend != "mistral":
                formatted_messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                    }
                )
        else:
            continue

    return formatted_messages


def format_messages(messages: list, backend: str = "openai"):
    """将VectorVein的Message序列化后的格式转换为不同模型支持的格式

    Args:
        messages (list): _description_
        backend (str, optional): _description_. Defaults to "openai".

    Returns:
        _type_: _description_
    """
    return _format_messages_openai(messages, backend=backend)


def generate_tool_use_system_prompt(tools: list, format_type: str = "openai") -> str:
    if format_type == "openai":
        return (
            "You have access to the following tools. Use them if required and wait for the tool call result. Stop output after calling a tool.\n\n"
            f"# Tools\n{tools}\n\n"
            "# Requirements when using tools\n"
            "Must starts with <|▶|> and ends with <|◀|>\n"
            "Must be valid JSON format and pay attention to escape characters.\n"
            '## Output format\n<|▶|>{"name": "<function name:str>", "arguments": <arguments:dict>}<|◀|>\n\n'
            '## Example output\n<|▶|>{"name": "get_current_weather", "arguments": {"location": "San Francisco, CA"}}<|◀|>'
        )
    elif format_type == "anthropic":
        # Anthropic 用 XML 格式，也许是他们训练时候数据集格式？
        return (
            "You have access to the following tools. Use them if required and wait for the tool call result. Stop output after calling a tool.\n\n"
            f"# Tools\n{tools}\n\n"
            "# Requirements when using tools\n"
            "Must starts with <|▶|> and ends with <|◀|>\n"
            "Must be valid XML format.\n"
            "## Output format\n<|▶|><invoke><tool_name>[function name:str]</tool_name><parameters><parameter_1_name>[parameter_1_value]</parameter_1_name><parameter_2_name>[parameter_2_value]</parameter_2_name>...</parameters></invoke><|◀|>\n\n"
            "## Example output\n<|▶|><invoke><tool_name>calculator</tool_name><parameters><first_operand>1984135</first_operand><second_operand>9343116</second_operand><operator>*</operator></parameters></invoke><|◀|>"
        )


def get_tool_call_data_in_openai_format(content: str, input_format: str = "openai", tools: list | None = None) -> dict:
    if "<|▶|>" not in content or "<|◀|>" not in content:
        return {}
    tool_calls_matches = tool_use_re.findall(content)
    if tool_calls_matches:
        if input_format == "openai":
            arguments_or_parameters = "arguments"
            try:
                tool_call_data = json.loads(tool_calls_matches[0])
            except json.JSONDecodeError:
                print(f"Failed to parse tool call data:\nContent: {content}\nMatch: {tool_calls_matches[0]}")
                return {}
        elif input_format == "anthropic":
            arguments_or_parameters = "parameters"
            try:
                root = ET.fromstring(tool_calls_matches[0])
                tool_call_data = {"name": "", "parameters": {}}
                for child in root:
                    if child.tag == "tool_name":
                        tool_call_data["name"] = child.text
                    elif child.tag == "parameters":
                        for param in child:
                            # param_type = param_types.get(param.tag, "string")
                            # tool_call_data["parameters"][param.tag] = convert_type(param.text, param_type)
                            tool_call_data["parameters"][param.tag] = param.text
                param_types = {}
                for tool in tools:
                    if tool["function"]["name"] != tool_call_data["name"]:
                        continue
                    parameters_definition = tool["function"]["parameters"]["properties"]
                    for param in parameters_definition:
                        param_types[param] = parameters_definition[param]["type"]
                tool_call_data["parameters"] = {
                    k: convert_type(v, param_types.get(k, "string")) for k, v in tool_call_data["parameters"].items()
                }
            except Exception:
                print(f"Failed to parse tool call data:\nContent: {content}\nMatch: {tool_calls_matches[0]}")
                return {}

        return {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "fc1",
                    "function": {
                        "arguments": json.dumps(tool_call_data[arguments_or_parameters], ensure_ascii=False),
                        "name": tool_call_data["name"],
                    },
                    "type": "function",
                }
            ]
        }
    else:
        return {}
