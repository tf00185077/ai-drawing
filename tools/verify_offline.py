"""Secret-free parent launcher; retains exact commands and raw output in scratch."""
import os, sys, subprocess, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
scratch = Path(os.environ['PAPERCLIP_SCRATCH_DIR'])
name = sys.argv[1]
env = {'PATH': '/usr/bin:/bin', 'TMPDIR': str(scratch), 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'AI_DRAWING_TEST_ROOT': str(scratch/('tests-'+name)), 'DATABASE_URL': 'sqlite:////private/production-like-sentinel.db'}
python = os.environ.get('OFFLINE_TEST_PYTHON') or '/Users/tf00185088/Desktop/tim-project/.ai-drawing-prepared-environments/7796fed8-398a-4d7c-b777-6e273514a5ce/backend-venv/bin/python'
if os.environ.get('MCP_TEST_PYTHON'):
    env['MCP_TEST_PYTHON'] = os.environ['MCP_TEST_PYTHON']
if os.environ.get('LORA_LIFECYCLE_HTTP_FIXTURE'):
    env['LORA_LIFECYCLE_HTTP_FIXTURE'] = os.environ['LORA_LIFECYCLE_HTTP_FIXTURE']
cmd = [python,'-I','-S','-B',str(ROOT/'tools/offline_pytest.py'),*sys.argv[2:]]
with (scratch/'evidence'/f'{name}.log').open('w') as log:
    r = subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
(scratch/'evidence'/f'{name}-command.json').write_text(json.dumps({'argv':cmd,'env':env,'exit':r.returncode},indent=2))
print('exit',r.returncode,flush=True)
print((scratch/'evidence'/f'{name}.log').read_text()[-6000:])
sys.exit(r.returncode)
