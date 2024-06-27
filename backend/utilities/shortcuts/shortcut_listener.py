# @Author: Bi Ying
# @Date:   2024-06-11 14:39:59
import string

from pynput import keyboard

from utilities.general import mprint


modifier_keys = {
    keyboard.Key.ctrl,
    keyboard.Key.ctrl_l,
    keyboard.Key.ctrl_r,
    keyboard.Key.alt,
    keyboard.Key.alt_l,
    keyboard.Key.alt_r,
    keyboard.Key.shift,
    keyboard.Key.shift_l,
    keyboard.Key.shift_r,
    keyboard.Key.cmd,
    keyboard.Key.cmd_l,
    keyboard.Key.cmd_r,
}

special_key_values = {
    keyboard.Key.f1.value.vk: keyboard.Key.f1,
    keyboard.Key.f2.value.vk: keyboard.Key.f2,
    keyboard.Key.f3.value.vk: keyboard.Key.f3,
    keyboard.Key.f4.value.vk: keyboard.Key.f4,
    keyboard.Key.f5.value.vk: keyboard.Key.f5,
    keyboard.Key.f6.value.vk: keyboard.Key.f6,
    keyboard.Key.f7.value.vk: keyboard.Key.f7,
    keyboard.Key.f8.value.vk: keyboard.Key.f8,
    keyboard.Key.f9.value.vk: keyboard.Key.f9,
    keyboard.Key.f10.value.vk: keyboard.Key.f10,
    keyboard.Key.f11.value.vk: keyboard.Key.f11,
    keyboard.Key.f12.value.vk: keyboard.Key.f12,
    keyboard.Key.home.value.vk: keyboard.Key.home,
    keyboard.Key.end.value.vk: keyboard.Key.end,
    keyboard.Key.insert.value.vk: keyboard.Key.insert,
    keyboard.Key.pause.value.vk: keyboard.Key.pause,
    keyboard.Key.print_screen.value.vk: keyboard.Key.print_screen,
    keyboard.Key.scroll_lock.value.vk: keyboard.Key.scroll_lock,
    keyboard.Key.num_lock.value.vk: keyboard.Key.num_lock,
}

normal_keys_names = set(string.ascii_lowercase + string.digits + string.punctuation + string.whitespace)


def is_combination_key(current_keys):
    has_modifier = any(k in modifier_keys for k in current_keys)
    has_alphanumeric = any(hasattr(k, "char") and (k.char in normal_keys_names) for k in current_keys)
    has_special = any(hasattr(k, "value") and k.value.vk in special_key_values.keys() for k in current_keys)

    return (has_modifier and has_alphanumeric) or has_special


class ShortcutsListener:
    def __init__(self):
        self.monitored_hotkeys = {}
        self.waiting_for_setting = False
        self.current_keys = set()
        self.key_combination_active = None
        self.finish_setting_mode_callback = None
        self.keyboard_listener = None
        self.hotkeys_listener = None

    def set_setting_mode(self, callback):
        self.stop()
        self.waiting_for_setting = True
        self.finish_setting_mode_callback = callback
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.keyboard_listener.start()

    def register_hotkeys(self, combo, callback):
        """_summary_

        Args:
            combo (_type_): Key combination like "<ctrl>+<alt>+K"
            callback (function): Function to call when the hotkey is pressed
        """

        def log_and_callback(callback):
            """Just a wrapper to log the hotkey pressed and call the callback."""
            mprint(f"Hotkey {combo} pressed")
            callback()

        # You can simply use `self.monitored_hotkeys[combo] = callback`
        # if you don't want to log the hotkey pressed.
        self.monitored_hotkeys[combo] = lambda: log_and_callback(callback)

    def clear_hotkeys(self):
        self.monitored_hotkeys.clear()

    def start(self):
        self.hotkeys_listener = keyboard.GlobalHotKeys(self.monitored_hotkeys)
        self.hotkeys_listener.start()

    def stop(self):
        if self.hotkeys_listener:
            self.hotkeys_listener.stop()

    def restart(self):
        self.stop()
        self.start()

    def _get_canonical_key(self, key):
        canonical_key = self.keyboard_listener.canonical(key)
        if hasattr(canonical_key, "vk"):
            canonical_key = special_key_values.get(canonical_key.vk, canonical_key)
        return canonical_key

    def on_press(self, key):
        self.current_keys.add(self._get_canonical_key(key))
        # Handle setting mode
        if self.waiting_for_setting:
            if is_combination_key(self.current_keys):
                self.finish_setting_mode_callback(frozenset(self.current_keys))
                self.waiting_for_setting = False
                self.current_keys.clear()
                self.keyboard_listener.stop()
                self.start()

    def on_release(self, key):
        canonical_key = self._get_canonical_key(key)
        if canonical_key in self.current_keys:
            self.current_keys.remove(canonical_key)
        # Reset active combination if it's released
        if self.key_combination_active and not self.key_combination_active.issubset(self.current_keys):
            self.key_combination_active = None


shortcuts_listener = ShortcutsListener()
