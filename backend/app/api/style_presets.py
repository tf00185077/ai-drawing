"""
風格預設目錄 API
列出 / 取得 / 驗證 / 組裝（compose）創作者風格食譜。
compose 產出可直接交給 generate_image / POST /api/generate 的 generation payload。
契約：docs/api-contract.md
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.resources import (
    list_checkpoints,
    list_diffusion_models,
    list_loras,
    list_text_encoders,
    list_vaes,
)
from app.core.style_presets import (
    DirStylePresetProvider,
    PresetExistsError,
    PresetNotFoundError,
    ProfileNotFoundError,
    ResourceInventory,
    StylePresetProvider,
    get_default_provider,
)
from app.core.queue import QueueFullError, submit_saved_workflow
from app.db.database import get_db
from app.services.style_preset_workflows import (
    StylePresetWorkflowError,
    load_saved_workflow,
    save_successful_workflow,
)
from app.schemas.style_preset_workflows import (
    SaveStylePresetWorkflowRequest,
    SaveStylePresetWorkflowResponse,
    TestStylePresetWorkflowRequest,
    TestStylePresetWorkflowResponse,
)
from app.schemas.style_presets import (
    ComposeRequest,
    ComposeResponse,
    CreatePresetRequest,
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


def _workflow_provider(
    provider: StylePresetProvider,
) -> DirStylePresetProvider:
    if isinstance(provider, DirStylePresetProvider):
        return provider
    raise StylePresetWorkflowError(
        "invalid_workflow_graph",
        "The configured style preset provider cannot persist workflow files.",
        "Use the directory-backed style preset provider.",
        status_code=500,
    )


def _workflow_http_error(exc: StylePresetWorkflowError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail())


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
            chinese_name=s.get("chinese_name"),
            profiles=s.get("profiles", []),
            note_path=s.get("note_path"),
            template=s.get("template"),
            checkpoint=s.get("checkpoint"),
            lora=s.get("lora"),
            loras=s.get("loras", []),
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


@router.post("/", status_code=201)
async def create_style_preset(
    body: CreatePresetRequest,
    provider: StylePresetProvider = Depends(_provider),
):
    """依欄位建立 preset：寫機器食譜 + 人類 note + reindex。id 重複回 409、id/name 不合法回 422。"""
    fields = body.model_dump(exclude={"create_note", "overwrite"})
    try:
        result = provider.create_preset(
            fields, create_note=body.create_note, overwrite=body.overwrite
        )
    except PresetExistsError:
        raise HTTPException(409, f"preset 已存在：{body.id}（如要取代請設 overwrite=true）")
    except ValueError as e:
        raise HTTPException(422, str(e))
    # 非阻斷式驗證：回報缺少的資源讓呼叫端後續修正
    v = provider.validate_preset(result["id"], _current_inventory())
    result["validation"] = {
        "valid": v.valid,
        "missing": [{"resource_type": m.resource_type, "name": m.name} for m in v.missing],
    }
    return result


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
        chinese_name=preset.chinese_name,
        note_path=preset.note_path,
        template=preset.template,
        checkpoint=preset.checkpoint,
        lora=preset.lora,
        lora_strength=preset.lora_strength,
        loras=[dict(x) for x in preset.loras],
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


@router.post(
    "/{preset_id}/workflow/save",
    response_model=SaveStylePresetWorkflowResponse,
    status_code=201,
)
async def save_style_preset_workflow(
    preset_id: str,
    body: SaveStylePresetWorkflowRequest,
    provider: StylePresetProvider = Depends(_provider),
    db: Session = Depends(get_db),
):
    """Explicitly promote one already-successful recorded graph."""
    try:
        result = save_successful_workflow(
            db,
            _workflow_provider(provider),
            preset_id=preset_id,
            profile=body.profile,
            source=body.source,
            prompt_keywords=body.prompt_keywords,
            negative_prompt_keywords=body.negative_prompt_keywords,
        )
    except StylePresetWorkflowError as exc:
        raise _workflow_http_error(exc) from exc
    return SaveStylePresetWorkflowResponse(
        preset_id=result.preset_id,
        profile=result.profile,
        source={"type": result.source_type, "id": result.source_id},
        workflow_path=result.workflow_path,
        prompt_keywords=result.prompt_keywords,
        negative_prompt_keywords=result.negative_prompt_keywords,
        retest_required=result.retest_required,
    )


@router.get("/{preset_id}/workflow")
async def get_saved_style_preset_workflow(
    preset_id: str,
    profile: str | None = Query(default=None),
    provider: StylePresetProvider = Depends(_provider),
):
    """Return only the raw saved ComfyUI API graph."""
    try:
        return load_saved_workflow(
            _workflow_provider(provider), preset_id, profile
        )
    except StylePresetWorkflowError as exc:
        raise _workflow_http_error(exc) from exc


@router.post(
    "/{preset_id}/workflow/test",
    response_model=TestStylePresetWorkflowResponse,
    status_code=202,
)
async def test_saved_style_preset_workflow(
    preset_id: str,
    body: TestStylePresetWorkflowRequest,
    provider: StylePresetProvider = Depends(_provider),
):
    """Queue the server-owned saved graph without runtime overrides."""
    try:
        graph = load_saved_workflow(
            _workflow_provider(provider), preset_id, body.profile
        )
        job_id = submit_saved_workflow(graph)
    except StylePresetWorkflowError as exc:
        raise _workflow_http_error(exc) from exc
    except QueueFullError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "queue_full",
                "message": str(exc),
                "hint": "Wait for a queued generation to finish, then retry.",
            },
        ) from exc
    return TestStylePresetWorkflowResponse(
        preset_id=preset_id,
        profile=body.profile,
        job_id=job_id,
    )
