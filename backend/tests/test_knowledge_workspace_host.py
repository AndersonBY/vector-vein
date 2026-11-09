from types import SimpleNamespace
import json

import pytest
from vv_agent.tools.base import ToolContext
from vv_agent.workspace.local import LocalWorkspaceBackend

from knowledge_base import KnowledgeService
from task_agent import knowledge
from task_agent.host import DesktopTaskAgentHost
from task_agent.live_approval import LiveApprovalProvider
from test_task_agent_knowledge import snapshot, save_task, SETTINGS


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    class Embedder:
        def get(self, value):
            return [1., .2, .3] if isinstance(value, str) else [[1., .2, .3] for _ in value]
    import knowledge_base
    service = KnowledgeService(tmp_path / 'kb', embedder_factory=lambda _: Embedder(), reranker_factory=lambda: None, start_worker=False)
    base = service.create('Manual', 'test', 'test', embedding_dimensions=3)
    source = service.add_text(base['id'], 'guide.pdf', 'Project quota: 42 members.\nThis is extracted PDF text.')
    service.run_pending()
    frozen = snapshot((base['id'],))
    frozen['knowledge_bases'] = [{'kb_id': base['id'], 'name': 'Manual'}]
    frozen['agent_profile']['allow_file_writes'] = True
    root = tmp_path / 'tasks'
    store = save_task(root, frozen=frozen)
    monkeypatch.setattr(knowledge_base, 'knowledge_service', lambda: service)
    knowledge.start_knowledge_bridge('http://127.0.0.1:9876')
    monkeypatch.setattr(knowledge, '_bridge_request', lambda operation, payload: knowledge._dispatch(root, operation, payload))
    request = SimpleNamespace(thread_id='task', cwd=str(root / 'workspaces/task'), metadata={'model_snapshot': frozen})
    host = DesktopTaskAgentHost(root, settings_loader=lambda: SETTINGS)
    config = host.build_run_config(request)
    registry = config.tool_registry_factory()
    workspace = root / 'workspaces/task'
    (workspace / 'local.txt').write_text('ordinary local text', encoding='utf-8')
    context = ToolContext(workspace=workspace, workspace_backend=LocalWorkspaceBackend(workspace), shared_state={}, cycle_index=1, task_id='task')
    yield SimpleNamespace(service=service, source=source, store=store, registry=registry, context=context,
                          path='.knowledge/Manual/guide.pdf', config=config, frozen=frozen)
    knowledge.stop_knowledge_bridge()
    service.close()


def invoke(mounted, name, arguments):
    return mounted.registry.get_executor(name).handler(mounted.context, arguments)


def test_host_routes_pdf_text_and_local_files_through_the_same_builtin_names(mounted):
    found = invoke(mounted, 'find_files', {'path': '.knowledge/'})
    assert not found.error_code, found.content
    assert mounted.path in found.content
    read = invoke(mounted, 'read_file', {'path': mounted.path})
    assert not read.error_code and '42 members' in read.content
    searched = invoke(mounted, 'search_files', {'path': '.knowledge/', 'pattern': 'quota', 'output_mode': 'content'})
    assert not searched.error_code, searched.content
    assert mounted.path in searched.content and '42 members' in searched.content
    assert 'ordinary local text' in invoke(mounted, 'read_file', {'path': 'local.txt'}).content


@pytest.mark.parametrize('mode', ['ask', 'auto', 'full'])
def test_virtual_writes_are_rejected_without_approval_in_every_mode(mounted, mode):
    task = mounted.store.get_task('task')
    task['config_snapshot']['agent_profile']['permission_mode'] = mode
    mounted.store.update_task('task', config_snapshot=json.dumps(task['config_snapshot']))
    provider = LiveApprovalProvider(mounted.store, 'task')
    before = mounted.service.read_document([mounted.source['kb_id']], mounted.source['id'])['text']
    for name, arguments in [('write_file', {'path': mounted.path, 'content': 'overwrite'}),
                            ('edit_file', {'path': mounted.path, 'old_string': '42', 'new_string': '99'})]:
        request = SimpleNamespace(request_id='test', tool_name=name, arguments=arguments)
        assert provider.should_request(request) is False
        result = invoke(mounted, name, arguments)
        assert result.error_code and 'read' in result.content.lower(), result.content
    assert mounted.service.read_document([mounted.source['kb_id']], mounted.source['id'])['text'] == before
    assert not (mounted.context.workspace / '.knowledge').exists()


def test_virtual_absolute_alias_read_needs_no_external_file_approval(mounted):
    provider = LiveApprovalProvider(mounted.store, 'task')
    for path in [mounted.path, '/' + mounted.path, '/workspace/' + mounted.path,
                 str(mounted.context.workspace / mounted.path)]:
        assert provider.should_request(SimpleNamespace(request_id='read', tool_name='read_file', arguments={'path': path})) is False
    assert provider.should_request(SimpleNamespace(request_id='read', tool_name='read_file', arguments={'path': '../outside.txt'})) is True


def test_existing_handler_binding_cannot_read_after_saved_mounts_are_removed(mounted):
    task = mounted.store.get_task('task')
    task['config_snapshot']['knowledge_bases'] = []
    task['config_snapshot']['agent_profile']['knowledge_base_ids'] = []
    mounted.store.update_task('task', config_snapshot=json.dumps(task['config_snapshot']))
    result = invoke(mounted, 'read_file', {'path': mounted.path})
    assert result.error_code
    assert '42 members' not in result.content
