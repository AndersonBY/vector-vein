from copy import deepcopy
import json
import pytest


@pytest.fixture
def external_settings(monkeypatch, tmp_path):
    from peewee import SqliteDatabase
    from models import Setting
    from api import user_api
    external = {'VERSION': '2', 'endpoints': [{'id': 'external', 'api_base': 'https://endpoint.invalid/v1',
                'api_key': 'SYNTHETIC-EXTERNAL-KEY', 'credentials': {'token': 'SYNTHETIC-TOKEN'}}],
                'backends': {'local': {'models': {'reviewer': {'id': 'reviewer', 'enabled': True, 'endpoints': ['external']}}}}}
    saved_llm = {'VERSION': '2', 'endpoints': [], 'backends': {}}
    class Config(dict):
        def save(self, *args):
            pass
    path = tmp_path / 'external-settings.json'
    path.write_text(json.dumps(external), encoding='utf-8')
    monkeypatch.setenv('VECTORVEIN_LLM_SETTINGS_FILE', str(path))
    monkeypatch.setattr(user_api, 'config', Config())
    database = SqliteDatabase(':memory:')
    with database.bind_ctx([Setting]):
        database.create_tables([Setting])
        setting = Setting.create(data={'settings_version': 2, 'llm_settings': saved_llm})
        yield user_api, setting, path, external
    database.close()


def test_external_credentials_are_not_cached_or_copied_when_saving_settings(external_settings):
    from models import Setting
    user_api, setting, path, external = external_settings
    visible = user_api.SettingAPI().get({})['data']
    saved_llm = deepcopy(Setting.get_by_id(setting.id).data['llm_settings'])
    assert 'SYNTHETIC' not in json.dumps(visible)
    visible['data']['task_agent_approval'] = {'model_provider': 'local', 'model': 'reviewer'}
    response = user_api.SettingAPI().update({'id': setting.id, 'data': visible['data']})
    assert response['status'] == 200
    saved = Setting.get_by_id(setting.id).data
    assert saved['llm_settings'] == saved_llm
    assert saved['task_agent_approval']['model'] == 'reviewer'
    assert 'SYNTHETIC' not in json.dumps(saved) + json.dumps(response)
    assert external['endpoints'][0]['api_key'] == 'SYNTHETIC-EXTERNAL-KEY'
    assert json.loads(path.read_text(encoding='utf-8'))['endpoints'] == external['endpoints']


def test_reloaded_settings_use_saved_key_and_replacements_persist(external_settings, monkeypatch):
    from vv_llm.types import EndpointSetting
    from models import Setting
    user_api, setting, path, external = external_settings
    api = user_api.SettingAPI()
    keys = []
    monkeypatch.setattr(EndpointSetting, 'model_list', lambda endpoint: keys.append(endpoint.api_key) or {'data': [{'id': 'reviewer'}]})
    tested = []
    monkeypatch.setattr(user_api, 'run_model_endpoint_test', lambda payload: tested.append(payload) or {'content': 'ok'})
    for replacement in (None, 'SYNTHETIC-REPLACEMENT'):
        visible = api.get({})['data']
        endpoint = visible['data']['llm_settings']['endpoints'][0]
        assert endpoint['api_key'] == ''
        assert 'api_key' in endpoint['_saved_secret_fields']
        if replacement:
            endpoint['api_key'] = replacement
            endpoint['_saved_secret_fields'].remove('api_key')
        result = api.update({'id': setting.id, 'data': visible['data']})
        assert result['status'] == 200
        assert 'SYNTHETIC' not in json.dumps(result)
        reloaded = api.get({})['data']['data']['llm_settings']['endpoints'][0]
        assert api.list_models({'endpoint': reloaded})['status'] == 200
        assert api.test_model_endpoint({'endpoint': reloaded})['status'] == 200
        expected = replacement or external['endpoints'][0]['api_key']
        assert keys[-1] == tested[-1]['endpoint']['api_key'] == expected
        assert json.loads(path.read_text(encoding='utf-8'))['endpoints'][0]['api_key'] == expected
        assert 'SYNTHETIC' not in json.dumps(Setting.get_by_id(setting.id).data)


@pytest.mark.parametrize('change', [{'api_base': 'https://other.invalid/v1'}, {'proxy': 'http://other.invalid'},
                                  {'headers': {'X-Destination': 'changed'}}, {'endpoint_type': 'anthropic'}])
def test_saved_keys_are_not_reused_for_changed_destinations(external_settings, monkeypatch, change):
    from vv_llm.types import EndpointSetting
    user_api, setting, path, external = external_settings
    monkeypatch.setattr(EndpointSetting, 'model_list', lambda _: pytest.fail('network request'))
    monkeypatch.setattr(user_api, 'run_model_endpoint_test', lambda _: pytest.fail('network request'))
    api = user_api.SettingAPI()
    visible = api.get({})['data']['data']
    endpoint = visible['llm_settings']['endpoints'][0]
    endpoint.update(change)
    assert api.list_models({'endpoint': endpoint})['status'] == 400
    assert api.test_model_endpoint({'endpoint': endpoint})['status'] == 400
    assert api.update({'id': setting.id, 'data': visible})['status'] == 400
    assert json.loads(path.read_text(encoding='utf-8')) == external


def test_failed_external_write_is_reported_and_does_not_claim_saved(external_settings, monkeypatch):
    from models import Setting
    user_api, setting, path, external = external_settings
    api = user_api.SettingAPI()
    visible = api.get({})['data']['data']
    before = deepcopy(Setting.get_by_id(setting.id).data)
    visible['llm_settings']['endpoints'][0]['api_key'] = 'SYNTHETIC-NEW'
    def fail(*args):
        raise PermissionError('Cannot write configuration')
    monkeypatch.setattr(user_api.os, 'replace', fail)
    result = api.update({'id': setting.id, 'data': visible})
    assert result['status'] == 500
    assert 'SYNTHETIC' not in json.dumps(result)
    assert Setting.get_by_id(setting.id).data == before
    assert json.loads(path.read_text(encoding='utf-8')) == external
    assert list(path.parent.iterdir()) == [path]


def test_saved_key_errors_are_redacted_and_explicit_clear_persists(external_settings, monkeypatch):
    from vv_llm.types import EndpointSetting
    user_api, setting, path, external = external_settings
    api = user_api.SettingAPI()
    endpoint = api.get({})['data']['data']['llm_settings']['endpoints'][0]
    def fail(*args):
        raise RuntimeError('Provider echoed SYNTHETIC-EXTERNAL-KEY SYNTHETIC-TOKEN')
    monkeypatch.setattr(EndpointSetting, 'model_list', fail)
    monkeypatch.setattr(user_api, 'run_model_endpoint_test', fail)
    for result in (api.list_models({'endpoint': endpoint}), api.test_model_endpoint({'endpoint': endpoint})):
        assert result['status'] >= 400
        assert 'SYNTHETIC' not in json.dumps(result)
    visible = api.get({})['data']['data']
    endpoint = visible['llm_settings']['endpoints'][0]
    endpoint['_saved_secret_fields'].remove('api_key')
    assert api.update({'id': setting.id, 'data': visible})['status'] == 200
    assert json.loads(path.read_text(encoding='utf-8'))['endpoints'][0]['api_key'] == ''


def test_unreadable_saved_settings_errors_do_not_expose_file_contents(external_settings, monkeypatch):
    user_api, setting, path, external = external_settings
    api = user_api.SettingAPI()
    visible = api.get({})['data']['data']
    endpoint = visible['llm_settings']['endpoints'][0]
    def fail():
        raise ValueError('Invalid configuration: SYNTHETIC-EXTERNAL-KEY')
    monkeypatch.setattr(user_api, 'Settings', fail)
    for result in (api.list_models({'endpoint': endpoint}), api.test_model_endpoint({'endpoint': endpoint}),
                   api.update({'id': setting.id, 'data': visible})):
        assert result['status'] >= 400
        assert 'SYNTHETIC' not in json.dumps(result)


def test_standard_endpoint_save_survives_reloading(monkeypatch):
    from peewee import SqliteDatabase
    from api import user_api
    from models import Setting
    monkeypatch.delenv('VECTORVEIN_LLM_SETTINGS_FILE', raising=False)
    monkeypatch.setattr(user_api.config, 'save', lambda *args: None)
    database = SqliteDatabase(':memory:')
    with database.bind_ctx([Setting]):
        database.create_tables([Setting])
        Setting.create(data=deepcopy(user_api.DEFAULT_SETTINGS))
        api = user_api.SettingAPI()
        visible = api.get({})['data']
        endpoint = visible['data']['llm_settings']['endpoints'][0]
        endpoint['api_key'] = 'SYNTHETIC-LOCAL-KEY'
        assert api.update({'id': visible['id'], 'data': visible['data']})['status'] == 200
        reloaded = api.get({})['data']['data']['llm_settings']['endpoints'][0]
        assert reloaded['api_key'] == 'SYNTHETIC-LOCAL-KEY'
    database.close()


def test_embedding_and_search_edits_survive_external_settings_reload(external_settings):
    user_api, setting, path, external = external_settings
    api = user_api.SettingAPI()
    visible = api.get({})['data']['data']
    visible['llm_settings']['embedding_backends']['cohere']['models']['chosen'] = {
        'id': 'embed-v4.0', 'endpoints': ['external'], 'protocol': 'cohere_embed_v2', 'enabled': True}
    visible['web_search']['deepseek']['api_key'] = 'SEARCH-KEY'
    assert api.update({'id': setting.id, 'data': visible})['status'] == 200
    reloaded = api.get({})['data']['data']
    assert reloaded['llm_settings']['embedding_backends']['cohere']['models']['chosen']['id'] == 'embed-v4.0'
    assert reloaded['web_search']['deepseek']['api_key'] == 'SEARCH-KEY'
    assert json.loads(path.read_text(encoding='utf-8'))['embedding_backends']['cohere']['models']['chosen']['id'] == 'embed-v4.0'
    assert 'SEARCH-KEY' not in path.read_text(encoding='utf-8')


def test_rerank_selection_and_native_backend_survive_external_save(external_settings):
    from models import Setting
    from test_rerank_settings import configured
    user_api, setting, path, external = external_settings
    api = user_api.SettingAPI()
    visible = api.get({})['data']['data']
    before = deepcopy(Setting.get_by_id(setting.id).data['llm_settings'])
    backend = configured()['llm_settings']['rerank_backends']['custom']
    backend['default_endpoint'] = 'external'
    visible['llm_settings']['rerank_backends']['custom'] = backend
    visible['knowledge_retrieval'] = configured()['knowledge_retrieval']
    result = api.update({'id': setting.id, 'data': visible})
    assert result['status'] == 200
    reloaded = api.get({})['data']['data']
    assert reloaded['knowledge_retrieval'] == configured()['knowledge_retrieval']
    assert reloaded['llm_settings']['rerank_backends']['custom']['models']['chosen']['id'] == 'local-reranker'
    assert json.loads(path.read_text(encoding='utf-8'))['endpoints'][0]['api_key'] == 'SYNTHETIC-EXTERNAL-KEY'
    saved = Setting.get_by_id(setting.id).data
    assert saved['llm_settings'] == before
    assert 'SYNTHETIC' not in json.dumps(saved) + json.dumps(result)


def test_invalid_rerank_selection_does_not_save_external_file_or_database(external_settings):
    from models import Setting
    user_api, setting, path, external = external_settings
    api = user_api.SettingAPI()
    visible = api.get({})['data']['data']
    before = deepcopy(Setting.get_by_id(setting.id).data)
    original_file = path.read_text(encoding='utf-8')
    visible['knowledge_retrieval'] = {'rerank': {'provider': 'custom', 'model': 'missing'}}
    result = api.update({'id': setting.id, 'data': visible})
    assert result['status'] == 400
    assert 'SYNTHETIC' not in json.dumps(result)
    assert Setting.get_by_id(setting.id).data == before
    assert path.read_text(encoding='utf-8') == original_file


def test_rerank_standard_settings_save_and_reload(monkeypatch):
    from peewee import SqliteDatabase
    from api import user_api
    from models import Setting
    from test_rerank_settings import configured
    monkeypatch.delenv('VECTORVEIN_LLM_SETTINGS_FILE', raising=False)
    monkeypatch.setattr(user_api.config, 'save', lambda *args: None)
    database = SqliteDatabase(':memory:')
    with database.bind_ctx([Setting]):
        database.create_tables([Setting])
        setting = Setting.create(data=deepcopy(user_api.DEFAULT_SETTINGS))
        api = user_api.SettingAPI()
        visible = api.get({})['data']['data']
        draft = configured()
        visible['knowledge_retrieval'] = draft['knowledge_retrieval']
        visible['llm_settings']['endpoints'].extend(draft['llm_settings']['endpoints'])
        visible['llm_settings']['rerank_backends'] = draft['llm_settings']['rerank_backends']
        assert api.update({'id': setting.id, 'data': visible})['status'] == 200
        assert api.get({})['data']['data']['knowledge_retrieval'] == draft['knowledge_retrieval']
        assert api.get({})['data']['data']['llm_settings']['rerank_backends']['custom']['models']['chosen']['id'] == 'local-reranker'
    database.close()
