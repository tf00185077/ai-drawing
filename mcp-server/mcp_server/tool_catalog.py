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
    docs_required: bool = True
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
    ToolCatalogEntry("civitai_resource_inspect", "mcp_server.tools.civitai_recipes", "civitai_resource_inspect", "dict", ("POST /api/civitai-recipes/resource-inspect",)),
    ToolCatalogEntry("civitai_resource_select", "mcp_server.tools.civitai_recipes", "civitai_resource_select", "dict", ("POST /api/civitai-recipes/resource-select",)),
    ToolCatalogEntry("civitai_resource_install", "mcp_server.tools.civitai_recipes", "civitai_resource_install", "dict", ("POST /api/civitai-recipes/resource-install",)),
    ToolCatalogEntry("civitai_recipe_import", "mcp_server.tools.civitai_recipes", "civitai_recipe_import", "dict", ("POST /api/civitai-recipes/import",)),
    ToolCatalogEntry("civitai_source_alias_resolve", "mcp_server.tools.civitai_recipes", "civitai_source_alias_resolve", "dict", ("POST /api/civitai-recipes/source-aliases/resolve",)),
    ToolCatalogEntry("civitai_source_alias_resolve_explicit_version", "mcp_server.tools.civitai_recipes", "civitai_source_alias_resolve_explicit_version", "dict", ("POST /api/civitai-recipes/source-aliases/resolve-explicit-version",)),
    ToolCatalogEntry("civitai_source_alias_rename", "mcp_server.tools.civitai_recipes", "civitai_source_alias_rename", "dict", ("POST /api/civitai-recipes/source-aliases/rename",)),
    ToolCatalogEntry("civitai_source_alias_archive", "mcp_server.tools.civitai_recipes", "civitai_source_alias_archive", "dict", ("POST /api/civitai-recipes/source-aliases/archive",)),
    ToolCatalogEntry("civitai_source_alias_repoint", "mcp_server.tools.civitai_recipes", "civitai_source_alias_repoint", "dict", ("POST /api/civitai-recipes/source-aliases/repoint",)),
    ToolCatalogEntry("civitai_source_alias_list", "mcp_server.tools.civitai_recipes", "civitai_source_alias_list", "dict", ("GET /api/civitai-recipes/source-aliases",)),
    ToolCatalogEntry("civitai_source_alias_search", "mcp_server.tools.civitai_recipes", "civitai_source_alias_search", "dict", ("POST /api/civitai-recipes/source-aliases/search",)),
    ToolCatalogEntry("civitai_recipe_inspect", "mcp_server.tools.civitai_recipes", "civitai_recipe_inspect", "dict", ("POST /api/civitai-recipes/inspect",)),
    ToolCatalogEntry("civitai_recipe_resolve", "mcp_server.tools.civitai_recipes", "civitai_recipe_resolve", "dict", ("POST /api/civitai-recipes/resolve",)),
    # CIV-V-C freezes documentation outside this executor scope; catalog still owns registration.
    ToolCatalogEntry("civitai_recipe_local_ledger", "mcp_server.tools.civitai_recipes", "civitai_recipe_local_ledger", "dict", ("GET /api/civitai-recipes/local-ledger",), docs_required=False),
    ToolCatalogEntry("civitai_recipe_resolve_local", "mcp_server.tools.civitai_recipes", "civitai_recipe_resolve_local", "dict", ("POST /api/civitai-recipes/resolve-local",), docs_required=False),
    ToolCatalogEntry("civitai_recipe_compatibility", "mcp_server.tools.civitai_recipes", "civitai_recipe_compatibility", "dict", ("POST /api/civitai-recipes/compatibility",)),
    ToolCatalogEntry("civitai_recipe_build", "mcp_server.tools.civitai_recipes", "civitai_recipe_build", "dict", ("POST /api/civitai-recipes/build",)),
    ToolCatalogEntry("civitai_recipe_run", "mcp_server.tools.civitai_recipes", "civitai_recipe_run", "dict", ("POST /api/civitai-recipes/run",)),
    ToolCatalogEntry("civitai_recipe_variant_generate", "mcp_server.tools.civitai_recipes", "civitai_recipe_variant_generate", "dict", ("POST /api/civitai-recipes/variants/generate-one",)),
    ToolCatalogEntry("civitai_recipe_variation_set_generate", "mcp_server.tools.civitai_recipes", "civitai_recipe_variation_set_generate", "dict", ("POST /api/civitai-recipes/variation-sets",)),
    ToolCatalogEntry("civitai_recipe_variation_set_status", "mcp_server.tools.civitai_recipes", "civitai_recipe_variation_set_status", "dict", ("GET /api/civitai-recipes/variation-sets/{variation_set_id}",)),
    ToolCatalogEntry("civitai_recipe_variation_set_cancel", "mcp_server.tools.civitai_recipes", "civitai_recipe_variation_set_cancel", "dict", ("POST /api/civitai-recipes/variation-sets/{variation_set_id}/cancel",)),
    ToolCatalogEntry("civitai_recipe_variation_set_export", "mcp_server.tools.civitai_recipes", "civitai_recipe_variation_set_export", "dict", ("GET /api/civitai-recipes/variation-sets/{variation_set_id}/export",)),
    ToolCatalogEntry("civitai_recipe_export", "mcp_server.tools.civitai_recipes", "civitai_recipe_export", "dict", ("GET /api/gallery/{image_id}/export?format=recipe",)),
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
    ToolCatalogEntry("lora_dataset_metadata_get", "mcp_server.tools.lora_train", "lora_dataset_metadata_get", "dict", ("GET /api/lora-train/datasets/{folder}/metadata",)),
    ToolCatalogEntry("lora_dataset_metadata_update", "mcp_server.tools.lora_train", "lora_dataset_metadata_update", "dict", ("PUT /api/lora-train/datasets/{folder}/metadata",)),
    ToolCatalogEntry("lora_dataset_metadata_validate", "mcp_server.tools.lora_train", "lora_dataset_metadata_validate", "dict", ("POST /api/lora-train/datasets/{folder}/metadata/validate",)),
    ToolCatalogEntry("lora_dataset_agent_inspect", "mcp_server.tools.lora_train", "lora_dataset_agent_inspect", "dict", ("GET /api/lora-train/datasets/{folder}/agent-inspect",)),
    ToolCatalogEntry("lora_dataset_prepare", "mcp_server.tools.lora_train", "lora_dataset_prepare", "dict", ("POST /api/lora-train/datasets/prepare",)),
    ToolCatalogEntry("lora_dataset_validate", "mcp_server.tools.lora_train", "lora_dataset_validate", "dict", ("POST /api/lora-train/datasets/validate",)),
    ToolCatalogEntry("lora_dataset_caption_assess", "mcp_server.tools.lora_train", "lora_dataset_caption_assess", "dict", ("POST /api/lora-train/datasets/caption-assessment",)),
    ToolCatalogEntry("lora_dataset_curate", "mcp_server.tools.lora_train", "lora_dataset_curate", "dict", ("POST /api/lora-train/datasets/curate",)),
    ToolCatalogEntry("lora_training_decision_preflight", "mcp_server.tools.lora_train", "lora_training_decision_preflight", "dict", ("POST /api/lora-train/datasets/training-decision-preflight",)),
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
