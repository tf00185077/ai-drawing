"""Closed LoRA diagnostic matrix through real HttpBackendClient, fake HTTP only."""
import copy
import json
import random
from unittest.mock import patch
import httpx
import pytest
from mcp_server.client import HttpBackendClient
from mcp_server.tools import lora_train


def invoke(payload, status=200, raw=None):
    transport=httpx.MockTransport(lambda req: httpx.Response(status,json=payload) if raw is None else httpx.Response(status,text=raw))
    original=httpx.Client
    with patch.object(lora_train,'_get_client',return_value=HttpBackendClient('http://fixture.invalid/api')),patch('httpx.Client',side_effect=lambda **kw: original(transport=transport,**kw)):
        return lora_train.lora_train_job_status('fixture')


def failure(details,shape):
    detail={'code':'recipe_validation_failed','message':'untrusted diagnostic','details':details}
    return invoke({'detail':detail},400) if shape=='http-error' else invoke({'ok':False,'error_code':'recipe_validation_failed','details':details})


def assert_failure(result):
    assert result['ok'] is False
    assert result['error']['code'] and result['error']['message'] and result['error']['hint']
    assert result['classification'] and result['phase']


@pytest.mark.parametrize('shape',['http-error','ok-false'])
def test_known_semantic_diagnostics_remain_useful(shape):
    details={'issues':[{'field':'recipe.optimization.optimizer_args','location':['body','recipe','optimization','optimizer_args',0], 'type':'invalid_value','code':'recipe_validation_failed','suggestion':'optimizer_args',
                       'constraints':{'max_length':64,'min_length':1,'ge':0,'lt':512,'multiple_of':1},'accepted_forms':['optimizerArgs','optimizer_args'],'accepted_values':['fp16','bf16'],'fields':['dataset.batch_size']}],
             'validation_errors':[{'loc':['body','recipe','dataset','batch_size'],'type':'greater_than_equal','ctx':{'ge':1}}],
             'fields':['output_name'],'accepted_fields':['batch_size'],'accepted_forms':['JSON object','JSON-object string'],'accepted_values':['sd15','sdxl','anima']}
    result=failure(details,shape);assert_failure(result)
    assert result['error']['details']==details


@pytest.mark.parametrize('shape',['http-error','ok-false'])
@pytest.mark.parametrize('slot',['field','location','path','type','code','suggestion','accepted_forms','accepted_values','fields','accepted_fields','constraint-key','constraint-value','validation-loc','validation-type','validation-ctx','root-fields','root-forms','root-values','root-accepted-fields'])
def test_unknown_identifier_shaped_strings_are_not_semantic_authority(shape,slot):
    sentinel=''.join(random.Random('aid16-'+slot).choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_',k=37))
    issue={'field':'recipe.optimization.optimizer_args','type':'invalid_value'}
    details={'issues':[issue]}
    if slot=='constraint-key':issue['constraints']={sentinel:2}
    elif slot=='constraint-value':issue['constraints']={'max_length':sentinel}
    elif slot.startswith('validation-'):
        key=slot.split('-')[1];details['validation_errors']=[{'loc':['body',sentinel]} if key=='loc' else {'type':sentinel} if key=='type' else {'ctx':{'ge':sentinel}}]
    elif slot.startswith('root-'):
        key={'fields':'fields','forms':'accepted_forms','values':'accepted_values','accepted-fields':'accepted_fields'}[slot[5:]];details[key]=[sentinel]
    else:issue[slot]=[sentinel] if slot in {'accepted_forms','accepted_values','fields','accepted_fields'} else sentinel
    result=failure(details,shape)
    assert sentinel not in json.dumps(result)
    assert_failure(result)
    assert result['error']['details']['issues'][0]['field']=='recipe.optimization.optimizer_args' if slot!='field' else result['error']['details']['issues'][0]['type']=='invalid_value'


@pytest.mark.parametrize('shape',['http-error','ok-false'])
@pytest.mark.parametrize('key,value',[('max_length','64'),('max_length',True),('max_length',1.5),('max_length',-1),('max_length',2**40),('ge',False),('ge','1'),('ge',10**400),('ge',float('inf')),('ge',float('nan')),('multiple_of',0),('min_length',[]),('expected','UnknownIdentifier16')])
def test_constraint_types_and_ranges_are_enforced(shape,key,value):
    # JSON permits no NaN/Inf on the wire: malformed numeric values become strings.
    if isinstance(value,float) and value!=value or value==float('inf'):
        value=str(value)
    details={'issues':[{'field':'output_name','constraints':{key:value}}],'validation_errors':[{'loc':['body','output_name'],'ctx':{key:value}}]}
    result=failure(details,shape)
    assert 'constraints' not in result['error']['details']['issues'][0]
    assert 'ctx' not in result['error']['details']['validation_errors'][0]
    assert_failure(result)


@pytest.mark.parametrize('shape',['http-error','ok-false'])
@pytest.mark.parametrize('details',[None,[],True,'MalformedIdentifier16',{'issues':['MalformedIdentifier16',None,[],{'field':{},'constraints':[]}],'validation_errors':[42,{'loc':['body',True]},{'loc':['body',-1]},{'loc':['body',2**40]}],'fields':{},'accepted_values':[{}]}])
def test_malformed_details_preserve_nonempty_failure(shape,details):
    result=failure(copy.deepcopy(details),shape);assert_failure(result)
    assert 'MalformedIdentifier16' not in json.dumps(result)
    assert 'true' not in json.dumps(result['error']['details']).lower()


@pytest.mark.parametrize('status',[400,422,500])
def test_raw_nonjson_failure_never_echoes_body(status):
    result=invoke(None,status,raw='RawPrivateIdentifier16 /private/raw')
    assert_failure(result);assert 'RawPrivateIdentifier16' not in json.dumps(result)


def test_list_validation_and_unknown_code_have_safe_fallback():
    result=invoke({'detail':[{'loc':['body','output_name'],'type':'string_too_long','ctx':{'max_length':64},'msg':'PrivateMessage16','input':'PrivateMessage16'}]},422)
    assert_failure(result)
    assert result['error']['details']['validation_errors']==[{'loc':['body','output_name'],'type':'string_too_long','ctx':{'max_length':64}}]
    result=invoke({'ok':False,'error_code':'UnknownCode16','errors':[{'field':'output_name','type':'missing','suggestion':'UnknownSuggestion16'}]})
    assert_failure(result);assert result['error']['code']=='backend_failed'
    assert 'Unknown' not in json.dumps(result)


@pytest.mark.parametrize('location',[['body','recipe','dataset','batch_size',1], 'recipe.model.family[0]', ['body','recipe','optimization','optimizer_args',-1], 'recipe.optimization.optimizer_args[1000001]'])
@pytest.mark.parametrize('shape',['http-error','ok-false'])
def test_indices_only_extend_known_collection_fields(shape,location):
    result=failure({'issues':[{'type':'invalid_value','location':location}]},shape)
    assert_failure(result)
    assert 'location' not in result['error']['details']['issues'][0]


@pytest.mark.parametrize('field',['optimizer_args','lr_scheduler_args'])
@pytest.mark.parametrize('value',[{'private':'MalformedOption16'},'MalformedOption16',[True,{},['MalformedOption16']]])
def test_malformed_option_shapes_redact_in_independent_mcp(field,value):
    payload={'job_id':'fixture','status':'failed','requested_recipe':{'optimization':{field:value}},'effective_recipe':{'optimization':{field:value}}}
    before=copy.deepcopy(payload);result=invoke(payload)
    assert result['ok'] is True and result['status']=='failed'
    assert 'MalformedOption16' not in json.dumps(result)
    assert result['requested_recipe']['optimization'][field] and 'redacted' in str(result['requested_recipe']['optimization'][field])
    assert payload==before


@pytest.mark.parametrize('shape',['http-error','ok-false'])
def test_known_literal_expectation_is_retained(shape):
    result=failure({'validation_errors':[{'loc':['body','recipe','model','family'],'type':'literal_error','ctx':{'expected':"'sd15', 'sdxl' or 'anima'"}}]},shape)
    assert result['error']['details']['validation_errors'][0]['ctx']=={'expected':"'sd15', 'sdxl' or 'anima'"}
    assert_failure(result)


def test_preflight_keeps_executable_start_payload_separate_from_display():
    start={'folder':'fixture','output_name':'旅人','recipe':{'optimization':{'optimizer_args':['unknown=PrivateInput16']}}}
    payload={'decision':'train','start_payload':start,'requested_recipe':start['recipe']}
    original=httpx.Client;transport=httpx.MockTransport(lambda req:httpx.Response(200,json=payload))
    with patch.object(lora_train,'_get_client',return_value=HttpBackendClient('http://fixture.invalid/api')),patch('httpx.Client',side_effect=lambda **kw:original(transport=transport,**kw)):
        result=lora_train.lora_training_decision_preflight('fixture',output_name='旅人')
    assert result['ok'] is True and result['start_payload']==start
    assert 'PrivateInput16' not in json.dumps(result['requested_recipe'])
