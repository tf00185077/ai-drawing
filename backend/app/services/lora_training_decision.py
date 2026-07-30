"""Deterministic, side-effect-free LoRA training decision preflight."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.schemas.lora_train import (
    ComponentIdentity,
    RecipeCompilationContext,
    RecipePolicySnapshot,
    TrainerCapabilitySnapshot,
    TrainingDecisionPreflightResponse,
    TrainingParameterSuggestion,
    TrainingStartPayload,
    ValidationIssue,
)
from app.services import (
    file_digest_cache,
    lora_dataset,
    lora_dataset_assessment,
    lora_dataset_curation,
    lora_trainer,
)
from app.services.lora_training_recipe import (
    NormalizedRecipeInput,
    RecipeError,
    compile_training_recipe,
    normalize_recipe_input,
)

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


def _configured_precision(settings: Any) -> str:
    value = str(_setting(settings, "lora_mixed_precision", "no") or "no").strip().lower()
    if value == "fp32":
        return "no"
    return value if value in {"no", "fp16", "bf16"} else "no"


def _component_identity(
    *,
    kind: str,
    requested_locator: str | None,
    model_family: str,
    allow_unverified: bool,
    settings: Any,
) -> ComponentIdentity:
    if not requested_locator:
        return lora_trainer.collect_component_identity(
            kind=kind,
            requested_locator=None,
            resolved_path=None,
            allow_unverified=allow_unverified,
            digest_resolver=file_digest_cache.sha256_for,
        )
    if (
        not lora_trainer._is_local_path(requested_locator)
        and not lora_trainer._is_bare_filename(requested_locator)
    ):
        return ComponentIdentity(
            kind=kind,
            requested_locator=requested_locator,
            resolved_locator=requested_locator,
            verification_status="unverified",
            reason="remote component identity is not locally verifiable",
            bypass_used=False,
        )
    if kind == "checkpoint":
        search_dirs = lora_trainer._checkpoint_search_dirs(
            settings,
            model_family,
        )
    elif kind in {"text_encoder", "tokenizer"}:
        search_dirs = lora_trainer._dir_candidates(
            _setting(settings, "comfyui_text_encoders_dir", "")
        )
    elif kind == "vae":
        search_dirs = lora_trainer._dir_candidates(
            _setting(settings, "comfyui_vae_dir", "")
        )
    else:
        search_dirs = []
    resolved_locator = lora_trainer._resolve_model_file(
        requested_locator,
        search_dirs,
    )
    candidate = Path(resolved_locator).expanduser()
    return lora_trainer.collect_component_identity(
        kind=kind,
        requested_locator=requested_locator,
        resolved_path=candidate,
        allow_unverified=allow_unverified,
        digest_resolver=file_digest_cache.sha256_for,
    )


def build_recipe_compilation_context(
    inspected: Any,
    normalized: NormalizedRecipeInput,
    *,
    approved_trigger_token: str | None = None,
    settings: Any | None = None,
    capability: TrainerCapabilitySnapshot | None = None,
) -> RecipeCompilationContext:
    """Snapshot all policy and evidence inputs shared by preflight and Start."""
    active_settings = settings or lora_dataset.get_settings()
    profile_hash = inspected.profile_hash
    trigger_token = approved_trigger_token or inspected.profile.trigger_token
    if not profile_hash or not trigger_token:
        raise RecipeError(
            "recipe_context_unavailable",
            "approved dataset metadata is incomplete",
            "repair dataset metadata and rerun decision preflight",
            {
                "issues": [
                    {
                        "location": "dataset.profile",
                        "type": "required_value",
                    }
                ]
            },
        )
    model_family = inspected.profile.model_family
    requested_model = normalized.requested.model
    requested_anima = (
        requested_model.anima
        if requested_model is not None
        else None
    )
    checkpoint = (
        requested_model.checkpoint
        if requested_model is not None and requested_model.checkpoint
        else str(_setting(active_settings, "lora_default_checkpoint", "") or "")
    )
    allow_unverified = bool(
        requested_model is not None
        and requested_model.allow_unverified_checkpoint
    )
    qwen3 = (
        requested_anima.qwen3
        if requested_anima is not None and requested_anima.qwen3
        else _setting(active_settings, "lora_anima_qwen3", "") or None
    )
    vae = (
        requested_anima.vae
        if requested_anima is not None and requested_anima.vae
        else _setting(active_settings, "lora_anima_vae", "") or None
    )
    tokenizer = (
        requested_anima.t5_tokenizer_path
        if requested_anima is not None and requested_anima.t5_tokenizer_path
        else _setting(active_settings, "lora_anima_t5_tokenizer_path", "") or None
    )
    components: dict[str, ComponentIdentity] = {
        "checkpoint": _component_identity(
            kind="checkpoint",
            requested_locator=checkpoint or None,
            model_family=model_family,
            allow_unverified=allow_unverified,
            settings=active_settings,
        )
    }
    if model_family == "anima":
        components["text_encoder"] = _component_identity(
            kind="text_encoder",
            requested_locator=qwen3,
            model_family=model_family,
            allow_unverified=True,
            settings=active_settings,
        )
        if vae:
            components["vae"] = _component_identity(
                kind="vae",
                requested_locator=vae,
                model_family=model_family,
                allow_unverified=True,
                settings=active_settings,
            )
        if tokenizer:
            components["tokenizer"] = _component_identity(
                kind="tokenizer",
                requested_locator=tokenizer,
                model_family=model_family,
                allow_unverified=True,
                settings=active_settings,
            )
    trainer_python = str(
        _setting(active_settings, "sd_scripts_python", "") or ""
    ).strip()
    capability_snapshot = capability or (
        lora_trainer.inspect_trainer_capability(trainer_python)
        if trainer_python
        else TrainerCapabilitySnapshot(
            platform="unknown",
            status="unavailable",
            reason="trainer Python is not configured for capability inspection",
            supported_mixed_precision=("no",),
        )
    )
    try:
        policy = RecipePolicySnapshot(
            default_checkpoint=checkpoint,
            default_anima_qwen3=qwen3,
            default_anima_vae=vae,
            default_anima_t5_tokenizer_path=tokenizer,
            resolution=int(_setting(active_settings, "lora_resolution", 1024)),
            batch_size=int(_setting(active_settings, "lora_batch_size", 4)),
            learning_rate=str(
                _setting(active_settings, "lora_learning_rate", "1e-4")
            ),
            keep_tokens=int(_setting(active_settings, "lora_keep_tokens", 1)),
            num_repeats=int(_setting(active_settings, "lora_num_repeats", 10)),
            mixed_precision=_configured_precision(active_settings),
            network_dim=int(_setting(active_settings, "lora_network_dim", 32)),
            network_alpha=int(
                _setting(active_settings, "lora_network_alpha", 16)
            ),
        )
        return RecipeCompilationContext(
            dataset_hash=inspected.dataset_hash,
            profile_hash=profile_hash,
            profile_model_family=model_family,
            approved_trigger_token=lora_dataset.normalize_trigger_token(
                trigger_token
            ),
            image_count=inspected.image_count,
            policy=policy,
            capability=capability_snapshot,
            component_identities=components,
        )
    except (TypeError, ValueError):
        raise RecipeError(
            "server_recipe_policy_invalid",
            "server LoRA recipe policy is invalid",
            "correct the server LoRA settings and rerun preflight",
            {
                "issues": [
                    {
                        "location": "server_policy",
                        "type": "invalid_value",
                    }
                ]
            },
        ) from None


def _recipe_issue(error: RecipeError) -> ValidationIssue:
    return _issue(
        error.code,
        error.message,
        path="recipe",
        details={
            "hint": error.hint,
            **error.details,
        },
    )


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
    recipe: object | None = None,
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

    normalized_recipe = None
    requested_recipe_family = None
    try:
        normalized_recipe = normalize_recipe_input(
            recipe if recipe is not None else {},
            policy_source="preflight_policy",
        )
        requested_model = normalized_recipe.requested.model
        if requested_model is not None:
            requested_recipe_family = requested_model.family
    except RecipeError as exc:
        _add_issue(blocking, _recipe_issue(exc))

    family_matches_config = True
    if (
        requested_recipe_family is None
        and inspected.profile.valid
        and inspected.profile.model_family in _NETWORK_MODULE_BY_MODEL_FAMILY
    ):
        configured_model_family = _configured_model_family(lora_dataset.get_settings())
        if configured_model_family != inspected.profile.model_family:
            family_matches_config = False
            _add_issue(
                warnings,
                _issue(
                    "model_family_mismatch",
                    "configured model family does not match dataset profile",
                    details={
                        "configured_model_family": configured_model_family,
                        "dataset_profile_model_family": inspected.profile.model_family,
                    },
                ),
            )

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
    compiled = None
    policy_rationale: list[str] = []
    if (
        not blocking
        and not review_warnings
        and normalized_trigger
        and inspected.profile.present
        and inspected.profile.valid
        and inspected.profile_hash
        and inspected.profile.model_family in _NETWORK_MODULE_BY_MODEL_FAMILY
        and family_matches_config
        and normalized_recipe is not None
    ):
        try:
            context = build_recipe_compilation_context(
                inspected,
                normalized_recipe,
                approved_trigger_token=normalized_trigger,
            )
            compiled = compile_training_recipe(
                normalized_recipe,
                context=context,
                policy_source="preflight_policy",
            )
            policy_rationale = [
                (
                    f"approved profile family={compiled.effective.model.family} "
                    f"selects {compiled.effective.model.network_module}"
                ),
                (
                    f"capability platform={compiled.capability.platform} "
                    f"status={compiled.capability.status} selects "
                    f"batch={compiled.effective.dataset.batch_size} and "
                    f"mixed_precision={compiled.effective.optimization.mixed_precision}"
                ),
                (
                    f"image_count={inspected.image_count} selects "
                    f"epochs={compiled.effective.optimization.epochs} and "
                    f"total_optimizer_steps={compiled.step_plan.total_optimizer_steps}"
                ),
                "caller omissions remain omitted in requested_recipe and are visible through field_sources",
            ]
        except RecipeError as exc:
            _add_issue(blocking, _recipe_issue(exc))

    review_warnings = [
        warning for warning in warnings if warning.code not in _INFO_ONLY_WARNING_CODES
    ]
    if blocking:
        decision = "do_not_train"
    elif review_warnings:
        decision = "needs_review"
    elif compiled is None:
        decision = "needs_review"
        _add_issue(
            warnings,
            _issue(
                "recipe_preview_unavailable",
                "a canonical training recipe preview could not be produced",
            ),
        )
        review_warnings = [
            warning
            for warning in warnings
            if warning.code not in _INFO_ONLY_WARNING_CODES
        ]
    else:
        decision = "train"

    for issue in [*blocking, *review_warnings]:
        _add_unique(next_actions, _next_action_for_issue(issue))
    if decision == "train":
        _add_unique(
            next_actions,
            "Ask the user for explicit approval, then submit start_payload exactly to lora_train_start.",
        )
    elif decision == "needs_review":
        _add_unique(next_actions, "Resolve review items, then rerun decision preflight before starting training.")
    else:
        _add_unique(next_actions, "Do not call lora_train_start until blocking issues are resolved.")

    start_payload = None
    suggested_params = None
    if decision == "train" and compiled is not None and inspected.profile_hash:
        payload_recipe = compiled.requested.model_copy(
            update={"expected_recipe_hash": compiled.recipe_hash}
        )
        start_payload = TrainingStartPayload(
            folder=inspected.folder,
            expected_dataset_hash=inspected.dataset_hash,
            expected_profile_hash=inspected.profile_hash,
            recipe=payload_recipe,
        )
        suggested_params = TrainingParameterSuggestion(
            params=start_payload.model_dump(mode="json"),
            rationale=policy_rationale,
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
        requested_recipe=compiled.requested if compiled is not None else None,
        effective_recipe=compiled.effective if compiled is not None else None,
        requested_scope=(
            compiled.requested.scope if compiled is not None else None
        ),
        effective_scope=(
            compiled.effective.scope if compiled is not None else None
        ),
        field_sources=(
            dict(compiled.field_sources) if compiled is not None else None
        ),
        step_plan=compiled.step_plan if compiled is not None else None,
        component_identities=(
            dict(compiled.component_identities)
            if compiled is not None
            else None
        ),
        capability=compiled.capability if compiled is not None else None,
        execution_evidence=(
            compiled.execution_evidence if compiled is not None else None
        ),
        recipe_hash=compiled.recipe_hash if compiled is not None else None,
        policy_rationale=policy_rationale,
        start_payload=start_payload,
        suggested_params=suggested_params,
    )
