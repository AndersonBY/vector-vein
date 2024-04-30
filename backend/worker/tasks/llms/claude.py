# @Author: Bi Ying
# @Date:   2024-03-29 01:33:37
import time

from anthropic import Anthropic
from anthropic.types.message import Message

from utilities.print_utils import mprint
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting
from .types.output import ModelOutput


class ClaudeTask(BaseLLMTask):
    NAME: str = "claude"
    DEFAULT_MODEL: str = "claude-3-haiku-20240307"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "claude-3-haiku": ModelSetting(
            id="claude-3-haiku-20240307",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="anthropic_api_base",
                    api_key_settings_key="anthropic_api_key",
                    rpm=50,
                    tpm=50000,
                )
            ],
        ),
        "claude-3-sonnet": ModelSetting(
            id="claude-3-sonnet-20240229",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="anthropic_api_base",
                    api_key_settings_key="anthropic_api_key",
                    rpm=50,
                    tpm=40000,
                )
            ],
        ),
        "claude-3-opus": ModelSetting(
            id="claude-3-opus-20240229",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="anthropic_api_base",
                    api_key_settings_key="anthropic_api_key",
                    rpm=50,
                    tpm=30000,
                )
            ],
        ),
        # deprecated models below
        "claude-2": ModelSetting(
            id="claude-2.1",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="anthropic_api_base",
                    api_key_settings_key="anthropic_api_key",
                    rpm=50,
                    tpm=30000,
                )
            ],
        ),
        "claude-2.1": ModelSetting(
            id="claude-2.1",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="anthropic_api_base",
                    api_key_settings_key="anthropic_api_key",
                    rpm=50,
                    tpm=30000,
                )
            ],
        ),
        "claude-instant-1": ModelSetting(
            id="claude-instant-1",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="anthropic_api_base",
                    api_key_settings_key="anthropic_api_key",
                    rpm=50,
                    tpm=30000,
                )
            ],
        ),
    }

    def process_prompt(
        self,
        prompt: str,
        index: int,
    ) -> ModelOutput:
        mprint(f"Processing prompt {index + 1}/{self.prompts_count}")

        request_success = False
        response = None
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

            anthropic = Anthropic(
                api_key=endpoint.api_key,
                base_url=endpoint.endpoint,
            )

            response = anthropic.messages.create(
                model=self.model_settings.id,
                max_tokens=4096,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            request_success = True

        response: Message = response
        content_output = response.content[0].text
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens

        return ModelOutput(
            content_output=content_output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
