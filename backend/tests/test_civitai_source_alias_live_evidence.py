"""CIV-SA-AB-R2 offline verifier for interrupted import adoption evidence."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
FIXTURE = ROOT / "fixtures" / "civitai" / "source_alias_live_acceptance.json"
EVIDENCE = PROJECT_ROOT / "agent_runs" / "CIV-SA-AB-R2.interrupted-import-adoption.json"
ALIAS = "Violet Rooftop Parent AB"
LOCATOR = "https://civitai.com/images/130519340"
CREATED_AT = "2026-07-13T22:38:38.111398Z"
EXPECTED_BINDING = {
    "original_alias": ALIAS,
    "normalized_alias": "violet rooftop parent ab",
    "registry_version": 1,
    "source_identity": {"provider": "civitai", "image_id": 130519340},
    "acquisition_evidence_sha256": "56155e437ed4bb2017e76420ec0f5e3efc932eedc750e1dc4f418e05f8442d63",
    "parent_recipe_sha256": "7737814089878228bd6decdd390d14396e7d0bf0f1fac9725e6593ba75ae0714",
    "thumbnail_url": "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/c2ac76e4-8bcb-48c0-abde-a8594288bfef/original=true/c2ac76e4-8bcb-48c0-abde-a8594288bfef.jpeg",
    "created_at": CREATED_AT,
}
ZERO_DELTA_FIELDS = (
    "import_calls", "remember_calls", "rename_calls", "archive_calls", "repoint_calls",
    "registry_mutation_calls", "variant_calls", "build_calls", "queue_calls", "generation_calls",
    "gallery_calls", "search_calls", "search_submissions", "raw_backend_http_calls",
    "direct_db_mutation_calls", "queue_internal_calls", "comfyui_api_calls",
)


def canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def verify(document: dict) -> bool:
    """Fail closed unless R2 only adopts the formally resolved immutable R1 binding."""
    try:
        unsigned = {key: value for key, value in document.items() if key != "evidence_sha256"}
        if (
            document["schema"] != "civ-sa-ab-r2.interrupted-import-adoption.v1"
            or canonical(unsigned) != document["evidence_sha256"]
            or document["stage"] != "CIV-SA-AB-R2"
            or document["status"] != "adopted_existing_immutable_binding"
            or document["source"] != {"locator": LOCATOR, "primary_alias": ALIAS}
        ):
            return False

        prior = document["r1_append_only"]
        if prior["stage"] != "CIV-SA-AB-R1" or prior["evidence_file"] != "agent_runs/CIV-SA-AB-R1.live-acceptance.json":
            return False
        if prior["evidence_sha256"] != "7697455b9dbdbd665c9263f5b1831560367d641f1cafac57b9387f8c2c4b697d":
            return False
        if prior["attempt_references"] != [
            {"attempt_id": "CIV-SA-AB-R1.execute.1.executor", "started_at": "2026-07-13T22:35:26.375036Z", "rate_limit_at": "2026-07-13T22:44:59.439502Z", "outcome": "interrupted_rate_limited"},
            {"attempt_id": "CIV-SA-AB-R1.execute.10.executor", "blocked_at": "2026-07-14T01:49:27.748875Z", "outcome": "blocked", "blocker_code": "primary_alias_already_exists"},
        ]:
            return False

        formal = document["formal_stdio"]
        if formal["catalog"] != {"tool_count": 75, "required_tool": "civitai_source_alias_resolve", "required_tool_present": True}:
            return False
        resolved = formal["exact_resolve"]
        if (
            resolved["request"] != {"alias": ALIAS}
            or resolved["outcome"] != "resolved_existing_binding"
            or resolved["binding"] != EXPECTED_BINDING
            or resolved["binding_sha256"] != canonical(EXPECTED_BINDING)
        ):
            return False

        temporal = document["temporal_boundary"]
        if temporal != {
            "created_at": CREATED_AT,
            "first_interrupted_execution": "CIV-SA-AB-R1.execute.1.executor",
            "window_start": "2026-07-13T22:35:26.375036Z",
            "window_end": "2026-07-13T22:44:59.439502Z",
            "created_at_within_window": True,
            "time_is_supporting_evidence_only": True,
        }:
            return False
        if not parse_utc(temporal["window_start"]) <= parse_utc(temporal["created_at"]) <= parse_utc(temporal["window_end"]):
            return False

        calls = document["tool_call_ledger"]
        if calls != [
            {"ordinal": 1, "tool": "list_tools", "request": {}, "response_summary": {"tool_count": 75, "required_tool_present": True}},
            {"ordinal": 2, "tool": "civitai_source_alias_resolve", "request": {"alias": ALIAS}, "response_summary": {"outcome": "resolved_existing_binding", "binding_sha256": canonical(EXPECTED_BINDING)}},
        ]:
            return False
        deltas = document["zero_side_effect_deltas"]
        if set(deltas) != set(ZERO_DELTA_FIELDS) or any(deltas[field] != 0 for field in ZERO_DELTA_FIELDS):
            return False

        inspected = {key: value for key, value in document.items() if key != "redaction"}
        text = json.dumps(inspected, sort_keys=True).lower()
        if any(secret in text for secret in ("authorization", "bearer ", "cookie", "token=", "password=", "x-amz-signature", "signature=")):
            return False
        return document["redaction"] == {
            "secret_fields_absent": ["authorization", "bearer", "cookie", "token", "password", "signature", "signed_url_secret"],
            "portable": True,
        } and document["notes_for_review"] == [
            "Formal stdio performed only catalog listing and one exact alias resolution.",
            "The existing binding is adopted as an immutable historical R1 binding; this recovery neither resumes nor weakens R1.",
            "The created_at correlation supports interrupted execute.1 attribution but is not accepted as an identity substitute.",
            "No Child, search, Gallery, or end-to-end acceptance is claimed.",
        ]
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def mutate(document: dict, *path: object, value: object) -> dict:
    result = deepcopy(document)
    cursor = result
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = value
    return result


def test_interrupted_import_existing_alias_adoption_is_identity_bound_zero_side_effect_and_tamper_evident() -> None:
    document = fixture()
    if EVIDENCE.is_file():
        assert document == json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert verify(document)

    identity_mutations = (
        ("source", "locator"), ("source", "primary_alias"),
        ("formal_stdio", "catalog", "tool_count"), ("formal_stdio", "catalog", "required_tool"),
        ("formal_stdio", "exact_resolve", "request", "alias"),
        ("formal_stdio", "exact_resolve", "binding", "original_alias"),
        ("formal_stdio", "exact_resolve", "binding", "normalized_alias"),
        ("formal_stdio", "exact_resolve", "binding", "registry_version"),
        ("formal_stdio", "exact_resolve", "binding", "source_identity", "provider"),
        ("formal_stdio", "exact_resolve", "binding", "source_identity", "image_id"),
        ("formal_stdio", "exact_resolve", "binding", "acquisition_evidence_sha256"),
        ("formal_stdio", "exact_resolve", "binding", "parent_recipe_sha256"),
        ("formal_stdio", "exact_resolve", "binding", "thumbnail_url"),
        ("r1_append_only", "stage"), ("r1_append_only", "evidence_sha256"),
        ("r1_append_only", "attempt_references", 0, "attempt_id"),
        ("r1_append_only", "attempt_references", 1, "attempt_id"),
    )
    time_mutations = (
        ("formal_stdio", "exact_resolve", "binding", "created_at"),
        ("temporal_boundary", "created_at"), ("temporal_boundary", "window_start"),
        ("temporal_boundary", "window_end"), ("temporal_boundary", "created_at_within_window"),
        ("temporal_boundary", "time_is_supporting_evidence_only"),
        ("r1_append_only", "attempt_references", 0, "started_at"),
        ("r1_append_only", "attempt_references", 0, "rate_limit_at"),
    )
    for path in identity_mutations + time_mutations:
        assert not verify(mutate(document, *path, value="forged")), path
    for field in ZERO_DELTA_FIELDS:
        assert not verify(mutate(document, "zero_side_effect_deltas", field, value=1)), field
    assert not verify(mutate(document, "tool_call_ledger", 1, "tool", value="civitai_recipe_import"))
    assert not verify(mutate(document, "evidence_sha256", value="0" * 64))
