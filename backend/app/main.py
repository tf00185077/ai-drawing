"""
AI 自動化出圖系統 - FastAPI 入口
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.watcher import start_watching, stop_watching


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期：啟動時開始監聽，關閉時停止"""
    start_watching()
    yield
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
from app.api import generate, gallery, lora_docs, lora_train

app.include_router(generate.router)
app.include_router(gallery.router)
app.include_router(lora_docs.router)
app.include_router(lora_train.router)


@app.get("/")
async def root():
    return {"status": "ok", "app": "AI 自動化出圖系統"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
