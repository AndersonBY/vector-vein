# @Author: Bi Ying
# @Date:   2024-03-29 01:26:27
import time

import httpx

from utilities.general import Retry, mprint
from utilities.ai_utils import get_token_counts
from .base_llm import BaseLLMTask
from .types.output import ModelOutput
from .types.model import ModelSetting, EndpointSetting


endpoints = [
    EndpointSetting(
        endpoint_settings_key="minimax_api_base",
        api_key_settings_key="minimax_api_key",
        rpm=120,
        tpm=360000,
    )
]


class MiniMaxTask(BaseLLMTask):
    NAME: str = "minimax"
    DEFAULT_MODEL: str = "abab5.5-chat"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "abab5-chat": ModelSetting(
            id="abab5-chat",
            endpoints=endpoints,
            max_tokens=6144,
        ),
        "abab5.5-chat": ModelSetting(
            id="abab5.5-chat",
            endpoints=endpoints,
            max_tokens=16384,
        ),
        "abab6-chat": ModelSetting(
            id="abab6-chat",
            endpoints=endpoints,
            max_tokens=32768,
        ),
        "abab6.5s-chat": ModelSetting(
            id="abab6.5s-chat",
            endpoints=endpoints,
            max_tokens=245000,
        ),
    }

    def process_prompt(
        self,
        prompt: str,
        index: int,
    ) -> ModelOutput:
        mprint(f"Processing prompt {index + 1}/{self.prompts_count}")
        token_counts = get_token_counts(prompt, self.model_settings.id)
        max_tokens = self.model_settings.max_tokens - token_counts - 200

        url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        headers = {"Content-Type": "application/json"}
        request_body = {
            "model": self.model_settings.id,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "max_tokens": max_tokens,
            "temperature": self.temperature,
            "mask_sensitive_info": False,
        }

        request_success = False
        response = None
        start_time = time.time()
        while time.time() - start_time < self.SINGLE_PROCESS_TIMEOUT and not request_success:
            has_available_endpoint = False
            for endpoint in self.model_settings.endpoints:
                if endpoint.model_available(self.model_settings.id):
                    has_available_endpoint = True
                    headers["Authorization"] = f"Bearer {endpoint.api_key}"
                    url = endpoint.endpoint
                    break
            if not has_available_endpoint:
                time.sleep(1)
                continue

            request_success, response = (
                Retry(httpx.post)
                .args(url=url, headers=headers, json=request_body, timeout=120)
                .retry_times(5)
                .sleep_time(10)
                .rate_limit(
                    product=f"{self.model_settings.id}:{endpoint.api_key}",
                    cycle=60,
                    max_count=endpoint.rpm,
                )
                .run()
            )

        if not request_success:
            mprint.error(f"MiniMax request failed: {response}")
            return ModelOutput(
                content_output="",
                prompt_tokens=0,
                completion_tokens=0,
            )

        response = response.json()
        if response["base_resp"]["status_code"] != 0:
            mprint.error("MiniMax request failed", response)
            return ModelOutput(
                content_output="",
                prompt_tokens=0,
                completion_tokens=0,
            )

        content_output = response["choices"][0]["message"]["content"]
        prompt_tokens = token_counts
        completion_tokens = max(0, response["usage"]["total_tokens"] - token_counts)

        return ModelOutput(
            content_output=content_output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
