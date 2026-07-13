"""CIV-SA-Y Gallery-only audited source-alias backfill acceptance tests."""
from __future__ import annotations

import hashlib
import json
import os
import socket
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import (
    CivitaiSourceAlias,
    CivitaiSourceAliasBackfillCandidate,
    CivitaiSourceAliasHistory,
    CivitaiSourceAliasRegistryRecord,
    CivitaiSourceAliasRepointTransition,
    GeneratedImage,
)
from app.schemas.civitai_source_aliases import canonical_json, canonical_sha256
from app.services.civitai_recipe_gallery import build_recipe_provenance_bundle, persistable_bundle
from app.services.civitai_source_alias_registry import exact_resolve, remember_source_alias


def _sha_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle(tmp_path: Path, *, image_id: int | None = 123, media_url: str | None = None) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    model = tmp_path / "base.safetensors"
    model.write_bytes(b"model")
    model_sha = _sha_bytes(model)
    workflow = {"1": {"class_type": "KSampler", "inputs": {"seed": 42}}}
    source = {"provider": "civitai"}
    if image_id is not None:
        source["image_id"] = image_id
    if media_url is not None:
        source["media_url"] = media_url
    recipe = {
        "schema_version": "1.0",
        "source": source,
        "base_prompt": "gallery backfill",
        "resources": [{"kind": "checkpoint", "name": "base.safetensors", "sha256": model_sha}],
        "sampling": {"seed": 42, "steps": 20, "cfg": 7.0, "sampler": "euler", "scheduler": "normal", "denoise": 1.0, "width": 512, "height": 512},
        "passes": [{"name": "base", "inherits_from": "recipe.sampling"}],
        "runtime": {"engine": "ComfyUI", "engine_version": "1", "reference": "runtime:1"},
        "workflow": {"reference": "gallery", "snapshot": workflow, "snapshot_sha256": canonical_sha256(workflow)},
    }
    return build_recipe_provenance_bundle(
        recipe=recipe,
        workflow=workflow,
        input_hashes=[],
        resource_locks=[{"index": 0, "kind": "checkpoint", "sha256": model_sha, "local_path": str(model), "local_sha256": model_sha}],
        runtime_provenance=recipe["runtime"],
        reproduction_level="workflow_ready_but_runtime_may_differ",
    )


@contextmanager
def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db, engine
    finally:
        db.close()
        engine.dispose()


def _gallery(db, bundle: dict, *, image_path: str = "gallery/one.png", job_id: str | None = None, lineage: dict | None = None) -> GeneratedImage:
    row = GeneratedImage(image_path=image_path, job_id=job_id, **persistable_bundle(bundle))
    if lineage is not None:
        row.recipe_variant_lineage_json = canonical_json(lineage)
        row.recipe_variant_lineage_sha256 = lineage["lineage_sha256"]
    db.add(row)
    db.commit()
    return row


def _registry_snapshot(db) -> tuple:
    records = [(r.registry_version, r.source_identity_json, r.acquisition_evidence_json, r.acquisition_evidence_sha256, r.parent_recipe_sha256, r.thumbnail_path) for r in db.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)]
    aliases = [(r.id, r.registry_version, r.original_alias, r.normalized_key, r.alias_kind) for r in db.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)]
    return records, aliases


_AUDITED_TABLES = (
    GeneratedImage,
    CivitaiSourceAliasBackfillCandidate,
    CivitaiSourceAliasRegistryRecord,
    CivitaiSourceAlias,
    CivitaiSourceAliasHistory,
    CivitaiSourceAliasRepointTransition,
)


def _audited_table_snapshot(db) -> tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...]:
    """Capture every persisted column of every AC4 audited table."""
    return tuple(
        (
            model.__tablename__,
            tuple(
                tuple(getattr(row, column.name) for column in model.__table__.columns)
                for row in db.query(model).order_by(*model.__mapper__.primary_key).all()
            ),
        )
        for model in _AUDITED_TABLES
    )


@contextmanager
def _forbidden_backfill_bombs(monkeypatch: pytest.MonkeyPatch):
    """One complete bomb set is installed around every representative AC4 outcome."""
    calls: list[str] = []

    def bomb(name: str):
        def _bomb(*_args: Any, **_kwargs: Any) -> None:
            calls.append(name)
            raise AssertionError(f"Gallery backfill called forbidden entry point: {name}")
        return _bomb

    targets = (
        ("app.services.civitai_acquisition", "acquire_civitai_recipe"),
        ("app.services.civitai_acquisition", "_request_json"),
        ("app.services.civitai_acquisition", "_fetch_media_evidence"),
        ("app.services.civitai_recipe_pipeline", "import_recipe"),
        ("app.services.civitai_recipe_pipeline", "resolve_recipe"),
        ("app.services.civitai_recipe_pipeline", "build_recipe"),
        ("app.services.civitai_resource_resolution", "resolve_recipe_resources"),
        ("app.services.civitai_recipe_compatibility", "preflight_recipe_compatibility"),
        ("app.services.civitai_recipe_workflow_compiler", "compile_generation_recipe_workflow"),
        ("app.services.civitai_recipe_variants", "generate_one_variant"),
        ("app.services.civitai_recipe_variants", "generate_one_variant_from_materialized_parent"),
        ("app.core.queue", "submit"),
        ("app.core.queue", "submit_custom"),
        ("app.core.queue", "submit_audited_recipe"),
        ("app.core.recording", "save"),
        ("app.core.recording", "save_artifact"),
        ("app.core.comfyui", "get_comfy_client"),
        ("app.api.gallery", "rerun_image"),
        ("app.api.generate", "trigger_generate"),
        ("app.api.generate", "trigger_generate_custom"),
    )
    with monkeypatch.context() as scoped:
        for module_name, attribute in targets:
            module = __import__(module_name, fromlist=[attribute])
            scoped.setattr(module, attribute, bomb(f"{module_name}.{attribute}"))
        for attribute in ("write_bytes", "write_text", "rename", "replace", "unlink"):
            scoped.setattr(Path, attribute, bomb(f"pathlib.Path.{attribute}"))
        for attribute in ("replace", "rename", "unlink"):
            scoped.setattr(os, attribute, bomb(f"os.{attribute}"))
        scoped.setattr(socket, "create_connection", bomb("socket.create_connection"))
        scoped.setattr(urllib.request, "urlopen", bomb("urllib.request.urlopen"))
        yield calls
    assert calls == []


def test_gallery_backfill_revalidates_canonical_parent_and_audited_identity(tmp_path: Path) -> None:
    from app.schemas.civitai_source_alias_backfill import CivitaiSourceAliasGalleryBackfillRequest
    from app.services.civitai_source_alias_backfill import backfill_gallery_source_alias

    with _db() as (db, _engine):
        row = _gallery(db, _bundle(tmp_path, image_id=456), image_path="gallery/456.png")
        result = backfill_gallery_source_alias(CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=row.id), db=db)

        assert result.status == "pending_name"
        assert result.parent_recipe_sha256 == canonical_sha256(json.loads(row.recipe_json))
        assert result.source_identity == {"provider": "civitai", "image_id": 456}
        expected = {"recipe": json.loads(row.recipe_json), "backfill_source": {"kind": "gallery_recipe", "gallery_image_id": row.id, "gallery_recipe_sha256": result.parent_recipe_sha256}}
        assert result.acquisition_evidence_snapshot == expected
        assert result.acquisition_evidence_sha256 == canonical_sha256(expected)
        assert result.candidate is not None and result.candidate.thumbnail_path == "gallery/456.png"

        # ``bundle_from_record`` deliberately normalizes legacy payloads. Backfill is
        # stricter: a persisted string image ID must not be silently coerced back to
        # the same canonical parent hash before an alias candidate is created.
        row.recipe_json = row.recipe_json.replace('"image_id":456', '"image_id":"456"')
        # Preserve the digest produced by permissive bundle normalization.  Only the
        # additional strict raw-recipe boundary can catch this persisted type error.
        row.recipe_sha256 = result.parent_recipe_sha256
        db.commit()
        strict_failure = backfill_gallery_source_alias(
            CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=row.id, primary_alias="must not coerce"), db=db
        )
        assert (strict_failure.status, strict_failure.code) in {
            ("ineligible", "gallery_parent_ineligible"),
            ("corrupt", "gallery_provenance_recipe_sha256_mismatch"),
        }
        assert db.query(__import__("app.db.models", fromlist=["CivitaiSourceAliasBackfillCandidate"]).CivitaiSourceAliasBackfillCandidate).count() == 1


def test_gallery_backfill_with_explicit_alias_atomically_remembers_or_fails_without_partial_candidate(tmp_path: Path) -> None:
    from app.schemas.civitai_source_alias_backfill import CivitaiSourceAliasGalleryBackfillRequest
    from app.services.civitai_source_alias_backfill import backfill_gallery_source_alias

    with _db() as (db, _engine):
        first = _gallery(db, _bundle(tmp_path, image_id=456), image_path="gallery/456.png")
        named = backfill_gallery_source_alias(CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=first.id, primary_alias="Parent 456"), db=db)
        assert named.status == "named" and named.record is not None
        before = _registry_snapshot(db)
        retry = backfill_gallery_source_alias(CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=first.id, primary_alias="  parent 456 "), db=db)
        assert retry.status == "named" and retry.record.registry_version == named.record.registry_version
        assert _registry_snapshot(db) == before
        second = _gallery(db, _bundle(tmp_path, image_id=789), image_path="gallery/789.png")
        conflict = backfill_gallery_source_alias(CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=second.id, primary_alias="PARENT 456"), db=db)
        assert conflict.status == "conflict" and conflict.source_identity is None and conflict.candidate is None
        assert _registry_snapshot(db) == before


def test_gallery_backfill_without_alias_persists_one_idempotent_pending_name_candidate_without_reserving_alias(tmp_path: Path) -> None:
    from app.db.models import CivitaiSourceAliasBackfillCandidate
    from app.schemas.civitai_source_alias_backfill import CivitaiSourceAliasGalleryBackfillRequest
    from app.services.civitai_source_alias_backfill import backfill_gallery_source_alias

    with _db() as (db, _engine):
        bundle = _bundle(tmp_path, image_id=321)
        occupied = {"provider": "civitai", "image_id": 999}
        evidence = {"recipe": bundle["recipe"], "backfill_source": {"kind": "gallery_recipe", "gallery_image_id": 999, "gallery_recipe_sha256": canonical_sha256(bundle["recipe"])}}
        from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
        remember_source_alias(CivitaiSourceAliasRememberRequest(primary_alias="civitai-image-321", source_identity=occupied, acquisition_evidence_snapshot=evidence, acquisition_evidence_sha256=canonical_sha256(evidence), parent_recipe_sha256=canonical_sha256(bundle["recipe"])), db=db)
        before = _registry_snapshot(db)
        row = _gallery(db, bundle, image_path="gallery/321.png")
        first = backfill_gallery_source_alias(CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=row.id), db=db)
        second = backfill_gallery_source_alias(CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=row.id), db=db)
        assert first.status == "pending_name" and first.candidate is not None
        assert second.status == "already_backfilled" and second.candidate is not None
        assert second.candidate.id == first.candidate.id
        assert first.candidate.suggested_alias == "civitai-image-321"
        assert db.query(CivitaiSourceAliasBackfillCandidate).count() == 1
        assert _registry_snapshot(db) == before
        assert exact_resolve("civitai-image-321", db=db).record.source_identity == occupied

        # A persisted candidate is auditable evidence, not merely a cache. Its JSON
        # must already be byte-for-byte canonical; do not silently reserialize it.
        candidate = db.query(CivitaiSourceAliasBackfillCandidate).one()
        candidate.acquisition_evidence_json = json.dumps(json.loads(candidate.acquisition_evidence_json), indent=2)
        db.commit()
        corrupt = backfill_gallery_source_alias(CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=row.id), db=db)
        assert (corrupt.status, corrupt.code) == ("corrupt", "candidate_invalid")



def _assert_empty_failure(result: Any, expected: tuple[str, str]) -> None:
    assert (result.status, result.code) == expected
    assert (
        result.record,
        result.candidate,
        result.source_identity,
        result.acquisition_evidence_snapshot,
        result.acquisition_evidence_sha256,
        result.parent_recipe_sha256,
    ) == (None, None, None, None, None, None)


def _invoke_no_side_effects(
    db: Any,
    monkeypatch: pytest.MonkeyPatch,
    call: Callable[[], Any],
    expected: tuple[str, str],
) -> None:
    """Invoke one frozen failure under all bombs and prove all six tables are unchanged."""
    before = _audited_table_snapshot(db)
    with _forbidden_backfill_bombs(monkeypatch):
        result = call()
    _assert_empty_failure(result, expected)
    assert _audited_table_snapshot(db) == before


def _valid_lineage(row: GeneratedImage) -> dict[str, Any]:
    lineage = {
        "schema_version": "1.0", "variant_id": "child-one", "job_id": "variant-job",
        "parent_recipe_sha256": "a" * 64, "derived_recipe_sha256": "b" * 64,
        "built_child_recipe_sha256": row.recipe_sha256, "applied_directives": [],
        "invalidated_evidence_sha256": canonical_sha256({}),
        "strict_resolution_snapshot_sha256": canonical_sha256({"resolution": "fresh"}),
        "compatibility_snapshot_sha256": canonical_sha256({"compatible": True}),
        "workflow_sha256": row.recipe_workflow_sha256,
        "resource_lock_sha256": canonical_sha256(json.loads(row.recipe_resource_locks_json)),
    }
    lineage["lineage_sha256"] = canonical_sha256(lineage)
    return lineage


def _replace_source(row: GeneratedImage, source: dict[str, Any]) -> None:
    recipe = json.loads(row.recipe_json)
    recipe["source"] = source
    row.recipe_json = canonical_json(recipe)
    row.recipe_sha256 = canonical_sha256(recipe)


def _seed_alias(db: Any, bundle: dict[str, Any], *, archived: bool = False, corrupt: bool = False) -> None:
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest

    evidence = {
        "recipe": bundle["recipe"],
        "backfill_source": {
            "kind": "gallery_recipe", "gallery_image_id": 999,
            "gallery_recipe_sha256": canonical_sha256(bundle["recipe"]),
        },
    }
    remembered = remember_source_alias(CivitaiSourceAliasRememberRequest(
        primary_alias="occupied", source_identity={"provider": "civitai", "image_id": 999},
        acquisition_evidence_snapshot=evidence, acquisition_evidence_sha256=canonical_sha256(evidence),
        parent_recipe_sha256=canonical_sha256(bundle["recipe"]),
    ), db=db)
    assert remembered.status == "success"
    record = db.query(CivitaiSourceAliasRegistryRecord).one()
    if archived:
        record.archived_at = datetime.now(timezone.utc)
    if corrupt:
        record.acquisition_evidence_sha256 = "0" * 64
    db.commit()


@pytest.mark.parametrize(
    "case_id",
    (
        "request_and_parent_eligibility",
        "persisted_binding_corruption",
        "variant_lineage_matrix",
        "immutable_identity_matrix",
        "pending_then_named_conflict",
        "remember_failure_matrix",
        "transaction_failure_matrix",
        "fresh_schema_unique_constraint",
    ),
    ids=lambda case_id: case_id,
)
def test_gallery_backfill_ineligible_corrupt_and_conflict_matrix_has_zero_side_effects_and_fresh_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case_id: str,
) -> None:
    """CIV-SA-Y-R1-AC1: exact eight-row AC4, fail-closed audit matrix."""
    from app.schemas.civitai_source_alias_backfill import CivitaiSourceAliasGalleryBackfillRequest
    from app.services.civitai_source_alias_backfill import backfill_gallery_source_alias

    def request(row_id: int, primary_alias: str | None = None) -> Any:
        return CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=row_id, primary_alias=primary_alias)

    if case_id == "request_and_parent_eligibility":
        with _db() as (db, _engine):
            _invoke_no_side_effects(db, monkeypatch, lambda: backfill_gallery_source_alias({"gallery_image_id": "1"}, db=db), ("ineligible", "invalid_request"))
            _invoke_no_side_effects(db, monkeypatch, lambda: backfill_gallery_source_alias({"gallery_image_id": 1, "primary_alias": "  "}, db=db), ("ineligible", "invalid_request"))
            _invoke_no_side_effects(db, monkeypatch, lambda: backfill_gallery_source_alias(request(999), db=db), ("ineligible", "gallery_not_found"))
            row = _gallery(db, _bundle(tmp_path / case_id, image_id=77))

            class DuplicateGalleryLookup:
                def filter_by(self, **_kwargs: Any) -> "DuplicateGalleryLookup":
                    return self

                def all(self) -> list[GeneratedImage]:
                    return [row, row]

            class DuplicateGalleryDb:
                def query(self, model: Any) -> Any:
                    return DuplicateGalleryLookup() if model is GeneratedImage else db.query(model)

            before = _audited_table_snapshot(db)
            with _forbidden_backfill_bombs(monkeypatch):
                duplicate = backfill_gallery_source_alias(request(row.id), db=DuplicateGalleryDb())
            _assert_empty_failure(duplicate, ("corrupt", "gallery_non_unique"))
            assert _audited_table_snapshot(db) == before
            row.recipe_json = None
            db.commit()
            _invoke_no_side_effects(db, monkeypatch, lambda: backfill_gallery_source_alias(request(row.id), db=db), ("corrupt", "gallery_provenance_recipe_bundle_missing"))
        # The persisted Gallery bundle reader permits legacy coercion for export, but
        # backfill must reject a string image ID at its strict immutable-audit edge.
        with _db() as (db, _engine):
            row = _gallery(db, _bundle(tmp_path / case_id / "legacy-string-image-id", image_id=77))
            row.recipe_json = row.recipe_json.replace('"image_id":77', '"image_id":"77"')
            # Keep the original permissive digest: this case specifically proves the
            # raw persisted recipe type boundary, not merely a digest mismatch.
            db.commit()
            _invoke_no_side_effects(
                db,
                monkeypatch,
                lambda: backfill_gallery_source_alias(request(row.id), db=db),
                ("ineligible", "gallery_parent_ineligible"),
            )
        return

    if case_id == "persisted_binding_corruption":
        corruptions: tuple[tuple[str, Callable[[GeneratedImage], None], tuple[str, str]], ...] = (
            ("partial-bundle", lambda row: setattr(row, "recipe_runtime_provenance_json", None), ("corrupt", "gallery_provenance_recipe_bundle_missing")),
            ("recipe-json", lambda row: setattr(row, "recipe_json", "not-json"), ("corrupt", "gallery_provenance_provenance_invalid")),
            ("recipe-hash", lambda row: setattr(row, "recipe_sha256", "0" * 64), ("corrupt", "gallery_provenance_recipe_sha256_mismatch")),
            ("workflow-json", lambda row: setattr(row, "recipe_workflow_json", "not-json"), ("corrupt", "gallery_provenance_provenance_invalid")),
            ("workflow-hash", lambda row: setattr(row, "recipe_workflow_sha256", "0" * 64), ("corrupt", "gallery_provenance_workflow_sha256_mismatch")),
            ("input-json", lambda row: setattr(row, "recipe_input_hashes_json", "not-json"), ("corrupt", "gallery_provenance_provenance_invalid")),
            ("resource-json", lambda row: setattr(row, "recipe_resource_locks_json", "[]"), ("corrupt", "gallery_provenance_resource_lock_missing")),
            ("resource-hash", lambda row: setattr(row, "recipe_resource_locks_json", canonical_json([{**json.loads(row.recipe_resource_locks_json)[0], "sha256": "0" * 64}])), ("corrupt", "gallery_provenance_resource_lock_identity_mismatch")),
            ("runtime-json", lambda row: setattr(row, "recipe_runtime_provenance_json", "{}"), ("corrupt", "gallery_provenance_runtime_provenance_invalid")),
        )
        for name, corrupt, expected in corruptions:
            with _db() as (db, _engine):
                row = _gallery(db, _bundle(tmp_path / case_id / name, image_id=77))
                corrupt(row)
                db.commit()
                _invoke_no_side_effects(db, monkeypatch, lambda row=row: backfill_gallery_source_alias(request(row.id), db=db), expected)
        return

    if case_id == "variant_lineage_matrix":
        mutations: tuple[tuple[str, Callable[[GeneratedImage], None], tuple[str, str]], ...] = (
            ("partial", lambda row: setattr(row, "recipe_variant_lineage_json", "{}"), ("corrupt", "gallery_provenance_variant_lineage_incomplete")),
            ("invalid", lambda row: (setattr(row, "recipe_variant_lineage_json", "{}"), setattr(row, "recipe_variant_lineage_sha256", "0" * 64)), ("corrupt", "gallery_provenance_variant_lineage_invalid")),
            ("valid", lambda row: (setattr(row, "job_id", "variant-job"), setattr(row, "recipe_variant_lineage_json", canonical_json(_valid_lineage(row))), setattr(row, "recipe_variant_lineage_sha256", _valid_lineage(row)["lineage_sha256"])), ("ineligible", "gallery_parent_ineligible")),
        )
        for name, mutate, expected in mutations:
            with _db() as (db, _engine):
                row = _gallery(db, _bundle(tmp_path / case_id / name, image_id=77))
                mutate(row)
                db.commit()
                _invoke_no_side_effects(db, monkeypatch, lambda row=row: backfill_gallery_source_alias(request(row.id), db=db), expected)
        return

    if case_id == "immutable_identity_matrix":
        with _db() as (db, _engine):
            row = _gallery(db, _bundle(tmp_path / case_id / "missing", image_id=77))
            _replace_source(row, {"provider": "civitai"})
            db.commit()
            _invoke_no_side_effects(db, monkeypatch, lambda: backfill_gallery_source_alias(request(row.id), db=db), ("ineligible", "gallery_parent_ineligible"))
        with _db() as (db, _engine):
            row = _gallery(db, _bundle(tmp_path / case_id / "invalid", image_id=77))
            _replace_source(row, {"provider": "civitai", "image_id": 0})
            db.commit()
            _invoke_no_side_effects(db, monkeypatch, lambda: backfill_gallery_source_alias(request(row.id), db=db), ("corrupt", "gallery_provenance_recipe_schema_invalid"))
        with _db() as (db, _engine):
            media_url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/ac4-media.jpg"
            row = _gallery(db, _bundle(tmp_path / case_id / "cdn", image_id=None, media_url=media_url))
            before = _audited_table_snapshot(db)
            with _forbidden_backfill_bombs(monkeypatch):
                result = backfill_gallery_source_alias(request(row.id), db=db)
            expected_identity = {"provider": "civitai", "media_url": media_url}
            expected_parent_sha = canonical_sha256(json.loads(row.recipe_json))
            expected_evidence = {
                "recipe": json.loads(row.recipe_json),
                "backfill_source": {
                    "kind": "gallery_recipe",
                    "gallery_image_id": row.id,
                    "gallery_recipe_sha256": expected_parent_sha,
                },
            }
            expected_evidence_sha = canonical_sha256(expected_evidence)
            expected_suggested_alias = "civitai-media-" + hashlib.sha256(media_url.encode()).hexdigest()[:12]
            assert (result.status, result.code) == ("pending_name", "pending_name_created")
            assert (
                result.source_identity,
                result.acquisition_evidence_snapshot,
                result.acquisition_evidence_sha256,
                result.parent_recipe_sha256,
            ) == (expected_identity, expected_evidence, expected_evidence_sha, expected_parent_sha)
            assert result.record is None and result.candidate is not None
            assert (
                result.candidate.gallery_image_id,
                result.candidate.source_identity,
                result.candidate.acquisition_evidence_snapshot,
                result.candidate.acquisition_evidence_sha256,
                result.candidate.parent_recipe_sha256,
                result.candidate.thumbnail_path,
                result.candidate.suggested_alias,
            ) == (
                row.id,
                expected_identity,
                expected_evidence,
                expected_evidence_sha,
                expected_parent_sha,
                row.image_path,
                expected_suggested_alias,
            )
            after = _audited_table_snapshot(db)
            before_tables = dict(before)
            after_tables = dict(after)
            for unchanged in (
                GeneratedImage,
                CivitaiSourceAliasRegistryRecord,
                CivitaiSourceAlias,
                CivitaiSourceAliasHistory,
                CivitaiSourceAliasRepointTransition,
            ):
                assert after_tables[unchanged.__tablename__] == before_tables[unchanged.__tablename__]
            assert result.candidate.id == 1
            expected_candidate_row = (
                result.candidate.id,
                row.id,
                canonical_json(expected_identity),
                canonical_json(expected_evidence),
                expected_evidence_sha,
                expected_parent_sha,
                row.image_path,
                expected_suggested_alias,
                result.candidate.created_at.replace(tzinfo=None),
            )
            assert after_tables[CivitaiSourceAliasBackfillCandidate.__tablename__] == (expected_candidate_row,)
        return

    if case_id == "pending_then_named_conflict":
        with _db() as (db, _engine):
            row = _gallery(db, _bundle(tmp_path / case_id, image_id=77))
            assert backfill_gallery_source_alias(request(row.id), db=db).status == "pending_name"
            _invoke_no_side_effects(db, monkeypatch, lambda: backfill_gallery_source_alias(request(row.id, "cannot-promote"), db=db), ("conflict", "pending_name_exists"))
        return

    if case_id == "remember_failure_matrix":
        for name, archived, corrupt, expected in (
            ("alias", False, False, ("conflict", "alias_target_conflict")),
            ("archived", True, False, ("conflict", "alias_archived")),
            ("corrupt", False, True, ("corrupt", "evidence_hash_mismatch")),
        ):
            with _db() as (db, _engine):
                bundle = _bundle(tmp_path / case_id / name, image_id=77)
                _seed_alias(db, bundle, archived=archived, corrupt=corrupt)
                row = _gallery(db, bundle)
                _invoke_no_side_effects(db, monkeypatch, lambda row=row: backfill_gallery_source_alias(request(row.id, "occupied"), db=db), expected)
        with _db() as (db, _engine), monkeypatch.context() as scoped:
            row = _gallery(db, _bundle(tmp_path / case_id / "exception", image_id=77))
            scoped.setattr("app.services.civitai_source_alias_backfill.remember_source_alias", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
            _invoke_no_side_effects(db, scoped, lambda: backfill_gallery_source_alias(request(row.id, "boom"), db=db), ("corrupt", "remember_exception"))
        return

    if case_id == "transaction_failure_matrix":
        for name, primary_alias, method, expected in (
            ("pending-flush", None, "flush", ("corrupt", "candidate_persistence_failed")),
            ("pending-commit", None, "commit", ("corrupt", "candidate_persistence_failed")),
            ("remember-flush", "named", "flush", ("corrupt", "remember_exception")),
            ("remember-commit", "named", "commit", ("corrupt", "remember_exception")),
        ):
            with _db() as (db, _engine), monkeypatch.context() as scoped:
                row = _gallery(db, _bundle(tmp_path / case_id / name, image_id=77))
                original = getattr(db, method)

                def fail_write(*args: Any, **kwargs: Any) -> Any:
                    if method == "flush" and not db.new:
                        return original(*args, **kwargs)
                    raise SQLAlchemyError(name)

                scoped.setattr(db, method, fail_write)
                _invoke_no_side_effects(db, scoped, lambda row=row, primary_alias=primary_alias: backfill_gallery_source_alias(request(row.id, primary_alias), db=db), expected)
        return

    assert case_id == "fresh_schema_unique_constraint"
    with _db() as (db, engine):
        assert "civitai_source_alias_backfill_candidates" in inspect(engine).get_table_names()
        constraints = inspect(engine).get_unique_constraints("civitai_source_alias_backfill_candidates")
        assert any(item["column_names"] == ["gallery_image_id"] for item in constraints)
        row = _gallery(db, _bundle(tmp_path / case_id, image_id=77))
        first = CivitaiSourceAliasBackfillCandidate(
            gallery_image_id=row.id, source_identity_json=canonical_json({"provider": "civitai", "image_id": 77}),
            acquisition_evidence_json=canonical_json({"evidence": 1}), acquisition_evidence_sha256="a" * 64,
            parent_recipe_sha256="b" * 64, suggested_alias="first",
        )
        db.add(first)
        db.commit()
        before = _audited_table_snapshot(db)
        db.add(CivitaiSourceAliasBackfillCandidate(
            gallery_image_id=row.id, source_identity_json=canonical_json({"provider": "civitai", "image_id": 77}),
            acquisition_evidence_json=canonical_json({"evidence": 2}), acquisition_evidence_sha256="c" * 64,
            parent_recipe_sha256="d" * 64, suggested_alias="duplicate",
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert _audited_table_snapshot(db) == before

