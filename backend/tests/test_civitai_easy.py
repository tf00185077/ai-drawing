"""Best-effort Civitai flow tests: digest cache, sampler mapping, planning, generate-like, acquire."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.civitai_easy as easy
import app.services.civitai_resource_acquire as acquire
from app.db.models import DownloadedResource
from app.services.civitai_easy import EasyGenerateError, generate_like, plan_generation
from app.services.civitai_resource_acquire import (
    AcquireError,
    acquisition_status,
    choose_file,
    license_snapshot,
    normalize_model_family,
    resolve_version_metadata,
    start_acquisition,
)
from app.services.civitai_sampling import split_sampler_scheduler
from app.services.file_digest_cache import record_sha256, sha256_for


# --- file digest cache -----------------------------------------------------


def test_digest_cache_hashes_once_until_identity_changes(tmp_path, monkeypatch) -> None:
    target = tmp_path / "model.safetensors"
    target.write_bytes(b"weights-v1")
    cache = tmp_path / "cache.json"

    calls = {"count": 0}
    real = sha256_for.__globals__["_stream_sha256"]

    def counting(path):
        calls["count"] += 1
        return real(path)

    monkeypatch.setitem(sha256_for.__globals__, "_stream_sha256", counting)
    first = sha256_for(target, cache_file=cache)
    second = sha256_for(target, cache_file=cache)
    assert first == second == hashlib.sha256(b"weights-v1").hexdigest()
    assert calls["count"] == 1

    target.write_bytes(b"weights-v2-different")
    third = sha256_for(target, cache_file=cache)
    assert third == hashlib.sha256(b"weights-v2-different").hexdigest()
    assert calls["count"] == 2


def test_digest_cache_survives_reload_from_disk(tmp_path, monkeypatch) -> None:
    target = tmp_path / "model.safetensors"
    target.write_bytes(b"payload")
    cache = tmp_path / "cache.json"
    record_sha256(target, "AB" * 32, cache_file=cache)

    import app.services.file_digest_cache as cache_module

    monkeypatch.setattr(cache_module, "_MEMORY", {})
    monkeypatch.setattr(cache_module, "_LOADED_PATH", None)
    assert sha256_for(target, cache_file=cache) == "ab" * 32


# --- sampler mapping ---------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Euler a", ("euler_ancestral", None)),
        ("DPM++ 2M Karras", ("dpmpp_2m", "karras")),
        ("DPM++ 2M SDE Exponential", ("dpmpp_2m_sde", "exponential")),
        ("UniPC", ("uni_pc", None)),
        ("dpmpp_2m", ("dpmpp_2m", None)),  # native ComfyUI names pass through
        ("Restart", ("Restart", None)),  # unknown labels pass through unchanged
    ],
)
def test_split_sampler_scheduler(label: str, expected: tuple[str, str | None]) -> None:
    assert split_sampler_scheduler(label) == expected


# --- planning ---------------------------------------------------------------


def _recipe(**overrides):
    payload = {
        "schema_version": "1.0",
        "source": {"provider": "civitai", "image_id": 130519340},
        "base_prompt": "1girl, rooftop, night city",
        "negative_prompt": "lowres, bad anatomy",
        "resources": [
            {"kind": "checkpoint", "name": "novaAnimeXL_ilV190.safetensors",
             "civitai_model_id": 376130, "civitai_model_version_id": 2940478},
        ],
        "sampling": {"sampler": "DPM++ 2M Karras", "steps": 28, "cfg": 5.5, "width": 832, "height": 1216, "seed": 42},
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def local_resources(monkeypatch):
    monkeypatch.setattr(easy, "list_checkpoints", lambda settings: ["novaAnimeXL_ilV190.safetensors"])
    monkeypatch.setattr(easy, "list_loras", lambda settings: ["style-a.safetensors"])
    monkeypatch.setattr(easy, "default_checkpoint", lambda settings: "novaAnimeXL_ilV190.safetensors")
    monkeypatch.setattr(easy, "local_identity_ledger", lambda db: SimpleNamespace(entries=[]))


def test_plan_matches_checkpoint_by_filename_and_maps_sampler(local_resources) -> None:
    plan = plan_generation(_recipe(), db=None)
    assert plan["checkpoint"] == "novaAnimeXL_ilV190.safetensors"
    assert plan["sampler_name"] == "dpmpp_2m"
    assert plan["scheduler"] == "karras"
    assert plan["steps"] == 28 and plan["cfg"] == 5.5
    assert plan["needs_download"] == [] and plan["substitutions"] == []


def test_plan_marks_missing_checkpoint_downloadable(local_resources) -> None:
    recipe = _recipe(resources=[{
        "kind": "checkpoint", "name": "someoneElsesModel.safetensors",
        "civitai_model_id": 999, "civitai_model_version_id": 1234,
    }])
    plan = plan_generation(recipe, db=None)
    assert plan["needs_download"] == [{
        "kind": "checkpoint", "name": "someoneElsesModel.safetensors",
        "civitai_model_version_id": 1234, "civitai_model_id": 999,
    }]
    # A substitute is still planned so download_missing=false can generate immediately.
    assert plan["checkpoint"] == "novaAnimeXL_ilV190.safetensors"
    assert any("代替" in note for note in plan["substitutions"])


def test_plan_skips_unidentifiable_lora_with_warning(local_resources) -> None:
    recipe = _recipe(resources=[
        {"kind": "checkpoint", "name": "novaAnimeXL_ilV190.safetensors"},
        {"kind": "lora", "name": "mystery-style"},
    ])
    plan = plan_generation(recipe, db=None)
    assert plan["loras"] == []
    assert any("mystery-style" in warning for warning in plan["warnings"])


def test_plan_matches_lora_by_stem_and_keeps_strengths(local_resources) -> None:
    recipe = _recipe(resources=[
        {"kind": "checkpoint", "name": "novaAnimeXL_ilV190.safetensors"},
        {"kind": "lora", "name": "Style-A", "civitai_model_version_id": 777, "strength_model": 0.8},
    ])
    plan = plan_generation(recipe, db=None)
    assert plan["loras"] == [{"name": "style-a.safetensors", "strength_model": 0.8}]


def test_plan_clamps_out_of_range_sampling(local_resources) -> None:
    recipe = _recipe(sampling={"steps": 500, "cfg": 5.0, "width": 832, "height": 4096})
    plan = plan_generation(recipe, db=None)
    assert plan["steps"] == 150
    assert plan["height"] == 2048
    assert any("steps=500" in warning for warning in plan["warnings"])


def test_plan_without_any_local_checkpoint_fails_with_hint(monkeypatch) -> None:
    monkeypatch.setattr(easy, "list_checkpoints", lambda settings: [])
    monkeypatch.setattr(easy, "list_loras", lambda settings: [])
    monkeypatch.setattr(easy, "default_checkpoint", lambda settings: None)
    monkeypatch.setattr(easy, "local_identity_ledger", lambda db: SimpleNamespace(entries=[]))
    recipe = _recipe(resources=[])
    with pytest.raises(EasyGenerateError) as excinfo:
        plan_generation(recipe, db=None)
    assert excinfo.value.code == "no_local_checkpoint"
    assert excinfo.value.hint


# --- generate_like -----------------------------------------------------------


def _imported(recipe):
    return {"recipe": recipe, "reproduction_report": {}}


def test_generate_like_replaces_prompt_and_submits_batch(local_resources, monkeypatch) -> None:
    monkeypatch.setattr(easy, "import_recipe", lambda locator, **kwargs: _imported(_recipe()))
    submitted: dict = {}

    def fake_submit(params):
        submitted.update(params)
        return "job-42"

    result = generate_like("130519340", db=None, prompt="1boy, samurai, dawn", submit_fn=fake_submit)

    assert result["status"] == "queued" and result["job_id"] == "job-42"
    assert submitted["prompt"] == "1boy, samurai, dawn"
    assert submitted["negative_prompt"] == "lowres, bad anatomy"
    assert submitted["checkpoint"] == "novaAnimeXL_ilV190.safetensors"
    assert submitted["sampler_name"] == "dpmpp_2m" and submitted["scheduler"] == "karras"
    assert submitted["steps"] == 28 and submitted["cfg"] == 5.5
    assert submitted["width"] == 832 and submitted["height"] == 1216
    assert submitted["batch_size"] == 4  # default: the source image is one pick of many seeds


def test_generate_like_without_prompt_reuses_source_prompt(local_resources, monkeypatch) -> None:
    monkeypatch.setattr(easy, "import_recipe", lambda locator, **kwargs: _imported(_recipe()))
    captured: dict = {}
    generate_like("130519340", db=None, submit_fn=lambda params: captured.update(params) or "job-1")
    assert captured["prompt"] == "1girl, rooftop, night city"


def test_generate_like_acquires_missing_resources_before_generating(local_resources, monkeypatch) -> None:
    recipe = _recipe(resources=[{
        "kind": "checkpoint", "name": "otherModel.safetensors",
        "civitai_model_id": 999, "civitai_model_version_id": 1234,
    }])
    monkeypatch.setattr(easy, "import_recipe", lambda locator, **kwargs: _imported(recipe))
    acquired: list = []

    def fake_acquire(identity, **kwargs):
        acquired.append(identity)
        return {"status": "downloading", "resource": {"acquisition_id": 9}}

    result = generate_like("1", db=None, acquire_fn=fake_acquire, submit_fn=lambda p: pytest.fail("must not submit"))

    assert result["status"] == "acquiring_resources"
    assert acquired == [1234]
    assert "civitai_resource_status" in result["next_step"]


def test_generate_like_download_missing_false_substitutes_and_submits(local_resources, monkeypatch) -> None:
    recipe = _recipe(resources=[{
        "kind": "checkpoint", "name": "otherModel.safetensors",
        "civitai_model_id": 999, "civitai_model_version_id": 1234,
    }])
    monkeypatch.setattr(easy, "import_recipe", lambda locator, **kwargs: _imported(recipe))
    captured: dict = {}
    result = generate_like(
        "1", db=None, download_missing=False,
        submit_fn=lambda params: captured.update(params) or "job-2",
    )
    assert result["status"] == "queued"
    assert captured["checkpoint"] == "novaAnimeXL_ilV190.safetensors"
    assert any("otherModel" in note for note in result["substitutions"])


def test_generate_like_missing_prompt_everywhere_is_actionable(local_resources, monkeypatch) -> None:
    monkeypatch.setattr(easy, "import_recipe", lambda locator, **kwargs: _imported(_recipe(base_prompt=None)))
    with pytest.raises(EasyGenerateError) as excinfo:
        generate_like("1", db=None, submit_fn=lambda p: "job")
    assert excinfo.value.code == "prompt_missing"


# --- resource acquisition ----------------------------------------------------


def _version_payload(sha: str, size: int, scan: str = "Success") -> dict:
    return {
        "id": 2940478,
        "modelId": 376130,
        "name": "v1.90",
        "baseModel": "Illustrious",
        "model": {"type": "Checkpoint", "name": "Nova Anime XL"},
        "files": [{
            "id": 2819621,
            "name": "novaAnimeXL_ilV190.safetensors",
            "primary": True,
            "hashes": {"SHA256": sha.upper()},
            "sizeKB": size / 1024,
            "downloadUrl": "https://civitai.com/api/download/models/2940478",
            "virusScanResult": scan,
        }],
    }


class _FakeJsonTransport:
    def __init__(self, routes: dict[str, tuple[int, dict]]):
        self.routes = routes
        self.calls: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.calls.append(url)
        for fragment, response in self.routes.items():
            if fragment in url:
                return response
        return (404, {})


class _FakeDownloadTransport:
    def __init__(self, body: bytes):
        self.body = body

    def get(self, url: str, *, headers=None):
        return (200, self.body, {})


@pytest.fixture
def acquire_env(tmp_path, monkeypatch):
    roots = {key: tmp_path / key for key in ("checkpoints", "loras", "vae", "embeddings", "controlnet", "upscale_models")}
    settings = SimpleNamespace(
        civitai_authorization=None,
        file_digest_cache_path=str(tmp_path / "digests.json"),
        **{f"comfyui_{key}_dir": str(path) for key, path in roots.items()},
    )
    monkeypatch.setattr(acquire, "get_settings", lambda: settings)
    import app.services.file_digest_cache as cache_module
    monkeypatch.setattr(cache_module, "_MEMORY", {})
    monkeypatch.setattr(cache_module, "_LOADED_PATH", None)

    engine = create_engine(f"sqlite:///{tmp_path / 'acquire.db'}", connect_args={"check_same_thread": False})
    DownloadedResource.__table__.create(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield SimpleNamespace(session_factory=factory, tmp_path=tmp_path)


def test_bare_number_resolves_as_model_version_first(acquire_env) -> None:
    body = b"x" * 2048
    sha = hashlib.sha256(body).hexdigest()
    transport = _FakeJsonTransport({
        "model-versions/2940478": (200, _version_payload(sha, len(body))),
        "models/376130": (200, {"id": 376130, "type": "Checkpoint"}),
    })
    resolved = resolve_version_metadata("2940478", transport=transport)
    assert resolved["version"]["id"] == 2940478
    assert any("model-versions/2940478" in call for call in transport.calls)


def test_image_url_gets_a_helpful_hint(acquire_env) -> None:
    with pytest.raises(AcquireError) as excinfo:
        resolve_version_metadata("https://civitai.com/images/130519340")
    assert excinfo.value.code == "locator_is_not_a_model"
    assert "civitai_generate_like" in (excinfo.value.hint or "")


def test_choose_file_hard_fails_on_virus_scan(acquire_env) -> None:
    payload = _version_payload("ab" * 32, 2048, scan="Danger")
    with pytest.raises(AcquireError) as excinfo:
        choose_file(payload)
    assert excinfo.value.code == "virus_scan_not_clean"


def test_license_gaps_warn_but_do_not_block() -> None:
    snapshot, warnings = license_snapshot({"id": 1, "allowNoCredit": True})
    assert snapshot["license_verified"] is False
    assert warnings and "license_verified=false" in warnings[0]
    full, no_warnings = license_snapshot({
        "allowNoCredit": True, "allowCommercialUse": ["Image"],
        "allowDerivatives": True, "allowDifferentLicense": False,
    })
    assert full["license_verified"] is True and no_warnings == []


def test_normalize_model_family_maps_base_model_labels() -> None:
    assert normalize_model_family("Illustrious") == "illustrious"
    assert normalize_model_family("SDXL 1.0") == "sdxl"
    assert normalize_model_family("Pony") == "sdxl"
    assert normalize_model_family("SD 1.5") is None


def test_start_acquisition_downloads_verifies_and_records(acquire_env) -> None:
    body = b"x" * 2048
    sha = hashlib.sha256(body).hexdigest()
    transport = _FakeJsonTransport({
        "model-versions/2940478": (200, _version_payload(sha, len(body))),
        "models/376130": (200, {
            "id": 376130, "type": "Checkpoint",
            "allowNoCredit": True, "allowCommercialUse": ["Image"],
            "allowDerivatives": True, "allowDifferentLicense": False,
        }),
    })
    session = acquire_env.session_factory()
    result = start_acquisition(
        "2940478", db=session,
        metadata_transport=transport,
        download_transport=_FakeDownloadTransport(body),
        run_in_background=False,
        session_factory=acquire_env.session_factory,
    )
    assert result["status"] == "installed"
    resource = result["resource"]
    assert resource["sha256"] == sha
    assert resource["model_family"] == "illustrious"
    final = Path(resource["local_path"])
    assert final.read_bytes() == body
    assert final.parent == acquire_env.tmp_path / "checkpoints"

    # Second call dedupes against the installed row without downloading again.
    again = start_acquisition(
        "2940478", db=session, metadata_transport=transport,
        download_transport=_FakeDownloadTransport(b"must-not-be-used"),
        run_in_background=False, session_factory=acquire_env.session_factory,
    )
    assert again["status"] == "already_installed"
    session.close()


def test_start_acquisition_records_failure_on_sha_mismatch(acquire_env) -> None:
    body = b"x" * 2048
    transport = _FakeJsonTransport({
        "model-versions/2940478": (200, _version_payload("ab" * 32, len(body))),
        "models/376130": (200, {"id": 376130, "type": "Checkpoint"}),
    })
    session = acquire_env.session_factory()
    result = start_acquisition(
        "2940478", db=session, metadata_transport=transport,
        download_transport=_FakeDownloadTransport(body),
        run_in_background=False, session_factory=acquire_env.session_factory,
    )
    assert result["status"] == "failed"
    assert result["resource"]["error"]
    status = acquisition_status(session, acquisition_id=result["resource"]["acquisition_id"])
    assert status["resources"][0]["status"] == "failed"
    session.close()
