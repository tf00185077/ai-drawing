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


async def test_prompt_defaults_are_composed_from_selected_preset_and_profile():
    def handler(req):
        import json

        assert req.url.path == "/api/style-presets/p/compose"
        assert json.loads(req.content) == {"content_prompt": " ", "profile": "portrait"}
        return httpx.Response(
            200,
            json={
                "preset_id": "p",
                "profile": "portrait",
                "generation": {
                    "prompt": "preset positive",
                    "negative_prompt": "preset negative",
                },
            },
        )

    api = make_api(handler)
    assert await api.get_prompt_defaults("p", "portrait") == (
        "preset positive",
        "preset negative",
    )


async def test_compose_and_submit_overrides_full_edited_prompts():
    calls = {}

    def handler(req):
        import json

        if req.url.path.endswith("/compose"):
            body = json.loads(req.content)
            calls["content_prompt"] = body["content_prompt"]
            calls["overrides"] = body["overrides"]
            return httpx.Response(200, json={"preset_id": "p", "profile": None, "generation": {"prompt": "x"}})
        if req.url.path == "/api/generate/":
            calls["generation"] = json.loads(req.content)
            return httpx.Response(201, json={"job_id": "J1", "status": "queued"})
        raise AssertionError(req.url.path)

    api = make_api(handler)
    job_id = await api.compose_and_submit(
        "p", None, "edited positive", "edited negative", 800, 600, 3
    )
    assert job_id == "J1"
    assert calls["content_prompt"] == " "
    assert calls["overrides"] == {
        "prompt": "edited positive",
        "negative_prompt": "edited negative",
        "width": 800,
        "height": 600,
        "batch_size": 3,
    }
    assert calls["generation"]["batch_seed_mode"] == "independent"


async def test_compose_and_submit_allows_user_to_clear_negative_prompt():
    calls = {}

    def handler(req):
        import json

        if req.url.path.endswith("/compose"):
            calls["overrides"] = json.loads(req.content)["overrides"]
            return httpx.Response(
                200,
                json={"preset_id": "p", "profile": None, "generation": {"prompt": "x"}},
            )
        if req.url.path == "/api/generate/":
            return httpx.Response(201, json={"job_id": "J2", "status": "queued"})
        raise AssertionError(req.url.path)

    api = make_api(handler)
    job_id = await api.compose_and_submit("p", None, "edited positive", "", 512, 512, 1)
    assert job_id == "J2"
    assert calls["overrides"]["negative_prompt"] == ""


async def test_collect_job_result_running():
    def handler(req):
        return httpx.Response(200, json={"status": "running"})

    api = make_api(handler)
    assert await api.collect_job_result("J1") == {"status": "running"}


async def test_collect_job_result_failed():
    def handler(req):
        return httpx.Response(200, json={"status": "failed", "error": "boom", "node_errors": ["n1"]})

    api = make_api(handler)
    out = await api.collect_job_result("J1")
    assert out["status"] == "failed"
    assert out["node_errors"] == ["n1"]


async def test_collect_job_result_completed_downloads_all():
    def handler(req):
        if req.url.path == "/api/generate/job/J1abcd99":
            return httpx.Response(200, json={"status": "completed", "image_id": 1})
        if req.url.path == "/api/gallery/":
            return httpx.Response(200, json={"items": [
                {"id": 1, "image_url": "/gallery/a.png"},
                {"id": 2, "image_url": "/gallery/b.png"},
            ], "total": 2})
        if req.url.path == "/gallery/a.png":
            return httpx.Response(200, content=b"AAA")
        if req.url.path == "/gallery/b.png":
            return httpx.Response(200, content=b"BBB")
        raise AssertionError(req.url.path)

    api = make_api(handler)
    out = await api.collect_job_result("J1abcd99")
    assert out["status"] == "completed"
    assert [name for name, _ in out["images"]] == ["a.png", "b.png"]
    assert [data for _, data in out["images"]] == [b"AAA", b"BBB"]
    assert out["urls"] == ["http://test/gallery/a.png", "http://test/gallery/b.png"]


async def test_collect_job_result_prefers_saveimage_artifacts_over_preview_images():
    job_id = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"

    def handler(req):
        if req.url.path == f"/api/generate/job/{job_id}":
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "artifacts": [
                        {
                            "source_node_type": "SaveImage",
                            "mime_type": "image/png",
                            "gallery_path": "2026-07-24/final_0.png",
                        },
                        {
                            "source_node_type": "PreviewImage",
                            "mime_type": "image/png",
                            "gallery_path": "2026-07-24/preview_0.png",
                        },
                    ],
                },
            )
        if req.url.path == "/gallery/2026-07-24/final_0.png":
            return httpx.Response(200, content=b"FINAL")
        if req.url.path == "/api/gallery/":
            raise AssertionError("artifact metadata should avoid the prefix gallery fallback")
        if "preview" in req.url.path:
            raise AssertionError("PreviewImage must not be delivered")
        raise AssertionError(req.url.path)

    api = make_api(handler)
    out = await api.collect_job_result(job_id)

    assert out["status"] == "completed"
    assert out["images"] == [("final_0.png", b"FINAL")]
    assert out["urls"] == ["http://test/gallery/2026-07-24/final_0.png"]


async def test_independent_preview_only_result_never_uses_legacy_gallery_fallback():
    job_id = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"

    def handler(req):
        if req.url.path == f"/api/generate/job/{job_id}":
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "batch_total": 1,
                    "batch_completed": 1,
                    "batch_failed": 0,
                    "artifacts": [
                        {
                            "source_node_type": "PreviewImage",
                            "mime_type": "image/png",
                            "gallery_path": "2026-07-25/preview-only.png",
                        }
                    ],
                },
            )
        if req.url.path == "/api/gallery/":
            raise AssertionError(
                "independent jobs must not re-enter legacy Gallery fallback"
            )
        if "preview-only" in req.url.path:
            raise AssertionError("PreviewImage must not be delivered")
        raise AssertionError(req.url.path)

    api = make_api(handler)
    out = await api.collect_job_result(job_id)

    assert out["status"] == "completed"
    assert out["images"] == []
    assert out["urls"] == []


async def test_collect_job_result_returns_mixed_counts_and_failed_members():
    job_id = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"

    def handler(req):
        if req.url.path == f"/api/generate/job/{job_id}":
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "batch_total": 4,
                    "batch_completed": 3,
                    "batch_failed": 1,
                    "failed_members": [
                        {
                            "batch_index": 1,
                            "seed": 22,
                            "code": "comfyui_execution_error",
                            "message": "ComfyUI execution error",
                        }
                    ],
                    "artifacts": [
                        {
                            "source_node_type": "SaveImage",
                            "mime_type": "image/png",
                            "gallery_path": f"2026-07-25/final-{index}.png",
                            "batch_index": index,
                        }
                        for index in (0, 2, 3)
                    ]
                    + [
                        {
                            "source_node_type": "PreviewImage",
                            "mime_type": "image/png",
                            "gallery_path": "2026-07-25/preview.png",
                            "batch_index": 0,
                        }
                    ],
                },
            )
        if req.url.path.startswith("/gallery/2026-07-25/final-"):
            return httpx.Response(200, content=b"FINAL")
        if "preview" in req.url.path:
            raise AssertionError("PreviewImage must not be delivered")
        raise AssertionError(req.url.path)

    api = make_api(handler)
    out = await api.collect_job_result(job_id)

    assert out["status"] == "completed"
    assert len(out["images"]) == 3
    assert out["batch_total"] == 4
    assert out["batch_completed"] == 3
    assert out["batch_failed"] == 1
    assert out["failed_members"] == [
        {
            "batch_index": 1,
            "seed": 22,
            "code": "comfyui_execution_error",
            "message": "ComfyUI execution error",
        }
    ]


async def test_collect_job_result_unknown_status_does_not_download():
    calls = {"gallery": 0}

    def handler(req):
        if req.url.path.startswith("/api/generate/job/"):
            return httpx.Response(200, json={"status": "weird"})
        if req.url.path == "/api/gallery/":
            calls["gallery"] += 1
            return httpx.Response(200, json={"items": [], "total": 0})
        raise AssertionError(req.url.path)

    api = make_api(handler)
    out = await api.collect_job_result("Jxxxxxxx")
    assert out == {"status": "weird"}
    assert calls["gallery"] == 0


async def test_collect_job_result_completed_skips_items_without_image_url():
    def handler(req):
        if req.url.path.startswith("/api/generate/job/"):
            return httpx.Response(200, json={"status": "completed"})
        if req.url.path == "/api/gallery/":
            return httpx.Response(200, json={"items": [
                {"id": 1, "image_url": "/gallery/a.png"},
                {"id": 2},
            ], "total": 2})
        if req.url.path == "/gallery/a.png":
            return httpx.Response(200, content=b"AAA")
        raise AssertionError(req.url.path)

    api = make_api(handler)
    out = await api.collect_job_result("Jyyyyyyy")
    assert [n for n, _ in out["images"]] == ["a.png"]
    assert out["urls"] == ["http://test/gallery/a.png"]
