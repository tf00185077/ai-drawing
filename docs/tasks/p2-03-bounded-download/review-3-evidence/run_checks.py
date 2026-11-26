"""Independent kickoff checks; no private configuration or live network."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SITES = [
    '/Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/lib/python3.11/site-packages',
    '/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-182-qa/.venv/lib/python3.11/site-packages',
    '/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-175-qa/.venv/lib/python3.11/site-packages',
]

def run(label, paths):
    assert not (OUT / (label + '.json')).exists(), 'Retain every attempt; choose a new label'
    scratch = Path(os.environ['PAPERCLIP_RUN_SCRATCH_DIR']).resolve()
    state = scratch / label
    state.mkdir()
    env = {k: os.environ[k] for k in ('PATH', 'LANG') if k in os.environ}
    env.update(TMPDIR=str(scratch), AI_DRAWING_TEST_ROOT=str(state),
               AI_DRAWING_TEST_SITES=os.pathsep.join(SITES),
               PYTHONPATH=os.pathsep.join([str(ROOT/'backend'), str(ROOT/'mcp-server')]),
               PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               MCP_TEST_PYTHON=str(ROOT/'.venv/bin/python'), BACKEND_TEST_PYTHON=str(ROOT/'.venv/bin/python'))
    exports = scratch / 'p203-cross-layer-exports'
    if label.startswith(('export', 'cross-layer', 'registry', 'fresh-wait')):
        exports.mkdir(exist_ok=True)
        env.update(HEALTH_WORKER_HTTP_EXPORT=str(exports/'health-workers'),
                   MULTI_LORA_HTTP_EXPORT=str(exports/'multi-lora.json'),
                   REVISION_HTTP_EXPORT=str(exports/'revision.json'),
                   LORA_LIFECYCLE_HTTP_FIXTURE=str(exports/'lifecycle.json'))
    # Ordinary body hashes identify loaded inputs even during a deliberate fault.
    source_paths = subprocess.check_output(['git','ls-files','-z','backend','mcp-server','scripts','pytest.ini'],cwd=ROOT).decode().split('\0')
    source_paths += [p for p in subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard','docs'],cwd=ROOT).decode().split('\0') if p.endswith('.py')]
    source_hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths if p and (ROOT/p).is_file()}
    if paths[0] == '--script':
        argv = [str(ROOT/'.venv/bin/python'), '-B', *paths[1:]]
    else:
        argv = [str(ROOT/'.venv/bin/python'), '-B', '-m', 'pytest', '-c', 'pytest.ini',
                '-p', 'pytest_asyncio.plugin', '-p', 'pytest_timeout', '-p', 'no:cacheprovider',
                '-o', 'log_file='+str(state/'pytest.log'), '--basetemp', str(state/'pytest'),
                '--timeout=60', '-q', *paths]
    before = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t = time.monotonic()
    with (OUT/(label+'.log')).open('wb') as log:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    if label.startswith('export') and (state/'http-export.json').exists():
        (exports/'lifecycle.json').write_bytes((state/'http-export.json').read_bytes())
    raw = (OUT/(label+'.log')).read_bytes()
    record = dict(source=before, source_hashes=source_hashes, argv=argv, cwd=str(ROOT), environment=env, started_utc=started,
                  seconds=round(time.monotonic()-t, 3), exit_code=result.returncode,
                  log_sha256=hashlib.sha256(raw).hexdigest(),
                  receipts=[json.loads(p.read_text()) for p in state.rglob('qa-guard-*.json')])
    (OUT/(label+'.json')).write_text(json.dumps(record, indent=2)+'\n')
    print(label, result.returncode, raw.decode(errors='replace').splitlines()[-1], flush=True)
    return result.returncode

if __name__ == '__main__':
    sys.exit(run(sys.argv[1], sys.argv[2:]))
