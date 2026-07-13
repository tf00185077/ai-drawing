"""CIV-SA-A audited source-alias registry: offline, fail-closed contracts."""
from __future__ import annotations

import hashlib
import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.database import Base


def _canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _payload(**overrides: object) -> dict[str, object]:
    evidence = {"image": {"id": 123, "meta": {"seed": 42}}, "provider": "civitai"}
    value: dict[str, object] = {
        "primary_alias": "Sunset Hero",
        "alternate_aliases": ["sunset protagonist"],
        "source_identity": {"provider": "civitai", "image_id": 123, "url": "https://civitai.com/images/123"},
        "acquisition_evidence_snapshot": evidence,
        "acquisition_evidence_sha256": _canonical(evidence),
        "parent_recipe_sha256": "a" * 64,
        "thumbnail_url": "https://image.civitai.com/x.jpg",
        "thumbnail_path": "2026-07/hero-thumb.png",
        "user_note": "approved source",
        "approved_tags": ["hero", "sunset"],
        "prompt_summary": "hero at sunset",
    }
    value.update(overrides)
    return value


def _session(tmp_path):
    from app.db import models  # noqa: F401 - register new models

    engine = create_engine(f"sqlite:///{tmp_path / 'aliases.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), engine


def test_normalize_alias_unicode_case_and_whitespace() -> None:
    from app.services.civitai_source_alias_registry import normalize_alias

    assert normalize_alias("  Ｈｅｒｏ\u2003\t\nName  ") == "hero name"
    with pytest.raises(ValueError):
        normalize_alias("\u2002\t\n")


def test_primary_and_alternate_aliases_share_unique_normalized_namespace(tmp_path) -> None:
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember

    Session, _ = _session(tmp_path)
    with Session() as db:
        rejected = CivitaiSourceAliasRememberRequest.model_validate(_payload(primary_alias="Hero", alternate_aliases=["  hero "]))
        result = remember(rejected, db=db)
        assert result.status == "rejected"
        assert result.code == "duplicate_alias_in_request"
        assert db.query(__import__("app.db.models", fromlist=["CivitaiSourceAlias"]).CivitaiSourceAlias).count() == 0

        created = remember(CivitaiSourceAliasRememberRequest.model_validate(_payload(primary_alias="Hero", alternate_aliases=["Other"])), db=db)
        conflict = remember(CivitaiSourceAliasRememberRequest.model_validate(_payload(primary_alias="  hero  ", alternate_aliases=[], source_identity={"provider": "civitai", "image_id": 999})), db=db)
        assert created.status == "success"
        assert conflict.status == "conflict"


@pytest.mark.parametrize(
    "media_url",
    [
        "https://civitai.com/images/123",
        "https://civitai.com/models/123",
        "https://civitai.com/posts/123",
        "https://civitai.com/api/download/models/123",
    ],
)
def test_remember_rejects_non_media_browser_locator_as_immutable_identity(tmp_path, media_url: str) -> None:
    from pydantic import ValidationError
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest

    with pytest.raises(ValidationError, match="immutable media_url"):
        CivitaiSourceAliasRememberRequest.model_validate(
            _payload(source_identity={"provider": "civitai", "media_url": media_url})
        )


def test_remember_accepts_image_id_or_civitai_cdn_media_identity(tmp_path) -> None:
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember

    Session, _ = _session(tmp_path)
    with Session() as db:
        image_id = remember(
            CivitaiSourceAliasRememberRequest.model_validate(
                _payload(source_identity={"provider": "civitai", "image_id": 123})
            ),
            db=db,
        )
        cdn_media = remember(
            CivitaiSourceAliasRememberRequest.model_validate(
                _payload(
                    primary_alias="cdn media",
                    alternate_aliases=[],
                    source_identity={
                        "provider": "civitai",
                        "media_url": "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example.jpg",
                    },
                )
            ),
            db=db,
        )

    assert (image_id.status, cdn_media.status) == ("success", "success")


def test_remember_persists_audited_immutable_target(tmp_path) -> None:
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember

    Session, _ = _session(tmp_path)
    with Session() as db:
        result = remember(CivitaiSourceAliasRememberRequest.model_validate(_payload()), db=db)
        assert result.status == "success"
        assert result.record.registry_version == 1
        assert result.record.source_identity == {"provider": "civitai", "image_id": 123, "url": "https://civitai.com/images/123"}
        assert result.record.acquisition_evidence_sha256 == _payload()["acquisition_evidence_sha256"]
        assert result.record.parent_recipe_sha256 == "a" * 64
        assert result.record.thumbnail_path == "2026-07/hero-thumb.png"


def test_remember_same_alias_same_target_is_idempotent(tmp_path) -> None:
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember

    Session, _ = _session(tmp_path)
    with Session() as db:
        request = CivitaiSourceAliasRememberRequest.model_validate(_payload())
        first = remember(request, db=db)
        second = remember(request, db=db)
        assert (first.status, second.status) == ("success", "success")
        assert first.record.registry_version == second.record.registry_version == 1


def test_remember_conflict_fails_without_mutation(tmp_path) -> None:
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasRegistryRecord
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import remember

    Session, _ = _session(tmp_path)
    with Session() as db:
        created = remember(CivitaiSourceAliasRememberRequest.model_validate(_payload()), db=db)
        before = (db.query(CivitaiSourceAliasRegistryRecord).count(), db.query(CivitaiSourceAlias).count(), created.record.registry_version)
        conflict = remember(CivitaiSourceAliasRememberRequest.model_validate(_payload(source_identity={"provider": "civitai", "image_id": 124})), db=db)
        after = (db.query(CivitaiSourceAliasRegistryRecord).count(), db.query(CivitaiSourceAlias).count(), created.record.registry_version)
        assert conflict.status == "conflict"
        assert before == after


def test_exact_resolve_returns_versioned_immutable_binding(tmp_path) -> None:
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import exact_resolve, remember

    Session, _ = _session(tmp_path)
    with Session() as db:
        remembered = remember(CivitaiSourceAliasRememberRequest.model_validate(_payload()), db=db)
        resolved = exact_resolve("  SUNSET\u2003HERO ", db=db)
        assert resolved.status == "success"
        assert resolved.record.registry_version == remembered.record.registry_version
        assert resolved.alias.original_alias == "Sunset Hero"
        assert resolved.alias.normalized_key == "sunset hero"
        assert resolved.alias.kind == "primary"
        assert resolved.record.acquisition_evidence_snapshot == _payload()["acquisition_evidence_snapshot"]


def test_exact_resolve_missing_fails_closed(tmp_path) -> None:
    from app.services.civitai_source_alias_registry import exact_resolve

    Session, _ = _session(tmp_path)
    with Session() as db:
        result = exact_resolve("not remembered", db=db)
        assert (result.status, result.code, result.record) == ("missing", "not_found", None)


def test_exact_resolve_detects_corrupt_or_non_unique_rows(tmp_path) -> None:
    from app.db.models import CivitaiSourceAliasRegistryRecord
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import exact_resolve, remember

    Session, engine = _session(tmp_path)
    with Session() as db:
        remember(CivitaiSourceAliasRememberRequest.model_validate(_payload()), db=db)
        db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "b" * 64})
        db.commit()
        corrupt = exact_resolve("sunset hero", db=db)
        assert (corrupt.status, corrupt.code) == ("corrupt", "evidence_hash_mismatch")

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE civitai_source_aliases"))
        connection.execute(text("CREATE TABLE civitai_source_aliases (id INTEGER PRIMARY KEY, registry_version INTEGER NOT NULL, original_alias VARCHAR(512) NOT NULL, normalized_key VARCHAR(512) NOT NULL, alias_kind VARCHAR(16) NOT NULL)"))
        connection.execute(text("INSERT INTO civitai_source_aliases (registry_version, original_alias, normalized_key, alias_kind) VALUES (1, 'first', 'duplicate', 'primary'), (1, 'second', 'duplicate', 'alternate')"))
    with Session() as db:
        non_unique = exact_resolve("duplicate", db=db)
        assert (non_unique.status, non_unique.code) == ("corrupt", "non_unique_alias")


def test_registry_models_create_on_fresh_database(tmp_path, monkeypatch) -> None:
    from app.db import database
    from sqlalchemy import inspect

    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()
    assert {"civitai_source_alias_registry_records", "civitai_source_aliases"} <= set(inspect(engine).get_table_names())


def test_registry_constraints_survive_new_session(tmp_path) -> None:
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
    from app.services.civitai_source_alias_registry import exact_resolve, remember

    Session, _ = _session(tmp_path)
    with Session() as first:
        remember(CivitaiSourceAliasRememberRequest.model_validate(_payload()), db=first)
    with Session() as second:
        resolved = exact_resolve("sunset protagonist", db=second)
        assert resolved.status == "success"
        assert resolved.record.registry_version == 1
        assert resolved.record.created_at.tzinfo is not None
