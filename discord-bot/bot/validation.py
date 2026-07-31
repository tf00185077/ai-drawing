"""Modal 輸入的純函式驗證與 URL 組裝。"""


class ValidationError(Exception):
    pass


def parse_dimension(raw: str, *, field: str) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{field}必須是整數")
    if not (256 <= value <= 2048):
        raise ValidationError(f"{field}必須介於 256–2048")
    return value


def parse_count(raw: str, *, default: int = 4) -> int:
    text = str(raw or "").strip()
    if text == "":
        return default
    try:
        value = int(text)
    except ValueError:
        raise ValidationError("張數必須是整數")
    if not (1 <= value <= 8):
        raise ValidationError("張數必須介於 1–8")
    return value


def parse_video_contract(
    total_seconds: float | str,
    source_frames: int | str,
    film_target_frames: int | str,
) -> tuple[float, int, int]:
    try:
        seconds = float(total_seconds)
        source = int(source_frames)
        target = int(film_target_frames)
    except (TypeError, ValueError):
        raise ValidationError("秒數與幀數格式錯誤")
    if not 1.0 <= seconds <= 20.0:
        raise ValidationError("總秒數必須介於 1–20（首幀至末幀）")
    if not 17 <= source <= 321:
        raise ValidationError("生成總幀數必須介於 17–321")
    if (source - 1) % 4:
        raise ValidationError("生成總幀數必須符合 Wan 4n+1")
    if not source <= target <= 1921:
        raise ValidationError("FILM 目標總幀數必須不小於生成幀數且不超過 1921")
    return seconds, source, target


def validate_discord_attachment(attachment, *, kind: str) -> None:
    image_types = {"image/png": {".png"}, "image/jpeg": {".jpg", ".jpeg"}, "image/webp": {".webp"}}
    video_types = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
    types = image_types if kind == "image" else video_types
    limit = 20 * 1024 * 1024 if kind == "image" else 100 * 1024 * 1024
    from pathlib import Path

    mime = str(getattr(attachment, "content_type", "") or "").split(";", 1)[0].lower()
    suffix = Path(str(getattr(attachment, "filename", ""))).suffix.lower()
    size = getattr(attachment, "size", 0)
    expected = types.get(mime)
    if expected is None or suffix not in (expected if isinstance(expected, set) else {expected}):
        raise ValidationError(f"{kind} attachment 類型或副檔名不支援")
    if type(size) is not int or not 1 <= size <= limit:
        raise ValidationError(f"{kind} attachment 大小必須介於 1 與 {limit} bytes")


def build_gallery_download_url(base_url: str, image_url: str) -> str:
    return f"{base_url.rstrip('/')}/{image_url.lstrip('/')}"
