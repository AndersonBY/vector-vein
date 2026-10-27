"""Process locks and restart reconciliation against disposable real storage."""
import os
import subprocess
import sys
from pathlib import Path


def test_dead_process_recovery_and_chat_continuation(tmp_path):
    script = r'''
import sys, subprocess, json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from models import Agent, Conversation, Message, Workflow, WorkflowRunRecord, create_tables, database
from utilities.config import cache, config
from utilities.workflow_recovery import OWNERS, process_owner, owner_exited, recover_interrupted_runs
from utilities.workflow_stopping import _key, guarded_execution, register_child
from utilities.workflow_timeline import reset_run, initialize_timeline, update_timeline
from utilities.workflow_messages import project_workflow_message
from api.agent_api import MessageAPI
from api.workflow_api import WorkflowAPI

create_tables()
agent = Agent.create(name='recovery', model='test', model_provider='OpenAI')
chat = Conversation.create(agent=agent, agent_version=agent.version, title='recovery', model='test', model_provider='OpenAI')
workflow = Workflow.create(title='recovery', data={'nodes': [], 'edges': []})
def create(status='RUNNING', owners=None, source=None, data=None):
    snapshot = deepcopy(data or {'nodes': [], 'edges': []})
    if owners is not None: snapshot[OWNERS] = owners
    record = WorkflowRunRecord.create(workflow=workflow, status=status, data=snapshot,
        run_from='CHAT' if source else 'WEB', source_message=source.mid if source else None)
    snapshot['rid'] = record.rid.hex
    record.data = snapshot; record.save()
    if source:
        source.metadata = {'record_id': record.rid.hex, 'recordStatus': status}
        source.status = 'R'; source.save()
    return record
def saved(record): return WorkflowRunRecord.get_by_id(record.rid)

child_code = 'import sys;sys.path.insert(0,sys.argv[1]);from utilities.workflow_recovery import process_owner;print(process_owner(),flush=True);sys.stdin.readline()'
child = subprocess.Popen([sys.executable, '-X', 'utf8', '-c', child_code, sys.argv[1]],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
try:
    live = child.stdout.readline().strip()
    assert len(live) == 32, live
    assert not owner_exited(live)
    assert not owner_exited(process_owner())
    active = create(owners=[live])
    assert active.rid.hex not in recover_interrupted_runs()
    assert saved(active).status == 'RUNNING'
    child.communicate('\n', timeout=20)
    assert child.returncode == 0 and owner_exited(live)

    message = Message.create(conversation=chat, author_type='A', content_type='WKF', content={}, status='R')
    artifact = Path('retained.txt').resolve(); artifact.write_text('retained artifact')
    node = {'id':'done','type':'Text','category':'textProcessing','data':{
        'task_name':'text_processing.join','template':{'output':{'value':'completed output','is_output':True}},
        'artifacts':[{'path':str(artifact)}]}}
    pending = deepcopy(node); pending['id']='pending'
    data = {'nodes':[deepcopy(node),pending],'edges':[],'node_timeline':{
        'done':{'status':'SUCCEEDED'},'pending':{'status':'RUNNING','started_at':1}}}
    data['nodes'][0]['data']['template']['output']['value']='stale'
    interrupted = create(owners=[live], source=message, data=data)
    cache.set('workflow:record:finished_nodes:'+interrupted.rid.hex, [node])
    cache.set(_key(interrupted.rid.hex,'active'), 3)
    paused = create('PAUSED', [live])
    terminal = create('FINISHED', [live])
    queued = create('QUEUED', [live])
    stopping = create('STOPPING', [live])
    mixed = create(owners=[live,process_owner()])
    unknown = create(owners=['invalid'])
    legacy = create()
    malformed = create(owners='invalid')
    parent = create('PAUSED', [live], data={'nodes':[],'edges':[], 'pending_feedback_runs':[queued.rid.hex]})
    register_child(parent.rid.hex, queued.rid.hex)
    recovered = recover_interrupted_runs()
    assert set(recovered) == {r.rid.hex for r in [active,interrupted,queued,stopping]}
    result = saved(interrupted)
    assert result.status == 'FAILED' and result.end_time
    assert result.data['failures'][0]['code']=='WORKFLOW_INTERRUPTED'
    assert result.data['nodes'][0]['data']['template']['output']['value']=='completed output'
    assert result.data['nodes'][0]['data']['artifacts'][0]['path']==str(artifact)
    assert artifact.read_text()=='retained artifact'
    assert result.data['node_timeline']['done']['status']=='SUCCEEDED'
    assert result.data['node_timeline']['pending']['status']=='FAILED'
    assert cache.get(_key(result.rid.hex,'active')) == 0
    projected = Message.get_by_id(message.mid)
    assert projected.status=='Z' and projected.metadata['recordStatus']=='FAILED'
    assert json.loads(projected.metadata['workflow_result'])['failures'][0]['code']=='WORKFLOW_INTERRUPTED'
    assert WorkflowAPI().check_status({'rid':result.rid.hex})['msg']=='FAILED'
    assert saved(paused).status=='PAUSED' and saved(terminal).status=='FINISHED'
    assert saved(parent).status=='FAILED'
    assert saved(parent).data['failures'][0]['code']=='WORKFLOW_INTERRUPTED'
    for record in [mixed, unknown, legacy, malformed]: assert saved(record).status=='RUNNING'
    assert recover_interrupted_runs()==[]
    called=[]
    @guarded_execution
    def replay(data): called.append(True)
    replay(saved(queued).data)
    assert not called

    # A completed chat run can create precisely one continuation, and only at its current tail.
    finished = create('FINISHED', [live], source=message)
    chat.current_message=message.mid;chat.save()
    payload={'cid':chat.cid.hex,'mid':message.mid.hex,'record_id':finished.rid.hex}
    first=MessageAPI().append_answer(payload)
    assert first['status']==200 and first['data'].get('ai_message_mid'), first
    assert Message.get_by_id(message.mid).status=='S'
    count=Message.select().count()
    assert MessageAPI().append_answer(payload)['data']['already_appended']
    chat.current_message=message.mid;chat.save()
    assert MessageAPI().append_answer(payload)['data']['already_appended']
    assert Message.select().count()==count
    # Old run projection may never overwrite a newer binding.
    before=Message.get_by_id(message.mid).metadata
    project_workflow_message(interrupted)
    assert Message.get_by_id(message.mid).metadata==before
    assert MessageAPI().append_answer({**payload,'record_id':interrupted.rid.hex})['status']==409
    assert MessageAPI().append_answer({**payload,'record_id':'bad'})['status']==400
    another = Message.create(conversation=chat, author_type='A', content_type='WKF', status='R')
    off_branch = create('FINISHED',[live],source=another)
    assert MessageAPI().append_answer({**payload,'mid':another.mid.hex,'record_id':off_branch.rid.hex})['data']['already_appended']
    assert Message.select().count()==count+1
    # Projection failures cannot roll back recovery or prevent startup.
    broken = create(owners=[live], source=another)
    with patch('utilities.workflow_messages.project_workflow_message', side_effect=RuntimeError('unavailable')):
        assert recover_interrupted_runs()==[broken.rid.hex]
    assert saved(broken).status=='FAILED'
    # A fast worker may finish before queue submission returns.
    from api.utils import run_workflow_common
    from utilities.workflow import Workflow as Execution
    def fast(data):
        assert Message.get_by_id(another.mid).metadata['record_id']==data['rid']
        Execution(data).report_workflow_status(200)
    with patch('celery_tasks.run_workflow.delay', side_effect=fast):
        rid=run_workflow_common({'nodes':[],'edges':[]},workflow,message=another,run_from='CHAT')
    assert WorkflowRunRecord.get_by_id(rid).data[OWNERS]==[process_owner()]
    assert Message.get_by_id(another.mid).status=='S'
    print('recovery integration passed')
finally:
    if child.poll() is None: child.communicate('\n',timeout=20)
    cache.close(); database.close(); config.close()
'''
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR")}
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", script,
                             str(Path(__file__).resolve().parents[1])], cwd=tmp_path,
                            env=environment, capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "recovery integration passed" in result.stdout
