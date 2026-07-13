"""Frozen CIV-SA-Y Gallery-only audited source-alias backfill service."""
from __future__ import annotations

import hashlib
import json
from datetime import timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db.models import CivitaiSourceAliasBackfillCandidate, GeneratedImage
from app.schemas.civitai_source_alias_backfill import (
    CivitaiSourceAliasBackfillCandidateView,
    CivitaiSourceAliasGalleryBackfillRequest,
    CivitaiSourceAliasGalleryBackfillResult,
)
from app.schemas.civitai_source_aliases import (
    CivitaiSourceAliasImmutableIdentity,
    CivitaiSourceAliasRememberRequest,
    canonical_json,
    canonical_sha256,
)
from app.schemas.generation_recipe import GenerationRecipe
from app.services.civitai_recipe_gallery import ProvenanceValidationError, bundle_from_record
from app.services.civitai_source_alias_registry import remember_source_alias


def _failure(status: str, code: str) -> CivitaiSourceAliasGalleryBackfillResult:
    return CivitaiSourceAliasGalleryBackfillResult(status=status, code=code)


def _candidate_view(row: CivitaiSourceAliasBackfillCandidate) -> CivitaiSourceAliasBackfillCandidateView:
    identity = json.loads(row.source_identity_json)
    evidence = json.loads(row.acquisition_evidence_json)
    identity = CivitaiSourceAliasImmutableIdentity.model_validate(identity, strict=True).model_dump(mode="json", exclude_none=True)
    if canonical_json(identity) != row.source_identity_json:
        raise ValueError("candidate_identity_noncanonical")
    if canonical_json(evidence) != row.acquisition_evidence_json:
        raise ValueError("candidate_evidence_noncanonical")
    if canonical_sha256(evidence) != row.acquisition_evidence_sha256:
        raise ValueError("candidate_evidence_hash_mismatch")
    if row.created_at is None:
        raise ValueError("candidate_created_at_missing")
    created_at = row.created_at if row.created_at.tzinfo is not None else row.created_at.replace(tzinfo=timezone.utc)
    return CivitaiSourceAliasBackfillCandidateView(
        id=row.id,
        gallery_image_id=row.gallery_image_id,
        source_identity=identity,
        acquisition_evidence_snapshot=evidence,
        acquisition_evidence_sha256=row.acquisition_evidence_sha256,
        parent_recipe_sha256=row.parent_recipe_sha256,
        thumbnail_path=row.thumbnail_path,
        suggested_alias=row.suggested_alias,
        created_at=created_at.astimezone(timezone.utc),
    )


def _suggested_alias(identity: dict[str, Any]) -> str:
    if identity.get("image_id") is not None:
        return f"civitai-image-{identity['image_id']}"
    media_url = identity.get("media_url")
    if not isinstance(media_url, str):
        raise ValueError("identity_invalid")
    return f"civitai-media-{hashlib.sha256(media_url.encode('utf-8')).hexdigest()[:12]}"


def _candidate_matches(
    candidate: CivitaiSourceAliasBackfillCandidateView,
    *,
    gallery_image_id: int,
    identity: dict[str, Any],
    evidence: dict[str, Any],
    evidence_sha: str,
    parent_sha: str,
    thumbnail_path: str | None,
) -> bool:
    return (
        candidate.gallery_image_id == gallery_image_id
        and candidate.source_identity == identity
        and candidate.acquisition_evidence_snapshot == evidence
        and candidate.acquisition_evidence_sha256 == evidence_sha
        and candidate.parent_recipe_sha256 == parent_sha
        and candidate.thumbnail_path == thumbnail_path
        and candidate.suggested_alias == _suggested_alias(identity)
    )


def _canonical_target(row: GeneratedImage) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    """Revalidate Gallery provenance and derive the sole permitted Parent target."""
    bundle = bundle_from_record(row, verify_files=False)
    if "variant_lineage" in bundle:
        raise ValueError("variant_lineage_ineligible")
    # Gallery's bundle reader intentionally retains legacy normalization for export.
    # A source-alias binding is a new immutable audit boundary: validate the persisted
    # recipe JSON in strict mode before trusting that normalized bundle projection.
    strict_recipe = GenerationRecipe.model_validate_json(row.recipe_json, strict=True)
    canonical_recipe = strict_recipe.model_dump(mode="json", exclude_none=True)
    if canonical_json(canonical_recipe) != canonical_json(bundle["recipe"]):
        raise ValueError("strict_recipe_bundle_mismatch")
    parent_sha = canonical_sha256(canonical_recipe)
    if parent_sha != bundle["recipe_sha256"]:
        raise ValueError("canonical_parent_hash_mismatch")
    source = canonical_recipe["source"]
    identity_raw: dict[str, Any] = {"provider": "civitai"}
    if source.get("image_id") is not None:
        identity_raw["image_id"] = source["image_id"]
    elif source.get("media_url") is not None:
        identity_raw["media_url"] = source["media_url"]
    else:
        raise ValueError("immutable_identity_missing")
    identity = CivitaiSourceAliasImmutableIdentity.model_validate(identity_raw, strict=True).model_dump(mode="json", exclude_none=True)
    evidence = {
        "recipe": canonical_recipe,
        "backfill_source": {
            "kind": "gallery_recipe",
            "gallery_image_id": row.id,
            "gallery_recipe_sha256": parent_sha,
        },
    }
    return identity, evidence, canonical_sha256(evidence), parent_sha


def backfill_gallery_source_alias(value: Any, *, db: Any) -> CivitaiSourceAliasGalleryBackfillResult:
    """Backfill exactly one verified non-variant Gallery Parent; no API/MCP/runtime effects."""
    try:
        request = value if isinstance(value, CivitaiSourceAliasGalleryBackfillRequest) else CivitaiSourceAliasGalleryBackfillRequest.model_validate(value, strict=True)
    except (ValidationError, TypeError):
        return _failure("ineligible", "invalid_request")
    try:
        rows = db.query(GeneratedImage).filter_by(id=request.gallery_image_id).all()
    except SQLAlchemyError:
        db.rollback()
        return _failure("corrupt", "gallery_lookup_failed")
    if not rows:
        return _failure("ineligible", "gallery_not_found")
    if len(rows) != 1:
        return _failure("corrupt", "gallery_non_unique")
    row = rows[0]
    try:
        identity, evidence, evidence_sha, parent_sha = _canonical_target(row)
    except ProvenanceValidationError as exc:
        return _failure("corrupt", f"gallery_provenance_{exc.code}")
    except (ValidationError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return _failure("ineligible", "gallery_parent_ineligible")

    candidates = db.query(CivitaiSourceAliasBackfillCandidate).filter_by(gallery_image_id=row.id).all()
    if len(candidates) > 1:
        return _failure("corrupt", "candidate_non_unique")
    if candidates:
        try:
            candidate = _candidate_view(candidates[0])
        except Exception:
            return _failure("corrupt", "candidate_invalid")
        if not _candidate_matches(
            candidate,
            gallery_image_id=row.id,
            identity=identity,
            evidence=evidence,
            evidence_sha=evidence_sha,
            parent_sha=parent_sha,
            thumbnail_path=row.image_path,
        ):
            return _failure("corrupt", "candidate_binding_mismatch")
        if request.primary_alias is not None:
            return _failure("conflict", "pending_name_exists")
        return CivitaiSourceAliasGalleryBackfillResult(status="already_backfilled", code="pending_name_exists", candidate=candidate)

    if request.primary_alias is not None:
        try:
            remember_request = CivitaiSourceAliasRememberRequest.model_validate({
                "primary_alias": request.primary_alias,
                "source_identity": identity,
                "acquisition_evidence_snapshot": evidence,
                "acquisition_evidence_sha256": evidence_sha,
                "parent_recipe_sha256": parent_sha,
                "thumbnail_path": row.image_path,
            }, strict=True)
        except (ValidationError, TypeError, ValueError):
            return _failure("ineligible", "alias_invalid")
        try:
            remembered = remember_source_alias(remember_request, db=db)
        except Exception:
            db.rollback()
            return _failure("corrupt", "remember_exception")
        if remembered.status == "conflict" or remembered.status == "archived":
            return _failure("conflict", remembered.code)
        if remembered.status != "success" or remembered.record is None:
            return _failure("corrupt", remembered.code)
        return CivitaiSourceAliasGalleryBackfillResult(
            status="named", code="named" if remembered.code == "created" else "named_idempotent",
            record=remembered.record, source_identity=identity,
            acquisition_evidence_snapshot=evidence, acquisition_evidence_sha256=evidence_sha,
            parent_recipe_sha256=parent_sha,
        )

    candidate = CivitaiSourceAliasBackfillCandidate(
        gallery_image_id=row.id,
        source_identity_json=canonical_json(identity),
        acquisition_evidence_json=canonical_json(evidence),
        acquisition_evidence_sha256=evidence_sha,
        parent_recipe_sha256=parent_sha,
        thumbnail_path=row.image_path,
        suggested_alias=_suggested_alias(identity),
    )
    try:
        db.add(candidate)
        db.commit()
        view = _candidate_view(candidate)
    except IntegrityError:
        db.rollback()
        reread = db.query(CivitaiSourceAliasBackfillCandidate).filter_by(gallery_image_id=row.id).all()
        if len(reread) == 1:
            try:
                existing = _candidate_view(reread[0])
            except Exception:
                return _failure("corrupt", "candidate_invalid")
            if not _candidate_matches(
                existing,
                gallery_image_id=row.id,
                identity=identity,
                evidence=evidence,
                evidence_sha=evidence_sha,
                parent_sha=parent_sha,
                thumbnail_path=row.image_path,
            ):
                return _failure("corrupt", "candidate_binding_mismatch")
            return CivitaiSourceAliasGalleryBackfillResult(
                status="already_backfilled", code="pending_name_exists", candidate=existing
            )
        return _failure("conflict", "candidate_create_conflict")
    except Exception:
        db.rollback()
        return _failure("corrupt", "candidate_persistence_failed")
    return CivitaiSourceAliasGalleryBackfillResult(
        status="pending_name", code="pending_name_created", candidate=view,
        source_identity=identity, acquisition_evidence_snapshot=evidence,
        acquisition_evidence_sha256=evidence_sha, parent_recipe_sha256=parent_sha,
    )
