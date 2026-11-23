"""Independent synthetic QA. No product imports, discovery execution or live I/O."""
import sys
sys.dont_write_bytecode=True
import pathlib,os,ast,json,hashlib,types,unittest
from fractions import Fraction
ROOT=pathlib.Path(sys.argv[1]).resolve()
QA_SOURCE=pathlib.Path(__file__).resolve()
DENIED=[]
def guard(event,args):
 if event=='open':
  path,mode,flags=args
  if not isinstance(path,(str,bytes)) or not (pathlib.Path(os.fsdecode(path)).resolve().is_relative_to(ROOT) or pathlib.Path(os.fsdecode(path)).resolve()==QA_SOURCE):
   DENIED.append(event);raise PermissionError('QA bundle-only reads')
  if flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) or (isinstance(mode,str) and any(c in mode for c in 'wax+')):
   DENIED.append(event);raise PermissionError('QA no writes')
 if event=='import' and args[0].split('.')[0] in {'app','bot','mcp_server','sqlite3','http','socket','subprocess','ctypes'}:
  DENIED.append(event);raise PermissionError('QA product/runtime import denied')
 if event.startswith(('socket.','subprocess.','os.exec','os.spawn')) or event in {'os.system','os.remove','os.rename','os.mkdir','os.rmdir','os.link','os.symlink','os.chmod','os.truncate','os.chdir'}:
  DENIED.append(event);raise PermissionError('QA runtime/mutation denied')
sys.addaudithook(guard)
# Denial probes are synthetic audit events: no actual product/private access occurs.
for event,args in [('open',('/__qa_excluded__/state','r',0)),('open',(str(ROOT/'not-created'),'w',os.O_CREAT)),('import',('app',None,None,None,None)),('import',('sqlite3',None,None,None,None)),('socket.connect',(None,None)),('subprocess.Popen',(None,None,None,None)),('os.remove',('synthetic',-1))]:
 try:sys.audit(event,*args)
 except PermissionError:pass
 else:raise AssertionError('pre-import guard failed')
source=(ROOT/'method.py').read_bytes();tree=ast.parse(source)
assert not any(isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.walk(tree))
m=types.ModuleType('qa_frozen_method');exec(compile(source,str(ROOT/'method.py'),'exec'),m.__dict__)

def bound(n,basis='derived',evidence='synthetic-independent-proof'):return dict(bytes=n,basis=basis,evidence=evidence)
def terms(p=13,db=31,ds=7,control=5):return dict(P=bound(p),D_B=bound(db),D_S=bound(ds),M=bound(control))
def alloc(pool='one',b=100,h=7,u=3):return dict(pool=pool,B=bound(b),H=bound(h),U=bound(u))
def fact(field='root',value='opaque-A',**changes):
 return dict(field=field,value=value,kind='loaded_snapshot',process='hostA:pid17:start100',epoch='E',complete=True,evidence='synthetic-private-custody',**changes)
def bind(facts,required=('root',),process='hostA:pid17:start100',epoch='E'):
 return m.binding(required,facts,process=process,epoch=epoch)

class Independent(unittest.TestCase):
 def test_discovery_exits_signals_and_empty_output(self):
  expected={0:'invalid_output',1:'no_match',2:'error',3:'error',127:'error',-9:'error',None:'error'}
  for code,state in expected.items():self.assertEqual(m.discovery(code,'')['state'],state)
  self.assertEqual(m.discovery(1,'17')['state'],'invalid_output')
 def test_discovery_success_strict_positive_unique_ascii_pids(self):
  self.assertEqual(m.discovery(0,'17\n18\n')['pids'],[17,18])
  for output in ['0','-1','17\n17','pid17','١٧','１７','17x']:
   self.assertEqual(m.discovery(0,output)['state'],'invalid_output')
 def test_timeout_wins_even_over_apparent_match_or_no_match(self):
  for code,output in [(0,'17'),(1,''),(2,'')]:self.assertEqual(m.discovery(code,output,timed_out=True)['state'],'timeout')
 def test_safe_error_metadata_no_stdout_or_stderr_text_leak(self):
  for present in [None,False,True]:
   r=m.discovery(2,'synthetic-private-argv',stderr_present=present)
   self.assertEqual(r,dict(state='error',pids=None,exit=2,stderr_present=present,cause='unknown'))
 def test_discovery_rejects_malformed_types(self):
  for args,kw in [((True,''),{}),((0,b'17'),{}),((0,''),dict(timed_out=1)),((0,''),dict(stderr_present='secret'))]:
   with self.assertRaises(ValueError):m.discovery(*args,**kw)
 def test_protection_distinct_names_overlap_and_links(self):
  a=dict(id='a',kind='file',bytes=200);b=dict(id='b',kind='file',bytes=200);l=dict(id='link',kind='link',bytes=9,target='a')
  self.assertEqual(m.protection([a,a.copy(),b,l],complete=True)['bytes'],409)
 def test_protection_incomplete_set_cannot_certify(self):
  for entries in [[],[dict(id='a',kind='file',bytes=200)]]:self.assertIsNone(m.protection(entries,complete=False)['bytes'])
 def test_protection_missing_and_cyclic_targets_unknown(self):
  for entries in [[dict(id='l',kind='link',bytes=1,target='missing')],[dict(id='l',kind='link',bytes=1,target='l')],[dict(id='l',kind='link',bytes=1,target='r'),dict(id='r',kind='link',bytes=1,target='l')]]:
   self.assertIsNone(m.protection(entries,complete=True)['bytes'])
 def test_protection_conflicts_and_numeric_errors_reject(self):
  with self.assertRaises(ValueError):m.protection([dict(id='a',kind='file',bytes=1),dict(id='a',kind='file',bytes=2)],complete=True)
  for n in [True,-1,2.0,'2']:
   with self.assertRaises(ValueError):m.protection([dict(id='a',kind='file',bytes=n)],complete=True)
 def test_logical_full_copies_at_boundary_and_one_byte_over(self):
  # Independently expanded: two 13-byte protections + full post DB31 + post-start7 + controls5 =69.
  for cap,state in [(69,'conditional_fit'),(68,'exceeds')]:
   r=m.capacity(terms(),[alloc()],{'one':132},cap=cap);self.assertEqual(r['logical_bytes'],69);self.assertEqual(r['state'],state);self.assertIs(r['runtime_acceptance'],False)
 def test_integer_physical_thresholds_against_rational_oracle(self):
  for n in list(range(401))+[2**53+1,2**64+1]:
   f=Fraction(6*n,5);ceil=-(-f.numerator//f.denominator)
   for available,state in [(ceil,'conditional_fit'),(ceil-1,'exceeds')] if ceil else [(0,'conditional_fit')]:
    r=m.capacity(terms(),[alloc(b=n,h=0,u=0)],{'one':available},cap=69)
    self.assertEqual(r['pools']['one']['threshold'],ceil);self.assertEqual(r['state'],state)
 def test_shared_pool_free_counted_once(self):
  r=m.capacity(terms(),[alloc(),alloc()],{'one':200},cap=69)
  self.assertEqual(r['pools']['one']['allocation'],220);self.assertEqual(r['pools']['one']['threshold'],264);self.assertEqual(r['state'],'exceeds')
 def test_distinct_pools_cannot_cover_each_other(self):
  r=m.capacity(terms(),[alloc('a'),alloc('b')],{'a':1000000,'b':131},cap=69)
  self.assertEqual(r['state'],'exceeds');self.assertIs(r['pools']['b']['fits'],False)
 def test_every_missing_logical_term_prevents_fit(self):
  for k in terms():
   t=terms();t[k]=None;r=m.capacity(t,[alloc()],{'one':132},cap=69)
   self.assertEqual(r['state'],'unknown');self.assertIn(k,r['missing'])
 def test_guesses_page_rounding_named_only_do_not_become_bounds(self):
  for basis in ['named_only','page_rounded','estimate','unknown']:
   t=terms();t['P']=bound(13,basis);r=m.capacity(t,[alloc()],{'one':132},cap=69)
   self.assertEqual(r['state'],'unknown')
 def test_no_physical_rows_or_free_and_each_missing_overhead_prevent_fit(self):
  self.assertEqual(m.capacity(terms(),[],{},cap=69)['state'],'unknown')
  self.assertEqual(m.capacity(terms(),[alloc()],{},cap=69)['state'],'unknown')
  for key in ['B','H','U']:
   a=alloc();a[key]=None;r=m.capacity(terms(),[a],{'one':1000000},cap=69);self.assertEqual(r['state'],'unknown')
 def test_bad_numeric_or_missing_proof_locator_prevent_fit(self):
  for n in [True,-1,1.1,'1']:
   with self.assertRaises(ValueError):m.capacity(terms(p=n),[alloc()],{'one':132},cap=69)
  for evidence in ['', '   ',None]:
   t=terms();t['P']=bound(13,evidence=evidence);self.assertEqual(m.capacity(t,[alloc()],{'one':132},cap=69)['state'],'unknown')
 def test_independent_known_physical_exceed_survives_unknown_logical(self):
  t=terms();t['D_B']=None;self.assertEqual(m.capacity(t,[alloc()],{'one':131},cap=69)['state'],'exceeds')
 def test_documented_known_logical_exceed_with_unknown_later_term(self):
  t=terms(p=100);t['D_B']=None;r=m.capacity(t,[alloc(b=0,h=0,u=0)],{'one':0},cap=199)
  self.assertEqual(r['state'],'exceeds',r) # 2P alone=200 >199, regardless of unknown nonnegative D_B.
 def test_documented_known_payload_exceed_with_unknown_overhead(self):
  a=alloc(b=100,h=0,u=0);a['H']=None;r=m.capacity(terms(),[a],{'one':119},cap=69)
  self.assertEqual(r['state'],'exceeds',r) # ceil(1.2*100)=120 >119 even with unknown nonnegative H.
 def test_sqlite_full_later_ceiling_includes_companions(self):
  self.assertEqual(m.sqlite_post_bound(8192,4,dict(pages=12,basis='enforced_limit',evidence='cap'),bound(900)),99204)
 def test_sqlite_missing_enforcement_or_companions_never_uses_current_size(self):
  for limit,extra in [(None,bound(0)),(dict(pages=12,basis='estimate',evidence='cap'),bound(0)),(dict(pages=12,basis='enforced_limit',evidence='cap'),None)]:
   self.assertIsNone(m.sqlite_post_bound(8192,4,limit,extra))
 def test_sqlite_bad_page_size_or_cap_reject(self):
  for size in [0,511,1000,65537,True]:
   with self.assertRaises(ValueError):m.sqlite_post_bound(size,4,None,None)
  for pages in [0,3,True,-1]:
   with self.assertRaises(ValueError):m.sqlite_post_bound(8192,4,dict(pages=pages,basis='enforced_limit',evidence='cap'),bound(0))
 def test_binding_requires_all_domains_and_never_accepts_runtime(self):
  r=bind([fact()],required=('root','companions','client'));self.assertEqual(r['missing'],['companions','client']);self.assertEqual(r['state'],'unknown');self.assertIs(r['runtime_acceptance'],False)
  r=bind([fact(),fact('companions'),fact('client')],required=('root','companions','client'));self.assertEqual(r['state'],'conditional_complete');self.assertIs(r['runtime_acceptance'],False)
 def test_binding_reused_pid_other_host_start_or_epoch_do_not_certify(self):
  for process,epoch in [('hostB:pid17:start100','E'),('hostA:pid17:start101','E'),('hostA:pid17:start100','E2')]:self.assertEqual(bind([fact()],process=process,epoch=epoch)['state'],'unknown')
 def test_binding_defaults_current_file_fd_argv_not_loaded(self):
  for kind in ['source_default','current_file','open_fd','argv','cwd']:
   f=fact();f['kind']=kind;self.assertEqual(bind([f])['state'],'unknown')
 def test_binding_conflicting_value_or_incomplete_evidence_unknown(self):
  self.assertEqual(bind([fact(),fact(value='opaque-B')])['state'],'unknown')
  for key,value in [('complete',False),('complete',1),('evidence',''),('value','')]:
   f=fact();f[key]=value;self.assertEqual(bind([f])['state'],'unknown')
 def test_control_exact_bytes_boundary_and_missing_aggregate_ledger(self):
  self.assertEqual(m.bounded_control(b'12',2),b'12')
  for payload in [b'123','12',bytearray(b'12')]:
   with self.assertRaises(ValueError):m.bounded_control(payload,2)
  # Two calls do not share a ledger; this is the documented limitation, no aggregate-cap claim.
  self.assertEqual(len(m.bounded_control(b'12',2))+len(m.bounded_control(b'12',2)),4)

suite=unittest.defaultTestLoader.loadTestsFromTestCase(Independent)
result=unittest.TextTestRunner(verbosity=2).run(suite)
print('QA_SUMMARY='+json.dumps(dict(tests=result.testsRun,failures=[t.id().split('.')[-1] for t,_ in result.failures],errors=[t.id().split('.')[-1] for t,_ in result.errors],guard_denials=len(DENIED),candidate_method_sha256=hashlib.sha256(source).hexdigest(),runtime_acceptance=False),sort_keys=True))
sys.exit(0 if result.wasSuccessful() else 1)
