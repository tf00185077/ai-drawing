"""Validate, snapshot and project ordinary image revision annotations.

References stay opaque. This module neither fetches them nor changes prompts.
"""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import GeneratedArtifact
from app.schemas.generate import RevisionContext, RevisionContextRequest


class RevisionParentError(ValueError):
    def __init__(self, status: int, code: str, hint: str):
        self.status = status
        self.detail = {"error": code, "hint": hint}
        super().__init__(code)


def canonical_snapshot(value: Any) -> dict | None:
    """Validate internal/storage shape and detach it from every mutable caller."""
    if value is None:
        return None
    return RevisionContext.model_validate(value).model_dump(mode="json")


def _stored_context(raw: str | None, *, artifact: bool = False) -> dict | None:
    if raw is None or raw == "":
        return None
    value = json.loads(raw)
    if artifact:
        if not isinstance(value, dict):
            raise ValueError("artifact metadata must be an object")
        value = value.get("revision_context")
    elif value is None:
        raise ValueError("nonempty image context must be an object")
    return canonical_snapshot(value)


def project_context(raw: str | None, *, artifact: bool = False) -> dict:
    """Corruption never invents lineage or hides the original image/row."""
    try:
        return {"revision_context": _stored_context(raw, artifact=artifact), "revision_context_error": None}
    except (ValueError, TypeError):
        return {"revision_context": None, "revision_context_error": "revision_context_unavailable"}


def resolve_context(context: RevisionContextRequest | None, db: Session) -> dict | None:
    if context is None:
        return None
    derived = dict(parent_job_id=None, parent_request_ref=None, parent_brief_revision=None,
                   parent_context_status="root")
    if context.parent_artifact_id is not None:
        parent = db.get(GeneratedArtifact, context.parent_artifact_id)
        if parent is None:
            raise RevisionParentError(404, "revision_parent_not_found", "Choose an existing canonical artifact ID.")
        if parent.artifact_type != "image":
            raise RevisionParentError(409, "revision_parent_not_image", "Choose an image artifact as the revision parent.")
        try:
            parent_context = _stored_context(parent.metadata_json, artifact=True)
        except (ValueError, TypeError):
            raise RevisionParentError(409, "revision_parent_context_invalid", "Recover the parent's stored context before using this anchor.") from None
        if parent_context and parent_context["request_ref"] != context.request_ref:
            raise RevisionParentError(409, "revision_request_conflict", "Use the parent's request_ref or choose a parent from this request.")
        derived.update(parent_job_id=parent.job_id, parent_context_status="available" if parent_context else "legacy",
                       parent_request_ref=parent_context["request_ref"] if parent_context else None,
                       parent_brief_revision=parent_context["brief_revision"] if parent_context else None)
    return canonical_snapshot({**context.model_dump(mode="json"), **derived})
