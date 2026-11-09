"""Run a real desktop task flow against a local model endpoint."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


workspace = Path(sys.argv[1]).resolve()
port = int(sys.argv[2])
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(workspace)

from cli import initialize  # noqa: E402
from models import Setting, database  # noqa: E402
from task_agent.service import TaskAgentService  # noqa: E402


initialize()
setting = Setting.select().order_by(Setting.create_time.desc()).first()
setting.data["llm_settings"] = {
    "VERSION": "2",
    "endpoints": [{
        "id": "mock-endpoint",
        "api_base": f"http://127.0.0.1:{port}/v1",
        "api_key": "local-test-credential",
    }],
    "backends": {
        "local": {
            "models": {
                "mock-task-model": {
                    "id": "mock-task-model",
                    "enabled": True,
                    "endpoints": ["mock-endpoint"],
                    "function_call_available": False,
                    "context_length": 32768,
                    "max_output_tokens": 2048,
                    "supported_reasoning_efforts": ["low", "max"],
                    "capabilities": {"reasoning_efforts": ["low", "max"]},
                },
            },
        },
    },
}
setting.data["custom_llms"] = {"local-test": ["mock-task-model"]}
setting.data["model_preferences"] = {"default": {"model_provider": "_local__local-test", "model": "mock-task-model"}}
setting.save()
database.close()


from api.task_agent_api import _call  # noqa: E402
from vv_agent.config import ConfigError  # noqa: E402

def invalid_config():
    raise ConfigError("An endpoint credential is no longer available")

assert _call(invalid_config)["data"]["model_failure"]["category"] == "credentials_missing"

service = TaskAgentService(workspace)
try:
    for status, expected in ((401,"authentication"),(404,"model_not_found"),(422,"parameter"),(500,"service")):
        setting.data["llm_settings"]["endpoints"][0]["api_base"] = f"http://127.0.0.1:{port}/{status}/v1"
        setting.save()
        tid = "error_" + str(status)
        service.create_task({"input_id":tid,"turn_input_id":"start","goal":"Test a model failure", "model_provider":"_local__local-test", "model":"mock-task-model"})
        for _ in range(120):
            detail = service.get_task(tid)
            if detail["task"]["status"] == "FAILED":
                break
            time.sleep(0.1)
        assert detail["task"]["status"] == "FAILED", detail
        errors = [item for item in detail["timeline"] if item["kind"] == "error"]
        assert errors[-1]["model_failure"]["category"] == expected, detail
        assert errors[-1]["model_failure"]["http_status"] == status
        assert detail["model_rejection_only"] is (status != 500), detail
        assert "SECRET_PROVIDER_BODY" not in json.dumps(detail)
        assert "local-test-credential" not in json.dumps(detail)
finally:
    service.stop()

service = TaskAgentService(workspace)
try:
    restored = service.get_task("error_401")
    assert next(item for item in restored["timeline"] if item["kind"] == "error")["model_failure"]["category"] == "authentication"
    assert "SECRET_PROVIDER_BODY" not in (workspace / "data/task-agent/tasks.db").read_bytes().decode("utf-8", errors="ignore")
    print(json.dumps({"passed": True,"cases":4,"restored":True}))
finally:
    service.stop()
