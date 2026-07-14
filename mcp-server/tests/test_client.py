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


def test_client_uses_bounded_audited_timeout_for_local_resolution_paths() -> None:
    """Cold hashing of large local models gets a bounded route-specific timeout."""
    import httpx

    client = HttpBackendClient(base_url="http://test:9000", timeout=30.0)
    mock_response = MagicMock(content=b'{"ok": true}')
    mock_response.json.return_value = {"ok": True}

    with patch.object(httpx, "Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        for path in (
            "civitai-recipes/resolve-local",
            "civitai-recipes/variants/generate-one",
            "civitai-recipes/variation-sets",
        ):
            client.post(path, json={})

    assert [call.kwargs["timeout"] for call in mock_client.call_args_list] == [120.0, 120.0, 120.0]


def test_client_keeps_default_timeout_for_ordinary_backend_paths() -> None:
    """The audited override must not make every backend failure wait two minutes."""
    import httpx

    client = HttpBackendClient(base_url="http://test:9000", timeout=30.0)
    mock_response = MagicMock(content=b'{"ok": true}')
    mock_response.json.return_value = {"ok": True}

    with patch.object(httpx, "Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        client.post("civitai-recipes/inspect", json={})

    assert mock_client.call_args.kwargs["timeout"] == 30.0


def test_client_delete_calls_httpx_with_correct_url() -> None:
    """Client.delete 呼叫正確的 URL 並回傳 JSON"""
    import httpx  # 確保模組已載入，供 patch 使用

    client = HttpBackendClient(base_url="http://test:9000")
    mock_response = MagicMock()
    mock_response.content = b'{"message": "cancelled", "job_id": "job-1"}'
    mock_response.json.return_value = {"message": "cancelled", "job_id": "job-1"}
    mock_response.raise_for_status = MagicMock()

    mock_http = MagicMock()
    mock_http.delete.return_value = mock_response

    with patch.object(httpx, "Client") as MockClient:
        MockClient.return_value.__enter__.return_value = mock_http
        MockClient.return_value.__exit__.return_value = None

        result = client.delete("api/generate/queue/job-1")

        assert result == {"message": "cancelled", "job_id": "job-1"}
        mock_http.delete.assert_called_once_with("http://test:9000/api/generate/queue/job-1")
