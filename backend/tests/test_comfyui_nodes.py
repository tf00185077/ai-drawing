"""ComfyUI 節點 schema：純函式、快取、與 API 端點測試"""
from unittest.mock import MagicMock, patch

from app.core.comfyui import (
    ComfyUIClient,
    clear_object_info_cache,
    extract_node_schema,
    get_comfy_client,
    list_node_categories,
    search_node_types,
)
from app.main import app

# 仿 ComfyUI /object_info 的精簡樣本
SAMPLE_OBJECT_INFO = {
    "KSampler": {
        "input": {
            "required": {
                "model": ["MODEL"],
                "seed": ["INT", {"default": 0}],
                "sampler_name": [["euler", "euler_ancestral"]],
                "scheduler": [["normal", "karras"]],
            },
            "optional": {"latent_image": ["LATENT"]},
        },
        "output": ["LATENT"],
        "output_name": ["LATENT"],
        "display_name": "KSampler",
        "category": "sampling",
    },
    "KSamplerAdvanced": {
        "input": {"required": {"model": ["MODEL"]}},
        "output": ["LATENT"],
        "output_name": ["LATENT"],
        "category": "sampling",
    },
    "CheckpointLoaderSimple": {
        "input": {"required": {"ckpt_name": [["a.safetensors"]]}},
        "output": ["MODEL", "CLIP", "VAE"],
        "output_name": ["MODEL", "CLIP", "VAE"],
        "category": "loaders",
    },
    "CLIPLoader": {
        "input": {"required": {"clip_name": [["t5.safetensors"]]}},
        "output": ["CLIP"],
        "output_name": ["CLIP"],
        "category": "advanced/loaders",
    },
}


def _names(rows: list[dict[str, str]]) -> list[str]:
    return [r["name"] for r in rows]


# --- 純函式 ---------------------------------------------------------------


def test_search_matches_by_substring_case_insensitive() -> None:
    rows = search_node_types(SAMPLE_OBJECT_INFO, "ksampler")
    assert _names(rows) == ["KSampler", "KSamplerAdvanced"]
    # 結果帶 category
    assert all("category" in r for r in rows)


def test_search_empty_lists_all_sorted() -> None:
    assert _names(search_node_types(SAMPLE_OBJECT_INFO)) == [
        "CLIPLoader",
        "CheckpointLoaderSimple",
        "KSampler",
        "KSamplerAdvanced",
    ]


def test_search_no_match_returns_empty_list() -> None:
    assert search_node_types(SAMPLE_OBJECT_INFO, "DoesNotExist") == []


def test_search_by_category_filters_by_function() -> None:
    # 只要 loaders 類（含 advanced/loaders）
    rows = search_node_types(SAMPLE_OBJECT_INFO, category="loaders")
    assert _names(rows) == ["CLIPLoader", "CheckpointLoaderSimple"]


def test_search_query_and_category_combine_with_and() -> None:
    rows = search_node_types(SAMPLE_OBJECT_INFO, query="clip", category="loaders")
    assert _names(rows) == ["CLIPLoader"]


def test_list_node_categories_counts() -> None:
    cats = {c["category"]: c["count"] for c in list_node_categories(SAMPLE_OBJECT_INFO)}
    assert cats == {"sampling": 2, "loaders": 1, "advanced/loaders": 1}


def test_extract_schema_known_node_has_inputs_and_outputs() -> None:
    schema = extract_node_schema(SAMPLE_OBJECT_INFO, "KSampler")
    assert schema is not None
    req_names = {i["name"] for i in schema["inputs"]["required"]}
    assert {"model", "seed", "sampler_name"} <= req_names
    # enum 清單型別標記為 COMBO，並保留正式 live capabilities 所需的可選成員。
    sampler = next(i for i in schema["inputs"]["required"] if i["name"] == "sampler_name")
    scheduler = next(i for i in schema["inputs"]["required"] if i["name"] == "scheduler")
    assert sampler == {"name": "sampler_name", "type": "COMBO", "options": ["euler", "euler_ancestral"]}
    assert scheduler == {"name": "scheduler", "type": "COMBO", "options": ["normal", "karras"]}
    assert [i["name"] for i in schema["inputs"]["optional"]] == ["latent_image"]
    assert schema["outputs"] == [{"name": "LATENT", "type": "LATENT"}]


def test_extract_schema_unknown_node_returns_none() -> None:
    assert extract_node_schema(SAMPLE_OBJECT_INFO, "NopeNode") is None


# --- 快取 -----------------------------------------------------------------


@patch("app.core.comfyui.httpx.Client")
def test_object_info_cached_within_ttl(mock_client_class: MagicMock) -> None:
    """TTL 內第二次呼叫走快取，不再打 HTTP。"""
    clear_object_info_cache()
    resp = MagicMock()
    resp.json.return_value = SAMPLE_OBJECT_INFO
    resp.raise_for_status = MagicMock()
    inst = MagicMock()
    inst.get.return_value = resp
    mock_client_class.return_value.__enter__.return_value = inst

    client = ComfyUIClient(base_url="http://test:8188")
    first = client.get_object_info()
    second = client.get_object_info()

    assert first == second == SAMPLE_OBJECT_INFO
    assert inst.get.call_count == 1  # 第二次命中快取


@patch("app.core.comfyui.httpx.Client")
def test_force_refresh_reflects_instance_change(mock_client_class: MagicMock) -> None:
    """force_refresh 重抓，反映 ComfyUI 重啟/新增 custom node 後的節點集合。"""
    clear_object_info_cache()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.side_effect = [
        SAMPLE_OBJECT_INFO,
        {**SAMPLE_OBJECT_INFO, "MyCustomNode": {"output": [], "output_name": []}},
    ]
    inst = MagicMock()
    inst.get.return_value = resp
    mock_client_class.return_value.__enter__.return_value = inst

    client = ComfyUIClient(base_url="http://test:8188")
    before = client.get_object_info()
    after = client.get_object_info(force_refresh=True)

    assert "MyCustomNode" not in before
    assert "MyCustomNode" in after
    assert inst.get.call_count == 2


# --- API 端點 -------------------------------------------------------------


def _override_comfy() -> MagicMock:
    fake = MagicMock()
    fake.get_object_info.return_value = SAMPLE_OBJECT_INFO
    return fake


def test_search_endpoint_returns_name_and_category() -> None:
    fake = _override_comfy()
    app.dependency_overrides[get_comfy_client] = lambda: fake
    try:
        from fastapi.testclient import TestClient

        c = TestClient(app)
        r = c.get("/api/comfyui/nodes", params={"query": "KSampler"})
        assert r.status_code == 200
        body = r.json()
        assert _names(body["nodes"]) == ["KSampler", "KSamplerAdvanced"]
        assert body["nodes"][0] == {"name": "KSampler", "category": "sampling"}
        assert body["total"] == 2
    finally:
        app.dependency_overrides.pop(get_comfy_client, None)


def test_search_endpoint_rejects_no_filter() -> None:
    fake = _override_comfy()
    app.dependency_overrides[get_comfy_client] = lambda: fake
    try:
        from fastapi.testclient import TestClient

        c = TestClient(app)
        r = c.get("/api/comfyui/nodes")  # 無 query、無 category
        assert r.status_code == 400
        fake.get_object_info.assert_not_called()  # 連 object_info 都不抓
    finally:
        app.dependency_overrides.pop(get_comfy_client, None)


def test_search_endpoint_filters_by_category() -> None:
    fake = _override_comfy()
    app.dependency_overrides[get_comfy_client] = lambda: fake
    try:
        from fastapi.testclient import TestClient

        c = TestClient(app)
        r = c.get("/api/comfyui/nodes", params={"category": "loaders"})
        assert r.status_code == 200
        assert _names(r.json()["nodes"]) == ["CLIPLoader", "CheckpointLoaderSimple"]
    finally:
        app.dependency_overrides.pop(get_comfy_client, None)


def test_search_endpoint_caps_results_and_flags_truncated() -> None:
    big = {f"Node{i:03d}": {"output": [], "output_name": [], "category": "x"} for i in range(120)}
    fake = MagicMock()
    fake.get_object_info.return_value = big
    app.dependency_overrides[get_comfy_client] = lambda: fake
    try:
        from fastapi.testclient import TestClient

        c = TestClient(app)
        r = c.get("/api/comfyui/nodes", params={"category": "x", "limit": 50})
        body = r.json()
        assert body["total"] == 120
        assert body["returned"] == 50
        assert len(body["nodes"]) == 50
        assert body["truncated"] is True
        assert body["next_offset"] == 50
    finally:
        app.dependency_overrides.pop(get_comfy_client, None)


def test_search_endpoint_paging_reaches_tail() -> None:
    big = {f"Node{i:03d}": {"output": [], "output_name": [], "category": "x"} for i in range(120)}
    fake = MagicMock()
    fake.get_object_info.return_value = big
    app.dependency_overrides[get_comfy_client] = lambda: fake
    try:
        from fastapi.testclient import TestClient

        c = TestClient(app)
        seen: list[str] = []
        offset = 0
        while True:
            body = c.get(
                "/api/comfyui/nodes", params={"category": "x", "limit": 50, "offset": offset}
            ).json()
            seen += _names(body["nodes"])
            if not body["truncated"]:
                break
            offset = body["next_offset"]
        # 翻頁後拿得到全部 120 個，含原本被截掉的尾巴
        assert len(seen) == 120
        assert "Node119" in seen
    finally:
        app.dependency_overrides.pop(get_comfy_client, None)


def test_categories_endpoint_lists_counts() -> None:
    fake = _override_comfy()
    app.dependency_overrides[get_comfy_client] = lambda: fake
    try:
        from fastapi.testclient import TestClient

        c = TestClient(app)
        r = c.get("/api/comfyui/node-categories")
        assert r.status_code == 200
        cats = {c["category"]: c["count"] for c in r.json()["categories"]}
        assert cats["sampling"] == 2
    finally:
        app.dependency_overrides.pop(get_comfy_client, None)


def test_schema_endpoint_returns_node_schema() -> None:
    fake = _override_comfy()
    app.dependency_overrides[get_comfy_client] = lambda: fake
    try:
        from fastapi.testclient import TestClient

        c = TestClient(app)
        r = c.get("/api/comfyui/nodes/KSampler")
        assert r.status_code == 200
        assert r.json()["node_type"] == "KSampler"
    finally:
        app.dependency_overrides.pop(get_comfy_client, None)


def test_schema_endpoint_unknown_node_404() -> None:
    fake = _override_comfy()
    app.dependency_overrides[get_comfy_client] = lambda: fake
    try:
        from fastapi.testclient import TestClient

        c = TestClient(app)
        r = c.get("/api/comfyui/nodes/NopeNode")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_comfy_client, None)
