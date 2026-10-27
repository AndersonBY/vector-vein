import pytest
from vv_llm.types import NOT_GIVEN
from utilities.model_selection import parse_reasoning_effort, validate_model_preferences


@pytest.mark.parametrize("value", [None, "", "default"])
def test_default_reasoning_is_omitted(value):
    assert parse_reasoning_effort(value) is NOT_GIVEN


@pytest.mark.parametrize("value", ["none", "minimal", "low", "medium", "high", "xhigh", "max"])
def test_explicit_reasoning_is_retained(value):
    assert parse_reasoning_effort(value) == value


@pytest.mark.parametrize("value", [True, 1, [], {}, "unknown"])
def test_invalid_reasoning_is_rejected(value):
    with pytest.raises(ValueError):
        parse_reasoning_effort(value)


def test_presets_validate_enabled_models_and_local_family_membership():
    data = {"llm_settings": {"backends": {"openai": {"models": {"good": {}, "off": {"enabled": False}}}}},
            "custom_llms": {"Family": ["legacy"]}, "model_preferences": {"default": {}}}
    validate_model_preferences(data)
    data["model_preferences"]["high_performance"] = {"model_provider": "OpenAI", "model": "good"}
    data["model_preferences"]["low_cost"] = {"model_provider": "_local__Family", "model": "legacy"}
    validate_model_preferences(data)
    for provider, model in [("OpenAI", "off"), ("OpenAI", "missing"), ("_local__Other", "legacy"), ("", "good")]:
        data["model_preferences"]["default"] = {"model_provider": provider, "model": model}
        with pytest.raises(ValueError):
            validate_model_preferences(data)


@pytest.mark.parametrize("presets", [None, [], {"unknown": {}}, {"default": []}, {"default": {"model_provider": 1}}])
def test_malformed_presets_are_rejected(presets):
    with pytest.raises(ValueError):
        validate_model_preferences({"model_preferences": presets})


def test_settings_api_keeps_saved_presets_when_new_selection_is_invalid(monkeypatch):
    from peewee import SqliteDatabase
    from models import Setting
    from api import user_api
    database = SqliteDatabase(":memory:")
    monkeypatch.setattr(user_api, "update_llm_settings_to_v2", lambda data: data)
    monkeypatch.setattr(user_api, "normalize_embedding_backends", lambda data: None)
    monkeypatch.setattr(user_api, "config", type("Config", (), {"save": lambda *args: None})())
    with database.bind_ctx([Setting]):
        database.create_tables([Setting])
        setting = Setting.create(data={"model_preferences": {}})
        payload = {"id": setting.id, "data": {"llm_settings": {"backends": {"openai": {"models": {"good": {}}}}},
            "model_preferences": {"default": {"model_provider": "OpenAI", "model": "good"}}}}
        assert user_api.SettingAPI().update(payload)["status"] == 200
        payload["data"]["model_preferences"]["default"]["model"] = "missing"
        assert user_api.SettingAPI().update(payload)["status"] == 400
        assert Setting.get_by_id(setting.id).data["model_preferences"]["default"]["model"] == "good"
    database.close()
