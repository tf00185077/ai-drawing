"""Agent-friendly best-effort Civitai endpoints.

These wrap the strict recipe machinery with forgiving inputs, tiered
substitution, and actionable errors. The audited strict pipeline stays at
``/api/civitai-recipes/*`` for exact-reproduction use.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.queue import QueueFullError
from app.db.database import get_db
from app.services.civitai_easy import EasyGenerateError, generate_like, source_info
from app.services.civitai_resource_acquire import AcquireError, acquisition_status, start_acquisition

router = APIRouter(prefix="/api/civitai", tags=["civitai-easy"])


class GenerateLikeRequest(BaseModel):
    """Everything except the source locator is optional; omitted fields follow the source image."""

    locator: int | str = Field(description="Civitai 圖片連結或圖片 ID")
    prompt: str | None = Field(default=None, description="取代原圖 prompt；省略時沿用原 prompt")
    negative_prompt: str | None = None
    batch_size: int | None = Field(default=None, ge=1, le=8)
    seed: int | None = Field(default=None, ge=0)
    steps: int | None = Field(default=None, ge=1, le=150)
    cfg: float | None = Field(default=None, ge=1.0, le=30.0)
    width: int | None = Field(default=None, ge=256, le=2048)
    height: int | None = Field(default=None, ge=256, le=2048)
    checkpoint: str | None = Field(default=None, description="強制使用指定本地 checkpoint 檔名")
    download_missing: bool = Field(default=True, description="缺模型時先自動下載（false 則以最接近的本地模型代替）")


class AcquireRequest(BaseModel):
    locator: int | str = Field(description="Civitai 模型頁連結、模型 ID 或 model-version ID")


def _easy_error(exc: EasyGenerateError) -> HTTPException:
    return HTTPException(status_code=422, detail=exc.to_dict())


def _acquire_error(exc: AcquireError) -> HTTPException:
    status = 404 if exc.code == "not_found" else 422
    return HTTPException(status_code=status, detail=exc.to_dict())


@router.get("/source-info")
def get_source_info(locator: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """預覽一張 Civitai 圖片的生成參數與本地資源可用性（唯讀）。"""
    try:
        return source_info(locator, db=db)
    except EasyGenerateError as exc:
        raise _easy_error(exc) from exc
    except AcquireError as exc:
        raise _acquire_error(exc) from exc


@router.post("/generate-like", status_code=202)
def post_generate_like(request: GenerateLikeRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """參考 Civitai 圖片的參數生圖：換 prompt、保留採樣設定、自動補資源。"""
    try:
        return generate_like(
            request.locator,
            db=db,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            batch_size=request.batch_size,
            seed=request.seed,
            steps=request.steps,
            cfg=request.cfg,
            width=request.width,
            height=request.height,
            checkpoint=request.checkpoint,
            download_missing=request.download_missing,
        )
    except EasyGenerateError as exc:
        raise _easy_error(exc) from exc
    except AcquireError as exc:
        raise _acquire_error(exc) from exc
    except QueueFullError as exc:
        raise HTTPException(status_code=503, detail={"code": "queue_full", "message": str(exc)}) from exc


@router.post("/resources/acquire", status_code=202)
def post_acquire_resource(request: AcquireRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """下載一個 Civitai 模型到外接硬碟並登記到本地帳本（背景執行）。"""
    try:
        return start_acquisition(request.locator, db=db)
    except AcquireError as exc:
        raise _acquire_error(exc) from exc


@router.get("/resources/status")
def get_resource_status(
    acquisition_id: int | None = None,
    limit: int = 10,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """查下載進度；不帶 acquisition_id 時列出最近的資源。"""
    try:
        return acquisition_status(db, acquisition_id=acquisition_id, limit=limit)
    except AcquireError as exc:
        raise _acquire_error(exc) from exc
