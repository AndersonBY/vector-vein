# Stopping chat generation

During generation, the composer shows a Stop generating button in place of Send. Clicking it sends a message-scoped stop control on the existing WebSocket. The server cancels generation, closes provider resources, saves received text and reasoning, and sends a terminal frame before the client closes its connection. Duplicate clicks send one control. The acknowledgement deadline is bounded even if more chunks arrive.

Stopped assistant replies use status `C` and plain text content. They show a small Stopped label, retain partial text and reasoning, and support continuation, regeneration, and forks. Empty stopped replies remain visible after reopening. Completed replies and completed tool handoffs are not overwritten by a late stop. A stop that races a socket-close failure retains the longer partial and records the explicit stop instead of a disconnect error. Stopped replies do not launch unfinished workflow calls.

If the socket has not been created or opened yet, or its stop acknowledgement fails, `message__stop` persists the stopped state. Pending socket setup is invalidated without waiting for the connection timeout. If persistence fails, the button allows another stop attempt while keeping the partial visible; sending stays blocked until the state is saved. Replies and saves from an earlier attempt cannot replace a later conversation. Draft text and attachments for the next message remain unchanged.

The existing one-character status column needs no schema migration. Workflow cancellation remains a separate operation.

Coverage: `backend/tests/test_chat_failures.py` includes real local WebSocket cancellation and replay tests. `frontend/tests/chatConnection.test.js` and `frontend/tests/chatFailures.test.js` cover stops before connecting, acknowledgements, partials, races, retries, stale responses, and rendering.
