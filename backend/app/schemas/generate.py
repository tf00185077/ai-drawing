"""
生圖 API 的 Request/Response 結構
對應 docs/api-contract.md 模組 1
"""
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError


class LoraSpec(BaseModel):
    """多 lora 的單一條目；strength_clip 省略時沿用 strength_model（model-only loader 忽略 clip）。"""

    name: str
    strength_model: float = Field(default=1.0, ge=0.0, le=2.0)
    strength_clip: float | None = Field(default=None, ge=0.0, le=2.0)


class GenerateRequest(BaseModel):
    """POST /api/generate/ 的 Request Body"""

    checkpoint: str | None = None
    lora: str | None = None
    loras: list[LoraSpec] | None = Field(
        default=None,
        description="多 lora（依 workflow 內 LoraLoader 節點順序逐一對應）；提供時優先於單一 lora",
    )
    template: str | None = Field(
        default=None,
        description="指定 workflow 模板名稱（如 anima）；省略時依是否有 lora 選 default / default_lora",
    )
    diffusion_model: str | None = Field(
        default=None,
        description="UNETLoader.unet_name（diffusion-model 家族，如 Anima）；省略時沿用模板內嵌值",
    )
    text_encoder: str | None = Field(
        default=None,
        description="CLIPLoader.clip_name；省略時沿用模板內嵌值",
    )
    vae: str | None = Field(
        default=None,
        description="VAELoader.vae_name；省略時沿用模板內嵌值",
    )
    prompt: str = Field(..., min_length=1)
    negative_prompt: str | None = None
    seed: int | None = None
    steps: int | None = Field(default=None, ge=1, le=150)
    cfg: float | None = Field(default=None, ge=1.0, le=30.0)
    use_workflow_defaults: bool = False
    seed_mode: Literal["workflow_default", "random", "fixed"] | None = None
    batch_seed_mode: Literal["shared", "independent"] = "shared"
    width: int | None = Field(default=None, ge=256, le=2048)
    height: int | None = Field(default=None, ge=256, le=2048)
    batch_size: int | None = Field(default=None, ge=1, le=8)
    sampler_name: str | None = None  # e.g. euler, dpmpp_2m, ddim
    scheduler: str | None = None  # e.g. normal, karras, exponential
    lora_strength: float | None = Field(default=None, ge=0.0, le=2.0)
    denoise: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_seed_controls(self) -> "GenerateRequest":
        if self.batch_seed_mode == "independent":
            if self.seed is not None:
                raise PydanticCustomError(
                    "invalid_batch_seed_mode",
                    "independent batch seed mode requires backend-owned random seeds",
                )
            if self.seed_mode in ("fixed", "workflow_default"):
                raise PydanticCustomError(
                    "invalid_batch_seed_mode",
                    "independent batch seed mode accepts only implicit or random seed selection",
                )
        if self.seed_mode is None:
            if self.use_workflow_defaults:
                raise PydanticCustomError("invalid_seed_mode", "seed_mode is required when use_workflow_defaults is true")
            return self
        if self.seed_mode == "workflow_default" and not self.use_workflow_defaults:
            raise PydanticCustomError("invalid_seed_mode", "workflow_default seed requires workflow defaults")
        if self.seed_mode == "fixed" and self.seed is None:
            raise PydanticCustomError("invalid_seed_mode", "fixed seed mode requires seed")
        if self.seed_mode != "fixed" and self.seed is not None:
            raise PydanticCustomError("invalid_seed_mode", "seed is only accepted in fixed mode")
        return self


class GenerateResponse(BaseModel):
    """POST /api/generate/ 的 Response"""

    job_id: str
    status: str = "queued"
    message: str | None = None


class QueueItem(BaseModel):
    """佇列單一項目"""

    job_id: str
    status: str
    submitted_at: str | None = None
    prompt_id: str | None = None
    batch_total: int | None = None
    batch_completed: int | None = None
    batch_failed: int | None = None
    current_batch_index: int | None = None
    failed_members: list[dict[str, Any]] | None = None


class QueueStatusResponse(BaseModel):
    """GET /api/generate/queue 的 Response"""

    queue_running: list[QueueItem] = Field(default_factory=list)
    queue_pending: list[QueueItem] = Field(default_factory=list)


class GenerateCustomRequest(BaseModel):
    """
    POST /api/generate/custom 的 Request Body
    可傳入自訂 ComfyUI workflow JSON，由 AI 根據使用者描述動態產生。
    """

    workflow: dict[str, Any] = Field(
        ...,
        description="ComfyUI API 格式的 workflow 物件，含 class_type、inputs 等節點",
    )
    prompt: str = Field(default="1girl, solo", min_length=1)
    checkpoint: str | None = None
    lora: str | None = None
    loras: list[LoraSpec] | None = Field(
        default=None,
        description="多 lora（依 workflow 內 LoraLoader 節點順序逐一對應）；提供時優先於單一 lora",
    )
    negative_prompt: str | None = None
    seed: int | None = None
    steps: int | None = Field(default=None, ge=1, le=150)
    cfg: float | None = Field(default=None, ge=1.0, le=30.0)
    width: int | None = Field(default=None, ge=256, le=2048)
    height: int | None = Field(default=None, ge=256, le=2048)
    batch_size: int | None = Field(default=None, ge=1, le=8)
    sampler_name: str | None = None
    scheduler: str | None = None
    lora_strength: float | None = Field(default=None, ge=0.0, le=2.0)
    denoise: float | None = Field(default=None, ge=0.0, le=1.0)
    image: str | None = Field(
        default=None,
        description="主體參考圖路徑（img2img），相對於 gallery_dir。會先上傳至 ComfyUI 再替換第一個 LoadImage。與 image_pose 搭配用於 img2img_lora_pose workflow",
    )
    image_pose: str | None = Field(
        default=None,
        description="姿態參考圖路徑，相對於 gallery_dir（如 2026-03-08/ComfyUI_xxx.png）。會先上傳至 ComfyUI 再替換 LoadImage",
    )
    mask: str | None = Field(
        default=None,
        description="遮罩參考圖路徑（inpaint），相對於 gallery_dir。會先上傳至 ComfyUI 再替換 LoadImageMask",
    )
    diffusion_model: str | None = Field(
        default=None,
        description="UNETLoader.unet_name（diffusion-model 家族，如 Anima）；省略時沿用 workflow JSON 既有值",
    )
    text_encoder: str | None = Field(
        default=None,
        description="CLIPLoader.clip_name；省略時沿用 workflow JSON 既有值",
    )
    vae: str | None = Field(
        default=None,
        description="VAELoader.vae_name；省略時沿用 workflow JSON 既有值",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_independent_batch_seed_mode(cls, data: Any) -> Any:
        if (
            isinstance(data, dict)
            and data.get("batch_seed_mode") == "independent"
        ):
            raise PydanticCustomError(
                "invalid_batch_seed_mode",
                "independent batch seed mode only supports normal template generation",
            )
        return data


class GenerateVideoCustomRequest(GenerateCustomRequest):
    """
    POST /api/generate/video/custom 的 Request Body.
    Video MVP still requires a complete supplied ComfyUI workflow JSON.
    """

    first_frame: str | None = Field(
        default=None,
        description="第一幀參考圖，gallery_dir 相對路徑。提供時上傳至 ComfyUI 並注入第一個 LoadImage",
    )
    last_frame: str | None = Field(
        default=None,
        description="最後一幀參考圖，gallery_dir 相對路徑。提供時上傳至 ComfyUI 並注入第二個 LoadImage（若存在）",
    )
    video_ref: str | None = Field(
        default=None,
        description="影片參考檔，gallery_dir 相對路徑。提供時會安全解析為本機檔案路徑並注入 video-like loader",
    )


class GenerateWanKeyframesVideoRequest(BaseModel):
    """POST /api/generate/video/wan-keyframes 的 Request Body."""

    images: list[str] = Field(
        ...,
        min_length=2,
        max_length=16,
        description="多張 keyframe 圖片路徑，皆為 gallery_dir 相對路徑，會複製到 ComfyUI input 後組成單一 WanDancer workflow",
    )
    prompt: str = Field(..., min_length=1)
    negative_prompt: str | None = Field(
        default="low quality, blurry, jitter, heavy flicker, morphing face, distorted face, extra limbs, duplicate character, cropped body, text, watermark",
    )
    width: int = Field(default=320, ge=256, le=2048, multiple_of=16)
    height: int = Field(default=480, ge=256, le=2048, multiple_of=16)
    length: int = Field(default=161, ge=17, le=10000)
    fps: float = Field(default=16.1, gt=0.0, le=120.0)
    steps: int = Field(default=4, ge=1, le=150)
    cfg: float = Field(default=1.0, ge=0.0, le=30.0)
    seed: int | None = Field(default=None, ge=0)
    filename_prefix: str = Field(
        default="video/wan_keyframes",
        min_length=1,
        description="ComfyUI SaveVideo filename_prefix",
    )
