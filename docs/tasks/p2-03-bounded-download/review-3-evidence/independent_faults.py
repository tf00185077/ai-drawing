"""QA3 independent replay: fourteen sequential production faults and exact restoration.

Run sequentially, with no other tests active in this worktree.
"""
import hashlib
import json
import subprocess
from run_checks import ROOT, OUT, run

HELPER='backend/app/services/civitai_safe_download.py'
INSTALL='backend/app/services/civitai_resource_install.py'
ACQUIRE='backend/app/services/civitai_resource_acquire.py'
RECORDS='backend/app/services/resource_records.py'
OLD='docs/tasks/p2-03-bounded-download/review-evidence/independent_checks.py'
NEW='docs/tasks/p2-03-bounded-download/review-2-evidence/independent_checks.py'
originals={p:(ROOT/p).read_bytes() for p in (HELPER,INSTALL,ACQUIRE,RECORDS,'backend/app/services/civitai_download_policy.py')}


def digest(body): return hashlib.sha256(body).hexdigest()


def restored():
    assert all((ROOT/p).read_bytes()==body for p,body in originals.items())


def assertion_red(label, selectors):
    code=run(label,selectors+['-s'])
    raw=(OUT/(label+'.log')).read_text()
    assert code==1 and 'AssertionError' in raw
    assert 'ERROR collecting' not in raw and 'Failed: Timeout' not in raw
    return {'exit_code':code,'assertion_failures':raw.count('\nFAILED '),
            'log_sha256':digest((OUT/(label+'.log')).read_bytes())}


audit=[]

faults=[
    ('current-publication',INSTALL,'current.status = "failed"','current.status = "installed"',
        NEW+'::test_committed_adoption_reports_actual_current_reason_and_keeps_history'),
    ('current-reason',INSTALL,'diagnostic = exc.to_dict() if isinstance(exc, CivitaiProviderError) else {"code": "ledger_persistence_failed"}',
        'diagnostic = {"code": "ledger_persistence_failed"}',
        NEW+'::test_committed_adoption_reports_actual_current_reason_and_keeps_history'),
    ('active-admission',INSTALL,'if row is not None and row.status == "downloading":','if False:',
        NEW+'::test_late_owner_claim_during_preflight_is_rechecked_at_admission'),
    ('byte',HELPER,'if total + len(chunk) > min(metadata.size, policy.max_bytes):','if False:',
        OLD+'::test_independent_byte_guard_observes_refusal_before_write'),
    ('space',HELPER,'if free - write_bytes < policy.free_space_floor_bytes:','if False:',
        OLD+'::test_independent_space_guard_tracks_destination_and_every_write'),
    ('range',HELPER,'if (match is None or tuple(map(int, match.groups())) != (offset, metadata.size - 1, metadata.size)\n                    or offset >= metadata.size):','if False:',
        OLD+'::test_independent_range_guard_retains_owned_prefix'),
    ('publication',HELPER,'os.link(part, target, follow_symlinks=False)','os.replace(part, target)',
        OLD+'::test_independent_publication_collision_guard'),
    ('verification',HELPER,'if total != metadata.size or actual_sha.lower() != metadata.sha256.lower():','if False:',
        OLD+'::test_independent_size_hash_guard'),
]
faults += [
    ('selected-size','backend/app/services/civitai_download_policy.py',
     'if size > self.max_bytes:', 'if False:',
     OLD+'::test_independent_registered_admission_without_side_effects'),
    ('post-commit-deadline',INSTALL,
     'db.commit()\n    if operation is not None: operation.remaining()\n    if identity is not None',
     'db.commit()\n    if identity is not None',
     NEW+'::test_committed_adoption_reports_actual_current_reason_and_keeps_history'),
    ('admission-wait',RECORDS,
     'if not resource_admission.acquire(timeout=remaining):',
     'if not resource_admission.acquire():',
     'docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py::test_real_callers_return_before_held_owner_releases'),
    ('admission-budget-reset',RECORDS,
     'remaining = operation.remaining() if operation is not None else 0',
     'if operation is not None: operation.deadline = __import__("time").monotonic() + 900\n    remaining = operation.remaining() if operation is not None else 0',
     'docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py::test_real_operation_entry_boundaries_balance_lock'),
]

faults += [
    ('entry-deadline', RECORDS,
     'if operation is not None:\n            operation.remaining()\n        yield',
     'yield',
     'docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py::test_real_operation_entry_boundaries_balance_lock'),
    ('foreign-preservation', ACQUIRE,
     'roots = _storage_roots(settings)\n        adoptions = {}',
     'roots = _storage_roots(settings)\n        foreign = roots["loras"] / components[0][0]["name"]\n        if foreign.exists(): foreign.write_bytes(b"corrupted foreign bytes")\n        adoptions = {}',
     'backend/tests/test_civitai_download_callers.py::test_acquisition_retains_known_storage_when_configured_root_changes'),
]
for name,path,old,new,guard in faults:
    restored(); original=originals[path]
    assert original.count(old.encode())==1,name
    mutated=original.replace(old.encode(),new.encode())
    item={'fault':name,'source':path,'old':old,'new':new,'guard':guard,
          'original_sha256':digest(original),'mutated_sha256':digest(mutated)}
    try:
        (ROOT/path).write_bytes(mutated)
        item.update(assertion_red('qa3-fault-'+name,[guard]))
    finally:
        (ROOT/path).write_bytes(original);restored()
        item['restored_sha256']=digest((ROOT/path).read_bytes())
        audit.append(item)
        (OUT/'final-fault-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
assert run('qa3-complete-features',[
    'docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py',
    'backend/tests/test_civitai_admission_deadline.py',
    'docs/tasks/p2-03-bounded-download/review-2-evidence/deadline_checks.py',
    NEW,OLD,'backend/tests/test_civitai_download_correction.py',
    'backend/tests/test_civitai_download_bounds.py','backend/tests/test_civitai_download_callers.py',
    'backend/tests/test_civitai_provider.py','-s'])==0
restored()
