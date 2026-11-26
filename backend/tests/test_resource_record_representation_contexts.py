"""Y1: local one-level units remain recognizable under harmless contexts."""
import json
from pathlib import Path
from sqlalchemy import event
from app.db import database
from app.db.models import DownloadedResource
from app.services.resource_records import normalize_metadata, provider_snapshot
from app.schemas.resources import ResourceMetadata
from tests import test_resource_record_credential_values as values


import pytest
from tests.test_resource_record_writers import boundary
from app.services.resource_records import safe_text
from tests.test_resource_record_serialized_assignments import representations
def old_read_guard(client, tmp_path, monkeypatch, field, text):
    data = provider_snapshot({'baseModel':'Pony', 'trainedWords':['allowed']}, None, {}).model_dump()
    data['license']['values'] = {'allowNoCredit': True, 'hash': values.SAFE_HASH}
    data['source_evidence'] = {'path':'src/tokenizer.py'}
    values.put_field(data, field, text)
    raw = json.dumps(data)
    notes = '  {"historical":"exact evidence"} \n'
    model = tmp_path/'synthetic.safetensors'; model.write_bytes(b'synthetic')
    with database.SessionLocal() as db:
        row = DownloadedResource(resource_name='old serialized record', resource_type='lora',
            provider='civitai', source_url='unknown', status='installed', local_path=str(model),
            sha256=values.SAFE_HASH, metadata_json=raw, notes=notes)
        db.add(row); db.commit(); rid = row.id
    def deny(*args, **kwargs):
        raise AssertionError('unexpected old-read effect')
    from app.services import resource_records, resource_record_backfill, civitai_provider
    monkeypatch.setattr(resource_records, 'publish_metadata', deny)
    monkeypatch.setattr(resource_record_backfill, 'backfill_metadata', deny)
    monkeypatch.setattr(civitai_provider, 'ProviderOperation', deny)
    original_open = Path.open
    def guarded(path, *args, **kwargs):
        if path == model: return deny()
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded)
    statements = []
    def readonly(conn, cursor, sql, *args):
        statements.append(sql)
        assert sql.split()[0].upper() in {'SELECT','PRAGMA'}, sql
    event.listen(database.engine, 'before_cursor_execute', readonly)
    try:
        responses = [client.get(url) for url in [
            '/api/resources/'+str(rid), '/api/resources', '/api/civitai-recipes/local-ledger']]
        for response in responses: assert response.status_code == 200, response.text
        item, page, ledger = [r.json() for r in responses]
        assert page['items'] == [item] and page['total'] == 1
        assert ledger['entries'][0]['diagnostics']['resource_record'] == item
        assert item['resource_id'] == rid and item['sha256'] == values.SAFE_HASH
        assert item['license']['values']['hash'] == values.SAFE_HASH
        assert item['trigger_words'][0] == 'allowed'
        assert item['source_evidence']['path'] == 'src/tokenizer.py'
        family = client.get('/api/resources', params={'model_family':'sdxl','limit':1}).json()
        assert family['total'] == (0 if field == 'base_model' else 1)
        assert family['items'] == ([] if field == 'base_model' else [item])
        assert any('LIMIT' in sql and 'OFFSET' in sql for sql in statements)
        print('ALL_FIELD_PHASES_JSON='+json.dumps({'field':field,'detail':item,'list':page,'ledger':ledger,'filtered':family}))
        normalized = normalize_metadata(ResourceMetadata.model_validate(data))
        assert normalize_metadata(normalized) == normalized
        if field.endswith('_key'):
            for container in [item['license']['values'], item['recommended_parameters'], item['source_evidence']]:
                assert text not in container
        elif field == 'base_model': assert item['base_model'] == values.REDACTED
        elif field == 'license': assert item['license']['values']['description'] == values.REDACTED
        elif field == 'missing_field': assert item['license']['missing_fields'][-1] == values.REDACTED
        elif field == 'diagnostic_code': assert {'code':values.REDACTED, 'field':'provider_note'} in item['diagnostics']
        elif field == 'diagnostic_field': assert {'code':'provider_note', 'field':values.REDACTED} in item['diagnostics']
        elif field == 'trigger': assert item['trigger_words'][-1] == values.REDACTED
        elif field == 'recommendation_value': assert item['recommended_parameters']['sampler']['value'] == values.REDACTED
        elif field == 'recommendation_origin': assert item['recommended_parameters']['sampler']['source_field'] == values.REDACTED
        elif field == 'evidence': assert item['source_evidence']['nested'][0]['description'] == values.REDACTED
    finally:
        event.remove(database.engine, 'before_cursor_execute', readonly)
        with database.SessionLocal() as db:
            row = db.get(DownloadedResource, rid)
            assert row.metadata_json == raw and row.notes == notes

        print('STORAGE_EXACT=true;FIELD='+field)

SECRET = 'complete synthetic representation-context value; retained suffix'
LABELS = ['HTTP_AUTH"\\u004f"RIZATION', 'CIVITAI_API_"\\u004b"EY',
          'vendor.api."\\u006b"ey', 'provider\\u0020api\\u0020"\\u006b"ey']
CONTEXTS = [('', ''), ('ordinary "unfinished; ', '; useful suffix'),
            ("ordinary 'unfinished; ", "; 'suffix'"),
            ('ordinary "finished"; ', '; "ending"'),
            ('ordinary "finished"; "unfinished; ', '; "ending"'),
            ('ordinary \\"escaped; ', '; useful suffix')]
CONTEXTS += [('ordinary ' + "\\" * n + '"unfinished; ', '; "' + "\\" * n + 'useful suffix')
             for n in [1,2,3,4,5,7]]
PLAIN = [label + ' = "' + SECRET + '"' for label in LABELS]
ATTACKS = list(dict.fromkeys(prefix + encoded + suffix
    for plain in PLAIN for encoded in representations(plain)
    for prefix, suffix in CONTEXTS))
# Each representation/context has real provider/writer/old-field coverage.
BOUNDARY = list(dict.fromkeys(prefix + encoded + suffix
    for encoded in representations(PLAIN[0]) for prefix, suffix in CONTEXTS))

@pytest.mark.parametrize('text', ATTACKS)
def test_representation_context_recognition(text):
    assert safe_text(text) == values.REDACTED
    assert safe_text(safe_text(text)) == values.REDACTED

@pytest.mark.parametrize('text', BOUNDARY)
def test_representation_context_publication(client, text):
    values.test_complete_value_direct_publication_commit_reload_and_idempotence(client, text)

@pytest.mark.parametrize('text', BOUNDARY)
def test_representation_context_provider(boundary, text):
    values.test_complete_value_real_provider_inspect_select_acquire_background(boundary, text)

@pytest.mark.parametrize('text', BOUNDARY)
def test_representation_context_edited_install(boundary, text):
    values.test_complete_value_registered_edited_install_publication(boundary, text)

@pytest.mark.parametrize('text', BOUNDARY)
@pytest.mark.parametrize('field', values.FIELDS)
def test_representation_context_old_reads_finally(client, tmp_path, monkeypatch, field, text):
    old_read_guard(client, tmp_path, monkeypatch, field, text)

SAFE = [prefix + encoded + suffix
    for label in ['CIVITAI_API_"\\u004b"EYBOARD', 'vendor.to"\\u006b"enizer', 'pa"\\u0073"swordless']
    for encoded in representations(label + ' = "useful original"')
    for prefix, suffix in CONTEXTS]

@pytest.mark.parametrize('text', SAFE)
def test_representation_context_safe_original(client, text):
    from tests.test_resource_record_credential_labels import test_near_neighbor_metadata_and_keys_remain_useful
    test_near_neighbor_metadata_and_keys_remain_useful(client, text)
