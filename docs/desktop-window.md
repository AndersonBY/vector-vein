# Window close behavior and system tray

The Windows desktop application keeps a notification-area icon while running.
Double-clicking it, or choosing **Open VectorVein** in its menu, restores the window.
Restoring preserves a maximized window. The tray menu's **Exit** closes the application
directly, regardless of the saved window-close policy.

Closing the window defaults to a native dialog with **Minimize to tray**, **Exit** and
**Cancel**. **Do not ask again** remembers the selected action after it succeeds.
Cancel never changes the preference. Minimizing hides the window without closing it:
Agent execution, workflow services and both schedulers remain running.

**Settings → Window & tray** provides three policies: ask every time, minimize to tray,
and exit. Changes save immediately. This section also provides an explicit minimize
button. The policy is stored as `window.close_action` in `config.json`, alongside the
existing window size, position and pin settings. It does not enter model settings or
the business-settings form. Normal shutdown flushes pending configuration writes.

`utilities/desktop_window.py` owns the native close handler and tray resources.
The Windows adapter uses the WinForms runtime already loaded by pywebview. It creates
the icon on `before_show`, cancels window closing when hiding or cancelling, and
disposes the icon during application shutdown. Tray startup or hide failure never
allows an invisible application without a restore entry. The current native tray
adapter targets Windows; other platforms retain a standard exit confirmation.

The existing settings bridge exposes:

- `get_window_setting`: close policy and current tray availability.
- `update_window_setting` with `close_action`: validates and saves `ask`, `tray` or `exit`.
- `minimize_to_tray`: hides the active desktop window, or returns 503 if unavailable.

`test_desktop_window.py` covers close-policy branches, remembering/resetting choices,
tray exit, unavailable native services, reentrant close requests, validation and bridge
responses. Its Windows subprocess constructs the real dialog controls, icon and menu
without displaying them.
