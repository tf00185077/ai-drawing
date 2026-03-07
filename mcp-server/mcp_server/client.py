"""
Backend API Client 抽象層

透過 Protocol 定義介面，業務邏輯依賴抽象，具體實作可替換（測試 mock、不同 base URL）。
"""
from typing import Any, Protocol


class BackendApiClient(Protocol):
    """Backend API 呼叫介面"""

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET 請求"""
        ...

    def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """POST 請求"""
        ...


class HttpBackendClient:
    """以 httpx 實作的 Backend API Client"""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _url(self, path: str) -> str:
        p = path if path.startswith("/") else f"/{path}"
        return f"{self._base_url}{p}"

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        import httpx

        url = self._url(path)
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(url, params=params or {})
            resp.raise_for_status()
            return resp.json() if resp.content else {}

    def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        import httpx

        url = self._url(path)
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, json=json or {})
            resp.raise_for_status()
            return resp.json() if resp.content else {}
