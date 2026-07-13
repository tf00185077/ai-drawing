"""CIV-V-C backend-owned local Civitai identity ledger contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db.database import get_db
from app.db.models import DownloadedResource
from app.main import app


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _recipe(sha256: str) -> dict:
    return {
        "schema_version": "1.0",
        "source": {"provider": "civitai", "image_id": 123},
        "base_prompt": "positive",
        "negative_prompt": "negative",
        "resources": [{
            "kind": "lora", "name": "mutable-name.safetensors", "sha256": sha256,
            "civitai_model_id": 10, "civitai_model_version_id": 20,
            "civitai_file_id": 30, "air": "urn:air:sd1:lora:civitai:10@20",
        }],
        "sampling": {"seed": 42, "steps": 20, "cfg": 7.0, "sampler": "euler", "scheduler": "normal", "denoise": 1.0, "width": 512, "height": 512},
        "passes": [{"name": "base", "inherits_from": "recipe.sampling"}],
    }


def _client_with_rows(tmp_path: Path, rows: list[dict]) -> TestClient:
    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'ledger.db'}", connect_args={"check_same_thread": False})
    DownloadedResource.__table__.create(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with session_factory.begin() as session:
        session.add_all(DownloadedResource(**row) for row in rows)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _row(path: Path, data: bytes, **overrides: object) -> dict:
    path.write_bytes(data)
    payload: dict[str, object] = {
        "resource_name": path.name,
        "resource_type": "lora",
        "provider": "civitai",
        "source_url": "https://civitai.com/api/download/models/30?token=SUPER_SECRET",
        "resolved_download_url": "https://download.example/model?Authorization=Bearer%20SUPER_SECRET",
        "local_path": str(path),
        "sha256": _sha(data),
        "model_id": "10",
        "version_id": "20",
        "civitai_file_id": "30",
        "air": "urn:air:sd1:lora:civitai:10@20",
        "status": "installed",
    }
    payload.update(overrides)
    return payload


def test_ledger_query_is_stable_filterable_and_secret_redacted(tmp_path: Path) -> None:
    first = _row(tmp_path / "first.safetensors", b"first")
    unavailable = _row(tmp_path / "unavailable.safetensors", b"unavailable", status="planned")
    ignored = _row(tmp_path / "ignored.safetensors", b"ignored", provider="other")
    client = _client_with_rows(tmp_path, [first, unavailable, ignored])
    try:
        response = client.get("/api/civitai-recipes/local-ledger")
        assert response.status_code == 200
        body = response.json()
        assert [entry["local_path"] for entry in body["entries"]] == [str(tmp_path / "first.safetensors"), str(tmp_path / "unavailable.safetensors")]
        assert [entry["availability"] for entry in body["entries"]] == [True, False]
        assert body["snapshot"]["excluded_non_civitai_count"] == 1
        assert "SUPER_SECRET" not in json.dumps(body)

        filtered = client.get("/api/civitai-recipes/local-ledger", params={"kind": "lora", "civitai_model_id": 10, "availability": True})
        assert filtered.status_code == 200
        assert [entry["civitai_file_id"] for entry in filtered.json()["entries"]] == [30]
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_resolve_local_builds_verified_ordered_locks_without_caller_ledger(tmp_path: Path) -> None:
    data = b"verified model"
    client = _client_with_rows(tmp_path, [_row(tmp_path / "local.safetensors", data)])
    try:
        response = client.post("/api/civitai-recipes/resolve-local", json={"recipe": _recipe(_sha(data))})
        assert response.status_code == 200
        body = response.json()
        assert body["report"]["strict"] is True
        assert body["report"]["ready"] is True
        assert [lock["index"] for lock in body["report"]["resource_lock"]] == [0]
        assert body["report"]["resource_lock"][0]["local_path"] == str(tmp_path / "local.safetensors")

        rejected = client.post("/api/civitai-recipes/resolve-local", json={"recipe": _recipe(_sha(data)), "ledger": []})
        assert rejected.status_code == 422
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_resolve_local_fails_closed_for_each_invalid_local_identity_state(tmp_path: Path) -> None:
    data = b"expected"
    sha = _sha(data)
    cases = {
        "missing_identity": [],
        "unavailable": [_row(tmp_path / "unavailable.safetensors", data, status="planned")],
        "duplicate": [_row(tmp_path / "one.safetensors", data), _row(tmp_path / "two.safetensors", data)],
        "conflict": [_row(tmp_path / "conflict.safetensors", data, civitai_file_id="999")],
        "missing_file": [_row(tmp_path / "missing.safetensors", data, local_path=str(tmp_path / "gone.safetensors"))],
        "malformed_id": [_row(tmp_path / "malformed.safetensors", data, model_id="ten")],
        "sha_mismatch": [_row(tmp_path / "tampered.safetensors", b"tampered", sha256=sha)],
    }
    for name, rows in cases.items():
        client = _client_with_rows(tmp_path / name, rows)
        try:
            response = client.post("/api/civitai-recipes/resolve-local", json={"recipe": _recipe(sha)})
            assert response.status_code == 409, name
            report = response.json()["detail"]["report"]
            assert report["ready"] is False, name
            assert report["resource_lock"] == [], name
        finally:
            client.close()
            app.dependency_overrides.clear()


def test_downloaded_resource_identity_columns_are_added_idempotently_without_row_loss(tmp_path: Path, monkeypatch) -> None:
    from app.db import database

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}", connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(text("""CREATE TABLE downloaded_resources (
            id INTEGER PRIMARY KEY, resource_name VARCHAR(512) NOT NULL, resource_type VARCHAR(64) NOT NULL,
            provider VARCHAR(64), source_url TEXT NOT NULL, status VARCHAR(64) NOT NULL
        )"""))
        connection.execute(text("INSERT INTO downloaded_resources (id, resource_name, resource_type, provider, source_url, status) VALUES (7, 'kept', 'lora', 'civitai', 'https://example.invalid', 'installed')"))
    monkeypatch.setattr(database, "engine", engine)

    database.init_db()
    database.init_db()

    columns = {column["name"] for column in inspect(engine).get_columns("downloaded_resources")}
    assert {"civitai_file_id", "air"} <= columns
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id, resource_name FROM downloaded_resources")).one() == (7, "kept")
