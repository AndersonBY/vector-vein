"""Persist terminal chat results before notifying a connected client."""
from datetime import datetime

from models import Message
from utilities.workflow_errors import redact_message


PENDING = (Message.StatusTypes.PENDING, Message.StatusTypes.GENERATING)
CLIENT_FAILURES = {
    "CHAT_CONNECTION_FAILED": "Could not connect to the chat server.",
    "CHAT_CONNECTION_CLOSED": "The chat connection closed before the response completed.",
    "CHAT_TIMEOUT": "The chat response timed out while waiting for data.",
}


def failure_response(code, content=None, error=None, model=None):
    message = CLIENT_FAILURES.get(code, "The chat request failed.")
    if error is not None and code == "CHAT_REQUEST_FAILED":
        body = getattr(error, "body", None)
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            body = body["error"]
        provider_message = body.get("message") if isinstance(body, dict) else None
        detail = provider_message.strip() if isinstance(provider_message, str) else ""
        message = redact_message(detail or error) or message
    return {"status": "F", "content_type": "TXT", "content": content or {},
            "metadata": {"error": {"code": code, "message": message}}, "model": model}


def stopped_response(content=None, model=None):
    content = content or {}
    return {"status": "C", "content_type": "TXT", "metadata": {}, "model": model,
            "content": {name: content.get(name, "") for name in ("text", "reasoning_content")}}


def persist_response(message, response):
    """A stale completion or disconnect notice cannot overwrite a terminal result."""
    current = Message.get_by_id(message.mid)
    allowed = PENDING
    error = (current.metadata or {}).get("error")
    # A deliberate stop can arrive just after its socket-close notice.
    if (response.get("status") == "C" and current.status == "F" and
            isinstance(error, dict) and error.get("code") == "CHAT_CONNECTION_CLOSED"):
        allowed = ("F",)
    if current.status not in allowed:
        return current
    content = dict(current.content or {})
    for name in ("text", "reasoning_content"):
        incoming = response.get("content", {}).get(name, "")
        if isinstance(incoming, str) and len(incoming) >= len(content.get(name, "")):
            content[name] = incoming
    metadata = {**(current.metadata or {}), **response.get("metadata", {})}
    status = response.get("status") or ("W" if response["content_type"] == "WKF" else "S")
    if status in ("F", "C"):
        metadata.pop("selected_workflow", None)
        metadata.pop("tool_calls", None)
        metadata.pop("tools", None)
    if status == "C":
        metadata.pop("error", None)
    if response.get("model"):
        metadata["model"] = response["model"]
    updated = Message.update(status=status, content_type="TXT" if status in ("F", "C") else response["content_type"],
        content=content, metadata=metadata, update_time=datetime.now()).where(
            (Message.mid == current.mid) & Message.status.in_(allowed)).execute()
    current = Message.get_by_id(current.mid)
    title = response.get("conversation_title")
    if updated and title:
        conversation = current.conversation
        conversation.title = title
        conversation.update_time = datetime.now()
        conversation.save()
    return current


def terminal_frame(message):
    metadata = message.metadata or {}
    frame = {"end": True, "mid": message.mid.hex, "status": message.status, "role": "assistant",
        "content": message.content.get("text", ""), "reasoning_content": message.content.get("reasoning_content", ""),
        "model": metadata.get("model"), "selected_workflow": metadata.get("selected_workflow", {}),
        "title": message.conversation.title}
    if message.status in ("F", "C"):
        frame["selected_workflow"] = {}
    if message.status == "F":
        frame["error"] = metadata.get("error", {"code": "CHAT_REQUEST_FAILED", "message": "The chat request failed."})
    return frame
