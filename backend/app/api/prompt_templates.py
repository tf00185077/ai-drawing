"""
模組 5：Prompt 模板庫 API
儲存常用 prompt 組合、變數替換
契約：docs/api-contract.md 模組 5
"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.prompt_templates import (
    PromptTemplateProvider,
    apply_variables,
    get_default_provider,
)
from app.schemas.prompt_templates import (
    PromptTemplateApplyRequest,
    PromptTemplateApplyResponse,
    PromptTemplateItem,
    PromptTemplateListResponse,
)

router = APIRouter(prefix="/api/prompt-templates", tags=["Prompt 模板"])


def _provider() -> PromptTemplateProvider:
    return get_default_provider()


@router.get("/", response_model=PromptTemplateListResponse)
async def list_templates(
    provider: PromptTemplateProvider = Depends(_provider),
):
    """取得所有 prompt 模板"""
    templates = provider.list_all()
    items = [
        PromptTemplateItem(
            id=t.id,
            name=t.name,
            template=t.template,
            variables=list(t.variables),
        )
        for t in templates
    ]
    return PromptTemplateListResponse(items=items)


@router.post("/apply", response_model=PromptTemplateApplyResponse)
async def apply_template(
    body: PromptTemplateApplyRequest,
    provider: PromptTemplateProvider = Depends(_provider),
):
    """依 template_id 與 variables 產出最終 prompt"""
    template = provider.get(body.template_id)
    if template is None:
        raise HTTPException(404, f"找不到模板: {body.template_id}")
    prompt = apply_variables(template.template, body.variables or {})
    return PromptTemplateApplyResponse(prompt=prompt)
