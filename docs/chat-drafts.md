# Chat drafts

Unsent text and attachment paths are stored in the local SQLite `ChatDraft` table.
Existing conversations have individual drafts. Each Agent also has an independent
new-chat draft. They survive navigation and application restarts, including changes
to the desktop HTTP port. Attachment files stay at their original paths.

`conversation__draft` reads a draft by Agent ID and optional conversation ID. Supplying
`text` and `attachments` saves it. The backend checks that the conversation belongs
to the Agent; an empty draft removes its row. Owner deletion removes the draft.
The table is registered with the existing startup `create_tables()` routine.

The chat store serializes writes for each owner. A late load cannot overwrite local
edits. Both composers use `useChatDraft` to restore the selected owner's input and
persist changes. File dialog, pasted-image and dropped-file callbacks cannot add
attachments to a different conversation after navigation.

Successful submission removes the submitted text only when it is still unchanged,
and removes the submitted attachments. Edits made while the request is pending stay
in their original draft, including when the user switches conversations. Failed
submissions keep their input. New chats persist the initial message in the target
conversation before navigation and scope the one-time send handoff to that target.
Opening another conversation cannot consume it. A failed initial send leaves an
ordinary draft for manual retry; reopening does not automatically resend it.

Creating a conversation Fork copies the current draft to the new conversation and
keeps the source conversation's draft.

Checks: `backend/tests/test_chat_drafts.py` covers persistence, owner validation and
deletion. `frontend/tests/chatFailures.test.js` covers write ordering, stale reads,
route reuse, send failures, concurrent edits, handoff isolation and Fork behavior.
