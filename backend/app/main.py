"""
AI 自動化出圖系統 - FastAPI 入口
"""
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.core.queue import start_worker as start_queue_worker, stop_worker as stop_queue_worker
from app.services.watcher import start_watching, stop_watching


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期：啟動時開始監聽與佇列 worker，關閉時停止"""
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
from app.api import generate, gallery, lora_docs, lora_train, prompt_templates

app.include_router(generate.router)
app.include_router(gallery.router)
app.include_router(lora_docs.router)
app.include_router(lora_train.router)
app.include_router(prompt_templates.router)

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
