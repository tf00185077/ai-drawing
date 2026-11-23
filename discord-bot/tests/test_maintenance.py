"""Real admission and filesystem stores; external effects are controlled fakes."""
import asyncio
import json
import os
from pathlib import Path
import pytest


def gate(**kwargs):
    from bot.maintenance import Admission
    return Admission(owner='synthetic-owner', epoch='epoch-1', version='source-1', **kwargs)


async def test_close_counts_waiters_and_timeout_does_not_cancel():
    g = gate()
    lock = asyncio.Lock()
    entered, release = asyncio.Event(), asyncio.Event()
    effects = []
    async def work():
        with g.enter('delivery'):
            async with lock:
                entered.set()
                await release.wait()
                effects.append('sent')
    first = asyncio.create_task(work())
    await entered.wait()
    second = asyncio.create_task(work())
    await asyncio.sleep(0)
    assert g.status()['active'] == {'delivery': 2}
    assert (await g.drain(0.001))['state'] == 'draining'
    assert not first.done() and not second.done()
    from bot.maintenance import MaintenanceClosed
    with pytest.raises(MaintenanceClosed):
        with g.enter('callback'): effects.append('late')
    release.set()
    await asyncio.gather(first, second)
    assert effects == ['sent', 'sent']
    assert (await g.drain(0.01))['state'] == 'closed'
    assert g.status()['epoch'] == 'epoch-1'


async def test_admitted_nested_operation_finishes_after_close_and_reconnect_stays_closed():
    from bot.maintenance import guarded
    g = gate()
    events=[]
    class Target:
        admission = g
        @guarded('reconnect')
        async def reconnect(self): events.append('sync')
    with g.enter('callback'):
        g.close()
        with g.enter('submit'): events.append('post')
    await Target().reconnect()
    assert events == ['post']
    assert g.status()['active'] == {}


async def test_callback_failure_leaves_visible_hold_without_replay():
    g=gate()
    with pytest.raises(asyncio.CancelledError):
        with g.enter('reply'):
            raise asyncio.CancelledError()
    assert g.status()['state'] == 'uncertain_closed'
    assert g.status()['uncertain'] == {'reply': 1}


def provision(tmp_path):
    from bot.attempt_store import AttemptStore
    p=tmp_path/'attempts.json'
    binding={'cwd':str(Path.cwd().resolve()),'root':str(tmp_path.resolve()),'config':'config-1','source':'source-1'}
    AttemptStore.provision(p,binding=binding)
    return p,binding


def test_store_intent_chunk_restart_and_force_cannot_erase_hold(tmp_path):
    from bot.attempt_store import AttemptStore, StoreError
    p,binding=provision(tmp_path)
    with AttemptStore(p,binding=binding) as s:
        a=s.begin('channel:1:job',job_id='job',destination='channel:1',epoch='epoch-1')
        s.receipt(a,'100')
        assert s.uncertain_count == 1
    with AttemptStore(p,binding=binding) as s:
        with pytest.raises(StoreError,match='hold'):
            s.begin('channel:1:job',job_id='job',destination='channel:1',epoch='epoch-2',force=True)
        assert s.uncertain_count == 1
    data=json.loads(p.read_text())
    assert data['attempts'][a]['message_ids']==['100']
    assert data['attempts'][a]['status']=='intent'


def test_store_final_and_explicit_completed_resend_remain_compatible(tmp_path):
    from bot.attempt_store import AttemptStore
    p,b=provision(tmp_path)
    with AttemptStore(p,binding=b) as s:
        a=s.begin('k',job_id='job',destination='channel',epoch='e')
        s.receipt(a,'1');s.complete(a,2)
        assert s.get('k') == (('1',),2)
        assert s.uncertain_count==0
        a2=s.begin('k',job_id='job',destination='channel',epoch='e',force=True)
        assert a2 != a
        assert s.uncertain_count==1


@pytest.mark.parametrize('damage',['missing','corrupt','legacy','binding','cwd'])
def test_store_refuses_missing_corrupt_legacy_and_wrong_binding(tmp_path, monkeypatch, damage):
    from bot.attempt_store import AttemptStore,StoreError
    p,b=provision(tmp_path)
    if damage=='missing':p.unlink()
    if damage=='corrupt':p.write_text('{')
    if damage=='legacy':p.write_text('{}')
    if damage=='binding':b['config']='other'
    if damage=='cwd':monkeypatch.chdir(tmp_path)
    with pytest.raises(StoreError):AttemptStore(p,binding=b)


def test_store_owner_conflict_and_fsync_failure_fail_closed(tmp_path, monkeypatch):
    from bot.attempt_store import AttemptStore,StoreError
    p,b=provision(tmp_path)
    with AttemptStore(p,binding=b) as s:
        with pytest.raises(StoreError):AttemptStore(p,binding=b)
        monkeypatch.setattr(os,'fsync',lambda fd: (_ for _ in ()).throw(OSError('synthetic')))
        with pytest.raises(StoreError):s.begin('k',job_id='job',destination='channel',epoch='e')
        with pytest.raises(StoreError):s.get('k')


def test_completed_resend_order_survives_sorted_atomic_restart(tmp_path):
    from bot.attempt_store import AttemptStore
    p,b=provision(tmp_path)
    with AttemptStore(p,binding=b) as s:
        for i in range(10):
            a=s.begin('k',job_id='job',destination='channel',epoch='e',force=True)
            s.receipt(a,str(i));s.complete(a,1)
    with AttemptStore(p,binding=b) as s:
        assert s.get('k') == (('9',),1)


def test_actual_child_crash_preserves_intent_and_actual_owner_conflict(tmp_path):
    from bot.attempt_store import AttemptStore
    import subprocess,sys
    p,b=provision(tmp_path)
    root=Path(__file__).resolve().parents[2]
    runner=root/'tools/offline_pytest.py'
    env={k:os.environ[k] for k in ('PATH','TMPDIR','PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONDONTWRITEBYTECODE','AI_DRAWING_TEST_ROOT') if k in os.environ}
    script=tmp_path/'crash.py'
    script.write_text("from bot.attempt_store import AttemptStore\nimport os\ns=AttemptStore("+repr(str(p))+",binding="+repr(b)+")\ns.begin('k',job_id='job',destination='channel',epoch='e')\nos._exit(9)\n")
    result=subprocess.run([sys.executable,'-I','-S','-B',str(runner),'--script',str(script)],env=env,capture_output=True,timeout=5)
    assert result.returncode==9,result.stderr
    with AttemptStore(p,binding=b) as s:
        assert s.uncertain_count==1
        script.write_text("from bot.attempt_store import AttemptStore,StoreError\ntry:s=AttemptStore("+repr(str(p))+",binding="+repr(b)+")\nexcept StoreError:pass\nelse:raise AssertionError('second owner acquired')\n")
        result=subprocess.run([sys.executable,'-I','-S','-B',str(runner),'--script',str(script)],env=env,capture_output=True,timeout=5)
        assert result.returncode==0,result.stderr


def test_restored_older_ledger_cannot_erase_crashed_intent(tmp_path):
    from bot.attempt_store import AttemptStore,StoreError
    p,b=provision(tmp_path);old=p.read_bytes()
    with AttemptStore(p,binding=b) as s:s.begin('k',job_id='job',destination='channel',epoch='e')
    p.write_bytes(old)  # independently stale ledger; surviving checkpoint must reject
    with pytest.raises(StoreError):AttemptStore(p,binding=b)


def test_true_thread_admission_close_race_has_one_linearized_outcome():
    from bot.maintenance import MaintenanceClosed
    import threading
    for _ in range(20):
        g=gate();start=threading.Barrier(2);release=threading.Event();outcomes=[]
        def callback():
            start.wait(timeout=1)
            try:
                with g.enter('callback'):
                    outcomes.append('admitted');release.wait(1)
            except MaintenanceClosed:outcomes.append('rejected')
        t=threading.Thread(target=callback);t.start()
        try:
            start.wait(timeout=1);g.close()
            with pytest.raises(MaintenanceClosed):
                with g.enter('late'):raise AssertionError('late admitted')
        finally:release.set();t.join(timeout=1)
        assert not t.is_alive()
        assert outcomes in (['admitted'],['rejected'])
        assert g.status()['active']=={}
        assert g.status()['state']=='closed'
