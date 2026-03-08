"""
專案配置
"""
from pathlib import Path

from pydantic_settings import BaseSettings
from functools import lru_cache

# 專案根目錄（backend 的上層），.env 在此
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # 資料庫
    database_url: str = "sqlite:///./auto_draw.db"

    # ComfyUI
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_ws_url: str = "ws://127.0.0.1:8188/ws"
    comfyui_timeout_submit: float = 60.0
    comfyui_timeout_fetch: float = 30.0
    comfyui_timeout_queue: float = 10.0

    # 輸出目錄
    output_dir: str = "./outputs"
    gallery_dir: str = "./outputs/gallery"

    # LoRA 訓練
    lora_train_dir: str = "./lora_train"
    lora_train_threshold: int = 10  # 自動觸發門檻（圖片數）
    lora_default_checkpoint: str = ""  # 未指定時的預設 checkpoint
    lora_sdxl: bool = False  # True 時使用 sdxl_train_network.py（SDXL/PDXL 模型）
    lora_auto_prompt: str = "1girl, solo, high quality"  # 訓練完成後自動產圖的 prompt
    sd_scripts_path: str = "./sd-scripts"
    sd_scripts_python: str = ""  # WD Tagger 用的 Python，需含 cv2/torch 等。未填則用 python
    # LoRA 訓練參數預設值（API 未帶入時使用）
    lora_resolution: int = 512
    lora_batch_size: int = 4
    lora_learning_rate: str = "1e-4"
    lora_class_tokens: str = "sks"
    lora_keep_tokens: int = 1
    lora_num_repeats: int = 10
    lora_mixed_precision: str = "fp16"
    lora_network_dim: int = 16
    lora_network_alpha: int = 16
    lora_save_every_n_epochs: int = 1  # 每 N epoch 存檔，0=僅最後

    # watchdog
    watch_dirs: str = "./lora_train"  # 逗號分隔

    class Config:
        env_file = str(_PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"  # 允許 .env 有未對應欄位（如 MCP_BACKEND_API_URL）


@lru_cache
def get_settings() -> Settings:
    return Settings()
