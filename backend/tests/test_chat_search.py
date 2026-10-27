from datetime import datetime, timedelta

import pytest
from peewee import SqliteDatabase

from api.agent_api import ConversationAPI
from models import Agent, Conversation, Message, User


@pytest.fixture
def history(tmp_path):
    database = SqliteDatabase(tmp_path / "search.db")
    with database.bind_ctx([User, Agent, Conversation, Message]):
        database.create_tables([User, Agent, Conversation, Message])
        agent = Agent.create(name="search", model_provider="openai", model="test")
        yield agent, database
    database.close()


def conversation(agent, title="chat", **kwargs):
    return Conversation.create(agent=agent, title=title, model_provider="openai", model="test", **kwargs)


def message(chat, text, **kwargs):
    return Message.create(conversation=chat, author_type="U", content_type="TXT", content={"text": text}, **kwargs)


def search(agent, query, **kwargs):
    return ConversationAPI().search({"aid": agent.aid.hex, "query": query, **kwargs})


def test_search_all_history_with_stable_pagination_and_agent_scope(history):
    agent, _ = history
    old = conversation(agent, "needle old", update_time=datetime(2020, 1, 1))
    hit = message(old, "older NEEDLE answer")
    for index in range(30):
        conversation(agent, f"recent {index}", update_time=datetime(2020, 1, 2) + timedelta(days=index))
    other = Agent.create(name="other", model_provider="openai", model="test")
    message(conversation(other, "needle foreign"), "needle foreign")
    first = search(agent, " needle ", limit=1)["data"]
    second = search(agent, "needle", limit=1, offset=1)["data"]
    assert first["total"] == second["total"] == 2
    assert first["results"][0]["match_type"] == "title"
    assert first["results"][0]["message_mid"] is None
    assert second["results"][0]["message_mid"] == hit.mid.hex
    assert second["results"][0]["cid"] == old.cid.hex
    assert search(agent, "needle", offset=2)["data"]["results"] == []
    assert search(agent, "needle", limit=1)["data"] == first


def test_literal_query_and_visible_text_only(history):
    agent, database = history
    chat = conversation(agent)
    hit = message(chat, "literal %_ ' OR 1=1 -- <script>example</script>")
    message(chat, "ordinary text")
    Message.create(conversation=chat, author_type="S", content_type="TXT", content={"text": "hidden"})
    Message.create(conversation=chat, author_type="A", content_type="TXT",
                   content={"reasoning_content": "hidden", "text": "visible"},
                   metadata={"text": "hidden"}, attachments=[{"name": "hidden"}])
    Message.create(conversation=chat, author_type="A", content_type="TXT", content={"text": {"hidden": True}})
    corrupt = message(chat, "placeholder")
    database.execute_sql("UPDATE message SET content = ? WHERE mid = ?", ("invalid JSON hidden", corrupt.mid.hex))
    for query in ("%_", "' OR 1=1 --", "<script>"):
        result = search(agent, query)["data"]
        assert result["total"] == 1
        assert result["results"][0]["message_mid"] == hit.mid.hex
        assert isinstance(result["results"][0]["snippet"], str)
    assert search(agent, "hidden")["data"]["total"] == 0
    assert search(agent, "visible")["data"]["total"] == 1


def test_bounded_snippets_and_empty_query(history):
    agent, _ = history
    chat = conversation(agent)
    message(chat, "a " * 300 + "needle" + " z" * 300)
    result = search(agent, "needle")["data"]["results"][0]
    assert "needle" in result["snippet"]
    assert len(result["snippet"]) <= 222
    assert "\n" not in result["snippet"]
    assert search(agent, "  \n\t")["data"]["total"] == 0


@pytest.mark.parametrize("kwargs", [
    {"aid": "invalid"}, {"query": None}, {"query": []}, {"query": "x" * 1001},
    {"limit": 0}, {"limit": 101}, {"limit": "20"}, {"limit": True},
    {"offset": -1}, {"offset": 1.5}, {"offset": 2147483648},
])
def test_invalid_search_input(history, kwargs):
    agent, _ = history
    payload = {"aid": agent.aid.hex, "query": "test", **kwargs}
    assert ConversationAPI().search(payload)["status"] == 400
    assert ConversationAPI().search(None)["status"] == 400


def test_get_focus_selects_branch_context_without_changing_current_message(history, monkeypatch):
    from api import agent_api

    agent, _ = history
    chat = conversation(agent)
    root = message(chat, "root")
    current = message(chat, "current", parent=root)
    alternate = message(chat, "alternate", parent=root)
    descendant = message(chat, "alternate followup", parent=alternate)
    chat.current_message = current.mid
    chat.save()
    # Conversation relation serialization is unrelated to the history branch under test.
    original = agent_api.model_serializer
    monkeypatch.setattr(agent_api, "model_serializer", lambda obj, **kwargs:
                        {"cid": obj.cid.hex} if isinstance(obj, Conversation) else
                        {"aid": obj.aid.hex} if isinstance(obj, Agent) else original(obj, **kwargs))
    api = ConversationAPI()
    focused = api.get({"cid": chat.cid.hex, "mid": alternate.mid.hex})["data"]
    assert focused["selected_message_path"] == [root.mid.hex, alternate.mid.hex, descendant.mid.hex]
    assert focused["focused_message_mid"] == alternate.mid.hex
    assert descendant.mid.hex in {item["mid"] for group in focused["messages"] for item in group}
    assert Conversation.get_by_id(chat.cid).current_message == current.mid
    current_focus = api.get({"cid": chat.cid.hex, "mid": root.mid.hex})["data"]
    assert current_focus["selected_message_path"] == [root.mid.hex, current.mid.hex]
    assert "selected_message_path" not in api.get({"cid": chat.cid.hex})["data"]
    foreign = message(conversation(agent), "foreign")
    assert api.get({"cid": chat.cid.hex, "mid": foreign.mid.hex})["status"] == 404
    assert api.get({"cid": chat.cid.hex, "mid": "invalid"})["status"] == 400
