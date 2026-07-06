"""Audited MCP tool catalog.

This module is the source of truth for agent-facing ai-drawing MCP tools.
Tests compare it against FastMCP registration and the public docs so hidden
tools, stale names, and undocumented additions fail quickly.
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
    notes: str = ""


@dataclass(frozen=True)
class IntentionalOmission:
    name: str
    reason: str
    replacement: str


INTENDED_TOOLS: tuple[ToolCatalogEntry, ...] = (
    ToolCatalogEntry("mcp_ping", "mcp_server.server", "mcp_ping", "plain_text", ("GET /health",)),
    ToolCatalogEntry("list_character_styles", "mcp_server.tools.character_style_tools", "list_character_styles", "plain_text"),
    ToolCatalogEntry("resolve_character_style_prompt", "mcp_server.tools.character_style_tools", "resolve_character_style_prompt", "plain_text"),
    ToolCatalogEntry("free_comfyui_memory", "mcp_server.tools.comfyui", "free_comfyui_memory", "json_string", ("POST <ComfyUI>/free",)),
    ToolCatalogEntry("search_nodes", "mcp_server.tools.comfyui", "search_nodes", "json_string", ("GET /api/comfyui/nodes",)),
    ToolCatalogEntry("list_node_categories", "mcp_server.tools.comfyui", "list_node_categories", "json_string", ("GET /api/comfyui/node-categories",)),
    ToolCatalogEntry("get_node_schema", "mcp_server.tools.comfyui", "get_node_schema", "json_string", ("GET /api/comfyui/nodes/{node_type}",)),
    ToolCatalogEntry("gallery_list", "mcp_server.tools.gallery", "gallery_list", "plain_text", ("GET /api/gallery/",)),
    ToolCatalogEntry("get_gallery_image", "mcp_server.tools.gallery", "get_gallery_image", "json_string", ("GET /api/gallery/{image_id}",)),
    ToolCatalogEntry("get_gallery_artifact", "mcp_server.tools.gallery", "get_gallery_artifact", "json_string", ("GET /api/gallery/artifacts/{artifact_id}",)),
    ToolCatalogEntry("gallery_rerun", "mcp_server.tools.gallery", "gallery_rerun", "plain_text", ("POST /api/gallery/{image_id}/rerun",)),
    ToolCatalogEntry("generate_image", "mcp_server.tools.generate", "generate_image", "json_string", ("POST /api/generate/",)),
    ToolCatalogEntry("list_workflow_templates", "mcp_server.tools.generate", "list_workflow_templates", "plain_text", ("GET /api/generate/workflow-templates",)),
    ToolCatalogEntry("get_workflow_template", "mcp_server.tools.generate", "get_workflow_template", "json_string", ("GET /api/generate/workflow-templates/{name}",)),
    ToolCatalogEntry("generate_image_custom_workflow", "mcp_server.tools.generate", "generate_image_custom_workflow", "json_string", ("POST /api/generate/custom",)),
    ToolCatalogEntry("generate_video_custom_workflow", "mcp_server.tools.generate", "generate_video_custom_workflow", "json_string", ("POST /api/generate/video/custom",)),
    ToolCatalogEntry("generate_video_wan_keyframes", "mcp_server.tools.generate", "generate_video_wan_keyframes", "json_string", ("POST /api/generate/video/wan-keyframes",)),
    ToolCatalogEntry("generate_queue_status", "mcp_server.tools.generate", "generate_queue_status", "plain_text", ("GET /api/generate/queue",)),
    ToolCatalogEntry("get_generation_status", "mcp_server.tools.generate", "get_generation_status", "json_string", ("GET /api/generate/job/{job_id}",)),
    ToolCatalogEntry("cancel_job", "mcp_server.tools.generate", "cancel_job", "plain_text", ("DELETE /api/generate/queue/{job_id}",)),
    ToolCatalogEntry("list_available_resources", "mcp_server.tools.generate", "list_available_resources", "json_string", ("GET /api/generate/available-resources",)),
    ToolCatalogEntry("caption_image", "mcp_server.tools.lora_train", "caption_image", "dict", ("POST /api/lora-docs/caption-llm/{image_path}",)),
    ToolCatalogEntry("lora_dataset_list", "mcp_server.tools.lora_train", "lora_dataset_list", "dict", ("GET /api/lora-train/datasets",)),
    ToolCatalogEntry("lora_dataset_inspect", "mcp_server.tools.lora_train", "lora_dataset_inspect", "dict", ("GET /api/lora-train/datasets/{folder}",)),
    ToolCatalogEntry("lora_dataset_prepare", "mcp_server.tools.lora_train", "lora_dataset_prepare", "dict", ("POST /api/lora-train/datasets/prepare",)),
    ToolCatalogEntry("lora_dataset_validate", "mcp_server.tools.lora_train", "lora_dataset_validate", "dict", ("POST /api/lora-train/datasets/validate",)),
    ToolCatalogEntry("lora_dataset_caption_assess", "mcp_server.tools.lora_train", "lora_dataset_caption_assess", "dict", ("POST /api/lora-train/datasets/caption-assessment",)),
    ToolCatalogEntry("lora_train_start", "mcp_server.tools.lora_train", "lora_train_start", "dict", ("POST /api/lora-train/start",)),
    ToolCatalogEntry("lora_train_status", "mcp_server.tools.lora_train", "lora_train_status", "dict", ("GET /api/lora-train/status",)),
    ToolCatalogEntry("lora_train_job_status", "mcp_server.tools.lora_train", "lora_train_job_status", "dict", ("GET /api/lora-train/jobs/{job_id}",)),
    ToolCatalogEntry("lora_train_logs", "mcp_server.tools.lora_train", "lora_train_logs", "dict", ("GET /api/lora-train/jobs/{job_id}/logs",)),
    ToolCatalogEntry("lora_train_cancel", "mcp_server.tools.lora_train", "lora_train_cancel", "dict", ("POST /api/lora-train/jobs/{job_id}/cancel",)),
    ToolCatalogEntry("lora_train_smoke_test", "mcp_server.tools.lora_train", "lora_train_smoke_test", "dict", ("POST /api/lora-train/jobs/{job_id}/smoke-test",)),
    ToolCatalogEntry("create_style_preset", "mcp_server.tools.style_presets", "create_style_preset", "json_string", ("POST /api/style-presets/",)),
    ToolCatalogEntry("reindex_style_presets", "mcp_server.tools.style_presets", "reindex_style_presets", "json_string", ("POST /api/style-presets/reindex",)),
    ToolCatalogEntry("list_style_presets", "mcp_server.tools.style_presets", "list_style_presets", "json_string", ("GET /api/style-presets/",)),
    ToolCatalogEntry("get_style_preset", "mcp_server.tools.style_presets", "get_style_preset", "json_string", ("GET /api/style-presets/{preset_id}",)),
    ToolCatalogEntry("validate_style_presets", "mcp_server.tools.style_presets", "validate_style_presets", "json_string", ("GET /api/style-presets/validate",)),
    ToolCatalogEntry("compose_style_preset", "mcp_server.tools.style_presets", "compose_style_preset", "json_string", ("POST /api/style-presets/{preset_id}/compose",)),
    ToolCatalogEntry("list_template_capabilities", "mcp_server.tools.workflow_catalog", "list_template_capabilities", "json_string", ("GET /api/workflow-catalog/",)),
    ToolCatalogEntry("match_workflow_template", "mcp_server.tools.workflow_catalog", "match_workflow_template", "json_string", ("GET /api/workflow-catalog/match",)),
    ToolCatalogEntry("save_workflow_template", "mcp_server.tools.workflow_catalog", "save_workflow_template", "json_string", ("POST /api/workflow-catalog/backfill",)),
    ToolCatalogEntry("consolidate_workflow_templates", "mcp_server.tools.workflow_catalog", "consolidate_workflow_templates", "json_string", ("POST /api/workflow-catalog/consolidate",)),
    ToolCatalogEntry("validate_template_capabilities", "mcp_server.tools.workflow_catalog", "validate_template_capabilities", "json_string", ("GET /api/workflow-catalog/validate",)),
)


INTENTIONAL_OMISSIONS: tuple[IntentionalOmission, ...] = (
    IntentionalOmission(
        "list_resources",
        "Removed because the name collided with the MCP resources/list primitive.",
        "list_available_resources",
    ),
    IntentionalOmission(
        "get_available_resources",
        "Removed legacy human-readable duplicate.",
        "list_available_resources",
    ),
    IntentionalOmission(
        "get_job_status",
        "Removed legacy human-readable duplicate.",
        "get_generation_status",
    ),
    IntentionalOmission(
        "gallery_detail",
        "Removed legacy human-readable duplicate.",
        "get_gallery_image",
    ),
    IntentionalOmission(
        "generate_image_from_description",
        "Disabled regex/NLP fallback; LLM agents should submit structured generation fields directly.",
        "generate_image",
    ),
    IntentionalOmission(
        "suggest_workflow_from_description",
        "Disabled regex/NLP fallback; agents should inspect catalog/schema tools directly.",
        "list_template_capabilities",
    ),
)


def intended_tool_names() -> tuple[str, ...]:
    return tuple(entry.name for entry in INTENDED_TOOLS if entry.external)
