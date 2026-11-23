"""Run with python3 -I -S. Guard is installed before loading method code.

No repo conftest, Settings, product app, DB, or collectors are loaded.
This guard constrains these controls, not arbitrary Python or future operations.
"""
import sys
sys.dont_write_bytecode = True
import pathlib
import importlib.util
import unittest
import json
import hashlib
import zipfile
import io
import os
import types
import ast

ROOT = pathlib.Path(__file__).resolve().parent


def guard(event, args):
    if event == 'open':
        path, mode, flags = args
        if not isinstance(path, (str, bytes)):
            raise PermissionError('file descriptors excluded')
        p = pathlib.Path(path).resolve()
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        if not p.is_relative_to(ROOT) or (isinstance(mode, str) and any(c in mode for c in 'wax+')) or flags & write_flags:
            raise PermissionError('only bundle reads permitted')
    if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn')) or event == 'os.system':
        raise PermissionError('runtime access excluded')
    if event == 'import' and args[0].split('.')[0] in {'app', 'bot', 'mcp_server', 'sqlite3', 'http', 'socket', 'subprocess'}:
        raise PermissionError('product/runtime imports excluded')
    if event in {'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.link', 'os.symlink', 'os.chmod', 'os.truncate'}:
        raise PermissionError('filesystem mutations excluded')


sys.addaudithook(guard)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = load('offline_method', ROOT / 'method.py')
checks = load('offline_checks', ROOT / 'controls/checks.py')
result = unittest.TextTestRunner(verbosity=2).run(checks.suite(m))
if not result.wasSuccessful():
    raise SystemExit(1)

# Confirm denial behavior before any product/runtime access could happen.
for attempt in [lambda: open('/__forbidden_synthetic__/db', 'rb'),
                lambda: open(ROOT / 'not-created', 'wb'),
                lambda: __import__('app'), lambda: __import__('sqlite3')]:
    try:
        attempt()
    except PermissionError:
        pass
    else:
        raise AssertionError('guard did not deny excluded access')
assert not (ROOT / 'not-created').exists()

zbytes = (ROOT / 'inputs/retained-second.zip').read_bytes()
assert len(zbytes) == 368512
assert hashlib.sha256(zbytes).hexdigest() == '3a04b1a0f9e97b2cd813af47732cafa27a18fbc4940b336bb72f010b5601bf4b'
with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
    assert z.testzip() is None
    manifest = json.loads(z.read('evidence-manifest.json'))
    for name, rec in manifest.items():
        b = z.read(name)
        assert len(b) == rec['bytes'] and hashlib.sha256(b).hexdigest() == rec['sha256']
    runtime = json.loads(z.read('runtime-supplement.json'))
    retained = json.loads(z.read('capacity-supplement.json'))
    assert m.discovery(runtime['MCP']['exit'], '')['state'] == 'error'
    assert sum(g['logical'] for g in retained['groups'].values()) == 37500797650
    assert 2 * 37500797650 == 75001595300
    metadata = json.loads(z.read('metadata-fingerprints.json'))
    link_bytes = [row['link_literal_bytes'] for row in metadata if 'link_literal_bytes' in row]
    assert len(link_bytes) == 10 and sum(link_bytes) == 1100
    assert 37500797650 + sum(link_bytes) == 37500798750
print('GUARD: 4 denied controls; no excluded read/write reached')
print('RETAINED: ZIP SHA/CRC and all 14 payloads verified; exit2 remains error')

# Exact retained arithmetic. A named regular-file subtotal is not effective P.
term = lambda n, basis: dict(bytes=n, basis=basis, evidence='retained-second.zip')
actual = m.capacity(dict(P=term(37500797650, 'named_only'), D_B=None, D_S=None,
                         M=term(67108864, 'estimate')),
                    [dict(pool='retained-R-C', B=term(75094040576, 'page_rounded'),
                          H=term(268435456, 'estimate'), U=term(268435456, 'estimate'))],
                    {'retained-R-C': 236750987264}, cap=128849018880)
assert actual['state'] == 'unknown'
assert actual['logical_bytes'] is None and actual['pools']['retained-R-C']['threshold'] is None
print('ACTUAL_RETAINED_PROJECTION=' + json.dumps(actual, sort_keys=True))

# Kill dangerous interpretation/arithmetic mutations without editing the source.
source = (ROOT / 'method.py').read_bytes().decode('utf-8')
assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(ast.parse(source)))
mutations = [
    ('error_as_absence', 'elif exit_code == 1:', 'elif exit_code in (1, 2):'),
    ('shared_free_double_credit', '(6 * rec[\'allocation\'] + 4) // 5', '(3 * rec[\'allocation\'] + 4) // 5'),
    ('defaults_as_loaded', "fact.get('kind') == 'loaded_snapshot'", "fact.get('kind') in {'loaded_snapshot', 'source_default', 'cwd', 'open_fd'}"),
]
for name, before, after in mutations:
    assert source.count(before) == 1
    mutant = types.ModuleType('mutant_' + name)
    exec(compile(source.replace(before, after), '<synthetic-mutant>', 'exec'), mutant.__dict__)
    stream = io.StringIO()
    verdict = unittest.TextTestRunner(stream=stream).run(checks.suite(mutant))
    assert verdict.failures and not verdict.errors, (name, stream.getvalue())
    print('MUTATION_KILLED=' + name + ':' + ','.join(t.id().split('.')[-1] for t, _ in verdict.failures))
