"""Offline CIV-C resource-identity resolution contract tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.schemas.generation_recipe import RecipeResource
from app.services.civitai_resource_resolution import (
    LocalResourceLedgerEntry,
    resolve_recipe_resources,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resource(**overrides: object) -> RecipeResource:
    payload: dict[str, object] = {
        "kind": "lora",
        "name": "mutable-name.safetensors",
        "civitai_model_id": 10,
        "civitai_model_version_id": 20,
        "civitai_file_id": 30,
        "air": "urn:air:sd1:lora:civitai:10@20",
        "sha256": "a" * 64,
    }
    payload.update(overrides)
    return RecipeResource.model_validate(payload)


def _ledger(path: Path, data: bytes, **overrides: object) -> LocalResourceLedgerEntry:
    path.write_bytes(data)
    payload: dict[str, object] = {
        "kind": "lora",
        "local_path": path,
        "sha256": _sha(data),
        "civitai_model_id": 10,
        "civitai_model_version_id": 20,
        "civitai_file_id": 30,
        "air": "urn:air:sd1:lora:civitai:10@20",
        "availability": True,
    }
    payload.update(overrides)
    return LocalResourceLedgerEntry(**payload)


def test_unique_intersection_and_verified_file_create_an_ordered_resource_lock(tmp_path: Path) -> None:
    data = b"verified model"
    resource = _resource(sha256=_sha(data))
    entry = _ledger(tmp_path / "local-name.safetensors", data)

    report = resolve_recipe_resources([resource], [entry], strict=True)

    assert report.ready is True
    assert [item.status for item in report.entries] == ["resolved"]
    assert report.entries[0].local_path == str(entry.local_path)
    assert report.entries[0].matched_by == [
        "civitai_model_id", "civitai_model_version_id", "civitai_file_id", "air", "sha256",
    ]
    assert report.resource_lock == [{
        "index": 0,
        "kind": "lora",
        "local_path": str(entry.local_path),
        "sha256": _sha(data),
        "civitai_model_id": 10,
        "civitai_model_version_id": 20,
        "civitai_file_id": 30,
        "air": "urn:air:sd1:lora:civitai:10@20",
    }]


def test_identity_conflict_is_mismatch_while_multiple_full_matches_are_ambiguous(tmp_path: Path) -> None:
    data = b"same digest"
    resource = _resource(sha256=_sha(data))
    mismatch = _ledger(tmp_path / "wrong-file.safetensors", data, civitai_file_id=999)
    mismatch_report = resolve_recipe_resources([resource], [mismatch], strict=True)
    assert mismatch_report.entries[0].status == "mismatch"
    assert mismatch_report.ready is False
    assert mismatch_report.resource_lock == []

    first = _ledger(tmp_path / "first.safetensors", data)
    second = _ledger(tmp_path / "second.safetensors", data)
    ambiguous_report = resolve_recipe_resources([resource], [first, second], strict=False)
    assert ambiguous_report.entries[0].status == "ambiguous"
    assert ambiguous_report.ready is True
    assert ambiguous_report.resource_lock == []


def test_filename_only_resource_is_missing_and_never_lockable(tmp_path: Path) -> None:
    data = b"filename is not identity"
    resource = _resource(
        civitai_model_id=None,
        civitai_model_version_id=None,
        civitai_file_id=None,
        air=None,
        sha256=None,
    )
    entry = _ledger(tmp_path / "same-name.safetensors", data)

    report = resolve_recipe_resources([resource], [entry], strict=False)

    assert report.entries[0].status == "missing"
    assert report.ready is True
    assert report.resource_lock == []


def test_missing_hash_or_unverified_disk_hash_never_enters_resource_lock_even_non_strict(tmp_path: Path) -> None:
    data = b"disk bytes"
    no_hash_resource = _resource(sha256=None)
    entry = _ledger(tmp_path / "candidate.safetensors", data)
    report = resolve_recipe_resources([no_hash_resource], [entry], strict=False)
    assert report.entries[0].status == "resolved"
    assert report.ready is True
    assert report.resource_lock == []

    expected = _sha(b"expected")
    mismatch_resource = _resource(sha256=expected)
    tampered = _ledger(tmp_path / "tampered.safetensors", data, sha256=expected)
    mismatch_report = resolve_recipe_resources([mismatch_resource], [tampered], strict=False)
    assert mismatch_report.entries[0].status == "mismatch"
    assert mismatch_report.resource_lock == []


def test_strict_requires_all_resources_available_and_hash_verified_but_preserves_ordered_diagnostics(tmp_path: Path) -> None:
    first_data = b"first"
    second_data = b"second"
    resources = [_resource(sha256=_sha(first_data)), _resource(name="second.safetensors", sha256=_sha(second_data))]
    first = _ledger(tmp_path / "first.safetensors", first_data)
    unavailable = _ledger(tmp_path / "second.safetensors", second_data, availability=False)

    strict = resolve_recipe_resources(resources, [first, unavailable], strict=True)
    relaxed = resolve_recipe_resources(resources, [first, unavailable], strict=False)

    assert [entry.status for entry in strict.entries] == ["resolved", "unavailable"]
    assert strict.ready is False
    assert [lock["index"] for lock in strict.resource_lock] == [0]
    assert relaxed.ready is True
    assert [lock["index"] for lock in relaxed.resource_lock] == [0]


def test_serialized_report_redacts_authorization_and_token_from_ledger_diagnostics(tmp_path: Path) -> None:
    secret = "RESOLUTION_TEST_TOKEN"
    data = b"verified"
    resource = _resource(sha256=_sha(data))
    ledger = _ledger(tmp_path / "resource.safetensors", data, diagnostics={"Authorization": f"Bearer {secret}", "nested": {"token": secret}})

    report = resolve_recipe_resources([resource], [ledger], strict=True)

    assert secret not in json.dumps(report.to_dict(), sort_keys=True)


def test_hash_identity_is_case_insensitive_and_explicit_secret_values_are_redacted(tmp_path: Path) -> None:
    secret = "UNKEYED_RESOLUTION_TOKEN"
    data = b"verified"
    resource = _resource(sha256=_sha(data))
    ledger = _ledger(
        tmp_path / "upper.safetensors", data,
        sha256=_sha(data).upper(), diagnostics={"note": f"transport said {secret}"},
    )

    report = resolve_recipe_resources([resource], [ledger], strict=True, secrets=(secret,))

    assert report.ready is True
    assert report.entries[0].status == "resolved"
    assert secret not in json.dumps(report.to_dict(), sort_keys=True)
