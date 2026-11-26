"""One strict selected-size interpretation and effective stock-download policy."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from app.config import get_settings
from app.services.civitai_provider import CivitaiProviderError


def download_error(code: str, message: str) -> CivitaiProviderError:
    return CivitaiProviderError(code, message, 'Inspect the same resource ID and destination policy before retrying; do not submit a duplicate download.')


def selected_size(file: Mapping[str, Any]) -> int | None:
    """Provider size is bytes, otherwise sizeKB is exactly 1024 bytes per unit.

    Fractional *bytes* are invalid: never round or truncate a provider identity.
    Decimal from the numeric spelling avoids binary multiplication rounding.
    """
    raw = file.get('size')
    factor = 1
    if raw is None:
        raw, factor = file.get('sizeKB'), 1024
    if type(raw) not in {int, float}:
        return None
    try:
        size = Decimal(str(raw)) * factor
        if size.is_finite() and size > 0 and size == size.to_integral_value():
            return int(size)
    except (InvalidOperation, ValueError, OverflowError):
        pass
    return None


@dataclass(frozen=True)
class DownloadPolicy:
    max_bytes: int
    free_space_floor_bytes: int

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in (self.max_bytes, self.free_space_floor_bytes)):
            raise download_error('civitai_download_policy_unavailable', 'Download byte and free-space settings must be positive integers')

    @classmethod
    def from_settings(cls, settings=None):
        settings = settings if settings is not None else get_settings()
        return cls(getattr(settings, 'civitai_download_max_bytes', None),
                   getattr(settings, 'civitai_download_free_space_floor_bytes', None))

    def validate(self, size, sha256):
        import re
        if type(size) is not int or size <= 0 or not isinstance(sha256, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', sha256):
            raise download_error('civitai_invalid_file_metadata', 'Selected file needs an exact positive integer byte size and 64-hex SHA-256')
        if size > self.max_bytes:
            raise download_error('civitai_byte_limit_exceeded', 'Selected file exceeds the configured per-file byte cap')

    def validate_format(self, kind, name):
        if kind in {'checkpoint', 'lora'} and not str(name).lower().endswith('.safetensors'):
            raise download_error('civitai_unsafe_format', 'Checkpoint and LoRA files must use the safetensors format')
