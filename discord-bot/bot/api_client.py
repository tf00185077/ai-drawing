"""backend HTTP 包裝——唯一知道 backend 契約的地方。"""
import httpx

from .validation import build_gallery_download_url


class BackendError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except Exception:
        return response.text or f"HTTP {response.status_code}"
    if isinstance(data, dict):
        detail = data.get("detail", data)
        if isinstance(detail, dict):
            return detail.get("message") or detail.get("error") or str(detail)
        return str(detail)
    return str(data)


class ApiClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None):
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(base_url=self._base_url, timeout=30.0)

    def _check(self, response: httpx.Response) -> httpx.Response:
        if response.status_code >= 400:
            raise BackendError(_error_message(response), status_code=response.status_code)
        return response

    async def list_presets(self) -> list[dict]:
        r = self._check(await self._client.get("/api/style-presets/"))
        return r.json().get("items", [])

    async def compose(self, preset_id: str, *, content_prompt: str,
                      profile: str | None = None, overrides: dict | None = None) -> dict:
        body: dict = {"content_prompt": content_prompt}
        if profile:
            body["profile"] = profile
        if overrides:
            body["overrides"] = overrides
        r = self._check(await self._client.post(f"/api/style-presets/{preset_id}/compose", json=body))
        return r.json()["generation"]

    async def get_prompt_defaults(
        self, preset_id: str, profile: str | None
    ) -> tuple[str, str]:
        generation = await self.compose(
            preset_id,
            content_prompt=" ",
            profile=profile,
        )
        return (
            str(generation.get("prompt") or ""),
            str(generation.get("negative_prompt") or ""),
        )

    async def submit_generate(self, generation: dict) -> str:
        r = self._check(await self._client.post("/api/generate/", json=generation))
        return r.json()["job_id"]

    async def get_job(self, job_id: str) -> dict:
        r = self._check(await self._client.get(f"/api/generate/job/{job_id}"))
        return r.json()

    async def list_job_images(self, job_id: str) -> list[dict]:
        r = self._check(await self._client.get(
            "/api/gallery/", params={"image_name": job_id[:8], "limit": 8}
        ))
        return r.json().get("items", [])

    async def download(self, image_url: str) -> bytes:
        r = self._check(await self._client.get(image_url))
        return r.content

    async def compose_and_submit(self, preset_id: str, profile: str | None,
                                 positive_prompt: str, negative_prompt: str,
                                 width: int, height: int, count: int) -> str:
        overrides: dict[str, object] = {
            "prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "batch_size": count,
        }
        generation = await self.compose(
            preset_id,
            content_prompt=" ",
            profile=profile,
            overrides=overrides,
        )
        return await self.submit_generate(generation)

    async def collect_job_result(self, job_id: str) -> dict:
        job = await self.get_job(job_id)
        status = job.get("status")
        if status in ("queued", "running"):
            return {"status": status}
        if status == "failed":
            return {
                "status": "failed",
                "error": job.get("error"),
                "node_errors": job.get("node_errors", []),
            }
        if status != "completed":
            return {"status": status}
        items = await self.list_job_images(job_id)
        images: list[tuple[str, bytes]] = []
        urls: list[str] = []
        for item in items:
            image_url = item.get("image_url")
            if not image_url:
                continue
            data = await self.download(image_url)
            filename = image_url.rsplit("/", 1)[-1]
            images.append((filename, data))
            urls.append(build_gallery_download_url(self._base_url, image_url))
        return {"status": "completed", "images": images, "urls": urls}
