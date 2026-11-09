"""Focused protocol/SDK routing tests; no desktop, paid models, or global SDK patches."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from vv_agent.tools.base import ToolContext
from vv_agent.tools.builtins import build_default_registry
from vv_agent.types import ToolCall, ToolResultStatus
from vv_agent.workspace.local import LocalWorkspaceBackend

from knowledge_base.storage import KnowledgeError
from task_agent import knowledge
from task_agent.knowledge_workspace import normalize_knowledge_path, register_knowledge_handlers

ROOT = '.knowledge/Manual'
PDF = ROOT + '/quota.pdf'
DOCX = ROOT + '/notes.docx'
MOUNTS = [{'kb_id': 'a' * 32, 'name': 'Manual'}]


@pytest.mark.parametrize('raw', ['.knowledge', './.knowledge', '/.knowledge', '/workspace/.knowledge',
                                 '.knowledge/', r'\workspace\.knowledge', '/task/cwd/.knowledge',
                                 '/task/cwd/./.knowledge', 'folder/../.knowledge'])
def test_aliases_use_one_lexical_namespace(raw):
    assert normalize_knowledge_path(raw, '/task/cwd') == '.knowledge'


@pytest.mark.parametrize('raw', [r'C:\tasks\t\.knowledge\Manual\quota.pdf',
                                 'c:/TASKS/t/.knowledge/Manual/quota.pdf',
                                 r'\\?\C:\tasks\t\.knowledge\Manual\quota.pdf'])
def test_windows_absolute_aliases_preserve_document_names(raw):
    assert normalize_knowledge_path(raw, r'C:\tasks\t') == PDF


@pytest.mark.parametrize('raw', ['.knowledge/../local.txt', '/workspace/.knowledge/x/../../local',
                                 r'C:\tasks\t\.knowledge\..\outside', '.knowledge/.. /local',
                                 '.knowledge:stream', '.knowledge./file', '.knowledge/file:stream'])
def test_namespace_traversal_and_windows_alias_bypasses_are_rejected(raw):
    with pytest.raises(ValueError):
        normalize_knowledge_path(raw, r'C:\tasks\t')


@pytest.mark.parametrize('raw', ['file.txt', '../outside', '/other/.knowledge/file', '.knowledge-backup/a', 'sub/.knowledge/a'])
def test_nonknowledge_paths_keep_native_routing(raw):
    assert normalize_knowledge_path(raw, '/task/cwd') is None


def test_normalization_never_resolves_symlinks(monkeypatch):
    monkeypatch.setattr(Path, 'resolve', lambda *_args, **_kwargs: pytest.fail('physical resolution'))
    assert normalize_knowledge_path('/task/cwd/.knowledge/Manual/quota.pdf', '/task/cwd') == PDF


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    state = {'calls': [], 'revoked': False, 'after_read': None,
             'documents': {PDF: 'before\nQuota 42\nquota 7\nafter\n', DOCX: 'Quota literal a.b\n'}}
    versions = {path: 'v1' for path in state['documents']}
    def entry(path):
        if path in ('.knowledge', ROOT):
            return dict(path=path, name=path.rsplit('/', 1)[-1], kind='folder', kb_id=MOUNTS[0]['kb_id'], status='ready', modified_at=None, size=0)
        if path not in state['documents']:
            raise KnowledgeError('not_found', 'C:/private/secret TOKEN')
        return dict(path=path, name=path.rsplit('/', 1)[-1], kind='file', kb_id=MOUNTS[0]['kb_id'], document_id='d' * 32,
                    status='ready', modified_at='2026-11-09', size=len(state['documents'][path].encode()), version=versions[path])
    def rpc(operation, payload):
        assert operation == 'vfs'
        assert payload['task_id'] == 'task' and payload['mounts'] == MOUNTS
        assert set(payload) == {'task_id', 'mounts', 'arguments'}
        state['calls'].append(deepcopy(payload['arguments']))
        if state['revoked']:
            raise KnowledgeError('invalid_scope', 'C:/private/secret TOKEN')
        args = payload['arguments']
        path = args['path']
        if args['action'] == 'stat':
            return entry(path)
        if args['action'] == 'list':
            assert args['recursive'] is True
            assert 0 <= args['offset'] <= 10000 and 1 <= args['limit'] <= 5000
            paths = [p for p in [ROOT, *state['documents']] if p.startswith(path + '/')]
            offset, limit = args['offset'], args['limit']
            values = [entry(p) for p in paths[offset:offset + limit]]
            end = offset + len(values)
            return dict(entries=values, total=len(paths), next_offset=end if end < len(paths) else None, truncated=end < len(paths))
        assert args['action'] == 'read' and args['limit'] <= 262144
        if args['expected_version'] != versions[path]:
            raise KnowledgeError('stale_source', 'private state')
        offset = args['offset']
        text = state['documents'][path]
        chunk = text[offset:offset + args['limit']]
        end = offset + len(chunk)
        result = dict(path=path, text=chunk, offset=offset, total=len(text), next_offset=end if end < len(text) else None, version=versions[path])
        if state['after_read']:
            state['after_read'](path)
        return result
    monkeypatch.setattr(knowledge, '_bridge_request', rpc)
    registry = build_default_registry()
    original_schemas = {name: registry.get_schema(name) for name in ('find_files', 'read_file', 'search_files', 'file_info')}
    register_knowledge_handlers(registry, tmp_path, 'task', {'knowledge_bases': MOUNTS}, tmp_path)
    context = ToolContext(workspace=tmp_path, shared_state={}, cycle_index=1, workspace_backend=LocalWorkspaceBackend(tmp_path), task_id='task')
    def invoke(name, **args):
        return registry.execute(ToolCall('test', name, args), context)
    return state, versions, registry, context, invoke, original_schemas


def test_schema_descriptions_are_extended_without_changing_parameters(mounted):
    _, _, registry, _, _, originals = mounted
    for name, original in originals.items():
        schema = registry.get_schema(name)
        assert schema['function']['parameters'] == original['function']['parameters']
        assert '.knowledge' in schema['function']['description'] and 'PDF/DOCX' in schema['function']['description']
        assert schema['function']['description'].startswith(original['function']['description'])


def test_local_calls_do_not_issue_rpc_or_change_native_read_state(mounted):
    state, _, _, context, invoke, _ = mounted
    (context.workspace / 'local.txt').write_text('local evidence', encoding='utf-8')
    read = invoke('read_file', path='local.txt')
    assert read.content == 'local evidence'
    assert state['calls'] == []
    assert context.shared_state['_workspace_file_baselines']['local.txt']['source'] == 'read_file'
    assert invoke('write_file', path='created.txt', content='local output').status_code == ToolResultStatus.SUCCESS
    assert (context.workspace / 'created.txt').read_text() == 'local output'
    assert state['calls'] == []


def test_root_discovery_keeps_page_quota_and_excludes_physical_collision(mounted):
    state, _, _, context, invoke, _ = mounted
    (context.workspace / 'local.txt').write_text('local')
    collision = context.workspace / '.knowledge'
    collision.mkdir()
    (collision / 'trap.txt').write_text('PHYSICAL_SECRET')
    for hidden in (False, True):
        result = invoke('find_files', path='.', max_results=1, offset=0, include_hidden=hidden)
        payload = json.loads(result.content)
        assert payload['virtual_directories'] == ['.knowledge/']
        assert len(payload['files']) <= 1
        assert not any('.knowledge' in path for path in payload['files'])
        assert 'PHYSICAL_SECRET' not in result.content
    assert 'Quota 42' in invoke('read_file', path=PDF).content
    assert (collision / 'trap.txt').read_text() == 'PHYSICAL_SECRET'
    state['calls'].clear()
    invoke('search_files', path='.', pattern='local')
    assert state['calls'] == []


@pytest.mark.parametrize('tool,args', [('write_file', {'content': 'overwrite'}), ('edit_file', {'old_string': '42', 'new_string': '99'})])
def test_virtual_writes_are_rejected_without_touching_bridge_or_disk(mounted, tool, args):
    state, _, _, context, invoke, _ = mounted
    result = invoke(tool, path=PDF, **args)
    assert result.error_code == 'knowledge_readonly'
    assert state['calls'] == [] and not (context.workspace / '.knowledge').exists()


def test_native_read_line_char_bounds_and_version_bound_cursor(mounted):
    state, versions, _, context, invoke, _ = mounted
    state['documents'][PDF] = '开始\n' + 'x' * 300000 + '\nlast'
    first = invoke('read_file', path='/workspace/' + PDF)
    assert first.truncated and first.cursor
    assert first.cursor.path == PDF
    assert first.cursor.offset_chars == 12000
    second = invoke('read_file', path=PDF, cursor=first.cursor.to_dict())
    assert not second.error_code and second.content.startswith('x')
    assert len([c for c in state['calls'] if c['action'] == 'read']) == 4
    versions[PDF] = 'v2'  # even unchanged text from a new generation invalidates continuation
    assert invoke('read_file', path=PDF, cursor=first.cursor.to_dict()).error_code == 'stale_source'
    selected = invoke('read_file', path=PDF, start_line=1, start_char=1, end_line=1, show_line_numbers=True)
    assert selected.content == '1: 始'
    assert context.shared_state == {}  # no cross-call content/baseline cache for mounts


def test_cross_rpc_page_change_discards_partial_text(mounted):
    state, versions, _, _, invoke, _ = mounted
    state['documents'][PDF] = 'PRIVATE_PARTIAL' + 'x' * 300000
    state['after_read'] = lambda path: versions.update({path: 'v2'})
    result = invoke('read_file', path=PDF)
    assert result.error_code == 'stale_source' and 'PRIVATE_PARTIAL' not in result.content


def test_file_info_and_find_preserve_original_suffix_and_bounded_paging(mounted):
    _, _, _, _, invoke, _ = mounted
    info = json.loads(invoke('file_info', path=PDF).content)
    assert info['is_file'] and info['suffix'] == '.pdf' and info['size'] > 0
    first = json.loads(invoke('find_files', path=ROOT, sort='path_asc', max_results=1).content)
    assert first['returned_count'] == 1 and first['truncated'] and first['next_offset'] == 1
    second = json.loads(invoke('find_files', path=ROOT, sort='path_asc', offset=1, max_results=1).content)
    assert first['files'] != second['files'] and not second['truncated']
    limited = json.loads(invoke('find_files', path='.knowledge', scan_limit=1).content)
    assert limited['truncated'] and limited['count_is_estimate']


def test_pdf_docx_search_modes_case_glob_type_context_and_paging(mounted):
    _, _, _, _, invoke, _ = mounted
    all_files = invoke('search_files', path='.knowledge', pattern='quota')
    assert all_files.metadata['files'] == [DOCX, PDF]
    counts = invoke('search_files', path=ROOT, pattern='quota', output_mode='count', type='pdf')
    assert counts.metadata['file_counts'] == {PDF: 2}
    sensitive = invoke('search_files', path=ROOT, pattern='Quota', output_mode='count')
    assert sensitive.metadata['summary']['total_matches'] == 2
    explicit = invoke('search_files', path=ROOT, pattern='Quota', case_sensitive=False, output_mode='count')
    assert explicit.metadata['summary']['total_matches'] == 3
    literal = invoke('search_files', path=ROOT, pattern='a.b', literal=True, glob='*.docx', output_mode='content')
    assert literal.metadata['matches'][0]['path'] == DOCX
    context = invoke('search_files', path=PDF, pattern='Quota', output_mode='content', c=1, head_limit=2)
    assert [(row['line'], row['is_match']) for row in context.metadata['matches']] == [(1, False), (2, True)]
    assert context.metadata['next_offset'] == 2
    last = invoke('search_files', path=PDF, pattern='Quota', output_mode='content', c=1, offset=2, head_limit=2)
    assert last.metadata['matches'][0]['line'] == 3
    assert not last.metadata['truncated']
    multiline = invoke('search_files', path=PDF, pattern='Quota 42\\nquota 7', multiline=True, output_mode='content')
    assert multiline.metadata['summary']['total_matches'] == 1
    assert multiline.metadata['matches'][0] == {'path': PDF, 'line': 2, 'text': 'Quota 42\nquota 7', 'is_match': True}


def test_long_match_rows_remain_pageable_and_report_clipped_text(mounted):
    state, _, _, _, invoke, _ = mounted
    state['documents'][PDF] = 'hit ' + 'x' * 40000 + '\nhit next'
    result = invoke('search_files', path=PDF, pattern='hit', output_mode='content', head_limit=1)
    assert result.metadata['matches'][0]['text_truncated']
    assert result.metadata['next_offset'] == 1 and result.metadata['content_truncated']
    following = invoke('search_files', path=PDF, pattern='hit', output_mode='content', offset=1)
    assert following.metadata['matches'][0]['text'] == 'hit next'


def test_revocation_and_provider_errors_are_safe_and_never_fall_back_local(mounted, monkeypatch):
    state, _, _, _, invoke, _ = mounted
    state['revoked'] = True
    for name in ('find_files', 'read_file', 'file_info', 'search_files'):
        args = {'pattern': 'quota'} if name == 'search_files' else {}
        result = invoke(name, path=PDF, **args)
        assert result.error_code and 'TOKEN' not in result.content and 'C:/private' not in result.content
    def fail(*_args):
        raise RuntimeError('C:/private TOKEN')
    monkeypatch.setattr(knowledge, '_bridge_request', fail)
    assert invoke('read_file', path=PDF).content == 'Knowledge access is unavailable. Check this task\'s mounted knowledge bases.'


def test_regex_budget_is_applied_to_virtual_text(mounted):
    state, _, _, _, invoke, _ = mounted
    state['documents'][PDF] = 'a' * 100000 + '!'
    result = invoke('search_files', path=PDF, pattern='(a+)+$', case_sensitive=True)
    assert result.error_code == 'regex_timeout'
