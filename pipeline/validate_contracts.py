#!/usr/bin/env python3
"""stdlib-only schemas shared by command-line check and dispatcher."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def load(p):
 with open(p,encoding='utf-8') as f:return json.load(f)
def require(o,keys,label):
 if not isinstance(o,dict):raise ValueError(label+' must be object')
 missing=[x for x in keys if x not in o]
 if missing:raise ValueError(label+' missing '+', '.join(missing))
def roles_ok(x):
 require(x,['schema','judge','executor'],'roles')
 if x['schema']!='hermes.roles.v1.1':raise ValueError('unsupported roles schema')
 for n in ('judge','executor'):
  require(x[n],['runner','provider','model','argv_template','timeout_min'],'role '+n)
  if x[n]['runner']!='hermes_cli' or not isinstance(x[n]['argv_template'],list):raise ValueError('invalid role '+n)
def state_ok(x):
 require(x,['schema','goal','stages','runs','rate_limit','planning','updated_at'],'state')
 if x['schema']!='hermes.pipeline.v1.1':raise ValueError('unsupported state schema')
 require(x['goal'],['id','status'],'goal')
 if x['goal']['status'] not in ('ACTIVE','PAUSED','DONE'):raise ValueError('bad goal status')
 if not isinstance(x['stages'],list) or not isinstance(x['runs'],dict):raise ValueError('bad state collections')
 for s in x['stages']:require(s,['id','status','attempts','max_attempts'],'stage')
def decision_ok(x):
 require(x,['schema','run_id','decision_type','summary'],'decision')
 if x['schema']!='hermes.decision.v1.1' or not isinstance(x['run_id'],str):raise ValueError('bad decision identity')
 if x['decision_type']=='plan':
  require(x,['new_stages','goal_done','blocked_reason','needs_from_owner'],'plan decision')
  if not isinstance(x['new_stages'],list) or not isinstance(x['goal_done'],bool):raise ValueError('bad plan fields')
  for s in x['new_stages']:require(s,['id','title','depends_on','kind','acceptance','executor_brief'],'new stage')
 elif x['decision_type']=='review':
  require(x,['stage','verdict','fixes','blocked_reason','needs_from_owner','commit'],'review decision')
  if x['verdict'] not in ('accept','accept_with_fixes','reject','blocked'):raise ValueError('bad verdict')
  if not isinstance(x['fixes'],list) or not isinstance(x['commit'],dict):raise ValueError('bad review fields')
 else:raise ValueError('bad decision_type')
def result_ok(x):
 require(x,['schema','run_id','status','summary','files_changed','how_verified','blocked_reason','notes_for_review'],'result')
 if x['schema']!='hermes.result.v1.1' or x['status'] not in ('done','partial','blocked'):raise ValueError('bad result')
 if not isinstance(x['files_changed'],list) or not all(isinstance(p,str) for p in x['files_changed']):raise ValueError('bad files_changed')
def main():
 try:
  roles_ok(load(ROOT/'pipeline/roles.json'));p=ROOT/'pipeline/state.json';state_ok(load(p if p.exists() else ROOT/'pipeline/state.example.json'))
 except Exception as e:print('INVALID:',e);return 1
 print('OK: roles.json and state.json contracts valid');return 0
if __name__=='__main__':sys.exit(main())
