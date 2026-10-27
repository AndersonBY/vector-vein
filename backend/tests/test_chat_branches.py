from datetime import datetime, timedelta
import uuid

import pytest
from peewee import SqliteDatabase

from api.agent_api import ConversationAPI, MessageAPI
from api.utils import get_history_messages
from models import Agent, Conversation, Message, User, Workflow, WorkflowTag, WorkflowTemplate


@pytest.fixture
def branches(tmp_path):
    database = SqliteDatabase(tmp_path / "branches.db")
    models = [User, WorkflowTag, Workflow, WorkflowTemplate, Agent, Conversation, Message]
    models += [model.tags.get_through_model() for model in (Workflow, WorkflowTemplate)]
    models += [getattr(model, key).get_through_model()
               for model in (Agent, Conversation) for key in ("related_workflows", "related_templates")]
    with database.bind_ctx(models):
        database.create_tables(models)
        agent = Agent.create(name="branch", model="test", model_provider="OpenAI")
        chat = Conversation.create(agent=agent, agent_version=agent.version, title="branches", model="test", model_provider="OpenAI")
        nodes = {}
        for index, (key, author, parent) in enumerate([
            ("root", "U", None), ("old", "A", "root"), ("old-question", "U", "old"),
            ("old-answer", "A", "old-question"), ("new", "A", "root"),
            ("new-question", "U", "new"), ("new-answer", "A", "new-question"),
        ]):
            nodes[key] = Message.create(conversation=chat, author_type=author, parent=nodes.get(parent),
                                        content_type="TXT", status="S", content={"text": key},
                                        create_time=datetime(2026, 1, 1) + timedelta(seconds=index))
        chat.current_message = nodes["new-answer"].mid
        chat.save()
        yield chat, nodes
    database.close()


def text_path(items):
    return [item["content"]["text"] for item in items]


def test_provider_context_follows_exact_ancestor_chain_instead_of_latest_siblings(branches):
    _, nodes = branches
    assert text_path(get_history_messages(nodes["old-answer"], count=None, all_children=False)) == [
        "root", "old", "old-question", "old-answer"]
    assert text_path(get_history_messages(nodes["old-answer"], count=2, all_children=False)) == ["old-question", "old-answer"]
    groups = get_history_messages(nodes["old-answer"], count=None)
    assert {item["mid"] for item in groups[1]} == {nodes["old"].mid.hex, nodes["new"].mid.hex}


@pytest.mark.parametrize("action", ["send", "regenerate", "append_answer"])
def test_generation_uses_requested_branch_even_when_newer_branch_exists(branches, action):
    chat, nodes = branches
    if action == "send":
        response = MessageAPI().send({"cid": chat.cid.hex, "parent_mid": nodes["old"].mid.hex,
                                      "content": "continue old", "content_type": "TXT"})
        expected = ["root", "old", "continue old"]
    else:
        response = getattr(MessageAPI(), action)({"cid": chat.cid.hex, "mid": nodes["old-answer"].mid.hex})
        expected = ["root", "old", "old-question"] + (["old-answer"] if action == "append_answer" else [])
    assert response["status"] == 200
    assert text_path(response["data"]["history_messages"]) == expected
    assert Conversation.get_by_id(chat.cid).current_message.hex == response["data"]["ai_message_mid"]


def test_selecting_versions_restores_each_branch_tail_and_survives_reopening(branches):
    chat, nodes = branches
    api = ConversationAPI()
    default = api.get({"cid": chat.cid.hex})["data"]
    new_path = [nodes[key].mid.hex for key in ("root", "new", "new-question", "new-answer")]
    old_path = [nodes[key].mid.hex for key in ("root", "old", "old-question", "old-answer")]
    assert default["selected_message_path"] == new_path
    selected = api.select_branch({"cid": chat.cid.hex, "mid": nodes["old"].mid.hex})
    assert selected["status"] == 200
    assert selected["data"]["selected_message_path"] == old_path
    assert "focused_message_mid" not in selected["data"]
    saved = Conversation.get_by_id(chat.cid)
    assert saved.current_message == nodes["old-answer"].mid
    assert saved.update_time == chat.update_time
    reopened = api.get({"cid": chat.cid.hex})["data"]
    assert reopened["selected_message_path"] == old_path
    assert text_path([group[0] for group in reopened["messages"][2:]]) == ["old-question", "old-answer"]
    assert api.select_branch({"cid": chat.cid.hex, "mid": nodes["new"].mid.hex})["data"]["selected_message_path"] == new_path
    assert Message.select().where(Message.conversation == chat).count() == 7


def test_selected_failed_reply_never_substitutes_a_successful_sibling(branches):
    chat, nodes = branches
    failed = Message.create(conversation=chat, parent=nodes["root"], author_type="A", status="F",
                            content_type="TXT", content={"text": "partial failure"})
    assert text_path(get_history_messages(failed, count=None, all_children=False)) == ["root"]
    selected = ConversationAPI().select_branch({"cid": chat.cid.hex, "mid": failed.mid.hex})
    assert selected["status"] == 200
    assert selected["data"]["selected_message_path"] == [nodes["root"].mid.hex, failed.mid.hex]


@pytest.mark.parametrize("status", ["P", "G", "R"])
def test_version_switch_during_generation_does_not_replace_current_branch(branches, status):
    chat, nodes = branches
    Message.update(status=status).where(Message.mid == nodes["new-answer"].mid).execute()
    assert ConversationAPI().select_branch({"cid": chat.cid.hex, "mid": nodes["old"].mid.hex})["status"] == 409
    assert Conversation.get_by_id(chat.cid).current_message == nodes["new-answer"].mid


def test_invalid_or_foreign_selection_leaves_current_branch_unchanged(branches):
    chat, nodes = branches
    api = ConversationAPI()
    for payload in (None, [], {}, {"cid": chat.cid.hex, "mid": "invalid"}):
        assert api.select_branch(payload)["status"] == 400
    assert api.select_branch({"cid": uuid.uuid4().hex, "mid": nodes["old"].mid.hex})["status"] == 404
    other = Conversation.create(title="other", model="other", model_provider="OpenAI")
    foreign = Message.create(conversation=other, author_type="A", content_type="TXT", content={"text": "foreign"})
    assert api.select_branch({"cid": chat.cid.hex, "mid": foreign.mid.hex})["status"] == 404
    assert Conversation.get_by_id(chat.cid).current_message == nodes["new-answer"].mid


def test_cannot_switch_to_an_unfinished_alternate_tail(branches):
    chat, nodes = branches
    Message.update(status="G").where(Message.mid == nodes["old-answer"].mid).execute()
    assert ConversationAPI().select_branch({"cid": chat.cid.hex, "mid": nodes["old"].mid.hex})["status"] == 409


@pytest.mark.parametrize("key,index,context", [("root", 0, []), ("new-question", 2, ["root", "new"])])
def test_edit_creates_question_version_preserving_original_descendants_and_attachments(branches, key, index, context):
    chat, nodes = branches
    original = nodes[key]
    original.attachments = ["C:/资料/attachment.txt"]
    original.save()
    before = {item.mid: item.__data__.copy() for item in Message.select()}
    response = MessageAPI().edit({"cid": chat.cid.hex, "mid": original.mid.hex, "content": "  revised question  ",
                                  "attachments": ["must-not-replace-original.txt"]})
    assert response["status"] == 200
    data = response["data"]
    question = Message.get_by_id(data["user_message_mid"])
    answer = Message.get_by_id(data["ai_message_mid"])
    assert question.mid != original.mid and question.parent_id == original.parent_id
    assert question.content == {"text": "  revised question  "}
    assert question.attachments == original.attachments
    assert question.status == "S" and question.author_type == "U"
    assert answer.parent_id == question.mid and answer.status == "P"
    assert text_path(data["history_messages"]) == context + ["  revised question  "]
    assert data["need_title"] is False
    assert Message.select().count() == len(before) + 2
    assert MessageAPI().edit({"cid": chat.cid.hex, "mid": original.mid.hex, "content": "duplicate"})["status"] == 409
    assert Message.select().count() == len(before) + 2
    for mid, saved in before.items():
        assert Message.get_by_id(mid).__data__ == saved
    answer.status = "S"
    answer.content = {"text": "revised reply"}
    answer.save()
    new_path = [item["mid"] for item in data["history_messages"]] + [answer.mid.hex]
    api = ConversationAPI()
    loaded = api.get({"cid": chat.cid.hex})["data"]
    assert loaded["selected_message_path"] == new_path
    assert {item["mid"] for item in loaded["messages"][index]} == {original.mid.hex, question.mid.hex}
    old = api.select_branch({"cid": chat.cid.hex, "mid": original.mid.hex})["data"]
    assert old["selected_message_path"] == [nodes[key].mid.hex for key in ("root", "new", "new-question", "new-answer")]
    assert api.select_branch({"cid": chat.cid.hex, "mid": question.mid.hex})["data"]["selected_message_path"] == new_path
    assert api.get({"cid": chat.cid.hex})["data"]["selected_message_path"] == new_path
    # A later reply uses only the edited question and its own answer.
    sent = MessageAPI().send({"cid": chat.cid.hex, "parent_mid": answer.mid.hex, "content_type": "TXT", "content": "continue"})
    assert text_path(sent["data"]["history_messages"]) == context + ["  revised question  ", "revised reply", "continue"]


@pytest.mark.parametrize("payload", [None, [], {}, {"cid": "bad", "mid": "bad", "content": "x"},
    {"content": ""}, {"content": " \n "}, {"content": None}, {"content": {}}, {"content": 1}])
def test_invalid_edits_leave_messages_and_branch_unchanged(branches, payload):
    chat, nodes = branches
    if isinstance(payload, dict) and "cid" not in payload and payload:
        payload = {"cid": chat.cid.hex, "mid": nodes["root"].mid.hex, **payload}
    assert MessageAPI().edit(payload)["status"] == 400
    assert Message.select().count() == 7
    assert Conversation.get_by_id(chat.cid).current_message == nodes["new-answer"].mid


@pytest.mark.parametrize("status", ["P", "G", "R"])
def test_edits_reject_active_generation_and_duplicate_submissions(branches, status):
    chat, nodes = branches
    Message.update(status=status).where(Message.mid == chat.current_message).execute()
    result = MessageAPI().edit({"cid": chat.cid.hex, "mid": nodes["root"].mid.hex, "content": "edited"})
    assert result["status"] == 409 and result["code"] == "CONVERSATION_BUSY"
    assert Message.select().count() == 7


def test_edits_reject_foreign_missing_or_non_question_messages(branches):
    chat, nodes = branches
    api = MessageAPI()
    other = Conversation.create(title="other", model="m", model_provider="OpenAI")
    for payload in [{"cid": uuid.uuid4().hex, "mid": nodes["root"].mid.hex},
                    {"cid": other.cid.hex, "mid": nodes["root"].mid.hex},
                    {"cid": chat.cid.hex, "mid": uuid.uuid4().hex}]:
        assert api.edit({**payload, "content": "x"})["status"] == 404
    assert api.edit({"cid": chat.cid.hex, "mid": nodes["new"].mid.hex, "content": "x"})["status"] == 400
    original = nodes["root"]
    for changes in ({"content_type": "IMG"}, {"content_type": "TXT", "status": "F"}):
        Message.update(**changes).where(Message.mid == original.mid).execute()
        assert api.edit({"cid": chat.cid.hex, "mid": original.mid.hex, "content": "x"})["status"] == 400
    assert Message.select().count() == 7


def test_edit_cannot_branch_from_an_unfinished_ancestor(branches):
    chat, nodes = branches
    Message.update(status="G").where(Message.mid == nodes["old"].mid).execute()
    result = MessageAPI().edit({"cid": chat.cid.hex, "mid": nodes["old-question"].mid.hex, "content": "revised"})
    assert result["status"] == 409 and result["code"] == "CONVERSATION_BUSY"
    assert Message.select().count() == 7


@pytest.mark.parametrize("corruption", ["cycle", "foreign", "missing"])
def test_edit_rejects_invalid_ancestry_without_creating_a_partial_branch(branches, corruption):
    chat, nodes = branches
    source = nodes["new-question"]
    if corruption == "cycle":
        nodes["new"].parent = source
        nodes["new"].save()
    elif corruption == "foreign":
        other = Conversation.create(title="other", model="m", model_provider="OpenAI")
        nodes["new"].parent = Message.create(conversation=other, author_type="A", content_type="TXT", status="S")
        nodes["new"].save()
    else:
        nodes["root"].parent_id = uuid.uuid4()
        nodes["root"].save()
    count = Message.select().count()
    assert MessageAPI().edit({"cid": chat.cid.hex, "mid": source.mid.hex, "content": "x"})["status"] == 409
    assert Message.select().count() == count
    assert Conversation.get_by_id(chat.cid).current_message == nodes["new-answer"].mid


def test_edit_rolls_back_question_and_current_branch_if_reply_creation_fails(branches, monkeypatch):
    chat, nodes = branches
    create = Message.create
    def fail_reply(**kwargs):
        if kwargs.get("author_type") == "A":
            raise RuntimeError("storage unavailable")
        return create(**kwargs)
    monkeypatch.setattr(Message, "create", fail_reply)
    with pytest.raises(RuntimeError, match="storage unavailable"):
        MessageAPI().edit({"cid": chat.cid.hex, "mid": nodes["root"].mid.hex, "content": "x"})
    assert Message.select().count() == 7
    assert Conversation.get_by_id(chat.cid).current_message == nodes["new-answer"].mid
    assert Conversation.get_by_id(chat.cid).current_message == nodes["new-answer"].mid
