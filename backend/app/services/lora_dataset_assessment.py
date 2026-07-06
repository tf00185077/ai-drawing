"""Deterministic LoRA dataset caption suitability assessment."""
from __future__ import annotations

from collections import Counter
from itertools import combinations

from app.schemas.lora_train import (
    CaptionAssessmentMetrics,
    CaptionTagStat,
    DatasetCaptionAssessmentResponse,
    TriggerTokenCoverage,
    ValidationIssue,
)
from app.services import lora_dataset


def _round(value: float) -> float:
    return round(value, 4)


def _parse_caption_tags(caption: str) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for part in caption.split(","):
        tag = part.strip().lower()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags


def _tag_stats(counter: Counter[str], denominator: int, *, limit: int | None = None) -> list[CaptionTagStat]:
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    if limit is not None:
        items = items[:limit]
    return [
        CaptionTagStat(
            tag=tag,
            count=count,
            coverage=_round(count / denominator) if denominator else 0.0,
        )
        for tag, count in items
    ]


def _mean_pairwise_jaccard(tag_sets: list[set[str]]) -> float:
    if len(tag_sets) < 2:
        return 1.0 if tag_sets else 0.0
    scores: list[float] = []
    for left, right in combinations(tag_sets, 2):
        union = left | right
        if not union:
            scores.append(0.0)
            continue
        scores.append(len(left & right) / len(union))
    return _round(sum(scores) / len(scores)) if scores else 0.0


def _resolve_trigger_token(requested: str | None) -> str | None:
    raw = (requested or "").strip()
    if not raw:
        settings = lora_dataset.get_settings()
        raw = (getattr(settings, "wd_trigger_word", "") or "").strip()
    return lora_dataset.normalize_trigger_token(raw) if raw else None


def _coverage_for_trigger(tag_sets: list[set[str]], trigger_token: str | None) -> TriggerTokenCoverage:
    total = len(tag_sets)
    if not trigger_token:
        return TriggerTokenCoverage(total_count=total)
    token = trigger_token.lower()
    covered = sum(1 for tags in tag_sets if token in tags)
    return TriggerTokenCoverage(
        normalized_trigger_token=trigger_token,
        covered_count=covered,
        total_count=total,
        coverage=_round(covered / total) if total else 0.0,
    )


def assess_caption_suitability(
    folder: str,
    *,
    trigger_token: str | None = None,
) -> DatasetCaptionAssessmentResponse:
    """Assess whether dataset captions are coherent enough for a useful training run."""
    inspected = lora_dataset.inspect_dataset(folder)
    normalized_trigger = _resolve_trigger_token(trigger_token)
    txt_count = sum(1 for item in inspected.files if item.has_caption)
    missing_txt_count = inspected.image_count - txt_count
    empty_txt_count = sum(1 for item in inspected.files if item.has_caption and not (item.caption or "").strip())

    tag_sets: list[set[str]] = []
    counter: Counter[str] = Counter()
    total_tag_count = 0
    for item in inspected.files:
        if not item.has_caption or not (item.caption or "").strip():
            continue
        tags = set(_parse_caption_tags(item.caption or ""))
        tag_sets.append(tags)
        counter.update(tags)
        total_tag_count += len(tags)

    non_empty_caption_count = len(tag_sets)
    unique_tag_count = len(counter)
    repeated_tag_count = sum(1 for count in counter.values() if count >= 2)
    rare_tag_count = sum(1 for count in counter.values() if count == 1)
    singleton_tag_ratio = _round(rare_tag_count / unique_tag_count) if unique_tag_count else 0.0
    repeated_tag_ratio = _round(repeated_tag_count / unique_tag_count) if unique_tag_count else 0.0
    average_tags_per_caption = _round(total_tag_count / non_empty_caption_count) if non_empty_caption_count else 0.0
    mean_pairwise_jaccard = _mean_pairwise_jaccard(tag_sets)

    metrics = CaptionAssessmentMetrics(
        total_tag_count=total_tag_count,
        unique_tag_count=unique_tag_count,
        repeated_tag_count=repeated_tag_count,
        rare_tag_count=rare_tag_count,
        singleton_tag_ratio=singleton_tag_ratio,
        repeated_tag_ratio=repeated_tag_ratio,
        average_tags_per_caption=average_tags_per_caption,
        mean_pairwise_jaccard=mean_pairwise_jaccard,
    )
    top_tags = _tag_stats(counter, non_empty_caption_count, limit=20)
    if normalized_trigger:
        top_tags.sort(key=lambda stat: (stat.tag != normalized_trigger.lower(), -stat.count, stat.tag))
    rare_tags = _tag_stats(Counter({tag: count for tag, count in counter.items() if count == 1}), non_empty_caption_count, limit=30)
    trigger_coverage = _coverage_for_trigger(tag_sets, normalized_trigger)

    warnings: list[ValidationIssue] = []
    recommendations: list[str] = []
    reasons: list[str] = []

    if inspected.image_count == 0:
        reasons.append("dataset has no trainable images")
        warnings.append(ValidationIssue(code="no_images", message="dataset has no trainable images"))
        recommendations.append("Add supported image files before assessing or training this dataset.")
    if missing_txt_count:
        reasons.append(f"{missing_txt_count} image(s) are missing .txt captions")
        warnings.append(
            ValidationIssue(
                code="missing_txt",
                message="one or more images are missing same-name .txt captions",
                details={"missing_txt_count": missing_txt_count},
            )
        )
        recommendations.append("Generate or write same-name .txt captions for every image before training.")
    if empty_txt_count:
        reasons.append(f"{empty_txt_count} caption file(s) are empty")
        warnings.append(
            ValidationIssue(
                code="empty_txt",
                message="one or more caption files are empty",
                details={"empty_txt_count": empty_txt_count},
            )
        )
        recommendations.append("Fill empty caption files with coherent trigger and descriptive tags.")
    if normalized_trigger and trigger_coverage.total_count and trigger_coverage.coverage < 0.8:
        reasons.append(
            f"trigger token coverage is {trigger_coverage.coverage:.2f}; expected at least 0.80"
        )
        warnings.append(
            ValidationIssue(
                code="low_trigger_coverage",
                message="trigger token coverage is below the recommended threshold",
                details=trigger_coverage.model_dump(),
            )
        )
        recommendations.append("Add the normalized trigger token to most captions or choose a token already used consistently.")

    if non_empty_caption_count >= 3 and unique_tag_count:
        if singleton_tag_ratio > 0.65:
            reasons.append("captions are dominated by one-off tags")
            warnings.append(
                ValidationIssue(
                    code="over_fragmented_tags",
                    message="too many tags appear only once across the dataset",
                    details={"singleton_tag_ratio": singleton_tag_ratio, "rare_tag_count": rare_tag_count},
                )
            )
            recommendations.append("Reduce scattered one-off tags and keep repeated identity/style tags across images.")
        if repeated_tag_count < 3:
            reasons.append("too few tags repeat across captions")
            warnings.append(
                ValidationIssue(
                    code="insufficient_repeated_tags",
                    message="too few tags repeat across captions to define a stable identity or style",
                    details={"repeated_tag_count": repeated_tag_count},
                )
            )
            recommendations.append("Ensure several identity/style tags are repeated across the dataset.")
        if mean_pairwise_jaccard < 0.15:
            reasons.append("caption tag sets have low pairwise overlap")
            warnings.append(
                ValidationIssue(
                    code="low_caption_overlap",
                    message="caption tag sets have low pairwise overlap",
                    details={"mean_pairwise_jaccard": mean_pairwise_jaccard},
                )
            )

    if inspected.image_count == 0 or missing_txt_count or empty_txt_count:
        verdict = "not_suitable"
    elif warnings:
        verdict = "needs_review"
    else:
        verdict = "suitable"

    return DatasetCaptionAssessmentResponse(
        folder=inspected.folder,
        verdict=verdict,
        reasons=reasons,
        dataset_hash=inspected.dataset_hash,
        image_count=inspected.image_count,
        txt_count=txt_count,
        missing_txt_count=missing_txt_count,
        empty_txt_count=empty_txt_count,
        trigger_token_coverage=trigger_coverage,
        top_tags=top_tags,
        rare_tags=rare_tags,
        metrics=metrics,
        warnings=warnings,
        recommendations=recommendations,
    )
