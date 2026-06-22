"""Workflow 模板能力 manifest：解析、詞彙驗證、載入與目錄 API 測試"""
import json

from app.core.workflow_manifest import (
    load_manifests,
    parse_manifest,
    validate_manifest,
)
from app.main import app
from fastapi.testclient import TestClient


# --- 純函式：解析 + 詞彙驗證 ----------------------------------------------


def test_valid_manifest_passes_validation() -> None:
    m = parse_manifest(
        "x",
        {
            "modality": "inpaint",
            "model_family": "sdxl",
            "io": ["text", "mask"],
            "conditioning": ["controlnet_pose"],
        },
    )
    assert validate_manifest(m, expected_id="x") == []


def test_missing_model_family_is_rejected() -> None:
    m = parse_manifest("x", {"modality": "txt2img"})
    assert any("missing required field: model_family" in p for p in validate_manifest(m))


def test_out_of_vocabulary_tag_is_rejected() -> None:
    m = parse_manifest("x", {"modality": "txt2img", "conditioning": ["pose_control"]})
    problems = validate_manifest(m)
    assert any("conditioning not in vocabulary" in p for p in problems)


def test_unknown_modality_is_rejected() -> None:
    m = parse_manifest("x", {"modality": "txt2audio"})
    assert any("modality not in vocabulary" in p for p in validate_manifest(m))


def test_video_modalities_and_io_tags_are_valid() -> None:
    txt2video = parse_manifest(
        "video_txt",
        {
            "modality": "txt2video",
            "model_family": "wan",
            "io": ["text", "video_ref", "audio_ref"],
        },
    )
    img2video = parse_manifest(
        "video_img",
        {
            "modality": "img2video",
            "model_family": "wan",
            "io": ["text", "first_frame", "last_frame"],
        },
    )

    assert validate_manifest(txt2video, expected_id="video_txt") == []
    assert validate_manifest(img2video, expected_id="video_img") == []


def test_missing_modality_is_rejected() -> None:
    m = parse_manifest("x", {"io": ["text"]})
    assert any("missing required field: modality" in p for p in validate_manifest(m))


def test_id_mismatch_is_reported() -> None:
    m = parse_manifest("x", {"id": "y", "modality": "txt2img"})
    assert any("id mismatch" in p for p in validate_manifest(m, expected_id="x"))


# --- 載入真實 sidecar ------------------------------------------------------


def test_load_real_manifests_all_valid() -> None:
    loaded = load_manifests()
    ids = {lm.manifest.id for lm in loaded}
    assert {"default", "default_lora", "anima", "inpaint"} <= ids
    assert all(lm.valid for lm in loaded), [
        (lm.manifest.id, lm.problems) for lm in loaded if not lm.valid
    ]
    # 索引只讀 meta，inpaint 的 io 應含 mask
    inpaint = next(lm for lm in loaded if lm.manifest.id == "inpaint")
    assert "mask" in inpaint.manifest.io


# --- API 端點 -------------------------------------------------------------


def test_catalog_index_lists_tags_without_workflow_json() -> None:
    c = TestClient(app)
    r = c.get("/api/workflow-catalog/")
    assert r.status_code == 200
    body = r.json()
    ids = {it["id"] for it in body["items"]}
    assert "anima" in ids
    anima = next(it for it in body["items"] if it["id"] == "anima")
    assert anima["model_family"] == "anima"
    assert anima["modality"] == "txt2img"
    # 不得夾帶完整 workflow JSON
    assert "nodes" not in anima and "workflow" not in anima


def test_catalog_validate_reports_all_valid() -> None:
    c = TestClient(app)
    r = c.get("/api/workflow-catalog/validate")
    assert r.status_code == 200
    assert r.json()["invalid"] == []
