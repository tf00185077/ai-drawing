"""Deterministic, side-effect-free LoRA training decision preflight."""
from __future__ import annotations

from typing import Any

from app.schemas.lora_train import (
    TrainingDecisionPreflightResponse,
    TrainingParameterSuggestion,
    ValidationIssue,
)
from app.services import lora_dataset, lora_dataset_assessment, lora_dataset_curation

_NETWORK_MODULE_BY_MODEL_FAMILY = {
    "sd15": "networks.lora",
    "sdxl": "networks.lora",
    "anima": "networks.lora_anima",
}
_INFO_ONLY_WARNING_CODES = {"auto_train_descriptive_only"}


def _issue(
    code: str,
    message: str,
    *,
    path: str | None = None,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, path=path, details=details)


def _add_issue(items: list[ValidationIssue], issue: ValidationIssue) -> None:
    key = (issue.code, issue.path, issue.message)
    if key not in {(item.code, item.path, item.message) for item in items}:
        items.append(issue)


def _extend_issues(items: list[ValidationIssue], issues: list[ValidationIssue]) -> None:
    for issue in issues:
        _add_issue(items, issue)


def _add_unique(items: list[str], value: str | None) -> None:
    if value and value not in items:
        items.append(value)


def _setting(settings: Any, name: str, default: Any) -> Any:
    return getattr(settings, name, default)


def _configured_model_family(settings: Any) -> str:
    configured = str(_setting(settings, "lora_model_family", "") or "").strip().lower()
    if configured in {"sd15", "sdxl", "anima"}:
        return configured
    return "sdxl" if bool(_setting(settings, "lora_sdxl", False)) else "sd15"


def _suggest_params(
    *,
    folder: str,
    dataset_hash: str,
    image_count: int,
    profile: Any,
    normalized_trigger_token: str,
) -> TrainingParameterSuggestion | None:
    metadata_ready = (
        profile.present
        and profile.valid
        and profile.dataset_type != "unknown"
        and profile.caption_profile != "unknown"
        and profile.model_family != "unknown"
    )
    if not metadata_ready:
        return None

    settings = lora_dataset.get_settings()
    model_family = profile.model_family
    params: dict[str, Any] = {
        "folder": folder,
        "trigger_token": normalized_trigger_token,
        "expected_dataset_hash": dataset_hash,
        "checkpoint": _setting(settings, "lora_default_checkpoint", "") or None,
        "model_family": model_family,
        "sdxl": model_family == "sdxl",
        "epochs": 12 if image_count < 12 else 10 if image_count <= 40 else 8,
        "resolution": int(_setting(settings, "lora_resolution", 1024)),
        "batch_size": int(_setting(settings, "lora_batch_size", 4)),
        "learning_rate": str(_setting(settings, "lora_learning_rate", "1e-4")),
        "class_tokens": normalized_trigger_token,
        "keep_tokens": int(_setting(settings, "lora_keep_tokens", 1)),
        "num_repeats": int(_setting(settings, "lora_num_repeats", 10)),
        "mixed_precision": str(_setting(settings, "lora_mixed_precision", "fp16")),
        "network_module": _NETWORK_MODULE_BY_MODEL_FAMILY[model_family],
        "network_dim": int(_setting(settings, "lora_network_dim", 32)),
        "network_alpha": int(_setting(settings, "lora_network_alpha", 16)),
    }
    if model_family == "anima":
        params["anima_qwen3"] = _setting(settings, "lora_anima_qwen3", "") or None
        params["anima_vae"] = _setting(settings, "lora_anima_vae", "") or None
        params["anima_t5_tokenizer_path"] = (
            _setting(settings, "lora_anima_t5_tokenizer_path", "") or None
        )

    rationale = [
        f"profile model_family={model_family} selects {params['network_module']}",
        f"dataset_type={profile.dataset_type} and caption_profile={profile.caption_profile} provide enough metadata",
        f"image_count={image_count} selects epochs={params['epochs']}",
        "suggested parameters are advisory; lora_train_start must still validate dataset hash and params",
    ]
    return TrainingParameterSuggestion(params=params, rationale=rationale)


def _next_action_for_issue(issue: ValidationIssue) -> str:
    code = issue.code
    if code in {"dataset_hash_mismatch", "profile_hash_mismatch"}:
        return "Re-inspect the dataset and rerun decision preflight with current hashes."
    if code in {
        "invalid_profile_json",
        "invalid_profile_schema",
        "invalid_profile_field",
        "unsupported_dataset_type",
        "unsupported_caption_profile",
        "unsupported_model_family",
        "dataset_type_unknown",
        "caption_profile_unknown",
        "model_family_unknown",
        "metadata_profile_missing",
    }:
        return "Fix or create .lora-dataset.json, then rerun lora_dataset_metadata_validate and decision preflight."
    if code in {"insufficient_images", "no_images"}:
        return "Add more supported training images with matching captions before training."
    if code in {"missing_caption", "missing_txt", "empty_caption", "empty_txt"}:
        return "Add or fill same-name .txt captions, then rerun caption assessment and validation."
    if code in {"missing_trigger_token", "low_trigger_coverage", "trigger_token_missing"}:
        return "Choose a trigger token and curate captions so the token appears consistently."
    if code == "dataset_locked":
        return "Wait for the active dataset operation to finish, then rerun decision preflight."
    if code in {"curation_review_required", "curation_changes_available"}:
        return "Review lora_dataset_curate dry-run output and apply reviewed curation with expected hashes if appropriate."
    if code == "curation_outliers_detected":
        return "Inspect curation outlier flags and approve or edit captions before training."
    if code in {"over_fragmented_tags", "insufficient_repeated_tags", "low_caption_overlap"}:
        return "Review captions for stable repeated identity/style tags before training."
    return "Review the reported issue, resolve it, then rerun decision preflight."


def _metadata_checks(inspected: Any, warnings: list[ValidationIssue], blocking: list[ValidationIssue]) -> None:
    profile = inspected.profile
    if not profile.present:
        _add_issue(
            warnings,
            _issue(
                "metadata_profile_missing",
                "metadata profile is missing",
                details={"folder": inspected.folder},
            ),
        )
    if not profile.valid:
        _extend_issues(blocking, profile.errors)
    _extend_issues(warnings, profile.warnings)
    if profile.valid:
        if profile.dataset_type == "unknown":
            _add_issue(warnings, _issue("dataset_type_unknown", "metadata dataset_type is unknown"))
        if profile.caption_profile == "unknown":
            _add_issue(warnings, _issue("caption_profile_unknown", "metadata caption_profile is unknown"))
        if profile.model_family == "unknown":
            _add_issue(warnings, _issue("model_family_unknown", "metadata model_family is unknown"))


def _resolve_trigger_token(inspected: Any, requested: str | None) -> str | None:
    raw = requested or inspected.profile.trigger_token
    if not raw and inspected.trigger_token_candidates:
        raw = inspected.trigger_token_candidates[0]
    return lora_dataset.normalize_trigger_token(raw) if raw else None


def decide_training_preflight(
    folder: str,
    *,
    trigger_token: str | None = None,
    expected_dataset_hash: str | None = None,
    expected_profile_hash: str | None = None,
) -> TrainingDecisionPreflightResponse:
    """Return a deterministic train/review/do-not-train assessment without writes or queues."""
    inspected = lora_dataset.inspect_dataset(folder)
    normalized_trigger = _resolve_trigger_token(inspected, trigger_token)
    reasons: list[str] = []
    blocking: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    next_actions: list[str] = []

    _metadata_checks(inspected, warnings, blocking)
    if inspected.profile.valid:
        _add_unique(reasons, "metadata profile is structurally valid")
    else:
        _add_unique(reasons, "metadata profile has blocking validation errors")

    if expected_profile_hash is not None and expected_profile_hash != inspected.profile_hash:
        _add_issue(
            blocking,
            _issue(
                "profile_hash_mismatch",
                "profile hash does not match expected hash",
                details={
                    "expected_profile_hash": expected_profile_hash,
                    "current_profile_hash": inspected.profile_hash,
                },
            ),
        )

    if not normalized_trigger:
        _add_issue(blocking, _issue("trigger_token_missing", "no trigger token could be resolved"))

    validation = None
    if normalized_trigger:
        validation = lora_dataset.validate_dataset(
            inspected.folder,
            trigger_token=normalized_trigger,
            expected_dataset_hash=expected_dataset_hash,
        )
        if validation.ok:
            _add_unique(reasons, "dataset validation passed")
        else:
            _add_unique(reasons, "dataset validation found blocking issues")
        _extend_issues(blocking, validation.errors)
        _extend_issues(warnings, validation.warnings)
    elif expected_dataset_hash is not None and expected_dataset_hash != inspected.dataset_hash:
        _add_issue(
            blocking,
            _issue(
                "dataset_hash_mismatch",
                "dataset hash does not match expected hash",
                details={
                    "expected_dataset_hash": expected_dataset_hash,
                    "current_dataset_hash": inspected.dataset_hash,
                },
            ),
        )

    caption_assessment = lora_dataset_assessment.assess_caption_suitability(
        inspected.folder,
        trigger_token=normalized_trigger,
    )
    if caption_assessment.verdict == "suitable":
        _add_unique(reasons, "caption assessment is suitable")
    elif caption_assessment.verdict == "needs_review":
        _add_unique(reasons, "caption assessment needs review")
        _extend_issues(warnings, caption_assessment.warnings)
    else:
        _add_unique(reasons, "caption assessment is not suitable for training")
        _extend_issues(blocking, caption_assessment.warnings)
    for recommendation in caption_assessment.recommendations:
        _add_unique(next_actions, recommendation)

    curation_plan = lora_dataset_curation.plan_curation(
        inspected.folder,
        trigger_token=normalized_trigger,
    )
    if curation_plan.summary.blocked_count or curation_plan.summary.review_required_count:
        _add_issue(
            warnings,
            _issue(
                "curation_review_required",
                "curation dry-run has changes requiring review",
                details=curation_plan.summary.model_dump(),
            ),
        )
        _add_unique(reasons, "curation dry-run has review-required changes")
    if curation_plan.summary.outlier_count:
        _add_issue(
            warnings,
            _issue(
                "curation_outliers_detected",
                "curation dry-run flagged caption outliers",
                details=curation_plan.summary.model_dump(),
            ),
        )
        _add_unique(reasons, "curation dry-run flagged caption outliers")
    if curation_plan.summary.changed_count:
        _add_issue(
            warnings,
            _issue(
                "curation_changes_available",
                "curation dry-run found deterministic caption cleanup changes",
                details=curation_plan.summary.model_dump(),
            ),
        )
        _add_unique(reasons, "curation dry-run found caption cleanup changes")
    if not (
        curation_plan.summary.blocked_count
        or curation_plan.summary.review_required_count
        or curation_plan.summary.outlier_count
        or curation_plan.summary.changed_count
    ):
        _add_unique(reasons, "curation dry-run has no required changes")

    review_warnings = [
        warning for warning in warnings if warning.code not in _INFO_ONLY_WARNING_CODES
    ]
    if blocking:
        decision = "do_not_train"
    elif review_warnings:
        decision = "needs_review"
    else:
        decision = "train"

    for issue in [*blocking, *review_warnings]:
        _add_unique(next_actions, _next_action_for_issue(issue))
    if decision == "train":
        _add_unique(
            next_actions,
            "Ask the user for explicit approval, then call lora_train_start with suggested params and expected_dataset_hash.",
        )
    elif decision == "needs_review":
        _add_unique(next_actions, "Resolve review items, then rerun decision preflight before starting training.")
    else:
        _add_unique(next_actions, "Do not call lora_train_start until blocking issues are resolved.")

    suggested_params = None
    if decision in {"train", "needs_review"} and normalized_trigger:
        suggested_params = _suggest_params(
            folder=inspected.folder,
            dataset_hash=inspected.dataset_hash,
            image_count=inspected.image_count,
            profile=inspected.profile,
            normalized_trigger_token=normalized_trigger,
        )

    return TrainingDecisionPreflightResponse(
        folder=inspected.folder,
        decision=decision,
        reasons=reasons,
        blocking_issues=blocking,
        warnings=warnings,
        next_actions=next_actions,
        dataset_hash=inspected.dataset_hash,
        profile_hash=inspected.profile_hash,
        normalized_trigger_token=normalized_trigger,
        suggested_params=suggested_params,
    )
