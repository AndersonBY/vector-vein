# Desktop UI and settings

Workspace list pages use a compact title, short description and action toolbar.
Non-actionable hero statistics are omitted. Agent cards show their chat action
without requiring hover. Brand colors and the existing component library remain
shared across pages.

Settings has one persistent Save settings action. Endpoint editing uses the same
save operation: the open editor is validated and included in the submitted
settings snapshot. The endpoint list and model catalog are published only after
success. Failed saves leave the editor and entered values intact. Canceling a
switch does not discard its editor. A duplicate endpoint name or invalid
credentials prevents submission.

Unsaved state includes open endpoint drafts and credentials. Switching settings
categories preserves drafts without warning toasts. Leaving the settings route
requires confirmation when changes remain. Edits made elsewhere during a save
remain unsaved; the response cannot mark newer edits as persisted. Shortcut
changes are registered whenever the saved shortcut configuration changes.

Workflow errors show their actionable explanation first. Node identifiers,
exception classes and error codes remain available under Technical details.
The optional debug timeline retains copyable node IDs. Loading completed
workflow output does not mask it behind the run button's second spinner.

Coverage: `frontend/tests/settingsSave.test.js` uses the real Settings and
EndpointSettings components for validation, failed save/retry, snapshot
isolation, switch cancellation, credentials, navigation and shortcut updates.
`frontend/tests/fileSelection.test.js` verifies native file-selection messages,
cancel behavior and failures in both languages.
