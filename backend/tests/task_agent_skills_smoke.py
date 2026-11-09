"""Run a real desktop task flow with selected Skills, activation, reference reads, and child sub-agent delegation."""
from __future__ import annotations

import json
import os
import shutil
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
from vv_agent.session.sqlite import SQLiteStore  # noqa: E402

initialize()
setting = Setting.select().order_by(Setting.create_time.desc()).first()
setting.data["llm_settings"] = {
    "VERSION": "2",
    "endpoints": [{
        "id": "mock-endpoint",
        "api_base": f"http://127.0.0.1:{port}/v1",
        "api_key": "local-test-credential-skills",
    }],
    "backends": {
        "local": {
            "models": {
                "mock-skill-model": {
                    "id": "mock-skill-model",
                    "enabled": True,
                    "endpoints": ["mock-endpoint"],
                    "function_call_available": True,
                    "context_length": 32768,
                    "max_output_tokens": 2048,
                    "supported_reasoning_efforts": ["low"],
                    "capabilities": {"reasoning_efforts": ["low"]},
                },
            },
        },
    },
}
setting.data["custom_llms"] = {"local-test": ["mock-skill-model"]}
setting.data["model_preferences"] = {"default": {"model_provider": "_local__local-test", "model": "mock-skill-model"}}
setting.save()
database.close()

# Create two skills: one selected ("domain-guide") from an imported directory with a bundled reference,
# and one unselected ("unselected-secret-skill").
import_src = workspace / "external_skill_src"
(import_src / "references").mkdir(parents=True, exist_ok=True)
(import_src / "SKILL.md").write_text(
    "---\n"
    "name: domain-guide\n"
    "description: Domain guide for synthetic verification\n"
    "allowed-tools: bash write_file\n"
    "---\n\n"
    "SYNTHETIC_SKILL_MARKER_V1: Read `references/spec.txt` in this skill directory and delegate verification to worker.\n",
    encoding="utf-8",
)
(import_src / "references" / "spec.txt").write_text("BUNDLED_REF_VALUE_V1_4242", encoding="utf-8")

service = TaskAgentService(workspace)
try:
    imported = service.import_skill({"skill_id": "domain_guide", "path": str(import_src)})
    assert imported["version"] == 1
    service.save_skill({
        "skill_id": "unselected_skill",
        "content": "---\nname: unselected-secret-skill\ndescription: Must not be exposed\n---\n\nUNSELECTED_BODY\n",
    })

    # Configure agent profile with allow_file_writes=False, allow_shell=False, allow_sub_agents=True, permission_mode="ask"
    # Even though SKILL.md frontmatter says `allowed-tools: bash write_file`, shell and write_file must remain disabled!
    # And reading the bundled reference inside the pinned skill directory must NOT trigger an outside-workspace approval wait.
    service.save_profile({
        "agent_id": "skill_worker_agent",
        "name": "Skill Worker Agent",
        "description": "Uses domain-guide skill without shell or write access",
        "instructions": "Use domain-guide skill and worker sub-agent.",
        "max_cycles": 10,
        "allow_file_writes": False,
        "allow_shell": False,
        "allow_sub_agents": True,
        "permission_mode": "ask",
        "skill_ids": ["domain_guide"],
    })

    # Mutate and delete the original import source directory before creating the task
    (import_src / "references" / "spec.txt").write_text("MUTATED_SOURCE_MUST_NOT_BE_USED", encoding="utf-8")
    shutil.rmtree(import_src)

    created = service.create_task({
        "input_id": "task_skill_smoke",
        "turn_input_id": "turn_1",
        "goal": "Activate domain-guide, read its bundled spec.txt, and have worker verify.",
        "agent_id": "skill_worker_agent",
        "model_provider": "_local__local-test",
        "model": "mock-skill-model",
        "reasoning_effort": "low",
    })

    for _ in range(80):
        detail = service.get_task("task_skill_smoke")
        if detail["task"]["status"] in {"COMPLETED", "FAILED", "WAITING_FOR_APPROVAL", "WAITING_FOR_USER"}:
            break
        time.sleep(0.2)

    assert detail["task"]["status"] == "COMPLETED", detail
    assert "BUNDLED_REF_VALUE_V1_4242" in detail["messages"][-1]["content"], detail
    assert "WORKER_VERIFIED_V1" in detail["messages"][-1]["content"], detail

    # Verify timeline contains activate_skill and read_file tool calls
    tool_names = [entry.get("tool_name") for entry in detail["timeline"] if entry.get("kind") == "tool"]
    assert "activate_skill" in tool_names, tool_names
    assert "read_file" in tool_names, tool_names
    assert "create_sub_task" in tool_names, tool_names

    # Now update the skill in the library to v2 and then delete it from the catalog altogether!
    v2 = service.save_skill({
        "skill_id": "domain_guide",
        "content": "---\nname: domain-guide\ndescription: Updated v2\n---\n\nSYNTHETIC_SKILL_MARKER_V2\n",
    })
    assert v2["version"] == 2
    service.delete_skill({"skill_id": "domain_guide", "expected_updated_at": v2["updated_at"]})
finally:
    service.stop()

# Restart TaskAgentService and send a follow-up turn on the existing task;
# it must still load the pinned v1 revision ("SYNTHETIC_SKILL_MARKER_V1" and "BUNDLED_REF_VALUE_V1_4242")!
resumed = TaskAgentService(workspace)
try:
    resumed.send_message({
        "task_id": "task_skill_smoke",
        "input_id": "turn_2",
        "text": "Re-activate domain-guide after restart and confirm the v1 marker.",
    })
    for _ in range(80):
        detail = resumed.get_task("task_skill_smoke")
        if detail["task"]["status"] in {"COMPLETED", "FAILED", "WAITING_FOR_APPROVAL", "WAITING_FOR_USER"} and len(detail["messages"]) == 4:
            break
        time.sleep(0.2)
    assert detail["task"]["status"] == "COMPLETED", detail
    assert len(detail["messages"]) == 4, detail
    assert "FOLLOWUP_CONFIRMED_V1:SYNTHETIC_SKILL_MARKER_V1" in detail["messages"][-1]["content"], detail
finally:
    resumed.stop()

with SQLiteStore.standalone(str(resumed.task_root / "sessions.db")) as ledger:
    tables = [r[0] for r in ledger.connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    dump = "\n".join(str(r) for tbl in tables for r in ledger.connection.execute(f"SELECT * FROM {tbl}").fetchall())
    assert "local-test-credential-skills" not in dump

print(json.dumps({"status": "COMPLETED", "turns": 2}, ensure_ascii=False))