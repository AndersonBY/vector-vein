import base64
import json
from types import SimpleNamespace

import pytest

from utilities import desktop_notifications as notifications


def test_windows_notification_passes_untrusted_text_as_stdin_not_shell_code(monkeypatch):
    calls = []
    monkeypatch.setattr(notifications.sys, "platform", "win32")
    monkeypatch.setattr(notifications.shutil, "which", lambda _: "powershell.exe")
    monkeypatch.setattr(notifications.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(notifications.subprocess, "run", lambda args, **kwargs: (calls.append((args, kwargs)), SimpleNamespace(returncode=0))[1])
    title, body = '"; $(secret)', "<tag>&中文 `value`"
    assert notifications.send_notification(title, body)
    args, options = calls[0]
    script = base64.b64decode(args[-1]).decode("utf-16le")
    assert title not in script and body not in script
    assert "SecurityElement]::Escape" in script
    assert json.loads(options["input"]) == {"title": title, "body": body}
    assert options["creationflags"] == 0x08000000 and options["timeout"] == 15
    assert "shell" not in options


@pytest.mark.parametrize("value", [None, {"enabled": "yes"}, {"enabled": True, "language": "bad"}, {"enabled": True, "command": "bad"}])
def test_notification_settings_are_validated(value):
    with pytest.raises(ValueError):
        notifications.validate_notification_settings(value)


def test_disabled_notifications_never_start_native_process_and_enabled_messages_are_private(monkeypatch):
    settings = {"enabled": False, "language": "en-US"}
    calls = []
    monkeypatch.setattr("utilities.config.Settings", lambda: SimpleNamespace(get=lambda *_: settings))
    monkeypatch.setattr(notifications, "send_notification", lambda *args: calls.append(args))
    monkeypatch.setattr(notifications.threading, "Thread", lambda *, target, args, **_: SimpleNamespace(start=lambda: target(*args)))
    notifications.notify_task_finished("COMPLETED")
    assert calls == []
    settings["enabled"] = True
    for status in ("COMPLETED", "FAILED", "INTERRUPTED"):
        notifications.notify_task_finished(status)
    assert calls == [("VectorVein", "Agent task completed."), ("VectorVein", "Agent task failed. Open the task for details."), ("VectorVein", "Agent task stopped.")]


def test_test_notification_reports_native_submission_failure(monkeypatch):
    from api.user_api import SettingAPI
    calls = []
    monkeypatch.setattr(notifications, "send_notification", lambda *args: (calls.append(args), False)[1])
    result = SettingAPI().test_notification({"language": "zh-CN"})
    assert result["status"] == 503 and result["data"]["submitted"] is False
    assert calls == [("VectorVein", "这是一条 VectorVein 测试通知。")]
    assert SettingAPI().test_notification({"language": "bad"})["status"] == 400
