from datetime import datetime, timedelta
import uuid

import pytest
from peewee import SqliteDatabase

from api.agent_api import ConversationAPI, MessageAPI
from models import Agent, ChatDraft, Conversation, Message, User, Workflow, WorkflowTag, WorkflowTemplate


@pytest.fixture
def tree(tmp_path):
    database = SqliteDatabase(tmp_path / "deletion.db", pragmas={"foreign_keys": 1})
    models = [User, WorkflowTag, Workflow, WorkflowTemplate, Agent, Conversation, Message, ChatDraft]
    models += [model.tags.get_through_model() for model in (Workflow, WorkflowTemplate)]
    models += [getattr(model, key).get_through_model()
               for model in (Agent, Conversation) for key in ("related_workflows", "related_templates")]
    with database.bind_ctx(models):
        database.create_tables(models)
        agent = Agent.create(name="deletion", model="test", model_provider="OpenAI")
        chat = Conversation.create(agent=agent, title="branches", model="test", model_provider="OpenAI")
        nodes = {}
        for index, (key, author, parent) in enumerate([
            ("root", "U", None), ("old", "A", "root"), ("old-question", "U", "old"),
            ("old-answer", "A", "old-question"), ("new", "A", "root"),
            ("new-question", "U", "new"), ("new-answer", "A", "new-question"),
        ]):
            nodes[key] = Message.create(conversation=chat, author_type=author, parent=nodes.get(parent),
                content_type="TXT", status="S", content={"text": key},
                create_time=datetime(2026, 1, 1) + timedelta(seconds=index))
        attachment = tmp_path / "资料.txt"
        attachment.write_text("Keep the attachment file.", encoding="utf-8")
        nodes["root"].attachments = [str(attachment)]
        nodes["root"].save()
        chat.current_message = nodes["new-answer"].mid
        chat.shared_at_message = nodes["new-question"].mid
        chat.save()
        ChatDraft.create(scope=f"{agent.aid.hex}:{chat.cid.hex}", agent=agent, conversation=chat,
                         text="unsent draft", attachments=[str(attachment)])
        yield chat, nodes, attachment
    database.close()


def delete(chat, node):
    return MessageAPI().delete({"cid": chat.cid.hex, "mid": node.mid.hex})


def snapshot():
    return {item.mid: item.__data__.copy() for item in Message.select()}


def path(nodes, *keys):
    return [nodes[key].mid.hex for key in keys]


def test_deleting_selected_reply_removes_its_whole_subtree_and_restores_other_version(tree):
    chat, nodes, attachment = tree
    before = snapshot()
    response = delete(chat, nodes["new"])
    assert response["status"] == 200
    removed = {nodes[key].mid for key in ("new", "new-question", "new-answer")}
    assert snapshot() == {mid: data for mid, data in before.items() if mid not in removed}
    expected = path(nodes, "root", "old", "old-question", "old-answer")
    assert response["data"]["selected_message_path"] == expected
    assert ConversationAPI().get({"cid": chat.cid.hex})["data"]["selected_message_path"] == expected
    saved = Conversation.get_by_id(chat.cid)
    assert saved.current_message == nodes["old-answer"].mid
    assert saved.shared_at_message is None
    assert (saved.title, saved.settings, saved.model, saved.update_time) == (chat.title, chat.settings, chat.model, chat.update_time)
    assert ChatDraft.get().text == "unsent draft" and attachment.exists()
    sent = MessageAPI().send({"cid": chat.cid.hex, "parent_mid": saved.current_message.hex,
                              "content_type": "TXT", "content": "continue"})
    assert [item["content"]["text"] for item in sent["data"]["history_messages"]] == [
        "root", "old", "old-question", "old-answer", "continue"]


def test_deleting_an_unselected_branch_preserves_current_path_and_does_not_reparent_messages(tree):
    chat, nodes, _ = tree
    before = snapshot()
    response = delete(chat, nodes["old"])
    removed = {nodes[key].mid for key in ("old", "old-question", "old-answer")}
    assert snapshot() == {mid: data for mid, data in before.items() if mid not in removed}
    assert response["data"]["selected_message_path"] == path(nodes, "root", "new", "new-question", "new-answer")
    assert Conversation.get_by_id(chat.cid).shared_at_message == chat.shared_at_message


@pytest.mark.parametrize("key,remaining_path", [
    ("new-question", ("root", "new")), ("new-answer", ("root", "new", "new-question")),
])
def test_deleting_without_an_alternate_version_returns_to_parent_context(tree, key, remaining_path):
    chat, nodes, _ = tree
    response = delete(chat, nodes[key])
    assert response["status"] == 200
    assert response["data"]["selected_message_path"] == path(nodes, *remaining_path)
    assert Message.get_by_id(nodes["old-answer"].mid).parent_id == nodes["old-question"].mid


def test_deleting_the_only_root_leaves_an_empty_chat_without_removing_files_or_draft(tree):
    chat, nodes, attachment = tree
    response = delete(chat, nodes["root"])
    assert response["status"] == 200
    assert response["data"]["messages"] == [] and response["data"]["selected_message_path"] == []
    assert Message.select().count() == 0
    assert Conversation.get_by_id(chat.cid).current_message is None
    assert ChatDraft.get().text == "unsent draft" and attachment.exists()
    sent = MessageAPI().send({"cid": chat.cid.hex, "content": "fresh question", "content_type": "TXT"})
    assert [item["content"]["text"] for item in sent["data"]["history_messages"]] == ["fresh question"]


def test_deleting_an_edited_root_restores_another_root_and_its_descendants(tree):
    chat, nodes, _ = tree
    edited = Message.create(conversation=chat, author_type="U", content_type="TXT", status="S", content={"text": "edited root"})
    reply = Message.create(conversation=chat, parent=edited, author_type="A", content_type="TXT", status="S", content={"text": "edited reply"})
    before = snapshot()
    response = delete(chat, nodes["root"])
    assert response["data"]["selected_message_path"] == [edited.mid.hex, reply.mid.hex]
    assert snapshot() == {mid: data for mid, data in before.items() if mid in (edited.mid, reply.mid)}


def test_fallback_skips_running_sibling_contexts_and_never_moves_their_messages(tree):
    chat, nodes, _ = tree
    Message.update(status="R").where(Message.mid == nodes["old"].mid).execute()
    before = snapshot()
    response = delete(chat, nodes["new"])
    assert response["status"] == 200
    assert response["data"]["selected_message_path"] == path(nodes, "root")
    for key in ("root", "old", "old-question", "old-answer"):
        assert Message.get_by_id(nodes[key].mid).__data__ == before[nodes[key].mid]


def test_fallback_uses_same_author_versions_and_their_latest_existing_tail(tree):
    chat, nodes, _ = tree
    edited = Message.create(conversation=chat, parent=nodes["new"], author_type="U", content_type="TXT", status="S",
                            content={"text": "edited question"})
    reply = Message.create(conversation=chat, parent=edited, author_type="A", content_type="TXT", status="S",
                           content={"text": "edited reply"})
    Message.create(conversation=chat, parent=edited, author_type="A", content_type="TXT", status="S",
                   content={"text": "older reply"}, create_time=datetime(2000, 1, 1))
    continuation = Message.create(conversation=chat, parent=nodes["new"], author_type="A", content_type="TXT", status="S",
                                  content={"text": "assistant continuation"})
    response = delete(chat, nodes["new-question"])
    assert response["data"]["selected_message_path"] == path(nodes, "root", "new") + [edited.mid.hex, reply.mid.hex]
    assert Message.get_by_id(continuation.mid).parent_id == nodes["new"].mid


def test_deep_subtree_is_removed_children_first_without_recursive_reparenting(tree):
    chat, nodes, _ = tree
    with Message._meta.database.atomic():
        parent = nodes["new-answer"]
        for index in range(150):
            parent = Message.create(conversation=chat, parent=parent, author_type="U" if index % 2 == 0 else "A",
                                    content_type="TXT", status="S", content={"text": f"nested {index}"})
        Conversation.update(current_message=parent.mid).where(Conversation.cid == chat.cid).execute()
    response = delete(chat, nodes["new"])
    assert response["status"] == 200
    assert Message.select().count() == 4
    assert response["data"]["selected_message_path"] == path(nodes, "root", "old", "old-question", "old-answer")


@pytest.mark.parametrize("key", ["new-answer", "old-answer"])
@pytest.mark.parametrize("status", ["P", "G", "R"])
def test_cannot_delete_running_current_context_or_running_target_descendants(tree, key, status):
    chat, nodes, _ = tree
    Message.update(status=status).where(Message.mid == nodes[key].mid).execute()
    before = snapshot()
    response = delete(chat, nodes["old"])
    assert response["status"] == 409 and response["code"] == "CONVERSATION_BUSY"
    assert snapshot() == before
    assert Conversation.get_by_id(chat.cid).current_message == chat.current_message


@pytest.mark.parametrize("payload", [None, [], {}, {"mid": "bad", "cid": "bad"},
    {"cid": uuid.uuid4().hex}, {"mid": uuid.uuid4().hex}])
def test_malformed_deletions_do_not_change_history(tree, payload):
    chat, _, _ = tree
    before = snapshot()
    assert MessageAPI().delete(payload)["status"] == 400
    assert snapshot() == before
    assert Conversation.get_by_id(chat.cid).current_message == chat.current_message


def test_missing_or_cross_conversation_messages_are_not_deleted(tree):
    chat, nodes, _ = tree
    other = Conversation.create(agent=chat.agent, title="other", model="m", model_provider="OpenAI")
    before = snapshot()
    for payload in [{"cid": other.cid.hex, "mid": nodes["new"].mid.hex},
                    {"cid": chat.cid.hex, "mid": uuid.uuid4().hex},
                    {"cid": uuid.uuid4().hex, "mid": nodes["new"].mid.hex}]:
        assert MessageAPI().delete(payload)["status"] == 404
        assert snapshot() == before


@pytest.mark.parametrize("corruption", ["cycle", "foreign-parent", "foreign-child", "missing-parent", "missing-tip"])
def test_corrupt_graphs_are_rejected_without_touching_either_conversation(tree, corruption):
    chat, nodes, _ = tree
    database = Message._meta.database
    other = Conversation.create(agent=chat.agent, title="other", model="m", model_provider="OpenAI")
    foreign = Message.create(conversation=other, author_type="U", content_type="TXT", status="S")
    if corruption == "cycle":
        Message.update(parent=nodes["new-answer"]).where(Message.mid == nodes["new"].mid).execute()
    elif corruption == "foreign-parent":
        Message.update(parent=foreign).where(Message.mid == nodes["new"].mid).execute()
    elif corruption == "foreign-child":
        Message.update(parent=nodes["new-question"]).where(Message.mid == foreign.mid).execute()
    elif corruption == "missing-parent":
        database.pragma("foreign_keys", 0)
        Message.update(parent=uuid.uuid4()).where(Message.mid == nodes["new"].mid).execute()
        database.pragma("foreign_keys", 1)
    else:
        Conversation.update(current_message=uuid.uuid4()).where(Conversation.cid == chat.cid).execute()
    before = snapshot()
    current = Conversation.get_by_id(chat.cid).current_message
    assert delete(chat, nodes["new"])["status"] == 409
    assert snapshot() == before
    assert Conversation.get_by_id(chat.cid).current_message == current


def test_storage_failure_rolls_back_an_already_deleted_descendant(tree, monkeypatch):
    chat, nodes, _ = tree
    before = snapshot()
    delete_query = Message.delete
    calls = 0
    def fail_second_delete():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("storage unavailable")
        return delete_query()
    monkeypatch.setattr(Message, "delete", fail_second_delete)
    with pytest.raises(RuntimeError, match="storage unavailable"):
        delete(chat, nodes["new"])
    assert calls == 2 and snapshot() == before
    assert Conversation.get_by_id(chat.cid).current_message == chat.current_message


def test_cannot_return_an_updated_history_rolls_back_the_deletion(tree, monkeypatch):
    chat, nodes, _ = tree
    before = snapshot()
    monkeypatch.setattr(ConversationAPI, "get", lambda *args: {"status": 503})
    assert delete(chat, nodes["new"])["status"] == 503
    assert snapshot() == before
    assert Conversation.get_by_id(chat.cid).current_message == chat.current_message
