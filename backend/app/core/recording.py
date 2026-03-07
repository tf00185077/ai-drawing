"""
自動記錄 Pipeline
每次生成後寫入參數，圖片存至結構化資料夾。
生圖完成後、LoRA 訓練完成產圖後，呼叫 save() 寫入 GeneratedImage。
"""
from sqlalchemy.orm import Session

from app.db.models import GeneratedImage


def save(
    image_path: str,
    *,
    checkpoint: str | None = None,
    lora: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    db: Session,
) -> GeneratedImage:
    """
    寫入 GeneratedImage 至資料庫。
    圖片檔必須已存至 gallery_dir。

    Returns:
        新增的 GeneratedImage 實例
    """
    record = GeneratedImage(
        image_path=image_path,
        checkpoint=checkpoint,
        lora=lora,
        seed=seed,
        steps=steps,
        cfg=cfg,
        prompt=prompt,
        negative_prompt=negative_prompt,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
