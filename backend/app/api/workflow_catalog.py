"""
Workflow 模板能力目錄 API

暴露模板能力 manifest 的輕量索引，讓 agent 不必展開整份 workflow JSON 即可判斷
模板是否適用（見 #3 二元 reuse 匹配）：
- GET /api/workflow-catalog/          能力索引（id + 標籤 + description，不含 workflow JSON）
- GET /api/workflow-catalog/validate  逐模板詞彙/檔案驗證（invalid 以資料回報）

契約：openspec/specs/workflow-template-catalog/spec.md
"""
from fastapi import APIRouter

from app.core.workflow_manifest import load_manifests

router = APIRouter(prefix="/api/workflow-catalog", tags=["Workflow 模板目錄"])


@router.get("/")
async def list_template_capabilities():
    """列出每個模板的能力標籤與 description（輕量，不含完整 workflow JSON）。"""
    items = [
        {
            "id": lm.manifest.id,
            **lm.manifest.tags(),
            "description": lm.manifest.description,
            "valid": lm.valid,
        }
        for lm in load_manifests()
    ]
    return {"items": items, "total": len(items)}


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
