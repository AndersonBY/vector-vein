import uuid

import pytest
from peewee import SqliteDatabase

from api.agent_api import AgentAPI, ConversationAPI
from models import Agent, ChatDraft, Conversation, Message, User, Workflow, WorkflowTag, WorkflowTemplate


@pytest.fixture
def drafts(tmp_path):
    database = SqliteDatabase(tmp_path / "drafts.db", pragmas={"foreign_keys": 1})
    models = [User, WorkflowTag, Workflow, WorkflowTemplate, Agent, Conversation, Message, ChatDraft]
    models += [model.tags.get_through_model() for model in (Workflow, WorkflowTemplate)]
    models += [getattr(model, key).get_through_model()
               for model in (Agent, Conversation) for key in ("related_workflows", "related_templates")]
    with database.bind_ctx(models):
        database.create_tables(models)
        agents = [Agent.create(name=name, model="m", model_provider="OpenAI") for name in ("A", "B")]
        chats = [Conversation.create(agent=agents[0], title=name, model="m", model_provider="OpenAI")
                 for name in ("first", "second")]
        yield agents, chats, database
    database.close()


def test_drafts_are_durable_and_isolated_by_agent_and_conversation(drafts):
    agents, chats, db = drafts
    api = ConversationAPI()
    owners = [{"aid": agent.aid.hex} for agent in agents]
    owners += [{"aid": agents[0].aid.hex, "cid": chat.cid.hex} for chat in chats]
    for index, owner in enumerate(owners):
        assert api.draft({**owner, "text": f"draft {index}", "attachments": [f"C:/附件/{index}.txt"]})["status"] == 200
    db.close()
    db.connect()
    for index, owner in enumerate(owners):
        assert api.draft(owner)["data"] == {"text": f"draft {index}", "attachments": [f"C:/附件/{index}.txt"]}
    assert api.draft({**owners[0], "text": "", "attachments": []})["status"] == 200
    assert ChatDraft.select().count() == 3
    assert api.draft(owners[0])["data"] == {"text": "", "attachments": []}
    assert api.draft({**owners[1], "text": "", "attachments": ["file-only"]})["status"] == 200
    assert api.draft(owners[1])["data"]["attachments"] == ["file-only"]


@pytest.mark.parametrize("bad", [None, [], {}, {"aid": "invalid"}, {"aid": str(uuid.uuid4()), "cid": "bad"},
    {"text": 2, "attachments": []}, {"text": "x", "attachments": "file"},
    {"text": "x", "attachments": [None]}, {"text": "x"}])
def test_invalid_drafts_do_not_write(drafts, bad):
    agents, _, _ = drafts
    payload = {"aid": agents[0].aid.hex, **bad} if isinstance(bad, dict) and "aid" not in bad else bad
    if bad == {}:
        payload = {}
    assert ConversationAPI().draft(payload)["status"] == 400
    assert ChatDraft.select().count() == 0


def test_drafts_reject_missing_and_cross_agent_owners(drafts):
    agents, chats, _ = drafts
    api = ConversationAPI()
    for owner in [{"aid": uuid.uuid4().hex}, {"aid": agents[0].aid.hex, "cid": uuid.uuid4().hex},
                  {"aid": agents[1].aid.hex, "cid": chats[0].cid.hex}]:
        assert api.draft({**owner, "text": "private", "attachments": []})["status"] == 404
    assert ChatDraft.select().count() == 0


def test_deleting_owners_removes_only_their_drafts(drafts):
    agents, chats, _ = drafts
    api = ConversationAPI()
    owners = [{"aid": agents[0].aid.hex}, {"aid": agents[0].aid.hex, "cid": chats[0].cid.hex},
              {"aid": agents[1].aid.hex}]
    for owner in owners:
        api.draft({**owner, "text": "keep until deleted", "attachments": []})
    assert api.delete({"cid": chats[0].cid.hex})["status"] == 200
    assert ChatDraft.select().count() == 2
    assert AgentAPI().delete({"aid": agents[0].aid.hex})["status"] == 200
    assert ChatDraft.select().count() == 1
    assert api.draft(owners[2])["data"]["text"] == "keep until deleted"
