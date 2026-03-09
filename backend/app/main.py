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

_slack_handler = None


def _on_lora_complete(output_lora_path: str, folder: str) -> None:
    """LoRA 訓練完成後自動產圖：若有 generate_after 則依其參數，否則用預設 prompt"""
    settings = get_settings()
    lora_name = Path(output_lora_path).name

    pending = lora_trainer.get_and_clear_pending_generate(folder)
    if pending:
        # 使用訓練時指定的 generate_after 參數
        prompt = pending.get("prompt", settings.lora_auto_prompt)
        count = max(1, min(int(pending.get("count", 1)), 64))
        batch_size = max(1, min(int(pending.get("batch_size", 1)), 8))
        base_params = {
            "lora": lora_name,
            "prompt": prompt,
            "negative_prompt": pending.get("negative_prompt"),
            "checkpoint": pending.get("checkpoint") or settings.lora_default_checkpoint,
        }
        base_params = {k: v for k, v in base_params.items() if v is not None}
        remaining = count
        submitted = 0
        try:
            while remaining > 0:
                bs = min(batch_size, remaining)
                params = {**base_params, "batch_size": bs}
                queue_submit(params)
                submitted += bs
                remaining -= bs
            logger.info("LoRA 完成已提交產圖: folder=%s, lora=%s, count=%d", folder, output_lora_path, submitted)
        except QueueFullError as e:
            logger.warning("生圖佇列已滿，已提交 %d 張後略過: %s", submitted, e)
        return

    try:
        params = {
            "lora": lora_name,
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
    global _slack_handler
    lora_trainer.register_on_complete(_on_lora_complete)
    lora_trainer.ensure_worker()
    start_watching()
    start_queue_worker()
    start_comfyui_watcher()

    # Slack Socket Mode（遠端觸發生圖）
    settings = get_settings()
    has_app = bool(settings.slack_app_token)
    has_bot = bool(settings.slack_bot_token)
    if has_app and has_bot:
        try:
            from slack_bolt import App
            from slack_bolt.adapter.socket_mode import SocketModeHandler

            from app.services.slack_handler import handle_message

            slack_app = App(token=settings.slack_bot_token)
            slack_app.event("message")(handle_message)
            _slack_handler = SocketModeHandler(slack_app, settings.slack_app_token)
            _slack_handler.connect()
            logger.info("Slack Socket Mode connected")
        except Exception as e:
            logger.exception("Slack Socket Mode failed to start: %s", e)
            _slack_handler = None
    else:
        logger.info(
            "Slack tokens not set (app=%s, bot=%s), skipping Socket Mode",
            has_app,
            has_bot,
        )

    yield

    if _slack_handler:
        try:
            _slack_handler.close()
            logger.info("Slack Socket Mode stopped")
        except Exception as e:
            logger.exception("Slack Socket Mode shutdown error: %s", e)
        _slack_handler = None
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
