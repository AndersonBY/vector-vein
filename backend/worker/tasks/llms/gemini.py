# @Author: Bi Ying
# @Date:   2024-03-29 01:34:55
import time

import httpx

from utilities.general import Retry, mprint
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting
from .types.output import ModelOutput


gemini_1_0_pro_endpoints = [
    EndpointSetting(
        endpoint_settings_key="gemini_api_base",
        api_key_settings_key="gemini_api_key",
        rpm=50,
        tpm=360000,
    )
]

gemini_1_5_pro_endpoints = [
    EndpointSetting(
        endpoint_settings_key="gemini_api_base",
        api_key_settings_key="gemini_api_key",
        rpm=2,
        tpm=3600000,
    )
]

gemini_1_5_flash_endpoints = [
    EndpointSetting(
        endpoint_settings_key="gemini_api_base",
        api_key_settings_key="gemini_api_key",
        rpm=15,
        tpm=1000000,
    )
]


class GeminiTask(BaseLLMTask):
    NAME: str = "gemini"
    DEFAULT_MODEL: str = "gemini-1.0-pro"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "gemini-1.0-pro": ModelSetting(
            id="gemini-1.0-pro",
            endpoints=gemini_1_0_pro_endpoints,
            max_output_tokens=2048,
        ),
        "gemini-1.5-pro": ModelSetting(
            id="gemini-1.5-pro",
            endpoints=gemini_1_5_pro_endpoints,
            max_output_tokens=8192,
        ),
        "gemini-1.5-flash": ModelSetting(
            id="gemini-1.5-flash",
            endpoints=gemini_1_5_flash_endpoints,
            max_output_tokens=8192,
        ),
    }

    def process_prompt(
        self,
        prompt: str,
        index: int,
    ) -> ModelOutput:
        mprint(f"Processing prompt {index + 1}/{self.prompts_count}")
        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.model_settings.max_output_tokens,
            },
        }
        headers = {"Content-Type": "application/json"}

        request_success = False
        content_output = ""
        start_time = time.time()
        while time.time() - start_time < self.SINGLE_PROCESS_TIMEOUT and not request_success:
            has_available_endpoint = False
            for endpoint in self.model_settings.endpoints:
                if endpoint.model_available(self.model_settings.id):
                    has_available_endpoint = True
                    break
            if not has_available_endpoint:
                time.sleep(1)
                continue

            sleep_time = 60 // endpoint.rpm

            url = f"{endpoint.endpoint}/models/{self.model_settings.id}:generateContent"
            params = {"key": endpoint.api_key}
            mprint("url", url)

            request_success, response = (
                Retry(httpx.post)
                .args(
                    url=url,
                    json=request_body,
                    headers=headers,
                    params=params,
                    timeout=None,
                )
                .retry_times(5)
                .sleep_time(sleep_time)
                .rate_limit(
                    product=f"{self.model_settings.id}:{endpoint.endpoint}:{endpoint.api_key}",
                    cycle=60,
                    max_count=endpoint.rpm,
                )
                .run()
            )
            if response.status_code != 200:
                mprint.error(f"Gemini request failed: {response}")
                break

            response = response.json()
            try:
                content_output = response["candidates"][0]["content"]["parts"][0]["text"]
                prompt_tokens = response["usageMetadata"]["promptTokenCount"]
                completion_tokens = response["usageMetadata"]["candidatesTokenCount"]
                break
            except Exception as e:
                mprint.error(f"Failed to get content_output: {e}")
                mprint.error(f"Response: {response}")

        if not request_success:
            mprint.error(f"Gemini request failed: {response}")
            return ModelOutput(
                content_output="",
                prompt_tokens=0,
                completion_tokens=0,
            )

        return ModelOutput(
            content_output=content_output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
