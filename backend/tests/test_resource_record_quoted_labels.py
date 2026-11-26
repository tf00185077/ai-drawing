"""U1-U3: reviewed quoted-label extraction leaks at actual writer/read boundaries.

Restoring the restricted quoted-label parser must fail these feature assertions.
External HTTP/scheduling substitutes are inherited; Settings/resolver/ORM are real.
"""
import json

import pytest
from app.services.resource_records import credential_label, safe_evidence, safe_text
from tests.test_resource_record_writers import boundary
from tests import test_resource_record_credential_labels as labels
from tests import test_resource_record_credential_values as values

LABELS = [
    ' CIVITAI_API_KEY ', ' HTTP_AUTHORIZATION ', 'provider\tapi\tkey ',
    '\tX-Api-Key\t', '\u2003serviceAccessToken\u3000', '\nremote.password\r',
    ' provider.api.key ', ' provider-api-key ', ' provider api key ',
    ' \t服务_API_KEY\t ', ' APP__TOKEN_2 ', ' v2.AUTHORIZATION ',
]
# Matching lexical units: both quotes and delimiters; literal and JSON-serialized
# forms (including escaped tabs/newlines/Unicode). No expected value uses policy.
ASSIGNMENTS = [f'{quote}{label}{quote} {delimiter} "synthetic full value; later suffix"'
               for label in LABELS for quote, delimiter in [('"', '='), ("'", ':')]]
ASSIGNMENTS += [json.dumps(label) + '\t:\u2003"synthetic full value; later suffix"'
                for label in LABELS]
ASSIGNMENTS += [
    "' HTTP_AUTHORIZATION ' = Basic b3BhcXVlUUEx",
    'prefix; " CIVITAI_API_KEY "\n:\t"synthetic full value; later suffix"; safe tail',
    '"provider\\u0009api\\u0009key\\u0020"="synthetic full value; later suffix"',
    "'provider\\tapi\\tkey ' = 'synthetic full value; later suffix'",
    '"provider\\u005fapi\\u005fkey "="synthetic full value; later suffix"',
    '"provider\\\" api key "="synthetic full value; later suffix"',
    "'provider\\' api key ' = 'synthetic full value; later suffix'",
    # The complete quoted value cannot conceal a recognizable inner assignment.
    '\"description: CIVITAI_API_KEY=synthetic full value; later suffix\"',
]


@pytest.mark.parametrize('text', ASSIGNMENTS)
def test_quoted_direct_publication_commit_reload_idempotent(client, text):
    values.test_complete_value_direct_publication_commit_reload_and_idempotence(client, text)


@pytest.mark.parametrize('text', ASSIGNMENTS)
def test_quoted_registered_edited_install(boundary, text):
    values.test_complete_value_registered_edited_install_publication(boundary, text)


@pytest.mark.parametrize('text', ASSIGNMENTS)
def test_quoted_provider_inspect_select_acquire_background(boundary, text):
    values.test_complete_value_real_provider_inspect_select_acquire_background(boundary, text)


@pytest.mark.parametrize('text', ASSIGNMENTS)
@pytest.mark.parametrize('field', values.FIELDS)
def test_quoted_old_storage_all_fields_readonly(client, tmp_path, monkeypatch, field, text):
    values.test_complete_value_old_storage_detail_list_ledger_readonly(client, tmp_path, monkeypatch, field, text)


@pytest.mark.parametrize('label', LABELS)
def test_quoted_key_text_consistency(label):
    assert credential_label(label)
    assert safe_evidence({label:'synthetic full value', 'tokenizer':'useful'}) == {'tokenizer':'useful'}
    for text in [json.dumps(label), '"'+label+'"', "'"+label+"'"]:
        for delimiter in [':', '=']:
            assert safe_text(text+delimiter+'"synthetic full value"') == '[redacted credential]'


@pytest.mark.parametrize('label', LABELS)
def test_quoted_keys_real_publication_and_reads(client, tmp_path, label):
    labels.test_credential_dictionary_keys_share_assignment_policy(client, tmp_path, label)


SAFE = [
    '" tokenizer " = useful', "'api_keyboard' : useful", '" passwordless "=useful',
    '"secretariat" : useful', '"credentialed"=useful', '"signaturelike"=useful',
    '" CIVITAI_API_KEY " documentation without assignment',
    "' HTTP_AUTHORIZATION ' ordinary documentation", 'ordinary "quoted text" remains useful',
    '"safe label" = "safe value"', '"safe label" = "a \\\"quoted\\\" value"',
    '"unterminated ordinary label', "'ordinary mismatched quote\" = useful",
    '" api_keyboard\\t " = useful', '" description " = "basic painting"',
]


@pytest.mark.parametrize('text', SAFE)
def test_quoted_safe_neighbors_retain_useful_metadata(client, text):
    labels.test_near_neighbor_metadata_and_keys_remain_useful(client, text)


@pytest.mark.timeout(3)
@pytest.mark.parametrize('fragment', ['ordinary description ', '"ordinary description" ', '"unterminated ordinary description '])
def test_quoted_long_descriptions_have_bounded_scanning(client, fragment):
    labels.test_near_neighbor_metadata_and_keys_remain_useful(client, (fragment*4000).rstrip())


@pytest.mark.timeout(3)
@pytest.mark.parametrize('quote', ['"', "'"])
def test_escaped_unmatched_long_description_consumes_tail_once(client, quote):
    labels.test_near_neighbor_metadata_and_keys_remain_useful(
        client, ('\\'+quote+'ordinary description ')*4000+'tail')


@pytest.mark.parametrize('text', [
    '\"ordinary prefix; \' HTTP_AUTHORIZATION \' = Basic b3BhcXVlUUEx\"',
    "'ordinary prefix; \" CIVITAI_API_KEY \" = synthetic full value; later suffix'",
])
def test_nested_opposite_quote_label_publication(client, text):
    values.test_complete_value_direct_publication_commit_reload_and_idempotence(client, text)
