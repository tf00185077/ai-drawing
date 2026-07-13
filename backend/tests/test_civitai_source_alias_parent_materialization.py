"""CIV-SA-T audited source-alias Parent Recipe materialization contracts."""
from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack, contextmanager, nullcontext
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.schemas.generation_recipe import GenerationRecipe


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _recipe(*, image_id: int = 123, media_url: str | None = None) -> dict[str, object]:
    source: dict[str, object] = {"provider": "civitai"}
    if image_id is not None:
        source["image_id"] = image_id
    if media_url is not None:
        source["media_url"] = media_url
    return {
        "schema_version": "1.0",
        "source": source,
        "base_prompt": "positive",
        "resources": [{"kind": "checkpoint", "name": "base.safetensors", "sha256": "a" * 64}],
        "sampling": {"seed": 42, "steps": 20, "cfg": 7.0, "sampler": "euler", "scheduler": "normal", "denoise": 1.0, "width": 512, "height": 512},
        "passes": [{"name": "base", "inherits_from": "recipe.sampling"}],
    }


def _payload(*, alias: str = "Sunset Hero", image_id: int = 123) -> dict[str, object]:
    recipe = GenerationRecipe.model_validate(_recipe(image_id=image_id)).model_dump(mode="json", exclude_none=True)
    evidence = {"recipe": recipe, "raw_api_payload": {"id": image_id, "meta": {"seed": 42}}}
    return {
        "primary_alias": alias,
        "alternate_aliases": ["Apple Alternate"],
        "source_identity": {"provider": "civitai", "image_id": image_id},
        "acquisition_evidence_snapshot": evidence,
        "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": _sha(recipe),
        "approved_tags": ["original"],
    }


def _session(tmp_path):
    from app.db import models  # noqa: F401

    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'materialization.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _remember(db, **kwargs):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember_source_alias

    result = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_payload(**kwargs)), db=db)
    assert result.status == "success"
    return result


def _repoint(db, *, image_id: int = 456):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRepointTarget
    from app.services.civitai_source_alias_registry import repoint_source_alias

    replacement = _payload(alias="unused", image_id=image_id)
    result = repoint_source_alias(
        {
            "current_primary_alias": "Sunset Hero",
            "expected_registry_version": 1,
            "replacement": CivitaiSourceAliasRepointTarget.model_validate(
                {key: replacement[key] for key in replacement if key not in {"primary_alias", "alternate_aliases"}}
            ).model_dump(mode="json", exclude_none=True),
        },
        db=db,
    )
    assert result.status == "success"
    return result


def _snapshot(db):
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord, CivitaiSourceAliasRepointTransition

    return (
        [(r.registry_version, r.source_identity_json, r.acquisition_evidence_json, r.acquisition_evidence_sha256, r.parent_recipe_sha256, r.thumbnail_url, r.thumbnail_path, r.user_note, r.approved_tags_json, r.prompt_summary, r.created_at.isoformat(), r.archived_at.isoformat() if r.archived_at else None) for r in db.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)],
        [(r.id, r.registry_version, r.original_alias, r.normalized_key, r.alias_kind) for r in db.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)],
        [(r.id, r.registry_version, r.operation, r.before_aliases_json, r.after_aliases_json, r.previous_event_sha256, r.event_sha256, r.created_at.isoformat()) for r in db.query(CivitaiSourceAliasHistory).order_by(CivitaiSourceAliasHistory.id)],
        [(r.id, r.from_registry_version, r.to_registry_version, r.aliases_json, r.from_record_sha256, r.to_record_sha256, r.source_history_tail_sha256, r.previous_repoint_event_sha256, r.event_sha256, r.created_at.isoformat()) for r in db.query(CivitaiSourceAliasRepointTransition).order_by(CivitaiSourceAliasRepointTransition.id)],
    )


@contextmanager
def _forbidden_bombs():
    def bomb(*_args, **_kwargs):
        raise AssertionError("materializer invoked forbidden boundary")

    targets = (
        "app.services.civitai_source_alias_parent.search_registry_sources",
        "app.services.civitai_source_alias_parent.list_registry_sources",
        "app.services.civitai_source_alias_parent.remember_source_alias",
        "app.services.civitai_source_alias_parent.rename_primary_source_alias",
        "app.services.civitai_source_alias_parent.archive_source_alias",
        "app.services.civitai_source_alias_parent.repoint_source_alias",
        "app.services.civitai_recipe_pipeline.acquire_civitai_recipe",
        "app.services.civitai_recipe_pipeline.build_recipe",
        "app.services.civitai_recipe_pipeline.compile_generation_recipe_workflow",
        "app.services.civitai_recipe_compatibility.preflight_recipe_compatibility",
        "app.core.queue.get_comfy_client",
        "app.core.queue.submit_audited_recipe",
        "app.services.civitai_recipe_variants.generate_one_variant",
        "app.services.civitai_recipe_variation_sets.create_variation_set",
        "app.services.civitai_recipe_gallery.build_recipe_provenance_bundle",
    )
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, side_effect=bomb, create=True))
        yield


def test_materialize_parent_uses_exact_or_explicit_version_resolver_only(tmp_path, monkeypatch) -> None:
    """CIV-SA-T-AC1: strict selector routes exactly once to its one permitted resolver."""
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasParentSelector
    from app.services import civitai_source_alias_parent as materializer

    for invalid in ({}, {"alias": " "}, {"alias": "x" * 513}, {"alias": "x", "registry_version": True}, {"alias": "x", "registry_version": "1"}, {"alias": "x", "registry_version": 1.0}, {"alias": "x", "registry_version": 0}, {"alias": "x", "registry_version": -1}, {"alias": "x", "extra": True}):
        with pytest.raises(ValidationError):
            CivitaiSourceAliasParentSelector.model_validate(invalid, strict=True)

    Session = _session(tmp_path)
    with Session() as db:
        _remember(db)
        bare_calls: list[object] = []
        versioned_calls: list[object] = []
        real_bare, real_versioned = materializer.resolve_source_alias_exact, materializer.resolve_source_alias_exact_version
        monkeypatch.setattr(materializer, "resolve_source_alias_exact", lambda alias, *, db: (bare_calls.append(alias), real_bare(alias, db=db))[1])
        monkeypatch.setattr(materializer, "resolve_source_alias_exact_version", lambda request, *, db: (versioned_calls.append(request), real_versioned(request, db=db))[1])
        bare = materializer.materialize_source_alias_parent({"alias": "  Sunset Hero  "}, db=db)
        assert bare.status == "success"
        assert bare_calls == ["  Sunset Hero  "] and versioned_calls == []
        assert _repoint(db).to_record is not None
        current = materializer.materialize_source_alias_parent({"alias": "Sunset Hero", "registry_version": 2}, db=db)
        historical = materializer.materialize_source_alias_parent({"alias": "Apple Alternate", "registry_version": 1}, db=db)
    assert (current.status, current.alias_binding.registry_version) == ("success", 2)
    assert (historical.status, historical.alias_binding.registry_version) == ("success", 1)
    assert bare_calls == ["  Sunset Hero  "]
    assert len(versioned_calls) == 2
    assert [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in versioned_calls] == [
        {"alias": "Sunset Hero", "registry_version": 2}, {"alias": "Apple Alternate", "registry_version": 1},
    ]


def test_materialize_parent_revalidates_persisted_recipe_hash_and_immutable_identity(tmp_path, monkeypatch) -> None:
    """CIV-SA-T-AC2: evidence recipe/hash/source corruption has no partial materialization."""
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasDomainResult, CivitaiSourceAliasRegistryView, CivitaiSourceAliasView
    from app.services import civitai_source_alias_parent as materializer

    def resolved(evidence, *, evidence_sha=None, parent_sha=None, identity=None):
        recipe = evidence.get("recipe") if isinstance(evidence, dict) and isinstance(evidence.get("recipe"), dict) else _payload()["acquisition_evidence_snapshot"]["recipe"]
        return CivitaiSourceAliasDomainResult(
            status="success", code="resolved",
            record=CivitaiSourceAliasRegistryView(
                registry_version=1,
                source_identity=identity or {"provider": "civitai", "image_id": 123},
                acquisition_evidence_snapshot=evidence,
                acquisition_evidence_sha256=evidence_sha or _sha(evidence),
                parent_recipe_sha256=parent_sha or _sha(recipe),
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            alias=CivitaiSourceAliasView(original_alias="Sunset Hero", normalized_key="sunset hero", kind="primary"),
        )

    class ReadOnlyDb:
        @property
        def no_autoflush(self):
            return nullcontext()

    readonly_db = ReadOnlyDb()

    def reject(name: str, evidence, **kwargs) -> None:
        expected_code = kwargs.pop("code", "persisted_recipe_invalid")
        monkeypatch.setattr(materializer, "resolve_source_alias_exact", lambda _alias, *, db: resolved(evidence, **kwargs))
        result = materializer.materialize_source_alias_parent({"alias": "Sunset Hero"}, db=readonly_db)
        assert (result.status, result.code) == ("rejected", expected_code), name
        assert result.parent_recipe is result.alias_binding is result.parent_recipe_sha256 is None

    good_evidence = _payload()["acquisition_evidence_snapshot"]
    monkeypatch.setattr(materializer, "resolve_source_alias_exact", lambda _alias, *, db: resolved(good_evidence))
    result = materializer.materialize_source_alias_parent({"alias": "Sunset Hero"}, db=readonly_db)
    assert result.status == "success"
    assert result.parent_recipe_sha256 == _sha(result.parent_recipe.model_dump(mode="json", exclude_none=True))
    reject("missing-recipe", {"raw": True})
    reject("null-recipe", {"recipe": None})
    reject("non-object-recipe", {"recipe": []})
    reject("extra-recipe", {"recipe": {**_recipe(), "extra": True}})
    reject("strict-numeric-recipe", {"recipe": {**_recipe(), "source": {"provider": "civitai", "image_id": "123"}}})
    reject("evidence-hash", good_evidence, evidence_sha="0" * 64, code="acquisition_evidence_invalid")
    reject("parent-hash", good_evidence, parent_sha="0" * 64, code="parent_recipe_sha_mismatch")
    reject("provider-identity", good_evidence, identity={"provider": "other", "image_id": 123}, code="source_identity_mismatch")
    reject("image-identity", good_evidence, identity={"provider": "civitai", "image_id": 999}, code="source_identity_mismatch")
    media_recipe = GenerationRecipe.model_validate(_recipe(image_id=None, media_url="https://image.civitai.com/x/y.png")).model_dump(mode="json", exclude_none=True)
    media_evidence = {"recipe": media_recipe}
    reject("media-identity", media_evidence, identity={"provider": "civitai", "media_url": "https://image.civitai.com/x/other.png"}, code="source_identity_mismatch")
    for corrupted_image_id in ("123", True, 123.0):
        reject(
            f"strict-image-identity-{type(corrupted_image_id).__name__}",
            good_evidence,
            identity={"provider": "civitai", "image_id": corrupted_image_id},
            code="source_identity_mismatch",
        )
    for corrupted_media_url in (123, True, 1.5):
        reject(
            f"strict-media-identity-{type(corrupted_media_url).__name__}",
            media_evidence,
            identity={"provider": "civitai", "media_url": corrupted_media_url},
            code="source_identity_mismatch",
        )


def test_materialize_parent_preserves_verified_persisted_import_provenance(tmp_path) -> None:
    """CIV-SA-T-R1-AC1: verified import evidence retains its canonical provenance and digest."""
    from pathlib import Path

    from app.services.civitai_acquisition import CivitaiTransportResponse, acquire_civitai_recipe, redact_secrets
    from app.services.civitai_recipe_pipeline import _source_alias_result
    from app.services.civitai_source_alias_parent import materialize_source_alias_parent

    fixture = json.loads((Path(__file__).parent / "fixtures" / "civitai" / "api" / "image_123.json").read_text(encoding="utf-8"))

    class FixtureTransport:
        def get_json(self, _url, *, params=None, headers=None):
            assert params == {"withMeta": "true", "imageId": 123}
            assert headers == {}
            return CivitaiTransportResponse(200, {"items": [fixture]}, {})

    Session = _session(tmp_path)
    with Session() as db:
        acquired = acquire_civitai_recipe("123", transport=FixtureTransport())
        assert acquired.recipe is not None and acquired.recipe.confirmed
        _source_alias_result(
            acquired,
            redact_secrets(acquired.to_dict()),
            remember_alias="Trusted Import",
            db=db,
        )
        materialized = materialize_source_alias_parent({"alias": "Trusted Import"}, db=db)

    assert materialized.status == "success", materialized.code
    assert materialized.parent_recipe_sha256 == _sha(acquired.recipe.model_dump(mode="json", exclude_none=True))
    assert materialized.parent_recipe.confirmed == acquired.recipe.confirmed
    assert materialized.parent_recipe.inferred == acquired.recipe.inferred


def test_materialize_parent_returns_deterministic_typed_alias_binding(tmp_path) -> None:
    """CIV-SA-T-AC3: canonical parent and binding come only from the resolved immutable record."""
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasMaterializedParent
    from app.services.civitai_source_alias_parent import materialize_source_alias_parent

    Session = _session(tmp_path)
    with Session() as db:
        _remember(db)
        _repoint(db)
        current = materialize_source_alias_parent({"alias": "Sunset Hero", "registry_version": 2}, db=db)
        historical = materialize_source_alias_parent({"alias": "Apple Alternate", "registry_version": 1}, db=db)
        repeat = materialize_source_alias_parent({"alias": "Apple Alternate", "registry_version": 1}, db=db)
    assert isinstance(current, CivitaiSourceAliasMaterializedParent)
    assert current.parent_recipe_sha256 == _sha(current.parent_recipe.model_dump(mode="json", exclude_none=True))
    assert historical.model_dump(mode="json") == repeat.model_dump(mode="json")
    assert current.alias_binding.model_dump(mode="json") == {
        "requested_alias": "Sunset Hero", "matched_alias": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero", "kind": "primary"},
        "registry_version": 2, "source_identity": {"provider": "civitai", "image_id": 456},
        "acquisition_evidence_sha256": current.alias_binding.acquisition_evidence_sha256,
        "parent_recipe_sha256": current.parent_recipe_sha256,
        "registry_created_at": current.alias_binding.registry_created_at.isoformat().replace("+00:00", "Z"),
    }
    assert historical.alias_binding.registry_version == 1
    assert historical.alias_binding.matched_alias.original_alias == "Apple Alternate"
    assert historical.alias_binding.source_identity.model_dump(mode="json", exclude_none=True) == {"provider": "civitai", "image_id": 123}
    with pytest.raises(ValidationError):
        CivitaiSourceAliasMaterializedParent.model_validate({
            "status": "success", "code": "materialized", "parent_recipe": historical.parent_recipe.model_dump(mode="json"),
            "parent_recipe_sha256": historical.parent_recipe_sha256, "alias_binding": {**historical.alias_binding.model_dump(mode="json"), "registry_created_at": "2026-01-01T00:00:00"},
        })


def test_materialize_parent_fail_closed_matrix_has_zero_generation_side_effects(tmp_path, monkeypatch) -> None:
    """CIV-SA-T-AC4: resolver failures and local validation failures are read-only and inert."""
    from app.services import civitai_source_alias_parent as materializer

    Session = _session(tmp_path)
    with Session() as db:
        _remember(db)
        _repoint(db)
        before = _snapshot(db)
        with monkeypatch.context() as scoped:
            for name in ("commit", "flush", "add", "delete"):
                scoped.setattr(db, name, lambda *_args, _name=name, **_kwargs: (_ for _ in ()).throw(AssertionError(f"readonly materializer called db.{_name}")))
            with _forbidden_bombs():
                results = [
                    materializer.materialize_source_alias_parent({"alias": "missing"}, db=db),
                    materializer.materialize_source_alias_parent({"alias": "Sunset Hero"}, db=db),
                    materializer.materialize_source_alias_parent({"alias": "Sunset Hero", "registry_version": 9}, db=db),
                    materializer.materialize_source_alias_parent({"alias": "not-bound", "registry_version": 2}, db=db),
                    materializer.materialize_source_alias_parent({"alias": "x", "registry_version": True}, db=db),
                ]
        after = _snapshot(db)
    assert [(item.status, item.code, item.parent_recipe, item.alias_binding) for item in results] == [
        ("missing", "not_found", None, None),
        ("repointed", "explicit_registry_version_required", None, None),
        ("missing", "registry_version_not_found", None, None),
        ("missing", "alias_not_bound_to_registry_version", None, None),
        ("rejected", "invalid_selector", None, None),
    ]
    assert after == before

    # Resolver outcomes are opaque to this stage: every failure is preserved as a
    # deterministic empty materialization, including ambiguous/archive/corrupt and
    # explicit-version cases.  No registry table is touched while doing so.
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasDomainResult
    outcome_before = _snapshot(db)
    outcomes = {
        "ambiguous": CivitaiSourceAliasDomainResult(status="corrupt", code="non_unique_alias"),
        "archived": CivitaiSourceAliasDomainResult(status="archived", code="target_archived"),
        "corrupt": CivitaiSourceAliasDomainResult(status="corrupt", code="record_invalid"),
        "repointed": CivitaiSourceAliasDomainResult(status="repointed", code="explicit_registry_version_required"),
        "version-missing": CivitaiSourceAliasDomainResult(status="missing", code="registry_version_not_found"),
        "version-mismatch": CivitaiSourceAliasDomainResult(status="missing", code="alias_not_bound_to_registry_version"),
    }
    monkeypatch.setattr(materializer, "resolve_source_alias_exact", lambda alias, *, db: outcomes[alias])
    monkeypatch.setattr(materializer, "resolve_source_alias_exact_version", lambda request, *, db: outcomes[request["alias"]])
    matrix = [
        materializer.materialize_source_alias_parent({"alias": "ambiguous"}, db=db),
        materializer.materialize_source_alias_parent({"alias": "archived"}, db=db),
        materializer.materialize_source_alias_parent({"alias": "corrupt"}, db=db),
        materializer.materialize_source_alias_parent({"alias": "repointed"}, db=db),
        materializer.materialize_source_alias_parent({"alias": "version-missing", "registry_version": 9}, db=db),
        materializer.materialize_source_alias_parent({"alias": "version-mismatch", "registry_version": 2}, db=db),
    ]
    assert [(item.status, item.code, item.parent_recipe, item.parent_recipe_sha256, item.alias_binding) for item in matrix] == [
        ("corrupt", "non_unique_alias", None, None, None),
        ("archived", "target_archived", None, None, None),
        ("corrupt", "record_invalid", None, None, None),
        ("repointed", "explicit_registry_version_required", None, None, None),
        ("missing", "registry_version_not_found", None, None, None),
        ("missing", "alias_not_bound_to_registry_version", None, None, None),
    ]
    assert _snapshot(db) == outcome_before
