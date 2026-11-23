"""Targeted subtotal/order/shared-pool regressions; python3 -I -S only.

Only synthetic inputs. Install and probe the audit guard before candidate load.
This constrains this harness; it is not an OS sandbox for hostile Python.
"""
import sys
sys.dont_write_bytecode = True
import pathlib
import os
import ast
import types
import unittest
import itertools
import hashlib
import json

ROOT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent
HARNESS = pathlib.Path(__file__).resolve()
DENIED = []


def guard(event, args):
    if event == 'open':
        path, mode, flags = args
        if not isinstance(path, (str, bytes)):
            raise PermissionError('file descriptors excluded')
        p = pathlib.Path(os.fsdecode(path)).resolve()
        if (not (p.is_relative_to(ROOT) or p == HARNESS)
                or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
                or isinstance(mode, str) and any(c in mode for c in 'wax+')):
            DENIED.append(event)
            raise PermissionError('candidate/harness reads only')
    if event == 'import' and args[0].split('.')[0] in {
            'app', 'bot', 'mcp_server', 'sqlite3', 'http', 'socket', 'subprocess', 'ctypes'}:
        DENIED.append(event)
        raise PermissionError('product/runtime imports excluded')
    if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn')) or event in {
            'os.system', 'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.link',
            'os.symlink', 'os.chmod', 'os.truncate', 'os.chdir'}:
        DENIED.append(event)
        raise PermissionError('runtime/mutations excluded')


sys.addaudithook(guard)
for event, args in [
        ('open', ('/__regression_excluded__/state', 'r', 0)),
        ('open', (str(ROOT / 'not-created'), 'w', os.O_CREAT)),
        ('import', ('app', None, None, None, None)),
        ('import', ('sqlite3', None, None, None, None)),
        ('socket.connect', (None, None)),
        ('subprocess.Popen', (None, None, None, None)),
        ('os.remove', ('synthetic', -1))]:
    try:
        sys.audit(event, *args)
    except PermissionError:
        pass
    else:
        raise AssertionError('pre-import denial failed')

source = (ROOT / 'method.py').read_bytes()
assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(ast.parse(source)))
m = types.ModuleType('subtotal_candidate')
exec(compile(source, str(ROOT / 'method.py'), 'exec'), m.__dict__)


def bound(value, basis='derived'):
    return dict(bytes=value, basis=basis, evidence='synthetic-regression-proof')


def terms():
    return dict(P=bound(100), D_B=bound(31), D_S=bound(7), M=bound(5))


def row(pool='one', b=100, h=7, u=3):
    return dict(pool=pool, B=bound(b), H=bound(h), U=bound(u))


class SubtotalRegression(unittest.TestCase):
    def test_logical_known_terms_survive_missing_first_middle_last(self):
        # Catches discarding earlier/later known terms or losing the factor 2 on P.
        for missing, subtotal in [('P', 43), ('D_B', 212), ('D_S', 236), ('M', 238)]:
            t = terms()
            t[missing] = None
            for cap, state in [(subtotal - 1, 'exceeds'), (subtotal, 'unknown')]:
                r = m.capacity(t, [row(b=0, h=0, u=0)], {'one': 0}, cap=cap)
                self.assertEqual(r['state'], state, (missing, cap, r))
                self.assertEqual(r.get('logical_known_budget_bytes'), subtotal)
                self.assertIsNone(r['logical_bytes'])
                self.assertEqual(r['missing'], [missing])
                self.assertIs(r['runtime_acceptance'], False)

    def test_physical_known_terms_survive_each_missing_component(self):
        # B/H/U may be missing before or after a justified contribution.
        for missing, subtotal, threshold in [('B', 10, 12), ('H', 103, 124), ('U', 107, 129)]:
            a = row()
            a[missing] = None
            for free, state in [(threshold - 1, 'exceeds'), (threshold, 'unknown')]:
                r = m.capacity(terms(), [a], {'one': free}, cap=243)
                self.assertEqual(r['state'], state, (missing, free, r))
                pool = r['pools']['one']
                self.assertEqual(pool.get('known_budget_bytes'), subtotal)
                self.assertEqual(pool.get('known_budget_threshold'), threshold)
                self.assertIsNone(pool['allocation'])
                self.assertIsNone(pool['threshold'])
                self.assertIsNone(pool['fits'])
                self.assertEqual(r['missing'], ['one:' + missing])
                self.assertIs(r['runtime_acceptance'], False)

    def test_repeated_shared_pool_rows_preserve_subtotal_in_every_order(self):
        # Catches a poisoned accumulator, resetting per row, or crediting F per row.
        a = row(b=None, h=10, u=0)
        b = row(b=100, h=None, u=0)
        c = row(b=20, h=3, u=0)
        for rows in itertools.permutations([a, b, c]):
            for free, state in [(159, 'exceeds'), (160, 'unknown')]:
                r = m.capacity(terms(), rows, {'one': free}, cap=243)
                self.assertEqual(r['state'], state, r)  # selected 133; ceil(159.6)=160
                self.assertEqual(r['pools']['one'].get('known_budget_bytes'), 133)
                self.assertEqual(r['pools']['one'].get('known_budget_threshold'), 160)
                self.assertIsNone(r['pools']['one']['allocation'])
                self.assertIsNone(r['pools']['one']['threshold'])
                self.assertIsNone(r['pools']['one']['fits'])
                self.assertEqual(set(r['missing']), {'one:B', 'one:H'})
                self.assertIs(r['runtime_acceptance'], False)

    def test_partial_pools_do_not_borrow_and_missing_free_stays_unknown(self):
        a = row('a', b=100, h=None, u=0)
        b = row('b', b=0, h=0, u=0)
        for rows in [(a, b), (b, a)]:
            for free, state in [({'a': 119, 'b': 1000000}, 'exceeds'),
                                ({'b': 1000000}, 'unknown')]:
                r = m.capacity(terms(), rows, free, cap=243)
                self.assertEqual(r['state'], state, r)
                self.assertEqual(r['pools']['a'].get('known_budget_threshold'), 120)
                self.assertIsNone(r['pools']['a']['fits'])
                self.assertIs(r['runtime_acceptance'], False)

    def test_unjustified_values_never_enter_selected_budget_subtotals(self):
        # An estimate is not a certified budget term, regardless of its magnitude.
        t = dict(P=bound(2**100, 'estimate'), D_B=None, D_S=bound(0), M=bound(0))
        a = row(b=0, h=None, u=0)
        a['B'] = bound(2**100, 'page_rounded')
        r = m.capacity(t, [a], {'one': 0}, cap=0)
        self.assertEqual(r['state'], 'unknown')
        self.assertEqual(r.get('logical_known_budget_bytes'), 0)
        self.assertEqual(r['pools']['one'].get('known_budget_bytes'), 0)
        self.assertEqual(r['pools']['one'].get('known_budget_threshold'), 0)
        self.assertIsNone(r['logical_bytes'])
        self.assertIsNone(r['pools']['one']['allocation'])
        self.assertIsNone(r['pools']['one']['threshold'])
        self.assertIsNone(r['pools']['one']['fits'])
        self.assertEqual(r['missing'], ['P', 'D_B', 'one:B', 'one:H'])
        self.assertIs(r['runtime_acceptance'], False)

    def test_partial_large_integer_equality_and_one_byte_boundaries(self):
        # Literal independent ceilings beyond float's exact range and uint64.
        for payload, threshold in [(9007199254740993, 10808639105689192),
                                   (18446744073709551617, 22136092888451461941)]:
            for free, state in [(threshold - 1, 'exceeds'), (threshold, 'unknown')]:
                r = m.capacity(terms(), [row(b=payload, h=None, u=0)], {'one': free}, cap=243)
                self.assertEqual(r['state'], state, r)
                self.assertEqual(r['pools']['one'].get('known_budget_threshold'), threshold)
                self.assertIsNone(r['pools']['one']['threshold'])
                self.assertIs(r['runtime_acceptance'], False)
        t = terms()
        t['P'] = bound(9007199254740993)
        t['D_B'] = None
        for cap, state in [(18014398509481997, 'exceeds'), (18014398509481998, 'unknown')]:
            r = m.capacity(t, [row(b=0, h=0, u=0)], {'one': 0}, cap=cap)
            self.assertEqual(r['state'], state, r)
            self.assertEqual(r.get('logical_known_budget_bytes'), 18014398509481998)
            self.assertIsNone(r['logical_bytes'])
            self.assertIs(r['runtime_acceptance'], False)


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SubtotalRegression))
print('REGRESSION_SUMMARY=' + json.dumps(dict(
    tests=result.testsRun, failures=[t.id() for t, _ in result.failures],
    errors=[t.id() for t, _ in result.errors], guard_denials=len(DENIED),
    method_sha256=hashlib.sha256(source).hexdigest(), runtime_acceptance=False), sort_keys=True))
sys.exit(0 if result.wasSuccessful() else 1)
