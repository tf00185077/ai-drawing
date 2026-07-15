"""Audited MCP tool catalog.

This module is the source of truth for agent-facing ai-drawing MCP tools.
Tests compare it against FastMCP registration so hidden tools and stale
names fail quickly.

Design rule: one tool per user intent. Low-level plumbing (workflow JSON
assembly, resource ledgers, provenance audits, registries) lives behind the
backend HTTP API and is never exposed as an MCP tool.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ResponseCategory = Literal["dict", "json_string", "plain_text"]


@dataclass(frozen=True)
class ToolCatalogEntry:
    name: str
    module: str
    function: str
    response_category: ResponseCategory
    backend_endpoints: tuple[str, ...] = ()
    external: bool = True
    docs_required: bool = True
    notes: str = ""


INTENDED_TOOLS: tuple[ToolCatalogEntry, ...] = (
    # Health
    ToolCatalogEntry("mcp_ping", "mcp_server.server", "mcp_ping", "plain_text", ("GET /health",)),
    # Civitai best-effort flow
    ToolCatalogEntry("civitai_source_info", "mcp_server.tools.civitai", "civitai_source_info", "dict", ("GET /api/civitai/source-info",)),
    ToolCatalogEntry("civitai_generate_like", "mcp_server.tools.civitai", "civitai_generate_like", "dict", ("POST /api/civitai/generate-like",)),
    ToolCatalogEntry("civitai_resource_acquire", "mcp_server.tools.civitai", "civitai_resource_acquire", "dict", ("POST /api/civitai/resources/acquire",)),
    ToolCatalogEntry("civitai_resource_status", "mcp_server.tools.civitai", "civitai_resource_status", "dict", ("GET /api/civitai/resources/status",)),
    # Generation
    ToolCatalogEntry("generate_image", "mcp_server.tools.generate", "generate_image", "json_string", ("POST /api/generate/",)),
    ToolCatalogEntry("generate_image_custom_workflow", "mcp_server.tools.generate", "generate_image_custom_workflow", "json_string", ("POST /api/generate/custom",), notes="escape hatch for img2img/ControlNet/inpaint; start from backend/workflows/*.json"),
    ToolCatalogEntry("generate_video_wan_keyframes", "mcp_server.tools.generate", "generate_video_wan_keyframes", "json_string", ("POST /api/generate/video/wan-keyframes",)),
    ToolCatalogEntry("generate_video_custom_workflow", "mcp_server.tools.generate", "generate_video_custom_workflow", "json_string", ("POST /api/generate/video/custom",), notes="submit a known-good video workflow JSON"),
    ToolCatalogEntry("get_generation_status", "mcp_server.tools.generate", "get_generation_status", "json_string", ("GET /api/generate/job/{job_id}",)),
    ToolCatalogEntry("cancel_job", "mcp_server.tools.generate", "cancel_job", "json_string", ("DELETE /api/generate/queue/{job_id}",)),
    ToolCatalogEntry("list_available_resources", "mcp_server.tools.generate", "list_available_resources", "json_string", ("GET /api/generate/available-resources",)),
    # Gallery
    ToolCatalogEntry("gallery_list", "mcp_server.tools.gallery", "gallery_list", "plain_text", ("GET /api/gallery/",)),
    ToolCatalogEntry("get_gallery_image", "mcp_server.tools.gallery", "get_gallery_image", "json_string", ("GET /api/gallery/{image_id}",)),
    ToolCatalogEntry("get_gallery_artifact", "mcp_server.tools.gallery", "get_gallery_artifact", "json_string", ("GET /api/gallery/artifacts/{artifact_id}",)),
    ToolCatalogEntry("gallery_rerun", "mcp_server.tools.gallery", "gallery_rerun", "plain_text", ("POST /api/gallery/{image_id}/rerun",)),
    # ComfyUI ops
    ToolCatalogEntry("free_comfyui_memory", "mcp_server.tools.comfyui", "free_comfyui_memory", "json_string", ("POST <ComfyUI>/free",)),
    # LoRA training
    ToolCatalogEntry("caption_image", "mcp_server.tools.lora_train", "caption_image", "dict", ("POST /api/lora-docs/caption-llm/{image_path}",)),
    ToolCatalogEntry("lora_training_decision_preflight", "mcp_server.tools.lora_train", "lora_training_decision_preflight", "dict", ("POST /api/lora-train/datasets/training-decision-preflight",)),
    ToolCatalogEntry("lora_train_start", "mcp_server.tools.lora_train", "lora_train_start", "dict", ("POST /api/lora-train/start",)),
    ToolCatalogEntry("lora_train_job_status", "mcp_server.tools.lora_train", "lora_train_job_status", "dict", ("GET /api/lora-train/jobs/{job_id}",)),
    ToolCatalogEntry("lora_train_logs", "mcp_server.tools.lora_train", "lora_train_logs", "dict", ("GET /api/lora-train/jobs/{job_id}/logs",)),
    ToolCatalogEntry("lora_train_cancel", "mcp_server.tools.lora_train", "lora_train_cancel", "dict", ("POST /api/lora-train/jobs/{job_id}/cancel",)),
)


def intended_tool_names() -> tuple[str, ...]:
    return tuple(entry.name for entry in INTENDED_TOOLS if entry.external)
