"""Describe text-only workflows as generation forms for UI and agents."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.workflow_manifest import load_manifests

EXTERNAL_IO = {"image_ref", "pose_ref", "mask", "first_frame", "last_frame", "video_ref", "audio_ref"}
EXTERNAL_CONDITIONING = {"controlnet_pose", "pose_transfer"}


class WorkflowParameterDescriptor(BaseModel):
    name: str
    kind: Literal["number", "select", "lora_list", "seed"]
    default: Any | None = None
    defaults: list[Any] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    slot_count: int | None = None


class WorkflowGenerationForm(BaseModel):
    id: str
    display_name: str
    description: str
    model_family: str
    modality: Literal["txt2img"] = "txt2img"
    io: list[str]
    fields: list[WorkflowParameterDescriptor]


class GenerationFormsResponse(BaseModel):
    items: list[WorkflowGenerationForm]
    capability_source: Literal["live", "fallback"] = "fallback"


def _values(workflow: dict[str, Any], class_types: set[str], key: str) -> list[Any]:
    values = []
    for node in workflow.values():
        if node.get("class_type") in class_types and key in node.get("inputs", {}):
            value = node["inputs"][key]
            if value not in values:
                values.append(value)
    return values


def build_generation_forms(workflows_dir: Path, *, resources: dict[str, list[str]], object_info: dict[str, Any]) -> GenerationFormsResponse:
    items = []
    sampler_schema = object_info.get("KSampler", {}).get("input", {}).get("required", {})
    for loaded in load_manifests(workflows_dir):
        manifest = loaded.manifest
        if not (loaded.valid and not manifest.deprecated and manifest.modality == "txt2img" and "text" in manifest.io and not set(manifest.io) & EXTERNAL_IO and not set(manifest.conditioning) & EXTERNAL_CONDITIONING):
            continue
        workflow = json.loads((workflows_dir / f"{manifest.id}.json").read_text(encoding="utf-8"))
        specs = [
            ("checkpoint", "select", {"CheckpointLoaderSimple"}, "ckpt_name", "checkpoints"),
            ("diffusion_model", "select", {"UNETLoader"}, "unet_name", "diffusion_models"),
            ("text_encoder", "select", {"CLIPLoader"}, "clip_name", "text_encoders"),
            ("vae", "select", {"VAELoader"}, "vae_name", "vaes"),
            ("seed", "seed", {"KSampler"}, "seed", None),
            ("steps", "number", {"KSampler"}, "steps", None),
            ("cfg", "number", {"KSampler"}, "cfg", None),
            ("sampler_name", "select", {"KSampler"}, "sampler_name", None),
            ("scheduler", "select", {"KSampler"}, "scheduler", None),
            ("denoise", "number", {"KSampler"}, "denoise", None),
            ("width", "number", {"EmptyLatentImage", "EmptySD3LatentImage"}, "width", None),
            ("height", "number", {"EmptyLatentImage", "EmptySD3LatentImage"}, "height", None),
            ("batch_size", "number", {"EmptyLatentImage", "EmptySD3LatentImage"}, "batch_size", None),
        ]
        fields = []
        for name, kind, classes, key, resource_key in specs:
            values = _values(workflow, classes, key)
            if not values:
                continue
            options = list(resources.get(resource_key, [])) if resource_key else []
            schema = sampler_schema.get(name)
            if isinstance(schema, (list, tuple)) and schema and isinstance(schema[0], list):
                options = list(schema[0])
            fields.append(WorkflowParameterDescriptor(name=name, kind=kind, default=values[0] if len(values) == 1 else None, defaults=values, options=options))
        items.append(WorkflowGenerationForm(id=manifest.id, display_name=manifest.id.replace("_", " "), description=manifest.description, model_family=manifest.model_family, io=list(manifest.io), fields=fields))
    return GenerationFormsResponse(items=items, capability_source="live" if object_info else "fallback")
