"""CIV-SA-N atomic audited explicit source-alias repoint contracts."""
from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack, contextmanager
from datetime import timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.database import Base


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _replacement(image_id: int = 456, **overrides: object) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 99}}, "provider": "civitai"}
    result: dict[str, object] = {
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence,
        "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "b" * 64,
        "thumbnail_url": "https://image.civitai.com/replacement.jpg",
        "thumbnail_path": "thumbs/replacement.png",
        "user_note": "replacement target",
        "approved_tags": ["replacement", "verified"],
        "prompt_summary": "replacement summary",
    }
    result.update(overrides)
    return result


def _remember_payload(image_id: int = 123) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 42}}, "provider": "civitai"}
    return {
        "primary_alias": "Sunset Hero", "alternate_aliases": ["Apple Alternate", "zebra alternate"],
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence, "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "a" * 64, "thumbnail_url": "https://image.civitai.com/original.jpg",
        "thumbnail_path": "thumbs/original.png", "user_note": "original target", "approved_tags": ["original"],
        "prompt_summary": "original summary",
    }


def _session(tmp_path):
    from app.db import models  # noqa: F401
    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'repoint.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), engine


def _remember(db):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember_source_alias
    result = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_remember_payload()), db=db)
    assert result.status == "success"
    return result


def _request(**overrides):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRepointRequest
    value = {"current_primary_alias": "Sunset Hero", "expected_registry_version": 1, "replacement": _replacement()}
    value.update(overrides)
    return CivitaiSourceAliasRepointRequest.model_validate(value)


def _snapshot(db):
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord, CivitaiSourceAliasRepointTransition
    return (
        [(r.registry_version, r.source_identity_json, r.acquisition_evidence_json, r.acquisition_evidence_sha256, r.parent_recipe_sha256, r.thumbnail_url, r.thumbnail_path, r.user_note, r.approved_tags_json, r.prompt_summary, r.created_at.isoformat(), r.archived_at.isoformat() if r.archived_at else None) for r in db.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)],
        [(r.id, r.registry_version, r.original_alias, r.normalized_key, r.alias_kind) for r in db.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)],
        [(r.id, r.registry_version, r.operation, r.before_aliases_json, r.after_aliases_json, r.previous_event_sha256, r.event_sha256, r.created_at.isoformat()) for r in db.query(CivitaiSourceAliasHistory).order_by(CivitaiSourceAliasHistory.id)],
        [(r.id, r.from_registry_version, r.to_registry_version, r.aliases_json, r.from_record_sha256, r.to_record_sha256, r.source_history_tail_sha256, r.previous_repoint_event_sha256, r.event_sha256, r.created_at.isoformat()) for r in db.query(CivitaiSourceAliasRepointTransition).order_by(CivitaiSourceAliasRepointTransition.id)],
    )


@contextmanager
def _bombs():
    def bomb(*_args, **_kwargs):
        raise AssertionError("repoint invoked forbidden side-effect path")
    targets = (
        "app.api.civitai_recipes.httpx.get", "app.api.civitai_recipes.httpx.post", "pathlib.Path.mkdir", "pathlib.Path.open",
        "app.api.civitai_recipes.import_recipe", "app.services.civitai_recipe_pipeline.build_recipe",
        "app.services.civitai_recipe_pipeline.compile_generation_recipe_workflow", "app.services.civitai_recipe_compatibility.preflight_recipe_compatibility",
        "app.api.civitai_recipes.submit_custom", "app.core.queue.get_comfy_client", "app.core.queue.submit_audited_recipe",
        "app.api.civitai_recipes.build_recipe_provenance_bundle", "app.api.civitai_recipes.generate_one_variant",
    )
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, side_effect=bomb))
        yield


def test_repoint_atomically_creates_replacement_and_keeps_alias_namespace_reserved(tmp_path) -> None:
    """CIV-SA-N-AC1: new immutable target, unchanged alias rows, bare resolve is deliberately ambiguous."""
    from app.services.civitai_source_alias_registry import archive_source_alias, exact_resolve, list_registry_sources, repoint_source_alias, search_registry_sources
    Session, _ = _session(tmp_path)
    with Session() as db:
        old = _remember(db)
        before = _snapshot(db)
        with _bombs():
            result = repoint_source_alias(_request(), db=db)
        after = _snapshot(db)
        primary, alternate = exact_resolve("Sunset Hero", db=db), exact_resolve("Apple Alternate", db=db)
        listed, searched = list_registry_sources(db=db), search_registry_sources("Sunset Hero", db=db)
        archived = archive_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 2}, db=db)
        archived_primary = exact_resolve("Sunset Hero", db=db)
        archived_alternate = exact_resolve("Apple Alternate", db=db)
    assert (result.status, result.code) == ("success", "repointed")
    assert result.from_record.model_dump() == old.record.model_dump()
    assert result.to_record.registry_version == 2
    assert result.to_record.source_identity == _replacement()["source_identity"]
    assert result.to_record.acquisition_evidence_snapshot == _replacement()["acquisition_evidence_snapshot"]
    assert result.to_record.created_at.tzinfo is not None
    assert after[0][0] == before[0][0] and after[2] == before[2]
    assert [(row[0], *row[2:]) for row in after[1]] == [(row[0], *row[2:]) for row in before[1]]
    assert {row[1] for row in after[1]} == {2}
    assert {r[3] for r in after[1]} == {r[3] for r in before[1]}
    assert len(after[3]) == 1
    assert all((r.status, r.code, r.record, r.alias) == ("repointed", "explicit_registry_version_required", None, None) for r in (primary, alternate))
    assert [entry.record.registry_version for entry in listed.entries] == [2]
    assert [candidate.record.registry_version for candidate in searched.candidates] == [2]
    assert archived.status == "success"
    assert all((r.status, r.code, r.record, r.alias) == ("repointed", "explicit_registry_version_required", None, None) for r in (archived_primary, archived_alternate))


def test_repoint_appends_hash_chained_target_transition_and_detects_tampering(tmp_path) -> None:
    """CIV-SA-N-AC2: transition chain binds records, exact alias snapshot, source history tail, and UTC event payload."""
    from app.db.models import CivitaiSourceAliasRepointTransition
    from app.services.civitai_source_alias_registry import repoint_source_alias, verify_source_alias_repoint_chain, list_registry_sources
    Session, _ = _session(tmp_path)
    with Session() as db:
        _remember(db)
        first = repoint_source_alias(_request(), db=db)
        first_row = _snapshot(db)[3][0]
        from app.services.civitai_source_alias_registry import rename_primary_source_alias
        renamed = rename_primary_source_alias({"current_primary_alias": "Sunset Hero", "new_primary_alias": "Aurora Hero", "expected_registry_version": 2}, db=db)
        before_second = _snapshot(db)
        second = repoint_source_alias(_request(current_primary_alias="Aurora Hero", expected_registry_version=2, replacement=_replacement(789)), db=db)
        rows = db.query(CivitaiSourceAliasRepointTransition).order_by(CivitaiSourceAliasRepointTransition.id).all()
        assert (first.status, renamed.status, second.status) == ("success", "success", "success")
        assert _snapshot(db)[3][0] == first_row and verify_source_alias_repoint_chain(db=db) is None
        assert _snapshot(db)[2][0] == before_second[2][0] and json.loads(rows[1].aliases_json)["primary"]["normalized_key"] == "aurora hero"
        assert rows[1].source_history_tail_sha256 == before_second[2][-1][6]
        assert rows[0].previous_repoint_event_sha256 is None and rows[1].previous_repoint_event_sha256 == rows[0].event_sha256
        assert rows[0].created_at.tzinfo is None or rows[0].created_at.tzinfo.utcoffset(rows[0].created_at) is not None
        rows[-1].to_record_sha256 = "0" * 64
        db.commit()
        corrupt = list_registry_sources(db=db)
        retry = repoint_source_alias(_request(expected_registry_version=3, replacement=_replacement(999)), db=db)
    assert (corrupt.status, retry.status) == ("corrupt", "corrupt")

    # A forged but canonical first snapshot must not be rescued by recomputing both event hashes.
    ForgedSession, _ = _session(tmp_path / "forged-snapshot")
    with ForgedSession() as db:
        _remember(db)
        assert repoint_source_alias(_request(), db=db).status == "success"
        assert repoint_source_alias(_request(expected_registry_version=2, replacement=_replacement(789)), db=db).status == "success"
        from app.schemas.civitai_source_aliases import canonical_json, canonical_sha256
        from app.services.civitai_source_alias_registry import _repoint_payload, verify_source_alias_repoint_chain
        rows = db.query(CivitaiSourceAliasRepointTransition).order_by(CivitaiSourceAliasRepointTransition.id).all()
        forged_snapshot = {"primary": {"original_alias": "Forged Primary", "normalized_key": "forged primary"}, "alternates": [{"original_alias": "Apple Alternate", "normalized_key": "apple alternate"}, {"original_alias": "zebra alternate", "normalized_key": "zebra alternate"}]}
        rows[0].aliases_json = canonical_json(forged_snapshot)
        rows[0].event_sha256 = canonical_sha256(_repoint_payload(from_registry_version=rows[0].from_registry_version, to_registry_version=rows[0].to_registry_version, aliases=forged_snapshot, from_record_sha256=rows[0].from_record_sha256, to_record_sha256=rows[0].to_record_sha256, source_history_tail_sha256=rows[0].source_history_tail_sha256, previous_repoint_event_sha256=None, created_at=rows[0].created_at))
        rows[1].previous_repoint_event_sha256 = rows[0].event_sha256
        second_snapshot = json.loads(rows[1].aliases_json)
        rows[1].event_sha256 = canonical_sha256(_repoint_payload(from_registry_version=rows[1].from_registry_version, to_registry_version=rows[1].to_registry_version, aliases=second_snapshot, from_record_sha256=rows[1].from_record_sha256, to_record_sha256=rows[1].to_record_sha256, source_history_tail_sha256=rows[1].source_history_tail_sha256, previous_repoint_event_sha256=rows[1].previous_repoint_event_sha256, created_at=rows[1].created_at))
        db.commit()
        assert verify_source_alias_repoint_chain(db=db) is not None
        assert list_registry_sources(db=db).status == "corrupt"

    # Backend-owned transition time is independently anchored to the replacement
    # record. Rehashing the event (and every downstream link) cannot legitimize a
    # forged timestamp in either a single-edge or multi-edge chain.
    for suffix, edge_count in (("forged-time-single", 1), ("forged-time-chain", 2)):
        TimeSession, _ = _session(tmp_path / suffix)
        with TimeSession() as db:
            _remember(db)
            assert repoint_source_alias(_request(), db=db).status == "success"
            if edge_count == 2:
                assert repoint_source_alias(_request(expected_registry_version=2, replacement=_replacement(789)), db=db).status == "success"
            from app.schemas.civitai_source_aliases import canonical_sha256
            from app.services.civitai_source_alias_registry import _repoint_payload
            rows = db.query(CivitaiSourceAliasRepointTransition).order_by(CivitaiSourceAliasRepointTransition.id).all()
            rows[0].created_at = rows[0].created_at + timedelta(seconds=1)
            previous = None
            for row in rows:
                row.previous_repoint_event_sha256 = previous
                row.event_sha256 = canonical_sha256(_repoint_payload(
                    from_registry_version=row.from_registry_version,
                    to_registry_version=row.to_registry_version,
                    aliases=json.loads(row.aliases_json),
                    from_record_sha256=row.from_record_sha256,
                    to_record_sha256=row.to_record_sha256,
                    source_history_tail_sha256=row.source_history_tail_sha256,
                    previous_repoint_event_sha256=row.previous_repoint_event_sha256,
                    created_at=row.created_at,
                ))
                previous = row.event_sha256
            db.commit()
            assert verify_source_alias_repoint_chain(db=db) is not None
            assert list_registry_sources(db=db).status == "corrupt"


def test_repoint_fail_closed_matrix_preserves_registry_state(tmp_path) -> None:
    """CIV-SA-N-AC3: strict boundary and all ineligible states leave every audited table byte-for-byte unchanged."""
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import archive_source_alias, repoint_source_alias
    Session, _ = _session(tmp_path)
    with Session() as db:
        _remember(db)
        before = _snapshot(db)
        invalid = ({}, {"current_primary_alias": " ", "expected_registry_version": 1, "replacement": _replacement()}, {"current_primary_alias": "Sunset Hero", "expected_registry_version": True, "replacement": _replacement()}, {"current_primary_alias": "Sunset Hero", "expected_registry_version": "1", "replacement": _replacement()}, {"current_primary_alias": "Sunset Hero", "expected_registry_version": 1, "replacement": {**_replacement(), "registry_version": 9}})
        with _bombs():
            for item in invalid:
                assert (repoint_source_alias(item, db=db).status, _snapshot(db)) == ("rejected", before)
            cases = [
                ("missing", {"current_primary_alias": "Missing", "expected_registry_version": 1, "replacement": _replacement()}),
                ("missing", {"current_primary_alias": "Apple Alternate", "expected_registry_version": 1, "replacement": _replacement()}),
                ("rejected", {"current_primary_alias": "Sunset Hero", "expected_registry_version": 2, "replacement": _replacement()}),
                ("rejected", {"current_primary_alias": "Sunset Hero", "expected_registry_version": 1, "replacement": _replacement(123)}),
            ]
            for expected, item in cases:
                assert repoint_source_alias(item, db=db).status == expected
                assert _snapshot(db) == before
            same_selector = _replacement(123, source_identity={"provider": "civitai", "image_id": 123})
            result = repoint_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 1, "replacement": same_selector}, db=db)
            assert (result.status, result.code, _snapshot(db)) == ("rejected", "same_immutable_target", before)
        db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "0" * 64}); db.commit()
        corrupt_before = _snapshot(db)
        assert repoint_source_alias(_request(), db=db).status == "corrupt" and _snapshot(db) == corrupt_before

    # A terminal archive marker is inseparable from its immutable archive event.
    for suffix, mutate in (
        ("cleared-marker", lambda db: setattr(db.query(CivitaiSourceAliasRegistryRecord).one(), "archived_at", None)),
        ("changed-marker", lambda db: setattr(db.query(CivitaiSourceAliasRegistryRecord).one(), "archived_at", db.query(CivitaiSourceAliasRegistryRecord).one().created_at)),
        ("removed-event", lambda db: db.delete(db.query(CivitaiSourceAliasHistory).one())),
    ):
        ScenarioSession, _ = _session(tmp_path / suffix)
        with ScenarioSession() as scenario_db:
            _remember(scenario_db)
            assert archive_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 1}, db=scenario_db).status == "success"
            mutate(scenario_db)
            scenario_db.commit()
            before_corrupt_call = _snapshot(scenario_db)
            exact = __import__("app.services.civitai_source_alias_registry", fromlist=["exact_resolve"]).exact_resolve("Sunset Hero", db=scenario_db)
            listed = __import__("app.services.civitai_source_alias_registry", fromlist=["list_registry_sources"]).list_registry_sources(db=scenario_db)
            searched = __import__("app.services.civitai_source_alias_registry", fromlist=["search_registry_sources"]).search_registry_sources("Sunset Hero", db=scenario_db)
            repointed = repoint_source_alias(_request(), db=scenario_db)
            assert (exact.status, exact.record, exact.alias) == ("corrupt", None, None)
            assert (listed.status, listed.entries, searched.status, searched.candidates, repointed.status, repointed.to_record) == ("corrupt", [], "corrupt", [], "corrupt", None)
            assert _snapshot(scenario_db) == before_corrupt_call

    MediaSession, _ = _session(tmp_path / "same-media-selector")
    with MediaSession() as media_db:
        from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
        from app.services.civitai_source_alias_registry import remember_source_alias
        media_payload = _remember_payload()
        media_payload["source_identity"] = {"provider": "civitai", "media_url": "https://image.civitai.com/immutable/unit.png"}
        assert remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(media_payload), db=media_db).status == "success"
        before_media = _snapshot(media_db)
        media_replacement = _replacement(456, source_identity={"provider": "civitai", "media_url": "https://image.civitai.com/immutable/unit.png"})
        result = repoint_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 1, "replacement": media_replacement}, db=media_db)
        assert (result.status, result.code, _snapshot(media_db)) == ("rejected", "same_immutable_target", before_media)
def test_repoint_concurrency_rollback_and_zero_generation_side_effects(tmp_path, monkeypatch) -> None:
    """CIV-SA-N-AC4: CAS has one winner and every failed write rolls back its replacement/event."""
    from app.db.models import CivitaiSourceAliasRepointTransition, CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import repoint_source_alias
    Session, _ = _session(tmp_path)
    with Session() as loser:
        _remember(loser)
        original_flush, won = loser.flush, False
        def race_flush(*args, **kwargs):
            nonlocal won
            if not won and any(isinstance(item, CivitaiSourceAliasRegistryRecord) and item.registry_version is None for item in loser.new):
                with Session() as winner:
                    assert repoint_source_alias(_request(), db=winner).status == "success"
                won = True
            return original_flush(*args, **kwargs)
        monkeypatch.setattr(loser, "flush", race_flush)
        with _bombs():
            losing = repoint_source_alias(_request(), db=loser)
        assert losing.status in {"rejected", "conflict"}
    with Session() as db:
        assert db.query(CivitaiSourceAliasRegistryRecord).count() == 2
        assert db.query(CivitaiSourceAliasRepointTransition).count() == 1
    Session, _ = _session(tmp_path / "rollback")
    with Session() as db:
        _remember(db); before = _snapshot(db)
        monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(RuntimeError("commit failed")))
        with _bombs():
            failed = repoint_source_alias(_request(), db=db)
        assert (failed.status, failed.code, _snapshot(db)) == ("corrupt", "repoint_write_failed", before)

    # CIV-SA-N-AC4: unrelated target-flush and commit IntegrityErrors are write failures,
    # not fabricated CAS loss; both leave no replacement record or transition behind.
    Session, _ = _session(tmp_path / "integrity-errors")
    with Session() as db:
        _remember(db); before = _snapshot(db)
        original_flush = db.flush
        def fail_target_flush(*args, **kwargs):
            if any(isinstance(item, CivitaiSourceAliasRegistryRecord) and item.registry_version is None for item in db.new):
                raise IntegrityError("INSERT", {}, RuntimeError("target flush failed"))
            return original_flush(*args, **kwargs)
        monkeypatch.setattr(db, "flush", fail_target_flush)
        with _bombs():
            failed_flush = repoint_source_alias(_request(), db=db)
        monkeypatch.setattr(db, "flush", original_flush)
        assert (failed_flush.status, failed_flush.code, _snapshot(db)) == ("corrupt", "repoint_write_failed", before)

    Session, _ = _session(tmp_path / "commit-integrity-error")
    with Session() as db:
        _remember(db); before = _snapshot(db)
        original_commit = db.commit
        monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(IntegrityError("COMMIT", {}, RuntimeError("commit integrity failed"))))
        with _bombs():
            failed_commit = repoint_source_alias(_request(), db=db)
        monkeypatch.setattr(db, "commit", original_commit)
        assert (failed_commit.status, failed_commit.code, _snapshot(db)) == ("corrupt", "repoint_write_failed", before)
