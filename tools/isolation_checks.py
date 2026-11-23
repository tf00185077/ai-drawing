"""Fresh-process bootstrap negative controls and original-test collection."""
import json, os, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
S=Path(os.environ['PAPERCLIP_SCRATCH_DIR'])
PYTHON='/Users/tf00185088/Desktop/tim-project/.ai-drawing-prepared-environments/7796fed8-398a-4d7c-b777-6e273514a5ce/backend-venv/bin/python'
BASE={'PATH':'/usr/bin:/bin','TMPDIR':str(S),'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PYTHONDONTWRITEBYTECODE':'1','DATABASE_URL':'sqlite:////private/PRODUCTION_SENTINEL.db'}
results=[]
def run(name,root,source=ROOT,args=('--collect-only','backend/tests/test_lora_trainer.py','-q')):
    env=dict(BASE)
    if root is not None:env['AI_DRAWING_TEST_ROOT']=str(root)
    cmd=[PYTHON,'-I','-S','-B',str(source/'tools/offline_pytest.py'),*args]
    r=subprocess.run(cmd,env=env,capture_output=True,text=True)
    (S/'evidence'/f'fresh-{name}.log').write_text(r.stdout+r.stderr)
    results.append({'name':name,'argv':cmd,'env':env,'exit':r.returncode})
    return r.returncode
# A fake .env is created only in the owned candidate, never canonical configuration.
sentinel=ROOT/'.env';assert not sentinel.exists()
sentinel.write_text('DATABASE_URL=sqlite:////private/PRIVATE_ENV_SENTINEL.db\nCIVITAI_AUTHORIZATION=FAKE_ENV_SENTINEL\n')
try:
    assert run('candidate-collection',S/'fresh-collection')==0
    assert run('candidate-original-body',S/'fresh-original',args=('backend/tests/test_lora_trainer.py::test_enqueue_valid_folder_returns_job_id_and_queued','-q'))==0
finally:
    sentinel.unlink()
assert run('missing-root',None)!=0
assert run('outside-root',S.parent/'AID43-denied-never-create')!=0
assert not (S.parent/'AID43-denied-never-create').exists()
link=S/'root-link';target=S/'link-target';target.mkdir(exist_ok=True)
if not link.is_symlink():link.symlink_to(target,target_is_directory=True)
assert link.resolve()==target.resolve()
assert run('root-symlink',link)!=0
for name in ('test.db','gallery_dir'):
    root=S/('escape-'+name);root.mkdir(exist_ok=True)
    if not (root/name).is_symlink():(root/name).symlink_to(target)
    assert (root/name).resolve()==target.resolve()
    assert run('path-symlink-'+name,root)!=0
# Guard is also exercised for attempts after bootstrap, before fixtures.
probe=S/'containment-probe.py';probe.write_text('''import socket,subprocess,sqlite3,threading
from pathlib import Path
from app.services import lora_trainer
for f in (lambda:socket.create_connection(('127.0.0.1',1)),lambda:subprocess.run(['/usr/bin/true']),lambda:sqlite3.connect('/AID43_DENIED.db'),lambda:Path('/AID43_DENIED').write_text('x')):
    try:f()
    except PermissionError:pass
    else:raise AssertionError('guard failed')
print('four negative controls denied')
''')
# Script mode intentionally has no app bootstrap; activate first explicitly.
probe.write_text('from test_support import activate\nactivate()\n'+probe.read_text())
assert run('guard-negatives',S/'fresh-guard',args=('--script',str(probe)))==0
(S/'evidence/fresh-isolation-results.json').write_text(json.dumps(results,indent=2))
print([(r['name'],r['exit']) for r in results])
