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


def build_gallery_download_url(base_url: str, image_url: str) -> str:
    return f"{base_url.rstrip('/')}/{image_url.lstrip('/')}"
