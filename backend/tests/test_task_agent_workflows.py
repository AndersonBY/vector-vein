import json
import os
import subprocess
import sys
from pathlib import Path


def test_provider_runs_real_workflow_and_preserves_admission_feedback_and_artifacts(tmp_path):
    env = {key: value for key, value in os.environ.items() if key not in {"VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR"}}
    result = subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).with_name("task_agent_workflow_smoke.py"))],
                            cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == {"passed": True, "workflow_runs": 4, "artifacts": 1}
