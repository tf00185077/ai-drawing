"""Backend API Client 單元測試"""
from unittest.mock import MagicMock, patch

from mcp_server.client import HttpBackendClient


def test_client_constructs_with_base_url() -> None:
    """Client 正確建構 base URL"""
    client = HttpBackendClient(base_url="http://test:9000")
    assert client._base_url == "http://test:9000"


def test_client_get_calls_httpx_with_correct_url() -> None:
    """Client.get 呼叫正確的 URL 並回傳 JSON"""
    import httpx  # 確保模組已載入，供 patch 使用

    client = HttpBackendClient(base_url="http://test:9000")
    mock_response = MagicMock()
    mock_response.content = b'{"ok": true}'
    mock_response.json.return_value = {"ok": True}
    mock_response.raise_for_status = MagicMock()

    mock_http = MagicMock()
    mock_http.get.return_value = mock_response

    with patch.object(httpx, "Client") as MockClient:
        MockClient.return_value.__enter__.return_value = mock_http
        MockClient.return_value.__exit__.return_value = None

        result = client.get("api/gallery/", params={"limit": 5})

        assert result == {"ok": True}
        mock_http.get.assert_called_once()
        call_args = mock_http.get.call_args
        assert "api/gallery/" in call_args[0][0] or "gallery" in call_args[0][0]
        assert call_args[1]["params"] == {"limit": 5}
