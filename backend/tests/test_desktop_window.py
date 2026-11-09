from types import SimpleNamespace
from unittest.mock import Mock
import os
from pathlib import Path
import subprocess
import sys

import pytest

from utilities import desktop_window as desktop


class MemoryConfig:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def save(self, key, value):
        self.values[key] = value


class FakeTray:
    def __init__(self, window, restore, exit_app):
        self.available = False
        self.restore = restore
        self.exit_app = exit_app
        self.stopped = 0

    def start(self):
        self.available = True

    def stop(self):
        self.available = False
        self.stopped += 1


@pytest.fixture
def setup_window(monkeypatch):
    settings = MemoryConfig()
    monkeypatch.setattr(desktop, "config", settings)
    monkeypatch.setattr(desktop, "_controller", None)
    window = SimpleNamespace(hide=Mock(), show=Mock(), restore=Mock(), destroy=Mock(),
                             native=SimpleNamespace(WindowState="Maximized"))
    return window, settings


def controller(window, action="cancel", remember=False, **kwargs):
    prompt = Mock(return_value=(action, remember))
    result = desktop.DesktopWindowController(window, prompt=prompt, tray_factory=kwargs.get("tray_factory", FakeTray))
    result.start()
    return result, prompt


def test_default_prompt_cancel_never_hides_exits_or_remembers(setup_window):
    window, settings = setup_window
    app, prompt = controller(window, remember=True)
    assert app.on_closing() is False
    prompt.assert_called_once_with(window, True)
    assert settings.values == {}
    window.hide.assert_not_called()
    window.destroy.assert_not_called()
    assert app.exiting is False


def test_tray_choice_keeps_application_alive_and_restores_maximized_window(setup_window):
    window, settings = setup_window
    app, _ = controller(window, "tray")
    assert app.on_closing() is False
    window.hide.assert_called_once()
    window.destroy.assert_not_called()
    assert app.in_tray and not app.exiting
    assert desktop.window_settings() == {"close_action": "ask", "tray_available": True}
    app.tray.restore()
    window.show.assert_called_once()
    window.restore.assert_not_called()
    assert app.in_tray is False
    window.native.WindowState = "Minimized"
    app.restore()
    window.restore.assert_called_once()
    assert settings.values == {}


@pytest.mark.parametrize("action,allowed", [("tray", False), ("exit", True)])
def test_remembered_choice_applies_on_later_closes_and_settings_can_reset_it(setup_window, action, allowed):
    window, settings = setup_window
    app, _ = controller(window, action, True)
    assert app.on_closing() is allowed
    assert settings.get("window.close_action") == action
    restarted, prompt = controller(window)
    assert restarted.on_closing() is allowed
    prompt.assert_not_called()
    desktop.save_close_action("ask")
    fresh, prompt = controller(window)
    assert fresh.on_closing() is False
    prompt.assert_called_once()


def test_explicit_tray_exit_bypasses_remembered_tray_without_changing_preference(setup_window):
    window, settings = setup_window
    settings.save("window.close_action", "tray")
    app, prompt = controller(window)
    app.tray.exit_app()
    window.destroy.assert_called_once()
    assert app.on_closing() is True
    prompt.assert_not_called()
    assert settings.get("window.close_action") == "tray"
    tray = app.tray
    app.stop()
    assert tray.stopped == 1
    assert desktop.get_controller() is None


def test_unavailable_tray_and_native_failures_never_leave_an_inaccessible_application(setup_window):
    window, settings = setup_window
    settings.save("window.close_action", "tray")

    class BrokenTray(FakeTray):
        def start(self):
            raise RuntimeError("Synthetic tray failure")

    app, prompt = controller(window, "cancel", tray_factory=BrokenTray)
    assert not app.tray_available
    assert app.on_closing() is False
    prompt.assert_called_once_with(window, False)
    window.hide.assert_not_called()
    window.destroy.assert_not_called()
    with pytest.raises(RuntimeError):
        app.minimize_to_tray()
    app.prompt = Mock(side_effect=RuntimeError("Synthetic dialog failure"))
    assert app.on_closing() is False
    assert not app.prompting
    app.prompt = Mock(return_value=("exit", False))
    assert app.on_closing() is True


def test_reentrant_close_and_failed_hide_are_cancelled_safely(setup_window):
    window, _ = setup_window
    app, _ = controller(window, "tray", True)
    window.hide.side_effect = RuntimeError("Synthetic hide failure")
    assert app.on_closing() is False
    assert not app.in_tray and not app.exiting
    assert desktop.window_settings()["close_action"] == "ask"
    app.prompt = Mock(side_effect=lambda *_: ("cancel" if app.on_closing() is False else "exit", False))
    assert app.on_closing() is False
    assert app.prompt.call_count == 1


@pytest.mark.parametrize("invalid", [None, [], {}, True, 1, "quit", ""])
def test_invalid_close_policy_is_rejected_and_corrupt_configuration_defaults_to_ask(setup_window, invalid):
    _, settings = setup_window
    with pytest.raises(ValueError):
        desktop.save_close_action(invalid)
    settings.save("window.close_action", invalid)
    assert desktop.window_settings()["close_action"] == "ask"


def test_window_settings_api_saves_without_loading_models_or_requiring_a_visible_window(setup_window):
    from api.user_api import SettingAPI
    window, settings = setup_window
    api = SettingAPI()
    assert api.get_window_setting({})["data"] == {"close_action": "ask", "tray_available": False}
    assert api.update_window_setting({"close_action": "tray"})["status"] == 200
    assert settings.get("window.close_action") == "tray"
    assert api.update_window_setting({"close_action": "bad"})["status"] == 400
    assert api.minimize_to_tray({})["status"] == 503
    app, _ = controller(window)
    assert api.minimize_to_tray({})["status"] == 200
    window.hide.assert_called_once()
    app.tray.stop = Mock(side_effect=RuntimeError("Synthetic cleanup failure"))
    app.stop()
    assert desktop.get_controller() is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native controls")
@pytest.mark.parametrize("bundled_icon", [True, False], ids=["bundled-icon", "native-icon-fallback"])
def test_windows_close_dialog_controls_construct_without_displaying_ui(tmp_path, bundled_icon):
    script = r'''
import shutil
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import clr
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
from System import Object
from System.Drawing import SystemIcons
from System.Windows.Forms import Button, DialogResult, Form, NotifyIcon
import bootstrap
bootstrap.APP_ROOT = Path.cwd() / "isolated-app"
image_path = bootstrap.APP_ROOT / "web" / "favicon.ico"
bundled_icon = sys.argv[2] == "True"
if bundled_icon:
    source_icon = Path(sys.argv[1]).parent / "frontend" / "public" / "favicon.ico"
    assert source_icon.is_file(), f"Tracked icon fixture is missing: {source_icon}"
    image_path.parent.mkdir(parents=True)
    shutil.copyfile(source_icon, image_path)
assert image_path.is_file() == bundled_icon, f"Incorrect isolated icon fixture: {image_path}"
from utilities.desktop_window import build_close_dialog, WindowsTray
from types import SimpleNamespace
for available in (True, False):
    dialog, remember = build_close_dialog(available)
    try:
        assert not dialog.Visible and not dialog.ShowInTaskbar, "Close dialog must remain hidden"
        assert not remember.Checked, "Remember choice must default to unchecked"
        buttons = [control for control in dialog.Controls if isinstance(control, Button)]
        assert len(buttons) == 3, f"Expected three close buttons, got {len(buttons)}"
        assert dialog.CancelButton.DialogResult == DialogResult.Cancel, "Cancel button result is incorrect"
        tray = next(button for button in buttons if button.DialogResult == DialogResult.No)
        assert tray.Enabled == available, f"Tray button enabled state differs from availability={available}"
        assert dialog.AcceptButton.DialogResult == (DialogResult.No if available else DialogResult.Yes), \
            f"Incorrect default button for tray availability={available}"
    finally:
        dialog.Dispose()
icon = NotifyIcon()
assert not icon.Visible, "New notification icon must remain hidden"
icon.Dispose()
native = Form()
native_icon = SystemIcons.Application.Clone()
native.Icon = native_icon
tray = WindowsTray(SimpleNamespace(native=native), lambda: None, lambda: None)
try:
    tray._create_icon()
    assert not native.Visible and not tray.icon.Visible, "Native form and tray icon must remain hidden"
    assert tray.icon.Icon is not None, f"Tray icon is missing (bundled_icon={bundled_icon})"
    if bundled_icon:
        assert tray.image is not None, f"Bundled icon was not loaded from {image_path}"
        assert Object.ReferenceEquals(tray.icon.Icon, tray.image), "Tray must use the loaded bundled icon"
        assert not Object.ReferenceEquals(tray.icon.Icon, native.Icon), "Bundled icon must take priority over native icon"
    else:
        assert tray.image is None, "Missing bundled icon must not create a loaded image"
        assert Object.ReferenceEquals(tray.icon.Icon, native.Icon), "Tray must fall back to the real native icon"
    assert tray.icon.Text == "VectorVein", f"Unexpected tray tooltip: {tray.icon.Text!r}"
    assert tray.icon.ContextMenuStrip.Items.Count == 2, "Tray menu must contain restore and exit actions"
finally:
    tray.stop()
    native.Dispose()
    native_icon.Dispose()
assert tray.icon is None and not tray.available, "Tray cleanup must clear the icon and availability"
from utilities.config import config, cache
config.close()
cache.close()
'''
    env = {key: value for key, value in os.environ.items()
           if key not in {"VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR"}}
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", script, str(Path(__file__).resolve().parents[1]), str(bundled_icon)],
                            cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, (
        f"Headless Windows controls check failed (bundled_icon={bundled_icon}, exit={result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
