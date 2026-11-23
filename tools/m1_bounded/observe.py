"""Fixed M1 finite observation subset; caller-supplied named socket handles.

No endpoint discovery, connection fallback, retry, broad process locator or shell.
"""
import json
import os
import selectors
import select
import socket
import subprocess
import sys
import time
from ledger import Stop, CHUNK, bounded_json, finish_owned

CATALOG={
 'pre-openapi':(8001,'/openapi.json',4194304),
 'pre-generate':(8001,'/api/generate/queue',2097152),
 'pre-training':(8001,'/api/lora-train/status',2097152),
 'pre-comfy':(8188,'/queue',2097152),
 'post-maintenance':(8001,'/maintenance/status',2097152),
 'post-comfy':(8188,'/queue',2097152)}
HEADER=65536
OUTPUT=2097152

class Deadline:
    def __init__(self,seconds=4):
        if type(seconds)not in(int,float) or not 0<seconds<=4:raise Stop('plan')
        self.end=time.monotonic()+seconds
    def left(self):
        t=self.end-time.monotonic()
        if t<=0:raise Stop('deadline')
        return t

def parse_json(raw):
    # Bound recursive parser stack and lexical string tokens BEFORE json.loads.
    if type(raw)is not bytes or len(raw)>4194304:raise Stop('limit')
    depth=0;quoted=False;escape=False;token=0;records=0
    for b in raw:
        if quoted:
            token+=1
            if token>131072:raise Stop('schema')
            if escape:escape=False
            elif b==92:escape=True
            elif b==34:quoted=False
        elif b==34:quoted=True;token=0
        elif b==44:
            records+=1
            if records>100000:raise Stop('schema')
        elif b in (91,123):
            depth+=1
            if depth>16:raise Stop('schema')
        elif b in (93,125):depth-=1
    def pairs(seq):
        if len(seq)>128:raise Stop('schema')
        d={}
        for k,v in seq:
            if k in d:raise Stop('schema')
            d[k]=v
        return d
    def number(s):
        if len(s)>19:raise Stop('schema')
        return int(s)
    def reject(_):raise Stop('schema')
    try:
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_int=number,parse_float=reject,parse_constant=reject)
    except (UnicodeError,ValueError,RecursionError):raise Stop('schema')
    bounded_json(value,4194304)
    return value

def project(name,value):
    """No current live schema certified. Supplied synthetic schema1 subset only."""
    if type(value)is not dict:raise Stop('schema')
    if name=='pre-training':
        if set(value)-{'status','current_job','queue','durable'} or value.get('status')not in('idle','running','queued') or 'current_job'not in value or type(value.get('queue'))is not list:
            raise Stop('schema')
        job=value['current_job']
        if job is not None and (type(job)is not dict or set(job)!={'job_id'} or type(job['job_id'])is not str or len(job['job_id'])>64):raise Stop('schema')
        if len(value['queue'])>100000:raise Stop('schema')
        durable=value.get('durable')
        # Preserve nullable/missing/unavailable, never invent a durable count.
        if durable is not None and (type(durable)is not dict or set(durable)!={'queued','running'} or any(type(n)is not int or n<0 for n in durable.values())):raise Stop('schema')
        return {'status':value['status'],'current_job_present':True,'current_job':job,
                'queue_count':len(value['queue']),'durable_present':'durable'in value,'durable':durable}
    # Finite receipt for unsupported actual catalog schemas, not fabricated queue0.
    return {'catalog':name,'schema_binding':'unavailable','observed':True,'typed_state':None}

class Observations:
    """One-use catalog budget attached to the same Window, not refillable objects."""
    def __init__(self,w):
        self.w=w

    def http(self,name,sock,slot,seconds=4):
        # Takes ownership of this explicit socket. No automatic endpoint selection.
        def action():
            if name not in CATALOG or name in self.w.observation_used:raise Stop('plan')
            self.w.observation_used.add(name)
            port,path,cap=CATALOG[name];deadline=Deadline(seconds)
            sock.setblocking(False)
            request=('GET '+path+' HTTP/1.1\r\nHost: 127.0.0.1:'+str(port)+'\r\nConnection: close\r\nAccept-Encoding: identity\r\n\r\n').encode('ascii')
            if self.w.plan.get(slot,('',))[0]!='file' or slot in self.w.used:
                raise Stop('plan')
            request_slot='controls/request-'+name
            if self.w.plan.get(request_slot)!=('native',len(request)):raise Stop('plan')
            self.w.claim(request_slot,'native')
            sent=0
            while sent<len(request):
                if not select.select([], [sock], [], deadline.left())[1]:raise Stop('deadline')
                n=sock.send(request[sent:])
                if not n:raise Stop('protocol')
                sent+=n
            raw=bytearray();wire=0
            def receive(maximum):
                nonlocal wire
                if not select.select([sock],[],[],deadline.left())[0]:raise Stop('deadline')
                data=sock.recv(min(CHUNK,maximum))
                wire+=len(data)
                if wire>HEADER+cap:raise Stop('limit')
                return data
            while b'\r\n\r\n' not in raw:
                data=receive(min(CHUNK,HEADER+1-len(raw)))
                if not data:raise Stop('protocol')
                raw.extend(data)
                if len(raw)>HEADER:raise Stop('limit')
            head,body=bytes(raw).split(b'\r\n\r\n',1)
            lines=head.split(b'\r\n')
            if len(lines)>129 or any(len(x)>4096 for x in lines) or lines[0]!=b'HTTP/1.1 200 OK':raise Stop('protocol')
            headers={}
            for line in lines[1:]:
                if b':'not in line or line[:1]in(b' ',b'\t'):raise Stop('protocol')
                key,value=line.split(b':',1);key=key.lower()
                if not key or any(x not in b'abcdefghijklmnopqrstuvwxyz0123456789-' for x in key) or key in headers or any(x<32 or x>126 for x in value):raise Stop('protocol')
                headers[key]=value.strip()
            if b'transfer-encoding'in headers or b'trailer'in headers or headers.get(b'content-encoding',b'identity')!=b'identity' or headers.get(b'connection',b'close').lower()!=b'close':raise Stop('protocol')
            length=headers.get(b'content-length',b'')
            if not length.isdigit() or len(length)>10:raise Stop('protocol')
            length=int(length)
            if length>cap:raise Stop('limit')
            if len(body)>length:raise Stop('protocol')
            raw=bytearray(body)
            while len(raw)<length:
                data=receive(length-len(raw))
                if not data:raise Stop('protocol')
                raw.extend(data)
            # Require close to account for trailing bytes; no keepalive ambiguity.
            if receive(1):raise Stop('protocol')
            deadline.left();value=parse_json(bytes(raw));result=project(name,value)
            encoded=bounded_json(result,min(OUTPUT,self.w.plan.get(slot,('',0))[1]))
            deadline.left();self.w.stream(slot,[encoded[i:i+CHUNK] for i in range(0,len(encoded),CHUNK)])
            deadline.left()
            return {'status':'captured','catalog':name,'wire_bytes':wire,'body_bytes':length,'projection':result,
                    'protection_verified':False,'source_start_allowed':False,'retry_b_allowed':False}
        entered=False;close_state='unknown'
        def close_owned():
            nonlocal close_state
            try:sock.close() # ownership ended or uncertain; never retry
            except BaseException as e:
                if not isinstance(e,Exception):self.w.stopped=True
                raise
            close_state='closed'
        def owned():
            nonlocal entered
            entered=True;error=None
            try:return action()
            except BaseException as e:
                error=e
                raise
            finally:
                finish_owned((close_owned,),error)
        try:
            result=self.w.run('capture',owned)
        except BaseException as e:
            # run may reject ownership before invoking the callback (e.g. busy).
            if not entered:finish_owned((close_owned,),e)
            raise
        if not entered:
            try:close_owned()
            except Exception:pass # keep the stopped admission result, mark unknown
            except BaseException:
                self.w.stopped=True
                raise
        result['owned_socket_close']=close_state
        return result

# Only these literal own-fixture children are runnable in this candidate.
# Native production utility argv/handle/schema/cleanup bindings remain UNAVAILABLE.
FIXTURE_SCRIPTS={
 'ok':"import os;os.write(1,b'123\\n');os.write(2,b'fixture\\n')",
 'no-match':"raise SystemExit(1)",
 'error':"raise SystemExit(2)",
 'overflow':"import os;os.write(1,b'x'*100000)",
 'timeout':"import os,time;os.write(1,b'partial');time.sleep(3)"}

def capture_fixture(w,name,stdout_slot,stderr_slot,result_slot,cwd,seconds=.25):
    def action():
        if name not in FIXTURE_SCRIPTS:raise Stop('plan')
        from ledger import directory,inode
        fd=directory(cwd);os.close(fd)
        deadline=Deadline(seconds);out=None;err=None;child=None;selector=selectors.DefaultSelector();result=None
        positions={stdout_slot:0,stderr_slot:0};error=None
        try:
            out=w.new_file(stdout_slot);err=w.new_file(stderr_slot)
            # Explicit clean env; no inherited private settings, handles or argv.
            child=subprocess.Popen([sys.executable,'-I','-S','-B','-c',FIXTURE_SCRIPTS[name]],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                   cwd=cwd,env={'TMPDIR':str(cwd)},close_fds=True,start_new_session=True)
            for stream,slot,dst in ((child.stdout,stdout_slot,out),(child.stderr,stderr_slot,err)):
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,(slot,dst))
            while selector.get_map():
                events=selector.select(deadline.left())
                if not events:raise Stop('deadline')
                for key,_ in events:
                    slot,dst=key.data;maximum=w.plan[slot][1]-positions[slot]
                    raw=os.read(key.fileobj.fileno(),min(CHUNK,maximum+1))
                    if not raw:selector.unregister(key.fileobj);continue
                    if len(raw)>maximum:raise Stop('limit')
                    positions[slot]=w.write(dst,slot,raw,positions[slot])
            try:code=child.wait(timeout=deadline.left())
            except subprocess.TimeoutExpired:raise Stop('deadline')
            classification='success' if code==0 else 'no_match' if code==1 else 'error'
            result={'outcome':classification,'exit_code':code,'stdout_bytes':positions[stdout_slot],'stderr_bytes':positions[stderr_slot]}
            for slot,dst in ((stdout_slot,out),(stderr_slot,err)):
                os.fsync(dst);w.check_file(dst,slot,positions[slot])
        except BaseException as e:
            error=e
            raise
        finally:
            actions=[selector.close]
            if child is not None:
                def stop_child():
                    def kill_running():
                        if child.poll() is None:child.kill()
                    # A kill/poll interruption must not skip the bounded reap.
                    finish_owned((kill_running,lambda:child.wait(timeout=.5)))
                actions.extend((stop_child,child.stdout.close,child.stderr.close))
            for fd in (out,err):
                if fd is not None:actions.append(lambda fd=fd:os.close(fd))
            finish_owned(actions,error)
        raw=bounded_json(result,w.plan[result_slot][1]);w.stream(result_slot,[raw])
        return dict(status='captured',**result,protection_verified=False,source_start_allowed=False,retry_b_allowed=False)
    return w.run('capture',action)
