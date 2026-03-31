from __future__ import annotations

from typing import Any

import pytest
from vv_llm.types import BackendType

from worker.tasks.llms.base_llm import BaseLLMTask
from worker.tasks.llms.universal_llm import UniversalLLMTask


def _build_workflow_data(provider: str) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "node-1",
                "type": "UniversalLlm",
                "category": "llms",
                "data": {
                    "task_name": "llms.universal_llm",
                    "template": {
                        "model_provider": {"value": provider},
                    },
                },
            }
        ],
        "edges": [],
    }


def _noop_base_init(self: Any, workflow_data: dict[str, Any], node_id: str) -> None:
    self.node_id = node_id


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("xAI", BackendType.XAI),
        (" XAI ", BackendType.XAI),
        ("stepfun", BackendType.StepFun),
        ("OpenAI", BackendType.OpenAI),
        ("unknown-provider", BackendType.OpenAI),
    ],
)
def test_universal_llm_normalizes_provider_names(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    expected: BackendType,
) -> None:
    monkeypatch.setattr(BaseLLMTask, "__init__", _noop_base_init)

    task = UniversalLLMTask(_build_workflow_data(provider), "node-1")

    assert task.MODEL_TYPE is expected
