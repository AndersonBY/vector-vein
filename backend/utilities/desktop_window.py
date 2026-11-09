"""Desktop close policy and the Windows notification-area icon."""

from __future__ import annotations

import logging
import sys
import threading

from utilities.config import config

logger = logging.getLogger(__name__)
CLOSE_ACTIONS = frozenset({"ask", "tray", "exit"})
_controller = None


def get_controller():
    return _controller


def window_settings():
    action = config.get("window.close_action", "ask")
    controller = get_controller()
    return {
        "close_action": action if isinstance(action, str) and action in CLOSE_ACTIONS else "ask",
        "tray_available": bool(controller and controller.tray_available),
    }


def save_close_action(action):
    if not isinstance(action, str) or action not in CLOSE_ACTIONS:
        raise ValueError("Invalid window close action")
    config.save("window.close_action", action)


def _labels():
    if config.get("language", "zh-CN") == "en-US":
        return {
            "title": "Close VectorVein",
            "message": "Minimize to the system tray to keep tasks and schedules running.\nExiting stops background execution.",
            "remember": "Do not ask again (change this in Settings → Window & tray)",
            "tray": "Minimize to tray",
            "exit": "Exit",
            "cancel": "Cancel",
            "open": "Open VectorVein",
            "unavailable": "The system tray is unavailable. You can exit or cancel.",
        }
    return {
        "title": "关闭 VectorVein",
        "message": "缩小到托盘后，任务与定时调度会继续运行。\n直接退出将停止后台运行。",
        "remember": "不再询问（可在“设置 → 窗口与托盘”中修改）",
        "tray": "缩小到托盘",
        "exit": "直接退出",
        "cancel": "取消",
        "open": "打开 VectorVein",
        "unavailable": "系统托盘暂不可用，可以直接退出或取消。",
    }


def build_close_dialog(tray_available):
    """Construct without showing, so native controls can also be checked headlessly."""
    from System.Drawing import Size, SizeF, Point
    from System.Windows.Forms import (
        AutoScaleMode, Button, CheckBox, DialogResult, Form, FormBorderStyle,
        FormStartPosition, Label,
    )

    labels = _labels()
    dialog = Form()
    dialog.Text = labels["title"]
    dialog.ClientSize = Size(540, 206)
    dialog.AutoScaleDimensions = SizeF(96, 96)
    dialog.AutoScaleMode = AutoScaleMode.Dpi
    dialog.FormBorderStyle = FormBorderStyle.FixedDialog
    dialog.StartPosition = FormStartPosition.CenterParent
    dialog.ShowInTaskbar = False
    dialog.ShowIcon = False
    dialog.MinimizeBox = False
    dialog.MaximizeBox = False
    text = Label()
    text.Text = labels["message"] if tray_available else labels["unavailable"]
    text.Location = Point(24, 22)
    text.Size = Size(492, 60)
    remember = CheckBox()
    remember.Text = labels["remember"]
    remember.Location = Point(24, 94)
    remember.Size = Size(492, 30)
    dialog.Controls.Add(text)
    dialog.Controls.Add(remember)
    for index, (key, result) in enumerate((
        ("cancel", DialogResult.Cancel), ("exit", DialogResult.Yes), ("tray", DialogResult.No),
    )):
        button = Button()
        button.Text = labels[key]
        button.DialogResult = result
        button.Location = Point(24 + index * 166, 150)
        button.Size = Size(160, 34)
        button.Enabled = key != "tray" or tray_available
        dialog.Controls.Add(button)
        if key == "cancel":
            dialog.CancelButton = button
        if key == ("tray" if tray_available else "exit"):
            dialog.AcceptButton = button
    return dialog, remember


def show_close_dialog(window, tray_available):
    if sys.platform != "win32":
        # Keep the window reachable on platforms without an installed tray adapter.
        labels = _labels()
        result = window.create_confirmation_dialog(labels["title"], labels["message"])
        return ("exit" if result else "cancel"), False
    from System.Windows.Forms import DialogResult

    dialog, remember = build_close_dialog(tray_available)
    try:
        result = dialog.ShowDialog(window.native)
        action = "exit" if result == DialogResult.Yes else "tray" if result == DialogResult.No else "cancel"
        return action, bool(remember.Checked)
    finally:
        dialog.Dispose()


class WindowsTray:
    def __init__(self, window, restore, exit_app):
        self.window = window
        self.restore = restore
        self.exit_app = exit_app
        self.icon = None
        self.menu = None
        self.image = None
        self.available = False

    def start(self):
        self._create_icon()
        self.icon.Visible = True
        self.available = True

    def _create_icon(self):
        from bootstrap import APP_ROOT
        from System.Drawing import Icon
        from System.Windows.Forms import ContextMenuStrip, NotifyIcon

        labels = _labels()
        self.menu = ContextMenuStrip()
        self.menu.Items.Add(labels["open"]).Click += self._restore
        self.menu.Items.Add(labels["exit"]).Click += self._exit
        self.icon = NotifyIcon()
        image_path = APP_ROOT / "web" / "favicon.ico"
        if image_path.is_file():
            self.image = Icon(str(image_path))
        self.icon.Icon = self.image or self.window.native.Icon
        self.icon.Text = "VectorVein"
        self.icon.ContextMenuStrip = self.menu
        self.icon.DoubleClick += self._restore

    def _restore(self, *_):
        threading.Thread(target=self.restore, daemon=True, name="tray-restore").start()

    def _exit(self, *_):
        threading.Thread(target=self.exit_app, daemon=True, name="tray-exit").start()

    def stop(self):
        self.available = False
        if self.icon is not None:
            self.icon.Visible = False
            self.icon.Dispose()
            self.icon = None
        if self.menu is not None:
            self.menu.Dispose()
            self.menu = None
        if self.image is not None:
            self.image.Dispose()
            self.image = None


class DesktopWindowController:
    def __init__(self, window, *, prompt=show_close_dialog, tray_factory=None):
        self.window = window
        self.prompt = prompt
        self.tray = None
        self.exiting = False
        self.prompting = False
        self.in_tray = False
        self._tray_factory = tray_factory or (WindowsTray if sys.platform == "win32" else None)

    @property
    def tray_available(self):
        return bool(self.tray and self.tray.available)

    def start(self):
        global _controller
        _controller = self
        if self._tray_factory:
            try:
                self.tray = self._tray_factory(self.window, self.restore, self.exit_app)
                self.tray.start()
            except Exception:
                logger.warning("System tray initialization failed", exc_info=False)
                self.stop()

    def minimize_to_tray(self):
        if not self.tray_available or self.exiting:
            raise RuntimeError("System tray unavailable")
        self.window.hide()
        self.in_tray = True

    def restore(self):
        if self.exiting:
            return
        self.window.show()
        if str(getattr(self.window.native, "WindowState", "")) == "Minimized":
            self.window.restore()
        self.in_tray = False

    def exit_app(self):
        self.exiting = True
        self.window.destroy()

    def on_closing(self):
        if self.exiting:
            return True
        if self.prompting:
            return False
        action = window_settings()["close_action"]
        if action == "exit":
            self.exiting = True
            return True
        if action == "tray" and self.tray_available:
            try:
                self.minimize_to_tray()
                return False
            except Exception:
                logger.warning("Could not minimize to system tray", exc_info=False)
        self.prompting = True
        try:
            action, remember = self.prompt(self.window, self.tray_available)
            if self.exiting:
                return True
            if action == "cancel":
                return False
            if action == "tray":
                self.minimize_to_tray()
            elif action != "exit":
                return False
            if remember:
                save_close_action(action)
            if action == "exit":
                self.exiting = True
                return True
        except Exception:
            logger.warning("Window close action failed; keeping the window open", exc_info=False)
            if self.in_tray:
                self.restore()
        finally:
            self.prompting = False
        return False

    def stop(self):
        global _controller
        try:
            if self.tray:
                self.tray.stop()
        except Exception:
            logger.warning("System tray cleanup failed", exc_info=False)
        finally:
            if _controller is self:
                _controller = None
