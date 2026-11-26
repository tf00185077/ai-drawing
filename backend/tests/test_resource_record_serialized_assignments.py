"""W1-W3: once-serialized assignment text crosses real writer/read boundaries.

Only wire HTTP and scheduling use retained synthetic substitutes. Old storage is
checked in finally, including when a secrecy or read-only assertion is adverse.
"""
import json
from pathlib import Path

import pytest
from sqlalchemy import event
from app.db import database
from app.db.models import DownloadedResource
from app.services.resource_records import normalize_metadata, provider_snapshot, safe_text
from app.schemas.resources import ResourceMetadata
from tests.test_resource_record_writers import boundary
from tests import test_resource_record_credential_values as values
from tests.test_resource_record_terminal_escapes import description


def representations(text):
    serialized = json.dumps(text)
    return [text, serialized, serialized[1:-1]]


PLAIN = [
    f'{q} {label} {q} {delimiter} {q}complete synthetic value; suffix{q}'
    for q in ['"', "'"] for delimiter in [':', '=']
    for label in ['CIVITAI_API_KEY', 'HTTP_AUTHORIZATION', 'provider\tapi\tkey']
] + [
    '" provider\\u0020api\\u0020key " = "complete synthetic value"',
    "' providerApiKey ' : 'complete synthetic value'",
    '"ordinary" = "useful"; " 資源.api.key\u2003" = "complete synthetic value"',
    "ordinary prefix; ' HTTP_AUTHORIZATION ' : Basic b3BhcXVl",
]
ATTACKS = [encoded for text in PLAIN for encoded in representations(text)]


@pytest.mark.parametrize('text', ATTACKS)
def test_serialized_assignment_publication(client, text):
    values.test_complete_value_direct_publication_commit_reload_and_idempotence(client, text)


@pytest.mark.parametrize('text', ATTACKS)
def test_serialized_assignment_provider(boundary, text):
    values.test_complete_value_real_provider_inspect_select_acquire_background(boundary, text)


@pytest.mark.parametrize('text', ATTACKS)
def test_serialized_assignment_edited_install_and_new_notes(boundary, text):
    values.test_complete_value_registered_edited_install_publication(boundary, text)


@pytest.mark.parametrize('text', representations(PLAIN[0]) + representations(PLAIN[6]))
@pytest.mark.parametrize('field', values.FIELDS)
def test_serialized_assignment_old_reads_finally(client, tmp_path, monkeypatch, field, text):
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
        family = client.get('/api/resources', params={'model_family':'sdxl','limit':1}).json()
        assert family['total'] == (0 if field == 'base_model' else 1)
        assert family['items'] == ([] if field == 'base_model' else [item])
        assert any('LIMIT' in sql and 'OFFSET' in sql for sql in statements)
    finally:
        event.remove(database.engine, 'before_cursor_execute', readonly)
        with database.SessionLocal() as db:
            row = db.get(DownloadedResource, rid)
            assert row.metadata_json == raw and row.notes == notes


@pytest.mark.parametrize('text', ATTACKS)
def test_serialized_assignment_key_text_consistency(text):
    from app.services.resource_records import safe_evidence
    assert safe_evidence({text: 'excluded', 'description': text, 'hash': values.SAFE_HASH}) == {
        'description': values.REDACTED, 'hash': values.SAFE_HASH}


SAFE = [
    '" api_keyboard " = "useful value"', "' tokenizer ' : 'ordinary description'",
    '"API_KEY documentation"', 'path C:\\tools\\assets; ordinary text',
    '"ordinary description" = "cookie cutter"', '"ordinary" : "basic painting"',
    '"secretariat" = "useful"', '"passwordless" = "ordinary"',
]


@pytest.mark.parametrize('text', [encoded for text in SAFE for encoded in representations(text)])
def test_serialized_safe_neighbors_keep_original_representation(client, text):
    from tests.test_resource_record_credential_labels import test_near_neighbor_metadata_and_keys_remain_useful
    test_near_neighbor_metadata_and_keys_remain_useful(client, text)


@pytest.mark.timeout(3)
@pytest.mark.parametrize('quote', ['"', "'"])
@pytest.mark.parametrize('outer', [False, True])
def test_serialized_ordinary_description_bound_and_content(client, quote, outer):
    from tests.test_resource_record_credential_labels import test_near_neighbor_metadata_and_keys_remain_useful
    raw = description(quote, "\\")
    assert len(raw) == 92001
    serialized = json.dumps(raw)
    text = serialized if outer else serialized[1:-1]
    test_near_neighbor_metadata_and_keys_remain_useful(client, text)
