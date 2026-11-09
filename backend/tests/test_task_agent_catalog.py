import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from task_agent.store import BusinessStore


@pytest.fixture
def store(tmp_path):
    store = BusinessStore(tmp_path / 'tasks.db')
    store.save_project({'project_id': 'p', 'name': 'Project', 'roots': [str(tmp_path)]})
    start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    for index in range(135):
        store.create_task({
            'tid': f'task-{index:03}', 'thread_id': f'thread-{index}', 'title': f'Task {index}',
            'goal': 'Older needle %_ report' if index == 1 else 'Goal', 'status': 'COMPLETED' if index % 2 else 'FAILED',
            'current_turn_id': 'turn', 'model_provider': 'mock', 'model': 'mock', 'reasoning_effort': 'default',
            'config_snapshot': {'agent_profile': {'agent_id': 'one' if index % 2 else 'general', 'name': 'Specialist' if index % 2 else ''}},
            'created_at': (start + timedelta(minutes=index)).isoformat(),
            'updated_at': (start + timedelta(minutes=134 - index)).isoformat(), 'project_id': 'p' if index % 2 else None,
        })
    with store.connect() as connection:
        for index, cycle in enumerate([2, 7, None, 'not numeric']):
            connection.execute('INSERT INTO task_events VALUES(?,?,?,?,?)', ('task-001', str(index), index, 0, json.dumps({'cycle': cycle})))
    return store


def test_catalog_paginates_all_tasks_and_sorts_before_paging(store):
    page = store.query_tasks(10, offset=100, sort_by='created_at', sort_order='desc', summary=True)
    assert page['total'] == 135
    assert [task['tid'] for task in page['tasks']] == [f'task-{index:03}' for index in range(34, 24, -1)]
    ascending = store.query_tasks(10, sort_by='created_at', sort_order='asc', summary=True)
    assert ascending['tasks'][0]['tid'] == 'task-000'
    assert store.list_tasks(1)[0]['tid'] == 'task-000'
    assert 'current_cycle_index' not in store.list_tasks(1)[0]


def test_catalog_combines_project_agent_status_and_literal_search_before_counting(store):
    page = store.query_tasks(10, 'p', search='needle %_', statuses=['COMPLETED'], agent_id='one', summary=True)
    assert page['total'] == 1
    assert page['tasks'][0]['tid'] == 'task-001'
    assert page['tasks'][0]['current_cycle_index'] == 7
    assert page['agents'] == [{'agent_id': 'one', 'name': 'Specialist'}]
    assert store.query_tasks(project_id='p', statuses=['FAILED'], summary=True)['total'] == 0
    assert len(store.query_tasks(search='does not exist', summary=True)['agents']) == 2
    assert store.query_tasks(search="' OR 1=1 --", summary=True)['total'] == 0
    assert store.query_tasks(summary=True)['tasks'][0]['current_cycle_index'] == 0


@pytest.mark.parametrize('options', [{'sort_by': 'title; DROP TABLE tasks'}, {'sort_order': 'desc;--'}])
def test_sort_identifiers_are_allowlisted(store, options):
    with pytest.raises(ValueError):
        store.query_tasks(**options)
    assert store.query_tasks(summary=True)['total'] == 135


def test_api_validates_catalog_options_and_passes_supported_values(monkeypatch):
    from api import task_agent_api
    calls = []
    service = SimpleNamespace(list_tasks=lambda *args, **kwargs: calls.append((args, kwargs)) or {'tasks': [], 'total': 0})
    monkeypatch.setattr(task_agent_api, 'task_agent_service', lambda: service)
    api = task_agent_api.TaskAgentAPI()
    options = {'limit': 10, 'offset': 100, 'search': 'report', 'project_id': 'p', 'agent_id': 'one',
               'statuses': ['COMPLETED', 'FAILED'], 'sort_by': 'created_at', 'sort_order': 'asc', 'summary': True}
    assert api.list(options)['status'] == 200
    assert calls[-1] == ((10, 'p', 100, 'report'), {key: value for key, value in options.items()
                                                if key not in {'limit', 'offset', 'search', 'project_id'}})
    count = len(calls)
    for invalid in [{'statuses': 'COMPLETED'}, {'statuses': [None]}, {'statuses': ['unknown']}, {'agent_id': '../invalid'},
                    {'sort_by': 'injected'}, {'sort_order': None}, {'summary': 'true'}]:
        assert api.list(invalid)['status'] == 400
    assert len(calls) == count


def test_catalog_api_service_and_database_share_the_same_filter_scope(store, tmp_path, monkeypatch):
    from api import task_agent_api
    from task_agent.service import TaskAgentService
    service = TaskAgentService(tmp_path, process=SimpleNamespace(stop=lambda: None), data_path=tmp_path / 'state')
    service.store = store
    monkeypatch.setattr(service, '_start_watching', lambda: None)
    monkeypatch.setattr(task_agent_api, 'task_agent_service', lambda: service)
    try:
        response = task_agent_api.TaskAgentAPI().list({'project_id': 'p', 'agent_id': 'one', 'statuses': ['COMPLETED'],
            'limit': 20, 'offset': 60, 'sort_by': 'created_at', 'summary': True})
        assert response['status'] == 200
        assert response['data']['total'] == 67
        assert len(response['data']['tasks']) == 7
        assert response['data']['tasks'][-1]['tid'] == 'task-001'
        assert response['data']['tasks'][-1]['current_cycle_index'] == 7
    finally:
        service.stop()
