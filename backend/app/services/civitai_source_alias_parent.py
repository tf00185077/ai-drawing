"""CIV-SA-T read-only materialization of one audited source-alias Parent Recipe."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.schemas.civitai_source_aliases import (
    CivitaiSourceAliasImmutableIdentity,
    CivitaiSourceAliasLineageBinding,
    CivitaiSourceAliasMaterializedParent,
    CivitaiSourceAliasParentSelector,
    canonical_json,
    canonical_sha256,
)
from app.schemas.generation_recipe import (
    EvidenceRecord,
    GenerationRecipe,
    _build_recipe_from_trusted_evidence,
    _evidence_snapshot_is_verified,
    _issue_trusted_provenance_capability,
)
from app.services.civitai_source_alias_registry import (
    resolve_source_alias_exact,
    resolve_source_alias_exact_version,
)


def _failure(status: str, code: str) -> CivitaiSourceAliasMaterializedParent:
    """Return the single failure shape, never leaking resolver internals or partial targets."""
    return CivitaiSourceAliasMaterializedParent(status=status, code=code)


def _selector(value: Any) -> CivitaiSourceAliasParentSelector | None:
    try:
        raw = value.model_dump(mode="python") if isinstance(value, CivitaiSourceAliasParentSelector) else value
        return CivitaiSourceAliasParentSelector.model_validate(raw, strict=True)
    except (TypeError, ValidationError):
        return None


def _immutable_projection(recipe: GenerationRecipe) -> dict[str, object] | None:
    source = recipe.source
    if source.image_id is not None:
        return {"provider": "civitai", "image_id": source.image_id}
    if source.media_url is None:
        return None
    try:
        return CivitaiSourceAliasImmutableIdentity.model_validate(
            {"provider": "civitai", "media_url": source.media_url}
        ).model_dump(mode="json", exclude_none=True)
    except (TypeError, ValidationError):
        return None


def canonicalize_source_alias_parent_recipe(recipe_payload: Any) -> GenerationRecipe:
    """Return the one canonical Parent form shared by import and materialization."""
    if not isinstance(recipe_payload, dict):
        raise ValueError("persisted recipe must be an object")
    untrusted_recipe = GenerationRecipe.model_validate_json(canonical_json(recipe_payload), strict=True)
    raw_confirmed = recipe_payload.get("confirmed", [])
    if not isinstance(raw_confirmed, list):
        raise ValueError("confirmed evidence must be a list")
    confirmed = [EvidenceRecord.model_validate_json(canonical_json(item), strict=True) for item in raw_confirmed]
    if not confirmed:
        return untrusted_recipe
    recipe = _build_recipe_from_trusted_evidence(
        recipe_payload,
        capability=_issue_trusted_provenance_capability(confirmed),
    )
    if not all(_evidence_snapshot_is_verified(recipe, item) for item in confirmed):
        raise ValueError("persisted evidence verification failed")
    return recipe


def _materialize_success(*, selector: CivitaiSourceAliasParentSelector, record: Any, matched_alias: Any) -> CivitaiSourceAliasMaterializedParent:
    """Revalidate exactly the persisted evidence recipe and its immutable identity."""
    try:
        evidence = record.acquisition_evidence_snapshot
        if not isinstance(evidence, dict) or canonical_sha256(evidence) != record.acquisition_evidence_sha256:
            return _failure("rejected", "acquisition_evidence_invalid")
        recipe_payload = evidence.get("recipe")
        if not isinstance(recipe_payload, dict):
            return _failure("rejected", "persisted_recipe_invalid")
        recipe = canonicalize_source_alias_parent_recipe(recipe_payload)
        canonical_recipe = recipe.model_dump(mode="json", exclude_none=True)
        parent_recipe_sha256 = canonical_sha256(canonical_recipe)
        if parent_recipe_sha256 != record.parent_recipe_sha256:
            return _failure("rejected", "parent_recipe_sha_mismatch")
        try:
            source_identity = CivitaiSourceAliasImmutableIdentity.model_validate(record.source_identity, strict=True)
        except (TypeError, ValueError, ValidationError):
            return _failure("rejected", "source_identity_mismatch")
        projected_identity = _immutable_projection(recipe)
        if projected_identity is None or canonical_json(projected_identity) != canonical_json(source_identity.model_dump(mode="json", exclude_none=True)):
            return _failure("rejected", "source_identity_mismatch")
        binding = CivitaiSourceAliasLineageBinding(
            requested_alias=selector.alias,
            matched_alias=matched_alias,
            registry_version=record.registry_version,
            source_identity=projected_identity,
            acquisition_evidence_sha256=record.acquisition_evidence_sha256,
            parent_recipe_sha256=parent_recipe_sha256,
            registry_created_at=record.created_at,
        )
        # The parent is already reconstructed through GenerationRecipe's internal
        # trusted-evidence boundary.  Constructing the outer typed result normally
        # would revalidate that nested model without its non-serializable capability
        # and demote those verified confirmations.
        return CivitaiSourceAliasMaterializedParent.model_construct(
            status="success",
            code="materialized",
            parent_recipe=recipe,
            parent_recipe_sha256=parent_recipe_sha256,
            alias_binding=binding,
        )
    except (TypeError, ValueError, ValidationError):
        return _failure("rejected", "persisted_recipe_invalid")


def materialize_source_alias_parent(value: Any, *, db: Any) -> CivitaiSourceAliasMaterializedParent:
    """Materialize one exact audited Parent Recipe without direct registry reads or writes."""
    selector = _selector(value)
    if selector is None:
        return _failure("rejected", "invalid_selector")
    if selector.registry_version is None:
        with db.no_autoflush:
            resolved = resolve_source_alias_exact(selector.alias, db=db)
    else:
        with db.no_autoflush:
            resolved = resolve_source_alias_exact_version(
                {"alias": selector.alias, "registry_version": selector.registry_version}, db=db
            )
    if resolved.status != "success" or resolved.record is None or resolved.alias is None:
        return _failure(resolved.status, resolved.code)
    return _materialize_success(selector=selector, record=resolved.record, matched_alias=resolved.alias)
