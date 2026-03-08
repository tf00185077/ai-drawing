"""caption_filter 單元測試"""
import pytest

from app.services.caption_filter import filter_caption


def test_filter_caption_deduplication() -> None:
    """重複 tag 只保留第一次出現"""
    raw = "1girl, solo, 1girl, smile, solo, breasts"
    result = filter_caption(raw)
    assert result == "1girl, solo, smile, breasts"


def test_filter_caption_redundancy() -> None:
    """較具體 tag 存在時，移除較籠統 tag"""
    raw = "1girl, swimsuit, one-piece_swimsuit, sitting, wariza"
    result = filter_caption(raw)
    tags = [t.strip() for t in result.split(",")]
    assert "swimsuit" not in tags
    assert "one-piece_swimsuit" in tags
    assert "sitting" not in tags
    assert "wariza" in tags


def test_filter_caption_noise() -> None:
    """雜訊 tag（;d、score_9 等）被移除"""
    raw = "1girl, ;d, solo, score_9, smile"
    result = filter_caption(raw)
    assert ";d" not in result
    assert "score_9" not in result
    assert "1girl" in result
    assert "solo" in result


def test_filter_caption_max_tags() -> None:
    """max_tags 限制保留 tag 數量"""
    raw = "a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p"
    result = filter_caption(raw, max_tags=5)
    tags = [t.strip() for t in result.split(",")]
    assert len(tags) == 5
    assert tags == ["a", "b", "c", "d", "e"]


def test_filter_caption_trigger_word() -> None:
    """trigger_word 前綴至 caption"""
    raw = "1girl, breasts, smile"
    result = filter_caption(raw, trigger_word="ohwx")
    assert result.startswith("ohwx, ")
    assert "1girl" in result
