"""LoRA dataset caption suitability assessment tests."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import lora_dataset, lora_dataset_assessment


@pytest.fixture(autouse=True)
def reset_dataset_locks():
    lora_dataset._reset_locks_for_test()
    yield
    lora_dataset._reset_locks_for_test()


def _settings(base: Path, trigger_word: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        lora_train_dir=str(base),
        lora_train_threshold=2,
        wd_trigger_word=trigger_word,
    )


def _make_dataset(base: Path, captions: list[str | None]) -> Path:
    dataset = base / "character" / "miku"
    dataset.mkdir(parents=True)
    for index, caption in enumerate(captions, start=1):
        image = dataset / f"{index:02d}.png"
        image.write_bytes(b"not-empty")
        if caption is not None:
            image.with_suffix(".txt").write_text(caption, encoding="utf-8")
    return dataset


def test_assess_caption_suitability_reports_coherent_dataset_as_suitable(tmp_path: Path) -> None:
    """重複 identity/style tags 足夠且 trigger 覆蓋完整時為 suitable。"""
    base = tmp_path / "lora_train"
    _make_dataset(
        base,
        [
            "miku_token, blue hair, twintails, school uniform, smile",
            "miku_token, blue hair, twintails, school uniform, looking at viewer",
            "miku_token, blue hair, twintails, pleated skirt, smile",
            "miku_token, blue hair, twintails, school uniform, standing",
        ],
    )

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        result = lora_dataset_assessment.assess_caption_suitability("character/miku", trigger_token="miku_token")

    assert result.verdict == "suitable"
    assert result.image_count == 4
    assert result.txt_count == 4
    assert result.missing_txt_count == 0
    assert result.empty_txt_count == 0
    assert result.trigger_token_coverage.normalized_trigger_token == "miku_token"
    assert result.trigger_token_coverage.coverage == 1.0
    assert result.top_tags[0].tag == "miku_token"
    assert result.top_tags[0].count == 4
    assert result.metrics.repeated_tag_count >= 4
    assert result.warnings == []


def test_assess_caption_suitability_flags_scattered_one_off_tags(tmp_path: Path) -> None:
    """多數 tag 只出現一次時，agent 應看到 over-fragmented 警告。"""
    base = tmp_path / "lora_train"
    _make_dataset(
        base,
        [
            "miku_token, glass tower, sunset, orange dress",
            "miku_token, rainy alley, umbrella, neon sign",
            "miku_token, beach chair, striped towel, noon",
            "miku_token, library shelf, red scarf, candle",
        ],
    )

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        result = lora_dataset_assessment.assess_caption_suitability("character/miku", trigger_token="miku_token")

    assert result.verdict == "needs_review"
    assert result.metrics.singleton_tag_ratio > 0.6
    assert any(issue.code == "over_fragmented_tags" for issue in result.warnings)
    assert any("repeated" in recommendation for recommendation in result.recommendations)


def test_assess_caption_suitability_blocks_missing_and_empty_txt(tmp_path: Path) -> None:
    """缺 caption 或空 caption 代表目前不適合訓練。"""
    base = tmp_path / "lora_train"
    _make_dataset(base, ["miku_token, blue hair", None, ""])

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        result = lora_dataset_assessment.assess_caption_suitability("character/miku", trigger_token="miku_token")

    assert result.verdict == "not_suitable"
    assert result.image_count == 3
    assert result.txt_count == 2
    assert result.missing_txt_count == 1
    assert result.empty_txt_count == 1
    warning_codes = {issue.code for issue in result.warnings}
    assert {"missing_txt", "empty_txt"}.issubset(warning_codes)
    assert any("caption" in reason for reason in result.reasons)


def test_assess_caption_suitability_warns_on_low_trigger_coverage(tmp_path: Path) -> None:
    """提供 trigger token 時，覆蓋率偏低應回 warning 與 needs_review。"""
    base = tmp_path / "lora_train"
    _make_dataset(
        base,
        [
            "miku_token, blue hair, twintails",
            "blue hair, twintails, school uniform",
            "blue hair, twintails, smile",
            "blue hair, twintails, standing",
        ],
    )

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        result = lora_dataset_assessment.assess_caption_suitability("character/miku", trigger_token="miku_token")

    assert result.verdict == "needs_review"
    assert result.trigger_token_coverage.covered_count == 1
    assert result.trigger_token_coverage.total_count == 4
    assert result.trigger_token_coverage.coverage == 0.25
    assert any(issue.code == "low_trigger_coverage" for issue in result.warnings)
