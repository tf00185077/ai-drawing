"""Prompt Library MCP tool behavior tests."""
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mcp_server.tools.prompt_library import prompt_library_restore, prompt_library_save


def _save(resource_type, payload, **kwargs):
    client = MagicMock()
    client.put.return_value = {"entry": {"id": kwargs.get("resource_id", "x")}, "entry_revision": 2}
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_save(resource_type=resource_type, payload=payload, **kwargs)
    return result, client


def test_entry_without_chinese_warns_but_saves():
    payload = {"name_zh": "masterpiece detail", "description_zh": "quality", "prompt": "masterpiece"}
    result, client = _save("entry", payload, resource_id="masterpiece", polarity="positive", category_id="quality-details")
    assert result["ok"] is True
    assert client.put.called
    assert result["warnings"][0]["code"] == "name_zh_missing_chinese"


def test_entry_echoing_prompt_warns_echoes():
    payload = {"name_zh": "Masterpiece", "description_zh": "quality", "prompt": "masterpiece"}
    result, _ = _save("entry", payload, resource_id="masterpiece", polarity="positive", category_id="quality-details")
    assert result["ok"] is True
    assert result["warnings"][0]["code"] == "name_zh_echoes_prompt"


def test_entry_with_meaningful_chinese_has_no_warnings():
    payload = {"name_zh": "傑作", "description_zh": "品質詞", "prompt": "masterpiece"}
    result, _ = _save("entry", payload, resource_id="masterpiece", polarity="positive", category_id="quality-details")
    assert result["ok"] is True
    assert "warnings" not in result


def test_category_without_chinese_warns_missing():
    payload = {"name_zh": "quality details", "description_zh": "quality"}
    result, _ = _save("category", payload, resource_id="quality-details", polarity="positive")
    assert result["ok"] is True
    assert result["warnings"][0]["code"] == "name_zh_missing_chinese"


def _restore(**kwargs):
    client = MagicMock()
    client.post.return_value = {
        "resource_type": kwargs["resource_type"],
        "resource_id": kwargs["resource_id"],
        "revision": kwargs["expected_revision"] + 1,
        "etag": "restored-etag",
    }
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_restore(**kwargs)
    return result, client


def test_restore_entry_posts_exact_payload_and_path():
    result, client = _restore(
        resource_type="entry",
        resource_id="masterpiece",
        polarity="positive",
        category_id="quality-ratings",
        expected_revision=21,
        expected_etag="current-etag",
    )

    client.post.assert_called_once_with(
        "prompt-library/restore",
        json={
            "resource_type": "entry",
            "resource_id": "masterpiece",
            "polarity": "positive",
            "category_id": "quality-ratings",
            "expected_revision": 21,
            "expected_etag": "current-etag",
        },
    )
    assert result["ok"] is True


def test_restore_category_omits_category_id_from_payload():
    _, client = _restore(
        resource_type="category",
        resource_id="quality-ratings",
        polarity="positive",
        category_id="must-be-omitted",
        expected_revision=8,
        expected_etag="category-etag",
    )

    payload = client.post.call_args.kwargs["json"]
    assert payload == {
        "resource_type": "category",
        "resource_id": "quality-ratings",
        "polarity": "positive",
        "expected_revision": 8,
        "expected_etag": "category-etag",
    }
    assert "category_id" not in payload


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "resource_type": "combination",
            "resource_id": "portrait",
            "expected_revision": 2,
            "expected_etag": "etag",
        },
        {
            "resource_type": "category",
            "resource_id": "quality-ratings",
            "expected_revision": 2,
            "expected_etag": "etag",
        },
        {
            "resource_type": "entry",
            "resource_id": "masterpiece",
            "polarity": "positive",
            "expected_revision": 2,
            "expected_etag": "etag",
        },
    ],
)
def test_restore_rejects_unsupported_or_incomplete_locator_without_backend_call(kwargs):
    result, client = _restore(**kwargs)

    assert result["ok"] is False
    assert result["tool"] == "prompt_library_restore"
    assert result["error"]["code"] == "invalid_resource_locator"
    assert result["error"]["message"]
    assert result["error"]["hint"]
    client.post.assert_not_called()


def test_restore_preserves_structured_backend_conflict():
    request = httpx.Request("POST", "http://backend.test/api/prompt-library/restore")
    detail = {
        "code": "revision_conflict",
        "message": "resource revision changed",
        "hint": "reload before restoring",
        "details": {"expected_revision": 21, "actual_revision": 22},
    }
    response = httpx.Response(409, json={"detail": detail}, request=request)
    client = MagicMock()
    client.post.side_effect = httpx.HTTPStatusError(
        "409 Conflict", request=request, response=response
    )

    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_restore(
            resource_type="entry",
            resource_id="masterpiece",
            polarity="positive",
            category_id="quality-ratings",
            expected_revision=21,
            expected_etag="current-etag",
        )

    assert result == {
        "ok": False,
        "tool": "prompt_library_restore",
        "error": detail,
        "status_code": 409,
    }


def test_restore_success_envelope_includes_backend_response_and_next():
    result, _ = _restore(
        resource_type="entry",
        resource_id="masterpiece",
        polarity="positive",
        category_id="quality-ratings",
        expected_revision=21,
        expected_etag="current-etag",
    )

    assert result == {
        "ok": True,
        "tool": "prompt_library_restore",
        "resource_type": "entry",
        "resource_id": "masterpiece",
        "revision": 22,
        "etag": "restored-etag",
        "next": "reload the category and use its new revision and etag",
    }
