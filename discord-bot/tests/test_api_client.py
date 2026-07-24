import httpx
import pytest

from bot.api_client import ApiClient, BackendError


def make_api(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return ApiClient("http://test", client=client)


async def test_list_presets():
    def handler(req):
        assert req.url.path == "/api/style-presets/"
        return httpx.Response(200, json={"items": [{"id": "a", "name": "A", "profiles": []}]})

    api = make_api(handler)
    items = await api.list_presets()
    assert items[0]["id"] == "a"


async def test_compose_sends_overrides_and_returns_generation():
    def handler(req):
        assert req.url.path == "/api/style-presets/p1/compose"
        import json

        body = json.loads(req.content)
        assert body["content_prompt"] == "a cat"
        assert body["profile"] == "day"
        assert body["overrides"] == {"width": 1024, "height": 768, "batch_size": 6}
        return httpx.Response(200, json={"preset_id": "p1", "profile": "day", "generation": {"prompt": "x", "batch_size": 6}})

    api = make_api(handler)
    gen = await api.compose("p1", content_prompt="a cat", profile="day", overrides={"width": 1024, "height": 768, "batch_size": 6})
    assert gen == {"prompt": "x", "batch_size": 6}


async def test_submit_generate_returns_job_id():
    def handler(req):
        assert req.url.path == "/api/generate/"
        return httpx.Response(201, json={"job_id": "job-123", "status": "queued"})

    api = make_api(handler)
    assert await api.submit_generate({"prompt": "x"}) == "job-123"


async def test_get_job():
    def handler(req):
        assert req.url.path == "/api/generate/job/job-123"
        return httpx.Response(200, json={"status": "running", "job_id": "job-123"})

    api = make_api(handler)
    assert (await api.get_job("job-123"))["status"] == "running"


async def test_list_job_images_filters_by_job_prefix():
    def handler(req):
        assert req.url.path == "/api/gallery/"
        assert req.url.params["image_name"] == "job-1234"
        assert req.url.params["limit"] == "8"
        return httpx.Response(200, json={"items": [{"id": 1, "image_url": "/gallery/x.png"}], "total": 1})

    api = make_api(handler)
    items = await api.list_job_images("job-1234-abcd-efgh")
    assert items[0]["image_url"] == "/gallery/x.png"


async def test_download_returns_bytes():
    def handler(req):
        assert req.url.path == "/gallery/x.png"
        return httpx.Response(200, content=b"PNGDATA")

    api = make_api(handler)
    assert await api.download("/gallery/x.png") == b"PNGDATA"


async def test_backend_error_maps_detail_message():
    def handler(req):
        return httpx.Response(404, json={"detail": "找不到風格 preset: p9"})

    api = make_api(handler)
    with pytest.raises(BackendError) as e:
        await api.compose("p9", content_prompt="x")
    assert e.value.status_code == 404
    assert "找不到風格 preset" in str(e.value)


async def test_backend_error_maps_dict_detail_message():
    def handler(req):
        return httpx.Response(422, json={"detail": {"message": "bad profile", "error": "x"}})

    api = make_api(handler)
    with pytest.raises(BackendError) as e:
        await api.get_job("j")
    assert e.value.status_code == 422
    assert "bad profile" in str(e.value)


async def test_backend_error_maps_dict_detail_error_fallback():
    def handler(req):
        return httpx.Response(500, json={"detail": {"error": "boom"}})

    api = make_api(handler)
    with pytest.raises(BackendError) as e:
        await api.get_job("j")
    assert "boom" in str(e.value)


async def test_compose_omits_profile_and_overrides_when_none():
    seen = {}

    def handler(req):
        import json

        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"preset_id": "p", "profile": None, "generation": {"prompt": "x"}})

    api = make_api(handler)
    await api.compose("p", content_prompt="hi")
    assert seen["body"] == {"content_prompt": "hi"}
    assert "profile" not in seen["body"]
    assert "overrides" not in seen["body"]
