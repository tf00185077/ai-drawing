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
from app.services.watcher import start_watching, stop_watching

logger = logging.getLogger(__name__)


def _on_lora_complete(output_lora_path: str, folder: str) -> None:
    """LoRA 訓練完成後自動產圖：提交至生圖佇列"""
    settings = get_settings()
    try:
        params = {
            "lora": output_lora_path,
            "prompt": settings.lora_auto_prompt,
        }
        if settings.lora_default_checkpoint:
            params["checkpoint"] = settings.lora_default_checkpoint
        queue_submit(params)
        logger.info("LoRA 完成已提交產圖: folder=%s, lora=%s", folder, output_lora_path)
    except QueueFullError as e:
        logger.warning("生圖佇列已滿，略過 LoRA 產圖: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期：啟動時開始監聽與佇列 worker，關閉時停止"""
    lora_trainer.register_on_complete(_on_lora_complete)
    start_watching()
    start_queue_worker()
    yield
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
from app.api import analytics, generate, gallery, lora_docs, lora_train, prompt_templates

app.include_router(generate.router)
app.include_router(gallery.router)
app.include_router(lora_docs.router)
app.include_router(lora_train.router)
app.include_router(prompt_templates.router)
app.include_router(analytics.router)

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
