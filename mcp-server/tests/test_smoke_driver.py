"""Actual CLI + SDK stdio + registered MCP + HTTP/storage fixtures.

Wire faults deliberately damage actual protocol results; the driver is never
imported or patched, and no duplicate qualification state machine is tested.
"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import uuid

import pytest
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
DRIVER=ROOT/'scripts/mcp_smoke_mac.py'


@pytest.fixture
def fixture_backend(tmp_path):
    gallery=tmp_path/'gallery';gallery.mkdir()
    output=io.BytesIO();Image.new('RGB',(512,512),'red').save(output,format='PNG');raw=output.getvalue()
    records={};jobs={};requests=[];submits=[]
    exports=ROOT/'mcp-server/tests/fixtures/health-workers'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send_json(self,body,status=200):
            encoded=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded)
        def do_GET(self):
            requests.append(('GET',self.path))
            route={'/health':('backend','response'),'/api/system/status':('comfyui-connected','response'),'/api/workers/status':('unconfigured','responses')}.get(self.path)
            if route:
                body=json.loads((exports/(route[0]+'.json')).read_text())[route[1]]
                self.send_json(body[0] if isinstance(body,list) else body)
            elif self.path=='/api/generate/available-resources': self.send_json({'checkpoints':['Illustrious-XL-v2.0.safetensors'],'workflows':['default']})
            elif self.path=='/api/workflow-catalog/generation-forms': self.send_json({'items':[]})
            elif self.path.startswith('/api/gallery/artifacts/'): self.send_json(records[int(self.path.rsplit('/',1)[1])])
            elif self.path.startswith('/api/generate/job/'):
                job=self.path.rsplit('/',1)[1];record=jobs[job]
                self.send_json({'job_id':job,'status':'completed','artifacts':[record],'revision_context':record['revision_context']})
            else: self.send_json({'detail':'not found'},404)
        def do_POST(self):
            assert self.path=='/api/generate/'
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            submits.append(body);requests.append(('POST',self.path))
            art=len(records)+1;job=str(uuid.uuid4());name=f'cup-{art}.png';(gallery/name).write_bytes(raw)
            context={**body['revision_context'],'schema_version':'1.0','parent_artifact_id':body['revision_context'].get('parent_artifact_id'),
                     'parent_job_id':None,'parent_request_ref':None,'parent_brief_revision':None,'parent_context_status':'root'}
            if context['parent_artifact_id']:
                parent=records[context['parent_artifact_id']]
                context.update(parent_job_id=parent['job_id'],parent_request_ref=parent['revision_context']['request_ref'],
                    parent_brief_revision=parent['revision_context']['brief_revision'],parent_context_status='available')
            record={'id':art,'job_id':job,'artifact_type':'image','mime_type':'image/png','gallery_path':name,
                'artifact_url':'/gallery/'+name,'local_path':str(gallery/name),'revision_context':context,
                'revision_context_error':None,'prompt':body['prompt'],'width':512,'height':512,'metadata_json':json.dumps({'revision_context':context})}
            records[art]=record;jobs[job]=record
            self.send_json({'job_id':job,'status':'queued','revision_context':context},202)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}',gallery,submits,requests,records
    server.shutdown();server.server_close();thread.join()


def run_driver(tmp_path,fixture_backend,fault=''):
    url,gallery,submits,requests,records=fixture_backend
    config=tmp_path/'config.json';out=tmp_path/'evidence'
    prepare=subprocess.run([sys.executable,str(DRIVER),'prepare','--config',str(config),'--backend',url,'--gallery',str(gallery)],cwd=ROOT,text=True,capture_output=True,timeout=15)
    assert prepare.returncode==0,prepare.stderr
    settings=json.loads(config.read_text())
    if fault:
        settings['server_command']=[sys.executable,str(ROOT/'mcp-server/tests/fixtures/smoke/wire_fault.py')]
        config.write_text(json.dumps(settings))
    env={**os.environ,'PYTHONPATH':str(ROOT/'mcp-server'),'SMOKE_WIRE_FAULT':fault}
    result=subprocess.run([sys.executable,str(DRIVER),'run','--config',str(config),'--output',str(out)],cwd=ROOT,env=env,text=True,capture_output=True,timeout=40)
    assert result.returncode in (0,2),result.stderr
    summary=json.loads((out/'summary.json').read_text())
    calls=[json.loads(line) for line in (out/'calls.jsonl').read_text().splitlines()]
    wire=[json.loads(line) for line in (out/'sdk-messages.jsonl').read_text().splitlines()]
    return result,summary,calls,wire,out,settings


def test_three_pairs_exact_eight_calls_and_new_session_content_roundtrip(tmp_path,fixture_backend):
    result,summary,calls,wire,out,settings=run_driver(tmp_path,fixture_backend)
    assert result.returncode==0, result.stderr
    assert summary['result']=='streak_complete_pending_sampling_audit'
    assert len(summary['attempts'])==3 and summary['streak']==3
    assert len(fixture_backend[2])==6
    expected=['health','list_resources','generate','wait_for_job','gallery_get','generate','wait_for_job','gallery_get']
    for n in range(1,4):
        assert [c['tool'] for c in calls if c['phase']=='attempt' and c['attempt']==n]==expected
    assert len([c for c in calls if c['phase']=='audit'])==6
    assert len({x['job_id'] for a in summary['attempts'] for x in a['images']})==6
    assert len(list((out/'payloads').glob('*.png')))==6
    for i,submit in enumerate(fixture_backend[2]):
        assert {k:submit[k] for k in ('execution_target','loras','steps','width','height','batch_size','cfg','sampler_name','scheduler')} == {'execution_target':'local','loras':[],'steps':4,'width':512,'height':512,'batch_size':1,'cfg':7,'sampler_name':'euler','scheduler':'normal'}
        assert submit['seed']==settings['attempts'][i//2]['seeds'][i%2]
    assert {x['session'] for x in wire}=={'qualification','persistence-audit'}
    assert any('base64' in json.dumps(x) for x in wire)
    # Exclusive evidence destination prevents accidental rerunning an invocation.
    rerun=subprocess.run([sys.executable,str(DRIVER),'run','--config',str(tmp_path/'config.json'),'--output',str(out)],cwd=ROOT,capture_output=True,timeout=10)
    assert rerun.returncode!=0 and len(fixture_backend[2])==6


@pytest.mark.parametrize('fault',['metadata-only','invalid-bytes','digest','length','parent','job','context-error','timeout','failed','cancelled','nonterminal'])
def test_actual_driver_rejects_damaged_results_retains_failures_and_recovers(tmp_path,fixture_backend,fault):
    result,summary,calls,wire,out,settings=run_driver(tmp_path,fixture_backend,fault)
    assert summary['attempts'][0]['qualifying'] is False
    assert summary['attempts'][0]['streak']==0
    assert summary['attempts'][0]['reason']
    # Later attempts are new declared requests, never a repeated submit.
    assert len({x['revision_context']['request_ref'] for x in fixture_backend[2]})==4
    submits=[c for c in calls if c['phase']=='attempt' and c['tool']=='generate']
    assert len(submits)==len(fixture_backend[2])==7
    assert all(x['execution_target']=='local' for x in fixture_backend[2])
    assert len(summary['attempts'])==4 and summary['streak']==3
    if fault in ('timeout','nonterminal'):
        assert len([c for c in calls if c['phase']=='recovery'])==1
    assert summary['attempts'][0]['calls']<=5


@pytest.mark.parametrize('fault',['unresolved','unknown-admission'])
def test_unknown_or_six_unresolved_recovery_calls_stop_without_duplicate_submit(tmp_path,fixture_backend,fault):
    result,summary,calls,wire,out,settings=run_driver(tmp_path,fixture_backend,fault)
    assert result.returncode==2
    assert len(summary['attempts'])==1 and summary['streak']==0
    assert len(fixture_backend[2])==1
    assert summary['result'] in ('unresolved_jobs','unknown_admission')
    assert len([c for c in calls if c['phase']=='recovery'])==(6 if fault=='unresolved' else 0)


def test_streak_resets_retains_first_success_and_uses_new_declared_attempts(tmp_path,fixture_backend):
    _,summary,calls,_,_,_=run_driver(tmp_path,fixture_backend,'reset')
    assert [a['streak'] for a in summary['attempts']]==[1,0,1,2,3]
    assert len(fixture_backend[2])==9


def test_six_attempt_budget_preserves_every_failure(tmp_path,fixture_backend):
    result,summary,calls,_,_,_=run_driver(tmp_path,fixture_backend,'budget')
    assert result.returncode==2
    assert summary['result']=='attempt_budget_exhausted'
    assert len(summary['attempts'])==6 and all(not a['qualifying'] for a in summary['attempts'])
    assert len(fixture_backend[2])==6
    assert len([c for c in calls if c['phase']=='recovery'])==6


def test_new_session_audit_failure_invalidates_a_complete_streak(tmp_path,fixture_backend):
    result,summary,calls,_,out,_=run_driver(tmp_path,fixture_backend,'audit')
    assert result.returncode==2 and summary['result']=='audit_failed'
    assert summary['streak']==3 and len(fixture_backend[2])==6
    assert len(list((out/'payloads').glob('*.png')))==6
    assert summary['persistence_audit']!='passed'
