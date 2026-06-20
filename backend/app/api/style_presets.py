"""
風格預設目錄 API
列出 / 取得 / 驗證 / 組裝（compose）創作者風格食譜。
compose 產出可直接交給 generate_image / POST /api/generate 的 generation payload。
契約：docs/api-contract.md
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.core.resources import (
    list_checkpoints,
    list_diffusion_models,
    list_loras,
    list_text_encoders,
    list_vaes,
)
from app.core.style_presets import (
    PresetNotFoundError,
    ProfileNotFoundError,
    ResourceInventory,
    StylePresetProvider,
    get_default_provider,
)
from app.schemas.style_presets import (
    ComposeRequest,
    ComposeResponse,
    MissingResourceItem,
    PresetValidationItem,
    StylePresetDetail,
    StylePresetListResponse,
    StylePresetProfileDetail,
    StylePresetSummary,
    StylePresetValidationResponse,
)

router = APIRouter(prefix="/api/style-presets", tags=["風格預設"])


def _provider() -> StylePresetProvider:
    return get_default_provider()


def _current_inventory() -> ResourceInventory:
    """掃描目前已安裝的 ComfyUI 資源與 workflow 模板。"""
    settings = get_settings()
    workflows_dir = Path(__file__).resolve().parent.parent.parent / "workflows"
    workflows = ()
    if workflows_dir.exists():
        workflows = tuple(sorted(p.stem for p in workflows_dir.glob("*.json")))
    return ResourceInventory(
        checkpoints=tuple(list_checkpoints(settings)),
        loras=tuple(list_loras(settings)),
        diffusion_models=tuple(list_diffusion_models(settings)),
        text_encoders=tuple(list_text_encoders(settings)),
        vaes=tuple(list_vaes(settings)),
        workflows=workflows,
    )


@router.get("/", response_model=StylePresetListResponse)
async def list_style_presets(
    provider: StylePresetProvider = Depends(_provider),
):
    """列出所有風格 preset（只讀輕量 index，不載入完整食譜或 Markdown）。"""
    items = [
        StylePresetSummary(
            id=s["id"],
            name=s["name"],
            profiles=s.get("profiles", []),
            note_path=s.get("note_path"),
            template=s.get("template"),
            checkpoint=s.get("checkpoint"),
            lora=s.get("lora"),
            diffusion_model=s.get("diffusion_model"),
        )
        for s in provider.list_summaries()
    ]
    return StylePresetListResponse(items=items)


@router.post("/reindex")
async def reindex_style_presets(
    provider: StylePresetProvider = Depends(_provider),
):
    """重建輕量 index（掃描 presets/*.json）。手動／編輯 preset 後呼叫。"""
    return provider.reindex()


@router.get("/validate", response_model=StylePresetValidationResponse)
async def validate_style_presets(
    provider: StylePresetProvider = Depends(_provider),
):
    """驗證所有 preset 參照的資源是否已安裝；invalid preset 仍會被列出。"""
    inventory = _current_inventory()
    items = [
        PresetValidationItem(
            preset_id=v.preset_id,
            valid=v.valid,
            checked=dict(v.checked),
            missing=[
                MissingResourceItem(resource_type=m.resource_type, name=m.name)
                for m in v.missing
            ],
        )
        for v in provider.validate_presets(inventory)
    ]
    return StylePresetValidationResponse(items=items)


@router.get("/{preset_id}", response_model=StylePresetDetail)
async def get_style_preset(
    preset_id: str,
    provider: StylePresetProvider = Depends(_provider),
):
    """取得單一 preset 的完整食譜。"""
    preset = provider.get_preset(preset_id)
    if preset is None:
        raise HTTPException(404, f"找不到風格 preset: {preset_id}")
    return StylePresetDetail(
        id=preset.id,
        name=preset.name,
        note_path=preset.note_path,
        template=preset.template,
        checkpoint=preset.checkpoint,
        lora=preset.lora,
        lora_strength=preset.lora_strength,
        diffusion_model=preset.diffusion_model,
        text_encoder=preset.text_encoder,
        vae=preset.vae,
        base_prompt=preset.base_prompt,
        negative_prompt=preset.negative_prompt,
        default_params=dict(preset.default_params),
        profiles=[
            StylePresetProfileDetail(
                name=prof.name,
                prompt_prefix=prof.prompt_prefix,
                prompt_suffix=prof.prompt_suffix,
                negative_prompt=prof.negative_prompt,
                params=dict(prof.params),
            )
            for prof in preset.profiles.values()
        ],
    )


@router.post("/{preset_id}/compose", response_model=ComposeResponse)
async def compose_style_preset(
    preset_id: str,
    body: ComposeRequest,
    provider: StylePresetProvider = Depends(_provider),
):
    """將 preset 與使用者 content_prompt 組裝成 generation payload（不送出生圖）。"""
    try:
        result = provider.compose(
            preset_id,
            content_prompt=body.content_prompt,
            profile=body.profile,
            overrides=body.overrides or None,
        )
    except PresetNotFoundError:
        raise HTTPException(404, f"找不到風格 preset: {preset_id}")
    except ProfileNotFoundError as e:
        raise HTTPException(
            422,
            f"preset {preset_id} 無此 profile: {e.profile}；可用 profiles: {e.available}",
        )
    return ComposeResponse(
        preset_id=result.preset_id,
        profile=result.profile,
        generation=result.generation,
    )
