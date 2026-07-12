#!/usr/bin/env python3
"""Read-only health monitor. It never imports or invokes the dispatcher."""
import datetime as dt,json,os,time
from pathlib import Path
ROOT=Path(os.environ.get('PIPELINE_PROJECT_ROOT',Path(__file__).resolve().parent.parent))
STATE=Path(os.environ.get('PIPELINE_STATE_PATH',ROOT/'pipeline/state.json'))
MEM=Path(os.environ.get('PIPELINE_HEALTH_STATE_PATH',Path.home()/'.hermes/state/ai_drawing_civitai_pipeline_health.json'))
def now():
 raw=os.environ.get('PIPELINE_HEALTH_NOW');return dt.datetime.fromisoformat(raw) if raw else dt.datetime.now(dt.timezone.utc)
def alive(pid):
 try:os.kill(int(pid),0);return True
 except OSError:return False
def load(p):
 with open(p,encoding='utf-8') as f:return json.load(f)
def main():
 incidents={}
 if not STATE.exists():incidents['state_missing']='runtime state.json is missing (watchdog will not initialize it)'
 else:
  try:s=load(STATE)
  except Exception as e:incidents['state_unparseable']='state cannot parse: '+str(e)
  else:
   running=[r for r in s.get('runs',{}).values() if r.get('status')=='RUNNING'];healthy_run=any(r.get('pid') and alive(r['pid']) for r in running)
   try:age=now()-dt.datetime.fromisoformat(s['updated_at'])
   except Exception:age=dt.timedelta.max
   if s.get('goal',{}).get('status')=='ACTIVE' and age>dt.timedelta(minutes=45) and not healthy_run:incidents['state_stale']='ACTIVE state older than 45m without live RUNNING handle'
   if age>dt.timedelta(minutes=4):
    for r in running:
     if not r.get('pid') or not alive(r['pid']):incidents['running_pid_lost']='RUNNING handle missing/dead and state older than two 2m cron intervals';break
   lp=ROOT/'pipeline/lock/dispatcher.lock/info.json'
   if lp.exists():
    try:i=load(lp);stale=not alive(i.get('pid',0)) or time.time()-i.get('ts',0)>1800
    except Exception:stale=True
    if stale:incidents['lock_stale']='dispatcher lock is stale'
 try:previous=load(MEM).get('incidents',{})
 except Exception:previous={}
 for k,msg in incidents.items():
  if k not in previous:print('HEALTH INCIDENT:',msg)
 for k in previous:
  if k not in incidents:print('HEALTH RECOVERED:',k)
 MEM.parent.mkdir(parents=True,exist_ok=True);tmp=MEM.with_name(MEM.name+'.tmp');tmp.write_text(json.dumps({'incidents':incidents},ensure_ascii=False));os.replace(tmp,MEM)
if __name__=='__main__':main()
