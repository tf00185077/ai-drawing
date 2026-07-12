import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,call
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dispatch
class P:
 nextpid=100
 def __init__(self,*a,**k):self.pid=P.nextpid;P.nextpid+=1
class DispatchTests(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.TemporaryDirectory();self.root=Path(self.d.name);(self.root/'pipeline/templates').mkdir(parents=True);(self.root/'agent_runs').mkdir();(self.root/'.git').mkdir();self.live=set()
  src=Path(__file__).resolve().parents[1]
  for n in ('executor.txt','judge_plan.txt','judge_review.txt'):(self.root/'pipeline/templates'/n).write_text((src/'templates'/n).read_text())
  (self.root/'pipeline/roles.json').write_text((src/'roles.json').read_text());(self.root/'pipeline/state.example.json').write_text((src/'state.example.json').read_text())
  self.s={'schema':'hermes.pipeline.v1.1','goal':{'id':'g','title':'g','status':'ACTIVE'},'roles_file':'pipeline/roles.json','stages':[],'runs':{},'rate_limit':{'active':False,'resume_at':None,'hit_count_today':0},'planning':{'counter':0,'failures':0,'max_failures':3},'updated_at':'x'};self.put();self.old=(dispatch.ROOT,dispatch.PIPE,dispatch.RUNS);dispatch.ROOT=self.root;dispatch.PIPE=self.root/'pipeline';dispatch.RUNS=self.root/'agent_runs'
 def tearDown(self):dispatch.ROOT,dispatch.PIPE,dispatch.RUNS=self.old;self.d.cleanup()
 def put(self): (self.root/'pipeline/state.json').write_text(json.dumps(self.s))
 def get(self):return json.loads((self.root/'pipeline/state.json').read_text())
 def tick(self):
  with patch('dispatch.subprocess.Popen',P),patch('dispatch.alive',lambda p:p in self.live):return dispatch.reconcile()
 def st(self):return {'id':'X','title':'x','status':'READY','depends_on':[],'contract_version':'1.0','inputs':['committed predecessor'], 'outputs':['tested artifact'],'in_scope':['one bounded change'],'out_of_scope':['future stages'],'acceptance':[{'id':'AC-1','text':'bounded behavior passes'}],'required_tests':['unit test'],'allowed_files':['backend/**'],'attempts':{'execute':0,'review':0,'validate':0},'dispatch_ordinals':{},'max_attempts':3,'max_review_rejections':3,'review_rejections':0,'deferred_findings':[],'fix_notes':[],'runs':[]}
 def dead(self,s,r):r['status']='RUNNING';r['pid']=999;s['runs'][r['run_id']]=r;self.s=s;self.put()
 def result(self,r,status='done'):
  (self.root/r['result_file']).write_text(json.dumps({'schema':'hermes.result.v1.1','run_id':r['run_id'],'status':status,'summary':'ok','files_changed':[],'how_verified':'x','blocked_reason':None,'notes_for_review':'x'}))
 def review(self,r,verdict='reject',criterion_ids=None):
  criterion_ids=['AC-1'] if criterion_ids is None and verdict!='accept' else (criterion_ids or [])
  fixes=[{'criterion_id':x,'instruction':'fix'} for x in criterion_ids]
  (self.root/r['result_file']).write_text(json.dumps({'schema':'hermes.decision.v1.1','run_id':r['run_id'],'decision_type':'review','stage':'X','verdict':verdict,'summary':'no','fixes':fixes,'blocking_criterion_ids':criterion_ids,'deferred_findings':[],'blocked_reason':None,'needs_from_owner':None,'commit':{'message':'x'}}))
 def plan(self,r):
  ns=dict(self.st(),id='Y',title='next',kind='implement',executor_brief='bounded next stage');ns.pop('status');ns.pop('attempts');ns.pop('dispatch_ordinals');ns.pop('max_attempts');ns.pop('max_review_rejections');ns.pop('review_rejections');ns.pop('deferred_findings');ns.pop('fix_notes');ns.pop('runs')
  (self.root/r['result_file']).write_text(json.dumps({'schema':'hermes.decision.v1.1','run_id':r['run_id'],'decision_type':'plan','summary':'planned','new_stages':[ns],'goal_done':False,'blocked_reason':None,'needs_from_owner':None}))
 # retained original cases
 def test_atomic_lock_single_flight(self):a=dispatch.lock();self.assertIsNotNone(a);self.assertIsNone(dispatch.lock());dispatch.unlock(a)
 def test_same_run_and_notification_not_duplicated(self):
  self.tick();r=list(self.get()['runs'].values())[0];self.live.add(r['pid']);self.tick();self.assertEqual(len(self.get()['runs']),1);self.assertEqual(len((self.root/'pipeline/notified.jsonl').read_text().splitlines()),1)
 def test_failure_exactly_three_then_pause(self):
  self.s['stages']=[self.st()];self.put()
  for _ in range(3):self.tick();s=self.get();self.dead(s,list(s['runs'].values())[-1]);self.tick()
  s=self.get();self.assertEqual(s['goal']['status'],'PAUSED');self.assertEqual(s['stages'][0]['attempts']['execute'],3)
 def test_alive_rejects_missing_or_invalid_pid_without_crashing(self):
  self.assertFalse(dispatch.alive(None))
  self.assertFalse(dispatch.alive('not-a-pid'))
 def test_hit_limit_does_not_consume_attempt(self):
  self.s['stages']=[self.st()];self.put();self.tick();s=self.get();r=list(s['runs'].values())[-1];(self.root/r['log_file']).write_text('usage limit resets 11:59pm');self.dead(s,r);self.tick();s=self.get();self.assertEqual(s['stages'][0]['attempts']['execute'],0);self.assertTrue(s['rate_limit']['active'])
 def test_valid_machine_result_wins_over_late_rate_limit_log(self):
  self.tick();s=self.get();r=s['runs']['plan.001.judge'];self.plan(r);(self.root/r['log_file']).write_text('completed decision\nHTTP 429: usage limit reached');self.dead(s,r);self.tick();s=self.get()
  self.assertFalse(s['rate_limit']['active']);self.assertEqual(s['runs'][r['run_id']]['status'],'COMPLETED');self.assertEqual(s['stages'][0]['id'],'Y');self.assertEqual(s['stages'][0]['status'],'RUNNING')
 def test_rate_limited_pending_run_recovers_when_valid_result_exists(self):
  self.tick();s=self.get();r=s['runs']['plan.001.judge'];(self.root/r['log_file']).write_text('HTTP 429: usage limit reached');self.dead(s,r);self.tick();s=self.get();self.assertTrue(s['rate_limit']['active'])
  r=s['runs']['plan.001.judge'];self.plan(r);self.s=s;self.put();self.tick();s=self.get()
  self.assertFalse(s['rate_limit']['active']);self.assertEqual(s['runs'][r['run_id']]['status'],'COMPLETED');self.assertEqual(s['stages'][0]['id'],'Y');self.assertEqual(s['stages'][0]['status'],'RUNNING')
 def test_rate_limit_episode_notifies_once_and_due_tick_dispatches_retry(self):
  self.s['stages']=[self.st()];self.put();t0=dispatch.dt.datetime(2026,7,11,1,0,tzinfo=dispatch.dt.timezone.utc)
  with patch('dispatch.now',return_value=t0):self.tick()
  s=self.get();r1=list(s['runs'].values())[-1];(self.root/r1['log_file']).write_text('HTTP 429: usage limit reached');self.dead(s,r1)
  with patch('dispatch.now',return_value=t0):notes1=self.tick()
  s=self.get();self.assertEqual(r1['run_id'],s['rate_limit']['pending']['run_id']);self.assertEqual(len([x for x in notes1 if 'hit limit' in x]),1)
  due=dispatch.dt.datetime.fromisoformat(s['rate_limit']['resume_at'])+dispatch.dt.timedelta(seconds=1)
  with patch('dispatch.now',return_value=due):notes2=self.tick()
  s=self.get();executors=[r for r in s['runs'].values() if r['role']=='executor'];self.assertEqual(len(executors),2);self.assertEqual(executors[-1]['status'],'RUNNING');self.assertFalse(s['rate_limit']['active']);self.assertEqual(notes2.count(''),0)
  r2=executors[-1];(self.root/r2['log_file']).write_text('HTTP 429: usage limit reached');self.dead(s,r2)
  with patch('dispatch.now',return_value=due):notes3=self.tick()
  self.assertEqual(len([x for x in notes3 if 'hit limit' in x]),0);self.assertEqual(len([json.loads(x) for x in (self.root/'pipeline/notified.jsonl').read_text().splitlines() if 'RATE_LIMIT_EPISODE' in x]),1)
 def test_resume_parses_local_reset_at_plus_one(self):
  utc=dispatch.dt.datetime(2026,7,11,12,0,tzinfo=dispatch.dt.timezone.utc);local=dispatch.dt.timezone(dispatch.dt.timedelta(hours=8))
  with patch('dispatch.now',return_value=utc),patch('dispatch.local_timezone',return_value=local):got=dispatch.resume('usage limit resets at 9:00pm',0)
  self.assertEqual(got,dispatch.dt.datetime(2026,7,11,13,1,tzinfo=dispatch.dt.timezone.utc))
 def test_empty_queue_plans_once(self):
  self.tick();r=list(self.get()['runs'].values())[0];self.live.add(r['pid']);self.tick();self.assertEqual(len(self.get()['runs']),1)
 def test_committed_empty_queue_plans_next_without_hardcode(self):self.s['stages']=[dict(self.st(),id='Z99',status='COMMITTED')];self.put();self.tick();self.assertIn('plan.001.judge',self.get()['runs'])
 def test_role_command_uses_hermes_and_configured_model(self):r=json.loads((self.root/'pipeline/roles.json').read_text())['judge'];c=dispatch.command(r,'hello');self.assertEqual(c[:2],['hermes','chat']);self.assertIn(r['model'],c)
 def test_noop_stdout_empty(self):
  self.s['goal']['status']='PAUSED';self.put();o=io.StringIO()
  with contextlib.redirect_stdout(o):self.tick()
  self.assertEqual(o.getvalue(),'')
 def test_reject_next_execute_has_new_run_id(self):
  self.s['stages']=[self.st()];self.put();self.tick();s=self.get();e1=list(s['runs'].values())[-1];self.result(e1);self.dead(s,e1);self.tick();s=self.get();self.tick();s=self.get();j=list(s['runs'].values())[-1];self.review(j);self.dead(s,j);self.tick();s=self.get();e2=[r for r in s['runs'].values() if r['role']=='executor'][-1];self.live.add(e2['pid']);self.tick();s=self.get();executors=[r for r in s['runs'].values() if r['role']=='executor'];self.assertEqual(len(executors),2);self.assertNotEqual(executors[0]['run_id'],executors[1]['run_id'])
 def test_commit_uses_completed_executor_files_not_judge(self):
  f=self.root/'new.txt';f.write_text('x');st=self.st();st['runs']=['X.execute.1.executor','X.review.1.judge'];s=self.s;s['stages']=[st];s['runs']={'X.execute.1.executor':{'role':'executor','action':'execute','status':'COMPLETED','result_file':'agent_runs/e.result.json'},'X.review.1.judge':{'role':'judge','action':'review','status':'COMPLETED','result_file':'agent_runs/j.decision.json'}};(self.root/'agent_runs/e.result.json').write_text(json.dumps({'files_changed':['new.txt']}))
  with patch('dispatch.dirty_paths',side_effect=[{'new.txt'},set()]),patch('dispatch.subprocess.check_output',side_effect=['','', 'abc']),patch('dispatch.subprocess.run') as run:
   run.return_value=type('R',(),{'returncode':0,'stdout':''})();ok,_=dispatch.commit(s,st,{'commit':{'message':'m'}})
  self.assertTrue(ok);self.assertIn(call(['git','add','--','new.txt'],cwd=self.root,text=True,stdout=-1,stderr=-2),run.call_args_list)
 def test_dispatched_crash_recovers(self):
  self.s['stages']=[self.st()];self.put();self.tick();s=self.get();r=list(s['runs'].values())[-1];r.pop('pid');r['status']='DISPATCHED';r['started_at']='2000-01-01T00:00:00+00:00';self.s=s;self.put();self.tick();s=self.get();self.assertEqual(s['stages'][0]['attempts']['execute'],1);self.assertEqual(s['stages'][0]['status'],'RUNNING')
 def test_first_run_initializes_state_from_example(self):
  (self.root/'pipeline/state.json').unlink();s=dispatch.load_state();self.assertTrue((self.root/'pipeline/state.json').exists());self.assertEqual(s['goal']['id'],'ai-drawing-civitai-recipe-v1')
 def test_invalid_machine_schema_is_retryable_failure(self):
  self.s['stages']=[self.st()];self.put();self.tick();s=self.get();r=list(s['runs'].values())[-1];(self.root/r['result_file']).write_text(json.dumps({'run_id':r['run_id'],'status':'done'}));self.dead(s,r);self.tick();s=self.get();self.assertEqual(s['stages'][0]['attempts']['execute'],1)
 def test_dirty_gate_blocks_executor_once_but_clean_allows(self):
  st=self.st();roles=json.loads((self.root/'pipeline/roles.json').read_text())
  with patch('dispatch.dirty_paths',return_value={'Other.cs'}),patch('dispatch.subprocess.Popen') as spawn:dispatch.dispatch(self.s,roles,'executor',st,notes=[]);spawn.assert_not_called()
  self.assertEqual(self.s['goal']['status'],'PAUSED');self.s['goal']['status']='ACTIVE';st['status']='READY'
  with patch('dispatch.dirty_paths',return_value=set()),patch('dispatch.subprocess.Popen',P):self.assertTrue(dispatch.dispatch(self.s,roles,'executor',st,notes=[]))
 def test_executor_scope_mismatch_does_not_enter_review(self):
  st=self.st();self.s['stages']=[st];r={'run_id':'X.execute.1.executor','role':'executor','stage':'X','action':'execute','status':'RUNNING','pid':999,'result_file':'agent_runs/x.result.json','log_file':'agent_runs/x.log'};self.s['runs'][r['run_id']]=r;st['runs']=[r['run_id']];self.result(r);self.result(r);data=json.loads((self.root/r['result_file']).read_text());data['files_changed']=['declared.cs'];(self.root/r['result_file']).write_text(json.dumps(data))
  with patch('dispatch.alive',return_value=False),patch('dispatch.dirty_paths',return_value={'actual.cs'}):dispatch.harvest(self.s,[])
  self.assertEqual(st['status'],'READY');self.assertEqual(st['attempts']['execute'],1)
 def test_executor_scope_ignores_only_its_own_machine_result_file(self):
  st=self.st();self.s['stages']=[st];r={'run_id':'X.execute.1.executor','role':'executor','stage':'X','action':'execute','status':'RUNNING','pid':999,'result_file':'agent_runs/x.result.json','log_file':'agent_runs/x.log'};self.s['runs'][r['run_id']]=r;st['runs']=[r['run_id']];self.result(r);data=json.loads((self.root/r['result_file']).read_text());data['files_changed']=['Assets/actual.cs',r['result_file']];(self.root/r['result_file']).write_text(json.dumps(data))
  with patch('dispatch.alive',return_value=False),patch('dispatch.dirty_paths',return_value={'backend/app/example.py'}):
   data=json.loads((self.root/r['result_file']).read_text());data['files_changed']=['backend/app/example.py',r['result_file']];(self.root/r['result_file']).write_text(json.dumps(data));dispatch.harvest(self.s,[])
  self.assertEqual(st['status'],'AWAITING_REVIEW');self.assertEqual(st['worktree_scope'],['backend/app/example.py']);self.assertEqual(st['attempts']['execute'],0)
 def test_executor_scope_accepts_ignored_evidence_separate_from_git_dirty(self):
  st=self.st();st['allowed_files'].append('agent_runs/X.*');self.s['stages']=[st];r={'run_id':'X.execute.1.executor','role':'executor','stage':'X','action':'execute','status':'RUNNING','pid':999,'result_file':'agent_runs/x.result.json','log_file':'agent_runs/x.log'};self.s['runs'][r['run_id']]=r;st['runs']=[r['run_id']];self.result(r);e='agent_runs/X.evidence.json';(self.root/e).write_text('{}');data=json.loads((self.root/r['result_file']).read_text());data['files_changed']=['backend/app/example.py'];data['evidence_files']=[e,str(self.root/r['result_file'])];(self.root/r['result_file']).write_text(json.dumps(data))
  with patch('dispatch.alive',return_value=False),patch('dispatch.dirty_paths',return_value={'backend/app/example.py'}):dispatch.harvest(self.s,[])
  self.assertEqual(st['status'],'AWAITING_REVIEW');self.assertEqual(st['worktree_scope'],['backend/app/example.py'])
 def test_executor_scope_rejects_missing_or_unsafe_evidence(self):
  for evidence in (['agent_runs/missing.json'],['agent_runs/../pipeline/state.json']):
   st=self.st();st['allowed_files'].append('agent_runs/X.*');self.s['stages']=[st];r={'run_id':'X.execute.1.executor','role':'executor','stage':'X','action':'execute','status':'RUNNING','pid':999,'result_file':'agent_runs/x.result.json','log_file':'agent_runs/x.log'};self.s['runs']={r['run_id']:r};st['runs']=[r['run_id']];self.result(r);data=json.loads((self.root/r['result_file']).read_text());data['evidence_files']=evidence;(self.root/r['result_file']).write_text(json.dumps(data))
   with patch('dispatch.alive',return_value=False),patch('dispatch.dirty_paths',return_value=set()):dispatch.harvest(self.s,[])
   self.assertEqual(r['status'],'FAILED')
 def test_executor_scope_legacy_agent_run_evidence_is_not_git_dirty(self):
  st=self.st();st['allowed_files'].append('agent_runs/X.*');self.s['stages']=[st];r={'run_id':'X.execute.1.executor','role':'executor','stage':'X','action':'execute','status':'RUNNING','pid':999,'result_file':'agent_runs/x.result.json','log_file':'agent_runs/x.log'};self.s['runs'][r['run_id']]=r;st['runs']=[r['run_id']];self.result(r);e='agent_runs/X.evidence.json';(self.root/e).write_text('{}');data=json.loads((self.root/r['result_file']).read_text());data['files_changed']=['backend/app/example.py',e,r['result_file']];(self.root/r['result_file']).write_text(json.dumps(data))
  with patch('dispatch.alive',return_value=False),patch('dispatch.dirty_paths',return_value={'backend/app/example.py'}):dispatch.harvest(self.s,[])
  self.assertEqual(st['status'],'AWAITING_REVIEW')
 def test_validator_tracked_churn_restores_only_new_path(self):
  st=self.st();ok,msg,restored=None,None,None
  with patch('dispatch.subprocess.run',return_value=type('R',(),{'returncode':0,'stdout':''})()) as run,patch('dispatch.dirty_paths',side_effect=[{'worker.cs','churn.cs'},{'worker.cs'}, {'worker.cs'}, {'worker.cs'}, {'worker.cs'}]),patch('dispatch.tracked_path',return_value=True):ok,msg,restored=dispatch.validators(st,{'worker.cs'})
  self.assertTrue(ok);self.assertEqual(restored,['churn.cs']);self.assertIn(call(['git','restore','--worktree','--source=HEAD','--','churn.cs'],cwd=self.root,text=True,stdout=-1,stderr=-2),run.call_args_list)
 def test_validator_untracked_churn_fails_without_restore(self):
  with patch('dispatch.subprocess.run',return_value=type('R',(),{'returncode':0,'stdout':''})()) as run,patch('dispatch.dirty_paths',return_value={'worker.cs','new.tmp'}),patch('dispatch.tracked_path',return_value=False):ok,msg,_=dispatch.validators(self.st(),{'worker.cs'})
  self.assertFalse(ok);self.assertIn('untracked',msg);self.assertFalse(any(c.args[0][1]=='restore' for c in run.call_args_list))
 def test_commit_postcondition_requires_clean_repo(self):
  f=self.root/'worker.cs';f.write_text('x');st=self.st();st['runs']=['e'];self.s['runs']={'e':{'role':'executor','action':'execute','status':'COMPLETED','result_file':'agent_runs/e.json'}};(self.root/'agent_runs/e.json').write_text(json.dumps({'files_changed':['worker.cs']}))
  with patch('dispatch.dirty_paths',side_effect=[{'worker.cs'},{'leftover.cs'}]),patch('dispatch.subprocess.check_output',side_effect=['','', 'hash']),patch('dispatch.subprocess.run',return_value=type('R',(),{'returncode':0,'stdout':''})()):ok,msg=dispatch.commit(self.s,st,{})
  self.assertFalse(ok);self.assertIn('not clean',msg)
 def test_failed_execute_safe_partial_scope_can_retry(self):
  st=self.st();self.s['stages']=[st];r={'run_id':'X.execute.1.executor','stage':'X','action':'execute','status':'RUNNING'}
  with patch('dispatch.dirty_paths',return_value={'Assets/partial.cs'}):dispatch.failure(self.s,r,'crash',[])
  self.assertEqual(st['worktree_scope'],['Assets/partial.cs']);roles=json.loads((self.root/'pipeline/roles.json').read_text())
  with patch('dispatch.dirty_paths',return_value={'Assets/partial.cs'}),patch('dispatch.subprocess.Popen',P):self.assertTrue(dispatch.dispatch(self.s,roles,'executor',st,notes=[]))
 def test_reject_scope_allows_retry_but_extra_path_blocks(self):
  st=self.st();st['worktree_scope']=['Assets/worker.cs'];roles=json.loads((self.root/'pipeline/roles.json').read_text())
  with patch('dispatch.dirty_paths',return_value={'Assets/worker.cs'}),patch('dispatch.subprocess.Popen',P):self.assertTrue(dispatch.dispatch(self.s,roles,'executor',st,notes=[]))
  st['status']='READY';self.s['goal']['status']='ACTIVE'
  with patch('dispatch.dirty_paths',return_value={'Assets/worker.cs','Assets/unexpected.cs'}),patch('dispatch.subprocess.Popen') as spawn:dispatch.dispatch(self.s,roles,'executor',st,notes=[]);spawn.assert_not_called()
  self.assertEqual(self.s['goal']['status'],'PAUSED')
 def test_planning_failure_caps_at_three(self):
  for _ in range(3):self.tick();s=self.get();r=list(s['runs'].values())[-1];self.dead(s,r);self.tick()
  self.assertEqual(self.get()['goal']['status'],'PAUSED');self.assertEqual(self.get()['planning']['failures'],3)
 def test_plan_requires_frozen_stage_contract(self):
  decision={'schema':'hermes.decision.v1.1','run_id':'plan.1','decision_type':'plan','summary':'x','new_stages':[{'id':'CIV-B','title':'b','depends_on':['CIV-A'],'kind':'implement','acceptance':['vague'],'executor_brief':'x'}],'goal_done':False,'blocked_reason':None,'needs_from_owner':None}
  with self.assertRaisesRegex(ValueError,'frozen contract'):dispatch.contracts.decision_ok(decision)
 def test_review_unknown_criterion_pauses_instead_of_expanding_scope(self):
  st=self.st();self.s['stages']=[st];r={'run_id':'X.review.1.judge','role':'judge','stage':'X','action':'review','status':'RUNNING','pid':999,'result_file':'agent_runs/j.json','log_file':'agent_runs/j.log'};self.s['runs'][r['run_id']]=r;st['runs']=[r['run_id']];self.review(r,'reject',['NEW-99'])
  with patch('dispatch.alive',return_value=False):dispatch.harvest(self.s,[])
  self.assertEqual(self.s['goal']['status'],'PAUSED');self.assertEqual(st['status'],'BLOCKED');self.assertIn('NEW-99',st['scope_violation'])
 def test_third_review_rejection_pauses_without_fourth_execute(self):
  st=self.st();st['review_rejections']=2;self.s['stages']=[st];r={'run_id':'X.review.3.judge','role':'judge','stage':'X','action':'review','status':'RUNNING','pid':999,'result_file':'agent_runs/j3.json','log_file':'agent_runs/j3.log'};self.s['runs'][r['run_id']]=r;st['runs']=[r['run_id']];self.review(r,'reject',['AC-1'])
  with patch('dispatch.alive',return_value=False):dispatch.harvest(self.s,[])
  self.assertEqual(self.s['goal']['status'],'PAUSED');self.assertEqual(st['status'],'BLOCKED');self.assertEqual(st['review_rejections'],3)
if __name__=='__main__':unittest.main()
