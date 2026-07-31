import pytest
from types import SimpleNamespace

from bot.validation import (
    ValidationError,
    build_gallery_download_url,
    parse_count,
    parse_dimension,
    parse_video_contract,
    validate_discord_attachment,
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


def test_video_contract_validates_4n_plus_1_and_exact_target():
    assert parse_video_contract(5, 81, 321) == (5.0, 81, 321)
    with pytest.raises(ValidationError, match="4n\\+1"):
        parse_video_contract(5, 80, 321)
    with pytest.raises(ValidationError, match="不小於"):
        parse_video_contract(5, 81, 80)


def test_discord_attachment_allowlist_suffix_and_size():
    validate_discord_attachment(SimpleNamespace(filename="photo.jpeg", content_type="image/jpeg", size=10), kind="image")
    validate_discord_attachment(SimpleNamespace(filename="driver.mp4", content_type="video/mp4", size=10), kind="video")
    with pytest.raises(ValidationError):
        validate_discord_attachment(SimpleNamespace(filename="photo.exe", content_type="image/png", size=10), kind="image")
    with pytest.raises(ValidationError):
        validate_discord_attachment(SimpleNamespace(filename="driver.mp4", content_type="video/mp4", size=0), kind="video")
