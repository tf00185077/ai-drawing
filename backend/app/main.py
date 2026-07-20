"""
AI 自動化出圖系統 - FastAPI 入口
"""
import logging
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.core.queue import (
    QueueFullError,
    start_worker as start_queue_worker,
    stop_worker as stop_queue_worker,
    submit as queue_submit,
)
from app.services import lora_trainer
from app.services.comfyui_history_watcher import start_watcher as start_comfyui_watcher
from app.services.comfyui_history_watcher import stop_watcher as stop_comfyui_watcher
from app.services.watcher import start_watching, stop_watching

logger = logging.getLogger(__name__)


def _on_lora_complete(output_lora_path: str, folder: str) -> None:
    """LoRA 訓練完成回呼。訓練與生圖已解耦，此處不再自動生圖。"""
    logger.info("LoRA 訓練完成：folder=%s, path=%s", folder, output_lora_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期：啟動時建表/補欄、開始監聽與佇列 worker，關閉時停止"""
    from app.db.database import init_db
    init_db()
    lora_trainer.register_on_complete(_on_lora_complete)
    lora_trainer.ensure_worker()
    start_watching()
    start_queue_worker()
    start_comfyui_watcher()

    yield

    stop_comfyui_watcher()
    stop_queue_worker()
    stop_watching()


app = FastAPI(
    lifespan=lifespan,
    title="AI 自動化出圖系統",
    description="ComfyUI 產圖 · LoRA 訓練 · 參數記錄",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 四大模組 API
from app.api import (
    analytics,
    civitai_easy,
    civitai_recipes,
    comfyui,
    generate,
    gallery,
    lora_docs,
    lora_train,
    prompt_library,
    prompt_templates,
    style_presets,
    system,
    workflow_catalog,
)

app.include_router(generate.router)
app.include_router(civitai_easy.router)
app.include_router(civitai_recipes.router)
app.include_router(gallery.router)
app.include_router(lora_docs.router)
app.include_router(lora_train.router)
app.include_router(prompt_library.router)
app.include_router(prompt_templates.router)
app.include_router(analytics.router)
app.include_router(style_presets.router)
app.include_router(comfyui.router)
app.include_router(workflow_catalog.router)
app.include_router(system.router)

# 圖庫靜態檔案
_gallery_path = Path(get_settings().gallery_dir)
_gallery_path.mkdir(parents=True, exist_ok=True)
app.mount("/gallery", StaticFiles(directory=str(_gallery_path)), name="gallery")


@app.get("/")
async def root():
    return {"status": "ok", "app": "AI 自動化出圖系統"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
