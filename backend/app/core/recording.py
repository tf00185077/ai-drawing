"""
自動記錄 Pipeline
每次生成後寫入參數，圖片存至結構化資料夾。
生圖完成後、LoRA 訓練完成產圖後，呼叫 save() 寫入 GeneratedImage。
"""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import GeneratedArtifact, GeneratedImage


def _json_or_none(value: dict[str, Any] | str | None) -> str | None:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return value


def save_artifact(
    *,
    gallery_path: str,
    artifact_type: str,
    mime_type: str | None = None,
    job_id: str | None = None,
    source_node_id: str | None = None,
    source_node_type: str | None = None,
    file_size: int | None = None,
    workflow_json: dict[str, Any] | str | None = None,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    metadata: dict[str, Any] | str | None = None,
    fps: float | None = None,
    frame_count: int | None = None,
    duration: float | None = None,
    width: int | None = None,
    height: int | None = None,
    db: Session,
) -> GeneratedArtifact:
    """Write a generic generated artifact record."""
    record = GeneratedArtifact(
        job_id=job_id,
        artifact_type=artifact_type,
        gallery_path=gallery_path,
        mime_type=mime_type,
        source_node_id=source_node_id,
        source_node_type=source_node_type,
        file_size=file_size,
        workflow_json=_json_or_none(workflow_json),
        prompt=prompt,
        negative_prompt=negative_prompt,
        metadata_json=_json_or_none(metadata),
        fps=fps,
        frame_count=frame_count,
        duration=duration,
        width=width,
        height=height,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def save(
    image_path: str,
    *,
    job_id: str | None = None,
    checkpoint: str | None = None,
    lora: str | None = None,
    template: str | None = None,
    diffusion_model: str | None = None,
    text_encoder: str | None = None,
    vae: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    workflow_json: dict[str, Any] | str | None = None,
    source_image: str | None = None,
    source_mask: str | None = None,
    artifact_mime_type: str | None = "image/png",
    artifact_source_node_id: str | None = None,
    artifact_source_node_type: str | None = None,
    artifact_file_size: int | None = None,
    db: Session,
) -> GeneratedImage:
    """
    寫入 GeneratedImage 至資料庫。
    圖片檔必須已存至 gallery_dir。
    workflow_json 為實際送出的 ComfyUI workflow（dict 會序列化為 JSON 字串），供忠實重生。

    Returns:
        新增的 GeneratedImage 實例
    """
    workflow_json = _json_or_none(workflow_json)
    record = GeneratedImage(
        image_path=image_path,
        job_id=job_id,
        checkpoint=checkpoint,
        lora=lora,
        template=template,
        diffusion_model=diffusion_model,
        text_encoder=text_encoder,
        vae=vae,
        seed=seed,
        steps=steps,
        cfg=cfg,
        prompt=prompt,
        negative_prompt=negative_prompt,
        workflow_json=workflow_json,
        source_image=source_image,
        source_mask=source_mask,
    )
    db.add(record)
    db.flush()
    db.add(
        GeneratedArtifact(
            job_id=job_id,
            artifact_type="image",
            gallery_path=image_path,
            mime_type=artifact_mime_type,
            source_node_id=artifact_source_node_id,
            source_node_type=artifact_source_node_type,
            file_size=artifact_file_size,
            workflow_json=workflow_json,
            prompt=prompt,
            negative_prompt=negative_prompt,
        )
    )
    db.commit()
    db.refresh(record)
    return record
