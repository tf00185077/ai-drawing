"""CIV-SA-Q audited explicit-version exact source-alias resolution contracts."""
from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _remember_payload(image_id: int = 123) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 42}}, "provider": "civitai"}
    return {
        "primary_alias": "Sunset Hero", "alternate_aliases": ["Apple Alternate"],
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence, "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "a" * 64, "approved_tags": ["original"],
    }


def _replacement(image_id: int = 456) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 99}}, "provider": "civitai"}
    return {
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence, "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "b" * 64, "approved_tags": ["replacement"],
    }


def _session(tmp_path):
    from app.db import models  # noqa: F401
    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'versioned-resolve.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _remember(db):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember_source_alias
    result = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_remember_payload()), db=db)
    assert result.status == "success"
    return result


def _repoint(db, version: int, image_id: int):
    from app.services.civitai_source_alias_registry import repoint_source_alias
    result = repoint_source_alias({"current_primary_alias": "Sunset Hero" if version == 1 else "Aurora Hero", "expected_registry_version": version, "replacement": _replacement(image_id)}, db=db)
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
def _bombs():
    def bomb(*_args, **_kwargs):
        raise AssertionError("versioned resolve invoked forbidden side-effect path")
    targets = (
        "app.api.civitai_recipes.httpx.get", "app.api.civitai_recipes.httpx.post", "pathlib.Path.mkdir", "pathlib.Path.open",
        "app.api.civitai_recipes.import_recipe", "app.services.civitai_source_alias_registry.search_registry_sources",
        "app.services.civitai_source_alias_registry.list_registry_sources", "app.services.civitai_source_alias_registry.exact_resolve",
        "app.services.civitai_source_alias_registry.rename_primary_source_alias", "app.services.civitai_source_alias_registry.archive_source_alias",
        "app.services.civitai_source_alias_registry.repoint_source_alias", "app.services.civitai_recipe_pipeline.build_recipe",
        "app.services.civitai_recipe_pipeline.compile_generation_recipe_workflow", "app.services.civitai_recipe_compatibility.preflight_recipe_compatibility",
        "app.api.civitai_recipes.submit_custom", "app.core.queue.get_comfy_client", "app.core.queue.submit_audited_recipe",
        "app.services.civitai_recipe_gallery.build_recipe_provenance_bundle", "app.services.civitai_recipe_variants.generate_one_variant",
        "app.services.civitai_recipe_variation_sets.create_variation_set", "app.api.civitai_recipes.build_recipe_provenance_bundle",
        "app.api.civitai_recipes.generate_one_variant",
    )
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, side_effect=bomb))
        yield


def test_explicit_version_resolve_selects_current_repoint_target_and_keeps_bare_resolve_closed(tmp_path) -> None:
    """CIV-SA-Q-AC1: explicit current version is exact; bare resolve remains deliberately closed."""
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasExplicitVersionResolveRequest
    from app.services.civitai_source_alias_registry import exact_resolve, resolve_source_alias_exact_version
    Session = _session(tmp_path)
    with Session() as db:
        _remember(db)
        target = _repoint(db, 1, 456)
        primary = resolve_source_alias_exact_version(CivitaiSourceAliasExplicitVersionResolveRequest.model_validate({"alias": " SUNSET HERO ", "registry_version": 2}), db=db)
        alternate = resolve_source_alias_exact_version({"alias": "apple alternate", "registry_version": 2}, db=db)
        bare = [exact_resolve(value, db=db) for value in ("Sunset Hero", "Apple Alternate")]
    assert [(result.status, result.code) for result in (primary, alternate)] == [("success", "resolved_explicit_version")] * 2
    assert all(result.record.model_dump() == target.to_record.model_dump() for result in (primary, alternate))
    assert (primary.alias.original_alias, primary.alias.kind) == ("Sunset Hero", "primary")
    assert (alternate.alias.original_alias, alternate.alias.kind) == ("Apple Alternate", "alternate")
    assert all((result.status, result.code, result.record, result.alias) == ("repointed", "explicit_registry_version_required", None, None) for result in bare)


def test_explicit_version_resolve_can_select_audited_superseded_version_by_its_final_alias_snapshot(tmp_path) -> None:
    """CIV-SA-Q-AC2: historical versions resolve only their own final outgoing audited snapshot."""
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasExplicitVersionResolveRequest
    from app.services.civitai_source_alias_registry import rename_primary_source_alias, resolve_source_alias_exact_version
    Session = _session(tmp_path)
    with Session() as db:
        v1 = _remember(db)
        _repoint(db, 1, 456)
        assert rename_primary_source_alias({"current_primary_alias": "Sunset Hero", "new_primary_alias": "Aurora Hero", "expected_registry_version": 2}, db=db).status == "success"
        v2 = _repoint(db, 2, 789).from_record
        first = resolve_source_alias_exact_version(CivitaiSourceAliasExplicitVersionResolveRequest.model_validate({"alias": "Apple Alternate", "registry_version": 1}), db=db)
        second = resolve_source_alias_exact_version({"alias": "Aurora Hero", "registry_version": 2}, db=db)
        repeat = resolve_source_alias_exact_version({"alias": "Aurora Hero", "registry_version": 2}, db=db)
        wrong_current = resolve_source_alias_exact_version({"alias": "No Such Alias", "registry_version": 2}, db=db)
    assert (first.status, first.code, first.record.model_dump(), first.alias.original_alias, first.alias.kind) == ("success", "resolved_explicit_version", v1.record.model_dump(), "Apple Alternate", "alternate")
    assert (second.status, second.code, second.record.model_dump(), second.alias.original_alias, second.alias.kind) == ("success", "resolved_explicit_version", v2.model_dump(), "Aurora Hero", "primary")
    assert repeat.model_dump() == second.model_dump()
    assert (wrong_current.status, wrong_current.code, wrong_current.record, wrong_current.alias) == ("missing", "alias_not_bound_to_registry_version", None, None)


def test_explicit_version_resolve_fail_closed_matrix_returns_no_target(tmp_path, monkeypatch) -> None:
    """CIV-SA-Q-AC3: every strict, absent, lifecycle, and audited-corruption failure leaks no target."""
    from app.db.models import CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord, CivitaiSourceAliasRepointTransition
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasExplicitVersionResolveRequest
    from app.services.civitai_source_alias_registry import archive_source_alias, rename_primary_source_alias, resolve_source_alias_exact_version
    Session = _session(tmp_path)
    with pytest.raises(ValidationError):
        CivitaiSourceAliasExplicitVersionResolveRequest.model_validate({"alias": " ", "registry_version": 1})
    for invalid in ({}, {"alias": "x", "registry_version": True}, {"alias": "x", "registry_version": "1"}, {"alias": "x", "registry_version": 1.0}, {"alias": "x", "registry_version": 0}, {"alias": "x", "registry_version": -1}, {"alias": "x", "registry_version": 1, "extra": True}, {"alias": "x" * 513, "registry_version": 1}):
        with pytest.raises(ValidationError):
            CivitaiSourceAliasExplicitVersionResolveRequest.model_validate(invalid)
    with Session() as db:
        _remember(db)
        cases = [
            resolve_source_alias_exact_version({"alias": "Sunset Hero", "registry_version": 9}, db=db),
            resolve_source_alias_exact_version({"alias": "No Such Alias", "registry_version": 1}, db=db),
        ]
        assert archive_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 1}, db=db).status == "success"
        cases.append(resolve_source_alias_exact_version({"alias": "Sunset Hero", "registry_version": 1}, db=db))
        db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "0" * 64}); db.commit()
        cases.append(resolve_source_alias_exact_version({"alias": "Sunset Hero", "registry_version": 1}, db=db))
    assert [(item.status, item.code, item.record, item.alias) for item in cases] == [
        ("missing", "registry_version_not_found", None, None),
        ("missing", "alias_not_bound_to_registry_version", None, None),
        ("archived", "target_archived", None, None),
        ("corrupt", "evidence_hash_mismatch", None, None),
    ]

    def corrupt(suffix, mutate, expected_code: str, *, alias: str = "Sunset Hero", version: int = 2) -> None:
        Scenario = _session(tmp_path / suffix)
        with Scenario() as db:
            _remember(db)
            _repoint(db, 1, 456)
            mutate(db)
            db.commit()
            result = resolve_source_alias_exact_version({"alias": alias, "registry_version": version}, db=db)
        assert (result.status, result.code, result.record, result.alias) == ("corrupt", expected_code, None, None)

    corrupt("identity", lambda db: setattr(db.query(CivitaiSourceAliasRegistryRecord).filter_by(registry_version=2).one(), "source_identity_json", "{}"), "identity_invalid")
    corrupt("noncanonical-snapshot", lambda db: setattr(db.query(CivitaiSourceAliasRepointTransition).one(), "aliases_json", '{"primary":{"original_alias":"Sunset Hero","normalized_key":"sunset hero"},"alternates":[]} '), "repoint_invalid")
    corrupt("duplicate-snapshot", lambda db: setattr(db.query(CivitaiSourceAliasRepointTransition).one(), "aliases_json", json.dumps({"primary": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero"}, "alternates": [{"original_alias": "Apple Alternate", "normalized_key": "apple alternate"}, {"original_alias": "Apple Alternate", "normalized_key": "apple alternate"}]}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))), "repoint_invalid")
    corrupt("dangling-transition", lambda db: setattr(db.query(CivitaiSourceAliasRepointTransition).one(), "to_registry_version", 999), "repoint_invalid")
    corrupt("transition-timestamp", lambda db: setattr(db.query(CivitaiSourceAliasRepointTransition).one(), "created_at", db.query(CivitaiSourceAliasRepointTransition).one().created_at + timedelta(seconds=1)), "repoint_invalid")
    corrupt("transition-hash", lambda db: setattr(db.query(CivitaiSourceAliasRepointTransition).one(), "event_sha256", "0" * 64), "repoint_invalid")

    def corrupt_history(db) -> None:
        assert rename_primary_source_alias({"current_primary_alias": "Sunset Hero", "new_primary_alias": "Aurora Hero", "expected_registry_version": 2}, db=db).status == "success"
        db.query(CivitaiSourceAliasHistory).filter_by(registry_version=2).one().event_sha256 = "0" * 64
    corrupt("history", corrupt_history, "history_invalid", alias="Aurora Hero")

    # SQLite constraints preclude malformed duplicate records/edges; a backend-owned
    # query double injects those corrupted read results without altering production schema.
    DuplicateRecordSession = _session(tmp_path / "duplicate-record")
    with DuplicateRecordSession() as db:
        _remember(db); _repoint(db, 1, 456)
        original_query, version_two_filters = db.query, 0
        def duplicate_record_query(model, *args, **kwargs):
            nonlocal version_two_filters
            query = original_query(model, *args, **kwargs)
            if model is not CivitaiSourceAliasRegistryRecord:
                return query
            original_filter_by = query.filter_by
            def filter_by(**filters):
                nonlocal version_two_filters
                selected = original_filter_by(**filters)
                if filters == {"registry_version": 2}:
                    version_two_filters += 1
                    if version_two_filters == 2:
                        row = selected.one()
                        return type("DuplicateRows", (), {"all": lambda self: [row, row]})()
                return selected
            query.filter_by = filter_by
            return query
        monkeypatch.setattr(db, "query", duplicate_record_query)
        duplicate_record = resolve_source_alias_exact_version({"alias": "Sunset Hero", "registry_version": 2}, db=db)
    assert (duplicate_record.status, duplicate_record.code, duplicate_record.record, duplicate_record.alias) == ("corrupt", "record_non_unique_or_missing", None, None)
    monkeypatch.undo()

    ForkSession = _session(tmp_path / "fork-cycle-link")
    with ForkSession() as db:
        _remember(db); _repoint(db, 1, 456)
        assert rename_primary_source_alias({"current_primary_alias": "Sunset Hero", "new_primary_alias": "Aurora Hero", "expected_registry_version": 2}, db=db).status == "success"
        _repoint(db, 2, 789)
        rows = db.query(CivitaiSourceAliasRepointTransition).order_by(CivitaiSourceAliasRepointTransition.id).all()
        rows[1].previous_repoint_event_sha256 = None
        db.commit()
        link = resolve_source_alias_exact_version({"alias": "Aurora Hero", "registry_version": 2}, db=db)
    assert (link.status, link.code, link.record, link.alias) == ("corrupt", "repoint_invalid", None, None)

    CycleSession = _session(tmp_path / "cycle")
    with CycleSession() as db:
        _remember(db); _repoint(db, 1, 456)
        assert rename_primary_source_alias({"current_primary_alias": "Sunset Hero", "new_primary_alias": "Aurora Hero", "expected_registry_version": 2}, db=db).status == "success"
        _repoint(db, 2, 789)
        db.query(CivitaiSourceAliasRepointTransition).order_by(CivitaiSourceAliasRepointTransition.id).all()[1].to_registry_version = 1
        db.commit()
        cycle = resolve_source_alias_exact_version({"alias": "Aurora Hero", "registry_version": 2}, db=db)
    assert (cycle.status, cycle.code, cycle.record, cycle.alias) == ("corrupt", "repoint_invalid", None, None)

    ForkSession = _session(tmp_path / "fork")
    with ForkSession() as db:
        _remember(db); _repoint(db, 1, 456)
        original_query = db.query
        def forked_transition_query(model, *args, **kwargs):
            query = original_query(model, *args, **kwargs)
            if model is not CivitaiSourceAliasRepointTransition:
                return query
            ordered = query.order_by
            def order_by(*order_args):
                selected = ordered(*order_args)
                rows = selected.all()
                return type("ForkedTransitionRows", (), {"all": lambda self: [*rows, rows[0]]})()
            query.order_by = order_by
            return query
        monkeypatch.setattr(db, "query", forked_transition_query)
        fork = resolve_source_alias_exact_version({"alias": "Sunset Hero", "registry_version": 2}, db=db)
    assert (fork.status, fork.code, fork.record, fork.alias) == ("corrupt", "repoint_invalid", None, None)
    monkeypatch.undo()


def test_explicit_version_resolve_is_read_only_and_has_zero_generation_side_effects(tmp_path, monkeypatch) -> None:
    """CIV-SA-Q-AC4: all representative paths preserve all four audited tables and avoid every forbidden boundary."""
    from app.db.models import CivitaiSourceAliasRepointTransition
    from app.services.civitai_source_alias_registry import archive_source_alias, resolve_source_alias_exact_version

    def run_case(suffix, request, expected, prepare=lambda db: None) -> None:
        Scenario = _session(tmp_path / suffix)
        with Scenario() as db:
            _remember(db)
            _repoint(db, 1, 456)
            prepare(db)
            before = _snapshot(db)
            with monkeypatch.context() as scoped:
                for name in ("commit", "flush", "add", "delete"):
                    scoped.setattr(db, name, lambda *_args, _name=name, **_kwargs: (_ for _ in ()).throw(AssertionError(f"read-only resolver called db.{_name}")))
                scoped.setattr("app.services.civitai_source_alias_registry.update", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("read-only resolver called SQL update")))
                with _bombs():
                    result = resolve_source_alias_exact_version(request, db=db)
            after = _snapshot(db)
        assert (result.status, result.code, result.record is None, result.alias is None) == expected
        assert after == before

    # AC1 current success, AC2 historical success, and each required AC3 representative
    # are independently snapshotted so one path cannot mask another path's write.
    run_case("current", {"alias": "Sunset Hero", "registry_version": 2}, ("success", "resolved_explicit_version", False, False))
    run_case("historical", {"alias": "Apple Alternate", "registry_version": 1}, ("success", "resolved_explicit_version", False, False))
    run_case("invalid", {"alias": "Sunset Hero", "registry_version": True}, ("rejected", "invalid_request", True, True))
    run_case("missing-version", {"alias": "Sunset Hero", "registry_version": 9}, ("missing", "registry_version_not_found", True, True))
    run_case("mismatch", {"alias": "No Such Alias", "registry_version": 2}, ("missing", "alias_not_bound_to_registry_version", True, True))
    run_case(
        "archived", {"alias": "Sunset Hero", "registry_version": 2}, ("archived", "target_archived", True, True),
        lambda db: (_ for _ in ()).throw(AssertionError("archive setup failed")) if archive_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 2}, db=db).status != "success" else None,
    )
    run_case(
        "corrupt", {"alias": "Sunset Hero", "registry_version": 2}, ("corrupt", "repoint_invalid", True, True),
        lambda db: (setattr(db.query(CivitaiSourceAliasRepointTransition).one(), "event_sha256", "0" * 64), db.commit()),
    )
