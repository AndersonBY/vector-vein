import json
from types import SimpleNamespace

import httpx
import pytest

from utilities.config.settings import DEFAULT_SETTINGS, normalize_web_search
from utilities.web_search import search_pages
from utilities.workflow_errors import WorkflowInputError


def configuration(**changes):
    values = {'web_search.deepseek.api_key': 'SYNTHETIC-KEY',
              'web_search.deepseek.endpoint': 'https://api.deepseek.com/v1/tools/search', **changes}
    return SimpleNamespace(get=lambda key, default=None: values.get(key, default))


def test_deepseek_uses_documented_request_and_maps_snippets_without_fetching_pages():
    seen = []
    def send(request):
        seen.append(request)
        return httpx.Response(200, json={'results': [{'title': 'Title', 'url': 'https://example.org', 'snippet': 'Summary', 'content': ''}]})
    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        result = search_pages(client, configuration(), 'deepseek', '量子计算 site:example.org', 3)
    assert result == [{'title': 'Title', 'url': 'https://example.org', 'content': 'Summary'}]
    assert len(seen) == 1
    assert seen[0].method == 'POST'
    assert str(seen[0].url) == 'https://api.deepseek.com/v1/tools/search'
    assert seen[0].headers['Authorization'] == 'Bearer SYNTHETIC-KEY'
    assert json.loads(seen[0].content) == {'query': '量子计算 site:example.org', 'count': 3, 'need_content': False}
    assert max(seen[0].extensions['timeout'].values()) == 60


@pytest.mark.parametrize('query,count,changes', [(' ', 10, {}), ('a' * 129, 10, {}), ('query', 0, {}),
    ('query', 51, {}), ('query', True, {}), ('query', 1, {'web_search.deepseek.api_key': ''}),
    ('query', 1, {'web_search.deepseek.endpoint': 'file:///tmp/key'}),
    ('query', 1, {'web_search.deepseek.endpoint': 'https://user:secret@example.org'})])
def test_invalid_search_settings_never_send_a_request(query, count, changes):
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail('Unexpected request'))) as client:
        with pytest.raises(WorkflowInputError):
            search_pages(client, configuration(**changes), 'deepseek', query, count)


@pytest.mark.parametrize('status', [400, 401, 402, 429, 500])
def test_provider_errors_are_actionable_redacted_and_not_retried(status):
    seen = []
    def send(request):
        seen.append(request)
        return httpx.Response(status, json={'error': {'message': 'SYNTHETIC-KEY'}})
    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        with pytest.raises(RuntimeError) as caught:
            search_pages(client, configuration(), 'deepseek', 'query', 1)
    assert f'HTTP {status}' in str(caught.value)
    assert 'SYNTHETIC' not in str(caught.value)
    assert len(seen) == 1


def test_empty_search_is_success_and_malformed_search_is_an_error():
    for body in ({'results': []}, {'results': None}, {'results': [{'title': 'Missing URL'}]}, {}):
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))) as client:
            if body == {'results': []}:
                assert search_pages(client, configuration(), 'deepseek', 'query', 1) == []
            else:
                with pytest.raises(RuntimeError, match='结果格式'):
                    search_pages(client, configuration(), 'deepseek', 'query', 1)


def test_transport_errors_hide_credentials_and_fail_explicitly():
    def fail(request):
        raise httpx.ReadTimeout('SYNTHETIC-KEY', request=request)
    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(RuntimeError, match='连接失败或超时') as caught:
            search_pages(client, configuration(), 'deepseek', 'query', 1)
    assert 'SYNTHETIC' not in str(caught.value)


def test_jina_applies_configured_key_and_count_on_the_first_request():
    seen = []
    def send(request):
        seen.append(request)
        return httpx.Response(200, json={'code': 200, 'data': [{'title': str(i), 'url': 'https://example.org', 'content': 'page'} for i in range(3)]})
    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        result = search_pages(client, configuration(**{'web_search.jinaai.api_key': 'JINA-KEY'}), 'jina.ai', 'a/b ?query', 1)
    assert len(result) == 1
    assert seen[0].headers['Authorization'] == 'Bearer JINA-KEY'
    assert len(seen) == 1


def test_settings_remove_retired_search_and_keep_deepseek_credentials():
    data = {'web_search': {'bing': {'ocp_apim_subscription_key': 'OLD-KEY'}, 'jinaai': {'api_key': 'JINA-KEY'}}}
    normalize_web_search(data)
    assert 'bing' not in data['web_search']
    assert data['web_search']['deepseek']['endpoint'] == 'https://api.deepseek.com/v1/tools/search'
    data['web_search']['deepseek']['api_key'] = 'NEW-KEY'
    normalize_web_search(data)
    assert data['web_search']['deepseek']['api_key'] == 'NEW-KEY'
    assert data['web_search']['jinaai']['api_key'] == 'JINA-KEY'
    assert 'bing' not in DEFAULT_SETTINGS['web_search']


def node_workflow(**changes):
    values = {'search_text': 'query', 'search_engine': 'deepseek', 'count': 2, 'combine_result_in_text': True,
              'max_snippet_length': 3, 'output_type': 'markdown', **changes}
    return {'nodes': [{'id': 'search', 'type': 'TextSearch', 'category': 'tools', 'data': {'task_name': 'tools.text_search',
        'template': {key: {'value': value} for key, value in values.items()}}}], 'edges': []}


@pytest.mark.parametrize('batch,combined', [(False, True), (False, False), (True, True), (True, False)])
def test_workflow_preserves_output_shape_and_closes_clients(monkeypatch, batch, combined):
    from utilities.workflow import Workflow
    from worker.tasks import tools
    clients = []
    def create_client(**kwargs):
        client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'results': [
            {'title': 'Title', 'url': 'https://example.org', 'snippet': 'abcdef', 'content': ''}]})))
        clients.append(client)
        return client
    monkeypatch.setattr(tools, 'Settings', configuration)
    monkeypatch.setattr(tools, 'new_httpx_client', create_client)
    monkeypatch.setattr(Workflow, 'report_node_status', lambda *args: True)
    monkeypatch.setattr(Workflow, 'report_workflow_status', lambda *args: True)
    result = tools.text_search(node_workflow(search_text=['one', 'two'] if batch else 'one', combine_result_in_text=combined), 'search')
    assert not result.get('failures')
    value = 'abc' if combined else ['abc']
    assert Workflow(result).get_node_field_value('search', 'output_page_snippet') == ([value, value] if batch else value)
    assert all(client.is_closed for client in clients)


@pytest.mark.parametrize('task_name', ['text_search', 'image_search'])
def test_retired_engines_fail_before_network_requests(monkeypatch, task_name):
    from utilities.workflow import Workflow
    from worker.tasks import tools
    monkeypatch.setattr(tools, 'new_httpx_client', lambda **kwargs: pytest.fail('Unexpected request'))
    monkeypatch.setattr(Workflow, 'report_node_status', lambda *args: True)
    monkeypatch.setattr(Workflow, 'report_workflow_status', lambda *args: True)
    data = node_workflow(search_engine='bing')
    with pytest.raises(WorkflowInputError, match='重新选择'):
        getattr(tools, task_name)(data, 'search')
    assert data['failures'][0]['code'] == 'INVALID_ARGUMENT'


def test_pexels_image_search_preserves_attribution_and_closes_client(monkeypatch):
    from utilities.workflow import Workflow
    from worker.tasks import tools
    seen = []
    def send(request):
        seen.append(request)
        return httpx.Response(200, json={'photos': [{'photographer': 'Photographer', 'url': 'https://pexels.com/photo/1',
                                                   'src': {'original': 'https://images.pexels.com/one.jpg'}}]})
    client = httpx.Client(transport=httpx.MockTransport(send))
    monkeypatch.setattr(tools, 'Settings', lambda: configuration(pexels_api_key='PEXELS-KEY'))
    monkeypatch.setattr(tools, 'new_httpx_client', lambda **kwargs: client)
    monkeypatch.setattr(Workflow, 'report_node_status', lambda *args: True)
    monkeypatch.setattr(Workflow, 'report_workflow_status', lambda *args: True)
    data = node_workflow(search_engine='pexels')
    result = tools.image_search(data, 'search')
    output = Workflow(result).get_node_field_value('search', 'output')
    assert output == ['![Photographer](https://images.pexels.com/one.jpg)\nPexels Photographer: [https://pexels.com/photo/1](https://pexels.com/photo/1)']
    assert seen[0].headers['Authorization'] == 'PEXELS-KEY'
    assert seen[0].url.params['per_page'] == '2'
    assert client.is_closed
