# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:38:43
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-12-22 21:55:10
from .chat_clients import create_chat_client


def conversation_title_generator(messages: list):
    zhipuai_client = create_chat_client("zhipuai", stream=False)
    conversation_text = ""
    for message in messages:
        conversation_text += f'{message["role"]}:\n{message["content"]}\n\n'
    prompt = "你是一个用户对话标题生成器，我会给你提供用户和AI的对话内容，请你生成1个简洁的标题，不超过10个字。\n对话内容：\n"
    messages = [{"role": "user", "content": f"{prompt}{conversation_text}"}]
    summary = zhipuai_client.create_completion(messages)["content"]
    return summary
