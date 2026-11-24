#!/usr/bin/env python3
"""Strict p1-05 SDK stdio smoke: one immutable invocation, no salvage retries.

prepare writes six declared seed/reference pairs; run creates an exclusive
append-only evidence directory. Product reads/submits use MCP during attempts.
A completed streak still needs an independent ComfyUI sampling audit and D4.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {'completed', 'failed', 'cancelled'}
PARAMETERS = {'mode':'template', 'checkpoint':'Illustrious-XL-v2.0.safetensors',
              'template':'default', 'execution_target':'local', 'loras':[],
              'width':512, 'height':512, 'batch_size':1, 'steps':4, 'cfg':7,
              'sampler_name':'euler', 'scheduler':'normal',
              'use_workflow_defaults':False, 'seed_mode':'fixed', 'negative_prompt':''}
PROMPTS = ['a red ceramic cup on a wooden table, simple still life, soft daylight',
           'a blue ceramic cup on a wooden table, simple still life, soft daylight']


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprints():
    paths = subprocess.check_output(['git','ls-files','backend/app','backend/workflows',
                                     'mcp-server/mcp_server','mcp-server/pyproject.toml',
                                     'mcp-server/uv.lock','prompt_library','style_presets'],cwd=ROOT,text=True).splitlines()
    paths += ['scripts/mcp_smoke_mac.py']
    return {p:digest((ROOT/p).read_bytes()) for p in paths if (ROOT/p).is_file()}


class Disqualified(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Disqualified(message)


class Evidence:
    def __init__(self, path):
        self.path=Path(path)
        self.path.mkdir(parents=True,exist_ok=False)
        (self.path/'payloads').mkdir()

    def append(self,name,value):
        with (self.path/name).open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'utc':utc(),**value},ensure_ascii=False)+'\n')
            stream.flush()
            os.fsync(stream.fileno())

    def write(self,name,value):
        with (self.path/name).open('x',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2)
            stream.write('\n')


class Tap:
    """Record actual JSON-RPC SessionMessages, including full result payloads."""
    def __init__(self, stream, evidence, session, direction):
        self.stream=stream;self.evidence=evidence;self.session=session;self.direction=direction
    def record(self,value):
        self.evidence.append('sdk-messages.jsonl',{'session':self.session,'direction':self.direction,
            'message':value.message.model_dump(mode='json',by_alias=True,exclude_none=True) if not isinstance(value,Exception) else {'exception':repr(value)}})
    async def send(self,value):
        self.record(value);await self.stream.send(value)
    async def receive(self):
        value=await self.stream.receive();self.record(value);return value
    def __aiter__(self): return self
    async def __anext__(self):
        try: return await self.receive()
        except anyio.EndOfStream: raise StopAsyncIteration
    async def __aenter__(self): return self
    async def __aexit__(self,*args): await self.aclose()
    async def aclose(self): await self.stream.aclose()


@asynccontextmanager
async def session(config,evidence,label):
    command=config['server_command']
    params=StdioServerParameters(command=command[0],args=command[1:],cwd=str(ROOT/'mcp-server'),
        env={'PYTHONPATH':str(ROOT/'mcp-server'), 'MCP_BACKEND_API_URL':config['backend'],
             'MCP_GALLERY_DIR':config['gallery'],
             **({'SMOKE_WIRE_FAULT':os.environ['SMOKE_WIRE_FAULT']} if 'SMOKE_WIRE_FAULT' in os.environ else {})})
    with (evidence.path/(label+'-stderr.txt')).open('x',encoding='utf-8') as stderr:
        async with stdio_client(params,errlog=stderr) as (read,write):
            async with ClientSession(Tap(read,evidence,label,'received'),Tap(write,evidence,label,'sent'),
                                     read_timeout_seconds=timedelta(seconds=65)) as client:
                await client.initialize()
                catalog=await client.list_tools()
                names={t.name for t in catalog.tools}
                require(len(names)==31 and {'gallery_get','generate','wait_for_job','health','list_resources'}<=names,'unexpected MCP discovery')
                gallery=next(t for t in catalog.tools if t.name=='gallery_get')
                require(gallery.description.startswith('Risk: read.') and gallery.inputSchema['properties'].get('include_content',{}).get('default') is False,'content contract absent from discovery')
                evidence.append('events.jsonl',{'phase':'preparation' if label=='qualification' else 'audit',
                    'event':'sdk_session_initialized','session':label,'command':command,'cwd':params.cwd})
                yield client


def envelope(result):
    require(not result.isError,'SDK returned isError')
    payload=result.structuredContent
    require(isinstance(payload,dict),'missing structured envelope')
    texts=[c.text for c in result.content if c.type=='text']
    require(len(texts)==1 and json.loads(texts[0])==payload,'text/structured envelopes disagree')
    require(type(payload.get('ok')) is bool,'invalid common envelope')
    return payload


def validate_record(data,job_id,art_id,declared,parent):
    require(data.get('artifact_id')==art_id and type(data.get('artifact_id')) is int,'canonical identity mismatch')
    require(data.get('job_id')==job_id and data.get('artifact_type')=='image','persisted job/type mismatch')
    require(data.get('revision_context_error') is None,'persisted context error')
    context=data.get('revision_context')
    require(isinstance(context,dict),'missing persisted context')
    required={'schema_version':'1.0','request_ref':declared['request_ref'],
        'brief_revision': 'blue-cup-v2' if parent else 'red-cup-v1',
        'parent_artifact_id':parent['artifact_id'] if parent else None,
        'parent_job_id':parent['job_id'] if parent else None,
        'parent_request_ref':declared['request_ref'] if parent else None,
        'parent_brief_revision':'red-cup-v1' if parent else None,
        'parent_context_status':'available' if parent else 'root'}
    require(all(k in context and context[k]==v for k,v in required.items()),'wrong persisted parent/request/brief lineage')
    require(data.get('mime_type')=='image/png','unsupported persisted MIME')
    workflow=data.get('workflow_metadata',{})
    require(workflow.get('prompt')==PROMPTS[1 if parent else 0],'persisted prompt mismatch')
    return context


def decode_content(data):
    content=data.get('content')
    require(isinstance(content,dict),'metadata-only result has no PNG bytes')
    require(set(content)=={'encoding','mime_type','byte_length','sha256','width','height','base64'},'invalid content shape')
    require(content['encoding']=='base64' and content['mime_type']=='image/png','invalid content encoding/MIME')
    encoded=content['base64']
    require(isinstance(encoded,str) and len(encoded)<=2796204,'unbounded content payload')
    try: raw=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError): raise Disqualified('invalid base64') from None
    require(0<len(raw)<=2097152 and type(content['byte_length']) is int and len(raw)==content['byte_length'],'byte length mismatch/limit')
    require(digest(raw)==content['sha256'],'PNG digest mismatch')
    try:
        with Image.open(io.BytesIO(raw),formats=['PNG']) as image:
            require(image.format=='PNG' and image.size==(512,512) and image.n_frames==1 and not getattr(image,'is_animated',False),'not static 512x512 PNG')
            require(type(content['width']) is int and type(content['height']) is int and image.size==(content['width'],content['height']),'decoded dimension mismatch')
            image.verify()
        with Image.open(io.BytesIO(raw),formats=['PNG']) as image: image.load()
    except Disqualified: raise
    except Exception: raise Disqualified('PNG full decoding failed') from None
    return raw


class Run:
    def __init__(self,config,evidence):
        self.config=config;self.evidence=evidence;self.frozen=fingerprints()
        self.jobs={};self.artifacts=set();self.phase='attempt';self.attempt=0;self.call_count=0
        self.summary={'result':'interrupted','streak':0,'attempts':[],'jobs':self.jobs,
                      'sampling_audit':'pending independent Backend/ComfyUI corroboration','owner_demo':'pending Producer/CTY'}

    async def call(self,client,tool,args):
        require(fingerprints()==self.frozen,'source changed during invocation')
        started=utc();begin=time.monotonic();self.call_count+=1
        try:
            result=await client.call_tool(tool,args)
            payload=envelope(result)
            self.evidence.append('calls.jsonl',{'phase':self.phase,'attempt':self.attempt,'tool':tool,'arguments':args,
                'started':started,'duration_seconds':time.monotonic()-begin,'result':result.model_dump(mode='json',by_alias=True,exclude_none=True)})
        except Exception as exc:
            self.evidence.append('calls.jsonl',{'phase':self.phase,'attempt':self.attempt,'tool':tool,'arguments':args,
                'started':started,'duration_seconds':time.monotonic()-begin,'exception':repr(exc)})
            raise
        require(fingerprints()==self.frozen,'source changed during call')
        return payload

    def status(self,job,payload):
        details=payload.get('data',{}) if payload.get('ok') else payload.get('error',{}).get('details',{})
        if details.get('job_id')==job and details.get('status') in TERMINAL:
            self.jobs[job]=details['status']

    async def image(self,client,declared,index,parent=None):
        args={**PARAMETERS,'prompt':PROMPTS[index],'seed':declared['seeds'][index],
              'revision_context':{'schema_version':'1.0','request_ref':declared['request_ref'],
                  'brief_revision':'blue-cup-v2' if index else 'red-cup-v1'}}
        if parent: args['revision_context']['parent_artifact_id']=parent['artifact_id']
        # Set uncertainty before transmission; no response/ID means stop admission.
        self.unknown_admission=True
        payload=await self.call(client,'generate',args)
        data=payload.get('data',{}) if payload.get('ok') else payload.get('error',{}).get('details',{})
        job=data.get('job_id') or payload.get('error',{}).get('job_id')
        require(isinstance(job,str) and bool(job) and job not in self.jobs,'unknown or repeated admission identity')
        self.unknown_admission=False;self.jobs[job]='unknown';self.status(job,payload)
        require(payload['ok'] and data.get('status') in {'queued','running'},'generation admission failed/nonterminal contract')
        waited=await self.call(client,'wait_for_job',{'job_id':job,'timeout_seconds':50})
        self.status(job,waited)
        result=waited.get('data',{})
        require(waited['ok'] and result.get('job_id')==job and result.get('status')=='completed'
                and result.get('job_domain')=='generation','wait did not return completed generation')
        artifacts=result.get('artifacts',[])
        require(len(artifacts)==1,'expected one canonical artifact')
        art=artifacts[0].get('artifact_id')
        require(type(art) is int and art>0 and art not in self.artifacts,'missing/repeated canonical artifact identity')
        payload=await self.call(client,'gallery_get',{'artifact_id':art,'include_content':True})
        require(payload['ok'],'canonical content read failed')
        data=payload['data'];validate_record(data,job,art,declared,parent)
        raw=decode_content(data)
        self.artifacts.add(art)
        filename=f'attempt-{self.attempt}-{index}-artifact-{art}.png'
        with (self.evidence.path/'payloads'/filename).open('xb') as stream: stream.write(raw)
        metadata={k:v for k,v in data.items() if k!='content'}
        record={'artifact_id':art,'job_id':job,'gallery_path':data.get('gallery_path'),
                'local_path':data.get('local_path'),'payload':filename,'sha256':digest(raw),
                'byte_length':len(raw),'width':512,'height':512,'metadata':metadata}
        self.current['images'].append(record)
        print(json.dumps({k:v for k,v in record.items() if k!='metadata'},ensure_ascii=False),flush=True)
        return record

    async def recover(self,client):
        self.phase='recovery'
        for job in self.jobs:
            if self.jobs[job] in TERMINAL: continue
            for _ in range(6):
                try:
                    payload=await self.call(client,'wait_for_job',{'job_id':job,'timeout_seconds':50})
                    self.status(job,payload)
                except Exception as exc:
                    self.evidence.append('events.jsonl',{'phase':'recovery','job_id':job,'error':repr(exc)})
                if self.jobs[job] in TERMINAL: break
        return all(status in TERMINAL for status in self.jobs.values())

    async def execute(self):
        self.evidence.write('frozen.json',{'utc':utc(),'config':self.config,'source':self.frozen,
            'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'interpreter':sys.executable,'packages':{x:importlib.metadata.version(x) for x in ('mcp','Pillow','httpx','pydantic','anyio')},
            'client_call_timeout_seconds':65,'tool_wait_overall_seconds':50})
        async with session(self.config,self.evidence,'qualification') as client:
            for number,declared in enumerate(self.config['attempts'],1):
                self.attempt=number;self.phase='attempt';self.call_count=0;self.unknown_admission=False
                self.current={'attempt':number,'declared':declared,'started':utc(),'qualifying':False,'images':[]}
                self.summary['attempts'].append(self.current)
                self.evidence.append('events.jsonl',{'phase':'attempt','event':'started','attempt':number})
                try:
                    health=await self.call(client,'health',{})
                    require(health['ok'] and health['data']['backend']['reachable'] and health['data']['comfyui']['reachable'],'Backend/local ComfyUI unavailable')
                    resources=await self.call(client,'list_resources',{})
                    require(resources['ok'] and PARAMETERS['checkpoint'] in resources['data'].get('checkpoints',[]) and 'default' in resources['data'].get('workflows',[]),'declared resources unavailable')
                    original=await self.image(client,declared,0)
                    await self.image(client,declared,1,original)
                    require(self.call_count==8,'extra/missing attempt calls')
                    self.current['qualifying']=True;self.summary['streak']+=1
                except Exception as exc:
                    self.current['reason']=str(exc);self.summary['streak']=0
                self.current.update(ended=utc(),calls=self.call_count,streak=self.summary['streak'])
                self.evidence.append('events.jsonl',{'phase':'attempt','event':'ended',**self.current})
                if self.unknown_admission:
                    self.summary['result']='unknown_admission';break
                if not self.current['qualifying'] and not await self.recover(client):
                    self.summary['result']='unresolved_jobs';break
                if self.summary['streak']==3:
                    self.summary['result']='streak_complete_pending_sampling_audit';break
            else: self.summary['result']='attempt_budget_exhausted'
        # New process/session corroborates already persisted records, outside flow.
        self.phase='audit'
        images=[image for attempt in self.summary['attempts'] for image in attempt['images']]
        if images:
            try:
                async with session(self.config,self.evidence,'persistence-audit') as client:
                    for image in images:
                        payload=await self.call(client,'gallery_get',{'artifact_id':image['artifact_id']})
                        require(payload['ok'] and payload['data']==image['metadata'],'new-session persistence mismatch')
                self.summary['persistence_audit']='passed'
            except Exception as exc:
                self.summary.update(result='audit_failed',persistence_audit=str(exc))
        else: self.summary['persistence_audit']='no validated images to corroborate'
        self.evidence.write('summary.json',self.summary)
        print(json.dumps({'result':self.summary['result'],'streak':self.summary['streak'],'attempts':len(self.summary['attempts']),'jobs':self.jobs}),flush=True)
        return 0 if self.summary['result']=='streak_complete_pending_sampling_audit' else 2


def prepare(args):
    seeds=[]
    while len(seeds)<12:
        value=secrets.randbits(48)
        if value not in seeds: seeds.append(value)
    identity=str(uuid.uuid4())
    value={'prepared_utc':utc(),'invocation_id':identity,'seed_origin':'secrets.randbits(48), allocated once before qualification',
        'parameters':PARAMETERS,'prompts':PROMPTS,'backend':args.backend,'gallery':str(Path(args.gallery).resolve()),
        'server_command':[sys.executable,'-m','mcp_server.server'],
        'attempts':[{'request_ref':f'p1-05/{identity}/attempt-{n+1}','seeds':seeds[n*2:n*2+2]} for n in range(6)]}
    with Path(args.config).open('x',encoding='utf-8') as stream: json.dump(value,stream,indent=2);stream.write('\n')
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--config',required=True);prep.add_argument('--backend',required=True);prep.add_argument('--gallery',required=True)
    run=sub.add_parser('run');run.add_argument('--config',required=True);run.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.command=='prepare': return prepare(args)
    config=json.loads(Path(args.config).read_text())
    require(config['parameters']==PARAMETERS and config['prompts']==PROMPTS,'changed fixed parameters/prompts')
    attempts=config['attempts'];seeds=[seed for a in attempts for seed in a['seeds']]
    require(len(attempts)==6 and len(seeds)==12 and len(set(seeds))==12 and all(type(s) is int and 0<=s<2**48 for s in seeds),'six fresh seed pairs required')
    require(len({a['request_ref'] for a in attempts})==6,'fresh request references required')
    evidence=Evidence(args.output);driver=Run(config,evidence)
    try: return asyncio.run(driver.execute())
    except BaseException as exc:
        evidence.append('events.jsonl',{'phase':driver.phase,'event':'invocation_interrupted','error':repr(exc)})
        if not (evidence.path/'summary.json').exists():
            driver.summary['interruption']=repr(exc);evidence.write('summary.json',driver.summary)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
