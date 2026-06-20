"""
風格預設目錄 API 的 Request/Response 結構
對應 docs/api-contract.md 模組「Style Preset Catalog」
"""
from typing import Any

from pydantic import BaseModel, Field


class StylePresetSummary(BaseModel):
    """list 端點的輕量 preset 條目（不含完整 prompt / 參數）。"""

    id: str
    name: str
    chinese_name: str | None = None
    profiles: list[str] = Field(default_factory=list)
    note_path: str | None = None
    template: str | None = None
    checkpoint: str | None = None
    lora: str | None = None
    loras: list[dict[str, Any]] = Field(default_factory=list)
    diffusion_model: str | None = None


class StylePresetListResponse(BaseModel):
    """GET /api/style-presets/ 的 Response"""

    items: list[StylePresetSummary]


class CreatePresetRequest(BaseModel):
    """POST /api/style-presets/ 的 Request：依欄位建立 preset（機器食譜 + 人類 note）。"""

    id: str
    name: str
    chinese_name: str | None = None
    base_prompt: str = ""
    negative_prompt: str = ""
    template: str | None = None
    checkpoint: str | None = None
    lora: str | None = None
    lora_strength: float | None = None
    loras: list[dict[str, Any]] = Field(
        default_factory=list,
        description="多 lora：[{name, strength_model, strength_clip?}]，依模板 LoraLoader 順序對應；優先於單一 lora",
    )
    diffusion_model: str | None = None
    text_encoder: str | None = None
    vae: str | None = None
    default_params: dict[str, Any] = Field(default_factory=dict)
    profiles: dict[str, Any] = Field(default_factory=dict)
    create_note: bool = True
    overwrite: bool = False


class StylePresetProfileDetail(BaseModel):
    """preset detail 中的 profile 內容。"""

    name: str
    prompt_prefix: str = ""
    prompt_suffix: str = ""
    negative_prompt: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class StylePresetDetail(BaseModel):
    """GET /api/style-presets/{preset_id} 的 Response：完整食譜。"""

    id: str
    name: str
    chinese_name: str | None = None
    note_path: str | None = None
    template: str | None = None
    checkpoint: str | None = None
    lora: str | None = None
    lora_strength: float | None = None
    loras: list[dict[str, Any]] = Field(default_factory=list)
    diffusion_model: str | None = None
    text_encoder: str | None = None
    vae: str | None = None
    base_prompt: str = ""
    negative_prompt: str = ""
    default_params: dict[str, Any] = Field(default_factory=dict)
    profiles: list[StylePresetProfileDetail] = Field(default_factory=list)


class MissingResourceItem(BaseModel):
    """驗證時找不到的單一資源。"""

    resource_type: str
    name: str


class PresetValidationItem(BaseModel):
    """單一 preset 的驗證結果。"""

    preset_id: str
    valid: bool
    checked: dict[str, str] = Field(default_factory=dict)
    missing: list[MissingResourceItem] = Field(default_factory=list)


class StylePresetValidationResponse(BaseModel):
    """GET /api/style-presets/validate 的 Response"""

    items: list[PresetValidationItem]


class ComposeRequest(BaseModel):
    """POST /api/style-presets/{preset_id}/compose 的 Request"""

    content_prompt: str = Field(..., min_length=1, description="使用者想在這張圖中呈現的內容")
    profile: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class ComposeResponse(BaseModel):
    """compose 的 Response：可直接交給 generate_image 的 generation payload。"""

    preset_id: str
    profile: str | None = None
    generation: dict[str, Any]
