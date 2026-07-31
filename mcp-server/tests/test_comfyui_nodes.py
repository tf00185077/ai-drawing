"""Tests for ComfyUI-Manager node resolve/install MCP tools."""
import json
from unittest.mock import MagicMock, patch

from mcp_server.tools.comfyui_nodes import comfyui_node_provision, comfyui_restart


def test_provision_resolves_and_installs_curated_package() -> None:
    """A node class name that maps to a cnr_id gets installed and flags needs_restart."""
    mock_client = MagicMock()
    mock_client.get.side_effect = [
        {"my-nodes-pack": [["MyCustomNode", "OtherNode"], {}]},  # getmappings
        {"is_processing": False, "in_progress_count": 0, "done_count": 1, "total_count": 1},  # queue/status
    ]
    mock_client.post.return_value = {}

    with patch("mcp_server.tools.comfyui_nodes._get_comfyui_client", return_value=mock_client), \
         patch("mcp_server.tools.comfyui_nodes.time.sleep"):
        result = comfyui_node_provision(["MyCustomNode"])

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "comfyui_node_provision"
    assert data["resolved"] is True
    assert data["node_type"] == "MyCustomNode"
    assert data["cnr_id"] == "my-nodes-pack"
    assert data["needs_restart"] is True
    assert data["unresolved_node_types"] == []
    mock_client.get.assert_any_call("/customnode/getmappings", params={"mode": "local"})
    mock_client.post.assert_any_call(
        "/manager/queue/install",
        json={
            "id": "my-nodes-pack",
            "version": "latest",
            "selected_version": "latest",
            "channel": "default",
            "mode": "cache",
            "ui_id": "my-nodes-pack",
        },
    )
    mock_client.post.assert_any_call("/manager/queue/start", json={})


def test_provision_reports_unresolved_when_node_not_in_any_package() -> None:
    """No package claims this node type: report unresolved, never call install."""
    mock_client = MagicMock()
    mock_client.get.return_value = {"some-pack": [["UnrelatedNode"], {}]}

    with patch("mcp_server.tools.comfyui_nodes._get_comfyui_client", return_value=mock_client):
        result = comfyui_node_provision(["TotallyUnknownNode"])

    data = json.loads(result)
    assert data["ok"] is True
    assert data["resolved"] is False
    assert data["unresolved_node_types"] == ["TotallyUnknownNode"]
    mock_client.post.assert_not_called()


def test_provision_skips_install_when_resolved_key_is_a_raw_url_not_a_cnr_id() -> None:
    """map_to_unified_keys leaves non-registry packages as a raw repo URL; never install those."""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "https://github.com/someone/not-in-registry": [["UnregisteredNode"], {}]
    }

    with patch("mcp_server.tools.comfyui_nodes._get_comfyui_client", return_value=mock_client):
        result = comfyui_node_provision(["UnregisteredNode"])

    data = json.loads(result)
    assert data["ok"] is True
    assert data["resolved"] is False
    assert data["unresolved_node_types"] == ["UnregisteredNode"]
    mock_client.post.assert_not_called()


def test_provision_getmappings_failure_returns_structured_error() -> None:
    mock_client = MagicMock()
    mock_client.get.side_effect = RuntimeError("comfyui unreachable")

    with patch("mcp_server.tools.comfyui_nodes._get_comfyui_client", return_value=mock_client):
        result = comfyui_node_provision(["AnyNode"])

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "comfyui_node_provision"
    assert data["error"]["code"] == "RuntimeError"
    assert data["error"]["details"]["where"] == "comfyui_manager_getmappings"


def test_provision_install_failure_returns_structured_error_with_cnr_id() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {"my-nodes-pack": [["MyCustomNode"], {}]}
    mock_client.post.side_effect = RuntimeError("security level too low")

    with patch("mcp_server.tools.comfyui_nodes._get_comfyui_client", return_value=mock_client):
        result = comfyui_node_provision(["MyCustomNode"])

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "comfyui_node_provision"
    assert data["error"]["code"] == "RuntimeError"
    assert data["error"]["details"]["where"] == "comfyui_manager_install"
    assert data["error"]["details"]["cnr_id"] == "my-nodes-pack"


def test_restart_calls_manager_reboot_and_returns_ok() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {}

    with patch("mcp_server.tools.comfyui_nodes._get_comfyui_client", return_value=mock_client):
        result = comfyui_restart()

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "comfyui_restart"
    mock_client.post.assert_called_once_with("/manager/reboot", json={})


def test_restart_failure_returns_structured_error() -> None:
    mock_client = MagicMock()
    mock_client.post.side_effect = RuntimeError("security level too low")

    with patch("mcp_server.tools.comfyui_nodes._get_comfyui_client", return_value=mock_client):
        result = comfyui_restart()

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "comfyui_restart"
    assert data["error"]["details"]["where"] == "comfyui_manager_reboot"
