"""Native desktop notifications with fixed commands and data passed separately."""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import threading


def validate_notification_settings(value):
    if not isinstance(value, dict) or set(value) - {"enabled", "language"} or type(value.get("enabled")) is not bool:
        raise ValueError("Invalid notification settings")
    if value.get("language", "zh-CN") not in {"zh-CN", "en-US"}:
        raise ValueError("Invalid notification language")
    return {"enabled": value["enabled"], "language": value.get("language", "zh-CN")}


def send_notification(title, body):
    if not isinstance(title, str) or not isinstance(body, str) or len(title) > 160 or len(body) > 500:
        return False
    options = {"capture_output": True, "timeout": 15}
    if sys.platform == "win32":
        exe = shutil.which("powershell.exe")
        if not exe:
            return False
        script = r'''
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [Text.UTF8Encoding]::new()
$data = [Console]::In.ReadToEnd() | ConvertFrom-Json
$appId = 'VectorVein.Desktop'
$registration = 'HKCU:\Software\Classes\AppUserModelId\VectorVein.Desktop'
if (-not (Test-Path -LiteralPath $registration)) { New-Item -Path $registration -Force | Out-Null }
New-ItemProperty -LiteralPath $registration -Name DisplayName -Value 'VectorVein' -PropertyType String -Force | Out-Null
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null
$title = [Security.SecurityElement]::Escape([string]$data.title)
$body = [Security.SecurityElement]::Escape([string]$data.body)
$xml = [Windows.Data.Xml.Dom.XmlDocument]::new()
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text>' + $title + '</text><text>' + $body + '</text></binding></visual></toast>')
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
'''
        args = [exe, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(script.encode("utf-16le")).decode("ascii")]
        options.update(input=json.dumps({"title": title, "body": body}, ensure_ascii=False).encode("utf-8"),
                       creationflags=subprocess.CREATE_NO_WINDOW)
    elif sys.platform == "darwin":
        exe = shutil.which("osascript")
        if not exe:
            return False
        args = [exe, "-e", "on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run", "--", title, body]
    else:
        exe = shutil.which("notify-send")
        if not exe:
            return False
        args = [exe, "--app-name=VectorVein", "--", title, body]
    try:
        return subprocess.run(args, **options).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def notify_task_finished(status):
    try:
        from utilities.config import Settings
        settings = validate_notification_settings(Settings().get("notifications", {"enabled": False}))
    except Exception:
        return
    if not settings["enabled"]:
        return
    if settings["language"] == "zh-CN":
        body = {"COMPLETED": "Agent 任务已完成。", "FAILED": "Agent 任务执行失败，请打开任务查看。", "INTERRUPTED": "Agent 任务已停止。"}[status]
    else:
        body = {"COMPLETED": "Agent task completed.", "FAILED": "Agent task failed. Open the task for details.", "INTERRUPTED": "Agent task stopped."}[status]
    # Do not put prompts, results, filenames or provider errors on the lock screen.
    try:
        threading.Thread(target=send_notification, args=("VectorVein", body), daemon=True, name="desktop-notification").start()
    except RuntimeError:
        pass
