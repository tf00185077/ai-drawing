"""Test-only JSON-RPC wire fault injector around the unmodified real server.

No product callable is patched. Arguments/responses otherwise pass verbatim.
"""
import json
import os
import subprocess
import sys
import threading

child=subprocess.Popen([sys.executable,'-m','mcp_server.server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
pending={}
waits=0
fault=os.environ.get('SMOKE_WIRE_FAULT','')

def forward():
    for line in sys.stdin.buffer:
        obj=json.loads(line)
        if 'id' in obj: pending[obj['id']]=obj.get('params',{})
        child.stdin.write(line);child.stdin.flush()
    child.stdin.close()
threading.Thread(target=forward,daemon=True).start()
for line in child.stdout:
    obj=json.loads(line)
    params=pending.get(obj.get('id'),{})
    name=params.get('name')
    if 'result' in obj and name:
        result=obj['result']
        payload=result.get('structuredContent')
        if name=='wait_for_job': waits+=1
        active = (fault!='reset' and waits==1) or fault in ('unresolved','budget') or (fault=='reset' and waits==3)
        if payload and payload.get('ok') and fault=='audit' and name=='gallery_get' and not params.get('arguments',{}).get('include_content'):
            payload['data']['job_id']='wrong-persisted-job'
            result['content']=[{'type':'text','text':json.dumps(payload,ensure_ascii=False)}]
        if payload and payload.get('ok') and active:
            data=payload['data']
            if name=='generate' and fault=='unknown-admission':
                payload={'ok':False,'error':{'code':'admission_uncertain','message':'wire lost admission identity','hint':'inspect existing request'}}
            elif name=='wait_for_job' and (fault!='budget' or waits%2==1) and fault in ('timeout','unresolved','reset','budget','failed','cancelled','nonterminal'):
                if fault=='nonterminal': data['status']='running'
                else:
                    status={'failed':'failed','cancelled':'cancelled'}.get(fault,'unknown')
                    payload={'ok':False,'error':{'code':'job_'+status if status!='unknown' else 'timeout',
                        'message':'injected wire event','hint':'same ID read',
                        'details':{'job_id':data['job_id'],'status':status}}}
            elif name=='gallery_get' and fault in ('metadata-only','invalid-bytes','digest','length','parent','job','context-error'):
                if fault=='metadata-only': data.pop('content',None)
                elif fault=='invalid-bytes': data['content']['base64']='not base64'
                elif fault=='digest': data['content']['sha256']='0'*64
                elif fault=='length': data['content']['byte_length']+=1
                elif fault=='parent': data['revision_context']['parent_artifact_id']=999
                elif fault=='job': data['job_id']='wrong-job'
                else: data['revision_context_error']='revision_context_unavailable'
            result['structuredContent']=payload
            result['content']=[{'type':'text','text':json.dumps(payload,ensure_ascii=False)}]
        elif payload and name=='generate' and fault=='unknown-admission':
            payload={'ok':False,'error':{'code':'admission_uncertain','message':'wire lost admission identity','hint':'inspect existing request'}}
            result['structuredContent']=payload;result['content']=[{'type':'text','text':json.dumps(payload)}]
    print(json.dumps(obj,ensure_ascii=False),flush=True)
child.wait()
