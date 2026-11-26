"""X1-X3: unrelated prose quotes cannot consume explicit label boundaries."""
import json
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

SECRET = 'complete synthetic quote-context value; retained suffix'
PLAIN = [f'{q}{label}{q}{delimiter}{q}{SECRET}{q}'
         for q in ['"', "'"]
         for label in [' CIVITAI_API_KEY ', '\tHTTP_AUTHORIZATION\t',
                       ' vendor.api.key\u2003', ' serviceApiKey ',
                       r' provider\u0020api\u0020key ']
         for delimiter in [' = ', '\t:\n']]
CONTEXTS = [('', ''), ('ordinary "unfinished; ', '; useful suffix'),
            ("ordinary 'unfinished; ", '; useful suffix'),
            ('ordinary "finished"; "unfinished; ', '; "ending"'),
            ("ordinary 'finished'; 'unfinished; ", "; 'ending'"),
            ('ordinary \\"escaped; ', '; useful suffix'),
            ("ordinary \\'escaped; ", '; useful suffix'),
            ('ordinary "\'mixed; ', '; useful suffix')]
ATTACKS = list(dict.fromkeys(prefix + encoded + suffix for plain in PLAIN
                           for encoded in representations(plain)
                           for prefix, suffix in CONTEXTS))
# Real boundaries cover both quotes, every representation and odd/even/escaped
# prose, in addition to the broader inexpensive recognition metamorphic guard.
BOUNDARY = list(dict.fromkeys(prefix + encoded + suffix
    for plain in [PLAIN[0], PLAIN[10]]
    for encoded in representations(plain)
    for prefix, suffix in CONTEXTS))

@pytest.mark.parametrize('text', ATTACKS)
def test_quote_context_complete_value_recognition(text):
    assert safe_text(text) == values.REDACTED
    assert safe_text(safe_text(text)) == values.REDACTED

@pytest.mark.parametrize('text', BOUNDARY)
def test_quote_context_publication(client, text):
    values.test_complete_value_direct_publication_commit_reload_and_idempotence(client, text)

@pytest.mark.parametrize('text', BOUNDARY)
def test_quote_context_provider(boundary, text):
    values.test_complete_value_real_provider_inspect_select_acquire_background(boundary, text)

@pytest.mark.parametrize('text', BOUNDARY)
def test_quote_context_edited_install(boundary, text):
    values.test_complete_value_registered_edited_install_publication(boundary, text)

@pytest.mark.parametrize('text', BOUNDARY)
@pytest.mark.parametrize('field', values.FIELDS)
def test_quote_context_old_reads(client, tmp_path, monkeypatch, field, text):
    old_read_guard(client, tmp_path, monkeypatch, field, text)

SAFE = [prefix + encoded + suffix
        for plain in ['" api_keyboard " = "useful value"', "' tokenizer ' : 'ordinary'",
                      '"ordinary" : "basic painting"', "'secretariat' = 'useful'"]
        for encoded in representations(plain) for prefix, suffix in CONTEXTS]

@pytest.mark.parametrize('text', SAFE)
def test_quote_context_safe_original(client, text):
    safe_original_guard(client, text)

@pytest.mark.timeout(3)
@pytest.mark.parametrize('quote', ['"', "'"])
@pytest.mark.parametrize('representation', ['literal', 'serialized', 'escaped'])
def test_dense_odd_quote_description_retains_content(client, quote, representation):
    raw = quote + (quote + 'ordinary description ') * 4000 + '\\'
    text = raw if representation == 'literal' else json.dumps(raw)
    if representation == 'escaped': text = text[1:-1]
    safe_original_guard(client, text)
