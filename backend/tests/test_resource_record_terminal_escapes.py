"""V1/V3: restoring suffix-retry scanning stalls real provider and stored reads.

Keep the existing three-second bound and exact complete ordinary values. External
HTTP/scheduling use the retained synthetic fixture; domain/schema/ORM/HTTP are real.
"""
import json

import pytest
from sqlalchemy import event

from app.db import database
from app.db.models import DownloadedResource
from app.schemas.resources import ResourceMetadata
from app.services.resource_records import normalize_metadata, provider_snapshot, publish_metadata
from tests.test_resource_record_writers import boundary
from tests import test_resource_record_credential_values as values


def description(quote, suffix, count=4000):
    return ('\\' + quote + 'ordinary description ') * count + suffix


# Terminal escape parity and matched/unmatched tails share the same input format.
SUFFIXES = ['\\', '\\\\', '\\\\\\', 'tail', 'tail"', "tail'", '\\\\tail']


@pytest.mark.timeout(3)
@pytest.mark.parametrize('quote', ['"', "'"])
@pytest.mark.parametrize('suffix', SUFFIXES)
def test_terminal_description_provider_publication_orm_detail(client, quote, suffix):
    text = description(quote, suffix)
    snapshot = provider_snapshot({'baseModel': 'Pony', 'trainedWords': ['allowed']},
                                 {'license': {'description': text}}, {})
    assert snapshot.license.values['model_license']['description'] == text
    with database.SessionLocal() as db:
        row = DownloadedResource(resource_name='ordinary description', resource_type='lora',
                                 source_url='unknown', status='planned')
        db.add(row); db.flush(); resource_id = row.id
        publish_metadata(row, snapshot); db.commit(); db.expire_all()
        raw = db.get(DownloadedResource, resource_id).metadata_json
        assert json.loads(raw)['license']['values']['model_license']['description'] == text
        assert normalize_metadata(ResourceMetadata.model_validate_json(raw)).model_dump_json() == raw
    response = client.get('/api/resources/' + str(resource_id))
    assert response.status_code == 200, response.text
    assert response.json()['license']['values']['model_license']['description'] == text


@pytest.mark.timeout(3)
@pytest.mark.parametrize('quote', ['"', "'"])
@pytest.mark.parametrize('suffix', SUFFIXES)
def test_terminal_description_registered_provider_inspect(boundary, quote, suffix):
    b = boundary
    text = description(quote, suffix)
    b.file['license'] = {'description': text}
    response = b.client.post('/api/civitai-recipes/resource-inspect', json={
        'locator': 'https://civitai.com/models/10?modelVersionId=21'})
    assert response.status_code == 200, response.text
    assert response.json()['candidates'][-1]['license']['description'] == text


@pytest.mark.timeout(3)
@pytest.mark.parametrize('route', ['detail', 'list', 'ledger'])
@pytest.mark.parametrize('quote', ['"', "'"])
@pytest.mark.parametrize('suffix', ['\\', '\\\\', '\\\\\\', 'tail'])
def test_terminal_description_stored_reads_readonly(client, tmp_path, monkeypatch, route, quote, suffix):
    text = description(quote, suffix)
    data = provider_snapshot({'baseModel': 'Pony', 'trainedWords': ['allowed']}, None, {}).model_dump()
    data['license']['values'] = {'description': text, 'hash': 'a' * 64}
    model = tmp_path / 'synthetic-only.safetensors'
    model.write_bytes(b'synthetic')
    notes = '  {"old":"preserve"} \n'
    raw = json.dumps(data)
    with database.SessionLocal() as db:
        row = DownloadedResource(resource_name='ordinary description', resource_type='lora',
            provider='civitai', source_url='unknown', status='installed', local_path=str(model),
            sha256='a'*64, notes=notes, metadata_json=raw)
        db.add(row); db.commit(); resource_id = row.id
    def deny(*args, **kwargs):
        raise AssertionError('unexpected stored-read side effect')
    from pathlib import Path
    from app.services import resource_records, resource_record_backfill, civitai_provider
    monkeypatch.setattr(resource_records, 'publish_metadata', deny)
    monkeypatch.setattr(resource_record_backfill, 'backfill_metadata', deny)
    monkeypatch.setattr(civitai_provider, 'ProviderOperation', deny)
    original_open = Path.open
    def guarded(path, *args, **kwargs):
        if path == model:
            return deny()
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded)
    def readonly(conn, cursor, sql, *args):
        assert sql.split()[0].upper() in {'SELECT', 'PRAGMA'}, sql
    event.listen(database.engine, 'before_cursor_execute', readonly)
    try:
        url = {'detail': '/api/resources/' + str(resource_id), 'list': '/api/resources',
               'ledger': '/api/civitai-recipes/local-ledger'}[route]
        response = client.get(url)
        assert response.status_code == 200, response.text
        body = response.json()
        item = body if route == 'detail' else body['items'][0] if route == 'list' else body['entries'][0]['diagnostics']['resource_record']
        assert item['license']['values'] == {'description': text, 'hash': 'a'*64}
        assert item['resource_id'] == resource_id and item['trigger_words'] == ['allowed']
    finally:
        event.remove(database.engine, 'before_cursor_execute', readonly)
        with database.SessionLocal() as db:
            row = db.get(DownloadedResource, resource_id)
            assert row.notes == notes and row.metadata_json == raw


@pytest.mark.timeout(3)
@pytest.mark.parametrize('count', [250, 500, 1000, 2000, 4000, 8000])
@pytest.mark.parametrize('quote', ['"', "'"])
def test_increasing_terminal_descriptions_retain_exact_content(client, count, quote):
    from tests.test_resource_record_credential_labels import test_near_neighbor_metadata_and_keys_remain_useful
    test_near_neighbor_metadata_and_keys_remain_useful(client, description(quote, '\\', count))


@pytest.mark.parametrize('text', [
    '" ordinary " = "useful\\\\"; " CIVITAI_API_KEY " = "full value"\\',
    "'ordinary prefix; \" HTTP_AUTHORIZATION \" = Basic b3BhcXVl'\\",
    '" provider\\u0020api\\u0020key " = "full value"\\\\',
    "' provider\\tapi\\tkey ' : 'full value'\\\\\\",
])
def test_terminal_neighbors_cannot_hide_complete_credentials(client, text):
    values.test_complete_value_direct_publication_commit_reload_and_idempotence(client, text)


@pytest.mark.timeout(3)
@pytest.mark.parametrize('quote', ['"', "'"])
@pytest.mark.parametrize('escapes', [1, 2, 3])
def test_serialized_terminal_descriptions_remain_complete(client, quote, escapes):
    from tests.test_resource_record_credential_labels import test_near_neighbor_metadata_and_keys_remain_useful
    text = json.dumps(description(quote, "\\" * escapes))
    test_near_neighbor_metadata_and_keys_remain_useful(client, text)
