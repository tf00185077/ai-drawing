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


Risk = Literal["read", "mutate", "admin"]


@dataclass(frozen=True)
class ToolCatalogEntry:
    name: str
    module: str
    function: str
    risk: Risk
    backend_endpoints: tuple[str, ...] = ()
    response_category: Literal["envelope"] = "envelope"
    external: bool = True
    docs_required: bool = True
    notes: str = ""


INTENDED_TOOLS: tuple[ToolCatalogEntry, ...] = (
    ToolCatalogEntry('health', 'mcp_server.tools.health', 'health', 'read', ('GET /health', 'GET /api/system/status', 'GET /api/workers/status')),
    ToolCatalogEntry('list_workers', 'mcp_server.tools.health', 'list_workers', 'read', ('GET /api/workers/status',)),
    ToolCatalogEntry('civitai_source_info', 'mcp_server.tools.civitai', 'civitai_source_info', 'read', ('GET /api/civitai/source-info',)),
    ToolCatalogEntry('civitai_resource_acquire', 'mcp_server.tools.civitai', 'civitai_resource_acquire', 'mutate', ('POST /api/civitai/resources/acquire',)),
    ToolCatalogEntry('civitai_resource_status', 'mcp_server.tools.civitai', 'civitai_resource_status', 'read', ('GET /api/civitai/resources/status',)),
    ToolCatalogEntry('generate', 'mcp_server.tools.intents', 'generate', 'mutate', ('POST /api/generate/', 'POST /api/generate/custom')),
    ToolCatalogEntry('job_status', 'mcp_server.tools.generate', 'get_generation_status', 'read', ('GET /api/generate/job/{job_id}',)),
    ToolCatalogEntry('wait_for_job', 'mcp_server.tools.wait_for_job', 'wait_for_job', 'read', ('GET /api/generate/job/{job_id}', 'GET /api/lora-train/jobs/{job_id}', 'GET /api/gallery/artifacts/{artifact_id}', 'GET /api/gallery/{image_id}')),
    ToolCatalogEntry('cancel_job', 'mcp_server.tools.generate', 'cancel_job', 'mutate', ('DELETE /api/generate/queue/{job_id}',)),
    ToolCatalogEntry('list_resources', 'mcp_server.tools.generate', 'list_available_resources', 'read', ('GET /api/generate/available-resources', 'GET /api/workflow-catalog/generation-forms')),
    ToolCatalogEntry('deliver_to_discord', 'mcp_server.tools.discord_delivery', 'deliver_generation_result_to_discord', 'mutate', ('POST <DiscordBot>/operator/v1/deliver-result',)),
    ToolCatalogEntry('gallery_search', 'mcp_server.tools.gallery', 'gallery_list', 'read', ('GET /api/gallery/',)),
    ToolCatalogEntry('gallery_get', 'mcp_server.tools.intents', 'gallery_get', 'read', ('GET /api/gallery/{image_id}', 'GET /api/gallery/artifacts/{artifact_id}')),
    ToolCatalogEntry('gallery_rerun', 'mcp_server.tools.gallery', 'gallery_rerun', 'mutate', ('POST /api/gallery/{image_id}/rerun',)),
    ToolCatalogEntry('comfyui_admin', 'mcp_server.tools.intents', 'comfyui_admin', 'admin', ('POST <ComfyUI>/free', 'GET <ComfyUI>/customnode/getmappings', 'POST <ComfyUI>/manager/queue/install', 'POST <ComfyUI>/manager/queue/start', 'GET <ComfyUI>/manager/queue/status', 'POST <ComfyUI>/manager/reboot')),
    ToolCatalogEntry('style_preset_save', 'mcp_server.tools.intents', 'style_preset_save', 'mutate', ('POST /api/style-presets/', 'POST /api/style-presets/{preset_id}/workflow/save')),
    ToolCatalogEntry('style_preset_get', 'mcp_server.tools.intents', 'style_preset_get', 'read', ('GET /api/style-presets/', 'GET /api/style-presets/{preset_id}')),
    ToolCatalogEntry('style_preset_compose', 'mcp_server.tools.style_presets', 'compose_style_preset', 'read', ('POST /api/style-presets/{preset_id}/compose',)),
    ToolCatalogEntry('style_preset_test', 'mcp_server.tools.style_presets', 'test_saved_style_preset_workflow', 'mutate', ('POST /api/style-presets/{preset_id}/workflow/test',)),
    ToolCatalogEntry('prompt_search', 'mcp_server.tools.prompt_library', 'prompt_library_search', 'read', ('GET /api/prompt-library/catalog', 'GET /api/prompt-library/categories/{polarity}/{category_id}', 'GET /api/prompt-library/search')),
    ToolCatalogEntry('prompt_write', 'mcp_server.tools.intents', 'prompt_write', 'mutate', ('PUT /api/prompt-library/categories/{polarity}/{category_id}', 'PUT /api/prompt-library/categories/{polarity}/{category_id}/entries/{entry_id}', 'PUT /api/prompt-library/combinations/{combination_id}', 'POST /api/prompt-library/archive', 'POST /api/prompt-library/restore')),
    ToolCatalogEntry('prompt_compose', 'mcp_server.tools.intents', 'prompt_compose', 'read', ('POST /api/prompt-library/compose',)),
    ToolCatalogEntry('caption_image', 'mcp_server.tools.lora_train', 'caption_image', 'mutate', ('POST /api/lora-docs/caption-llm/{image_path}',)),
    ToolCatalogEntry('lora_training_decision_preflight', 'mcp_server.tools.lora_train', 'lora_training_decision_preflight', 'read', ('POST /api/lora-train/datasets/training-decision-preflight',)),
    ToolCatalogEntry('lora_train_start', 'mcp_server.tools.lora_train', 'lora_train_start', 'mutate', ('POST /api/lora-train/start',)),
    ToolCatalogEntry('lora_train_job_status', 'mcp_server.tools.lora_train', 'lora_train_job_status', 'read', ('GET /api/lora-train/jobs/{job_id}',)),
    ToolCatalogEntry('lora_train_logs', 'mcp_server.tools.lora_train', 'lora_train_logs', 'read', ('GET /api/lora-train/jobs/{job_id}/logs',)),
    ToolCatalogEntry('lora_train_cancel', 'mcp_server.tools.lora_train', 'lora_train_cancel', 'mutate', ('POST /api/lora-train/jobs/{job_id}/cancel',)),
    ToolCatalogEntry('lora_dataset_list', 'mcp_server.tools.lora_train', 'lora_dataset_list', 'read', ('GET /api/lora-train/datasets',)),
    ToolCatalogEntry('lora_dataset_inspect', 'mcp_server.tools.lora_train', 'lora_dataset_inspect', 'read', ('GET /api/lora-train/datasets/{folder}/agent-inspect',)),
    ToolCatalogEntry('lora_train_smoke_test', 'mcp_server.tools.lora_train', 'lora_train_smoke_test', 'mutate', ('POST /api/lora-train/jobs/{job_id}/smoke-test',)),
)


def intended_tool_names() -> tuple[str, ...]:
    return tuple(entry.name for entry in INTENDED_TOOLS if entry.external)
