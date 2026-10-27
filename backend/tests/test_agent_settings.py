import pytest
from peewee import IntegrityError, SqliteDatabase

from api.agent_api import AgentAPI, ConversationAPI
from models import Agent, Conversation, User, Workflow, WorkflowTag, WorkflowTemplate


@pytest.fixture
def saved_agent(tmp_path):
    database = SqliteDatabase(tmp_path / "agents.db")
    models = [User, WorkflowTag, Workflow, WorkflowTemplate, Agent, Conversation]
    models += [model.tags.get_through_model() for model in (Workflow, WorkflowTemplate)]
    models += [getattr(model, key).get_through_model()
               for model in (Agent, Conversation) for key in ("related_workflows", "related_templates")]
    with database.bind_ctx(models):
        database.create_tables(models)
        agent = Agent.create(name="original", model="old-model", model_provider="openai",
                             settings={"temperature": 0.3})
        workflow = Workflow.create(title="workflow")
        template = WorkflowTemplate.create(title="template")
        agent.related_workflows.add(workflow)
        agent.related_templates.add(template)
        yield agent, workflow, template
    database.close()


def update(agent, **payload):
    return AgentAPI().update({"aid": agent.aid.hex, **payload})


def test_metadata_update_preserves_relations(saved_agent):
    agent, workflow, template = saved_agent
    response = update(agent, name="renamed")
    assert response["status"] == 200
    assert response["data"]["is_owner"] is True
    assert [item["wid"] for item in response["data"]["related_workflows"]] == [workflow.wid.hex]
    assert [item["tid"] for item in response["data"]["related_templates"]] == [template.tid.hex]
    saved = Agent.get_by_id(agent.aid)
    assert saved.name == "renamed"
    assert saved.version == agent.version + 1
    assert list(saved.related_workflows) == [workflow]
    assert list(saved.related_templates) == [template]


@pytest.mark.parametrize("key,model,id_key", [
    ("related_workflows", Workflow, "wid"), ("related_templates", WorkflowTemplate, "tid"),
])
def test_explicit_relation_replaces_and_empty_list_clears(saved_agent, key, model, id_key):
    agent, workflow, template = saved_agent
    replacement = model.create(title="replacement")
    assert update(agent, **{key: [getattr(replacement, id_key).hex]})["status"] == 200
    saved = Agent.get_by_id(agent.aid)
    assert list(getattr(saved, key)) == [replacement]
    other = "related_templates" if key == "related_workflows" else "related_workflows"
    assert list(getattr(saved, other)) == [template if other == "related_templates" else workflow]
    assert update(agent, **{key: []})["status"] == 200
    assert list(getattr(Agent.get_by_id(agent.aid), key)) == []


@pytest.mark.parametrize("invalid", [None, "invalid", {}, [None], ["invalid"]])
def test_invalid_relation_leaves_all_saved_data_unchanged(saved_agent, invalid):
    agent, workflow, template = saved_agent
    assert update(agent, name="changed", related_workflows=[], related_templates=invalid)["status"] == 400
    saved = Agent.get_by_id(agent.aid)
    assert saved.name == agent.name
    assert saved.version == agent.version
    assert list(saved.related_workflows) == [workflow]
    assert list(saved.related_templates) == [template]


def test_failed_field_save_rolls_back_relation_changes(saved_agent):
    agent, workflow, template = saved_agent
    with pytest.raises(IntegrityError):
        update(agent, name=None, related_workflows=[], related_templates=[])
    saved = Agent.get_by_id(agent.aid)
    assert saved.name == agent.name
    assert saved.version == agent.version
    assert list(saved.related_workflows) == [workflow]
    assert list(saved.related_templates) == [template]


def test_new_conversation_inherits_saved_configuration_and_allows_overrides(saved_agent):
    agent, workflow, template = saved_agent
    settings = {"temperature": 0.8, "system_prompt": "Saved prompt"}
    assert update(agent, model="new-model", model_provider="custom", settings=settings,
                  related_workflows=[workflow.wid.hex], related_templates=[template.tid.hex])["status"] == 200
    saved = Agent.get_by_id(agent.aid)
    response = ConversationAPI().create({"conversation": {"aid": agent.aid.hex}})
    chat = Conversation.get_by_id(response["data"]["cid"])
    assert (chat.model, chat.model_provider, chat.settings, chat.agent_version) == (
        "new-model", "custom", settings, saved.version)
    assert list(chat.related_workflows) == [workflow]
    assert list(chat.related_templates) == [template]
    response = ConversationAPI().create({"conversation": {
        "aid": agent.aid.hex, "model": "override", "model_provider": "other", "settings": {},
    }})
    chat = Conversation.get_by_id(response["data"]["cid"])
    assert (chat.model, chat.model_provider, chat.settings) == ("override", "other", {})
