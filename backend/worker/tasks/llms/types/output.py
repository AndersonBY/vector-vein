from typing import Optional

import pydantic


class ModelOutput(pydantic.BaseModel):
    content_output: Optional[str] = None
    reasoning_content: Optional[str] = None
    tool_calls: Optional[list] = None
    function_call_arguments: Optional[dict] = None
    prompt_tokens: int
    completion_tokens: int
