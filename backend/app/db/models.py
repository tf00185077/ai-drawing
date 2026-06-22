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
    # 忠實重生所需：實際送出 ComfyUI 的完整 workflow（JSON 字串），以及來源圖/遮罩的
    # gallery 相對路徑（workflow_json 內只嵌 ComfyUI 暫存輸入檔名，重生需重新上傳原圖）。
    workflow_json = Column(Text, nullable=True)
    source_image = Column(String(512), nullable=True)
    source_mask = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GeneratedArtifact(Base):
    """Generic generated artifact record for images, videos, and future files."""
    __tablename__ = "generated_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), nullable=True, index=True)
    artifact_type = Column(String(32), nullable=False, index=True)
    gallery_path = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=True)
    source_node_id = Column(String(64), nullable=True)
    source_node_type = Column(String(256), nullable=True)
    file_size = Column(Integer, nullable=True)
    workflow_json = Column(Text, nullable=True)
    prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    fps = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
