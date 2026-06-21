"""layer-style-preset-catalog：index/detail 分層、reindex、self-heal、drift"""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core import style_presets as sp
from app.core.style_presets import (
    DirStylePresetProvider,
    ResourceInventory,
    reindex,
)
from app.main import app


def _preset(pid="creator-a", **over):
    d = {
        "id": pid,
        "name": f"Name {pid}",
        "template": "default_lora",
        "checkpoint": "m.safetensors",
        "base_prompt": "masterpiece",
        "profiles": {"portrait": {"prompt_prefix": "close-up"}},
    }
    d.update(over)
    return d


def _agent(tmp_path, *presets, write_index=True):
    pdir = tmp_path / "presets"
    pdir.mkdir(parents=True, exist_ok=True)
    for p in presets:
        (pdir / f"{p['id']}.json").write_text(json.dumps(p), encoding="utf-8")
    if write_index:
        reindex(tmp_path)
    return DirStylePresetProvider(tmp_path, project_root=tmp_path)


# --- 分層 / detail 載入 ---------------------------------------------------


def test_list_summaries_reads_index_without_loading_bodies(tmp_path) -> None:
    prov = _agent(tmp_path, _preset())
    # 用 patch 確保 list 不會去 parse 單檔 detail（只讀 index）
    with patch.object(sp, "_parse_preset", side_effect=AssertionError("should not parse detail")):
        summaries = prov.list_summaries()
    assert [s["id"] for s in summaries] == ["creator-a"]
    assert summaries[0]["profiles"] == ["portrait"]


def test_get_and_compose_load_single_preset(tmp_path) -> None:
    prov = _agent(tmp_path, _preset())
    pr = prov.get_preset("creator-a")
    assert pr.base_prompt == "masterpiece"
    assert "close-up" in prov.compose("creator-a", "a girl", profile="portrait").generation["prompt"]


# --- reindex / self-heal --------------------------------------------------


def test_reindex_reflects_added_preset(tmp_path) -> None:
    prov = _agent(tmp_path, _preset("a"))
    # 直接丟入新 detail 檔（未更新 index）
    (tmp_path / "presets" / "b.json").write_text(json.dumps(_preset("b")), encoding="utf-8")
    assert {s["id"] for s in prov.list_summaries()} == {"a"}  # 尚未 reindex
    prov.reindex()
    assert {s["id"] for s in prov.list_summaries()} == {"a", "b"}


def test_missing_index_self_heals(tmp_path) -> None:
    prov = _agent(tmp_path, _preset(), write_index=False)
    assert not (tmp_path / "index.json").exists()
    summaries = prov.list_summaries()  # 應自我修復重建
    assert [s["id"] for s in summaries] == ["creator-a"]
    assert (tmp_path / "index.json").exists()


# --- drift 驗證 -----------------------------------------------------------


def test_validate_reports_detail_without_index_entry(tmp_path) -> None:
    prov = _agent(tmp_path, _preset("a"))
    # 加一個 detail 檔但不 reindex → index 漏列
    (tmp_path / "presets" / "ghost.json").write_text(json.dumps(_preset("ghost")), encoding="utf-8")
    inv = ResourceInventory(checkpoints=("m.safetensors",), workflows=("default_lora",))
    results = {r.preset_id: r for r in prov.validate_presets(inv)}
    assert any(m.resource_type == "index_entry" for m in results["ghost"].missing)


def test_validate_reports_index_entry_without_detail(tmp_path) -> None:
    prov = _agent(tmp_path, _preset("a"))
    # index 列了 phantom，但無對應 detail 檔
    idx = json.loads((tmp_path / "index.json").read_text())
    idx["presets"].append({"id": "phantom", "name": "x", "profiles": []})
    (tmp_path / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    inv = ResourceInventory(checkpoints=("m.safetensors",), workflows=("default_lora",))
    results = {r.preset_id: r for r in prov.validate_presets(inv)}
    assert "phantom" in results
    assert any(m.resource_type == "detail_file" for m in results["phantom"].missing)


# --- API ------------------------------------------------------------------


@pytest.fixture
def client_dir(tmp_path):
    prov = _agent(tmp_path, _preset())
    app.dependency_overrides[sp.get_default_provider] = lambda: prov
    # _provider 用的是 get_default_provider；但 API 以 Depends(_provider)
    from app.api import style_presets as api
    app.dependency_overrides[api._provider] = lambda: prov
    try:
        yield TestClient(app), tmp_path, prov
    finally:
        app.dependency_overrides.clear()


def test_api_list_from_index(client_dir) -> None:
    client, _, _ = client_dir
    r = client.get("/api/style-presets/")
    assert r.status_code == 200
    ids = [it["id"] for it in r.json()["items"]]
    assert ids == ["creator-a"]


def test_api_reindex_endpoint(client_dir) -> None:
    client, tmp_path, _ = client_dir
    (tmp_path / "presets" / "b.json").write_text(json.dumps(_preset("b")), encoding="utf-8")
    r = client.post("/api/style-presets/reindex")
    assert r.status_code == 200
    assert {e["id"] for e in r.json()["presets"]} == {"creator-a", "b"}
