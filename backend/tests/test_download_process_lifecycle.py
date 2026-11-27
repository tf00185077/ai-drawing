"""Actual controlled process death, fresh SQLite readers and live lock refusal."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name('durable_download_process.py')


def child(tmp_path, mode):
    receipt = tmp_path / (mode + '-receipt.json')
    state = tmp_path / (mode + '-state')
    env = {k: os.environ[k] for k in ('PATH', 'TMPDIR', 'AI_DRAWING_TEST_SITES', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD', 'PYTHONDONTWRITEBYTECODE') if k in os.environ}
    env['AI_DRAWING_TEST_ROOT'] = str(state)
    env['TMPDIR'] = str(tmp_path)
    log = (tmp_path / (mode + '-child.log')).open('w')
    process = subprocess.Popen([sys.executable, '-I', '-S', '-B', str(ROOT / 'tools/offline_pytest.py'),
        '--script', str(SCRIPT), str(tmp_path / 'lifecycle.db'), mode, str(receipt)], env=env, stdout=log, stderr=subprocess.STDOUT)
    return process, receipt, log


def ready(process, receipt, log):
    deadline = time.monotonic() + 8
    while not receipt.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert receipt.exists(), Path(log.name).read_text()
    return json.loads(receipt.read_text())


def invoke(tmp_path, mode):
    process, receipt, log = child(tmp_path, mode)
    try:
        assert process.wait(timeout=8) == 0, Path(log.name).read_text()
        return json.loads(receipt.read_text())
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=5)
        log.close()


@pytest.mark.parametrize('boundary', ['queued', 'published'])
def test_dead_owner_is_interrupted_once_without_replay_or_file_inference(tmp_path, boundary):
    process, receipt, log = child(tmp_path, boundary)
    try:
        admitted = ready(process, receipt, log)
        identity = admitted['job_id']
        before = invoke(tmp_path, 'read')['jobs'][0]
        assert before['job_id'] == identity
        assert before['status'] == ('queued' if boundary == 'queued' else 'running')
        live = invoke(tmp_path, 'reconcile')
        assert live['error']['code'] == 'download_owner_live_or_uncertain'
        assert invoke(tmp_path, 'read')['jobs'][0] == before
        target = tmp_path / 'models/process.safetensors'
        assert target.exists() is (boundary == 'published')
        # Kill only the disposable process returned by this fixture. wait()
        # confirms its actual exit; the next kernel lock acquisition is the
        # production proof that no supported thread worker can still execute.
        process.kill()
        assert process.wait(timeout=5) != 0
        first = invoke(tmp_path, 'reconcile')['jobs'][0]
        assert first['job_id'] == identity and first['status'] == 'failed'
        assert first['error']['code'] == 'download_interrupted'
        assert first['components'][0]['status'] == 'failed'
        assert first['components'][0]['downloaded_bytes'] == (0 if boundary == 'queued' else 21)
        second = invoke(tmp_path, 'reconcile')['jobs'][0]
        assert second == first
        assert target.exists() is (boundary == 'published')
        if boundary == 'published': assert target.read_bytes() == b'actual isolated bytes'
        print('DURABLE_PROCESS=' + json.dumps({'boundary': boundary, 'job_id': identity,
            'before': before, 'after': first, 'repeat_exact': second == first, 'exit': process.returncode}))
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=5)
        log.close()
