"""R5-1: real POSIX CLI signals; only the lower HTTP/storage boundary is synthetic.

Removing cancellation call capture or once-only attempt finalization must make
these fail. No driver, MCP callable, SDK transport or signal handler is patched.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / 'scripts/mcp_smoke_mac.py'
spec = importlib.util.spec_from_file_location('smoke_lower_fixture', ROOT / 'mcp-server/tests/test_smoke_driver.py')
lower = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lower)
fixture_backend = lower.fixture_backend


@pytest.mark.skipif(os.name == 'nt', reason='POSIX SIGINT subprocess boundary for p1-05 correction 1; docs/tasks/p1-05-mcp-e2e-smoke-mac/repair-round-1.md')
@pytest.mark.parametrize('boundary,tool,call_count,submit_count', [
    ('health', 'health', 1, 2),
    ('admitted-wait', 'wait_for_job', 4, 3),
    ('uncertain-submit', 'generate', 3, 3),
])
def test_sigint_finishes_active_attempt_and_retains_sent_call(
        tmp_path, fixture_backend, boundary, tool, call_count, submit_count):
    backend, gallery, submits, requests, records = fixture_backend
    held = threading.Event()
    release = threading.Event()
    exchanges = []
    health_count = 0

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def forward(self):
            nonlocal health_count
            if self.path == '/health':
                health_count += 1
            body = self.rfile.read(int(self.headers.get('Content-Length', '0'))) if self.command == 'POST' else None
            req = urllib.request.Request(backend + self.path, data=body, method=self.command,
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read()
                status = response.status
            exchanges.append({'method': self.command, 'path': self.path,
                              'request': json.loads(body) if body else None, 'response': json.loads(raw)})
            pause = ((boundary == 'health' and self.path == '/health' and health_count == 2)
                     or (boundary == 'admitted-wait' and self.path.startswith('/api/generate/job/') and len(submits) == 3)
                     or (boundary == 'uncertain-submit' and self.command == 'POST' and len(submits) == 3))
            if pause:
                held.set()
                release.wait(20)
            try:
                self.send_response(status)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

        do_GET = forward
        do_POST = forward

    server = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = tmp_path / 'config.json'
    output = tmp_path / 'run'
    proc = None
    try:
        prepared = subprocess.run([sys.executable, str(DRIVER), 'prepare', '--config', str(config),
                                   '--backend', f'http://127.0.0.1:{server.server_port}', '--gallery', str(gallery)],
                                  cwd=ROOT, capture_output=True, text=True, timeout=15)
        assert prepared.returncode == 0, prepared.stderr
        proc = subprocess.Popen([sys.executable, str(DRIVER), 'run', '--config', str(config), '--output', str(output)],
                                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={**os.environ, 'PYTHONPATH': str(ROOT / 'mcp-server')})
        assert held.wait(20), f'{boundary} was not reached'
        # A response is known only to the lower fixture, never to the SDK client.
        proc.send_signal(signal.SIGINT)
        stdout, stderr = proc.communicate(timeout=20)
        (tmp_path / 'stdout.txt').write_bytes(stdout)
        (tmp_path / 'stderr.txt').write_bytes(stderr)
        summary = json.loads((output / 'summary.json').read_text())
        calls = [json.loads(line) for line in (output / 'calls.jsonl').read_text().splitlines()]
        events = [json.loads(line) for line in (output / 'events.jsonl').read_text().splitlines()]
        wire = [json.loads(line) for line in (output / 'sdk-messages.jsonl').read_text().splitlines()]
        (tmp_path / 'lower-exchanges.json').write_text(json.dumps(exchanges, indent=2) + '\n')
        (tmp_path / 'observed.json').write_text(json.dumps({'exit_code': proc.returncode,
            'boundary': boundary, 'submits': len(submits), 'summary': summary}, indent=2) + '\n')
        assert proc.returncode != 0
        assert len(submits) == submit_count
        assert len(summary['attempts']) == 2
        assert summary['attempts'][0]['qualifying'] is True
        current = summary['attempts'][1]
        # Aggregate independent state assertions to retain the complete RED diagnosis.
        problems = []
        if summary['result'] != 'interrupted' or summary['streak'] != 0:
            problems.append(f"interrupted result/streak: {summary['result']}/{summary['streak']}")
        if current.get('qualifying') is not False or not current.get('reason'):
            problems.append('active attempt lacks nonqualifying reason')
        if not current.get('ended') or current.get('calls') != call_count or current.get('streak') != 0:
            problems.append('active attempt lacks end/calls/zero streak')
        ending = [e for e in events if e.get('phase') == 'attempt' and e.get('attempt') == 2 and e.get('event') == 'ended']
        if len(ending) != 1:
            problems.append(f'expected one attempt ending event, got {len(ending)}')
        active = [c for c in calls if c['phase'] == 'attempt' and c['attempt'] == 2]
        if len(active) != call_count or active[-1]['tool'] != tool or not active[-1].get('interruption'):
            problems.append('sent interrupted call absent/incomplete')
        assert not problems, problems
        assert current['started'] <= current['ended']
        assert current['unknown_admission'] is (boundary == 'uncertain-submit')
        interrupted = active[-1]
        assert interrupted['started'] <= interrupted['ended']
        assert interrupted['duration_seconds'] >= 0
        assert 'result' not in interrupted
        sent = [w['message'] for w in wire if w['direction'] == 'sent' and w['message'].get('method') == 'tools/call']
        assert len(sent) == len(calls) == 8 + call_count
        assert [(m['params']['name'], m['params'].get('arguments', {})) for m in sent] == [(c['tool'], c['arguments']) for c in calls]
        received_ids = {w['message'].get('id') for w in wire if w['direction'] == 'received'}
        assert sent[-1]['id'] not in received_ids
        assert sent[-1]['params']['name'] == tool
        assert not any(c['phase'] in ('recovery', 'audit') for c in calls)
        assert {w['session'] for w in wire} == {'qualification'}
        assert len(summary['jobs']) == (3 if boundary == 'admitted-wait' else 2)
        assert list(summary['jobs'].values())[:2] == ['completed', 'completed']
        if boundary == 'admitted-wait':
            job = next(reversed(summary['jobs']))
            assert summary['jobs'][job] == 'queued'  # last observed admission, not a guessed failure
            assert interrupted['arguments'] == {'job_id': job, 'timeout_seconds': 50}
        if boundary == 'uncertain-submit':
            unseen_job = exchanges[-1]['response']['job_id']
            assert unseen_job not in summary['jobs']
            assert interrupted['arguments']['revision_context']['request_ref'] == current['declared']['request_ref']
        assert all(s['execution_target'] == 'local' for s in submits)
        # Existing evidence cannot be resumed, even after interruption.
        rerun = subprocess.run([sys.executable, str(DRIVER), 'run', '--config', str(config), '--output', str(output)],
                               cwd=ROOT, capture_output=True, timeout=10)
        assert rerun.returncode != 0 and len(submits) == submit_count
    finally:
        release.set()
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=5)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        destination = os.environ.get('SMOKE_SIGNAL_EVIDENCE_ROOT')
        if destination:
            shutil.copytree(tmp_path, Path(destination) / boundary)
