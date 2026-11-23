"""Scope direct tests before candidate imports; Python audit, not OS confinement."""
import importlib.abc
import json
import os
from pathlib import Path
import runpy
import sys

ROOT=Path(sys.argv[1]).resolve(strict=True)
HERE=Path(__file__).resolve().parent
os.chdir(ROOT)
os.environ.clear()
os.environ['TMPDIR']=str(ROOT)
sys.path.insert(0,str(HERE))
COUNTS={}
class NoProduct(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='app' or fullname.startswith('app.') or fullname in ('sqlite3','_sqlite3'):
            raise AssertionError('product_and_db_import_prohibited')
sys.meta_path.insert(0,NoProduct())
def contained(p):
    p=Path(p)
    return p==ROOT or ROOT in p.parents

def audit(event,args):
    if event.startswith(('socket.','subprocess.','os.')) or event=='open':
        COUNTS[event]=COUNTS.get(event,0)+1
    if event in ('socket.connect','socket.bind','socket.getaddrinfo'):
        raise AssertionError('network_prohibited')
    if event=='subprocess.Popen':
        executable,argv,cwd,env=args
        module=sys.modules.get('observe')
        if module is None or argv[:5]!=[sys.executable,'-I','-S','-B','-c'] or argv[5:]not in [[s] for s in module.FIXTURE_SCRIPTS.values()] or not contained(cwd) or env!={'TMPDIR':str(cwd)}:
            raise AssertionError('unreviewed_process_prohibited')
    if event=='open':
        p,mode,flags=args
        writing=bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if writing and isinstance(p,(str,bytes)):
            p=os.fsdecode(p)
            # Relative basename opens are anchored by the reviewed helper FDs.
            # The audit event omits dir_fd; it cannot prove native containment.
            if p=='/dev/null' and not flags & (os.O_CREAT|os.O_TRUNC|os.O_APPEND):return
            if Path(p).is_absolute() and not contained(p):raise AssertionError('outside_write')
            if not Path(p).is_absolute() and ('/'in p or p in('.','..')):raise AssertionError('relative_write')
    if event in ('os.remove','os.rmdir','os.rename','os.mkdir','os.chmod','os.chown','os.utime','os.symlink','os.link'):
        # This guard covers the destination for symlink, whose literal may be outside.
        p=args[1] if event=='os.symlink' else args[0]
        if isinstance(p,(str,bytes)) and Path(os.fsdecode(p)).is_absolute() and not contained(os.fsdecode(p)):
            raise AssertionError('outside_mutation')
sys.addaudithook(audit)
try:
    sys.argv=[str(HERE/'test_m1.py'),str(ROOT)]
    runpy.run_path(str(HERE/'test_m1.py'),run_name='__main__')
finally:
    (ROOT/'audit-counts.json').write_text(json.dumps(COUNTS,sort_keys=True,indent=2))
