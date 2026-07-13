"""CIV-V-D offline inspect/select/install contracts (RED before implementation)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import DownloadedResource


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture() -> dict:
    return json.loads((Path(__file__).parent / "fixtures" / "civitai" / "resource_inspect_model.json").read_text())


def test_resource_inspect_is_canonical_and_redacts_secret_url() -> None:
    from app.services.civitai_resource_install import inspect_civitai_resource

    first = inspect_civitai_resource(_fixture())
    second = inspect_civitai_resource(_fixture())
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(second, sort_keys=True, separators=(",", ":"))
    assert [item["civitai_file_id"] for item in first["candidates"]] == [11, 12]
    assert first["candidates"][0]["sha256"] == "a" * 64
    assert "TOKEN_SENTINEL" not in json.dumps(first)
    assert first["candidates"][0]["license"]["name"] == "test-license"
    assert [(item["civitai_model_id"], item["civitai_model_version_id"], item["civitai_file_id"]) for item in first["candidates"]] == [(101, 201, 11), (101, 201, 12)]


def test_resource_inspect_normalizes_authoritative_public_model_policy_fields() -> None:
    """CIV-V-H-R2: normalize the fields emitted by Civitai's real model API."""
    from app.services.civitai_resource_install import inspect_civitai_resource, select_civitai_resource

    payload = _fixture()
    candidate = payload["modelVersions"][0]["files"][0]
    candidate.pop("availability")
    candidate.pop("license")
    candidate.pop("usage")
    payload.update({
        "availability": "Public",
        "allowNoCredit": True,
        "allowCommercialUse": "{RentCivit,Image,Rent}",
        "allowDerivatives": True,
        "allowDifferentLicense": True,
    })

    inspected = inspect_civitai_resource(payload)
    normalized = inspected["candidates"][0]

    assert normalized["availability"] is True
    assert normalized["license"] == {
        "source": "civitai_model_permissions",
        "allow_no_credit": True,
        "allow_different_license": True,
    }
    assert normalized["usage_restrictions"] == {
        "allow_commercial_use": ["Image", "Rent", "RentCivit"],
        "allow_derivatives": True,
    }
    assert select_civitai_resource(inspected, {"civitai_file_id": 11})["status"] == "completed"


@pytest.mark.parametrize("field,value", [
    ("allowNoCredit", None),
    ("allowNoCredit", "true"),
    ("allowCommercialUse", []),
    ("allowCommercialUse", "Image"),
    ("allowCommercialUse", [" "]),
    ("allowCommercialUse", ["Image", 1]),
    ("allowDerivatives", "true"),
    ("allowDifferentLicense", None),
])
def test_resource_inspect_model_policy_requires_explicit_complete_typed_values(field: str, value: object) -> None:
    """CIV-V-H-R2-AC1: absent/malformed model policy cannot satisfy selection gates."""
    from app.services.civitai_resource_install import inspect_civitai_resource, select_civitai_resource

    payload = _fixture()
    candidate = payload["modelVersions"][0]["files"][0]
    candidate.pop("availability")
    candidate.pop("license")
    candidate.pop("usage")
    payload.update({
        "availability": "Public",
        "allowNoCredit": True,
        "allowCommercialUse": ["Image"],
        "allowDerivatives": True,
        "allowDifferentLicense": True,
        field: value,
    })

    inspected = inspect_civitai_resource(payload)
    normalized = inspected["candidates"][0]

    assert normalized["availability"] is True
    assert normalized["license"] is None
    assert normalized["usage_restrictions"] is None
    result = select_civitai_resource(inspected, {"civitai_file_id": 11})
    assert result == {"status": "blocked", "diagnostic": {"code": "unsafe_metadata", "reason": "unsafe_metadata"}}


def test_model_version_payload_preserves_distinct_model_version_and_file_ids() -> None:
    from app.services.civitai_resource_install import inspect_civitai_resource

    version = _fixture()["modelVersions"][0]
    version["model"] = {"id": 101}
    inspected = inspect_civitai_resource(version)

    assert [(item["civitai_model_id"], item["civitai_model_version_id"], item["civitai_file_id"]) for item in inspected["candidates"]] == [(101, 201, 11), (101, 201, 12)]


def test_selection_fails_closed_before_transport_or_database_side_effects() -> None:
    from app.services.civitai_resource_install import inspect_civitai_resource, select_civitai_resource

    inspected = inspect_civitai_resource(_fixture())
    for selectors, code in [
        ({"resource_kind": "lora"}, "ambiguous"),
        ({"civitai_file_id": 999}, "not_found"),
        ({"civitai_file_id": 11, "civitai_model_id": 999}, "conflicting_identity"),
        ({"civitai_file_id": 12}, "unsafe_metadata"),
    ]:
        result = select_civitai_resource(inspected, selectors)
        assert result["status"] == "blocked"
        assert result["diagnostic"]["code"] == code


@pytest.mark.parametrize("mutation", [
    lambda candidate: candidate.pop("name"),
    lambda candidate: candidate.__setitem__("unexpected", "forged"),
    lambda candidate: candidate.__setitem__("civitai_file_id", "11"),
    lambda candidate: candidate.__setitem__("download_url_identity", "https://evil.example/file"),
    lambda candidate: candidate.__setitem__("name", "../escape.safetensors"),
])
def test_selection_revalidates_forged_candidate_before_returning_descriptor(mutation) -> None:
    """CIV-V-D-AC2: select must not launder a hand-crafted inspect payload."""
    from app.services.civitai_resource_install import inspect_civitai_resource, select_civitai_resource

    inspected = inspect_civitai_resource(_fixture())
    candidate = inspected["candidates"][0]
    mutation(candidate)

    result = select_civitai_resource(inspected, {"civitai_file_id": 11})

    assert result["status"] == "blocked"
    assert result["diagnostic"]["code"] == "unsafe_metadata"


def test_resource_requests_are_strictly_typed_at_backend_boundary() -> None:
    """CIV-V-D-AC7: no generic mappings or extra properties cross the HTTP boundary."""
    from pydantic import ValidationError
    from app.schemas.civitai_recipes import CivitaiResourceInstallRequest, CivitaiResourceSelectRequest
    from app.services.civitai_resource_install import inspect_civitai_resource

    inspected = inspect_civitai_resource(_fixture())
    selected = inspected["candidates"][0]
    with pytest.raises(ValidationError):
        CivitaiResourceSelectRequest.model_validate({
            "inspect": {**inspected, "extra": True},
            "selectors": {"civitai_file_id": 11, "token": "TOKEN_SENTINEL"},
        })
    with pytest.raises(ValidationError):
        CivitaiResourceInstallRequest.model_validate({
            "selected": {**selected, "unexpected": True}, "storage_root": "loras", "overwrite": False,
        })
    with pytest.raises(ValidationError):
        CivitaiResourceInstallRequest.model_validate({
            "selected": {**selected, "civitai_file_id": "11", "byte_size": "1024"},
            "storage_root": "loras", "overwrite": False,
        })


def test_install_redacts_secret_bearing_license_evidence_before_persistence(tmp_path: Path) -> None:
    from app.services.civitai_resource_install import install_civitai_resource

    data = b"verified install"
    selected = {**_selected(data), "license": {"proof_url": "https://example.invalid/license?token=TOKEN_SENTINEL"}}
    with _session(tmp_path)() as db:
        result = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": tmp_path / "loras"}, transport=_Transport(data))
        row = db.query(DownloadedResource).one()

    assert result["status"] == "completed"
    assert "TOKEN_SENTINEL" not in json.dumps(result)
    assert "TOKEN_SENTINEL" not in row.notes
    assert "proof_url" in row.notes


def _selected(data: bytes) -> dict:
    from app.services.civitai_resource_install import inspect_civitai_resource, select_civitai_resource

    fixture = _fixture()
    fixture["modelVersions"][0]["files"][0]["hashes"]["SHA256"] = _sha(data)
    fixture["modelVersions"][0]["files"][0]["sizeKB"] = len(data) / 1024
    return select_civitai_resource(inspect_civitai_resource(fixture), {"civitai_file_id": 11})["selected"]


class _Transport:
    def __init__(self, data: bytes): self.data, self.calls = data, []
    def get(self, url, *, headers=None):
        from app.services.civitai_safe_download import DownloadResponse
        self.calls.append((url, headers))
        return DownloadResponse(200, self.data)


def _session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'install.db'}")
    DownloadedResource.__table__.create(engine)
    return sessionmaker(bind=engine)


def test_install_uses_safe_download_and_publishes_ledger_only_after_verified_file(tmp_path: Path) -> None:
    from app.services.civitai_resource_install import install_civitai_resource

    data = b"verified install"
    selected = _selected(data)
    Session = _session(tmp_path)
    with Session() as db:
        result = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": tmp_path / "loras"}, transport=_Transport(data))
        assert result["status"] == "completed"
        assert Path(result["final_path"]).read_bytes() == data
        row = db.query(DownloadedResource).one()
        assert (row.provider, row.status, row.civitai_file_id, row.sha256) == ("civitai", "installed", "11", _sha(data))


def test_install_rejects_forged_or_incomplete_descriptor_before_transport(tmp_path: Path) -> None:
    from app.services.civitai_resource_install import install_civitai_resource

    data = b"verified install"
    selected = _selected(data)
    invalid = [
        {key: value for key, value in selected.items() if key != "sha256"},
        {**selected, "download_url_identity": "https://evil.example/file"},
        {**selected, "download_url_identity": "https://civitai.com/api/download/models/11?token=TOKEN_SENTINEL"},
        {**selected, "unexpected": "field"},
        {**selected, "name": "../escape.safetensors"},
    ]
    Session = _session(tmp_path)
    for descriptor in invalid:
        transport = _Transport(data)
        with Session() as db:
            result = install_civitai_resource(descriptor, "loras", db=db, storage_roots={"loras": tmp_path / "loras"}, transport=transport)
            assert result["status"] == "blocked"
            assert transport.calls == []
            assert db.query(DownloadedResource).count() == 0


def test_existing_final_blocks_before_transport_and_database_mutation(tmp_path: Path) -> None:
    from app.services.civitai_resource_install import install_civitai_resource

    data = b"verified install"
    selected = _selected(data)
    final = tmp_path / "loras" / selected["name"]
    final.parent.mkdir()
    final.write_bytes(b"existing-final")
    transport = _Transport(data)
    with _session(tmp_path)() as db:
        result = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": tmp_path / "loras"}, transport=transport)
        assert result["status"] == "blocked"
        assert result["diagnostic"]["code"] == "already_exists"
        assert final.read_bytes() == b"existing-final"
        assert transport.calls == []
        assert db.query(DownloadedResource).count() == 0


def test_existing_exact_file_is_adopted_without_transport_and_is_idempotent(tmp_path: Path) -> None:
    """CIV-V-H-R1-AC1: an exact canonical final is ledger-adopted, never downloaded."""
    from app.services.civitai_resource_install import install_civitai_resource

    data = b"existing physical Civitai file"
    selected = _selected(data)
    root = tmp_path / "loras"
    final = root / selected["name"]
    final.parent.mkdir()
    final.write_bytes(data)
    transport = _Transport(b"transport must never be read")
    Session = _session(tmp_path)

    with Session() as db:
        first = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": root}, transport=transport)
        first_row = db.query(DownloadedResource).one()
        second = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": root}, transport=transport)
        rows = db.query(DownloadedResource).all()

    assert first["status"] == second["status"] == "completed"
    assert first["final_path"] == second["final_path"] == str(final)
    assert first["sha256"] == second["sha256"] == selected["sha256"]
    assert first["byte_size"] == second["byte_size"] == len(data)
    assert transport.calls == []
    assert final.read_bytes() == data
    assert len(rows) == 1
    assert rows[0].id == first_row.id
    assert (rows[0].provider, rows[0].model_id, rows[0].version_id, rows[0].civitai_file_id, rows[0].sha256, rows[0].local_path) == (
        "civitai", "101", "201", "11", selected["sha256"], str(final),
    )


@pytest.mark.parametrize("existing_kind,contents", [
    ("mismatch", b"wrong existing bytes"),
    ("symlink", b""),
    ("directory", b""),
])
def test_existing_adverse_targets_have_zero_transport_file_or_ledger_side_effects(
    tmp_path: Path, existing_kind: str, contents: bytes,
) -> None:
    """CIV-V-H-R1-AC2: non-adoptable finals retain the old already_exists fail-closed result."""
    from app.services.civitai_resource_install import install_civitai_resource

    data = b"expected existing physical file"
    selected = _selected(data)
    root = tmp_path / "loras"
    final = root / selected["name"]
    root.mkdir()
    outside = tmp_path / "outside"
    if existing_kind == "symlink":
        outside.write_bytes(b"outside must remain unchanged")
        final.symlink_to(outside)
    elif existing_kind == "directory":
        final.mkdir()
    else:
        final.write_bytes(contents)
    before = outside.read_bytes() if outside.exists() else None
    transport = _Transport(b"transport must never be read")

    with _session(tmp_path)() as db:
        result = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": root}, transport=transport)
        assert result == {"status": "blocked", "diagnostic": {"code": "already_exists"}}
        assert transport.calls == []
        assert db.query(DownloadedResource).count() == 0

    assert final.is_symlink() if existing_kind == "symlink" else final.exists()
    if before is not None:
        assert outside.read_bytes() == before


@pytest.mark.parametrize("field,value", [
    ("scan_status", "unknown"),
    ("availability", False),
    ("license", None),
    ("download_url_identity", "https://civitai.com/api/download/models/11?token=TOKEN_SENTINEL"),
])
def test_existing_unsafe_metadata_remains_redacted_and_side_effect_free(tmp_path: Path, field: str, value: object) -> None:
    """CIV-V-H-R1-AC2: descriptor gates run before any existing-file adoption."""
    from app.services.civitai_resource_install import install_civitai_resource

    data = b"expected existing physical file"
    selected = {**_selected(data), field: value}
    root = tmp_path / "loras"
    final = root / selected["name"]
    final.parent.mkdir()
    final.write_bytes(data)
    transport = _Transport(b"transport must never be read")

    with _session(tmp_path)() as db:
        result = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": root}, transport=transport)
        assert result["status"] == "blocked"
        assert transport.calls == []
        assert db.query(DownloadedResource).count() == 0

    assert final.read_bytes() == data
    assert "TOKEN_SENTINEL" not in json.dumps(result)


def test_existing_exact_file_with_conflicting_ledger_identity_is_side_effect_free(tmp_path: Path) -> None:
    """CIV-V-H-R1-AC2: adoption never launders a pre-existing conflicting identity."""
    from app.services.civitai_resource_install import install_civitai_resource

    data = b"expected existing physical file"
    selected = _selected(data)
    root = tmp_path / "loras"
    final = root / selected["name"]
    final.parent.mkdir()
    final.write_bytes(data)
    transport = _Transport(b"transport must never be read")
    with _session(tmp_path)() as db:
        conflict = DownloadedResource(
            resource_name="conflict.safetensors", resource_type="lora", provider="civitai",
            source_url="https://civitai.com/api/download/models/999", status="installed",
            civitai_file_id=str(selected["civitai_file_id"]), model_id="999", version_id="998",
            sha256="f" * 64, local_path=str(tmp_path / "elsewhere"),
        )
        db.add(conflict)
        db.commit()
        before = (conflict.model_id, conflict.version_id, conflict.sha256, conflict.local_path)
        result = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": root}, transport=transport)
        after = db.query(DownloadedResource).one()

    assert result == {"status": "blocked", "diagnostic": {"code": "already_exists"}}
    assert transport.calls == []
    assert (after.model_id, after.version_id, after.sha256, after.local_path) == before
    assert final.read_bytes() == data


def test_ledger_commit_failure_removes_only_new_publication_and_row(tmp_path: Path, monkeypatch) -> None:
    from app.services.civitai_resource_install import install_civitai_resource

    data = b"verified install"
    selected = _selected(data)
    Session = _session(tmp_path)
    with Session() as db:
        monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(RuntimeError("TOKEN_SENTINEL")))
        result = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": tmp_path / "loras"}, transport=_Transport(data), authorization="Bearer TOKEN_SENTINEL")
        assert result["status"] == "failed"
        assert result["diagnostic"]["code"] == "ledger_persistence_failed"
        assert "TOKEN_SENTINEL" not in json.dumps(result)
        assert not (tmp_path / "loras" / selected["name"]).exists()
        assert db.query(DownloadedResource).count() == 0


@pytest.mark.parametrize("field,value", [
    ("sha256", None), ("byte_size", None), ("byte_size", 0),
    ("scan_status", "unknown"), ("availability", False),
])
def test_unsafe_metadata_matrix_blocks_before_transport_and_db(tmp_path: Path, field, value) -> None:
    from app.services.civitai_resource_install import install_civitai_resource
    data = b"verified install"; descriptor = {**_selected(data), field: value}; transport = _Transport(data)
    with _session(tmp_path)() as db:
        result = install_civitai_resource(descriptor, "loras", db=db, storage_roots={"loras": tmp_path / "loras"}, transport=transport)
        assert result["status"] == "blocked"
        assert transport.calls == []
        assert db.query(DownloadedResource).count() == 0


@pytest.mark.parametrize("storage_root", ["checkpoints", "/absolute", "../escape"])
def test_kind_root_and_caller_path_matrix_blocks_before_transport(tmp_path: Path, storage_root) -> None:
    from app.services.civitai_resource_install import install_civitai_resource
    data = b"verified install"; transport = _Transport(data)
    with _session(tmp_path)() as db:
        result = install_civitai_resource(_selected(data), storage_root, db=db, storage_roots={storage_root: tmp_path / "other"}, transport=transport)
        assert result["status"] == "blocked"
        assert transport.calls == []
        assert db.query(DownloadedResource).count() == 0


@pytest.mark.parametrize("body,status", [(b"server error", 500), (b"wrong-size", 200), (b"same length bad!", 200)])
def test_http_size_sha_failures_leave_no_final_or_ledger(tmp_path: Path, body: bytes, status: int) -> None:
    from app.services.civitai_resource_install import install_civitai_resource
    from app.services.civitai_safe_download import DownloadResponse
    expected = b"verified install"; selected = _selected(expected)
    class Transport(_Transport):
        def get(self, url, *, headers=None):
            self.calls.append((url, headers)); return DownloadResponse(status, body)
    transport = Transport(body)
    with _session(tmp_path)() as db:
        result = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": tmp_path / "loras"}, transport=transport)
        assert result["status"] == "failed"
        assert not (tmp_path / "loras" / selected["name"]).exists()
        assert db.query(DownloadedResource).count() == 0


def test_symlink_part_fails_without_transport_final_or_ledger(tmp_path: Path) -> None:
    from app.services.civitai_resource_install import install_civitai_resource
    data = b"verified install"; selected = _selected(data); root = tmp_path / "loras"; root.mkdir()
    outside = tmp_path / "outside"; outside.write_bytes(b"do-not-touch")
    (root / (selected["name"] + ".part")).symlink_to(outside)
    transport = _Transport(data)
    with _session(tmp_path)() as db:
        result = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": root}, transport=transport)
        assert result["status"] == "failed"
        assert transport.calls == []
        assert outside.read_bytes() == b"do-not-touch"
        assert not (root / selected["name"]).exists()
        assert db.query(DownloadedResource).count() == 0


def test_successful_install_is_visible_in_backend_owned_ledger(tmp_path: Path) -> None:
    from app.services.civitai_local_identity_ledger import ledger_payload, local_identity_ledger
    from app.services.civitai_resource_install import install_civitai_resource
    data = b"verified install"; selected = _selected(data)
    with _session(tmp_path)() as db:
        result = install_civitai_resource(selected, "loras", db=db, storage_roots={"loras": tmp_path / "loras"}, transport=_Transport(data))
        snapshot = ledger_payload(local_identity_ledger(db))
        assert result["status"] == "completed"
        assert len(snapshot["entries"]) == 1
        entry = snapshot["entries"][0]
        assert entry["civitai_file_id"] == selected["civitai_file_id"]
        assert entry["sha256"] == selected["sha256"]
        assert entry["availability"] is True


def test_installed_audited_model_family_reaches_strict_resolution_lock(tmp_path: Path) -> None:
    """Provider metadata persisted at install remains audited compatibility evidence."""
    from app.schemas.generation_recipe import RecipeResource
    from app.services.civitai_local_identity_ledger import local_identity_ledger
    from app.services.civitai_resource_install import install_civitai_resource
    from app.services.civitai_resource_resolution import resolve_recipe_resources

    data = b"audited illustrious checkpoint"
    selected = {**_selected(data), "resource_kind": "checkpoint", "model_family": "Illustrious"}
    with _session(tmp_path)() as db:
        result = install_civitai_resource(
            selected, "checkpoints", db=db,
            storage_roots={"checkpoints": tmp_path / "checkpoints"}, transport=_Transport(data),
        )
        report = resolve_recipe_resources([
            RecipeResource.model_validate({
                "kind": "checkpoint", "name": selected["name"], "sha256": selected["sha256"],
                "civitai_model_id": selected["civitai_model_id"],
                "civitai_model_version_id": selected["civitai_model_version_id"],
                "civitai_file_id": selected["civitai_file_id"], "air": selected["air"],
            })
        ], local_identity_ledger(db).entries, strict=True).to_dict()

    assert result["status"] == "completed"
    assert report["entries"][0]["actual_identity"]["model_family"] == "illustrious"
    assert report["resource_lock"][0]["model_family"] == "illustrious"


def test_install_updates_one_existing_ledger_identity_then_strict_resolver_consumes_it(tmp_path: Path) -> None:
    """CIV-V-D-AC8: guarded install updates, then CIV-V-C reads and strictly locks it."""
    from app.schemas.generation_recipe import RecipeResource
    from app.services.civitai_local_identity_ledger import local_identity_ledger
    from app.services.civitai_resource_install import install_civitai_resource
    from app.services.civitai_resource_resolution import resolve_recipe_resources

    data = b"ledger-consumable install"
    selected = _selected(data)
    with _session(tmp_path)() as db:
        old = DownloadedResource(
            resource_name="old-name.safetensors", resource_type="lora", provider="civitai",
            source_url="https://civitai.com/api/download/models/11", status="planned",
            civitai_file_id=str(selected["civitai_file_id"]), local_path=str(tmp_path / "stale"),
        )
        db.add(old)
        db.commit()
        old_id = old.id

        result = install_civitai_resource(
            selected, "loras", db=db, storage_roots={"loras": tmp_path / "loras"},
            transport=_Transport(data),
        )
        snapshot = local_identity_ledger(db)
        report = resolve_recipe_resources([
            RecipeResource.model_validate({
                "kind": "lora", "name": "display-name-is-not-identity.safetensors",
                "sha256": selected["sha256"],
                "civitai_model_id": selected["civitai_model_id"],
                "civitai_model_version_id": selected["civitai_model_version_id"],
                "civitai_file_id": selected["civitai_file_id"],
                "air": selected["air"],
            })
        ], snapshot.entries, strict=True)

        assert result["status"] == "completed"
        assert db.query(DownloadedResource).count() == 1
        assert db.query(DownloadedResource).one().id == old_id
        assert report.ready is True
        assert report.resource_lock == [{
            "index": 0, "kind": "lora", "local_path": result["final_path"],
            "sha256": selected["sha256"], "civitai_model_id": 101,
            "civitai_model_version_id": 201, "civitai_file_id": 11,
            "air": selected["air"], "model_family": "sdxl",
        }]


def test_backend_route_redacts_authorization_and_token_query_in_success_and_error_payloads(monkeypatch) -> None:
    """CIV-V-D-AC8: transport-facing canonical HTTP payloads never disclose credentials."""
    from fastapi.testclient import TestClient
    from app.api import civitai_recipes
    from app.main import app

    secret = "AUTHORIZATION_SENTINEL"
    selected = _selected(b"route-redaction")
    body = {"selected": selected, "storage_root": "loras", "overwrite": False}
    dirty_success = {
        "status": "completed", "authorization": f"Bearer {secret}",
        "source": f"https://civitai.com/api/download/models/11?token={secret}",
    }
    dirty_error = {
        "status": "blocked", "diagnostic": {
            "code": "unsafe_metadata", "authorization": f"Bearer {secret}",
            "source": f"https://civitai.com/api/download/models/11?token={secret}",
        },
    }
    client = TestClient(app)
    try:
        monkeypatch.setattr(civitai_recipes, "install_civitai_resource", lambda *args, **kwargs: dirty_success)
        success = client.post("/api/civitai-recipes/resource-install", json=body)
        monkeypatch.setattr(civitai_recipes, "install_civitai_resource", lambda *args, **kwargs: dirty_error)
        error = client.post("/api/civitai-recipes/resource-install", json=body)
    finally:
        client.close()

    assert success.status_code == 200
    assert error.status_code == 409
    assert secret not in json.dumps(success.json())
    assert secret not in json.dumps(error.json())
