#!/usr/bin/env python3
"""Deterministic stdlib-only Hermes pipeline reconciler; stable from any cwd."""
import datetime as dt,json,os,re,signal,subprocess,sys,tempfile,time
from pathlib import Path
import validate_contracts as contracts
ROOT=Path(__file__).resolve().parent.parent; PIPE=ROOT/'pipeline'; RUNS=ROOT/'agent_runs'
ACTIVE={'READY','DISPATCHED','RUNNING','AWAITING_REVIEW','REVIEWING','ACCEPTED'}
def now(): return dt.datetime.now(dt.timezone.utc)
def local_timezone(): return dt.datetime.now().astimezone().tzinfo or dt.timezone.utc
def stamp(x=None): return (x or now()).isoformat()
def readj(p):
 with open(p,encoding='utf-8') as f:return json.load(f)
def writej(p,o):
 p.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix=p.name+'.',dir=p.parent)
 with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(o,f,ensure_ascii=False,indent=2);f.write('\n')
 os.replace(tmp,p)
def append(p,o):
 p.parent.mkdir(parents=True,exist_ok=True)
 with open(p,'a',encoding='utf-8') as f:f.write(json.dumps(o,ensure_ascii=False)+'\n')
def dirty_paths():
 """Tracked modified/deleted plus non-ignored untracked paths, safely NUL parsed."""
 try:raw=subprocess.check_output(['git','status','--porcelain=v1','-z','--untracked-files=all'],cwd=ROOT)
 except Exception:return set()
 parts=(raw.decode('utf-8','surrogateescape') if isinstance(raw,bytes) else raw).split('\0');out=set();i=0
 while i<len(parts)-1:
  entry=parts[i];i+=1
  if not entry:continue
  code,path=entry[:2],entry[3:]
  if code[0] in 'RC' or code[1] in 'RC':i+=1 # consume porcelain rename/copy source
  if path:out.add(path)
 return out
def scope_ok(paths):return all(isinstance(p,str) and safe_file(p) for p in paths)
def load_state():
 p=PIPE/'state.json'
 if not p.exists():writej(p,readj(PIPE/'state.example.json'))
 return readj(p)
def save(s):s['updated_at']=stamp();writej(PIPE/'state.json',s)
def stage(s,i):return next((x for x in s['stages'] if x['id']==i),None)
def alive(pid):
 try:os.kill(pid,0);return True
 except OSError:return False
def event(s,e,d,notes):
 append(PIPE/'events.jsonl',{'event_id':e,'ts':stamp(),'detail':d});p=PIPE/'notified.jsonl';seen=set()
 if p.exists():
  for line in p.read_text(encoding='utf-8').splitlines():
   try:seen.add(json.loads(line)['event_id'])
   except (ValueError,KeyError):pass
 if e not in seen:append(p,{'event_id':e,'ts':stamp()});notes.append(d)
def lock():
 p=PIPE/'lock'/'dispatcher.lock';p.parent.mkdir(parents=True,exist_ok=True)
 try:p.mkdir();(p/'info.json').write_text(json.dumps({'pid':os.getpid(),'ts':time.time()}));return p
 except FileExistsError:
  try:i=readj(p/'info.json');stale=not alive(i.get('pid',0)) or time.time()-i.get('ts',0)>1800
  except Exception:stale=True
  if not stale:return None
  try:
   for x in p.iterdir():x.unlink()
   p.rmdir();p.mkdir();(p/'info.json').write_text(json.dumps({'pid':os.getpid(),'ts':time.time()}));return p
  except OSError:return None
def unlock(p):
 try:
  for x in p.iterdir():x.unlink()
  p.rmdir()
 except OSError:pass
def text(p):
 try:return p.read_text(encoding='utf-8',errors='replace')
 except OSError:return ''
def hit(run):return bool(re.search(r'rate.?limit|usage limit|limit reached|overloaded|\b429\b|hit.?limit',text(ROOT/run['log_file']),re.I))
def resume(log,n=0):
 m=re.search(r'resets?(?:\s+at)?\s+(\d{1,2}:\d{2}\s*(?:am|pm))',log,re.I)
 if m:
  t=dt.datetime.strptime(m.group(1).replace(' ',''),'%I:%M%p').time();current=now();local=current.astimezone(local_timezone());x=local.replace(hour=t.hour,minute=t.minute,second=0,microsecond=0)
  return (x+dt.timedelta(days=1 if x<=local else 0,minutes=1)).astimezone(dt.timezone.utc)
 return now()+dt.timedelta(minutes=15)
def rate_limited(s,run,notes):
 rl=s.setdefault('rate_limit',{});pending=rl.get('pending');same=bool(pending and pending.get('stage')==run.get('stage') and pending.get('action')==run.get('action') and rl.get('episode_id'))
 if not same:
  rl['episode_id']=f"{s.get('goal',{}).get('id','goal')}:{run.get('stage') or 'planning'}:{run.get('action')}:{stamp()}";rl['hit_count_today']=rl.get('hit_count_today',0)+1
 retry_at=resume(text(ROOT/run['log_file']))
 run['status']='RATE_LIMITED';run['retry_at']=stamp(retry_at)
 st=stage(s,run.get('stage'))
 if st:st['status']='AWAITING_REVIEW' if run['action']=='review' else 'READY'
 rl.update(active=True,resume_at=stamp(retry_at),pending={'run_id':run['run_id'],'stage':run.get('stage'),'action':run.get('action')})
 event(s,'RATE_LIMIT_EPISODE:'+rl['episode_id'],f"hit limit; retry scheduled for {rl['resume_at']}",notes)
def close_rate_episode(s,run):
 rl=s.get('rate_limit',{});pending=rl.get('pending')
 if pending and pending.get('stage')==run.get('stage') and pending.get('action')==run.get('action'):
  rl.update(active=False,resume_at=None,pending=None,episode_id=None,hit_count_today=0)
def failure(s,run,reason,notes):
 run['status']='FAILED';run['failure']=reason;st=stage(s,run.get('stage'));action=run['action']
 if st is None: # planning is independently capped
  pl=s['planning'];pl['failures']=pl.get('failures',0)+1
  if pl['failures']>=pl.get('max_failures',3):s['goal']['status']='PAUSED';event(s,run['run_id']+':FAILED','planning failed 3 times: '+reason,notes)
  else:event(s,run['run_id']+':retry','planning failed: '+reason,notes)
  return
 if action=='execute':
  actual=dirty_paths()
  if scope_ok(actual):st['worktree_scope']=sorted(actual)
  else:
   st['status']='BLOCKED';s['goal']['status']='PAUSED';event(s,run['run_id']+':UNSAFE_DIRTY','unsafe dirty paths after execute failure: '+', '.join(sorted(actual)),notes);return
 st['attempts'][action]=st['attempts'].get(action,0)+1
 if st['attempts'][action]>=st.get('max_attempts',3):st['status']='FAILED';s['goal']['status']='PAUSED';event(s,run['run_id']+':FAILED',f"{st['id']} {action} failed 3 times: {reason}",notes)
 else:st['status']='AWAITING_REVIEW' if action=='review' else 'READY';event(s,run['run_id']+':retry',f"{st['id']} {action} failed: {reason}",notes)
def render(n,v):
 o=(PIPE/'templates'/n).read_text(encoding='utf-8')
 for k,x in v.items():o=o.replace('{'+k+'}',str(x))
 return o
def command(role,prompt):
 vals={'provider':role['provider'],'model':role['model'],'prompt':prompt};return [str(vals.get(x[1:-1],x)) if x.startswith('{') and x.endswith('}') else x for x in role['argv_template']]
def ordinal(st,action):st.setdefault('dispatch_ordinals',{});st['dispatch_ordinals'][action]=st['dispatch_ordinals'].get(action,0)+1;return st['dispatch_ordinals'][action]
def recent_commits():
 try:return subprocess.check_output(['git','log','--oneline','-5'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
 except Exception:return '(unavailable)'
def reusable_scopes(s,st):
 scopes=[]
 if st.get('worktree_scope') is not None:scopes.append(set(st['worktree_scope']))
 for rid in reversed(st.get('runs',[])):
  r=s['runs'][rid]
  if r.get('role')=='executor' and r.get('action')=='execute' and r.get('status')=='COMPLETED':
   try:
    o=readj(ROOT/r['result_file']);contracts.result_ok(o)
    if o.get('run_id')==r['run_id'] and scope_ok(o['files_changed']):scopes.append(set(o['files_changed']));break
   except Exception:pass
 return scopes
def dispatch(s,roles,name,st=None,action='execute',notes=None):
 notes=[] if notes is None else notes;role=roles[name]
 if name=='executor':
  dirty=dirty_paths();allowed=reusable_scopes(s,st)
  if dirty and set(dirty) not in allowed:
   st['status']='BLOCKED';s['goal']['status']='PAUSED';event(s,st['id']+':DIRTY_GATE','executor blocked by unexpected dirty paths: '+', '.join(sorted(dirty)),notes);return False
 if st: n=ordinal(st,action);rid=f'{st["id"]}.{action}.{n}.{name}'
 else:s['planning']['counter']=s['planning'].get('counter',0)+1;n=s['planning']['counter'];rid=f'plan.{n:03d}.{name}'
 RUNS.mkdir(exist_ok=True);out=RUNS/(rid+('.decision.json' if name=='judge' else '.result.json'));pf=RUNS/(rid+'.prompt.txt');log=RUNS/(rid+'.log')
 last_exec=next((r for r in reversed([s['runs'][x] for x in st.get('runs',[])]) if r['role']=='executor'),None) if st else None
 v={'project_root':str(ROOT),'goal_title':s['goal']['title'],'run_id':rid,'stage_id':st['id'] if st else 'planning','stage_title':st['title'] if st else 'Next-stage planning','executor_brief':st.get('executor_brief','') if st else '','acceptance':json.dumps(st.get('acceptance',[]) if st else s['goal'].get('acceptance',[]),ensure_ascii=False),'inputs':json.dumps(st.get('inputs',[]) if st else [],ensure_ascii=False),'outputs':json.dumps(st.get('outputs',[]) if st else [],ensure_ascii=False),'in_scope':json.dumps(st.get('in_scope',[]) if st else [],ensure_ascii=False),'out_of_scope':json.dumps(st.get('out_of_scope',[]) if st else [],ensure_ascii=False),'required_tests':json.dumps(st.get('required_tests',[]) if st else [],ensure_ascii=False),'allowed_files':json.dumps(st.get('allowed_files',[]) if st else [],ensure_ascii=False),'review_rejections':st.get('review_rejections',0) if st else 0,'max_review_rejections':st.get('max_review_rejections',3) if st else 3,'fix_notes':json.dumps(st.get('fix_notes',[]) if st else [],ensure_ascii=False),'existing_worktree_scope':json.dumps(st.get('worktree_scope',[]) if st else [],ensure_ascii=False),'result_file':str(out),'decision_file':str(out),'committed_stages':json.dumps([x['id'] for x in s['stages'] if x['status']=='COMMITTED']),'goal_acceptance':json.dumps(s['goal'].get('acceptance',[]),ensure_ascii=False),'committed_stage_details':json.dumps([{'id':x['id'],'title':x.get('title',''),'commit':x.get('commit')} for x in s['stages'] if x['status']=='COMMITTED'],ensure_ascii=False),'recent_commits':recent_commits(),'worker_result':text(ROOT/last_exec['result_file']) if last_exec else ''}
 pf.write_text(render('executor.txt' if name=='executor' else ('judge_review.txt' if action=='review' else 'judge_plan.txt'),v),encoding='utf-8')
 run={'run_id':rid,'role':name,'stage':st['id'] if st else None,'action':action,'dispatch_ordinal':n if st else s['planning']['counter'],'status':'DISPATCHED','prompt_file':str(pf.relative_to(ROOT)),'log_file':str(log.relative_to(ROOT)),'result_file':str(out.relative_to(ROOT)),'started_at':stamp(),'deadline_at':stamp(now()+dt.timedelta(minutes=role['timeout_min']))};s['runs'][rid]=run
 if st:st['status']='REVIEWING' if action=='review' else 'DISPATCHED';st.setdefault('runs',[]).append(rid)
 save(s) # durable before spawn
 try:
  with open(log,'wb') as f:p=subprocess.Popen(command(role,pf.read_text(encoding='utf-8')),cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
  run.update(pid=p.pid,handle={'pid':p.pid},status='RUNNING');
  if st:st['status']='RUNNING'
  event(s,rid+':DISPATCHED',f"dispatched {name}({role['model']}) for {st['id'] if st else 'planning'}",notes);save(s) # close crash window
  return True
 except OSError as e:failure(s,run,'spawn failed: '+str(e),notes);save(s);return False
def safe_file(p):
 q=Path(p);return not q.is_absolute() and '..' not in q.parts and not (q.parts and q.parts[0] in ('pipeline','agent_runs'))
def executor_result(s,st):
 for rid in reversed(st.get('runs',[])):
  r=s['runs'][rid]
  if r['role']=='executor' and r['action']=='execute' and r['status']=='COMPLETED':return readj(ROOT/r['result_file'])
 raise ValueError('no completed executor result')
def tracked_path(p):
 try:return bool(subprocess.check_output(['git','ls-files','--',p],cwd=ROOT,text=True).strip())
 except Exception:return False
def validators(st,before=None):
 before=set(before if before is not None else dirty_paths());fake=os.environ.get('PIPELINE_FAKE_VALIDATOR');restored=[]
 if fake:return fake=='pass','fake validator '+fake,restored
 commands=[
  [sys.executable,'pipeline/validate_contracts.py'],
  ['uv','run','--python','3.11','pytest','backend/tests/','-x','-q'],
  ['uv','run','--project','mcp-server','pytest','mcp-server/tests/','-x','-q'],
 ]
 out=[]
 for cmd in commands:
  x=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);out.append('$ '+' '.join(cmd)+'\n'+x.stdout[-2000:])
  after=dirty_paths();new=after-before
  untracked=[p for p in new if not tracked_path(p)]
  if untracked:return False,'validator created untracked paths: '+', '.join(sorted(untracked)),restored
  churn=[p for p in new if tracked_path(p)]
  if churn:
   subprocess.run(['git','restore','--worktree','--source=HEAD','--',*churn],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);restored.extend(churn)
   if dirty_paths()!=before:return False,'validator churn restore did not return to worker scope',restored
  if x.returncode:return False,'\n'.join(out),restored
 return True,'contracts, backend tests and MCP tests passed',restored
def commit(s,st,decision):
 try:files=executor_result(s,st)['files_changed']
 except Exception as e:return False,str(e)
 if not isinstance(files,list) or not scope_ok(files):return False,'unsafe files_changed path'
 if dirty_paths()!=set(files):return False,'commit dirty scope no longer equals executor declaration'
 tracked=set(subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines());deleted=set(subprocess.check_output(['git','ls-files','--deleted'],cwd=ROOT,text=True).splitlines())
 selected=[x for x in files if (ROOT/x).exists() or x in deleted]
 if len(selected)!=len(files):return False,'files_changed contains absent non-deleted path'
 if selected:
  a=subprocess.run(['git','add','--',*selected],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  if a.returncode:return False,a.stdout
  c=subprocess.run(['git','commit','-m',decision.get('commit',{}).get('message',f"{st['id']}: pipeline stage")],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  if c.returncode:return False,c.stdout
  if dirty_paths():return False,'post-commit repository is not clean'
  return True,subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 return True,'no changes'
def valid(run,obj):
 try:
  (contracts.result_ok if run['action']=='execute' else contracts.decision_ok)(obj)
  return obj.get('run_id')==run['run_id']
 except (ValueError,TypeError):return False
def harvest(s,notes):
 for r in list(s['runs'].values()):
  if r['status']=='DISPATCHED':
   age=now()-dt.datetime.fromisoformat(r['started_at'])
   if not r.get('pid') and age>dt.timedelta(seconds=15):failure(s,r,'DISPATCHED spawn recovery',notes)
   continue
  if r['status']!='RUNNING':continue
  if alive(r.get('pid',0)):
   if now()<=dt.datetime.fromisoformat(r['deadline_at']):continue
   try:os.killpg(r['pid'],signal.SIGTERM)
   except OSError:pass
   failure(s,r,'timeout',notes);continue
  try:o=readj(ROOT/r['result_file'])
  except Exception:
   if hit(r):rate_limited(s,r,notes)
   else:failure(s,r,'no parseable machine result',notes)
   continue
  if not valid(r,o):
   if hit(r):rate_limited(s,r,notes)
   else:failure(s,r,'invalid machine result schema',notes)
   continue
  r['status']='COMPLETED';st=stage(s,r.get('stage'));close_rate_episode(s,r)
  if r['action']=='plan':
   if o.get('blocked_reason'):s['goal']['status']='PAUSED';event(s,r['run_id']+':BLOCKED','planning blocked: '+o['blocked_reason'],notes)
   elif o['goal_done']:s['goal']['status']='DONE';event(s,r['run_id']+':DONE',o.get('summary','goal done'),notes)
   elif not o['new_stages']:failure(s,r,'plan has goal_done=false and no new_stages',notes)
   else:
    for ns in o['new_stages']:
     if ns.get('id') and not stage(s,ns['id']):ns.update(status='READY',created_by='run:'+r['run_id'],attempts={'execute':0,'review':0,'validate':0},dispatch_ordinals={},max_attempts=3,max_review_rejections=3,review_rejections=0,deferred_findings=[],fix_notes=[],artifacts=[],runs=[]);s['stages'].append(ns)
    event(s,r['run_id']+':PLANNED',o.get('notify_owner',o.get('summary','planning completed')),notes)
  elif r['action']=='execute':
   declared=set(o['files_changed']);declared.discard(r.get('result_file'))
   actual=dirty_paths()
   if not scope_ok(declared) or actual!=declared:
    failure(s,r,'executor dirty scope mismatch declared='+repr(sorted(declared))+' actual='+repr(sorted(actual)),notes);continue
   st['worktree_scope']=sorted(declared)
   if o['status']=='blocked':st['status']='BLOCKED';s['goal']['status']='PAUSED';event(s,r['run_id']+':BLOCKED',o.get('blocked_reason','executor blocked'),notes)
   else:st['status']='AWAITING_REVIEW';event(s,r['run_id']+':AWAITING_REVIEW',o['summary'],notes)
  else:
   v=o['verdict'];st.setdefault('deferred_findings',[]).extend(o.get('deferred_findings',[]))
   valid_ids={a['id'] for a in st.get('acceptance',[]) if isinstance(a,dict) and a.get('id')};blocking=set(o.get('blocking_criterion_ids',[]));unknown=blocking-valid_ids
   if unknown:
    st['scope_violation']='review cited criteria outside frozen contract: '+', '.join(sorted(unknown));st['status']='BLOCKED';s['goal']['status']='PAUSED';event(s,r['run_id']+':SCOPE_VIOLATION',st['scope_violation'],notes)
   elif v=='accept':st['status']='ACCEPTED';st['review_decision']=o;event(s,r['run_id']+':ACCEPTED',o.get('notify_owner',o['summary']),notes)
   elif v in ('accept_with_fixes','reject'):
    if not blocking:
     st['scope_violation']='reject/accept_with_fixes requires at least one frozen acceptance criterion';st['status']='BLOCKED';s['goal']['status']='PAUSED';event(s,r['run_id']+':SCOPE_VIOLATION',st['scope_violation'],notes)
    else:
     st['review_rejections']=st.get('review_rejections',0)+1;st['fix_notes']=o.get('fixes',[])
     if st['review_rejections']>=st.get('max_review_rejections',3):
      st['status']='BLOCKED';s['goal']['status']='PAUSED';event(s,r['run_id']+':REVIEW_LIMIT',f"{st['id']} reached frozen review rejection limit; owner scope decision required",notes)
     else:st['status']='READY';event(s,r['run_id']+':READY',o.get('notify_owner',o['summary']),notes)
   else:st['status']='BLOCKED';s['goal']['status']='PAUSED';event(s,r['run_id']+':BLOCKED',o.get('blocked_reason','judge blocked'),notes)
def reconcile():
 l=lock()
 if not l:return []
 notes=[]
 try:
  s=load_state();roles=readj(ROOT/s.get('roles_file','pipeline/roles.json'))
  if s['rate_limit'].get('active'):
   pending=s['rate_limit'].get('pending') or {};pending_run=s.get('runs',{}).get(pending.get('run_id'))
   recovered=False
   if pending_run and pending_run.get('status')=='RATE_LIMITED':
    try:recovered=valid(pending_run,readj(ROOT/pending_run['result_file']))
    except Exception:recovered=False
   if recovered:
    pending_run['status']='RUNNING';s['rate_limit']['active']=False
   elif now()<dt.datetime.fromisoformat(s['rate_limit']['resume_at']):return []
   else:
    s['rate_limit']['active']=False
    st=stage(s,pending.get('stage'))
    if st and st.get('status') not in ('COMMITTED','FAILED','BLOCKED'):st['status']='AWAITING_REVIEW' if pending.get('action')=='review' else 'READY'
    s['rate_limit']['last_resumed_at']=stamp()
  if s['goal']['status']!='ACTIVE':save(s);return notes
  harvest(s,notes)
  if s['rate_limit'].get('active'):
   save(s);return notes
  if s['goal']['status']=='ACTIVE':
   for st in s['stages']:
    if st['status']=='ACCEPTED':
     before=dirty_paths();ok,msg,restored=validators(st,before)
     if restored:msg+='; restored validator churn: '+', '.join(sorted(restored))
     if ok:ok,msg=commit(s,st,st.get('review_decision',{}))
     if ok:st['status']='COMMITTED';st['commit']=msg;st.pop('worktree_scope',None);event(s,st['id']+':COMMITTED',f"{st['id']} committed: {msg}",notes)
     else:
      st['attempts']['validate']=st['attempts'].get('validate',0)+1;st['fix_notes'].append('validator/commit: '+msg);st['status']='READY'
      if 'post-commit repository is not clean' in msg:s['goal']['status']='PAUSED';event(s,st['id']+':DIRTY_POST_COMMIT',msg,notes)
      elif st['attempts']['validate']>=st.get('max_attempts',3):st['status']='FAILED';s['goal']['status']='PAUSED';event(s,st['id']+':FAILED','validator failed 3 times',notes)
    if st['status']=='READY' and all((stage(s,x) or {}).get('status')=='COMMITTED' for x in st.get('depends_on',[])):dispatch(s,roles,'executor',st,'execute',notes);break
    if st['status']=='AWAITING_REVIEW':dispatch(s,roles,'judge',st,'review',notes);break
   if not any(x['status'] in ACTIVE for x in s['stages']) and not any(r['status'] in ('DISPATCHED','RUNNING') and r['action']=='plan' for r in s['runs'].values()) and s['planning'].get('failures',0)<s['planning'].get('max_failures',3):dispatch(s,roles,'judge',None,'plan',notes)
  save(s);return notes
 finally:unlock(l)
def main():
 for x in reconcile():print(x)
if __name__=='__main__':main()
