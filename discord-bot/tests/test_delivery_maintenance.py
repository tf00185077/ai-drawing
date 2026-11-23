import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from bot.delivery import DeliveryLedger, ResultDeliveryService


def store(tmp_path):
    path=tmp_path/'ledger.json'
    if hasattr(DeliveryLedger,'provision'):
        DeliveryLedger.provision(path)
    return DeliveryLedger(path)


async def test_partial_chunk_is_persisted_before_failure_and_retry_cannot_send(tmp_path):
    ledger=store(tmp_path)
    api=SimpleNamespace(collect_job_result=AsyncMock(return_value={
        'status':'completed','artifacts':[(str(i)+'.png',b'x') for i in range(11)]}))
    effects=[]
    async def send(*args,**kwargs):
        effects.append('accepted')
        if len(effects)==2:raise RuntimeError('synthetic failure')
        return SimpleNamespace(id=100)
    service=ResultDeliveryService(api,ledger)
    with pytest.raises(Exception):await service.deliver('job','channel:1',send)
    with pytest.raises(Exception):await service.deliver('job','channel:1',send,force_resend=True)
    assert effects==['accepted','accepted']
    raw=json.loads((tmp_path/'ledger.json').read_text())
    attempts=raw['attempts']
    assert len(attempts)==1
    assert list(attempts.values())[0]['message_ids']==['100']
    assert list(attempts.values())[0]['status']=='intent'


async def test_accepted_no_return_cancel_survives_restart(tmp_path):
    ledger=store(tmp_path);accepted=asyncio.Event()
    api=SimpleNamespace(collect_job_result=AsyncMock(return_value={'status':'completed','artifacts':[('one.png',b'x')]}))
    effects=[]
    async def send(*args,**kwargs):
        effects.append('accepted');accepted.set()
        if len(effects)==1:await asyncio.Event().wait()
        return SimpleNamespace(id=100)
    service=ResultDeliveryService(api,ledger)
    task=asyncio.create_task(service.deliver('job','channel:1',send))
    await accepted.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    if hasattr(ledger,'close'):ledger.close()
    ledger=DeliveryLedger(tmp_path/'ledger.json');service=ResultDeliveryService(api,ledger)
    with pytest.raises(Exception):await service.deliver('job','channel:1',send,force_resend=True)
    assert effects==['accepted']
    ledger.close()


async def test_late_modal_and_reconnect_after_close_have_zero_external_effects(tmp_path):
    from bot.config import Config
    from bot.main import build_bot
    from bot.views import DrawModal
    config=Config(discord_token='synthetic',guild_id=1,backend_base_url='http://test',delivery_ledger_path=tmp_path/'bot.json')
    if hasattr(DeliveryLedger,'provision'):
        from bot.config import ledger_binding
        DeliveryLedger.provision(config.delivery_ledger_path,binding=ledger_binding(config))
    client,tree,api=build_bot(config)
    g=getattr(client,'admission',None)
    if g is not None:g.close()
    api.compose_and_submit=AsyncMock(return_value='job')
    api.list_presets=AsyncMock(return_value=[])
    interaction=SimpleNamespace(response=SimpleNamespace(defer=AsyncMock(),send_message=AsyncMock(),send_modal=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
    modal=DrawModal(api,'preset',None,'prompt','negative')
    await modal.on_submit(interaction)
    assert interaction.response.defer.await_count==0
    assert interaction.followup.send.await_count==0
    assert api.compose_and_submit.await_count==0
    sync=AsyncMock();tree.sync=sync
    await client.on_ready()
    assert sync.await_count==0
    if hasattr(client,'shutdown'):await client.shutdown(timeout=0.01)


@pytest.mark.parametrize('phase',['receipt','complete'])
async def test_post_send_io_failure_leaves_hold_on_restart(tmp_path,monkeypatch,phase):
    ledger=store(tmp_path)
    api=SimpleNamespace(collect_job_result=AsyncMock(return_value={'status':'completed','artifacts':[('one.png',b'x')]}))
    effects=[]
    async def send(*args,**kwargs):effects.append('accepted');return SimpleNamespace(id=10)
    monkeypatch.setattr(ledger,phase,lambda *a:(_ for _ in ()).throw(OSError('synthetic I/O')))
    service=ResultDeliveryService(api,ledger)
    with pytest.raises(OSError):await service.deliver('job','channel:1',send)
    assert service.admission.status()['state']=='uncertain_closed'
    ledger.close();restored=DeliveryLedger(tmp_path/'ledger.json')
    with pytest.raises(Exception):await ResultDeliveryService(api,restored).deliver('job','channel:1',send,force_resend=True)
    assert effects==['accepted']
    restored.close()


async def test_operator_closed_before_body_channel_lookup_and_typed_owner_status():
    from bot.operator_api import OperatorConfig,OperatorDeliveryServer
    from bot.maintenance import Admission
    g=Admission(owner='owner-1',epoch='epoch-1',version='source-1')
    client=SimpleNamespace(get_channel=lambda _:(_ for _ in ()).throw(AssertionError('lookup after close')))
    server=OperatorDeliveryServer(client,SimpleNamespace(admission=g),OperatorConfig('synthetic-token',{'results':1},8765),1)
    g.close()
    request=SimpleNamespace(headers={'Authorization':'Bearer synthetic-token'},json=AsyncMock(side_effect=AssertionError('read body after close')))
    response=await server._handle_delivery(request)
    assert response.status==503
    assert request.json.await_count==0
    response=await server._handle_status(request)
    assert json.loads(response.body)=={'schema_version':1,'state':'closed','owner':'owner-1','epoch':'epoch-1','version':'source-1','active':{},'uncertain':{},'legacy_process_certified':False}
    denied=await server._handle_status(SimpleNamespace(headers={}))
    assert denied.status==401


async def test_all_slash_modal_select_submit_boundaries_stay_closed(tmp_path):
    import discord
    from bot.config import Config,ledger_binding
    from bot.main import build_bot
    from bot.views import DrawModal,FixedVideoModal,MiniMaxH3I2VModal,ProfileSelect,PresetSelect,send_draw_modal
    cfg=Config(discord_token='synthetic',guild_id=1,backend_base_url='http://test',delivery_ledger_path=tmp_path/'bot.json')
    DeliveryLedger.provision(cfg.delivery_ledger_path,binding=ledger_binding(cfg))
    client,tree,api=build_bot(cfg);client.admission.close()
    interaction=SimpleNamespace(response=SimpleNamespace(defer=AsyncMock(),send_message=AsyncMock(),send_modal=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
    for command in tree.get_commands(guild=discord.Object(1)):
        await command.callback(interaction)  # guard rejects before argument use or side effect
    for cls in (DrawModal,FixedVideoModal,MiniMaxH3I2VModal,ProfileSelect,PresetSelect):
        obj=SimpleNamespace(_api=api)
        await getattr(cls,'on_submit' if hasattr(cls,'on_submit') else 'callback')(obj,interaction)
    await send_draw_modal(interaction,api,'preset',None)
    from bot.maintenance import MaintenanceClosed
    for name in ('submit_generate','submit_fixed_video','submit_animegen_i2v','submit_minimax_h3_i2v','submit_wan22_animate','compose_and_submit'):
        with pytest.raises(MaintenanceClosed):await getattr(api,name)()
    assert interaction.response.defer.await_count==0
    assert interaction.response.send_message.await_count==0
    assert interaction.response.send_modal.await_count==0
    assert interaction.followup.send.await_count==0
    await client.shutdown(timeout=0.01)


async def test_operator_success_and_alias_rename_bind_actual_destination(tmp_path):
    from bot.operator_api import OperatorConfig,OperatorDeliveryServer
    ledger=store(tmp_path)
    api=SimpleNamespace(collect_job_result=AsyncMock(return_value={'status':'completed','artifacts':[('one.png',b'x')]}))
    send=AsyncMock(return_value=SimpleNamespace(id=1234))
    service=ResultDeliveryService(api,ledger)
    channel=SimpleNamespace(guild=SimpleNamespace(id=1),send=send)
    client=SimpleNamespace(get_channel=lambda _:channel)
    server=OperatorDeliveryServer(client,service,OperatorConfig('synthetic-token',{'old':99,'new':99},8765),1)
    for alias,dedup in [('old',False),('new',True)]:
        req=SimpleNamespace(headers={'Authorization':'Bearer synthetic-token'},json=AsyncMock(return_value={'job_id':'11111111-2222-3333-4444-555555555555','destination_alias':alias}))
        response=await server._handle_delivery(req)
        assert response.status==200
        data=json.loads(response.body)
        assert data['message_ids']==['1234'] and data['artifact_count']==1
        assert data['destination_alias']==alias and data['deduplicated'] is dedup
    assert send.await_count==1
    ledger.close()


async def test_status_detects_corrupted_history_before_any_new_external_effect(tmp_path):
    from bot.operator_api import OperatorConfig,OperatorDeliveryServer
    ledger=store(tmp_path)
    service=ResultDeliveryService(SimpleNamespace(),ledger)
    server=OperatorDeliveryServer(SimpleNamespace(),service,OperatorConfig('synthetic-token',{'result':99},8765),1)
    (tmp_path/'ledger.json').write_text('{')
    req=SimpleNamespace(headers={'Authorization':'Bearer synthetic-token'})
    response=await server._handle_status(req)
    assert json.loads(response.body)['state']=='uncertain_closed'
    ledger.close()
