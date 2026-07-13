"""CIV-V-G durable, sequential variation-set lifecycle facade."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
import secrets
from typing import Any, Callable, Mapping

from pydantic import ValidationError

from app.core.queue import cancel as queue_cancel, get_job_status as queue_get_job_status
from app.db.models import CivitaiVariationSet, CivitaiVariationSetEvent, CivitaiVariationSetMember, GeneratedImage
from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
from app.schemas.civitai_source_aliases import CivitaiSourceAliasLineageBinding, CivitaiSourceAliasMaterializedParent
from app.schemas.generation_recipe import GenerationRecipe
from app.services.civitai_acquisition import redact_secrets
from app.services.civitai_recipe_gallery import bundle_from_record, canonical_sha256
from app.services.civitai_recipe_variants import (
    VariantFacadeError,
    generate_one_variant,
    generate_one_variant_from_materialized_parent,
)
from app.services.civitai_source_alias_parent import materialize_source_alias_parent


_OPAQUE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_TERMINAL = {"submission_failed": "failed", "failed": "failed", "cancelled": "cancelled", "completed": "completed"}


class VariationSetError(ValueError):
    def __init__(self, phase: str, code: str, message: str = "variation set operation rejected") -> None:
        self.phase, self.code, self.message = phase, code, message
        super().__init__(code)

    def detail(self) -> dict[str, str]:
        return {"phase": self.phase, "code": self.code, "message": self.message}


class InMemoryVariationSetStore:
    """Test-only durable-shape store; production uses the small SQLAlchemy tables."""
    def __init__(self) -> None:
        self.sets: dict[str, dict[str, Any]] = {}

    def create(self, set_id: str, parent_sha: str, members: list[dict[str, Any]]) -> None:
        if set_id in self.sets:
            raise VariationSetError("persistence", "variation_set_id_conflict")
        self.sets[set_id] = {"variation_set_id": set_id, "parent_recipe_sha256": parent_sha, "created_at": datetime.utcnow().isoformat(), "members": [{**deepcopy(item), "events": []} for item in members]}

    def append_event(self, set_id: str, ordinal: int, event_type: str, payload: Mapping[str, Any]) -> None:
        self.sets[set_id]["members"][ordinal]["events"].append({"type": event_type, "payload": redact_secrets(dict(payload)), "created_at": datetime.utcnow().isoformat()})


_SENSITIVE_KEY_NAMES = frozenset({
    "authorization", "api_key", "apikey", "access_token", "token", "secret", "password", "cookie",
})
_SENSITIVE_QUERY_VALUE = re.compile(
    r"([?&](?:authorization|api_key|apikey|access_token|token|secret|password|cookie|signature|sig|policy|expires|x-amz-[^=&#\s]+)=)[^&#\s]*",
    re.IGNORECASE,
)
_SENSITIVE_INLINE_VALUE = re.compile(
    r"\b(authorization|api[_-]?key|access[_-]?token|token|secret|password|cookie)\s*[:=]\s*[^,;\s]+",
    re.IGNORECASE,
)
_STABLE_ERROR_COMPONENT = re.compile(r"^[a-z0-9_]{1,64}$")
_MATERIALIZER_STATUSES = frozenset({"success", "rejected", "missing", "corrupt", "archived", "repointed"})


def _safe(value: Any) -> Any:
    """Recursively redact stored/returned untrusted collaborator and gallery payloads."""
    redacted = redact_secrets(deepcopy(value))

    def scrub(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                key: "[REDACTED]" if str(key).lower().replace("-", "_") in _SENSITIVE_KEY_NAMES else scrub(value)
                for key, value in item.items()
            }
        if isinstance(item, list):
            return [scrub(value) for value in item]
        if isinstance(item, tuple):
            return tuple(scrub(value) for value in item)
        if isinstance(item, str):
            item = _SENSITIVE_QUERY_VALUE.sub(r"\1[REDACTED]", item)
            item = _SENSITIVE_INLINE_VALUE.sub(lambda match: f"{match.group(1)}: [REDACTED]", item)
            return re.sub(r"\bBearer\s+[^\s,;]+", "Bearer [REDACTED]", item, flags=re.IGNORECASE)
        return item

    return scrub(redacted)


def _submission_failure(exc: Exception) -> dict[str, str]:
    """Persist only stable facade phase/code; collaborator messages are never evidence."""
    phase = str(getattr(exc, "phase", "submission"))
    code = str(getattr(exc, "code", "submission_failed"))
    if _STABLE_ERROR_COMPONENT.fullmatch(phase) is None:
        phase = "submission"
    if _STABLE_ERROR_COMPONENT.fullmatch(code) is None:
        code = "submission_failed"
    return {"phase": phase, "code": code, "message": "child submission failed"}


def _identity_from_result(result: Any) -> dict[str, Any]:
    raw = result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)
    keys = ("variant_id", "job_id", "derived_recipe_sha256", "built_child_recipe_sha256", "workflow_sha256", "resource_lock_sha256", "parent_recipe_sha256", "provenance_components")
    identity = {key: raw[key] for key in keys if raw.get(key) is not None}
    if "variant_id" not in identity or "job_id" not in identity:
        raise VariationSetError("submission", "variant_response_invalid")
    return identity


def _source_identity(recipe: GenerationRecipe) -> dict[str, Any]:
    if recipe.source.image_id is not None:
        return {"provider": "civitai", "image_id": recipe.source.image_id}
    if recipe.source.media_url is not None:
        return {"provider": "civitai", "media_url": recipe.source.media_url}
    raise ValueError("source identity invalid")


def _materialize_common_parent(request: Any, *, db: Any) -> tuple[GenerationRecipe, str, CivitaiSourceAliasLineageBinding]:
    """The sole set-level alias gate: no factory, persistence, or child derivation precedes it."""
    try:
        result = materialize_source_alias_parent(request.source_alias, db=db)
    except Exception:
        raise VariationSetError("source_alias_materialization", "materialization_failed") from None
    if not isinstance(result, CivitaiSourceAliasMaterializedParent):
        raise VariationSetError("source_alias_materialization", "materialization_invalid")
    status, code = getattr(result, "status", None), getattr(result, "code", None)
    parent, parent_sha, raw_binding = getattr(result, "parent_recipe", None), getattr(result, "parent_recipe_sha256", None), getattr(result, "alias_binding", None)
    if not isinstance(status, str) or status not in _MATERIALIZER_STATUSES or not isinstance(code, str) or _STABLE_ERROR_COMPONENT.fullmatch(code) is None:
        raise VariationSetError("source_alias_materialization", "materialization_invalid")
    if status != "success":
        if parent is not None or parent_sha is not None or raw_binding is not None:
            raise VariationSetError("source_alias_materialization", "materialization_invalid")
        raise VariationSetError("source_alias_materialization", code)
    try:
        if not isinstance(parent, GenerationRecipe) or not isinstance(parent_sha, str) or not isinstance(raw_binding, CivitaiSourceAliasLineageBinding):
            raise ValueError("partial success")
        binding = CivitaiSourceAliasLineageBinding.model_validate(raw_binding.model_dump(mode="json"))
        canonical_parent_sha = canonical_sha256(parent.model_dump(mode="json", exclude_none=True))
        if (
            canonical_parent_sha != parent_sha.lower()
            or binding.parent_recipe_sha256 != canonical_parent_sha
            or binding.source_identity.model_dump(mode="json", exclude_none=True) != _source_identity(parent)
        ):
            raise ValueError("binding mismatch")
        return parent, canonical_parent_sha, binding
    except (AttributeError, TypeError, ValueError, ValidationError):
        raise VariationSetError("source_alias_materialization", "materialization_invalid") from None


def _create(store: Any, set_id: str, parent_sha: str, members: list[dict[str, Any]]) -> None:
    if isinstance(store, InMemoryVariationSetStore):
        store.create(set_id, parent_sha, members); return
    store.add(CivitaiVariationSet(variation_set_id=set_id, parent_recipe_sha256=parent_sha))
    for member in members:
        store.add(CivitaiVariationSetMember(variation_set_id=set_id, ordinal=member["ordinal"], client_child_key=member["client_child_key"], identity_json=canonical_json(member)))
    store.commit()


def canonical_json(value: Any) -> str:
    from app.services.civitai_recipe_gallery import canonical_json as _canonical_json
    return _canonical_json(value)


def _append(store: Any, set_id: str, ordinal: int, event_type: str, payload: Mapping[str, Any]) -> None:
    payload = _safe(payload)
    if isinstance(store, InMemoryVariationSetStore):
        store.append_event(set_id, ordinal, event_type, payload); return
    store.add(CivitaiVariationSetEvent(variation_set_id=set_id, member_ordinal=ordinal, event_type=event_type, payload_json=canonical_json(payload)))
    store.commit()


def _read(store: Any, set_id: str) -> dict[str, Any]:
    if isinstance(store, InMemoryVariationSetStore):
        found = store.sets.get(set_id)
        if found is None: raise VariationSetError("lookup", "not_found")
        return deepcopy(found)
    row = store.query(CivitaiVariationSet).filter_by(variation_set_id=set_id).first()
    if row is None: raise VariationSetError("lookup", "not_found")
    import json
    members = []
    for member in store.query(CivitaiVariationSetMember).filter_by(variation_set_id=set_id).order_by(CivitaiVariationSetMember.ordinal.asc()).all():
        identity = json.loads(member.identity_json)
        events = []
        for event in store.query(CivitaiVariationSetEvent).filter_by(variation_set_id=set_id, member_ordinal=member.ordinal).order_by(CivitaiVariationSetEvent.id.asc()).all():
            events.append({"type": event.event_type, "payload": json.loads(event.payload_json), "created_at": event.created_at.isoformat()})
        members.append({**identity, "events": events})
    return {"variation_set_id": row.variation_set_id, "parent_recipe_sha256": row.parent_recipe_sha256, "created_at": row.created_at.isoformat(), "members": members}


def _terminal_status(member: Mapping[str, Any]) -> str | None:
    """Terminal evidence is append-only and always wins over mutable queue observations."""
    for event in member.get("events", []):
        terminal = _TERMINAL.get(event["type"])
        if terminal is not None:
            return terminal
    return None


def _last_observed_status(member: Mapping[str, Any]) -> str | None:
    for event in reversed(member.get("events", [])):
        if event["type"] == "queue_observed":
            status = event.get("payload", {}).get("status")
            return status if status in {"queued", "running"} else None
    return None


def _refresh_member(
    store: Any, set_id: str, member: Mapping[str, Any], queue_status: Callable[[str], Any], gallery_lookup: Callable[[str], Any],
) -> str:
    terminal = _terminal_status(member)
    if terminal is not None:
        return terminal
    if not member.get("job_id"):
        return "submitting"
    job_id = member["job_id"]
    # Gallery evidence is the only completion evidence; record it durably once.
    if gallery_lookup(job_id) is not None:
        _append(store, set_id, member["ordinal"], "completed", {"source": "gallery"})
        return "completed"
    try:
        observed = queue_status(job_id)
    except Exception:
        # Queue eviction is not evidence of a terminal state and must not undo history.
        return _last_observed_status(member) or "queued"
    status = observed.get("status") if isinstance(observed, Mapping) else None
    if status == "failed":
        _append(store, set_id, member["ordinal"], "failed", {"source": "queue", "code": "queue_failed"})
        return "failed"
    if status in {"queued", "running"}:
        if _last_observed_status(member) != status:
            _append(store, set_id, member["ordinal"], "queue_observed", {"status": status})
        return status
    return _last_observed_status(member) or "queued"


def _aggregate(states: list[str]) -> dict[str, Any]:
    # Counts describe members only. Aggregate-only labels deliberately remain zero.
    names = ("submitting", "queued", "running", "partially_failed", "completed", "failed", "cancelled", "partially_cancelled")
    counts = {name: states.count(name) for name in names}
    total = len(states); completed = counts["completed"]; failed = counts["failed"]; cancelled = counts["cancelled"]
    if counts["running"]:
        status = "running"
    elif counts["queued"]:
        status = "queued"
    elif cancelled and cancelled != total:
        status = "partially_cancelled"
    elif cancelled == total:
        status = "cancelled"
    elif failed and (completed or failed != total):
        status = "partially_failed"
    elif failed == total:
        status = "failed"
    elif completed == total:
        status = "completed"
    else:
        status = "submitting"
    return {"status": status, "counts": counts, "member_statuses": states}


def _queue_status(job_id: str) -> Any: return queue_get_job_status(job_id)
def _gallery_lookup(db: Any, job_id: str) -> Any:
    return db.query(GeneratedImage).filter_by(job_id=job_id).first() if not isinstance(db, InMemoryVariationSetStore) else None


def _gallery_identity(record: Any) -> dict[str, Any] | None:
    if record is None:
        return None
    return {"id": record.id, "job_id": record.job_id, "image_path": record.image_path}


def create_variation_set(request: Any, *, db: Any, variation_set_id_factory: Callable[[], str] | None = None) -> dict[str, Any]:
    """Create durable members only after a common alias Parent has been fully materialized."""
    alias_binding: CivitaiSourceAliasLineageBinding | None = None
    if request.source_alias is not None:
        parent_recipe, parent_sha, alias_binding = _materialize_common_parent(request, db=db)
    else:
        parent_recipe, parent_sha = request.parent_recipe, request.parent_recipe_sha256.lower()
    # The factory is deliberately after alias preflight: no identity leaks on an alias failure.
    factory = variation_set_id_factory or (lambda: secrets.token_urlsafe(24))
    set_id = factory()
    if not isinstance(set_id, str) or _OPAQUE_ID.fullmatch(set_id) is None: raise VariationSetError("persistence", "variation_set_id_invalid")
    binding_payload = alias_binding.model_dump(mode="json") if alias_binding is not None else None
    identities = [
        {
            "ordinal": index,
            "client_child_key": child.client_child_key,
            **(
                {
                    "parent_recipe_sha256": parent_sha,
                    "source_alias_binding": deepcopy(binding_payload),
                }
                if binding_payload is not None else {}
            ),
        }
        for index, child in enumerate(request.children)
    ]
    _create(db, set_id, parent_sha, identities)
    outcomes = []
    for ordinal, child in enumerate(request.children):
        variant_request = CivitaiRecipeVariantGenerateRequest(
            parent_recipe=parent_recipe if alias_binding is None else None,
            parent_recipe_sha256=parent_sha if alias_binding is None else None,
            source_alias=request.source_alias if alias_binding is not None else None,
            directives=child.directives, model_family=request.model_family,
            runtime_capabilities=request.runtime_capabilities, runtime_provenance=request.runtime_provenance,
            input_bindings=request.input_bindings,
        )
        try:
            if alias_binding is None:
                identity = _identity_from_result(generate_one_variant(variant_request, db=db))
            else:
                identity = _identity_from_result(generate_one_variant_from_materialized_parent(
                    variant_request, parent_recipe=parent_recipe, parent_recipe_sha256=parent_sha,
                    source_alias_binding=alias_binding, db=db,
                ))
                # A Child response cannot overwrite the set's immutable materialized Parent.
                if identity.get("parent_recipe_sha256") != parent_sha or alias_binding.parent_recipe_sha256 != parent_sha:
                    raise VariationSetError("provenance_validation", "provenance_validation")
            if isinstance(db, InMemoryVariationSetStore): db.sets[set_id]["members"][ordinal].update(identity)
            else:
                member = db.query(CivitaiVariationSetMember).filter_by(variation_set_id=set_id, ordinal=ordinal).first(); old = _read(db, set_id)["members"][ordinal]; old.update(identity); member.identity_json = canonical_json({key: value for key, value in old.items() if key != "events"}); db.commit()
            _append(db, set_id, ordinal, "submission_succeeded", {"status": "queued"})
            outcomes.append({"client_child_key": child.client_child_key, "outcome": "submitted", **identity})
        except (VariantFacadeError, VariationSetError) as exc:
            failure = _submission_failure(exc)
            _append(db, set_id, ordinal, "submission_failed", failure)
            outcomes.append({"client_child_key": child.client_child_key, "outcome": "failed", "error": failure})
        except Exception as exc:
            failure = _submission_failure(exc)
            _append(db, set_id, ordinal, "submission_failed", failure)
            outcomes.append({"client_child_key": child.client_child_key, "outcome": "failed", "error": failure})
    view = get_variation_set(set_id, db=db)
    return {"variation_set_id": set_id, "members": outcomes, "aggregate": view["aggregate"]}


def get_variation_set(variation_set_id: str, *, db: Any, queue_status: Callable[[str], Any] | None = None, gallery_lookup: Callable[[str], Any] | None = None) -> dict[str, Any]:
    value = _read(db, variation_set_id)
    queue_status = queue_status or _queue_status
    gallery_lookup = gallery_lookup or (lambda job: _gallery_lookup(db, job))
    states = [
        _refresh_member(db, variation_set_id, member, queue_status, gallery_lookup)
        for member in value["members"]
    ]
    # Reload after append-only observations so the response/export exposes durable history.
    value = _read(db, variation_set_id)
    aggregate = _aggregate(states)
    for member, observed in zip(value["members"], aggregate["member_statuses"]):
        member["status"] = observed
    value["aggregate"] = {"status": aggregate["status"], "counts": aggregate["counts"]}
    return _safe(value)


def cancel_variation_set(variation_set_id: str, *, db: Any, queue_status: Callable[[str], Any] | None = None, cancel: Callable[[str], Any] | None = None, gallery_lookup: Callable[[str], Any] | None = None) -> dict[str, Any]:
    value = _read(db, variation_set_id)
    queue_status = queue_status or _queue_status
    cancel = cancel or queue_cancel
    gallery_lookup = gallery_lookup or (lambda job: _gallery_lookup(db, job))
    for member in value["members"]:
        active_status = _refresh_member(db, variation_set_id, member, queue_status, gallery_lookup)
        if active_status not in {"queued", "running"}:
            continue
        try:
            result = cancel(member["job_id"])
            if result is False:
                raise RuntimeError("cancel_not_accepted")
            _append(db, variation_set_id, member["ordinal"], "cancel_attempt", {"outcome": "accepted"})
            _append(db, variation_set_id, member["ordinal"], "cancelled", {"outcome": "cancelled"})
        except Exception as exc:
            _append(db, variation_set_id, member["ordinal"], "cancel_attempt", {"outcome": "failed", "code": "cancel_failed", "message": exc.__class__.__name__})
    return get_variation_set(variation_set_id, db=db, queue_status=queue_status, gallery_lookup=gallery_lookup)


def _validate_alias_member_binding(member: Mapping[str, Any], *, parent_sha: str) -> dict[str, Any] | None:
    """Alias identities are immutable set evidence, including before a Child succeeds."""
    durable = member.get("source_alias_binding")
    if durable is None:
        return None
    try:
        expected = CivitaiSourceAliasLineageBinding.model_validate(durable).model_dump(mode="json")
        if (
            member.get("parent_recipe_sha256") != parent_sha
            or expected["parent_recipe_sha256"] != parent_sha
        ):
            raise ValueError("durable parent mismatch")
        return expected
    except (AttributeError, KeyError, TypeError, ValueError, ValidationError):
        raise VariationSetError("provenance_validation", "provenance_validation") from None


def _validate_alias_gallery_binding(member: Mapping[str, Any], *, parent_sha: str, gallery_export: Any) -> None:
    """Cross-check a completed alias child without ever minting replacement provenance."""
    expected = _validate_alias_member_binding(member, parent_sha=parent_sha)
    try:
        if not isinstance(gallery_export, Mapping):
            raise ValueError("gallery export invalid")
        lineage = gallery_export.get("variant_lineage")
        gallery_claims_alias = isinstance(lineage, Mapping) and (
            lineage.get("schema_version") == "1.1"
            or "source_alias_binding" in lineage
        )
        if expected is None:
            if gallery_claims_alias:
                raise ValueError("durable alias binding missing")
            return
        if not isinstance(lineage, Mapping) or lineage.get("schema_version") != "1.1":
            raise ValueError("alias lineage missing")
        if lineage.get("parent_recipe_sha256") != parent_sha:
            raise ValueError("lineage parent mismatch")
        if lineage.get("source_alias_binding") != expected:
            raise ValueError("lineage binding mismatch")
        if canonical_sha256({key: value for key, value in lineage.items() if key != "lineage_sha256"}) != lineage.get("lineage_sha256"):
            raise ValueError("lineage digest mismatch")
    except (AttributeError, TypeError, ValueError, ValidationError):
        raise VariationSetError("provenance_validation", "provenance_validation") from None


def export_variation_set(variation_set_id: str, *, db: Any, queue_status: Callable[[str], Any] | None = None, gallery_export: Callable[[str], Any] | None = None, gallery_identity: Callable[[str], Any] | None = None) -> dict[str, Any]:
    view = get_variation_set(variation_set_id, db=db, queue_status=queue_status)
    gallery_export = gallery_export or (lambda job: bundle_from_record(_gallery_lookup(db, job), verify_files=True) if _gallery_lookup(db, job) is not None else None)
    gallery_identity = gallery_identity or (lambda job: _gallery_identity(_gallery_lookup(db, job)))
    members = []
    for member in view["members"]:
        item = deepcopy(member)
        is_alias_member = member.get("source_alias_binding") is not None
        if is_alias_member:
            _validate_alias_member_binding(member, parent_sha=view["parent_recipe_sha256"])
        item["gallery_identity"] = gallery_identity(member["job_id"]) if member.get("job_id") else None
        item["gallery_export"] = gallery_export(member["job_id"]) if member.get("job_id") else None
        if is_alias_member and member.get("status") == "completed" and item["gallery_export"] is None:
            raise VariationSetError("provenance_validation", "provenance_validation")
        if item["gallery_export"] is not None:
            _validate_alias_gallery_binding(member, parent_sha=view["parent_recipe_sha256"], gallery_export=item["gallery_export"])
        members.append(item)
    document = _safe({
        "schema_version": "1.0", "variation_set_id": view["variation_set_id"],
        "parent_recipe_sha256": view["parent_recipe_sha256"], "created_at": view["created_at"],
        "members": members, "aggregate": view["aggregate"],
    })
    # Hash the exact redacted document returned to callers, excluding only its self-hash.
    document["export_sha256"] = canonical_sha256(document)
    return document


def verify_variation_set_export(document: Any) -> bool:
    if not isinstance(document, Mapping) or not isinstance(document.get("export_sha256"), str): return False
    return canonical_sha256({key: value for key, value in document.items() if key != "export_sha256"}) == document["export_sha256"]
