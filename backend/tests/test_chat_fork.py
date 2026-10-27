from datetime import datetime
import uuid

import pytest
from peewee import IntegrityError, SqliteDatabase

from api.agent_api import ConversationAPI, MessageAPI
from models import Agent, Conversation, Message, User, Workflow, WorkflowTag, WorkflowTemplate


@pytest.fixture
def history(tmp_path):
    database = SqliteDatabase(tmp_path / "fork.db", pragmas={"foreign_keys": 1})
    models = [User, WorkflowTag, Workflow, WorkflowTemplate, Agent, Conversation, Message]
    models += [model.tags.get_through_model() for model in (Workflow, WorkflowTemplate)]
    models += [getattr(model, key).get_through_model()
               for model in (Agent, Conversation) for key in ("related_workflows", "related_templates")]
    with database.bind_ctx(models):
        database.create_tables(models)
        agent = Agent.create(name="agent", model_provider="OpenAI", model="agent-default", version=4,
                             settings={"system_prompt": "agent default"})
        source = Conversation.create(agent=agent, agent_version=1, title="source", model_provider="Moonshot",
                                     model="reasoner", settings={"reasoning_effort": "high", "system_prompt": "custom"},
                                     shared=True, is_public=True, shared_meta={"old": "link"})
        source.related_workflows.add(Workflow.create(title="linked workflow"))
        source.related_templates.add(WorkflowTemplate.create(title="linked template"))
        yield source, database
    database.close()


def add_message(chat, text, parent=None, **kwargs):
    return Message.create(conversation=chat, parent=parent, author_type="A" if parent else "U",
                          content_type="TXT", status="S", content={"text": text}, **kwargs)


def fork(chat, reply, **kwargs):
    return ConversationAPI().fork({"source_cid": chat.cid.hex, "source_mid": reply.mid.hex, **kwargs})


def test_fork_copies_only_selected_ancestry_and_preserves_snapshot_without_touching_source(history):
    source, _ = history
    root = add_message(source, "question", attachments=["C:/local/picture.png"])
    add_message(source, "old version", root, metadata={"model": "old"})
    selected = add_message(source, "selected version", root,
                           metadata={"record_id": "completed-run", "recordStatus": "FINISHED"})
    # Parent order must be determined by the graph, not timestamps.
    followup = add_message(source, "followup", selected, create_time=datetime(2000, 1, 1))
    source.current_message = followup.mid
    source.save()
    original = Conversation.get_by_id(source.cid).__data__.copy()
    result = fork(source, selected, title="  alternate  ")
    assert result["status"] == 200
    target = Conversation.get_by_id(result["data"]["cid"])
    assert target.cid != source.cid
    assert target.title == "alternate"
    assert target.agent_id == source.agent_id
    assert target.agent_version == source.agent.version
    assert (target.model, target.model_provider, target.settings) == (source.model, source.model_provider, source.settings)
    assert list(target.related_workflows) == list(source.related_workflows)
    assert list(target.related_templates) == list(source.related_templates)
    assert not target.shared and not target.is_public and target.shared_meta == {} and target.shared_at_message is None
    copies = {item.content["text"]: item for item in Message.select().where(Message.conversation == target)}
    originals = [root, selected]
    assert len(copies) == len(originals)
    assert {item.mid for item in originals}.isdisjoint(item.mid for item in copies.values())
    assert copies["question"].parent_id is None
    assert copies["selected version"].parent_id == copies["question"].mid
    assert target.current_message == copies["selected version"].mid
    assert "old version" not in copies and "followup" not in copies
    for item in originals:
        clone = copies[item.content["text"]]
        assert (clone.content, clone.metadata, clone.attachments, clone.status, clone.create_time, clone.update_time) == (
            item.content, item.metadata, item.attachments, item.status, item.create_time, item.update_time)
    assert Conversation.get_by_id(source.cid).__data__ == original
    loaded = ConversationAPI().get({"cid": target.cid.hex})
    assert loaded["status"] == 200
    assert loaded["data"]["conversation"]["settings"] == source.settings
    assert [group[0]["content"]["text"] for group in loaded["data"]["messages"]] == ["question", "selected version"]
    # Editing and continuing the copy leaves the original tree and config unchanged.
    ConversationAPI().update({"cid": target.cid.hex, "model": "alternate", "settings": {"reasoning_effort": "low"}})
    sent = MessageAPI().send({"cid": target.cid.hex, "parent_mid": copies["selected version"].mid.hex,
                              "content": "new path", "content_type": "TXT"})
    assert sent["status"] == 200
    assert Message.get_by_id(sent["data"]["user_message_mid"]).parent_id == copies["selected version"].mid
    assert Message.select().where(Message.conversation == source).count() == 4
    assert Conversation.get_by_id(source.cid).__data__ == original
    assert Conversation.get_by_id(target.cid).settings == {"reasoning_effort": "low"}


def test_failed_replies_can_fork_and_keep_their_partial_content(history):
    source, _ = history
    root = add_message(source, "question")
    failed = Message.create(conversation=source, parent=root, author_type="A", content_type="TXT", status="F",
                            content={"text": "partial"}, metadata={"error": {"code": "CHAT_TIMEOUT"}})
    source.current_message = failed.mid
    source.save()
    result = fork(source, failed)
    copy = Conversation.get_by_id(result["data"]["cid"])
    assert Message.get_by_id(copy.current_message).status == "F"
    assert Message.get_by_id(copy.current_message).metadata == failed.metadata
    assert copy.title == "source · Fork"


@pytest.mark.parametrize("status", ["P", "G", "R"])
def test_fork_rejects_running_messages_without_creating_partial_copies(history, status):
    source, _ = history
    selected = Message.create(conversation=source, author_type="A", content_type="TXT", status=status)
    result = fork(source, selected)
    assert result["status"] == 409 and result["code"] == "CONVERSATION_BUSY"
    assert Conversation.select().count() == 1


@pytest.mark.parametrize("invalid_graph", ["foreign_parent", "cycle"])
def test_fork_rejects_invalid_graph_before_creating_copy(history, invalid_graph):
    source, _ = history
    root = add_message(source, "root")
    selected = add_message(source, "answer", root)
    if invalid_graph == "foreign_parent":
        other = Conversation.create(agent=source.agent, title="other", model="m", model_provider="p")
        root.parent = add_message(other, "foreign")
        root.save()
    elif invalid_graph == "cycle":
        root.parent = root
        root.save()
    count = Conversation.select().count()
    assert fork(source, selected)["status"] == 409
    assert Conversation.select().count() == count


def test_failed_copy_rolls_back_messages_conversation_and_relations(history, monkeypatch):
    source, _ = history
    root = add_message(source, "root")
    selected = add_message(source, "answer", root)
    create = Message.create
    calls = 0

    def failing_create(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise IntegrityError("local failure")
        return create(**kwargs)

    monkeypatch.setattr(Message, "create", failing_create)
    with pytest.raises(IntegrityError):
        fork(source, selected)
    assert Conversation.select().count() == 1
    assert Message.select().count() == 2
    for key in ("related_workflows", "related_templates"):
        assert getattr(Conversation, key).get_through_model().select().count() == 1


@pytest.mark.parametrize("payload", [None, [], {}, {"source_cid": "bad"}, {"source_mid": "bad"}, {"source_mid": None},
    {"title": []}, {"title": ""}, {"title": " "}, {"title": "x" * 513}])
def test_invalid_fork_inputs(history, payload):
    source, _ = history
    selected = Message.create(conversation=source, author_type="A", content_type="TXT", status="S")
    if isinstance(payload, dict) and "title" in payload:
        payload = {"source_cid": source.cid.hex, "source_mid": selected.mid.hex, **payload}
    assert ConversationAPI().fork(payload)["status"] == 400
    assert Conversation.select().count() == 1


def test_missing_source_and_missing_agent_are_not_copied(history):
    source, _ = history
    selected = Message.create(conversation=source, author_type="A", content_type="TXT", status="S")
    assert ConversationAPI().fork({"source_cid": uuid.uuid4().hex, "source_mid": selected.mid.hex})["status"] == 404
    source.agent = None
    source.save()
    assert fork(source, selected)["status"] == 404
    assert Conversation.select().count() == 1


def test_model_picker_settings_update_validates_before_writing(history):
    source, _ = history
    assert ConversationAPI().update({"cid": source.cid.hex, "model": "changed", "settings": []})["status"] == 400
    saved = Conversation.get_by_id(source.cid)
    assert saved.model == source.model and saved.settings == source.settings


def test_fork_from_old_reply_excludes_siblings_and_later_running_descendants(history):
    source, _ = history
    root = add_message(source, "question")
    older = add_message(source, "old answer", root)
    add_message(source, "new answer", root)
    later = add_message(source, "later question", older)
    later.author_type = "U"
    later.save()
    running = Message.create(conversation=source, parent=later, author_type="A", content_type="TXT", status="G")
    source.current_message = running.mid
    source.save()
    response = fork(source, older)
    assert response["status"] == 200
    target = Conversation.get_by_id(response["data"]["cid"])
    assert [item.content["text"] for item in target.messages.order_by(Message.create_time)] == ["question", "old answer"]
    assert Message.get_by_id(target.current_message).content["text"] == "old answer"
    assert Message.get_by_id(running.mid).status == "G"
    assert Conversation.get_by_id(source.cid).current_message == running.mid


def test_message_must_be_assistant_reply_in_source_conversation(history):
    source, _ = history
    user = add_message(source, "question")
    assert fork(source, user)["status"] == 400
    other = Conversation.create(agent=source.agent, title="other", model="m", model_provider="p")
    foreign = Message.create(conversation=other, author_type="A", content_type="TXT", status="S")
    assert fork(source, foreign)["status"] == 404
    assert ConversationAPI().fork({"source_cid": source.cid.hex, "source_mid": uuid.uuid4().hex})["status"] == 404
    assert Conversation.select().count() == 2
