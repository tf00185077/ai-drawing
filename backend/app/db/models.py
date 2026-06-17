"""
資料庫 Schema
欄位：圖片路徑、checkpoint、LoRA、seed、steps、prompt、生成時間
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float

from app.db.database import Base


class GeneratedImage(Base):
    """生成圖片記錄"""
    __tablename__ = "generated_images"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), nullable=True, index=True)
    image_path = Column(String(512), nullable=False)
    checkpoint = Column(String(256), nullable=True)
    lora = Column(String(256), nullable=True)
    # 重生所需：使用的 workflow 模板與 diffusion-model 家族（如 Anima）的元件檔名
    template = Column(String(128), nullable=True)
    diffusion_model = Column(String(256), nullable=True)  # UNETLoader.unet_name
    text_encoder = Column(String(256), nullable=True)  # CLIPLoader.clip_name
    vae = Column(String(256), nullable=True)  # VAELoader.vae_name
    seed = Column(Integer, nullable=True)
    steps = Column(Integer, nullable=True)
    cfg = Column(Float, nullable=True)
    prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
