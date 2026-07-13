"""CIV-SA-H atomic audited primary source-alias rename contracts."""
from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack, contextmanager
from datetime import timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.database import Base


def _canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _payload(*, primary: str = "Sunset Hero", alternates: list[str] | None = None, image_id: int = 123) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 42}}, "provider": "civitai"}
    return {
        "primary_alias": primary,
        "alternate_aliases": ["zebra alternate", "Apple Alternate"] if alternates is None else alternates,
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence,
        "acquisition_evidence_sha256": _canonical(evidence),
        "parent_recipe_sha256": "a" * 64,
        "thumbnail_url": "https://image.civitai.com/x.jpg",
        "thumbnail_path": "2026-07/hero-thumb.png",
        "user_note": "approved source",
        "approved_tags": ["hero", "sunset"],
        "prompt_summary": "hero at sunset",
    }


def _session(tmp_path):
    from app.db import models  # noqa: F401

    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'alias-rename.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), engine


def _remember(db, **kwargs):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember_source_alias

    result = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_payload(**kwargs)), db=db)
    assert result.status == "success"
    return result


def _request(**kwargs):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRenameRequest

    values = {"current_primary_alias": "Sunset Hero", "new_primary_alias": "Aurora Hero", "expected_registry_version": 1}
    values.update(kwargs)
    return CivitaiSourceAliasRenameRequest.model_validate(values)


def _snapshot(db):
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord

    return (
        [
            (row.registry_version, row.source_identity_json, row.acquisition_evidence_json, row.acquisition_evidence_sha256,
             row.parent_recipe_sha256, row.thumbnail_url, row.thumbnail_path, row.user_note, row.approved_tags_json,
             row.prompt_summary, row.created_at.isoformat())
            for row in db.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)
        ],
        [(row.id, row.registry_version, row.original_alias, row.normalized_key, row.alias_kind)
         for row in db.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)],
        [(row.id, row.registry_version, row.operation, row.before_aliases_json, row.after_aliases_json,
          row.previous_event_sha256, row.event_sha256, row.created_at.isoformat())
         for row in db.query(CivitaiSourceAliasHistory).order_by(CivitaiSourceAliasHistory.id)],
    )


@contextmanager
def _forbidden_side_effect_bombs():
    """Fail if the offline rename core reaches any frozen forbidden subsystem."""
    def bomb(*_args, **_kwargs):
        raise AssertionError("rename invoked a forbidden side-effect path")

    targets = (
        # HTTP/network and filesystem boundaries.
        "app.api.civitai_recipes.httpx.get",
        "app.api.civitai_recipes.httpx.post",
        "pathlib.Path.mkdir",
        "pathlib.Path.open",
        # Civitai import, compiler/build, and compatibility boundaries.
        "app.api.civitai_recipes.import_recipe",
        "app.services.civitai_recipe_pipeline.build_recipe",
        "app.services.civitai_recipe_pipeline.compile_generation_recipe_workflow",
        "app.services.civitai_recipe_compatibility.preflight_recipe_compatibility",
        # Queue/ComfyUI submission, Gallery provenance, and generation facades.
        "app.api.civitai_recipes.submit_custom",
        "app.core.queue.get_comfy_client",
        "app.core.queue.submit_audited_recipe",
        "app.api.civitai_recipes.build_recipe_provenance_bundle",
        "app.api.civitai_recipes.generate_one_variant",
    )
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, side_effect=bomb))
        yield


def test_rename_primary_alias_atomically_preserves_old_exact_alias_and_target(tmp_path) -> None:
    """CIV-SA-H-AC1: new primary and preserved old alternate resolve to one immutable target."""
    from app.services.civitai_source_alias_registry import (
        exact_resolve, list_registry_sources, rename_primary_source_alias, search_registry_sources,
    )

    Session, _ = _session(tmp_path)
    with Session() as db:
        remembered = _remember(db)
        original_target = remembered.record.model_dump()
        result = rename_primary_source_alias(_request(), db=db)
        new = exact_resolve("  AURORA\u2003HERO ", db=db)
        old = exact_resolve("sunset hero", db=db)
        listed = list_registry_sources(db=db)
        searched = search_registry_sources("sunset hero", db=db)

    assert (result.status, result.code) == ("success", "renamed")
    assert result.record.model_dump() == original_target
    assert result.new_primary.original_alias == "Aurora Hero"
    assert (result.preserved_old_alternate.original_alias, result.preserved_old_alternate.kind) == ("Sunset Hero", "alternate")
    assert [alias.normalized_key for alias in result.alternate_aliases] == ["apple alternate", "sunset hero", "zebra alternate"]
    assert (new.status, old.status) == ("success", "success")
    assert new.record.model_dump() == old.record.model_dump() == original_target
    assert (new.alias.kind, old.alias.kind) == ("primary", "alternate")
    assert (listed.total, len(listed.entries), listed.entries[0].primary_alias.original_alias) == (1, 1, "Aurora Hero")
    assert searched.candidates[0].record.registry_version == remembered.record.registry_version


def test_rename_appends_hash_chained_audit_history_without_rewriting_prior_events(tmp_path) -> None:
    """CIV-SA-H-AC2: canonical snapshots and hash chaining are append-only and tamper-detecting."""
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory
    from app.services.civitai_source_alias_registry import rename_primary_source_alias, verify_source_alias_history_chain

    Session, _ = _session(tmp_path)
    with Session() as db:
        _remember(db)
        first = rename_primary_source_alias(_request(), db=db)
        first_persisted = _snapshot(db)[2][0]
        second = rename_primary_source_alias(_request(current_primary_alias="Aurora Hero", new_primary_alias="Moon Hero"), db=db)
        events = db.query(CivitaiSourceAliasHistory).order_by(CivitaiSourceAliasHistory.id).all()
        assert db.query(CivitaiSourceAliasHistory).count() == 2
        assert _snapshot(db)[2][0] == first_persisted
        assert verify_source_alias_history_chain(1, db=db) is None

    assert (first.status, second.status) == ("success", "success")
    assert json.loads(events[0].before_aliases_json) == {
        "alternates": [
            {"normalized_key": "apple alternate", "original_alias": "Apple Alternate"},
            {"normalized_key": "zebra alternate", "original_alias": "zebra alternate"},
        ],
        "primary": {"normalized_key": "sunset hero", "original_alias": "Sunset Hero"},
    }
    assert json.loads(events[1].after_aliases_json)["primary"]["normalized_key"] == "moon hero"
    assert events[0].previous_event_sha256 is None
    assert events[1].previous_event_sha256 == events[0].event_sha256
    for event in events:
        payload = {
            "registry_version": event.registry_version,
            "operation": event.operation,
            "before_aliases": json.loads(event.before_aliases_json),
            "after_aliases": json.loads(event.after_aliases_json),
            "previous_event_sha256": event.previous_event_sha256,
            "created_at": (event.created_at.replace(tzinfo=timezone.utc) if event.created_at.tzinfo is None else event.created_at).isoformat().replace("+00:00", "Z"),
        }
        assert _canonical(payload) == event.event_sha256

    with Session() as db:
        event = db.query(CivitaiSourceAliasHistory).filter_by(id=events[-1].id).one()
        event.after_aliases_json = '{"primary":{}}'
        db.commit()
        before = _snapshot(db)
        corrupt = rename_primary_source_alias(_request(current_primary_alias="Moon Hero", new_primary_alias="Bad"), db=db)
        assert (corrupt.status, corrupt.code) == ("corrupt", "history_invalid")
        assert _snapshot(db) == before

    # A recomputed hash cannot make a semantically noncanonical alternate order valid.
    Session, _ = _session(tmp_path / "noncanonical-alternates")
    with Session() as db:
        _remember(db)
        renamed = rename_primary_source_alias(_request(), db=db)
        assert renamed.status == "success"
        event = db.query(CivitaiSourceAliasHistory).one()
        after = json.loads(event.after_aliases_json)
        after["alternates"].reverse()
        event.after_aliases_json = json.dumps(after, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        event.event_sha256 = _canonical({
            "registry_version": event.registry_version,
            "operation": event.operation,
            "before_aliases": json.loads(event.before_aliases_json),
            "after_aliases": after,
            "previous_event_sha256": event.previous_event_sha256,
            "created_at": (event.created_at.replace(tzinfo=timezone.utc) if event.created_at.tzinfo is None else event.created_at).isoformat().replace("+00:00", "Z"),
        })
        db.commit()
        before = _snapshot(db)
        corrupt = rename_primary_source_alias(_request(current_primary_alias="Aurora Hero", new_primary_alias="Bad"), db=db)
        assert (corrupt.status, corrupt.code) == ("corrupt", "history_invalid")
        assert _snapshot(db) == before

    # A valid chain must still terminate in the actual alias rows before the next write.
    Session, _ = _session(tmp_path / "tail-does-not-match-rows")
    with Session() as db:
        _remember(db)
        renamed = rename_primary_source_alias(_request(), db=db)
        assert renamed.status == "success"
        primary = db.query(CivitaiSourceAlias).filter_by(alias_kind="primary").one()
        primary.original_alias = "Drift Hero"
        primary.normalized_key = "drift hero"
        db.commit()
        before = _snapshot(db)
        corrupt = rename_primary_source_alias(_request(current_primary_alias="Drift Hero", new_primary_alias="Bad"), db=db)
        assert (corrupt.status, corrupt.code) == ("corrupt", "history_invalid")
        assert _snapshot(db) == before


def test_rename_fails_closed_on_invalid_conflicting_stale_or_corrupt_state(tmp_path) -> None:
    """CIV-SA-H-AC3: rejected/conflict/missing/corrupt inputs leave all audited state untouched."""
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import rename_primary_source_alias

    Session, _ = _session(tmp_path)
    with Session() as db:
        _remember(db)
        before = _snapshot(db)
        for invalid in (
            {"current_primary_alias": " ", "new_primary_alias": "Valid", "expected_registry_version": 1},
            {"current_primary_alias": "Sunset Hero", "new_primary_alias": "x" * 513, "expected_registry_version": 1},
            {"current_primary_alias": "Sunset Hero", "new_primary_alias": "Valid", "expected_registry_version": 0},
            {"current_primary_alias": "Sunset Hero", "new_primary_alias": "Valid", "expected_registry_version": True},
            {"current_primary_alias": "Sunset Hero", "new_primary_alias": "Valid", "expected_registry_version": "1"},
            {"current_primary_alias": "Sunset Hero", "new_primary_alias": "Valid", "expected_registry_version": 1, "unexpected": True},
        ):
            result = rename_primary_source_alias(invalid, db=db)
            assert (result.status, result.code) == ("rejected", "invalid_request")
            assert _snapshot(db) == before
        result = rename_primary_source_alias(_request(new_primary_alias=" sunset\u2003hero "), db=db)
        assert (result.status, result.code) == ("rejected", "alias_unchanged")
        assert _snapshot(db) == before

    scenarios = [
        ("conflict", lambda db: _remember(db, primary="Taken", alternates=[]), _request(new_primary_alias="Taken")),
        ("missing", lambda db: None, _request(current_primary_alias="Missing")),
        ("rejected", lambda db: None, _request(expected_registry_version=2)),
        ("corrupt", lambda db: db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "b" * 64}), _request()),
        ("corrupt", lambda db: db.query(CivitaiSourceAlias).filter_by(alias_kind="primary").update({"alias_kind": "alternate"}), _request()),
    ]
    for index, (status, corrupt, request) in enumerate(scenarios):
        Session, _ = _session(tmp_path / str(index))
        with Session() as db:
            _remember(db)
            corrupt(db)
            db.commit()
            before = _snapshot(db)
            result = rename_primary_source_alias(request, db=db)
            assert result.status == status
            assert _snapshot(db) == before


def test_rename_rolls_back_on_concurrent_collision_and_has_zero_generation_side_effects(tmp_path, monkeypatch) -> None:
    """CIV-SA-H-AC4: success/failure matrix and race stay inside the offline rename core."""
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import exact_resolve, rename_primary_source_alias

    # Every representative typed outcome executes under the same complete set of
    # forbidden-boundary bombs.  Setup/corruption happens before the call so the
    # bombs prove the rename operation itself is offline and generation-free.
    Session, _ = _session(tmp_path / "success")
    with Session() as db:
        _remember(db)
        before = _snapshot(db)
        with _forbidden_side_effect_bombs():
            success = rename_primary_source_alias(_request(), db=db)
        after = _snapshot(db)
        assert (success.status, success.code) == ("success", "renamed")
        assert after[0] == before[0]
        assert [(row[2], row[4]) for row in after[1]] == [
            ("Sunset Hero", "alternate"),
            ("zebra alternate", "alternate"),
            ("Apple Alternate", "alternate"),
            ("Aurora Hero", "primary"),
        ]
        assert len(after[2]) == len(before[2]) + 1
        event = after[2][-1]
        assert (event[1], event[2], event[5], event[6]) == (
            success.record.registry_version,
            "rename",
            success.event.previous_event_sha256,
            success.event.event_sha256,
        )
        assert json.loads(event[3]) == success.event.before_aliases == {
            "primary": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero"},
            "alternates": [
                {"original_alias": "Apple Alternate", "normalized_key": "apple alternate"},
                {"original_alias": "zebra alternate", "normalized_key": "zebra alternate"},
            ],
        }
        assert json.loads(event[4]) == success.event.after_aliases == {
            "primary": {"original_alias": "Aurora Hero", "normalized_key": "aurora hero"},
            "alternates": [
                {"original_alias": "Apple Alternate", "normalized_key": "apple alternate"},
                {"original_alias": "Sunset Hero", "normalized_key": "sunset hero"},
                {"original_alias": "zebra alternate", "normalized_key": "zebra alternate"},
            ],
        }

    failure_cases = (
        ("rejected", "invalid_request", {"current_primary_alias": "Sunset Hero", "new_primary_alias": "Valid", "expected_registry_version": True}, None),
        ("conflict", "alias_already_bound", _request(new_primary_alias="Taken"), "conflict"),
        ("missing", "current_alias_not_found", _request(current_primary_alias="Missing"), None),
        ("corrupt", "evidence_hash_mismatch", _request(), "corrupt"),
    )
    for index, (expected_status, expected_code, request, setup) in enumerate(failure_cases):
        Session, _ = _session(tmp_path / f"typed-{index}")
        with Session() as db:
            _remember(db)
            if setup == "conflict":
                _remember(db, primary="Taken", alternates=[], image_id=456)
            elif setup == "corrupt":
                db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "b" * 64})
                db.commit()
            before = _snapshot(db)
            with _forbidden_side_effect_bombs():
                result = rename_primary_source_alias(request, db=db)
            assert (result.status, result.code) == (expected_status, expected_code)
            assert _snapshot(db) == before

    Session, _ = _session(tmp_path / "concurrent")
    with Session() as db:
        original = _remember(db)
        winner = _remember(db, primary="Winner Target", alternates=[], image_id=456)
        original_target = original.record.model_dump()
        before = _snapshot(db)
        original_flush = db.flush
        winner_committed = False

        def collision_flush(*args, **kwargs):
            nonlocal winner_committed
            if any(getattr(item, "normalized_key", None) == "aurora hero" for item in db.new):
                # The loser has completed its preflight reads.  A distinct Session wins
                # the namespace key before the loser's flush is forced to fail.
                with Session() as winner_db:
                    winner_db.add(CivitaiSourceAlias(
                        registry_version=winner.record.registry_version,
                        original_alias="Aurora Hero",
                        normalized_key="aurora hero",
                        alias_kind="alternate",
                    ))
                    winner_db.commit()
                winner_committed = True
                raise IntegrityError("insert", {}, Exception("unique collision"))
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(db, "flush", collision_flush)
        with _forbidden_side_effect_bombs():
            result = rename_primary_source_alias(_request(), db=db)
        assert (result.status, result.code) == ("conflict", "alias_already_bound")
        assert winner_committed is True

    with Session() as fresh:
        new = exact_resolve("Aurora Hero", db=fresh)
        old = exact_resolve("Sunset Hero", db=fresh)
        post_collision = _snapshot(fresh)
        assert (new.status, new.record.registry_version) == ("success", winner.record.registry_version)
        assert (old.status, old.record.model_dump()) == ("success", original_target)
        # The losing transaction left every immutable record/history row intact;
        # the only additional alias is the independently committed winner key.
        assert post_collision[0] == before[0]
        assert post_collision[2] == before[2]
        assert [(row[1], row[2], row[3], row[4]) for row in post_collision[1]] == [
            (original.record.registry_version, "Sunset Hero", "sunset hero", "primary"),
            (original.record.registry_version, "zebra alternate", "zebra alternate", "alternate"),
            (original.record.registry_version, "Apple Alternate", "apple alternate", "alternate"),
            (winner.record.registry_version, "Winner Target", "winner target", "primary"),
            (winner.record.registry_version, "Aurora Hero", "aurora hero", "alternate"),
        ]
