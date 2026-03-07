"""
Prompt 模板 API 的 Request/Response 結構
對應 docs/api-contract.md 模組 5
"""
from pydantic import BaseModel


class PromptTemplateItem(BaseModel):
    """單一模板項目"""

    id: str
    name: str
    template: str
    variables: list[str]


class PromptTemplateListResponse(BaseModel):
    """GET /api/prompt-templates 的 Response"""

    items: list[PromptTemplateItem]


class PromptTemplateApplyRequest(BaseModel):
    """POST /api/prompt-templates/apply 的 Request"""

    template_id: str
    variables: dict[str, str] = {}


class PromptTemplateApplyResponse(BaseModel):
    """POST /api/prompt-templates/apply 的 Response"""

    prompt: str
