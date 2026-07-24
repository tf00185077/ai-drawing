"""Save a proven generation graph as a keyword-only style-preset workflow."""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.queue import get_job_status
from app.core.style_presets import (
    DirStylePresetProvider,
    is_valid_preset_id,
)
from app.db.models import GeneratedArtifact, GeneratedImage


SourceKind = Literal["image", "artifact", "job"]
_SAMPLER_CLASS_TYPES = frozenset({"KSampler", "KSamplerAdvanced"})
_KEYWORD_SEPARATOR = re.compile(r"[,\n]")
_SAFE_LINKED_TEXT_CARRIER_FIELDS: dict[str, tuple[str, ...]] = {
    "Primitive": ("value",),
    "PrimitiveNode": ("value",),
    "String": ("text", "value"),
}


class StylePresetWorkflowError(ValueError):
    """Repairable domain error returned by workflow save/read/test routes."""

    def __init__(
        self,
        code: str,
        message: str,
        hint: str,
        *,
        status_code: int = 422,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.status_code = status_code
        super().__init__(message)

    def detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "hint": self.hint}


@dataclass(frozen=True)
class SourceLocator:
    kind: SourceKind
    identifier: int | str


@dataclass(frozen=True)
class ResolvedWorkflow:
    source_type: SourceKind
    source_id: str
    workflow: dict[str, Any]
    source_prompt: str | None
    source_negative_prompt: str | None


@dataclass(frozen=True)
class SavedWorkflow:
    preset_id: str
    profile: str | None
    source_type: SourceKind
    source_id: str
    workflow_path: str
    prompt_keywords: list[str]
    negative_prompt_keywords: list[str]
    retest_required: bool = True


def _source_error(
    code: str,
    message: str,
    hint: str,
    *,
    status_code: int = 422,
) -> StylePresetWorkflowError:
    return StylePresetWorkflowError(
        code, message, hint, status_code=status_code
    )


def parse_source_locator(source: int | str) -> SourceLocator:
    """Parse a compact image/artifact/job locator without accepting paths."""
    if isinstance(source, bool):
        raise _source_error(
            "source_not_found",
            "The generation source locator is invalid.",
            "Use an image id, image:<id>, artifact:<id>, or job:<job-id>.",
            status_code=404,
        )
    if isinstance(source, int):
        if source > 0:
            return SourceLocator("image", source)
        raise _source_error(
            "source_not_found",
            "The Gallery image id must be positive.",
            "Use a positive Gallery image id from a successful generation.",
            status_code=404,
        )
    if not isinstance(source, str):
        raise _source_error(
            "source_not_found",
            "The generation source locator is invalid.",
            "Use an image id, image:<id>, artifact:<id>, or job:<job-id>.",
            status_code=404,
        )

    value = source.strip()
    if not value:
        raise _source_error(
            "source_not_found",
            "The generation source locator is empty.",
            "Provide a successful Gallery image, image artifact, or completed job id.",
            status_code=404,
        )
    if value.isdecimal():
        identifier = int(value)
        if identifier > 0:
            return SourceLocator("image", identifier)

    prefix, separator, suffix = value.partition(":")
    if separator:
        normalized_prefix = prefix.strip().lower()
        normalized_suffix = suffix.strip()
        if normalized_prefix in {"image", "artifact"}:
            if normalized_suffix.isdecimal() and int(normalized_suffix) > 0:
                return SourceLocator(
                    normalized_prefix, int(normalized_suffix)
                )
        elif normalized_prefix == "job" and normalized_suffix:
            return SourceLocator("job", normalized_suffix)
        raise _source_error(
            "source_not_found",
            f"Unsupported generation source locator: {value}",
            "Use image:<id>, artifact:<id>, or job:<job-id>.",
            status_code=404,
        )

    return SourceLocator("job", value)


def normalize_keywords(value: str | list[str] | None) -> list[str]:
    """Normalize only separators, whitespace, empty items, and exact duplicates."""
    if value is None:
        return []
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or any(
        not isinstance(item, str) for item in values
    ):
        raise StylePresetWorkflowError(
            "invalid_keywords",
            "Keywords must be a string or a list of strings.",
            "Provide compact comma/newline-separated keywords or a string list.",
        )

    normalized: list[str] = []
    seen: set[str] = set()
    for value_item in values:
        for item in _KEYWORD_SEPARATOR.split(value_item):
            keyword = item.strip()
            if keyword and keyword not in seen:
                normalized.append(keyword)
                seen.add(keyword)
    return normalized


def _parse_recorded_graph(value: object) -> dict[str, Any]:
    if not value:
        raise _source_error(
            "source_has_no_workflow",
            "The successful source has no recorded workflow graph.",
            "Choose a newer successful image whose Gallery record includes workflow_json.",
        )
    try:
        graph = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError) as exc:
        raise _source_error(
            "source_has_no_workflow",
            "The source workflow_json is not valid JSON.",
            "Choose another successful Gallery image with a valid recorded workflow.",
        ) from exc
    if not isinstance(graph, dict) or not graph:
        raise _source_error(
            "source_has_no_workflow",
            "The source workflow_json is not a nonempty graph object.",
            "Choose another successful Gallery image with a recorded ComfyUI API graph.",
        )
    return copy.deepcopy(graph)


def _resolved(
    kind: SourceKind,
    source_id: int | str,
    workflow_json: object,
    source_prompt: str | None,
    source_negative_prompt: str | None,
) -> ResolvedWorkflow:
    return ResolvedWorkflow(
        source_type=kind,
        source_id=str(source_id),
        workflow=_parse_recorded_graph(workflow_json),
        source_prompt=source_prompt,
        source_negative_prompt=source_negative_prompt,
    )


def resolve_successful_workflow(
    session: Session, source: int | str
) -> ResolvedWorkflow:
    """Resolve a successful image-compatible record to its server-owned graph."""
    locator = parse_source_locator(source)
    if locator.kind == "image":
        row = (
            session.query(GeneratedImage)
            .filter(GeneratedImage.id == locator.identifier)
            .first()
        )
        if row is None:
            raise _source_error(
                "source_not_found",
                f"Gallery image {locator.identifier} was not found.",
                "Use an id returned by get_gallery_image or a completed generation job.",
                status_code=404,
            )
        return _resolved(
            "image",
            locator.identifier,
            row.workflow_json,
            row.prompt,
            row.negative_prompt,
        )

    if locator.kind == "artifact":
        row = (
            session.query(GeneratedArtifact)
            .filter(GeneratedArtifact.id == locator.identifier)
            .first()
        )
        if row is None:
            raise _source_error(
                "source_not_found",
                f"Generated artifact {locator.identifier} was not found.",
                "Use an artifact id returned by a completed generation.",
                status_code=404,
            )
        if row.artifact_type != "image":
            raise _source_error(
                "source_not_image",
                f"Artifact {locator.identifier} is not an image.",
                "Choose a successful image artifact, Gallery image id, or image-generation job.",
            )
        return _resolved(
            "artifact",
            locator.identifier,
            row.workflow_json,
            row.prompt,
            row.negative_prompt,
        )

    job_id = str(locator.identifier)
    image_row = (
        session.query(GeneratedImage)
        .filter(GeneratedImage.job_id == job_id)
        .order_by(GeneratedImage.id.asc())
        .first()
    )
    if image_row is not None:
        return _resolved(
            "job",
            job_id,
            image_row.workflow_json,
            image_row.prompt,
            image_row.negative_prompt,
        )

    artifacts = (
        session.query(GeneratedArtifact)
        .filter(GeneratedArtifact.job_id == job_id)
        .order_by(GeneratedArtifact.id.asc())
        .all()
    )
    image_artifact = next(
        (row for row in artifacts if row.artifact_type == "image"), None
    )
    if image_artifact is not None:
        return _resolved(
            "job",
            job_id,
            image_artifact.workflow_json,
            image_artifact.prompt,
            image_artifact.negative_prompt,
        )
    if artifacts:
        raise _source_error(
            "source_not_image",
            f"Completed job {job_id} has no image output.",
            "Choose a job that completed with an image artifact.",
        )

    status = get_job_status(job_id)
    if status is not None:
        raise _source_error(
            "source_not_successful",
            f"Generation job {job_id} is {status.get('status', 'unfinished')}.",
            "Wait for successful completion, then explicitly request the save again.",
            status_code=409,
        )
    raise _source_error(
        "source_not_found",
        f"Generation job {job_id} was not found.",
        "Use a completed generation job id or a successful Gallery image/artifact id.",
        status_code=404,
    )


def _validated_node_keys(workflow: dict[str, Any]) -> dict[str, str | int]:
    if not isinstance(workflow, dict) or not workflow:
        raise StylePresetWorkflowError(
            "invalid_workflow_graph",
            "The recorded workflow is not a nonempty ComfyUI API graph.",
            "Choose a successful source with a valid recorded API workflow.",
        )
    keys: dict[str, str | int] = {}
    for node_id, node in workflow.items():
        if (
            not isinstance(node, dict)
            or not isinstance(node.get("class_type"), str)
            or not isinstance(node.get("inputs"), dict)
        ):
            raise StylePresetWorkflowError(
                "invalid_workflow_graph",
                f"Workflow node {node_id!s} is not a valid ComfyUI API node.",
                "Choose a source whose workflow nodes contain class_type and inputs.",
            )
        keys[str(node_id)] = node_id
    return keys


def validate_workflow_graph(workflow: object) -> dict[str, Any]:
    """Require the strict node-object shape persisted by ComfyUI's API."""
    if not isinstance(workflow, dict):
        raise StylePresetWorkflowError(
            "invalid_workflow_graph",
            "The saved workflow is not a JSON object.",
            "Save a valid successful ComfyUI API workflow again.",
        )
    _validated_node_keys(workflow)
    return workflow


def _linked_node_id(
    value: object, node_keys: dict[str, str | int]
) -> str | int | None:
    linked = _linked_output(value, node_keys)
    return linked[0] if linked is not None else None


def _linked_output(
    value: object, node_keys: dict[str, str | int]
) -> tuple[str | int, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], (str, int))
        and isinstance(value[1], int)
    ):
        node_id = node_keys.get(str(value[0]))
        if node_id is not None:
            return node_id, value[1]
    return None


def _reachable_text_nodes(
    workflow: dict[str, Any],
    start: object,
    node_keys: dict[str, str | int],
) -> set[str | int]:
    first = _linked_node_id(start, node_keys)
    if first is None:
        return set()
    pending = [first]
    visited: set[str | int] = set()
    text_nodes: set[str | int] = set()
    while pending:
        node_id = pending.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        node = workflow[node_id]
        if node["class_type"] == "CLIPTextEncode":
            text_nodes.add(node_id)
            continue
        for input_value in node["inputs"].values():
            upstream = _linked_node_id(input_value, node_keys)
            if upstream is not None and upstream not in visited:
                pending.append(upstream)
    return text_nodes


def _prompt_confidentiality_error(message: str) -> StylePresetWorkflowError:
    return StylePresetWorkflowError(
        "prompt_confidentiality_unproven",
        message,
        (
            "Use a graph whose conditioning text is stored directly or in an "
            "exclusive Primitive/String carrier, with no exact source-prompt copies elsewhere."
        ),
    )


def _link_consumers(
    workflow: dict[str, Any],
    node_keys: dict[str, str | int],
) -> dict[str | int, set[tuple[str | int, str]]]:
    consumers: dict[str | int, set[tuple[str | int, str]]] = {}
    for consumer_id, node in workflow.items():
        for input_name, input_value in node["inputs"].items():
            linked = _linked_output(input_value, node_keys)
            if linked is None:
                continue
            linked_node_id, _output_index = linked
            consumers.setdefault(linked_node_id, set()).add(
                (consumer_id, input_name)
            )
    return consumers


def _replace_conditioning_text(
    workflow: dict[str, Any],
    positive_nodes: set[str | int],
    negative_nodes: set[str | int],
    positive_text: str,
    negative_text: str,
    node_keys: dict[str, str | int],
) -> None:
    desired_by_node = {
        **{node_id: positive_text for node_id in positive_nodes},
        **{node_id: negative_text for node_id in negative_nodes},
    }
    consumers = _link_consumers(workflow, node_keys)
    carrier_replacements: dict[str | int, set[str]] = {}
    carrier_targets: dict[str | int, set[tuple[str | int, str]]] = {}

    for node_id, desired_text in desired_by_node.items():
        text_input = workflow[node_id]["inputs"].get("text")
        if isinstance(text_input, str):
            workflow[node_id]["inputs"]["text"] = desired_text
            continue

        linked = _linked_output(text_input, node_keys)
        if linked is None:
            raise _prompt_confidentiality_error(
                "A sampler-linked CLIPTextEncode text input cannot be replaced safely."
            )
        carrier_id, _output_index = linked
        carrier = workflow[carrier_id]
        allowed_fields = _SAFE_LINKED_TEXT_CARRIER_FIELDS.get(
            carrier["class_type"]
        )
        if allowed_fields is None:
            raise _prompt_confidentiality_error(
                "A linked conditioning-text carrier is not a supported Primitive/String node."
            )
        string_fields = [
            field
            for field in allowed_fields
            if isinstance(carrier["inputs"].get(field), str)
        ]
        if len(string_fields) != 1:
            raise _prompt_confidentiality_error(
                "A linked conditioning-text carrier has no unambiguous string value."
            )
        carrier_replacements.setdefault(carrier_id, set()).add(desired_text)
        carrier_targets.setdefault(carrier_id, set()).add((node_id, "text"))

    for carrier_id, desired_texts in carrier_replacements.items():
        if len(desired_texts) != 1:
            raise StylePresetWorkflowError(
                "ambiguous_conditioning",
                "The same linked text carrier feeds both prompt polarities.",
                "Choose a graph with separate positive and negative text carriers.",
            )
        if consumers.get(carrier_id, set()) != carrier_targets[carrier_id]:
            raise _prompt_confidentiality_error(
                "A linked conditioning-text carrier also feeds a non-target input."
            )
        carrier = workflow[carrier_id]
        allowed_fields = _SAFE_LINKED_TEXT_CARRIER_FIELDS[
            carrier["class_type"]
        ]
        field = next(
            name
            for name in allowed_fields
            if isinstance(carrier["inputs"].get(name), str)
        )
        carrier["inputs"][field] = next(iter(desired_texts))


def _contains_exact_prompt(value: object, evidence: set[str]) -> bool:
    if isinstance(value, str):
        return any(prompt in value for prompt in evidence)
    if isinstance(value, dict):
        return any(
            _contains_exact_prompt(key, evidence)
            or _contains_exact_prompt(item, evidence)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_exact_prompt(item, evidence) for item in value)
    return False


def _target_conditioning_text_evidence(
    workflow: dict[str, Any],
    target_nodes: set[str | int],
    node_keys: dict[str, str | int],
) -> set[str]:
    """Collect trusted pre-mutation text from proven target conditioning inputs."""
    evidence: set[str] = set()
    for node_id in target_nodes:
        text_input = workflow[node_id]["inputs"].get("text")
        if isinstance(text_input, str):
            if text_input:
                evidence.add(text_input)
            continue
        linked = _linked_output(text_input, node_keys)
        if linked is None:
            continue
        carrier_id, _output_index = linked
        carrier = workflow[carrier_id]
        for field in _SAFE_LINKED_TEXT_CARRIER_FIELDS.get(
            carrier["class_type"], ()
        ):
            value = carrier["inputs"].get(field)
            if isinstance(value, str) and value:
                evidence.add(value)
    return evidence


def _workflow_without_target_conditioning_text(
    workflow: dict[str, Any],
    target_nodes: set[str | int],
    node_keys: dict[str, str | int],
) -> dict[str, Any]:
    """Blank only proven conditioning carriers before leak detection.

    A caller may intentionally save keywords that are identical to the source
    prompt. Those values are legitimate in sampler-linked target carriers;
    exact copies anywhere else in the graph still fail closed.
    """
    evidence_graph: Any = copy.deepcopy(workflow)
    for node_id in target_nodes:
        text_input = evidence_graph[node_id]["inputs"].get("text")
        if isinstance(text_input, str):
            evidence_graph[node_id]["inputs"]["text"] = ""
            continue
        linked = _linked_output(text_input, node_keys)
        if linked is None:
            continue
        carrier_id, _output_index = linked
        carrier = evidence_graph[carrier_id]
        for field in _SAFE_LINKED_TEXT_CARRIER_FIELDS.get(
            carrier["class_type"], ()
        ):
            if isinstance(carrier["inputs"].get(field), str):
                carrier["inputs"][field] = ""
    return evidence_graph


def sanitize_workflow_prompts(
    workflow: dict[str, Any],
    positive: str | list[str] | None,
    negative: str | list[str] | None,
    *,
    source_prompt: str | None = None,
    source_negative_prompt: str | None = None,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Deep-copy a graph and replace only sampler-reachable text encoders."""
    positive_keywords = normalize_keywords(positive)
    negative_keywords = normalize_keywords(negative)
    if not positive_keywords:
        raise StylePresetWorkflowError(
            "positive_keywords_required",
            "At least one positive style keyword is required.",
            "Provide compact positive keywords selected for the saved preset.",
        )

    sanitized = copy.deepcopy(workflow)
    node_keys = _validated_node_keys(sanitized)
    positive_nodes: set[str | int] = set()
    negative_nodes: set[str | int] = set()

    for node in sanitized.values():
        if node["class_type"] not in _SAMPLER_CLASS_TYPES:
            continue
        inputs = node["inputs"]
        if "positive" in inputs:
            reachable = _reachable_text_nodes(
                sanitized, inputs["positive"], node_keys
            )
            if not reachable:
                raise StylePresetWorkflowError(
                    "conditioning_not_found",
                    "A sampler positive input has no reachable CLIPTextEncode node.",
                    "Use a supported successful graph with link-based positive conditioning.",
                )
            positive_nodes.update(reachable)
        if "negative" in inputs:
            reachable = _reachable_text_nodes(
                sanitized, inputs["negative"], node_keys
            )
            if not reachable:
                raise StylePresetWorkflowError(
                    "conditioning_not_found",
                    "A sampler negative input has no reachable CLIPTextEncode node.",
                    "Use a supported successful graph with link-based negative conditioning.",
                )
            negative_nodes.update(reachable)

    if not positive_nodes:
        raise StylePresetWorkflowError(
            "conditioning_not_found",
            "No positive sampler-linked CLIPTextEncode node was found.",
            "Use a successful KSampler or KSamplerAdvanced API graph with linked conditioning.",
        )
    if positive_nodes & negative_nodes:
        raise StylePresetWorkflowError(
            "ambiguous_conditioning",
            "The same CLIPTextEncode node feeds both positive and negative conditioning.",
            "Choose a graph with separate positive and negative text encoders.",
        )

    positive_prompt_evidence = _target_conditioning_text_evidence(
        sanitized, positive_nodes, node_keys
    )
    negative_prompt_evidence = _target_conditioning_text_evidence(
        sanitized, negative_nodes, node_keys
    )
    if source_prompt is None and not positive_prompt_evidence:
        raise _prompt_confidentiality_error(
            "Positive source-prompt evidence is missing from both the record and target conditioning."
        )
    if source_negative_prompt is None and not negative_prompt_evidence:
        raise _prompt_confidentiality_error(
            "Negative source-prompt evidence is missing from both the record and target conditioning."
        )

    target_nodes = positive_nodes | negative_nodes
    prompt_evidence = positive_prompt_evidence | negative_prompt_evidence
    prompt_evidence.update(
        value
        for value in (source_prompt, source_negative_prompt)
        if isinstance(value, str) and value
    )

    positive_text = ", ".join(positive_keywords)
    negative_text = ", ".join(negative_keywords)
    _replace_conditioning_text(
        sanitized,
        positive_nodes,
        negative_nodes,
        positive_text,
        negative_text,
        node_keys,
    )
    evidence_graph = _workflow_without_target_conditioning_text(
        sanitized,
        target_nodes,
        node_keys,
    )
    if _contains_exact_prompt(evidence_graph, prompt_evidence):
        raise _prompt_confidentiality_error(
            "The sanitized workflow still contains exact source-prompt text."
        )
    return sanitized, positive_keywords, negative_keywords


def _validated_target(
    provider: DirStylePresetProvider,
    preset_id: str,
    profile: str | None,
) -> tuple[str, str | None]:
    preset = provider.get_preset(preset_id)
    if preset is None:
        raise StylePresetWorkflowError(
            "preset_not_found",
            f"Style preset {preset_id} was not found.",
            "Choose an id returned by list_style_presets.",
            status_code=404,
        )
    if not is_valid_preset_id(preset.id):
        raise StylePresetWorkflowError(
            "preset_not_found",
            f"Style preset {preset_id} does not have a safe canonical id.",
            "Repair the preset id before saving a workflow.",
            status_code=404,
        )
    if profile is not None:
        if profile not in preset.profiles:
            raise StylePresetWorkflowError(
                "profile_not_found",
                f"Style preset {preset_id} has no profile {profile}.",
                f"Use one of: {preset.profile_names}.",
                status_code=404,
            )
        if not is_valid_preset_id(profile):
            raise StylePresetWorkflowError(
                "profile_not_found",
                f"Style preset profile {profile} cannot be used as a workflow filename.",
                "Use a profile with a slug-safe name.",
                status_code=404,
            )
    return preset.id, profile


def workflow_path_for(
    provider: DirStylePresetProvider,
    preset_id: str,
    profile: str | None,
) -> Path:
    """Derive the conventional server-owned workflow path."""
    canonical_preset, canonical_profile = _validated_target(
        provider, preset_id, profile
    )
    filename = (
        f"{canonical_profile}.api.json"
        if canonical_profile is not None
        else "__base__.api.json"
    )
    target = (
        provider.agent_dir
        / "workflows"
        / canonical_preset
        / filename
    )
    workflows_root = (provider.agent_dir / "workflows").resolve()
    try:
        target.resolve().relative_to(workflows_root)
    except ValueError as exc:
        raise StylePresetWorkflowError(
            "invalid_workflow_graph",
            "The derived workflow path escaped the preset workflow root.",
            "Repair the preset/profile identifiers before saving.",
        ) from exc
    return target


def _relative_workflow_path(
    provider: DirStylePresetProvider, path: Path
) -> str:
    project_root = provider.project_root or provider.agent_dir.parent.parent
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError as exc:
        raise StylePresetWorkflowError(
            "invalid_workflow_graph",
            "The preset workflow root is outside the configured project.",
            "Configure the style preset provider under the project root.",
        ) from exc


def _atomic_write_raw_graph(path: Path, workflow: dict[str, Any]) -> None:
    validate_workflow_graph(workflow)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(workflow, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            with temporary_path.open(encoding="utf-8") as stream:
                parsed = json.load(stream)
            validate_workflow_graph(parsed)
        except StylePresetWorkflowError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise StylePresetWorkflowError(
                "invalid_workflow_graph",
                "The temporary workflow file failed JSON parse-back validation.",
                "Retry the explicit save from the successful source.",
            ) from exc
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def save_successful_workflow(
    session: Session,
    provider: DirStylePresetProvider,
    *,
    preset_id: str,
    profile: str | None,
    source: int | str,
    prompt_keywords: str | list[str] | None,
    negative_prompt_keywords: str | list[str] | None,
) -> SavedWorkflow:
    """Resolve, sanitize, validate, and atomically publish one proven graph."""
    target = workflow_path_for(provider, preset_id, profile)
    resolved = resolve_successful_workflow(session, source)
    sanitized, positive, negative = sanitize_workflow_prompts(
        resolved.workflow,
        prompt_keywords,
        negative_prompt_keywords,
        source_prompt=resolved.source_prompt,
        source_negative_prompt=resolved.source_negative_prompt,
    )
    _atomic_write_raw_graph(target, sanitized)
    return SavedWorkflow(
        preset_id=preset_id,
        profile=profile,
        source_type=resolved.source_type,
        source_id=resolved.source_id,
        workflow_path=_relative_workflow_path(provider, target),
        prompt_keywords=positive,
        negative_prompt_keywords=negative,
    )


def load_saved_workflow(
    provider: DirStylePresetProvider,
    preset_id: str,
    profile: str | None,
) -> dict[str, Any]:
    """Read a conventional saved workflow as its raw graph object."""
    target = workflow_path_for(provider, preset_id, profile)
    if not target.is_file():
        raise StylePresetWorkflowError(
            "saved_workflow_not_found",
            f"No saved workflow exists for preset {preset_id} profile {profile or '__base__'}.",
            "Explicitly save a successful generation workflow first.",
            status_code=404,
        )
    try:
        with target.open(encoding="utf-8") as stream:
            graph = json.load(stream)
        return copy.deepcopy(validate_workflow_graph(graph))
    except StylePresetWorkflowError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise StylePresetWorkflowError(
            "invalid_workflow_graph",
            f"Saved workflow {target.name} is not valid JSON.",
            "Explicitly save a successful generation workflow again.",
        ) from exc
