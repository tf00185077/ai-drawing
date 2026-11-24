"""Public intent dispatchers over existing Backend adapters.

Mode-specific inputs are checked before dispatch; no automatic retry, fallback,
workflow rewriting or cross-call transaction is introduced here.
"""
from __future__ import annotations

import inspect
from typing import Any, Literal
from pydantic import StrictBool, StrictInt

from mcp_server.tools import generate as generation, gallery, prompt_library, style_presets, comfyui, comfyui_nodes
from mcp_server.tools.responses import error_payload


def _invalid(message: str) -> dict[str, Any]:
    result = error_payload("intent", "request_validation_failed", message)
    result["error"]["hint"] = "Use the advertised mode/action and provide only its supported fields."
    return result


def generate(
    mode: Literal["template", "custom_workflow"] = "template",
    prompt: str = '1girl, solo',
    character: str | None = None,
    style: str | None = None,
    checkpoint: str | None = None,
    lora: str | None = None,
    template: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
    batch_size: int | None = None,
    sampler_name: str | None = None,
    scheduler: str | None = None,
    lora_strength: float | None = None,
    loras: list[dict] | None = None,
    denoise: float | None = None,
    diffusion_model: str | None = None,
    text_encoder: str | None = None,
    vae: str | None = None,
    use_workflow_defaults: bool | None = None,
    seed_mode: Literal['workflow_default', 'random', 'fixed'] | None = None,
    execution_target: Literal['local', 'worker'] = 'local',
    revision_context: dict | None = None,
    workflow: str = "",
    image: str | None = None,
    image_pose: str | None = None,
    mask: str | None = None,
) -> Any:
    """Submit an image once using a template or custom_workflow JSON string.

    Template mode supports revision_context and workflow-default/seed controls.
    Custom mode requires workflow; image/image_pose/mask are Gallery-relative
    inputs. Omitted overrides preserve graph defaults. Omitted loras preserves
    loaders; [] disables them. Poll job_status with the returned job_id before
    considering resubmission after a timeout. Worker failure never falls back
    to local automatically. Character/style resolution is preserved.
    """
    values = locals().copy()
    fn = generation.generate_image if mode == "template" else generation.generate_image_custom_workflow
    allowed = set(inspect.signature(fn).parameters)
    unsupported = [key for key, value in values.items() if key not in allowed and key != "mode" and value is not None and not (key == "workflow" and value == "")]
    if unsupported:
        return _invalid(f"Fields unsupported in {mode} mode: {', '.join(sorted(unsupported))}")
    if mode == "custom_workflow" and not workflow:
        return _invalid("custom_workflow mode requires workflow")
    return fn(**{key: value for key, value in values.items() if key in allowed})


def gallery_get(image_id: StrictInt | None = None, artifact_id: StrictInt | None = None,
                include_content: StrictBool = False) -> Any:
    """Read image metadata/locators or a canonical artifact (including existing videos).

    include_content=true requires a positive canonical artifact_id and reads a
    bounded static PNG from configured host Gallery (2 MiB, 2048 per dimension).
    Supply exactly one selector. Image IDs and artifact IDs are different
    namespaces. Returned paths and URLs are preserved; host paths require
    access to the Backend filesystem. Use a canonical artifact ID for revision.
    """
    if (image_id is None) == (artifact_id is None):
        return _invalid("Provide exactly one of image_id or artifact_id")
    if include_content and (image_id is not None or type(artifact_id) is not int or artifact_id <= 0):
        return _invalid("Content requires one positive canonical artifact_id")
    if image_id is not None:
        return gallery.get_gallery_image(image_id)
    return gallery.get_gallery_artifact(artifact_id, include_content=include_content)


def prompt_write(
    action: Literal["save", "archive", "restore"],
    resource_type: Literal["category", "entry", "combination"],
    resource_id: str,
    payload: dict | None = None,
    expected_revision: int | None = None,
    expected_etag: str | None = None,
    polarity: str | None = None,
    category_id: str | None = None,
) -> Any:
    """Save, archive or restore a Prompt Library resource with concurrency checks.

    save accepts fields in payload plus explicit expected_revision/expected_etag.
    To save composed combinations, carry positive/negative fragment arrays,
    metadata and applicable context/provenance fields, never rendered strings.
    Create uses revision 0; update uses current revision and ETag. Conflicts
    are returned without overwrite/retry. archive/restore require both current
    revision and ETag; restore supports category/entry only. This write and a
    prior compose are separate calls without an atomic transaction.
    """
    if action == "save":
        if payload is None:
            return _invalid("save requires payload")
        return prompt_library.prompt_library_save(resource_type, resource_id, payload, 0 if expected_revision is None else expected_revision, expected_etag, polarity, category_id)
    if payload is not None:
        return _invalid(f"{action} does not accept payload")
    if expected_revision is None or expected_etag is None:
        return _invalid(f"{action} requires current expected_revision and expected_etag")
    fn = prompt_library.prompt_library_archive if action == "archive" else prompt_library.prompt_library_restore
    return fn(resource_type, resource_id, expected_revision, expected_etag, polarity, category_id)


def style_preset_get(preset_id: str | None = None) -> Any:
    """List lightweight preset summaries without preset_id; otherwise read a full recipe."""
    return style_presets.list_style_presets() if preset_id is None else style_presets.get_style_preset(preset_id)


def style_preset_save(
    from_source: Literal["fields", "successful_job"],
    preset_id: str,
    name: str | None = None,
    base_prompt: str = "",
    negative_prompt: str = "",
    template: str | None = None,
    checkpoint: str | None = None,
    lora: str | None = None,
    lora_strength: float | None = None,
    loras: list[dict] | None = None,
    diffusion_model: str | None = None,
    text_encoder: str | None = None,
    vae: str | None = None,
    default_params: dict | None = None,
    profiles: dict | None = None,
    overwrite: bool = False,
    source: int | str | None = None,
    prompt_keywords: str | list[str] | None = None,
    negative_prompt_keywords: str | list[str] = "",
    profile: str | None = None,
) -> Any:
    """Save a preset from fields or capture a successful server-owned workflow.

    from_source=fields requires preset_id and name; optional recipe fields and
    overwrite retain their existing meaning. successful_job requires source
    (existing job/image locator) and prompt_keywords; profile/negative keywords
    are optional. Call this capture only on an explicit request to save the
    successful result. Backend owns the graph; replay via style_preset_test.
    """
    values = locals().copy()
    if from_source == "fields":
        if not name:
            return _invalid("fields requires name")
        if source is not None or prompt_keywords is not None or profile is not None or negative_prompt_keywords:
            return _invalid("successful_job fields are unsupported in fields mode")
        fn = style_presets.create_style_preset
        values["id"] = preset_id
    else:
        if source is None or prompt_keywords is None:
            return _invalid("successful_job requires source and prompt_keywords")
        if any(value is not None for value in (name, template, checkpoint, lora, lora_strength, loras, diffusion_model, text_encoder, vae, default_params, profiles)) or base_prompt or negative_prompt or overwrite:
            return _invalid("recipe fields are unsupported in successful_job mode")
        fn = style_presets.save_successful_workflow_as_style_preset
    allowed = set(inspect.signature(fn).parameters)
    return fn(**{key: value for key, value in values.items() if key in allowed})


def comfyui_admin(
    action: Literal["restart", "free_memory", "install_node"],
    unload_models: bool = True,
    free_memory: bool = True,
    node_class_names: list[str] | None = None,
) -> Any:
    """Operate the configured local ComfyUI directly: restart, free VRAM or install
    a curated Manager node package. Install never restarts automatically.
    This does not target a worker; consult docs/OPERATING-POLICY.md for authority.
    """
    if action == "install_node":
        if not node_class_names:
            return _invalid("install_node requires node_class_names")
        return comfyui_nodes.comfyui_node_provision(node_class_names)
    if node_class_names is not None:
        return _invalid("node_class_names is supported only for install_node")
    if action == "restart":
        return comfyui_nodes.comfyui_restart()
    return comfyui.free_comfyui_memory(unload_models, free_memory)


def prompt_compose(
    combination_id: str | None = None,
    positive: list[dict] | None = None,
    negative: list[dict] | None = None,
) -> Any:
    """Compose Prompt Library fragments without saving.

    Use combination_id or positive/negative fragments. To persist the returned
    arrays and metadata, call prompt_write(action=save) separately with existing
    revision/ETag and provenance fields. Legacy save_as is rejected at the MCP
    boundary, even when empty or null. No cross-call transaction is promised.
    """
    return prompt_library.prompt_library_compose(combination_id, positive, negative)
