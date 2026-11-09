import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Job integration")


def context_at(tmp_path, task_id="root/turn/one", parent=None):
    from vv_agent.tools.base import ToolContext
    from vv_agent.workspace.local import LocalWorkspaceBackend
    from task_agent.host import command_shell

    metadata = {"bash_shell": command_shell({"allow_shell": True})["executable"]}
    if parent:
        metadata["parent_run_id"] = parent
    return ToolContext(
        workspace=tmp_path,
        workspace_backend=LocalWorkspaceBackend(tmp_path),
        shared_state={},
        cycle_index=1,
        task_id=task_id,
        tool_call_id="tool-call",
        task_metadata=metadata,
    )


@pytest.fixture
def manager():
    from task_agent.windows_commands import WindowsCommands

    value = WindowsCommands()
    try:
        yield value
    finally:
        value.shutdown()


def await_terminal(manager, context, identifier, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = manager.check(context, {"session_id": identifier})
        payload = json.loads(result.content)
        if payload.get("status") in {"completed", "failed", "timeout", "stopped"}:
            return result, payload
        time.sleep(0.05)
    raise AssertionError(payload)


def python_command(code):
    # Git Bash accepts this quoted Windows executable path.
    import shlex

    return shlex.quote(sys.executable.replace("\\", "/")) + " -c " + shlex.quote(code)


def test_foreground_stdout_exit_code_and_repeated_query(tmp_path, manager):
    workspace = tmp_path / "工作 space [1]"
    workspace.mkdir()
    context = context_at(workspace)
    result = manager.run(
        context,
        {
            "command": "printf '中文 176'; printf '文件' > '结果.txt'",
            "yield_time_ms": 10000,
        },
    )
    payload = json.loads(result.content)
    assert payload["status"] == "completed" and payload["exit_code"] == 0
    assert payload["output"] == "中文 176"
    assert payload["session_id"].startswith("bg_") and not payload["session_id"].startswith("bg_win_")
    assert result.error_code is None
    assert (workspace / "结果.txt").read_text(encoding="utf-8") == "文件"
    queried = json.loads(
        manager.check(context, {"session_id": payload["session_id"]}).content
    )
    assert queried == payload
    session = manager.sessions[payload["session_id"]]
    assert session.job.job is None and session.job.process is None
    assert not session.capture.exists()


def test_failed_command_is_not_success_or_unknown(tmp_path, manager):
    context = context_at(tmp_path)
    result = manager.run(
        context, {"command": "printf failure; exit 7", "yield_time_ms": 10000}
    )
    payload = json.loads(result.content)
    assert payload["status"] == "failed" and payload["exit_code"] == 7
    assert result.error_code and payload["output"] == "failure"


def test_shell_exit_does_not_finish_live_detached_descendant(tmp_path, manager):
    context = context_at(tmp_path)
    marker = tmp_path / "descendant-finished.txt"
    child = f"import time,pathlib;time.sleep(2);pathlib.Path({marker.as_posix()!r}).write_text('finished')"
    parent = f"import subprocess,sys;subprocess.Popen([sys.executable,'-c',{child!r}],creationflags=subprocess.DETACHED_PROCESS,stdin=subprocess.DEVNULL);print('parent-finished',flush=True)"
    initial = json.loads(
        manager.run(
            context, {"command": python_command(parent), "yield_time_ms": 0}
        ).content
    )
    deadline = time.monotonic() + 8
    saw_parent = False
    while time.monotonic() < deadline:
        payload = json.loads(
            manager.check(context, {"session_id": initial["session_id"]}).content
        )
        if "parent-finished" in payload.get("output", "") and not marker.exists():
            assert payload["status"] == "running" and "exit_code" not in payload
            saw_parent = True
            break
        time.sleep(0.02)
    assert saw_parent
    _, finished = await_terminal(manager, context, initial["session_id"])
    assert finished["status"] == "completed" and marker.read_text() == "finished"


@pytest.mark.parametrize("action", ["timeout", "stop", "cancel"])
def test_timeout_stop_and_parent_cancellation_terminate_descendants(
    tmp_path, manager, action
):
    context = context_at(
        tmp_path, "root/child/worker/turn/start", parent="root/turn/one"
    )
    ready = tmp_path / "child-ready"
    child = f"from pathlib import Path;import time;Path({ready.as_posix()!r}).write_text('ready');time.sleep(30)"
    parent = f"import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',{child!r}],creationflags=subprocess.DETACHED_PROCESS,stdin=subprocess.DEVNULL);time.sleep(30)"
    args = {"command": python_command(parent), "yield_time_ms": 0}
    if action == "timeout":
        args["timeout_seconds"] = 3
    initial = json.loads(manager.run(context, args).content)
    deadline = time.monotonic() + 5
    while not ready.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert ready.exists()
    if action == "stop":
        manager.stop(context, {"session_id": initial["session_id"]})
    if action == "cancel":
        manager.on_event(SimpleNamespace(type="run_cancelled", run_id="root/turn/one"))
    result, payload = await_terminal(manager, context, initial["session_id"])
    assert payload["status"] == ("timeout" if action == "timeout" else "stopped")
    assert payload["exit_code"] is not None
    assert (result.error_code is not None) == (action == "timeout")
    if action == "cancel":
        assert (
            manager.run(context, {"command": "echo should-not-run"}).error_code
            == "command_cancelled"
        )


def test_handle_ownership_and_missing_handles(tmp_path, manager):
    context = context_at(tmp_path)
    initial = json.loads(
        manager.run(context, {"command": "sleep 10", "yield_time_ms": 0}).content
    )
    handle = {"session_id": initial["session_id"]}
    assert (
        manager.stop(replace(context, task_id="other"), handle).error_code
        == "background_session_forbidden"
    )
    assert (
        manager.check(replace(context, workspace=tmp_path.parent), handle).error_code
        == "background_session_forbidden"
    )
    assert (
        manager.check(context, {"session_id": "bg_old-process"}).error_code
        == "background_session_missing"
    )
    assert json.loads(manager.stop(context, handle).content)["status"] == "stopped"


def test_output_artifact_and_parallel_capture_isolation(tmp_path, manager):
    context = context_at(tmp_path)

    def execute(index):
        local = replace(context, tool_call_id=f"parallel-{index}")
        return json.loads(
            manager.run(
                local, {"command": f"printf result-{index}", "yield_time_ms": 10000}
            ).content
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(execute, range(4)))
    assert [p["output"] for p in outputs] == [f"result-{i}" for i in range(4)]
    from vv_agent.workspace.local import LocalWorkspaceBackend
    class OwningWorkspaceBackend(LocalWorkspaceBackend):
        task_id = "owning-workspace"
    context = replace(context, workspace_backend=OwningWorkspaceBackend(tmp_path))
    large = manager.run(
        context,
        {"command": python_command("print('中文输出'*20000)"), "yield_time_ms": 10000},
    )
    payload = json.loads(large.content)
    assert payload["status"] == "completed" and payload["output_truncated"]
    assert payload["artifact"] and large.truncated
    assert manager.sessions[payload["session_id"]].artifact is not None
    from vv_agent.workspace.artifacts import is_task_artifact_path
    assert is_task_artifact_path(payload["artifact"]["path"], task_id="owning-workspace")
    assert not is_task_artifact_path(payload["artifact"]["path"], task_id=context.task_id)


def test_stdin_is_a_file_and_cannot_block_initial_yield(tmp_path, manager):
    context = context_at(tmp_path)
    value = "输入数据" * 50000
    payload = json.loads(
        manager.run(
            context,
            {
                "command": python_command("import sys;print(len(sys.stdin.read()))"),
                "stdin": value,
                "yield_time_ms": 0,
            },
        ).content
    )
    _, payload = await_terminal(manager, context, payload["session_id"])
    assert payload["status"] == "completed" and payload["output"].strip() == str(
        len(value)
    )


def test_supervision_failure_never_resumes_user_code(tmp_path, monkeypatch):
    import task_agent.windows_job as module

    marker = tmp_path / "must-not-exist"
    monkeypatch.setattr(module, "AssignJob", lambda *args: 0)
    with (
        tempfile.TemporaryFile("w+b") as stdin,
        tempfile.TemporaryFile("w+b") as output,
    ):
        with pytest.raises(OSError):
            module.WindowsJob(
                [
                    sys.executable,
                    "-c",
                    f"from pathlib import Path;Path({marker.as_posix()!r}).write_text('unsafe')",
                ],
                cwd=tmp_path,
                stdin_file=stdin,
                output_file=output,
                env=os.environ,
            )
    assert not marker.exists()


def test_exit_code_259_is_terminal_not_still_active(tmp_path):
    from task_agent.windows_job import WindowsJob

    with (
        tempfile.TemporaryFile("w+b") as stdin,
        tempfile.TemporaryFile("w+b") as output,
    ):
        job = WindowsJob(
            [sys.executable, "-c", "import sys;sys.exit(259)"],
            cwd=tmp_path,
            stdin_file=stdin,
            output_file=output,
            env=os.environ,
        )
        try:
            deadline = time.monotonic() + 8
            while job.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            assert job.poll() == 259
        finally:
            job.close()


def test_abrupt_host_exit_kills_owned_child_and_grandchild(tmp_path):
    from ctypes import wintypes as W
    from task_agent.windows_job import bind, Wait, CloseHandle

    open_process = bind("OpenProcess", W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
    owner = subprocess.Popen(
        [
            sys._base_executable,
            str(Path(__file__).with_name("task_agent_windows_job_owner.py")),
            str(tmp_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    handles = []
    try:
        deadline = time.monotonic() + 10
        while (
            not (tmp_path / "grandchild.pid").exists() and time.monotonic() < deadline
        ):
            assert owner.poll() is None
            time.sleep(0.02)
        for name in ("child.pid", "grandchild.pid"):
            handle = open_process(0x100000, False, int((tmp_path / name).read_text()))
            assert handle
            handles.append(handle)
            assert Wait(handle, 0) == 258
        owner.kill()
        owner.wait(timeout=5)
        assert all(Wait(handle, 5000) == 0 for handle in handles)
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)
        for handle in handles:
            CloseHandle(handle)


def test_null_command_is_rejected_before_launch(tmp_path, manager):
    result = manager.run(context_at(tmp_path), {"command": "echo before\0echo after"})
    assert result.error_code == "invalid_tool_arguments"
    assert not manager.sessions


def test_observation_failure_stays_unknown_but_timeout_still_terminates(
    tmp_path, manager
):
    from task_agent.windows_job import Wait

    context = context_at(tmp_path)
    initial = json.loads(
        manager.run(
            context, {"command": "sleep 30", "yield_time_ms": 0, "timeout_seconds": 1}
        ).content
    )
    session = manager.sessions[initial["session_id"]]
    original_poll = session.job.poll

    def unavailable():
        raise OSError("synthetic observation failure")

    with session.lock:
        session.job.poll = unavailable
    try:
        assert Wait(session.job.process, 5000) == 0
        observed = json.loads(
            manager.check(context, {"session_id": initial["session_id"]}).content
        )
        assert (
            observed["status"] in {"unknown", "stopping"}
            and "exit_code" not in observed
        )
    finally:
        with session.lock:
            session.job.poll = original_poll
    _, terminal = await_terminal(manager, context, initial["session_id"])
    assert terminal["status"] == "timeout"


def test_old_turn_cancellation_cannot_stop_a_new_turn(tmp_path, manager):
    context = context_at(tmp_path, "root/turn/two")
    initial = json.loads(
        manager.run(
            context, {"command": "sleep 1; printf next-turn", "yield_time_ms": 0}
        ).content
    )
    manager.on_event(SimpleNamespace(type="run_cancelled", run_id="root/turn/one"))
    _, result = await_terminal(manager, context, initial["session_id"])
    assert result["status"] == "completed" and result["output"] == "next-turn"
