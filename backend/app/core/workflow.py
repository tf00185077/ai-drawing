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
    prompt: str = "",
    negative_prompt: str = "",
    seed: int | None = None,
    steps: int = 20,
    cfg: float = 7.0,
    width: int | None = None,
    height: int | None = None,
    batch_size: int | None = None,
    sampler_name: str | None = None,
    scheduler: str | None = None,
) -> dict:
    """
    將參數替換進 workflow，回傳可提交的 prompt dict。
    ComfyUI prompt 格式為 { "node_id": { "inputs": {...}, "class_type": "..." }, ... }

    透過 class_type 與連線關係自動定位要替換的節點：
    - CheckpointLoaderSimple.ckpt_name <- checkpoint
    - LoraLoader.lora_name <- lora
    - CLIPTextEncode (接 KSampler.positive).text <- prompt
    - CLIPTextEncode (接 KSampler.negative).text <- negative_prompt
    - KSampler.seed, steps, cfg, sampler_name, scheduler
    - EmptyLatentImage.width, height, batch_size

    Args:
        workflow: 原始 workflow（會複製，不修改原物件）
        其餘: 生圖參數，None 表示不替換

    Returns:
        已替換參數的 workflow 深拷貝
    """
    import copy

    wf = copy.deepcopy(workflow)

    # 1. 尋找 KSampler 以取得 positive/negative 對應的 node_id
    ksampler_ids: list[str] = []
    positive_node_ids: set[str] = set()
    negative_node_ids: set[str] = set()

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
                positive_node_ids.add(str(pos_link[0]))
            if isinstance(neg_link, list) and len(neg_link) >= 1:
                negative_node_ids.add(str(neg_link[0]))

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

        if ct == "EmptyLatentImage":
            if width is not None:
                inputs["width"] = width
            if height is not None:
                inputs["height"] = height
            if batch_size is not None:
                inputs["batch_size"] = batch_size

        if ct == "CLIPTextEncode":
            if nid in positive_node_ids:
                inputs["text"] = prompt
            if nid in negative_node_ids:
                inputs["text"] = negative_prompt

    return wf
