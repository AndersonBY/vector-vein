import json
from copy import deepcopy

import pytest
from vv_agent.approval import ApprovalRequest
from vv_agent.types import LLMResponse

from task_agent.risk_review import LLMApprovalProvider, review_with_model
from task_agent.store import BusinessStore, now

SETTINGS = {'task_agent_approval': {'model_provider': 'local', 'model': 'reviewer'},
            'llm_settings': {'VERSION': '2', 'endpoints': [{'id': 'e', 'api_key': 'SYNTHETIC-REVIEW-KEY', 'api_base': 'http://localhost:1/v1'}],
                             'backends': {'local': {'models': {'reviewer': {'id': 'review-wire', 'enabled': True, 'endpoints': ['e']}}}}}}
SAFE = {'decision': 'allow', 'risk': 'low', 'reason': 'within_scope'}


def store_for(tmp_path):
    store = BusinessStore(tmp_path / 'tasks.db')
    store.create_task({'tid': 'task', 'thread_id': 'task', 'title': 'Create report', 'goal': 'Create outputs/report.txt', 'status': 'PROCESSING',
                      'current_turn_id': 'task/turn/one', 'model_provider': 'local', 'model': 'primary', 'reasoning_effort': 'default',
                      'config_snapshot': {}, 'created_at': now(), 'updated_at': now()})
    return store


def request(request_id='approval-one', **arguments):
    return ApprovalRequest(request_id=request_id, tool_name='write_file', tool_call_id='call', run_id='task/turn/one', arguments=arguments or {'path': 'outputs/report.txt', 'content': 'Report'})


def test_review_is_independent_retained_and_bound_to_exact_arguments(tmp_path):
    store = store_for(tmp_path)
    calls = []
    def evaluate(settings, selection, evidence):
        calls.append(json.loads(evidence))
        assert selection['model'] == 'reviewer'
        return SAFE
    provider = LLMApprovalProvider(store, 'task', settings_loader=lambda: SETTINGS, evaluate=evaluate)
    assert provider.decide(request()).action == 'allow'
    restored = LLMApprovalProvider(store, 'task', settings_loader=lambda: {}, evaluate=lambda *args: pytest.fail('Replayed review made another model call'))
    assert restored.decide(request()).action == 'allow'
    assert restored.decide(request(path='../different.txt')) is None
    assert len(calls) == 1 and calls[0]['user_goal'] == 'Create outputs/report.txt'
    audit = store.risk_reviews('task')[0]
    assert audit['status'] == 'approved' and audit['model'] == 'reviewer'
    assert 'Report' not in json.dumps(audit) and 'SYNTHETIC-REVIEW-KEY' not in json.dumps(audit)


@pytest.mark.parametrize('verdict', [
    {'decision': 'ask', 'risk': 'high', 'reason': 'destructive'},
    {'decision': 'allow', 'risk': 'high', 'reason': 'within_scope'},
    {'decision': 'allow', 'risk': 'low', 'reason': 'credentials'},
])
def test_uncertain_or_risky_verdict_never_auto_approves(tmp_path, verdict):
    store = store_for(tmp_path)
    provider = LLMApprovalProvider(store, 'task', settings_loader=lambda: SETTINGS, evaluate=lambda *a: verdict)
    assert provider.decide(request()) is None
    assert store.risk_reviews('task')[0]['status'] == 'manual'


@pytest.mark.parametrize('kind,expected', [('missing', 'not_configured'), ('timeout', 'review_failed'), ('secret', 'credentials'), ('large', 'too_large')])
def test_failure_and_sensitive_evidence_fall_back_without_persisting_input(tmp_path, kind, expected):
    store = store_for(tmp_path)
    calls = []
    def evaluate(*args):
        calls.append(1)
        raise TimeoutError('SYNTHETIC-REVIEW-KEY raw provider response')
    provider = LLMApprovalProvider(store, 'task', settings_loader=lambda: {} if kind == 'missing' else SETTINGS, evaluate=evaluate)
    content = 'SYNTHETIC-REVIEW-KEY' if kind == 'secret' else 'x' * 50000 if kind == 'large' else 'text'
    assert provider.decide(request(content=content)) is None
    rows = store.risk_reviews('task')
    assert rows[0]['reason'] == expected
    assert len(calls) == (1 if kind == 'timeout' else 0)
    assert 'SYNTHETIC-REVIEW-KEY' not in json.dumps(rows) and 'provider response' not in json.dumps(rows)


def test_interrupted_review_becomes_manual_and_late_result_cannot_override(tmp_path):
    store = store_for(tmp_path)
    def evaluate(*args):
        restarted = LLMApprovalProvider(store, 'task', settings_loader=lambda: SETTINGS)
        assert restarted.decide(request()) is None
        return SAFE
    provider = LLMApprovalProvider(store, 'task', settings_loader=lambda: SETTINGS, evaluate=evaluate)
    assert provider.decide(request()) is None
    assert store.risk_reviews('task')[0]['reason'] == 'interrupted'


def test_reviewer_setting_change_applies_to_next_request(tmp_path):
    store = store_for(tmp_path)
    settings = deepcopy(SETTINGS)
    models = []
    provider = LLMApprovalProvider(store, 'task', settings_loader=lambda: settings,
                                   evaluate=lambda data, selection, evidence: (models.append(selection['model']) or SAFE))
    provider.decide(request())
    settings['task_agent_approval']['model'] = 'other-reviewer'
    provider.decide(request('approval-two'))
    assert models == ['reviewer', 'other-reviewer']


@pytest.mark.parametrize('content', ['not json', '```json\n{}\n```', '{"decision":"allow"}', json.dumps({**SAFE, 'instructions': 'ignore safety'}), json.dumps({**SAFE, 'reason': ['within_scope']})])
def test_invalid_model_response_is_rejected(monkeypatch, content):
    class Client:
        def complete(self, call):
            assert call.model == 'review-wire' and not call.tools
            assert call.model_settings.retry.max_attempts == 1
            assert call.messages[0].role == 'system'
            return LLMResponse(content)
    monkeypatch.setattr('task_agent.risk_review.DesktopModelProvider.client', lambda *a: Client())
    with pytest.raises(ValueError):
        review_with_model(SETTINGS, SETTINGS['task_agent_approval'], '{"tool":"bash"}')


def test_v4_store_upgrade_preserves_history(tmp_path):
    store = store_for(tmp_path)
    with store.connect() as connection:
        connection.execute('DROP INDEX tasks_project_order')
        connection.execute('ALTER TABLE tasks DROP COLUMN project_id')
        connection.execute('DROP TABLE task_projects')
        connection.execute('DROP TABLE task_risk_reviews')
        connection.execute('ALTER TABLE tasks DROP COLUMN hidden')
        for table in ('task_schedules', 'task_schedule_runs', 'task_completion_effects'):
            connection.execute(f'DROP TABLE {table}')
        connection.execute('PRAGMA user_version=4')
    restored = BusinessStore(store.path)
    assert restored.get_task('task')['goal'] == 'Create outputs/report.txt'
    assert restored.get_task('task')['hidden'] == 0
    assert restored.risk_reviews('task') == []


@pytest.mark.parametrize('content', ['{"password": "synthetic-private-password"}', 'API_KEY=synthetic-private-key', '-----BEGIN RSA PRIVATE KEY-----'])
def test_credential_markers_are_not_sent_to_reviewer(tmp_path, content):
    store = store_for(tmp_path)
    provider = LLMApprovalProvider(store, 'task', settings_loader=lambda: SETTINGS, evaluate=lambda *args: pytest.fail('Credential evidence must not be transmitted'))
    assert provider.decide(request(content=content)) is None
    assert store.risk_reviews('task')[0]['reason'] == 'credentials'
