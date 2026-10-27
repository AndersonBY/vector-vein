# Chat history search

The chat sidebar searches the current Agent's local conversation titles and user/assistant message text, including conversations not loaded in the sidebar and older regenerated replies. Reasoning, attachment paths and workflow metadata are excluded.

Queries use literal substring matching. `%` and `_` are ordinary characters. SQLite's built-in case folding covers ASCII; other characters match literally. Results include plain-text context and load in pages of 20.

`conversation__search` accepts `aid`, `query`, `limit` (1–100) and `offset`. It returns `results`, `total`, `limit` and `offset`. Each result includes `cid`, `conversation_title`, `match_type`, `message_mid` and `snippet`.

Message results open the conversation with a `mid` query parameter. `conversation__get({cid, mid})` validates that the message belongs to the conversation and returns `focused_message_mid` and `selected_message_path`. The UI selects the matching reply versions and scrolls only the chat body. For an alternate branch, the response includes context through its newest descendant leaf. Reading search results does not change the conversation's saved current message.

Changing or clearing the keyword removes the previous focus marker. Pending responses are ignored after keyword, Agent or conversation changes. Search failures retain already loaded result pages and allow retry.

Backend coverage is in `backend/tests/test_chat_search.py`; frontend coverage is in `frontend/tests/chatSearch.test.js` and `frontend/tests/chatFailures.test.js`.
