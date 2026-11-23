"""Run only in a fresh explicit task-owned parent. No product imports."""
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve(strict=True)
if not root.is_dir() or any(root.iterdir()):
    raise SystemExit('fresh empty fixture parent required')
(root / 'tmp').mkdir(mode=0o700)
os.chdir(root)
os.environ.clear()
os.environ['TMPDIR'] = str(root / 'tmp')
source = Path(__file__).resolve().parent
# Paths below are public code, never product cwd/config/state.
forbidden = ('app', 'sqlalchemy', 'conftest', 'database', 'settings', 'pytest')
def audit(event, args):
    if event == 'import' and args[0].split('.')[0].lower() in forbidden:
        raise RuntimeError('product import forbidden')
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'):
        raise RuntimeError('network/child forbidden')
    if event == 'sqlite3.connect':
        p = Path(os.fsdecode(args[0]))
        if not p.is_absolute() or root not in p.parents or '..' in p.parts:
            raise RuntimeError('scratch SQLite only')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        p = Path(os.fsdecode(args[0])).absolute()
        if str(p).startswith(('/Users/tf00185088/Desktop/tim-project/ai-drawing/', '/Volumes/AI-Drawing-16T/', '/Users/tf00185088/Desktop/tim-project/.ai-drawing-maintenance-backups/')):
            raise RuntimeError('excluded private root')
        flags = args[2]
        if isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
            if root != p and root not in p.parents:
                raise RuntimeError('outside scratch write')
sys.addaudithook(audit)
sys.path.insert(0, str(source))
sys.path.insert(1, str(source.parent / 'm1_bounded'))
sys.argv = [str(source / 'test_contract.py')] + sys.argv[2:]
import runpy
runpy.run_path(str(source / 'test_contract.py'), run_name='__main__')
