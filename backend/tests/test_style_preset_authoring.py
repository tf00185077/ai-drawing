"""add-style-preset-authoring：create_preset 寫 detail + note + reindex"""
import json

import pytest
from fastapi.testclient import TestClient

from app.core import style_presets as sp
from app.core.style_presets import (
    DirStylePresetProvider,
    PresetExistsError,
    ResourceInventory,
)
from app.main import app


def _provider(tmp_path) -> DirStylePresetProvider:
    agent = tmp_path / "style_presets" / "agent"
    agent.mkdir(parents=True)
    return DirStylePresetProvider(agent, project_root=tmp_path)


def _inv():
    return ResourceInventory(checkpoints=("m.safetensors",), workflows=("default",))


# --- core -----------------------------------------------------------------


def test_create_writes_detail_note_and_index(tmp_path) -> None:
    prov = _provider(tmp_path)
    r = prov.create_preset({"id": "creator-x", "name": "X", "checkpoint": "m.safetensors", "template": "default"})
    assert r["created"] and r["id"] == "creator-x"
    # detail + note + index 都在
    assert (tmp_path / "style_presets/agent/presets/creator-x.json").exists()
    note = tmp_path / "style_presets/human/creator-x.md"
    assert note.exists()
    assert "preset_id: creator-x" in note.read_text(encoding="utf-8")
    assert {s["id"] for s in prov.list_summaries()} == {"creator-x"}


def test_created_preset_passes_note_validation(tmp_path) -> None:
    prov = _provider(tmp_path)
    prov.create_preset({"id": "cx", "name": "X", "checkpoint": "m.safetensors", "template": "default"})
    v = prov.validate_preset("cx", _inv())
    # note_path / note_preset_id 不應出現在 missing（frontmatter 對齊）
    assert not any(m.resource_type in ("note_path", "note_preset_id") for m in v.missing)
    assert v.valid


def test_create_duplicate_rejected(tmp_path) -> None:
    prov = _provider(tmp_path)
    prov.create_preset({"id": "dup", "name": "X"})
    with pytest.raises(PresetExistsError):
        prov.create_preset({"id": "dup", "name": "Y"})


def test_create_overwrite_replaces(tmp_path) -> None:
    prov = _provider(tmp_path)
    prov.create_preset({"id": "dup", "name": "X"})
    prov.create_preset({"id": "dup", "name": "Y", "base_prompt": "new"}, overwrite=True)
    assert prov.get_preset("dup").name == "Y"
    assert prov.get_preset("dup").base_prompt == "new"


def test_create_bad_id_rejected(tmp_path) -> None:
    prov = _provider(tmp_path)
    with pytest.raises(ValueError):
        prov.create_preset({"id": "bad id/slash", "name": "X"})


def test_create_reports_missing_resource_not_blocking(tmp_path) -> None:
    prov = _provider(tmp_path)
    prov.create_preset({"id": "mx", "name": "X", "checkpoint": "absent.safetensors"})
    v = prov.validate_preset("mx", _inv())
    assert any(m.resource_type == "checkpoint" for m in v.missing)  # 報告
    assert prov.get_preset("mx") is not None  # 但仍建立


# --- API ------------------------------------------------------------------


@pytest.fixture
def client_dir(tmp_path):
    prov = _provider(tmp_path)
    from app.api import style_presets as api
    app.dependency_overrides[api._provider] = lambda: prov
    try:
        yield TestClient(app), tmp_path
    finally:
        app.dependency_overrides.clear()


def test_api_create_then_list(client_dir) -> None:
    client, _ = client_dir
    r = client.post("/api/style-presets/", json={"id": "apix", "name": "API X", "checkpoint": "m.safetensors"})
    assert r.status_code == 201
    assert r.json()["created"] is True
    ids = [it["id"] for it in client.get("/api/style-presets/").json()["items"]]
    assert "apix" in ids


def test_api_create_duplicate_409(client_dir) -> None:
    client, _ = client_dir
    client.post("/api/style-presets/", json={"id": "d", "name": "X"})
    r = client.post("/api/style-presets/", json={"id": "d", "name": "Y"})
    assert r.status_code == 409


def test_api_create_bad_id_422(client_dir) -> None:
    client, _ = client_dir
    r = client.post("/api/style-presets/", json={"id": "bad/slug", "name": "X"})
    assert r.status_code == 422
