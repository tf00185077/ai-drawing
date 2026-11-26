"""Budget reset also fails real registered contention, independently of direct entry checks."""
import hashlib,json
from run_checks import ROOT,OUT,run
p=ROOT/'backend/app/services/resource_records.py';original=p.read_bytes()
before=b'remaining = operation.remaining() if operation is not None else 0'
after=b'if operation is not None: operation.deadline = __import__("time").monotonic() + 900\n    '+before
assert original.count(before)==1
record=dict(fault='admission-budget-reset-real-callers',old=before.decode(),new=after.decode(),original_sha256=hashlib.sha256(original).hexdigest())
try:
 mutated=original.replace(before,after);p.write_bytes(mutated);record['mutated_sha256']=hashlib.sha256(mutated).hexdigest()
 record['exit_code']=run('qa3-fault-budget-reset-real-callers',['docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py::test_real_callers_return_before_held_owner_releases','-k','0.12','-s'])
 raw=(OUT/'qa3-fault-budget-reset-real-callers.log').read_text();record['assertion_failures']=raw.count('\nFAILED ')
 assert record['exit_code']==1 and record['assertion_failures']==3 and 'AssertionError' in raw and 'Failed: Timeout' not in raw and 'ERROR collecting' not in raw
finally:
 p.write_bytes(original);assert p.read_bytes()==original;record['restored_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
 (OUT/'supplemental-deadline-fault.json').write_text(json.dumps(record,indent=2)+'\n')
assert run('qa3-complete-final',[
 'docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py',
 'backend/tests/test_civitai_admission_deadline.py',
 'docs/tasks/p2-03-bounded-download/review-2-evidence/deadline_checks.py',
 'docs/tasks/p2-03-bounded-download/review-2-evidence/independent_checks.py',
 'docs/tasks/p2-03-bounded-download/review-evidence/independent_checks.py',
 'backend/tests/test_civitai_download_correction.py',
 'backend/tests/test_civitai_download_bounds.py','backend/tests/test_civitai_download_callers.py',
 'backend/tests/test_civitai_provider.py','-s'])==0
