"""二元 reuse 匹配（superset 測試）：純函式與 /match 端點"""
from app.core.workflow_manifest import (
    CapabilityRequest,
    LoadedManifest,
    WorkflowManifest,
    find_matching_templates,
    manifest_covers,
)
from app.main import app
from fastapi.testclient import TestClient


def _m(**kw) -> WorkflowManifest:
    return WorkflowManifest(
        id=kw.get("id", "t"),
        modality=kw["modality"],
        model_family=kw.get("model_family", "sdxl"),
        conditioning=tuple(kw.get("conditioning", ())),
        io=tuple(kw.get("io", ())),
    )


# --- 純函式 superset ------------------------------------------------------


def test_template_covering_request_matches() -> None:
    tmpl = _m(modality="img2img", conditioning=("controlnet_pose",), io=("text", "image_ref"))
    req = CapabilityRequest(modality="img2img", io=("image_ref",))
    assert manifest_covers(tmpl, req) is True


def test_missing_required_conditioning_is_miss() -> None:
    tmpl = _m(modality="img2img", io=("text", "image_ref"))  # 無 controlnet_pose
    req = CapabilityRequest(modality="img2img", conditioning=("controlnet_pose",))
    assert manifest_covers(tmpl, req) is False


def test_differing_modality_is_miss_despite_overlap() -> None:
    # conditioning 完全相同，但 modality 不同 → 嚴格 miss
    tmpl = _m(modality="txt2img", conditioning=("controlnet_pose",), io=("text", "image_ref"))
    req = CapabilityRequest(modality="img2img", conditioning=("controlnet_pose",))
    assert manifest_covers(tmpl, req) is False


def test_model_family_constrains_only_when_given() -> None:
    tmpl = _m(modality="txt2img", model_family="anima", io=("text",))
    assert manifest_covers(tmpl, CapabilityRequest(modality="txt2img")) is True  # 不指定家族
    assert manifest_covers(tmpl, CapabilityRequest(modality="txt2img", model_family="sdxl")) is False
    assert manifest_covers(tmpl, CapabilityRequest(modality="txt2img", model_family="anima")) is True


def test_invalid_manifest_is_not_matchable() -> None:
    good = LoadedManifest(manifest=_m(id="good", modality="txt2img", io=("text",)))
    bad = LoadedManifest(
        manifest=_m(id="bad", modality="txt2img", io=("text",)), problems=["bad tag"]
    )
    req = CapabilityRequest(modality="txt2img")
    assert find_matching_templates([good, bad], req) == ["good"]


# --- /match 端點（用真實 sidecar）----------------------------------------


def test_match_endpoint_pose_img2img_hits_expected() -> None:
    c = TestClient(app)
    r = c.get(
        "/api/workflow-catalog/match",
        params={"modality": "img2img", "conditioning": "controlnet_pose", "io": "image_ref"},
    )
    assert r.status_code == 200
    matched = r.json()["matched"]
    assert "img2img_lora_pose" in matched
    assert "controlnet_pose" in matched
    assert "txt2img_lora_pose" not in matched  # modality 不符


def test_match_endpoint_requires_modality() -> None:
    c = TestClient(app)
    r = c.get("/api/workflow-catalog/match", params={"conditioning": "controlnet_pose"})
    assert r.status_code == 400


def test_match_endpoint_unsatisfiable_is_empty() -> None:
    c = TestClient(app)
    # 沒有任何 sd15 模板 → strict miss
    r = c.get("/api/workflow-catalog/match", params={"modality": "txt2img", "model_family": "sd15"})
    assert r.status_code == 200
    assert r.json()["matched"] == []
