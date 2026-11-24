"""Exercise real registered MCP wrappers; replace only external HTTP transport."""
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from mcp_server.config import get_mcp_settings
from mcp_server.server import mcp
from mcp_server.tool_catalog import INTENDED_TOOLS


ARGUMENTS = {
    'wait_for_job': {'job_id': 'fixture', 'timeout_seconds': .05},
    'generate': {'mode': 'template', 'prompt': 'cup', 'loras': [], 'execution_target': 'local'},
    'gallery_get': {'image_id': 44},
    'gallery_rerun': {'image_id': 44},
    'style_preset_save': {'from_source': 'fields', 'preset_id': 'cup', 'name': 'Cup'},
    'style_preset_test': {'preset_id': 'cup'},
    'style_preset_compose': {'preset_id': 'cup', 'content_prompt': 'cup'},
    'prompt_write': {'action': 'save', 'resource_type': 'combination', 'resource_id': 'cup', 'payload': {}},
    'comfyui_admin': {'action': 'free_memory'},
    'lora_train_start': {'folder': 'character/cup', 'output_name': 'Cup', 'expected_dataset_hash': 'd', 'expected_profile_hash': 'p', 'recipe': {}},
    'lora_training_decision_preflight': {'folder': 'character/cup', 'output_name': 'Cup'},
}


def arguments_for(tool):
    if tool.name in ARGUMENTS:
        return dict(ARGUMENTS[tool.name])
    values = {'string': 'fixture', 'integer': 1, 'number': 1.0, 'object': {}, 'array': ['ExampleNode'], 'boolean': True}
    props = tool.inputSchema['properties']
    return {name: values.get(props[name].get('type'), 'fixture') for name in tool.inputSchema.get('required', [])}


@contextmanager
def transport(monkeypatch, *, status=200, body=None, exception=None):
    """No tool callable is replaced: SDK validation, wrappers and HTTP client stay real."""
    monkeypatch.setenv('MCP_BACKEND_API_URL', 'http://backend.invalid')
    monkeypatch.setenv('MCP_COMFYUI_API_URL', 'http://comfy.invalid')
    monkeypatch.setenv('MCP_GALLERY_DIR', str(Path('/fixture/gallery').resolve()))
    monkeypatch.setenv('MCP_DISCORD_OPERATOR_TOKEN', 'synthetic-operator-token')
    get_mcp_settings.cache_clear()
    requests = []
    def respond(request):
        requests.append(request)
        if exception:
            raise exception
        payload = body
        if payload is None:
            payload = {'ok': True, 'job_id': 'job-1', 'status': 'queued', 'id': 44,
                       'caption': 'a cup', 'content': 'a cup', 'image_path': 'cup.png',
                       'message_ids': ['message-1'], 'artifact_count': 1, 'deduplicated': True}
            status_files = {'/health': ('backend', 'response'), '/api/system/status': ('comfyui-connected', 'response'), '/api/workers/status': ('up', 'responses')}
            if request.url.path in status_files:
                import os
                directory = Path(os.environ.get('HEALTH_WORKER_HTTP_EXPORT', Path(__file__).parent / 'fixtures' / 'health-workers'))
                filename, key = status_files[request.url.path]
                payload = json.loads((directory / (filename + '.json')).read_text(encoding='utf-8'))[key]
                if key == 'responses': payload = payload[0]
            if request.url.path == '/api/generate/job/fixture':
                payload = {'job_id': 'fixture', 'status': 'completed', 'image_id': 44, 'image_path': 'cup.png', 'artifacts': []}
            if request.url.path == '/customnode/getmappings':
                payload = {'example-pack': [['ExampleNode'], {}]}
        return httpx.Response(status, json=payload, request=request)
    real_client = httpx.Client
    real_async_client = httpx.AsyncClient
    with patch('httpx.AsyncClient', side_effect=lambda **kwargs: real_async_client(transport=httpx.MockTransport(respond), **kwargs)), patch('httpx.Client', side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs)), patch('httpx.post', side_effect=lambda url, **kwargs: respond(httpx.Request('POST', url, json=kwargs.get('json')))):
        try:
            yield requests
        finally:
            get_mcp_settings.cache_clear()


async def call(name, args):
    result = await mcp.call_tool(name, args)
    assert isinstance(result, tuple), 'tools must expose structured content'
    blocks, structured = result
    assert json.loads(blocks[0].text) == structured
    return structured


@pytest.mark.parametrize('entry', INTENDED_TOOLS, ids=lambda entry: entry.name)
@pytest.mark.parametrize('failure', [None, 'http', 'connection'])
async def test_catalog_registered_success_failure_envelope(monkeypatch, entry, failure):
    tool = next(tool for tool in await mcp.list_tools() if tool.name == entry.name)
    kwargs = {}
    if failure == 'http': kwargs = {'status': 598, 'body': {'detail': 'unknown failure'}}
    if failure == 'connection': kwargs = {'exception': httpx.ConnectError('offline')}
    with transport(monkeypatch, **kwargs) as requests:
        payload = await call(entry.name, arguments_for(tool))
    assert requests, 'must execute a real wrapper dependency'
    if failure and entry.name == 'health':
        assert payload['ok'] is True
        assert set(payload['data']) == {'backend', 'comfyui', 'worker'}
        assert all(not item['reachable'] for item in payload['data'].values())
        assert payload['data']['comfyui']['reason_code'] == payload['data']['worker']['reason_code'] == 'not_observed'
        if failure == 'http': assert '598' in payload['data']['backend']['reason']
    elif failure:
        assert set(payload) == {'ok', 'error'}
        assert payload['ok'] is False
        assert all(payload['error'].get(key) for key in ('code', 'message', 'hint'))
        if failure == 'http': assert '598' in payload['error']['message']
    else:
        assert set(payload) == {'ok', 'data'}
        assert payload['ok'] is True


@pytest.mark.parametrize('name,args', [('job_status', {}), ('generate', {'mode': 'video'}), ('lora_train_start', {'folder': 'cup'})])
async def test_pre_body_validation_is_enveloped_and_no_http(monkeypatch, name, args):
    with transport(monkeypatch) as requests:
        payload = await call(name, args)
    assert not requests
    assert payload['ok'] is False
    assert payload['error']['code'] == 'request_validation_failed'
    assert payload['error']['hint']


@pytest.mark.parametrize('value', [{}, '', None, {'id': 'cup'}])
async def test_prompt_compose_legacy_save_presence_rejected_before_http(monkeypatch, value):
    with transport(monkeypatch) as requests:
        payload = await call('prompt_compose', {'save_as': value})
    assert not requests
    assert payload['error']['code'] == 'request_validation_failed'
    assert 'prompt_write(action=save)' in payload['error']['hint']


# Each merged branch crosses registration, dispatch, adapter and HTTP client.
MODES = [
    ('generate', {'mode': 'template', 'prompt': 'cup', 'execution_target': 'worker', 'loras': [], 'revision_context': {'request_ref': 'r', 'brief_revision': 'v2', 'parent_artifact_id': 9}}, 'POST', '/api/generate/', {'prompt': 'cup', 'batch_size': 1, 'execution_target': 'worker', 'loras': [], 'revision_context': {'request_ref': 'r', 'brief_revision': 'v2', 'parent_artifact_id': 9}}),
    ('generate', {'mode': 'custom_workflow', 'workflow': '{"1":{"class_type":"SaveImage"}}', 'prompt': 'cup', 'image': 'a.png', 'image_pose': 'p.png', 'mask': 'm.png', 'loras': [], 'execution_target': 'worker'}, 'POST', '/api/generate/custom', {'workflow': {'1': {'class_type': 'SaveImage'}}, 'prompt': 'cup', 'image': 'a.png', 'image_pose': 'p.png', 'mask': 'm.png', 'loras': [], 'execution_target': 'worker'}),
    ('gallery_get', {'image_id': 44}, 'GET', '/api/gallery/44', None),
    ('gallery_get', {'artifact_id': 9}, 'GET', '/api/gallery/artifacts/9', None),
    ('prompt_write', {'action': 'save', 'resource_type': 'combination', 'resource_id': 'cup', 'payload': {'positive': [], 'negative': []}, 'expected_revision': 0}, 'PUT', '/api/prompt-library/combinations/cup', {'positive': [], 'negative': [], 'expected_revision': 0}),
    ('prompt_write', {'action': 'archive', 'resource_type': 'entry', 'resource_id': 'cup', 'expected_revision': 2, 'expected_etag': 'e', 'polarity': 'positive', 'category_id': 'objects'}, 'POST', '/api/prompt-library/archive', {'resource_type': 'entry', 'resource_id': 'cup', 'expected_revision': 2, 'expected_etag': 'e', 'polarity': 'positive', 'category_id': 'objects'}),
    ('prompt_write', {'action': 'restore', 'resource_type': 'entry', 'resource_id': 'cup', 'expected_revision': 2, 'expected_etag': 'e', 'polarity': 'positive', 'category_id': 'objects'}, 'POST', '/api/prompt-library/restore', {'resource_type': 'entry', 'resource_id': 'cup', 'expected_revision': 2, 'expected_etag': 'e', 'polarity': 'positive', 'category_id': 'objects'}),
    ('style_preset_get', {}, 'GET', '/api/style-presets/', None),
    ('style_preset_get', {'preset_id': 'cup'}, 'GET', '/api/style-presets/cup', None),
    ('style_preset_save', {'from_source': 'fields', 'preset_id': 'cup', 'name': 'Cup', 'loras': []}, 'POST', '/api/style-presets/', {'id': 'cup', 'name': 'Cup', 'base_prompt': '', 'negative_prompt': '', 'template': None, 'checkpoint': None, 'lora': None, 'lora_strength': None, 'loras': [], 'diffusion_model': None, 'text_encoder': None, 'vae': None, 'default_params': {}, 'profiles': {}, 'overwrite': False}),
    ('style_preset_save', {'from_source': 'successful_job', 'preset_id': 'cup', 'source': 'job-1', 'prompt_keywords': ['cup'], 'negative_prompt_keywords': ['blur'], 'profile': 'portrait'}, 'POST', '/api/style-presets/cup/workflow/save', {'source': 'job-1', 'prompt_keywords': ['cup'], 'negative_prompt_keywords': ['blur'], 'profile': 'portrait'}),
    ('comfyui_admin', {'action': 'restart'}, 'POST', '/manager/reboot', {}),
    ('comfyui_admin', {'action': 'free_memory', 'unload_models': False}, 'POST', '/free', {'unload_models': False, 'free_memory': True}),
    ('comfyui_admin', {'action': 'install_node', 'node_class_names': ['ExampleNode']}, 'POST', '/manager/queue/install', {'id': 'example-pack', 'version': 'latest', 'selected_version': 'latest', 'channel': 'default', 'mode': 'cache', 'ui_id': 'example-pack'}),
]


@pytest.mark.parametrize('name,args,method,path,body', MODES, ids=[f'{name}-{args.get("mode", args.get("action", args.get("from_source", path)))}' for name,args,_,path,_ in MODES])
async def test_merged_modes_forward_exact_requests(monkeypatch, name, args, method, path, body):
    with transport(monkeypatch) as requests:
        payload = await call(name, args)
    assert payload['ok'] is True, payload
    matching = [request for request in requests if request.method == method and request.url.path == path]
    assert len(matching) == 1
    assert (json.loads(matching[0].content) if matching[0].content else None) == body
    if name == 'comfyui_admin':
        assert all(request.url.host == 'comfy.invalid' for request in requests)
        assert sum(request.url.path == '/manager/reboot' for request in requests) == (args['action'] == 'restart')


async def test_compose_then_write_preserves_fragments_metadata_provenance_and_conflict(monkeypatch):
    fragments = {'positive': [{'ref': {'polarity': 'positive', 'category_id': 'objects', 'entry_id': 'cup'}, 'snapshot': 'cup', 'weight': 1.2}, {'text': 'on table', 'weight': 0.9}], 'negative': [{'text': 'blur'}]}
    composed = {**fragments, 'positive_prompt': '(cup:1.2), (on table:0.9)', 'negative_prompt': 'blur'}
    with transport(monkeypatch, body=composed) as requests:
        result = await call('prompt_compose', fragments)
    assert result['ok'] is True
    assert len(requests) == 1
    assert json.loads(requests[0].content) == fragments
    assert 'save_as' not in json.loads(requests[0].content)
    saved = {key: result['data'][key] for key in ('positive', 'negative')}
    saved.update(name_zh='茶杯', description_zh='桌上的杯子', tags=['cup'], source_combination_id='source', document_context_token='ctx', literal_conversion_token='literal', provenance_resolutions=[{'ref': 'original'}])
    args = {'action': 'save', 'resource_type': 'combination', 'resource_id': 'cup', 'payload': saved, 'expected_revision': 7, 'expected_etag': 'etag-7'}
    for conflict in (None, 'revision_conflict', 'external_change'):
        detail = {'code': conflict, 'message': 'Changed', 'hint': 'Reload before saving.', 'details': {'expected_revision': 7, 'actual_revision': 8}}
        with transport(monkeypatch, status=409 if conflict else 200, body={'detail': detail} if conflict else {'revision': 8, 'etag': 'etag-8'}) as requests:
            result = await call('prompt_write', args)
        assert len(requests) == 1  # No overwrite or retry on conflict.
        assert requests[0].method == 'PUT'
        assert json.loads(requests[0].content) == {**saved, 'expected_revision': 7, 'expected_etag': 'etag-7'}
        if conflict:
            assert result['ok'] is False
            assert result['error']['code'] == conflict
            assert result['error']['hint'] == detail['hint']
            assert result['error']['details']['actual_revision'] == 8
        else:
            assert result['data']['revision'] == 8


@pytest.mark.parametrize('mode', ['template', 'custom_workflow'])
@pytest.mark.parametrize('loras', [None, [], [{'name': 'cup.safetensors', 'strength_model': 0.5, 'strength_clip': 0.3}]])
async def test_generate_preserves_omitted_empty_ordered_loras_and_graph_defaults(monkeypatch, mode, loras):
    args = {'mode': mode}
    if mode == 'custom_workflow': args['workflow'] = '{"1":{"inputs":{"seed":77,"steps":22}}}'
    if loras is not None: args['loras'] = loras
    with transport(monkeypatch) as requests:
        result = await call('generate', args)
    assert result['ok'] is True
    assert len(requests) == 1
    submitted = json.loads(requests[0].content)
    assert ('loras' in submitted) == (loras is not None)
    if loras is not None: assert submitted['loras'] == loras
    if mode == 'custom_workflow':
        assert submitted['workflow'] == {'1': {'inputs': {'seed': 77, 'steps': 22}}}
        assert not {'seed', 'steps', 'batch_size', 'cfg'} & set(submitted)


@pytest.mark.parametrize('name,args', [
    ('generate', {'mode': 'custom_workflow'}),
    ('generate', {'mode': 'custom_workflow', 'workflow': '{}', 'revision_context': {}}),
    ('generate', {'mode': 'template', 'workflow': '{}'}),
    ('gallery_get', {}), ('gallery_get', {'image_id': 1, 'artifact_id': 1}),
    ('prompt_write', {'action': 'archive', 'resource_type': 'entry', 'resource_id': 'x'}),
    ('prompt_write', {'action': 'restore', 'resource_type': 'combination', 'resource_id': 'x', 'expected_revision': 1, 'expected_etag': 'e'}),
    ('style_preset_save', {'from_source': 'successful_job', 'preset_id': 'x', 'source': 1, 'prompt_keywords': 'cup', 'overwrite': True}),
    ('comfyui_admin', {'action': 'install_node'}),
])
async def test_invalid_merged_inputs_fail_before_http(monkeypatch, name, args):
    with transport(monkeypatch) as requests:
        result = await call(name, args)
    assert result['ok'] is False
    assert not requests


@pytest.mark.parametrize('selector,path', [({'image_id': 44}, '/api/gallery/44'), ({'artifact_id': 9}, '/api/gallery/artifacts/9')])
async def test_gallery_keeps_namespaces_locators_metadata_and_lineage(monkeypatch, selector, path):
    context = {'request_ref': 'r', 'brief_revision': 'v2', 'parent_artifact_id': 9, 'artifact_id': 10}
    backend = {'id': next(iter(selector.values())), 'image_path': '2026/cup.png', 'image_url': '/gallery/2026/cup.png', 'local_path': '/host/gallery/clip.mp4', 'artifact_url': '/gallery/clip.mp4', 'artifact_type': 'video', 'mime_type': 'video/mp4', 'gallery_path': 'clip.mp4', 'file_size': 42, 'workflow_json': '{}', 'metadata_json': '{"seed":123}', 'seed': 9223372036854775806, 'revision_context': context}
    with transport(monkeypatch, body=backend) as requests:
        result = await call('gallery_get', selector)
    assert len(requests) == 1 and requests[0].url.path == path
    data = result['data']
    assert data['revision_context'] == context
    if 'image_id' in selector:
        assert data['image_id'] == 44 and 'artifact_id' not in data
        assert data['image_url'] == backend['image_url']
        assert data['local_path'] == str(Path('/fixture/gallery').resolve() / '2026/cup.png')
        assert data['metadata']['seed'] == backend['seed']
    else:
        assert data['artifact_id'] == 9 and 'image_id' not in data
        for key in ('artifact_type', 'mime_type', 'gallery_path', 'artifact_url', 'local_path', 'file_size'):
            assert data[key] == backend[key]
        assert data['workflow_metadata']['workflow_json'] == '{}'


@pytest.mark.parametrize('name,args', [('generate', {'mode': 'template'}), ('prompt_search', {}), ('style_preset_get', {}), ('style_preset_save', {'from_source': 'fields', 'preset_id': 'x', 'name': 'X'})])
async def test_structured_backend_code_hint_details_preserved(monkeypatch, name, args):
    detail = {'code': 'revision_conflict', 'message': 'Changed', 'hint': 'Reload exact revision.', 'details': {'actual_revision': 3}}
    with transport(monkeypatch, status=409, body={'detail': detail}) as requests:
        result = await call(name, args)
    assert len(requests) == 1
    assert result['error']['code'] == detail['code']
    assert result['error']['message'] == detail['message'] or result['error']['message'] == 'HTTP 409: Changed'
    assert result['error']['hint'] == detail['hint']
    assert result['error']['details']['actual_revision'] == 3


async def test_lora_uncertain_admission_keeps_canonical_job_and_no_resubmit(monkeypatch):
    with transport(monkeypatch, status=503, body={'detail': {'code': 'admission_uncertain', 'job_id': 'train-123'}}) as requests:
        result = await call('lora_train_start', ARGUMENTS['lora_train_start'])
    assert len(requests) == 1
    assert result['error']['code'] == 'admission_uncertain'
    assert result['error']['job_id'] == 'train-123'
    assert result['error']['details']['job_id'] == 'train-123'
    assert result['error']['details']['classification'] == 'admission_uncertain'
    assert 'do not resubmit' in result['error']['hint']


async def test_saved_graph_replay_forwards_only_locator_profile_target(monkeypatch):
    with transport(monkeypatch) as requests:
        result = await call('style_preset_test', {'preset_id': 'cup', 'profile': 'portrait', 'execution_target': 'worker'})
    assert result['data']['job_id'] == 'job-1'
    assert len(requests) == 1
    assert requests[0].url.path == '/api/style-presets/cup/workflow/test'
    assert json.loads(requests[0].content) == {'profile': 'portrait', 'execution_target': 'worker'}
    with transport(monkeypatch) as requests:
        result = await call('style_preset_test', {'preset_id': 'cup', 'overrides': {'seed': 3}})
    assert not requests and result['error']['code'] == 'request_validation_failed'


async def test_discord_forwards_alias_force_and_preserves_dedup_and_rejection(monkeypatch):
    args = {'job_id': 'job-1', 'destination_alias': 'project', 'force_resend': False}
    with transport(monkeypatch) as requests:
        result = await call('deliver_to_discord', args)
    assert result['data']['deduplicated'] is True
    assert json.loads(requests[0].content) == args
    with transport(monkeypatch, status=403, body={'error': {'code': 'destination_not_allowed', 'message': 'Use an allowed alias'}}) as requests:
        result = await call('deliver_to_discord', {**args, 'force_resend': True})
    assert len(requests) == 1
    assert json.loads(requests[0].content) == {**args, 'force_resend': True}
    assert result['error']['code'] == 'destination_not_allowed'
    assert result['error']['details']['status_code'] == 403
    with transport(monkeypatch) as requests:
        result = await call('deliver_to_discord', {**args, 'channel_id': 'arbitrary'})
    assert not requests and result['error']['code'] == 'request_validation_failed'


async def test_worker_failure_never_retries_or_falls_back(monkeypatch):
    with transport(monkeypatch, exception=httpx.ReadTimeout('admission unknown')) as requests:
        result = await call('generate', {'prompt': 'cup', 'execution_target': 'worker'})
    assert len(requests) == 1
    assert json.loads(requests[0].content)['execution_target'] == 'worker'
    assert result['error']['code'] == 'backend_unavailable'
    assert 'existing job ID' in result['error']['hint']


async def test_job_failure_preserves_domain_context_in_error_details(monkeypatch):
    backend = {'status': 'failed', 'error': 'worker offline', 'node_errors': [{'node_id': '1'}], 'recording_error': 'not recorded', 'revision_context': {'request_ref': 'r'}, 'revision_context_error': 'legacy'}
    with transport(monkeypatch, body=backend) as requests:
        result = await call('job_status', {'job_id': 'job-1'})
    assert len(requests) == 1 and requests[0].method == 'GET'
    assert result['error']['code'] == 'generation_failed'
    details = result['error']['details']
    assert details['job_id'] == 'job-1'
    for field in ('status', 'node_errors', 'recording_error', 'revision_context', 'revision_context_error'):
        assert details[field] == backend[field]


@pytest.mark.parametrize('args,path,params', [({}, '/api/prompt-library/catalog', {}), ({'category_id': 'objects', 'polarity': 'positive'}, '/api/prompt-library/categories/positive/objects', {}), ({'query': 'cup', 'polarity': 'positive', 'resource_types': ['entry'], 'include_archived': True, 'threshold': 60, 'limit': 7}, '/api/prompt-library/search', {'q': 'cup', 'polarity': 'positive', 'resource_types': 'entry', 'include_archived': 'true', 'threshold': '60', 'limit': '7'})])
async def test_prompt_search_preserves_catalog_category_and_query_modes(monkeypatch, args, path, params):
    with transport(monkeypatch) as requests:
        result = await call('prompt_search', args)
    assert result['ok'] is True
    assert len(requests) == 1 and requests[0].url.path == path
    assert dict(requests[0].url.params) == params


@pytest.mark.parametrize('args,path', [({'action': 'save', 'resource_type': 'category', 'resource_id': 'objects', 'polarity': 'positive', 'payload': {'name_zh': '物件'}}, '/api/prompt-library/categories/positive/objects'), ({'action': 'save', 'resource_type': 'entry', 'resource_id': 'cup', 'polarity': 'negative', 'category_id': 'objects', 'payload': {'name_zh': '杯子', 'prompt': 'cup'}, 'expected_revision': 2, 'expected_etag': 'e'}, '/api/prompt-library/categories/negative/objects/entries/cup')])
async def test_prompt_save_preserves_all_resource_locators(monkeypatch, args, path):
    with transport(monkeypatch) as requests:
        result = await call('prompt_write', args)
    assert result['ok'] is True
    assert len(requests) == 1 and requests[0].url.path == path
    assert json.loads(requests[0].content) == {**args['payload'], 'expected_revision': args.get('expected_revision', 0), **({'expected_etag': 'e'} if 'expected_etag' in args else {})}


async def test_lora_start_unknown_field_is_validated_before_http(monkeypatch):
    with transport(monkeypatch) as requests:
        result = await call('lora_train_start', {**ARGUMENTS['lora_train_start'], 'unsupported_option': 'value'})
    assert not requests
    assert result['error']['code'] == 'request_validation_failed'
