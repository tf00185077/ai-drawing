"""Unrelated terminal escapes cannot hide an unchanged explicit quoted label."""
import pytest
from app.services.resource_records import safe_text
from tests.test_resource_record_writers import boundary
from tests import test_resource_record_credential_values as values
from tests.test_resource_record_serialized_assignments import (
    representations, test_serialized_assignment_old_reads_finally as old_read_guard,
)
from tests.test_resource_record_credential_labels import (
    test_near_neighbor_metadata_and_keys_remain_useful as safe_original_guard,
)
TEXTS = [encoded for quote in ['"', "'"] for count in [0, 1, 2, 3, 4, 5, 7]
         for encoded in representations('ordinary prefix; ' + '\\' * count + quote +
             ' CIVITAI_API_KEY ' + quote + ' = ' + quote +
             'complete synthetic value; retained suffix' + quote)]

@pytest.mark.parametrize('text', TEXTS)
def test_quote_prefix_complete_value(text):
    assert safe_text(text) == values.REDACTED

@pytest.mark.parametrize('text', TEXTS)
def test_quote_prefix_publication(client, text):
    values.test_complete_value_direct_publication_commit_reload_and_idempotence(client, text)

@pytest.mark.parametrize('text', TEXTS)
def test_quote_prefix_provider(boundary, text):
    values.test_complete_value_real_provider_inspect_select_acquire_background(boundary, text)

@pytest.mark.parametrize('text', TEXTS)
@pytest.mark.parametrize('field', values.FIELDS)
def test_quote_prefix_old_reads(client, tmp_path, monkeypatch, field, text):
    old_read_guard(client, tmp_path, monkeypatch, field, text)

SAFE = [text.replace(' CIVITAI_API_KEY ', ' api_keyboard ') for text in TEXTS]

@pytest.mark.parametrize('text', SAFE)
def test_quote_prefix_safe_original(client, text):
    safe_original_guard(client, text)
