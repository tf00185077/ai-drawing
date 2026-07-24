import pytest

from bot.validation import (
    ValidationError,
    build_gallery_download_url,
    parse_count,
    parse_dimension,
)


def test_parse_dimension_valid():
    assert parse_dimension("1024", field="寬") == 1024
    assert parse_dimension("  512 ", field="寬") == 512


@pytest.mark.parametrize("raw", ["255", "2049", "abc", "", "3.5"])
def test_parse_dimension_invalid(raw):
    with pytest.raises(ValidationError):
        parse_dimension(raw, field="寬")


def test_parse_count_empty_returns_default():
    assert parse_count("") == 4
    assert parse_count("   ") == 4


def test_parse_count_valid():
    assert parse_count("1") == 1
    assert parse_count("8") == 8


@pytest.mark.parametrize("raw", ["0", "9", "-1", "x"])
def test_parse_count_invalid(raw):
    with pytest.raises(ValidationError):
        parse_count(raw)


def test_build_gallery_download_url():
    assert build_gallery_download_url("http://h:8000", "/gallery/2026/x.png") == "http://h:8000/gallery/2026/x.png"
    assert build_gallery_download_url("http://h:8000/", "gallery/x.png") == "http://h:8000/gallery/x.png"
