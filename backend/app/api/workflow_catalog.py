"""
Workflow 模板能力目錄 API

暴露模板能力 manifest 的輕量索引，讓 agent 不必展開整份 workflow JSON 即可判斷
模板是否適用（見 #3 二元 reuse 匹配）：
- GET  /api/workflow-catalog/          能力索引（id + 標籤 + description，不含 workflow JSON）
- GET  /api/workflow-catalog/match     二元 reuse 匹配
- GET  /api/workflow-catalog/validate  逐模板詞彙/檔案驗證（invalid 以資料回報）
- POST /api/workflow-catalog/backfill  把已成功 job 的 workflow 晉升為模板（DB 成功閘門）

契約：openspec/specs/workflow-template-catalog/spec.md
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.workflow_manifest import (
    CapabilityRequest,
    backfill_template,
    consolidate_templates,
    find_matching_templates,
    load_manifests,
)
from app.db.database import get_db
from app.db.models import GeneratedArtifact, GeneratedImage
from app.core.workflow_form import GenerationFormsResponse, build_generation_forms
from app.core.resources import list_checkpoints, list_diffusion_models, list_loras, list_text_encoders, list_vaes
from app.config import get_settings
from app.core.comfyui import ComfyUIClient

router = APIRouter(prefix="/api/workflow-catalog", tags=["Workflow 模板目錄"])


@router.get("/generation-forms", response_model=GenerationFormsResponse)
async def generation_forms():
    settings = get_settings()
    resources = {"checkpoints": list_checkpoints(settings), "loras": list_loras(settings), "diffusion_models": list_diffusion_models(settings), "text_encoders": list_text_encoders(settings), "vaes": list_vaes(settings)}
    try:
        object_info = ComfyUIClient().get_object_info()
    except Exception:
        object_info = {}
    return build_generation_forms(Path(__file__).resolve().parent.parent.parent / "workflows", resources=resources, object_info=object_info)


class BackfillRequest(BaseModel):
    job_id: str
    modality: str
    model_family: str
    conditioning: list[str] = []
    io: list[str] = []
    description: str = ""


def _csv(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


@router.get("/")
async def list_template_capabilities():
    """列出每個模板的能力標籤與 description（輕量，不含完整 workflow JSON）。"""
    items = [
        {
            "id": lm.manifest.id,
            **lm.manifest.tags(),
            "description": lm.manifest.description,
            "valid": lm.valid,
            "deprecated": lm.manifest.deprecated,
        }
        for lm in load_manifests()
    ]
    return {"items": items, "total": len(items)}


@router.get("/match")
async def match_templates(
    modality: str = "",
    model_family: str = "",
    conditioning: str = "",
    io: str = "",
):
    """二元 reuse 匹配：回傳能力涵蓋需求（template ⊇ request）的模板 id。modality 必填（皆空回 400）；conditioning/io 以逗號分隔。命中→可用其 id 走 generate_image；無命中→需自組。"""
    if not modality.strip():
        raise HTTPException(400, "match 需要 modality（必填）；conditioning/io 為選用集合")
    request = CapabilityRequest(
        modality=modality.strip(),
        model_family=model_family.strip() or None,
        conditioning=_csv(conditioning),
        io=_csv(io),
    )
    matched = find_matching_templates(load_manifests(), request)
    return {
        "request": {
            "modality": request.modality,
            "model_family": request.model_family,
            "conditioning": list(request.conditioning),
            "io": list(request.io),
        },
        "matched": matched,
        "total": len(matched),
    }


@router.get("/validate")
async def validate_template_capabilities():
    """逐模板驗證能力 manifest：詞彙是否合法、id 是否與檔名一致、對應 workflow 是否存在。"""
    items = [
        {
            "id": lm.manifest.id,
            "valid": lm.valid,
            "problems": lm.problems,
        }
        for lm in load_manifests()
    ]
    invalid = [it["id"] for it in items if not it["valid"]]
    return {"items": items, "invalid": invalid, "total": len(items)}


@router.post("/backfill")
async def backfill(body: BackfillRequest, db: Session = Depends(get_db)):
    """把一份「已成功產圖」的 job 的 workflow 晉升為可重用模板。

    閘門：以 job_id 查 DB 成功記錄（GeneratedImage）且需有 workflow_json——只有真正成功
    且 recording 過的 job 能晉升（不信片面之詞，跨進程/重啟皆成立）。形狀讀自 DB 的
    workflow_json（剝去 prompt/seed），標籤經受控詞彙驗證，能力 key 去重、依家族歸檔、版本化。
    """
    row = (
        db.query(GeneratedImage)
        .filter(GeneratedImage.job_id == body.job_id)
        .order_by(GeneratedImage.id.desc())
        .first()
    )
    if row is None:
        row = (
            db.query(GeneratedArtifact)
            .filter(GeneratedArtifact.job_id == body.job_id)
            .order_by(GeneratedArtifact.id.desc())
            .first()
        )
    if row is None:
        raise HTTPException(404, f"找不到成功記錄：job_id={body.job_id}（未完成或未 recording，不可晉升）")
    if not row.workflow_json:
        raise HTTPException(409, "該記錄無 workflow_json（legacy 或 template 路徑），無法取得可回填的形狀")
    try:
        wf = json.loads(row.workflow_json)
    except (TypeError, ValueError):
        raise HTTPException(409, "該記錄的 workflow_json 非合法 JSON")

    result = backfill_template(
        wf,
        modality=body.modality,
        model_family=body.model_family,
        conditioning=body.conditioning,
        io=body.io,
        description=body.description,
    )
    if not result.get("ok"):
        raise HTTPException(422, {"error": result.get("error"), "problems": result.get("problems")})
    return result


@router.post("/consolidate")
async def consolidate():
    """清理已 deprecated 的模板（刪除其 sidecar）。手動／週期性家務整理，回傳被移除的 id。"""
    return consolidate_templates()
