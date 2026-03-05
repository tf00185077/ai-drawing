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
    image_path = Column(String(512), nullable=False)
    checkpoint = Column(String(256), nullable=True)
    lora = Column(String(256), nullable=True)
    seed = Column(Integer, nullable=True)
    steps = Column(Integer, nullable=True)
    cfg = Column(Float, nullable=True)
    prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
