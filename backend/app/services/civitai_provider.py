"""Private credentials and bounded requests for retained Civitai resource callers.

Synchronous services drive cancellable async HTTP reads on a private event loop.
The absolute deadline spans nested requests, redirects, retries and streaming;
HTTP phase timeouts alone cannot bound a server that keeps sending small chunks.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from http.cookiejar import CookieJar, DefaultCookiePolicy
import logging
import os
import re
import stat
import time
from typing import Any
from urllib.parse import urljoin, urlsplit, unquote_plus

import httpx

from app.config import get_settings
from app.services.civitai_acquisition import redact_secrets


_log_secrets: ContextVar[tuple[str, ...]] = ContextVar('civitai_log_secrets', default=())


class _SafeProviderLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # httpx logs full request URLs and httpcore debug logs Location headers.
        # Filter at their emitting loggers, before any application handler sees it.
        # httpcore debug events render raw header tuples, including cookies.
        # Do not turn transport header dumps into a free-text recognition task.
        if record.name.startswith('httpcore.'):
            return False
        from app.services.resource_records import safe_text
        record.msg = safe_text(redact_secrets(record.getMessage(), secrets=_log_secrets.get()))
        record.args = ()
        return True


for _name in ('httpx', 'httpcore.connection', 'httpcore.http11', 'httpcore.http2', 'httpcore.proxy', 'httpcore.socks'):
    logging.getLogger(_name).addFilter(_SafeProviderLog())


class CivitaiProviderError(Exception):
    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        self.code, self.message, self.hint = code, message, hint
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **({"hint": self.hint} if self.hint else {})}


def _credential_error() -> CivitaiProviderError:
    return CivitaiProviderError(
        "civitai_credentials_unavailable", "Civitai credentials are unavailable",
        "Check the CIVITAI_API_KEY_FILE setting. Use a readable regular UTF-8 file containing one key (at most 64 KiB); no fallback is used when configured.",
    )


def resolve_credentials(settings: Any | None = None) -> str | None:
    """Read at most 64 KiB; never open a blocking FIFO."""
    settings = settings if settings is not None else get_settings()
    path = (getattr(settings, 'civitai_api_key_file', None) or '').strip()
    if path:
        descriptor = None
        try:
            # Precheck and fstat both matter: a path can change between stat/open.
            if not stat.S_ISREG(os.stat(path).st_mode):
                raise ValueError()
            descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0))
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                raise ValueError()
            with os.fdopen(descriptor, 'rb') as stream:
                descriptor = None
                raw = stream.read(65536)
                if os.fstat(stream.fileno()).st_size > 65536:
                    raise ValueError()
            value = raw.decode('utf-8').strip()
            # A file is a single token, never a header block/JSON. Trim outer
            # whitespace, but reject internal whitespace, controls and non-ASCII.
            if not value or not re.fullmatch(r'[A-Za-z0-9._~+/=-]+', value):
                raise ValueError()
            return 'Bearer ' + value
        except (OSError, ValueError, UnicodeError):
            raise _credential_error() from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
    value = (getattr(settings, 'civitai_authorization', None) or '').strip()
    if not value:
        return None
    if any(ord(c) < 32 or ord(c) == 127 or ord(c) > 126 for c in value):
        raise _credential_error()
    return value if value.lower().startswith('bearer ') else 'Bearer ' + value


def validate_url(url: str) -> tuple[str, str, int]:
    try:
        parsed = urlsplit(url)
        if (any(ord(c) <= 32 or ord(c) == 127 for c in url)
                or parsed.scheme != 'https'
                or parsed.hostname not in {'civitai.com', 'www.civitai.com', 'b2.civitai.com'}
                or parsed.port not in (None, 443) or parsed.username is not None
                or parsed.password is not None or '\\' in parsed.netloc):
            raise ValueError()
        return 'https', parsed.hostname, 443
    except (ValueError, TypeError):
        raise CivitaiProviderError('civitai_redirect_blocked', 'Civitai request URL or redirect is blocked',
                                   'Use HTTPS on civitai.com, www.civitai.com or b2.civitai.com with the default port and no userinfo; at most five redirects are allowed.') from None


def _timeout_error() -> CivitaiProviderError:
    return CivitaiProviderError('civitai_timeout', 'Civitai operation deadline or HTTP timeout reached',
                               'Inspect the same acquisition ID before retrying; do not submit a duplicate after a caller timeout.')


class _RejectProviderCookies(DefaultCookiePolicy):
    """Provider credentials have no cookie channel, including implicit state."""
    def set_ok(self, cookie, request):
        return False

    def return_ok(self, cookie, request):
        return False


class ProviderOperation:
    def __init__(self, kind: str, *, settings: Any | None = None) -> None:
        if kind not in {'metadata', 'download'}:
            raise ValueError('unknown provider operation')
        self.authorization = resolve_credentials(settings)
        self.deadline = time.monotonic() + (20 if kind == 'metadata' else 900)
        self.connect_limit, self.read_limit = (5, 10) if kind == 'metadata' else (10, 30)
        self._runner: asyncio.Runner | None = None
        self._responses: list[Any] = []
        self._bodies: list[Any] = []

    @property
    def headers(self) -> dict[str, str]:
        return {'Authorization': self.authorization} if self.authorization else {}

    def sanitize(self, value: Any) -> Any:
        return redact_secrets(value, secrets=tuple(v for v in (self.authorization, (self.authorization or '').split(' ', 1)[-1]) if v))

    def metadata(self, value: Any) -> Any:
        # Raw download locators exist only in this internal operation's result;
        # the request policy consumes them and persisted/public projections redact.
        clean = self.sanitize(value)

        def retain_locators(raw, sanitized):
            if isinstance(raw, dict):
                for key, item in raw.items():
                    if key == 'downloadUrl' and isinstance(item, str):
                        self._check_url(item)
                        sanitized[key] = item
                    elif isinstance(sanitized.get(key), (dict, list)):
                        retain_locators(item, sanitized[key])
            elif isinstance(raw, list):
                for item, result in zip(raw, sanitized):
                    retain_locators(item, result)
        retain_locators(value, clean)
        return clean

    def _check_url(self, url: str) -> tuple[str, str, int]:
        origin = validate_url(url)
        key = (self.authorization or '').split(' ', 1)[-1]
        if key and key in unquote_plus(url):
            raise CivitaiProviderError('civitai_redirect_blocked', 'Credential-bearing Civitai URL is blocked',
                                       'Keep the Backend credential in Authorization only; use the public provider route.')
        return origin

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise _timeout_error()
        return remaining

    def _loop(self) -> asyncio.Runner:
        if self._runner is None:
            self._runner = asyncio.Runner()
        return self._runner

    def run(self, coroutine):
        try:
            remaining = self.remaining()
        except BaseException:
            coroutine.close()
            raise
        async def bounded():
            token = _log_secrets.set(tuple(v for v in (self.authorization, (self.authorization or '').split(' ', 1)[-1]) if v))
            try:
                return await asyncio.wait_for(coroutine, timeout=remaining)
            finally:
                _log_secrets.reset(token)
        try:
            result = self._loop().run(bounded())
            return result
        except (TimeoutError, httpx.TimeoutException):
            raise _timeout_error() from None
        except httpx.HTTPError:
            raise CivitaiProviderError('civitai_network_error', 'Civitai network request failed',
                                       'Check provider availability and connectivity; inspect the same acquisition before retrying.') from None

    def pause(self, seconds: float, sleep=time.sleep) -> None:
        remaining = self.remaining()
        sleep(min(seconds, remaining))
        self.remaining()

    @contextmanager
    def request(self, method: str, url: str, *, headers: dict[str, str] | None = None):
        origin = self._check_url(url)
        send_auth = origin == ('https', 'civitai.com', 443)
        # Ignore caller Authorization: the credential snapshot is Backend owned.
        safe_headers = {k: v for k, v in (headers or {}).items() if k.lower() not in {'authorization', 'cookie', 'proxy-authorization'}}
        client = httpx.AsyncClient(follow_redirects=False, trust_env=False,
                                   cookies=CookieJar(policy=_RejectProviderCookies()))
        response = None
        try:
            for hop in range(6):
                remaining = self.remaining()
                timeout = httpx.Timeout(connect=min(self.connect_limit, remaining), read=min(self.read_limit, remaining),
                                        write=min(self.connect_limit, remaining), pool=min(self.connect_limit, remaining))
                request = client.build_request(method, url, headers=safe_headers, timeout=timeout)
                # Client preparation can add default headers or cookie-jar state.
                # Apply the channel policy to the final request on every hop.
                for name in ('Authorization', 'Cookie', 'Proxy-Authorization'):
                    request.headers.pop(name, None)
                request.headers.update(self.headers if send_auth else {})
                response = self.run(client.send(request, stream=True))
                self._responses.append(response)
                self.remaining()
                if response.status_code not in {301, 302, 303, 307, 308}:
                    yield response
                    return
                location = response.headers.get('location')
                if not location or hop == 5:
                    raise CivitaiProviderError('civitai_redirect_blocked', 'Civitai redirect limit or invalid redirect',
                                               'Check the provider route; at most five redirects are allowed.')
                next_url = urljoin(url, location)
                next_origin = self._check_url(next_url)
                send_auth = send_auth and next_origin == origin
                self._loop().run(response.aclose())
                self._responses.remove(response)
                response = None
                url, origin = next_url, next_origin
        finally:
            if response is not None:
                self._loop().run(response.aclose())
                if response in self._responses:
                    self._responses.remove(response)
            self._loop().run(client.aclose())

    def get_json(self, url: str) -> tuple[int, Any]:
        with self.request('GET', url) as response:
            self.run(response.aread())
            self.remaining()
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            return response.status_code, payload

    def close(self) -> None:
        for body in self._bodies[:]:
            body.close()
        if self._runner is not None:
            try:
                for response in self._responses[:]:
                    self._runner.run(response.aclose())
            finally:
                self._responses.clear()
                self._runner.close()
                self._runner = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class _Body:
    """Explicit close works even when an iterator has never been advanced."""
    def __init__(self, operation: ProviderOperation, context, response, *, owns_operation: bool):
        self.operation, self.context, self.response = operation, context, response
        self.iterator = response.aiter_bytes(chunk_size=1024 * 1024).__aiter__()
        self.owns_operation, self.closed = owns_operation, False
        operation._bodies.append(self)

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        try:
            chunk = self.operation.run(self.iterator.__anext__())
            self.operation.remaining()
            return chunk
        except StopAsyncIteration:
            self.close()
            raise StopIteration from None
        except BaseException:
            self.close()
            raise

    def close(self):
        if not self.closed:
            self.closed = True
            self.operation._bodies.remove(self)
            try:
                self.context.__exit__(None, None, None)
            finally:
                if self.owns_operation:
                    self.operation.close()


class ProviderDownloadTransport:
    def __init__(self, operation: ProviderOperation | None = None):
        self.operation = operation

    def get(self, url: str, *, headers: dict[str, str] | None = None):
        from app.services.civitai_safe_download import DownloadResponse
        operation = self.operation or ProviderOperation('download')
        context = operation.request('GET', url, headers=headers)
        try:
            response = context.__enter__()
        except BaseException:
            if self.operation is None:
                operation.close()
            raise
        body = _Body(operation, context, response, owns_operation=self.operation is None)
        return DownloadResponse(response.status_code, body, operation.sanitize(dict(response.headers)))
