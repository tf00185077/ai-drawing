"""CIV-SA-E deterministic, offline read-only source-alias discovery contracts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.database import Base


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _payload(*, ordinal: int, primary: str, alternates: list[str] | None = None, **overrides: object) -> dict[str, object]:
    evidence = {
        "safe": {"evidence_label": f"evidence-{ordinal}"},
        "token": {"must_not_search": f"secret-{ordinal}"},
        "client_secret": {"must_not_search": f"client-secret-{ordinal}"},
        "refresh_token": {"must_not_search": f"refresh-secret-{ordinal}"},
    }
    payload: dict[str, object] = {
        "primary_alias": primary,
        "alternate_aliases": alternates or [],
        "source_identity": {
            "provider": "civitai",
            "image_id": 1000 + ordinal,
            "url": f"https://civitai.com/images/{1000 + ordinal}",
        },
        "acquisition_evidence_snapshot": evidence,
        "acquisition_evidence_sha256": _canonical_sha256(evidence),
        "parent_recipe_sha256": (format(ordinal % 16, "x") * 64),
        "thumbnail_url": f"https://image.civitai.com/thumbnail-{ordinal}.png",
        "thumbnail_path": f"thumbnails/hidden-{ordinal}.png",
        "user_note": f"note-{ordinal}",
        "approved_tags": [f"tag-{ordinal}"],
        "prompt_summary": f"prompt-{ordinal}",
    }
    payload.update(overrides)
    return payload


def _session(tmp_path):
    from app.db import models  # noqa: F401 - register source alias models

    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'source-alias-discovery.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), engine


def _remember(db, **kwargs: object):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember_source_alias

    result = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_payload(**kwargs)), db=db)
    assert result.status == "success"
    return result


def _snapshot(db) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasRegistryRecord

    return (
        [
            (
                row.registry_version, row.source_identity_json, row.acquisition_evidence_json,
                row.acquisition_evidence_sha256, row.parent_recipe_sha256, row.thumbnail_url,
                row.thumbnail_path, row.user_note, row.approved_tags_json, row.prompt_summary,
                row.created_at.isoformat() if row.created_at is not None else None,
            )
            for row in db.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)
        ],
        [
            (row.id, row.registry_version, row.original_alias, row.normalized_key, row.alias_kind)
            for row in db.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)
        ],
    )


def test_registry_list_is_complete_stable_and_audited(tmp_path) -> None:
    """CIV-SA-E-AC1: list is complete, version-ordered, paged, alias-audited evidence."""
    from app.services.civitai_source_alias_registry import list_registry_sources

    Session, _ = _session(tmp_path)
    with Session() as db:
        first = _remember(db, ordinal=1, primary="First Primary", alternates=["zebra alternate", "Apple Alternate"])
        second = _remember(db, ordinal=2, primary="Second Primary", alternates=["secondary alias"])
        third = _remember(db, ordinal=3, primary="Third Primary")

        full = list_registry_sources(db=db)
        page = list_registry_sources(db=db, offset=1, limit=1)

    assert full.status == "success"
    assert (full.total, full.limit, full.offset) == (3, 50, 0)
    assert [entry.record.registry_version for entry in full.entries] == [
        first.record.registry_version, second.record.registry_version, third.record.registry_version,
    ]
    assert full.entries[0].primary_alias.model_dump() == {
        "original_alias": "First Primary", "normalized_key": "first primary", "kind": "primary",
    }
    assert [item.normalized_key for item in full.entries[0].alternate_aliases] == ["apple alternate", "zebra alternate"]
    audited = full.entries[0].record
    assert audited.source_identity == _payload(ordinal=1, primary="unused")["source_identity"]
    assert audited.acquisition_evidence_snapshot == _payload(ordinal=1, primary="unused")["acquisition_evidence_snapshot"]
    assert audited.acquisition_evidence_sha256 == _payload(ordinal=1, primary="unused")["acquisition_evidence_sha256"]
    assert audited.parent_recipe_sha256 == _payload(ordinal=1, primary="unused")["parent_recipe_sha256"]
    assert (audited.thumbnail_url, audited.thumbnail_path, audited.user_note, audited.approved_tags, audited.prompt_summary) == (
        "https://image.civitai.com/thumbnail-1.png", "thumbnails/hidden-1.png", "note-1", ["tag-1"], "prompt-1",
    )
    assert audited.created_at.tzinfo is not None
    assert (page.status, page.total, page.limit, page.offset) == ("success", 3, 1, 1)
    assert [entry.record.registry_version for entry in page.entries] == [second.record.registry_version]


def test_registry_search_uses_only_frozen_persisted_corpus_and_score_formula(tmp_path) -> None:
    """CIV-SA-E-AC2: exact and weighted scoring search only the six frozen fields."""
    from app.services.civitai_source_alias_registry import search_registry_sources

    Session, _ = _session(tmp_path)
    with Session() as db:
        _remember(
            db,
            ordinal=7,
            primary="Solar Hero",
            alternates=["Day Champion"],
            user_note="note-only",
            approved_tags=["tag-only"],
            prompt_summary="prompt-only",
        )
        exact_primary = search_registry_sources("  ＳＯＬＡＲ\u2003hero ", db=db)
        exact_alternate = search_registry_sources("day champion", db=db)
        weighted = search_registry_sources("solar tag-only", db=db)
        hits = {
            "primary": search_registry_sources("solar", db=db),
            "alternate": search_registry_sources("champion", db=db),
            "tag": search_registry_sources("tag-only", db=db),
            "note": search_registry_sources("note-only", db=db),
            "prompt": search_registry_sources("prompt-only", db=db),
            "metadata": search_registry_sources("evidence-7", db=db),
        }
        excluded = [
            search_registry_sources("thumbnail-7", db=db),
            search_registry_sources("hidden-7", db=db),
            search_registry_sources("2025-01", db=db),
            search_registry_sources("h" * 64, db=db),
            search_registry_sources(_payload(ordinal=7, primary="unused")["acquisition_evidence_sha256"], db=db),
            search_registry_sources("secret-7", db=db),
            search_registry_sources("client-secret-7", db=db),
            search_registry_sources("refresh-secret-7", db=db),
        ]

    assert exact_primary.normalized_query == "solar hero"
    assert [(candidate.score, candidate.matched_fields) for candidate in exact_primary.candidates] == [(1000, ["primary_alias"])]
    assert [(candidate.score, candidate.matched_fields) for candidate in exact_alternate.candidates] == [(900, ["alternate_aliases"])]
    assert [(candidate.score, candidate.matched_fields) for candidate in weighted.candidates] == [(170, ["primary_alias", "approved_tags"])]
    expected = {
        "primary": (100, ["primary_alias"]),
        "alternate": (90, ["alternate_aliases"]),
        "tag": (70, ["approved_tags"]),
        "note": (50, ["user_note"]),
        "prompt": (30, ["prompt_summary"]),
        "metadata": (40, ["source_metadata"]),
    }
    assert {name: (result.candidates[0].score, result.candidates[0].matched_fields) for name, result in hits.items()} == expected
    assert all(result.status == "success" and result.candidates == [] for result in excluded)


def test_registry_search_returns_ranked_candidates_matched_fields_and_source_evidence(tmp_path) -> None:
    """CIV-SA-E-AC3: candidates only, deterministic ranking/paging, no exact-resolve fallback."""
    from app.services.civitai_source_alias_registry import search_registry_sources

    Session, _ = _session(tmp_path)
    with Session() as db:
        first = _remember(db, ordinal=1, primary="Solar Hero", alternates=["hero alternate"], approved_tags=["bright"])
        second = _remember(db, ordinal=2, primary="Solar Other", alternates=["other alternate"], approved_tags=["bright"])
        third = _remember(db, ordinal=3, primary="Other", approved_tags=["bright"])

        def bomb(*_args, **_kwargs):
            raise AssertionError("discovery must not call an exact resolver or side-effect path")

        with patch("app.services.civitai_source_alias_registry.exact_resolve", side_effect=bomb):
            ranked = search_registry_sources("solar bright", db=db)
            exact_like = search_registry_sources("solar hero", db=db, limit=1)
            empty = search_registry_sources("not-present", db=db)

    assert ranked.status == "success"
    assert ranked.total == 2
    assert [(item.score, item.record.registry_version, item.matched_fields) for item in ranked.candidates] == [
        (170, first.record.registry_version, ["primary_alias", "approved_tags"]),
        (170, second.record.registry_version, ["primary_alias", "approved_tags"]),
    ]
    assert ranked.candidates[0].primary_alias.kind == "primary"
    assert ranked.candidates[0].record.acquisition_evidence_snapshot == _payload(ordinal=1, primary="unused")["acquisition_evidence_snapshot"]
    assert not hasattr(ranked, "selected") and not hasattr(ranked, "resolved_target")
    assert (exact_like.total, len(exact_like.candidates), exact_like.candidates[0].score) == (1, 1, 1000)
    assert (empty.status, empty.total, empty.candidates) == ("success", 0, [])
    assert third.record.registry_version == 3


def test_registry_discovery_fails_closed_on_invalid_or_corrupt_data_and_has_zero_side_effects(tmp_path) -> None:
    """CIV-SA-E-AC4: invalid input/corruption returns typed no-write results and no forbidden calls."""
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import list_registry_sources, search_registry_sources

    Session, engine = _session(tmp_path)
    with Session() as db:
        _remember(db, ordinal=9, primary="Valid Primary", alternates=["valid alternate"])
        before_invalid = _snapshot(db)

        def bomb(*_args, **_kwargs):
            raise AssertionError("read-only discovery invoked a forbidden side-effect path")

        with (
            patch("app.services.civitai_source_alias_registry.exact_resolve", side_effect=bomb),
            patch("app.services.civitai_recipe_pipeline.compile_generation_recipe_workflow", side_effect=bomb),
            patch("app.services.civitai_recipe_pipeline.build_recipe", side_effect=bomb),
            patch("app.api.civitai_recipes.submit_custom", side_effect=bomb),
            patch("app.api.civitai_recipes.httpx.get", side_effect=bomb),
            patch("app.core.queue.get_comfy_client", side_effect=bomb),
            patch("pathlib.Path.mkdir", side_effect=bomb),
        ):
            invalid = [
                list_registry_sources(db=db, limit=0),
                list_registry_sources(db=db, limit=101),
                list_registry_sources(db=db, offset=-1),
                search_registry_sources(" \t\n", db=db),
                search_registry_sources("x" * 513, db=db),
                search_registry_sources("valid", db=db, limit=0),
                search_registry_sources("valid", db=db, offset=-1),
            ]
        assert all(result.status == "rejected" for result in invalid)
        assert _snapshot(db) == before_invalid

        corruptions = ["missing_primary", "duplicate_key", "dangling", "identity", "evidence", "nan", "infinity", "tags", "hash"]

    for name in corruptions:
        Session, engine = _session(tmp_path / name)
        with Session() as db:
            _remember(db, ordinal=9, primary="Valid Primary", alternates=["valid alternate"])
            if name == "duplicate_key":
                with engine.begin() as connection:
                    connection.execute(text("DROP TABLE civitai_source_aliases"))
                    connection.execute(text("CREATE TABLE civitai_source_aliases (id INTEGER PRIMARY KEY, registry_version INTEGER NOT NULL, original_alias VARCHAR(512) NOT NULL, normalized_key VARCHAR(512) NOT NULL, alias_kind VARCHAR(16) NOT NULL)"))
                    connection.execute(text("INSERT INTO civitai_source_aliases (registry_version, original_alias, normalized_key, alias_kind) VALUES (1, 'one', 'duplicate', 'primary'), (1, 'two', 'duplicate', 'alternate')"))
            elif name == "missing_primary":
                db.query(CivitaiSourceAlias).filter_by(alias_kind="primary").delete()
                db.commit()
            elif name == "dangling":
                db.add(CivitaiSourceAlias(registry_version=999, original_alias="dangling", normalized_key="dangling", alias_kind="primary"))
                db.commit()
            elif name == "identity":
                db.query(CivitaiSourceAliasRegistryRecord).update({"source_identity_json": "{}"})
                db.commit()
            elif name == "evidence":
                db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_json": "{bad"})
                db.commit()
            elif name == "nan":
                db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_json": '{"x":NaN}'})
                db.commit()
            elif name == "infinity":
                db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_json": '{"x":Infinity}'})
                db.commit()
            elif name == "tags":
                db.query(CivitaiSourceAliasRegistryRecord).update({"approved_tags_json": '["", ""]'})
                db.commit()
            elif name == "hash":
                db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "f" * 64})
                db.commit()
            before = _snapshot(db)
            with (
                patch("app.services.civitai_source_alias_registry.exact_resolve", side_effect=bomb),
                patch("app.services.civitai_recipe_pipeline.compile_generation_recipe_workflow", side_effect=bomb),
                patch("app.services.civitai_recipe_pipeline.build_recipe", side_effect=bomb),
                patch("app.api.civitai_recipes.submit_custom", side_effect=bomb),
                patch("app.api.civitai_recipes.httpx.get", side_effect=bomb),
                patch("app.core.queue.get_comfy_client", side_effect=bomb),
                patch("pathlib.Path.mkdir", side_effect=bomb),
            ):
                listed = list_registry_sources(db=db)
                searched = search_registry_sources("valid", db=db)
            assert listed.status == searched.status == "corrupt", name
            assert _snapshot(db) == before
