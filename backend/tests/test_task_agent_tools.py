import json
import subprocess
import shlex
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from task_agent_scenario import ScenarioModelHandler


class DelegationModel(ScenarioModelHandler):
    calls = []

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).calls.append(payload)
        tools = [m for m in payload['messages'] if m['role'] == 'tool']
        tool_names = {t['function']['name'] for t in payload.get('tools', [])}
        child = 'create_sub_task' not in tool_names
        goal = next((m['content'] for m in payload['messages'] if m['role'] == 'user'), '')
        gate = 'GATED_CHILD' in goal
        restricted = 'RESTRICTED' in goal
        if child:
            plans = ([('ask_user', {'question': 'Continue child?', 'options': ['Yes'], 'selection_type': 'single', 'allow_custom_options': False})] if gate else [])
            plans += [('bash', {'command': 'printf child-shell-ok', 'yield_time_ms': 10000}), ('write_file', {'path': 'outputs/' + ('gated' if gate else ('batch-a' if 'BATCH_A' in goal else 'batch-b')) + '.txt', 'content': 'child verified'})]
            content = 'CHILD_COMPLETE'
        else:
            plans = [('bash', {'command': 'printf parent-shell-ok', 'yield_time_ms': 10000}),
                     ('create_sub_task', {'agent_id': 'worker', 'task_description': 'GATED_CHILD: confirm then execute shell and write output.', 'wait_for_completion': True}),
                     ('create_sub_task', {'agent_id': 'worker', 'tasks': [{'task_description': 'BATCH_A'}, {'task_description': 'BATCH_B'}], 'wait_for_completion': False}),
                     ('sub_task_status', {'wait_for_completion': True})]
            content = 'PARENT_COMPLETE'
        if restricted and not child:
            plans = [('create_sub_task', {'agent_id': 'worker', 'task_description': 'RESTRICTED_CHILD', 'wait_for_completion': True})]
        if 'CANCEL_CHILDREN' in goal and not child:
            plans = [('create_sub_task', {'agent_id': 'worker', 'tasks': [{'task_description': 'GATED_CHILD_A'}, {'task_description': 'GATED_CHILD_B'}], 'wait_for_completion': True})]
        if 'CANCEL_SHELL' in goal and not child:
            program = "import os,time;from pathlib import Path;Path('command.pid').write_text(str(os.getpid()));time.sleep(30)"
            command = shlex.quote(sys._base_executable.replace('\\', '/')) + ' -c ' + shlex.quote(program)
            plans = [('bash', {'command': command, 'yield_time_ms': 0}), ('ask_user', {'question': 'Wait while command is running?'})]
        count = len(tools)
        call = None
        if count < len(plans):
            name, arguments = plans[count]
            if name == 'sub_task_status':
                arguments = {**arguments, 'task_ids': json.loads(tools[-1]['content'])['task_ids']}
            call = {'id': f'call_{count}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(arguments)}}
            content = 'Working'
        chunks = [self._chunk(payload, {'role': 'assistant', 'content': content})]
        if call:
            chunks.append(self._chunk(payload, {'tool_calls': [{'index': 0, **call}]}))
        chunks.append(self._chunk(payload, {}, 'tool_calls' if call else 'stop'))
        body = (''.join('data: ' + json.dumps(chunk) + '\n\n' for chunk in chunks) + 'data: [DONE]\n\n').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_shell_children_restart_background_batch_and_results(tmp_path):
    DelegationModel.calls = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), DelegationModel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).with_name('task_agent_tools_smoke.py')), str(tmp_path), str(server.server_port)], capture_output=True, text=True, encoding='utf-8', timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)['children'] == 3
        child_calls = [c for c in DelegationModel.calls if 'create_sub_task' not in {t['function']['name'] for t in c.get('tools', [])}]
        assert child_calls
        assert all(c['model'] == 'mock-task-model' for c in child_calls)
        assert all('sub_task_status' not in {t['function']['name'] for t in c.get('tools', [])} for c in child_calls)
        outputs = [m['content'] for c in DelegationModel.calls for m in c['messages'] if m['role'] == 'tool']
        assert any('parent-shell-ok' in v for v in outputs)
        assert any('child-shell-ok' in v for v in outputs)
        restricted_calls = [c for c in child_calls if any('RESTRICTED_CHILD' in str(m.get('content')) for m in c['messages'] if m['role'] == 'user')]
        assert restricted_calls
        assert all(not {'bash', 'write_file', 'edit_file'}.intersection(t['function']['name'] for t in c.get('tools', [])) for c in restricted_calls)
        assert any('tool_not_allowed' in m['content'] for c in restricted_calls for m in c['messages'] if m['role'] == 'tool')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
