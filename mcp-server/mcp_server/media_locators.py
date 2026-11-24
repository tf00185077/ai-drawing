"""Construct Gallery locators only when their file relationship is established.

No file existence/byte verification, migration, or basename remapping occurs.
"""
import re
from pathlib import Path, PureWindowsPath
from urllib.parse import quote, unquote, urlsplit


class LocatorUnavailable(ValueError):
    """A supplied locator cannot safely identify a configured Gallery file."""

    def __init__(self, message: str, *, local_path: str | None = None):
        super().__init__(message)
        self.local_path = local_path


def _relative(value: str) -> str:
    if (not value or value.startswith(('/', '~')) or PureWindowsPath(value).drive
            or any(ord(c) < 32 or ord(c) == 127 or c in '\\:' for c in value)
            or any(part in {'', '.', '..'} for part in value.split('/'))):
        raise LocatorUnavailable('unsafe Gallery-relative path')
    return value


def _url_relative(value: str, backend_url: str) -> str:
    try:
        if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 or c in '\\?#' for c in value):
            raise LocatorUnavailable('unsafe Gallery URL')
        if re.search(r'%(?![0-9a-fA-F]{2})', value):
            raise LocatorUnavailable('malformed URL encoding')
        url, base = urlsplit(value), urlsplit(backend_url)
        if (url.query or url.fragment or url.username or url.password
                or value.startswith('//')
                or (url.scheme or url.netloc) and (url.scheme, url.netloc) != (base.scheme, base.netloc)):
            raise LocatorUnavailable('URL is not an uncredentialed configured Backend Gallery URL')
        prefix = base.path.rstrip('/') + '/gallery/'
        if not url.path.startswith(prefix):
            raise LocatorUnavailable('URL is outside the configured Backend Gallery route')
        relative = unquote(url.path[len(prefix):], errors='strict')
        if relative.count('/') != url.path[len(prefix):].count('/'):
            raise LocatorUnavailable('encoded path separator')
        _relative(relative)
        # Reject multiply encoded traversal/separators rather than depending on
        # how many times a proxy/static server decodes a URL.
        decoded = relative
        while '%' in decoded:
            next_value = unquote(decoded, errors='strict')
            if next_value == decoded:
                break
            if next_value.count('/') != decoded.count('/'):
                raise LocatorUnavailable('encoded path separator')
            _relative(next_value)
            decoded = next_value
        return relative
    except (ValueError, UnicodeError, TypeError) as exc:
        raise LocatorUnavailable(str(exc)) from exc


def gallery_locators(*, path: str | None, url: str | None, local_path: str | None,
                     gallery_dir: str, backend_url: str) -> tuple[str, str]:
    """Return a contained host path and target-preserving absolute Gallery URL."""
    root = Path(gallery_dir).expanduser().resolve()
    if not Path(gallery_dir).expanduser().is_absolute():
        raise LocatorUnavailable('MCP_GALLERY_DIR must be an absolute host path')
    relative = None
    # A Gallery-relative path is authoritative. Backend local_path may be a
    # container path: ignore it when a relative path or Gallery URL establishes
    # identity. Never re-root an unrelated absolute gallery_path's basename.
    candidate = path or (local_path if not url else None)
    if candidate:
        if not isinstance(candidate, str):
            raise LocatorUnavailable('invalid Gallery path type')
        if Path(candidate).is_absolute():
            if any(part in {'.', '..'} for part in candidate.replace('\\', '/').split('/')):
                raise LocatorUnavailable('absolute Gallery path contains traversal')
            try:
                relative = Path(candidate).resolve().relative_to(root).as_posix()
            except (ValueError, OSError, RuntimeError) as exc:
                raise LocatorUnavailable('absolute path has no supported host Gallery relationship') from exc
        else:
            relative = candidate
        _relative(relative)
    # A rejected supplied URL must not erase a separately supported host path,
    # nor be replaced by a newly invented URL. Conflicting valid mappings are
    # ambiguous and retain neither as a usable locator.
    try:
        url_relative = _url_relative(url, backend_url) if url else None
    except LocatorUnavailable as exc:
        host = None
        if relative:
            try:
                candidate_host = (root / relative).resolve()
                candidate_host.relative_to(root)
                host = str(candidate_host)
            except (ValueError, OSError, RuntimeError):
                pass
        raise LocatorUnavailable(str(exc), local_path=host) from exc
    if relative and url_relative and relative != url_relative:
        raise LocatorUnavailable('Gallery path and URL identify different files')
    relative = relative or url_relative
    if not relative:
        raise LocatorUnavailable('no supported Gallery path or URL')
    try:
        host = (root / relative).resolve()
        host.relative_to(root)
    except (ValueError, OSError, RuntimeError) as exc:
        raise LocatorUnavailable('host path escapes MCP_GALLERY_DIR') from exc
    # Preserve existing escapes/target and encode raw Unicode/spaces returned
    # by older Backend readers. Bind relative routes only to this authority.
    if url:
        parsed = urlsplit(url)
        base = urlsplit(backend_url)
        absolute_url = f'{base.scheme}://{base.netloc}' + quote(parsed.path, safe='/%')
    else:
        absolute_url = backend_url.rstrip('/') + '/gallery/' + quote(relative, safe='/')
    return str(host), absolute_url
