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
    assert Conversation.get_by_id(chat.cid).current_message == nodes["new-answer"].mid
