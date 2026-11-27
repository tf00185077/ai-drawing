"""Guarded, secret-free offline runner. Invoke with prepared Python -I -S -B.
Only allowlisted fixture children using this same guard may spawn; no network.
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(sys.executable).parent.parent / f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages'
sys.path[:0] = [str(SITE), str(ROOT / 'backend'), str(ROOT / 'mcp-server'), str(ROOT / 'discord-bot')]
EXTRA_SITES = [Path(p).resolve() for p in os.environ.get('AI_DRAWING_TEST_SITES','').split(os.pathsep) if p]
sys.path[:0] = [str(ROOT), str(ROOT/'backend'),str(ROOT/'mcp-server'),str(ROOT/'discord-bot'),*[str(p) for p in EXTRA_SITES]]  # repository packages, no site/.pth execution
raw_state = Path(os.environ['AI_DRAWING_TEST_ROOT']).absolute()
STATE = raw_state.resolve()
temp_base = Path(os.environ['TMPDIR']).resolve()
if STATE == temp_base or not STATE.is_relative_to(temp_base):
    raise RuntimeError('offline test root must be below explicit scratch')
cursor = raw_state
while cursor.resolve() != temp_base:
    if cursor.is_symlink():
        raise RuntimeError('offline test root link forbidden')
    cursor = cursor.parent
STATE.mkdir(parents=True, exist_ok=True)
os.chdir(ROOT)
allowed = [ROOT, SITE.resolve(), Path(sys.base_prefix).resolve(), STATE.parent, *EXTRA_SITES]
def inside(path, roots):
    return any(path == r or r in path.parents for r in roots)
def check(path, write=False):
    if path is None or isinstance(path, int): return
    p = Path(os.fsdecode(path)).resolve()
    if p == Path('/dev/null') and not write: return
    if p.name == '.env' or not inside(p, [STATE.parent] if write else allowed):
        events['blocked'].append('filesystem')
        frames = []
        frame = sys._getframe(1)
        while frame is not None and len(frames) < 10:
            frames.append({'file': frame.f_code.co_filename, 'line': frame.f_lineno, 'function': frame.f_code.co_name})
            frame = frame.f_back
        events['blocked_details'].append({'path': str(p), 'write': bool(write), 'frames': frames})
        raise PermissionError('offline filesystem boundary')
events = {"sqlite": [], "blocked": [], "blocked_details": []}
def audit(event, args):
    if event == 'open':
        mode, flags = args[1:3]
        write = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        check(args[0], write)
    elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.truncate'):
        check(args[0], True)
    elif event in ('os.rename','os.link'):
        check(args[0], True); check(args[1], True)
    elif event == 'sqlite3.connect':
        db = str(args[0])
        events['sqlite'].append(db)
        if db != ':memory:':
            # URI read-only databases must also stay in own scratch.
            from urllib.parse import unquote
            check(unquote(db.removeprefix('file:').split('?')[0]), True)
    elif event == 'subprocess.Popen':
        executable, argv, cwd, env = args
        keys = {'PATH','TMPDIR','PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONDONTWRITEBYTECODE','AI_DRAWING_TEST_ROOT','AI_DRAWING_TEST_CONFIGURED','DATABASE_URL','GALLERY_DIR','AI_DRAWING_TEST_SITES'}
        if not (executable in {sys.executable, os.environ.get('MCP_TEST_PYTHON')} and len(argv)>=7 and argv[1:5]==['-I','-S','-B',str(ROOT/'tools/offline_pytest.py')] and argv[5]=='--script' and set(env)<=keys):
            raise PermissionError('offline unguarded child denied')
        check(argv[6])
    elif event in ('socket.connect' ,'socket.bind','socket.getaddrinfo','os.system','os.posix_spawn','os.fork'):
        raise PermissionError('offline network/process boundary')
sys.addaudithook(audit)
import atexit, json
@atexit.register
def receipt():
    (STATE/'guard-receipt.json').write_text(json.dumps({'events':events,'main_imported':'app.main' in sys.modules,'config_imported':'app.config' in sys.modules,'python':sys.version},indent=2))
import mimetypes
mimetypes.knownfiles = []
mimetypes.init(files=[])
if sys.argv[1:2] == ['--script']:
    import runpy
    script = sys.argv[2]
    sys.argv = sys.argv[2:]
    runpy.run_path(script,run_name='__main__')
    sys.exit(0)
import pytest
sys.exit(pytest.main(['-c',str(ROOT/'pytest.ini'),'-p','pytest_asyncio.plugin','-p','no:cacheprovider','--basetemp',str(STATE/'pytest'),'-o','log_file='+str(STATE/'pytest.log'),*sys.argv[1:]]))
