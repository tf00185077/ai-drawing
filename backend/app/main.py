"""
AI 自動化出圖系統 - FastAPI 入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
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
