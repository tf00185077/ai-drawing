"""
Workflow JSON 管理
可動態替換：checkpoint、LoRA、prompt、negative_prompt、seed、steps、cfg

對應 docs/internal-interfaces.md workflow 介面
"""
from __future__ import annotations

import json
import random
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent.parent / "workflows"


def load_template(name: str) -> dict:
    """
    載入 workflow JSON 模板
    從 backend/workflows/{name}.json 讀取，若 name 已含副檔名則不重複加。

    Args:
        name: 模板名稱，如 "default" 或 "default.json"

    Returns:
        ComfyUI API 格式的 workflow dict

    Raises:
        FileNotFoundError: 模板不存在
    """
    path = WORKFLOWS_DIR / name
    if not path.suffix:
        path = path.with_suffix(".json")
    if not path.exists():
        raise FileNotFoundError(f"Workflow template not found: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def apply_params(
    workflow: dict,
    *,
    checkpoint: str | None = None,
    lora: str | None = None,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int = 20,
    cfg: float = 7.0,
    width: int | None = None,
    height: int | None = None,
    batch_size: int | None = None,
    sampler_name: str | None = None,
    scheduler: str | None = None,
    image: str | None = None,
    image_pose: str | None = None,
    denoise: float | None = None,
    bbox_detector: str | None = "yolo_nas_s_fp16.onnx",
) -> dict:
    """
    將參數替換進 workflow，回傳可提交的 prompt dict。
    ComfyUI prompt 格式為 { "node_id": { "inputs": {...}, "class_type": "..." }, ... }

    透過 class_type 與連線關係自動定位要替換的節點：
    - CheckpointLoaderSimple.ckpt_name <- checkpoint
    - LoraLoader.lora_name <- lora
    - CLIPTextEncode (接 KSampler.positive).text <- prompt
    - CLIPTextEncode (接 KSampler.negative).text <- negative_prompt
    - KSampler.seed, steps, cfg, sampler_name, scheduler, denoise
    - EmptyLatentImage.width, height, batch_size
    - LoadImage.image <- image / image_pose（依節點順序：第一為 subject，第二為 pose）
    - DWPreprocessor.bbox_detector <- bbox_detector（ControlNet 預處理器，預設 yolo_nas_s_fp16.onnx）

    Args:
        workflow: 原始 workflow（會複製，不修改原物件）
        其餘: 生圖參數，None 表示不替換

    Returns:
        已替換參數的 workflow 深拷貝
    """
    import copy

    wf = copy.deepcopy(workflow)

    # 1. 尋找 KSampler → positive/negative 對應的 CLIPTextEncode node_id
    # 若中間有 ControlNetApply，需再追蹤其 positive/negative 輸入
    ksampler_ids: list[str] = []
    positive_node_ids: set[str] = set()
    negative_node_ids: set[str] = set()

    def _resolve_to_clip(nid: str) -> str | None:
        """追蹤到 CLIPTextEncode，若為 ControlNetApply 則再往上游找"""
        node = wf.get(nid)
        if not isinstance(node, dict):
            return None
        ct = node.get("class_type")
        if ct == "CLIPTextEncode":
            return nid
        if ct == "ControlNetApply":
            pos_in = node.get("inputs", {}).get("positive") or node.get("inputs", {}).get("conditioning")
            if isinstance(pos_in, list) and len(pos_in) >= 1:
                return _resolve_to_clip(str(pos_in[0]))
        return None

    def _resolve_neg_to_clip(nid: str) -> str | None:
        """追蹤 negative 到 CLIPTextEncode"""
        node = wf.get(nid)
        if not isinstance(node, dict):
            return None
        ct = node.get("class_type")
        if ct == "CLIPTextEncode":
            return nid
        if ct == "ControlNetApply":
            neg_in = node.get("inputs", {}).get("negative")
            if isinstance(neg_in, list) and len(neg_in) >= 1:
                return _resolve_neg_to_clip(str(neg_in[0]))
        return None

    for nid, node in wf.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type")
        inputs = node.get("inputs", {})
        if ct == "KSampler":
            ksampler_ids.append(nid)
            pos_link = inputs.get("positive")
            neg_link = inputs.get("negative")
            if isinstance(pos_link, list) and len(pos_link) >= 1:
                resolved = _resolve_to_clip(str(pos_link[0]))
                if resolved:
                    positive_node_ids.add(resolved)
                else:
                    positive_node_ids.add(str(pos_link[0]))
            if isinstance(neg_link, list) and len(neg_link) >= 1:
                resolved = _resolve_neg_to_clip(str(neg_link[0]))
                if resolved:
                    negative_node_ids.add(resolved)
                else:
                    negative_node_ids.add(str(neg_link[0]))

    # 1b. 找出 LoadImage 節點（依 node id 排序，第一為 subject、第二為 pose）
    load_image_ids = sorted(
        nid for nid, node in wf.items()
        if isinstance(node, dict) and node.get("class_type") == "LoadImage"
    )

    # 2. 替換各類節點
    for nid, node in wf.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type")
        inputs = node.get("inputs", {})

        if ct == "CheckpointLoaderSimple" and checkpoint is not None:
            inputs["ckpt_name"] = checkpoint

        if ct == "LoraLoader" and lora is not None:
            inputs["lora_name"] = lora

        if ct == "KSampler":
            if seed is not None:
                inputs["seed"] = seed
            else:
                inputs["seed"] = random.randint(0, 2**32 - 1)
            inputs["steps"] = steps
            inputs["cfg"] = cfg
            if sampler_name is not None:
                inputs["sampler_name"] = sampler_name
            if scheduler is not None:
                inputs["scheduler"] = scheduler
            if denoise is not None:
                inputs["denoise"] = denoise

        if ct == "LoadImage" and (image is not None or image_pose is not None):
            idx = load_image_ids.index(nid) if nid in load_image_ids else -1
            # image_pose 用於第二個 LoadImage，或僅有一個 LoadImage（ControlNet pose）時
            if image_pose is not None and (idx == 1 or len(load_image_ids) == 1):
                inputs["image"] = image_pose
            elif image is not None:
                inputs["image"] = image

        if ct == "DWPreprocessor" and bbox_detector is not None:
            inputs["bbox_detector"] = bbox_detector

        if ct == "EmptyLatentImage":
            if width is not None:
                inputs["width"] = width
            if height is not None:
                inputs["height"] = height
            if batch_size is not None:
                inputs["batch_size"] = batch_size

        if ct == "CLIPTextEncode":
            if nid in positive_node_ids and prompt is not None:
                inputs["text"] = prompt
            if nid in negative_node_ids and negative_prompt is not None:
                inputs["text"] = negative_prompt

    return wf


def get_seed_from_workflow(workflow: dict) -> int | None:
    """
    從 workflow 中提取 KSampler 的 seed。
    用於 recording 時取得「實際使用」的 seed（含 apply_params 產生的隨機值）。

    Returns:
        KSampler 的 seed，若無則 None
    """
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "KSampler":
            seed = node.get("inputs", {}).get("seed")
            if isinstance(seed, int):
                return seed
    return None
