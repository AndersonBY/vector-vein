import json
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from task_agent.permissions import requires_approval, outside_workspace, validate_permission_mode
from task_agent_scenario import ScenarioModelHandler


@pytest.mark.parametrize('mode,name,args,expected', [
    ('ask', 'bash', {'command': 'pwd'}, True),
    ('auto', 'bash', {'command': 'pwd'}, True),
    ('auto', 'bash', {'command': 'pwd; curl https://example.invalid'}, True),
    ('auto', 'bash', {'command': 'ls $(touch unsafe)'}, True),
    ('auto', 'bash', {'command': 'python script.py'}, True),
    ('auto', 'bash', {'command': 'pwd', 'exec_dir': '..'}, True),
    ('auto', 'bash', {'command': 'pwd', 'auto_confirm': True}, True),
    ('auto', 'bash', {'command': ['pwd']}, True),
    ('ask', 'write_file', {'path': 'outputs/a.txt'}, False),
    ('auto', 'write_file', {'path': '../outside.txt'}, True),
    ('ask', 'read_file', {'path': '../outside.txt'}, True),
    ('full', 'write_file', {'path': '../outside.txt'}, False),
    ('full', 'bash', {'command': 'arbitrary command'}, False),
])
def test_policy_decisions(tmp_path, mode, name, args, expected):
    assert requires_approval(mode, name, SimpleNamespace(workspace=tmp_path), args) is expected


def test_invalid_mode_and_sibling_prefix_are_not_trusted(tmp_path):
    with pytest.raises(ValueError):
        validate_permission_mode('never')
    assert outside_workspace(tmp_path / 'task', str(tmp_path / 'task-other/file'))


class PermissionModel(ScenarioModelHandler):
    reviews = []
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if payload['model'] == 'risk-model':
            type(self).reviews.append(payload)
            evidence = json.loads(payload['messages'][-1]['content'])
            safe = evidence['tool'] == 'bash' and evidence['arguments']['command'] == 'pwd'
            body = json.dumps({'id': 'review', 'object': 'chat.completion', 'created': 1, 'model': 'risk-model', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': json.dumps({'decision': 'allow' if safe else 'ask', 'risk': 'low' if safe else 'high', 'reason': 'within_scope' if safe else 'external_access'})}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 20, 'completion_tokens': 15, 'total_tokens': 35}}).encode()
            if payload.get('stream'):
                content = json.dumps({'decision': 'allow' if safe else 'ask', 'risk': 'low' if safe else 'high', 'reason': 'within_scope' if safe else 'external_access'})
                chunks = [self._chunk(payload, {'role': 'assistant', 'content': content}), self._chunk(payload, {}, 'stop')]
                body = (''.join('data: ' + json.dumps(c) + '\n\n' for c in chunks) + 'data: [DONE]\n\n').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream' if payload.get('stream') else 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        messages = payload['messages']
        goal = next(m['content'] for m in messages if m['role'] == 'user')
        target = goal.split('TARGET=', 1)[1].splitlines()[0].strip()
        tools = [m for m in messages if m['role'] == 'tool']
        child = 'create_sub_task' not in {t['function']['name'] for t in payload.get('tools', [])}
        if child:
            plans = [('write_file', {'path': target, 'content': 'approved-child'})]
        else:
            plans = [('create_sub_task', {'agent_id': 'worker', 'task_description': 'TARGET=' + target, 'wait_for_completion': True}),
                     ('bash', {'command': 'pwd', 'yield_time_ms': 1000}),
                     ('bash', {'command': 'mkdir -p outputs && printf command-ran > outputs/command.txt', 'yield_time_ms': 10000})]
        delta = {'role': 'assistant', 'content': 'Done'}
        count = len(tools)
        if count < len(plans):
            name, args = plans[count]
            delta['tool_calls'] = [{'index': 0, 'id': f'permission-{count}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]
        chunks = [self._chunk(payload, delta), self._chunk(payload, {}, 'tool_calls' if count < len(plans) else 'stop')]
        data = (''.join('data: ' + json.dumps(c) + '\n\n' for c in chunks) + 'data: [DONE]\n\n').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def test_permission_modes_child_approval_restart_and_denied_side_effects(tmp_path):
    PermissionModel.reviews = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), PermissionModel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).with_name('task_agent_permissions_smoke.py')), str(tmp_path), str(server.server_port)], capture_output=True, text=True, encoding='utf-8', timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout) == {'ask': 3, 'auto': 2, 'full': 0}
        assert len(PermissionModel.reviews) == 3
        assert all(not r.get('tools') for r in PermissionModel.reviews)
        assert all(r['model'] == 'risk-model' for r in PermissionModel.reviews)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
