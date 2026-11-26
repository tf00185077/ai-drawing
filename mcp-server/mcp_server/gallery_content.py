"""Bounded canonical PNG reads; no paths or URLs supplied by callers.

Locator construction is metadata only. The descriptor check below verifies the
regular file actually opened, including intermediate-component races. Unsupported
OS handle inspection fails closed. Bytes are returned verbatim.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
from pathlib import Path
import stat
import sys
import warnings

from PIL import Image

from mcp_server.media_locators import LocatorUnavailable, gallery_locators

MAX_BYTES = 2_097_152
MAX_DIMENSION = 2048
MAX_PIXELS = 4_194_304


class ContentError(ValueError):
    def __init__(self, code: str):
        self.code = 'artifact_content_' + code
        super().__init__(self.code)


def _descriptor_path(fd: int) -> Path:
    """OS identity of the opened file, rather than a second path-only resolve."""
    if sys.platform == 'darwin':
        import fcntl
        raw = fcntl.fcntl(fd, 50, bytes(1024))  # F_GETPATH, Darwin sys/fcntl.h
        return Path(os.fsdecode(raw.split(b'\0', 1)[0]))
    if sys.platform.startswith('linux'):
        return Path(os.readlink(f'/proc/self/fd/{fd}'))
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        import msvcrt
        get_path = ctypes.WinDLL('kernel32', use_last_error=True).GetFinalPathNameByHandleW
        get_path.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
        get_path.restype = wintypes.DWORD
        buffer = ctypes.create_unicode_buffer(32768)
        length = get_path(msvcrt.get_osfhandle(fd), buffer, len(buffer), 0)
        if not length or length >= len(buffer):
            raise OSError('handle path unavailable')
        value = buffer.value
        if value.startswith('\\\\?\\UNC\\'):
            value = '\\\\' + value[8:]
        elif value.startswith('\\\\?\\'):
            value = value[4:]
        return Path(value)
    raise OSError('opened-file identity unavailable')


def read_png(record: dict, artifact_id: int, *, gallery_dir: str, backend_url: str) -> dict:
    if not isinstance(record, dict) or type(record.get('id')) is not int or record['id'] != artifact_id:
        raise ContentError('unavailable')
    if record.get('artifact_type') != 'image' or record.get('mime_type') != 'image/png':
        raise ContentError('invalid')
    try:
        root = Path(gallery_dir).expanduser().resolve(strict=True)
        host, _ = gallery_locators(path=record.get('gallery_path'), url=record.get('artifact_url'),
                                  local_path=record.get('local_path'),
                                  gallery_dir=gallery_dir, backend_url=backend_url)
        expected = Path(host)
        # A second host locator cannot contradict the canonical Gallery mapping.
        # Backend container paths may coexist with a relative path/URL, as in the
        # existing locator contract; they are never used as the opened path.
        local = record.get('local_path')
        if local:
            local_path = Path(local)
            if not local_path.is_absolute():
                raise LocatorUnavailable('invalid local locator')
            relative = record.get('gallery_path')
            container_mapping = (isinstance(relative, str) and not Path(relative).is_absolute()
                                 and local_path == Path('/data/gallery') / relative)
            if local_path.resolve() != expected and not container_mapping:
                raise LocatorUnavailable('conflicting or unsupported local locator')
        flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
        fd = os.open(expected, flags)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ContentError('unavailable')
            actual = _descriptor_path(fd)
            # Do not resolve actual: an attacker could replace its new path too.
            actual.relative_to(root)
            if actual != expected:
                raise ContentError('unavailable')
            # Recheck root identity to reject a moved/replaced configured root.
            if Path(gallery_dir).expanduser().resolve(strict=True) != root:
                raise ContentError('unavailable')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(MAX_BYTES + 1)
        finally:
            os.close(fd)
    except ContentError:
        raise
    except (OSError, ValueError, RuntimeError, TypeError):
        raise ContentError('unavailable') from None
    if len(raw) > MAX_BYTES:
        raise ContentError('too_large')
    width, height = validate_png(raw)
    return {'encoding':'base64', 'mime_type':'image/png', 'byte_length':len(raw),
            'sha256':hashlib.sha256(raw).hexdigest(), 'width':width, 'height':height,
            'base64':base64.b64encode(raw).decode('ascii')}


def validate_png(raw: bytes) -> tuple[int, int]:
    if not raw:
        raise ContentError('invalid')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw), formats=['PNG']) as image:
                width, height = image.size
                if not (1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION) or width * height > MAX_PIXELS:
                    raise ContentError('too_large')
                if image.format != 'PNG' or image.n_frames != 1 or getattr(image, 'is_animated', False):
                    raise ContentError('invalid')
                image.verify()  # structural/CRC checks, including the final chunk
            with Image.open(io.BytesIO(raw), formats=['PNG']) as image:
                image.load()  # require a full successful decode, not just a header
    except ContentError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ContentError('too_large') from None
    except Exception:
        raise ContentError('invalid') from None
    return width, height
