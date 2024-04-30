# @Author: Bi Ying
# @Date:   2024-04-11 20:57:20
from typing import List, Optional

import pydantic

from utilities.settings import Settings
from utilities.ratelimit import is_request_allowed, add_request_record


class EndpointSetting(pydantic.BaseModel):
    region: Optional[str] = None

    endpoint: Optional[str] = None

    endpoint_settings_key: Optional[str] = None
    """The key for current endpoint in settings. Useful for manual refresh."""

    api_key: Optional[str] = None

    api_key_settings_key: Optional[str] = None
    """The key for current api key in settings. Useful for manual refresh."""

    credentials: Optional[dict] = None

    is_azure: bool = False

    rpm: int
    """Requests per minute."""

    tpm: int
    """Tokens per minute."""

    def model_available(self, model_id: str, add_record: bool = True) -> bool:
        """
        Check if the model is available under the current rate limits.

        Args:
            model_id (str): The ID of the model to check.
            add_record (bool, optional): Whether to add a request record. Defaults to True.

        Returns:
            bool: True if the request is allowed, False otherwise.
        """
        product = f"{model_id}:{self.endpoint}:{self.api_key}"
        cycle = 60  # seconds
        max_count = self.rpm

        return is_request_allowed(product, cycle, max_count, add_record)

    def add_request_record(self, model_id: str) -> bool:
        """
        Add a request record for the model.

        Args:
            model_id (str): The ID of the model.

        Returns:
            bool: True if the record is added successfully, False otherwise.
        """
        product = f"{model_id}:{self.endpoint}:{self.api_key}"
        cycle = 60

        return add_request_record(product, cycle)


class ModelSetting(pydantic.BaseModel):
    id: Optional[str] = None
    """The id of the model."""

    id_settings_key: Optional[str] = None
    """The key for the model id in settings. Useful for manual refresh."""

    endpoints: List[EndpointSetting]
    """Available endpoints for the model."""

    function_call_available: bool = False

    response_format_available: bool = False

    concurrent: int = 5

    max_tokens: int = 4096

    max_output_tokens: Optional[int] = None

    def refresh(self):
        """
        Refresh settings for the model.
        """
        settings = Settings()
        if self.id_settings_key:
            self.id = settings.get(self.id_settings_key)
        for endpoint in self.endpoints:
            endpoint.endpoint = settings.get(endpoint.endpoint_settings_key)
            endpoint.api_key = settings.get(endpoint.api_key_settings_key)
