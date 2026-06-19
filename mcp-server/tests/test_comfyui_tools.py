"""ComfyUI 節點 schema MCP 工具測試"""
import json
from unittest.mock import MagicMock, patch

import httpx

from mcp_server.tools.comfyui import get_node_schema, list_node_categories, search_nodes


def test_search_nodes_returns_nodes_with_category() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "nodes": [{"name": "KSampler", "category": "sampling"}],
        "total": 1,
    }
    with patch("mcp_server.tools.comfyui._get_client", return_value=mock_client):
        result = json.loads(search_nodes("KSampler"))

    assert result["ok"] is True
    assert result["nodes"] == [{"name": "KSampler", "category": "sampling"}]
    mock_client.get.assert_called_once_with(
        "comfyui/nodes", params={"query": "KSampler", "category": "", "limit": 50, "offset": 0}
    )


def test_search_nodes_forwards_category_and_limit() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {"nodes": [], "total": 0}
    with patch("mcp_server.tools.comfyui._get_client", return_value=mock_client):
        json.loads(search_nodes(category="loaders"))

    mock_client.get.assert_called_once_with(
        "comfyui/nodes", params={"query": "", "category": "loaders", "limit": 50, "offset": 0}
    )


def test_search_nodes_truncated_tells_agent_to_narrow() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "nodes": [{"name": "Node000", "category": "x"}],
        "total": 120,
        "offset": 0,
        "returned": 1,
        "truncated": True,
        "next_offset": 1,
    }
    with patch("mcp_server.tools.comfyui._get_client", return_value=mock_client):
        result = json.loads(search_nodes(category="x"))

    assert result["truncated"] is True
    assert result["next_offset"] == 1
    assert "offset=1" in result["next"]


def test_search_nodes_rejects_empty_filter_without_calling_backend() -> None:
    mock_client = MagicMock()
    with patch("mcp_server.tools.comfyui._get_client", return_value=mock_client):
        result = json.loads(search_nodes())

    assert result["ok"] is False
    assert result["error"] == "missing_filter"
    assert "list_node_categories" in result["next"]
    mock_client.get.assert_not_called()


def test_search_nodes_no_match_is_ok_with_empty_list() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {"nodes": [], "total": 0}
    with patch("mcp_server.tools.comfyui._get_client", return_value=mock_client):
        result = json.loads(search_nodes("Nope"))

    assert result["ok"] is True
    assert result["nodes"] == []


def test_list_node_categories_returns_categories() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "categories": [{"category": "sampling", "count": 2}],
        "total": 1,
    }
    with patch("mcp_server.tools.comfyui._get_client", return_value=mock_client):
        result = json.loads(list_node_categories())

    assert result["ok"] is True
    assert result["categories"] == [{"category": "sampling", "count": 2}]
    mock_client.get.assert_called_once_with("comfyui/node-categories")


def test_get_node_schema_returns_schema() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "node_type": "KSampler",
        "inputs": {"required": [{"name": "model", "type": "MODEL"}], "optional": []},
        "outputs": [{"name": "LATENT", "type": "LATENT"}],
    }
    with patch("mcp_server.tools.comfyui._get_client", return_value=mock_client):
        result = json.loads(get_node_schema("KSampler"))

    assert result["ok"] is True
    assert result["schema"]["node_type"] == "KSampler"
    mock_client.get.assert_called_once_with("comfyui/nodes/KSampler")


def test_get_node_schema_unknown_node_reports_not_found() -> None:
    mock_client = MagicMock()
    response = httpx.Response(404, request=httpx.Request("GET", "http://x/comfyui/nodes/Nope"))
    mock_client.get.side_effect = httpx.HTTPStatusError(
        "404", request=response.request, response=response
    )
    with patch("mcp_server.tools.comfyui._get_client", return_value=mock_client):
        result = json.loads(get_node_schema("Nope"))

    assert result["ok"] is False
    assert result["error"] == "not_found"
