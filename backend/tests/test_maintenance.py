"""Maintenance/drain behavior against real modules; no product jobs or runners."""
import asyncio
import threading
from types import SimpleNamespace
import pytest


@pytest.fixture(autouse=True)
def local_worker_controls(monkeypatch):
    # Our drain regressions must not leave a closed event in another module's tests.
    from app.core import queue
    from app.services import lora_trainer,comfyui_history_watcher,watcher
    for module in (queue,lora_trainer,comfyui_history_watcher):
        monkeypatch.setattr(module,'_stop_event',threading.Event())
    monkeypatch.setattr(lora_trainer,'_children',[])
    monkeypatch.setattr(watcher,'_closing',False)
    monkeypatch.setattr(watcher,'_debounce_timers',{})
    monkeypatch.setattr(watcher,'_caption_threads',set())
    monkeypatch.setattr(watcher,'_observer',None)


def test_queue_retains_and_reports_alive_worker(monkeypatch):
    from app.core import queue
    alive = SimpleNamespace(join=lambda timeout:None,is_alive=lambda:True)
    monkeypatch.setattr(queue,'_worker_thread',alive)
    monkeypatch.setattr(queue,'_argus_runner',None)
    assert queue.stop_worker(timeout=0.001) is False
    assert queue._worker_thread is alive


def test_history_retains_alive_handle(monkeypatch):
    from app.services import comfyui_history_watcher as history
    alive=SimpleNamespace(join=lambda timeout:None,is_alive=lambda:True)
    monkeypatch.setattr(history,'_worker_thread',alive)
    assert history.stop_watcher(timeout=0.001) is False
    assert history._worker_thread is alive


def test_caption_closes_pending_timer_and_rejects_late_event(monkeypatch,tmp_path):
    from app.services import watcher
    calls=[]
    monkeypatch.setattr(watcher,'_process_caption_folder',lambda p:calls.append(p))
    monkeypatch.setattr(watcher,'DEBOUNCE_SECONDS',0.03)
    monkeypatch.setattr(watcher,'_observer',None)
    monkeypatch.setattr(watcher,'_debounce_timers',{})
    monkeypatch.setattr(watcher,'_caption_threads',set(),raising=False)
    monkeypatch.setattr(watcher,'_closing',False,raising=False)
    watcher.on_new_image(tmp_path/'image.png')
    assert watcher.stop_watching(timeout=0.2) is True
    watcher.on_new_image(tmp_path/'late.png')
    assert not watcher._debounce_timers
    assert calls==[]


def test_caption_active_thread_timeout_retains_handle(monkeypatch,tmp_path):
    from app.services import watcher
    entered,release=threading.Event(),threading.Event()
    def caption(p):entered.set();release.wait(2);return False
    monkeypatch.setattr(watcher,'_process_caption_folder',caption)
    monkeypatch.setattr(watcher,'DEBOUNCE_SECONDS',0.001)
    monkeypatch.setattr(watcher,'_observer',None)
    monkeypatch.setattr(watcher,'_debounce_timers',{})
    monkeypatch.setattr(watcher,'_caption_threads',set(),raising=False)
    monkeypatch.setattr(watcher,'_closing',False,raising=False)
    try:
        watcher.on_new_image(tmp_path/'image.png')
        assert entered.wait(1)
        assert watcher.stop_watching(timeout=0.001) is False
        assert watcher._caption_threads
    finally:
        release.set()
        assert watcher.stop_watching(timeout=1) is True


def test_trainer_drain_does_not_terminate_child_and_checks_exit(monkeypatch):
    from app.services import lora_trainer as trainer
    calls=[]
    child=SimpleNamespace(poll=lambda:None,terminate=lambda:calls.append('terminate'))
    alive=SimpleNamespace(join=lambda timeout:None,is_alive=lambda:True)
    monkeypatch.setattr(trainer,'_worker_thread',alive)
    monkeypatch.setattr(trainer,'_running',SimpleNamespace(proc=child))
    assert trainer.stop_worker(timeout=0.001) is False
    assert trainer._worker_thread is alive
    assert calls==[]


async def test_lifespan_always_drains_trainer_and_reports_partial(monkeypatch):
    from app import main
    from app.db import database
    calls=[]
    monkeypatch.setattr(database,'init_db',lambda:None)
    monkeypatch.setattr(main.lora_trainer,'register_on_complete',lambda cb:None)
    monkeypatch.setattr(main.lora_trainer,'ensure_worker',lambda:None)
    for name in ['start_watching','start_queue_worker','start_comfyui_watcher']:
        monkeypatch.setattr(main,name,lambda:None)
    for name in ['stop_watching','stop_queue_worker','stop_comfyui_watcher']:
        monkeypatch.setattr(main,name,lambda **kwargs:True)
    monkeypatch.setattr(main.lora_trainer,'stop_worker',lambda **kwargs:calls.append('trainer') or False,raising=False)
    async with main.lifespan(main.app):pass
    assert calls==['trainer']
    assert main.app.state.maintenance_drain['complete'] is False


def test_trainer_checks_real_bounded_synthetic_child_exit(monkeypatch,tmp_path):
    from app.services import lora_trainer as trainer
    import os,subprocess,sys
    from pathlib import Path
    runner=Path(__file__).resolve().parents[2]/'tools/offline_pytest.py'
    script=tmp_path/'child.py';script.write_text('import time\ntime.sleep(0.3)\n')
    env={k:os.environ[k] for k in ('PATH','TMPDIR','PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONDONTWRITEBYTECODE','AI_DRAWING_TEST_ROOT') if k in os.environ}
    child=subprocess.Popen([sys.executable,'-I','-S','-B',str(runner),'--script',str(script)],env=env)
    monkeypatch.setattr(trainer,'_worker_thread',None)
    monkeypatch.setattr(trainer,'_running',None)
    monkeypatch.setattr(trainer,'_children',[child])
    try:
        assert trainer.stop_worker(timeout=0.001) is False
        assert trainer._children==[child]
    finally:child.wait(timeout=5)
    assert trainer.stop_worker(timeout=0.1) is True
