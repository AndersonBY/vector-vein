# Reply versions and conversation context

Provider history follows the requested message's exact parent chain. Alternate replies and questions are never substituted for the selected versions. Failed assistant replies remain visible in the UI but their partial text is omitted from provider history.

Conversation reads always return `selected_message_path`, including ordinary reopening without a search target. The UI uses that path to select the saved reply version in every message group. Search focus remains read-only and does not change the saved branch.

Version pagination calls `conversation__select_branch` with the conversation and message IDs. The API restores that version's latest descendant branch, saves its tail as `current_message`, and returns its history and selected path. Switching back restores the other version's existing descendants. This changes no message contents or timestamps. The UI waits for success before replacing history and clears the search target from the URL after an explicit version choice or successful generation request. Invalid IDs, active generations, failed saves, and stale responses do not replace the displayed branch. Searching for another version during generation defers loading that branch until the reply ends.

Sending uses the last displayed message's selected version as its parent. Regenerating an earlier reply hides its previous descendants while the new reply is generated; those descendants remain saved and are restored when switching back. Continuing a workflow reply also follows its selected branch.

Coverage is in `backend/tests/test_chat_branches.py`, `backend/tests/test_chat_search.py`, and `frontend/tests/chatFailures.test.js`.
