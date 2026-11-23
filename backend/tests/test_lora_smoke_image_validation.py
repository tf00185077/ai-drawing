"""Recover corrupt image candidates through real scratch HTTP/DB/Gallery.

The two tiny PNGs are unchanged AID-23 QA fixtures, not generated artwork.
"""
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import struct

from PIL import Image, ImageFile
import pytest

from app.core import queue
from app.db.models import LoraTrainingJob
from app.services import lora_smoke
from tests.test_lora_delivery import write_lora
from tests.test_lora_smoke_reconciliation import smoke


FIXTURES = Path(__file__).parent / 'fixtures' / 'lora_smoke'


def corrupt_bytes(good, defect):
    if defect != 'checksum-only':
        return (FIXTURES / (defect + '.png')).read_bytes()
    # Keep pixels valid but break IDAT's CRC: load() alone would accept this.
    data = bytearray(good)
    pos = 8
    while pos < len(data):
        size = struct.unpack('>I', data[pos:pos + 4])[0]
        if data[pos + 4:pos + 8] == b'IDAT':
            data[pos + 8 + size] ^= 1
            return bytes(data)
        pos += size + 12
    raise AssertionError('fixture has no IDAT')


def training_fields(w):
    with w.sessions() as db:
        row = db.query(LoraTrainingJob).one()
        return {c.name: getattr(row, c.name) for c in row.__table__.columns
                if not c.name.startswith('smoke_test_') and c.name != 'updated_at'}


def request(w, kind, artifact=None, ids=(None, None)):
    url = '/api/lora-train/jobs/train-1'
    response = (w.client.get(url) if kind == 'status' else
                w.client.post(url + '/smoke-test', json={'prompt': 'changed', 'execution_target': 'worker'}))
    assert response.status_code == 200, response.text
    payload = response.json()
    prefix = 'smoke_test_' if kind == 'status' else ''
    state = 'completed' if artifact else 'artifact_unavailable'
    assert payload['smoke_test_status'] == state
    assert payload['smoke_test_job_id' if kind == 'status' else 'generation_job_id'] == 'gen-1'
    assert payload[prefix + 'artifact'] == artifact
    assert (payload[prefix + 'image_id'], payload[prefix + 'artifact_id']) == ids
    assert payload['registered_lora_name'] == 'products/旅人_002.safetensors'
    sha = None
    if artifact:
        assert payload[prefix + 'artifact_url'] == '/gallery/' + artifact
        retrieved = w.client.get(payload[prefix + 'artifact_url'])
        assert retrieved.status_code == 200
        assert retrieved.content == (w.root / artifact).read_bytes()
        with Image.open(BytesIO(retrieved.content)) as image:
            image.load()
        sha = hashlib.sha256(retrieved.content).hexdigest()
        assert payload[prefix + 'error_code'] is None
    else:
        assert payload[prefix + 'artifact_url'] is None
        assert payload[prefix + 'error_code'] == 'smoke_artifact_unavailable'
        assert payload[prefix + 'error'] and payload[prefix + 'hint']
    assert str(w.root.parent) not in response.text
    assert not queue.get_status()['queue_pending']
    with w.sessions() as db:
        row = db.query(LoraTrainingJob).one()
        assert row.smoke_test_status == state and row.smoke_test_artifact == artifact
        assert row.smoke_test_job_id == 'gen-1'
    out = os.environ.get('SMOKE_IMAGE_HTTP_FIXTURE_OUT')
    if out:
        path = Path(out)
        records = json.loads(path.read_text()) if path.exists() else []
        records.append({'kind': kind, 'state': state, 'payload': payload,
                        'artifact': artifact, 'image_id': ids[0], 'artifact_id': ids[1],
                        'gallery_sha256': sha})
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2))


@pytest.mark.parametrize('defect', ['corrupt-crc', 'undecodable', 'checksum-only'])
@pytest.mark.parametrize('first', ['status', 'smoke'])
@pytest.mark.parametrize('previous', ['submitted', 'completed'])
def test_corrupt_images_reconcile_and_restore_without_resubmission(smoke, defect, first, previous):
    ids = smoke.image('first.png')
    path = smoke.root / 'first.png'
    good = path.read_bytes()
    path.write_bytes(corrupt_bytes(good, defect))
    smoke.update(smoke_test_status=previous,
                 smoke_test_artifact='first.png' if previous == 'completed' else None)
    before = training_fields(smoke)
    # Synthetic training final/parameter documents: smoke reads must preserve bytes.
    run = smoke.root.parent / 'train' / before['run_locator']
    run.mkdir(parents=True)
    final = run / '旅人_002.safetensors'
    write_lora(final)
    params = run / 'training-parameters.json'
    params.write_text(before['params_json'])
    readable = run / 'training-parameters.md'
    readable.write_text('# 旅人_002\n\nmodel_family: sdxl\ncheckpoint: base.safetensors\n')
    originals = {p: p.read_bytes() for p in (final, params, readable)}
    other = 'smoke' if first == 'status' else 'status'
    for kind in (first, other, first):
        request(smoke, kind)
    # Restore only bytes, retaining DB/artifact/image/job identities and claim.
    path.write_bytes(good)
    for kind in (first, other):
        request(smoke, kind, 'first.png', ids)
    assert training_fields(smoke) == before
    assert {p: p.read_bytes() for p in originals} == originals


@pytest.mark.parametrize('defect', ['corrupt-crc', 'undecodable', 'checksum-only'])
@pytest.mark.parametrize('first', ['status', 'smoke'])
def test_invalid_first_candidate_falls_through_to_next_exact_job_image(smoke, defect, first):
    smoke.image('first.png')
    ids = smoke.image('second.png')
    smoke.image('third.png')
    smoke.image('newer-unrelated.png', 'other-job')
    path = smoke.root / 'first.png'
    bad = corrupt_bytes(path.read_bytes(), defect)
    path.write_bytes(bad)
    smoke.update(smoke_test_status='completed', smoke_test_artifact='first.png')
    before = training_fields(smoke)
    for kind in (first, 'smoke' if first == 'status' else 'status'):
        request(smoke, kind, 'second.png', ids)
    assert path.read_bytes() == bad  # Candidate selection never repairs/deletes images.
    assert training_fields(smoke) == before


def test_png_fixtures_distinguish_checksum_validation_from_pixel_decoding(smoke):
    smoke.image('good.png')
    good = (smoke.root / 'good.png').read_bytes()
    assert ImageFile.LOAD_TRUNCATED_IMAGES is False
    with Image.open(BytesIO(corrupt_bytes(good, 'checksum-only'))) as image:
        image.load()
    with Image.open(FIXTURES / 'undecodable.png') as image:
        image.verify()
    with Image.open(FIXTURES / 'undecodable.png') as image:
        with pytest.raises(OSError):
            image.load()
    for defect in ('corrupt-crc', 'checksum-only'):
        with Image.open(BytesIO(corrupt_bytes(good, defect))) as image:
            with pytest.raises(SyntaxError):
                image.verify()


def test_unknown_programming_errors_are_not_classified_as_bad_images(smoke, monkeypatch):
    smoke.image('good.png')
    def broken(*args, **kwargs):
        raise RuntimeError('programming failure')
    monkeypatch.setattr(Image, 'open', broken)
    with pytest.raises(RuntimeError, match='programming failure'):
        lora_smoke._image_file(smoke.root.resolve(), 'good.png')


def test_decompression_bomb_protection_is_retained(smoke, monkeypatch):
    smoke.image('large.png')
    monkeypatch.setattr(Image, 'MAX_IMAGE_PIXELS', 1)
    assert lora_smoke._image_file(smoke.root.resolve(), 'large.png') is False
