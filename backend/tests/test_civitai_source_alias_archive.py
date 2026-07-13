"""CIV-SA-I atomic audited source-alias archive core contracts."""
from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack, contextmanager
from datetime import timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base


def _sha(value: object) -> str:
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
        "acquisition_evidence_sha256": _sha(evidence),
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
    engine = create_engine(f"sqlite:///{tmp_path / 'alias-archive.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), engine


def _remember(db, **kwargs):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember_source_alias

    result = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_payload(**kwargs)), db=db)
    assert result.status == "success"
    return result


def _archive_request(**overrides):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasArchiveRequest

    value = {"current_primary_alias": "Sunset Hero", "expected_registry_version": 1}
    value.update(overrides)
    return CivitaiSourceAliasArchiveRequest.model_validate(value)


def _snapshot(db):
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord

    return (
        [
            (row.registry_version, row.source_identity_json, row.acquisition_evidence_json, row.acquisition_evidence_sha256,
             row.parent_recipe_sha256, row.thumbnail_url, row.thumbnail_path, row.user_note, row.approved_tags_json,
             row.prompt_summary, row.created_at.isoformat(), row.archived_at.isoformat() if row.archived_at else None)
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
    def bomb(*_args, **_kwargs):
        raise AssertionError("archive invoked a forbidden side-effect path")

    targets = (
        "app.api.civitai_recipes.httpx.get",
        "app.api.civitai_recipes.httpx.post",
        "pathlib.Path.mkdir",
        "pathlib.Path.open",
        "app.api.civitai_recipes.import_recipe",
        "app.services.civitai_recipe_pipeline.build_recipe",
        "app.services.civitai_recipe_pipeline.compile_generation_recipe_workflow",
        "app.services.civitai_recipe_compatibility.preflight_recipe_compatibility",
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


def test_archive_atomically_marks_target_and_preserves_reserved_aliases(tmp_path) -> None:
    """CIV-SA-I-AC1: archive only adds its UTC terminal marker; every alias key remains reserved."""
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import archive_source_alias, exact_resolve, remember_source_alias

    Session, _ = _session(tmp_path)
    with Session() as db:
        remembered = _remember(db)
        before = _snapshot(db)
        with _forbidden_side_effect_bombs():
            archived = archive_source_alias(_archive_request(), db=db)
            after = _snapshot(db)
            resolved = [exact_resolve(alias, db=db) for alias in ("Sunset Hero", "Apple Alternate", "zebra alternate")]
            same = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_payload()), db=db)
            different = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_payload(image_id=999)), db=db)

    assert (archived.status, archived.code) == ("success", "archived")
    assert archived.record.model_dump() == remembered.record.model_dump()
    assert archived.archived_at.tzinfo is not None
    assert after[0][0][:-1] == before[0][0][:-1]
    assert after[0][0][-1] is not None and after[1] == before[1] and len(after[2]) == 1
    assert all((result.status, result.code, result.record, result.alias) == ("archived", "target_archived", None, None) for result in resolved)
    assert (same.status, same.code) == ("conflict", "alias_archived")
    assert (different.status, different.code) == ("conflict", "alias_archived")


def test_archive_appends_terminal_hash_chained_event_without_rewriting_history(tmp_path) -> None:
    """CIV-SA-I-AC2: the archive snapshot is canonical/no-op and is the one immutable chain tail."""
    from app.db.models import CivitaiSourceAliasHistory
    from app.services.civitai_source_alias_registry import (
        archive_source_alias, rename_primary_source_alias, verify_source_alias_history_chain,
    )

    Session, _ = _session(tmp_path)
    with Session() as db:
        _remember(db)
        renamed = rename_primary_source_alias({"current_primary_alias": "Sunset Hero", "new_primary_alias": "Aurora Hero", "expected_registry_version": 1}, db=db)
        rename_row = _snapshot(db)[2][0]
        archived = archive_source_alias(_archive_request(current_primary_alias="Aurora Hero"), db=db)
        events = db.query(CivitaiSourceAliasHistory).order_by(CivitaiSourceAliasHistory.id).all()
        assert renamed.status == "success"
        assert _snapshot(db)[2][0] == rename_row
        assert verify_source_alias_history_chain(1, db=db) is None

    event = events[-1]
    before, after = json.loads(event.before_aliases_json), json.loads(event.after_aliases_json)
    payload = {
        "registry_version": event.registry_version, "operation": "archive", "before_aliases": before,
        "after_aliases": after, "previous_event_sha256": event.previous_event_sha256,
        "created_at": (event.created_at.replace(tzinfo=timezone.utc) if event.created_at.tzinfo is None else event.created_at).isoformat().replace("+00:00", "Z"),
    }
    assert (archived.status, event.operation, before, after) == ("success", "archive", before, before)
    assert event.previous_event_sha256 == events[-2].event_sha256
    assert event.event_sha256 == _sha(payload)
    assert archived.archived_at == (event.created_at.replace(tzinfo=timezone.utc) if event.created_at.tzinfo is None else event.created_at)

    with Session() as db:
        event = db.query(CivitaiSourceAliasHistory).order_by(CivitaiSourceAliasHistory.id.desc()).first()
        event.after_aliases_json = '{"alternates":[],"primary":{}}'
        db.commit()
        assert verify_source_alias_history_chain(1, db=db) == "history_invalid"

    # Every archive-specific verifier failure is fail-closed even if an attacker
    # recomputes individual fields: terminality, canonicality, linkage, and the
    # record/event instant are all part of one audit invariant.
    def assert_history_corrupt(suffix, mutate) -> None:
        ScenarioSession, _ = _session(tmp_path / suffix)
        with ScenarioSession() as scenario_db:
            _remember(scenario_db)
            assert archive_source_alias(_archive_request(), db=scenario_db).status == "success"
            mutate(scenario_db)
            scenario_db.commit()
            assert verify_source_alias_history_chain(1, db=scenario_db) == "history_invalid"

    def append_post_archive_event(scenario_db) -> None:
        tail = scenario_db.query(CivitaiSourceAliasHistory).one()
        scenario_db.add(CivitaiSourceAliasHistory(
            registry_version=1, operation="archive", before_aliases_json=tail.before_aliases_json,
            after_aliases_json=tail.after_aliases_json, previous_event_sha256=tail.event_sha256,
            event_sha256="0" * 64, created_at=tail.created_at,
        ))

    def break_chain(scenario_db) -> None:
        scenario_db.query(CivitaiSourceAliasHistory).one().previous_event_sha256 = "f" * 64

    def make_noncanonical(scenario_db) -> None:
        tail = scenario_db.query(CivitaiSourceAliasHistory).one()
        snapshot = json.loads(tail.before_aliases_json)
        snapshot["alternates"].reverse()
        tail.before_aliases_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def mismatch_archive_instant(scenario_db) -> None:
        from datetime import timedelta
        from app.db.models import CivitaiSourceAliasRegistryRecord

        record = scenario_db.query(CivitaiSourceAliasRegistryRecord).one()
        record.archived_at = record.archived_at + timedelta(microseconds=1)

    assert_history_corrupt("post-archive-event", append_post_archive_event)
    assert_history_corrupt("broken-chain", break_chain)
    assert_history_corrupt("noncanonical-archive", make_noncanonical)
    assert_history_corrupt("archive-instant", mismatch_archive_instant)


def test_archive_and_post_archive_mutations_fail_closed_on_invalid_stale_or_corrupt_state(tmp_path) -> None:
    """CIV-SA-I-AC3: malformed/stale/corrupt inputs and all post-archive mutations never write."""
    from app.db.models import CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import archive_source_alias, rename_primary_source_alias

    Session, _ = _session(tmp_path)
    with Session() as db:
        _remember(db)
        before = _snapshot(db)
        with _forbidden_side_effect_bombs():
            for invalid in (
                {}, {"current_primary_alias": " ", "expected_registry_version": 1},
                {"current_primary_alias": "x" * 513, "expected_registry_version": 1},
                {"current_primary_alias": "Sunset Hero", "expected_registry_version": True},
                {"current_primary_alias": "Sunset Hero", "expected_registry_version": 1, "extra": True},
            ):
                result = archive_source_alias(invalid, db=db)
                assert (result.status, result.code) == ("rejected", "invalid_request")
                assert _snapshot(db) == before
            stale = archive_source_alias(_archive_request(expected_registry_version=2), db=db)
            missing = archive_source_alias(_archive_request(current_primary_alias="Missing"), db=db)
            assert (stale.status, stale.code) == ("rejected", "stale_registry_version")
            assert (missing.status, missing.code) == ("missing", "current_alias_not_found")
            assert _snapshot(db) == before
            archived = archive_source_alias(_archive_request(), db=db)
            post = _snapshot(db)
            renamed = rename_primary_source_alias({"current_primary_alias": "Sunset Hero", "new_primary_alias": "Nope", "expected_registry_version": 1}, db=db)
            repeat = archive_source_alias(_archive_request(), db=db)
        assert (archived.status, renamed.status, renamed.code, repeat.status, repeat.code) == ("success", "rejected", "target_archived", "conflict", "already_archived")
        assert _snapshot(db) == post

    Session, _ = _session(tmp_path / "corrupt")
    with Session() as db:
        _remember(db)
        db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "b" * 64})
        db.commit()
        before = _snapshot(db)
        with _forbidden_side_effect_bombs():
            corrupt = archive_source_alias(_archive_request(), db=db)
        assert corrupt.status == "corrupt"
        assert _snapshot(db) == before

    # CIV-SA-I-AC3 repair regression: a losing remember call observes no alias,
    # then a separate writer creates and archives that exact target before the
    # loser gets its real unique-key IntegrityError.  Recovery must not return
    # idempotent success for an archived target.
    Session, _ = _session(tmp_path / "remember-race")
    with Session() as loser:
        original_flush = loser.flush
        winner_committed = False

        def remember_race_flush(*args, **kwargs):
            nonlocal winner_committed
            if not winner_committed:
                with Session() as winner:
                    _remember(winner)
                    winner_archive = archive_source_alias(_archive_request(), db=winner)
                    assert (winner_archive.status, winner_archive.code) == ("success", "archived")
                winner_committed = True
            return original_flush(*args, **kwargs)

        monkeypatch = __import__("pytest").MonkeyPatch()
        monkeypatch.setattr(loser, "flush", remember_race_flush)
        try:
            from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
            from app.services.civitai_source_alias_registry import remember_source_alias

            with _forbidden_side_effect_bombs():
                losing_remember = remember_source_alias(
                    CivitaiSourceAliasRememberRequest.model_validate(_payload()), db=loser,
                )
        finally:
            monkeypatch.undo()
        assert winner_committed is True
        assert (losing_remember.status, losing_remember.code) == ("conflict", "alias_archived")

    with Session() as fresh:
        records, aliases, history = _snapshot(fresh)
        assert len(records) == len(history) == 1
        assert records[0][-1] is not None and history[0][2] == "archive"
        assert {(row[2], row[3], row[4]) for row in aliases} == {
            ("Sunset Hero", "sunset hero", "primary"),
            ("Apple Alternate", "apple alternate", "alternate"),
            ("zebra alternate", "zebra alternate", "alternate"),
        }


def test_archive_rolls_back_on_interleaving_or_write_failure_with_zero_generation_side_effects(tmp_path, monkeypatch) -> None:
    """CIV-SA-I-AC4: real lifecycle CAS chooses one winner; loser cannot archive or rename after it."""
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import archive_source_alias, rename_primary_source_alias

    Session, _ = _session(tmp_path / "interleaving")
    with Session() as loser:
        _remember(loser)
        original_flush = loser.flush
        won = False

        def race_flush(*args, **kwargs):
            nonlocal won
            if not won and any(isinstance(item, CivitaiSourceAliasHistory) and item.operation == "archive" for item in loser.new):
                with Session() as winner:
                    winner_result = archive_source_alias(_archive_request(), db=winner)
                    assert (winner_result.status, winner_result.code) == ("success", "archived")
                won = True
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(loser, "flush", race_flush)
        with _forbidden_side_effect_bombs():
            losing = archive_source_alias(_archive_request(), db=loser)
        assert (losing.status, losing.code) == ("conflict", "already_archived")

    with Session() as fresh:
        rows = fresh.query(CivitaiSourceAliasRegistryRecord).all()
        events = fresh.query(CivitaiSourceAliasHistory).all()
        assert len(rows) == len(events) == 1
        assert rows[0].archived_at is not None and events[0].operation == "archive"

    Session, _ = _session(tmp_path / "rename-interleaving")
    with Session() as loser:
        _remember(loser)
        original_flush = loser.flush
        won = False

        def rename_race_flush(*args, **kwargs):
            nonlocal won
            if not won and any(getattr(item, "normalized_key", None) == "nope" for item in loser.new):
                with Session() as winner:
                    winner_result = archive_source_alias(_archive_request(), db=winner)
                    assert (winner_result.status, winner_result.code) == ("success", "archived")
                won = True
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(loser, "flush", rename_race_flush)
        with _forbidden_side_effect_bombs():
            losing_rename = rename_primary_source_alias(
                {"current_primary_alias": "Sunset Hero", "new_primary_alias": "Nope", "expected_registry_version": 1}, db=loser,
            )
        assert (losing_rename.status, losing_rename.code) == ("rejected", "target_archived")

    with Session() as fresh:
        rows = fresh.query(CivitaiSourceAliasRegistryRecord).all()
        events = fresh.query(CivitaiSourceAliasHistory).all()
        aliases = fresh.query(CivitaiSourceAlias).all()
        assert len(rows) == len(events) == 1
        assert rows[0].archived_at is not None and events[0].operation == "archive"
        assert {row.normalized_key for row in aliases} == {"sunset hero", "apple alternate", "zebra alternate"}

    Session, _ = _session(tmp_path / "write-failure")
    with Session() as db:
        _remember(db)
        before = _snapshot(db)
        def failed_commit():
            raise RuntimeError("simulated commit failure")
        monkeypatch.setattr(db, "commit", failed_commit)
        with _forbidden_side_effect_bombs():
            failed = archive_source_alias(_archive_request(), db=db)
        assert (failed.status, failed.code) == ("corrupt", "archive_write_failed")
        assert _snapshot(db) == before
