from __future__ import annotations

import json
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _compose() -> dict:
    return yaml.safe_load(
        (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )


def _binds(service: dict) -> dict[str, str]:
    return {
        volume["target"]: volume["source"]
        for volume in service.get("volumes", [])
        if isinstance(volume, dict) and volume.get("type") == "bind"
    }


def test_backend_uses_root_image_context_optional_env_and_generated_defaults() -> None:
    backend = _compose()["services"]["backend"]

    assert backend["build"] == {
        "context": ".",
        "dockerfile": "backend/Dockerfile",
    }
    assert backend["env_file"] == [{"path": ".env", "required": False}]
    assert backend["ports"] == ["127.0.0.1:${BACKEND_PORT:-8001}:8000"]
    assert backend["environment"]["COMFYUI_MODE"] == "${COMFYUI_MODE:-disabled}"
    assert backend["environment"]["DATABASE_URL"] == (
        "${DATABASE_URL:-sqlite:////data/database/auto_draw.db}"
    )
    assert backend["environment"]["PROMPT_LIBRARY_DIR"] == (
        "${PROMPT_LIBRARY_DIR:-/data/prompt_library}"
    )


def test_compose_persists_all_application_data_without_base_model_mounts() -> None:
    backend = _compose()["services"]["backend"]
    binds = _binds(backend)

    assert binds == {
        "/data/database": "./data/database",
        "/data/outputs": "./data/outputs",
        "/data/gallery": "./data/gallery",
        "/data/lora_train": "./data/lora_train",
        "/data/prompt_library": "./data/prompt_library",
        "/data/logs": "./data/logs",
    }
    assert not any(target.startswith("/comfyui/") for target in binds)


def test_compose_has_safe_lifecycle_health_dependency_and_linux_host_gateway() -> None:
    services = _compose()["services"]
    backend = services["backend"]
    frontend = services["frontend"]

    assert set(services) == {"backend", "frontend"}
    assert backend["extra_hosts"] == ["host.docker.internal:host-gateway"]
    assert backend["init"] is True
    assert backend["stop_grace_period"] == "10s"
    assert backend["healthcheck"]["test"][0] == "CMD"
    assert frontend["depends_on"] == {"backend": {"condition": "service_healthy"}}
    assert frontend["ports"] == ["127.0.0.1:${FRONTEND_PORT:-5173}:80"]
    assert frontend["init"] is True
    assert frontend["stop_grace_period"] == "10s"


def test_backend_image_contains_runtime_seed_and_exec_entrypoint() -> None:
    dockerfile = (PROJECT_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.11-slim")
    assert "COPY backend /workspace/backend" in dockerfile
    assert "COPY style_presets /workspace/style_presets" in dockerfile
    assert "COPY prompt_library /opt/ai-drawing-seed/prompt_library" in dockerfile
    assert 'ENTRYPOINT ["python", "scripts/docker_entrypoint.py"]' in dockerfile
    assert 'CMD ["uvicorn", "app.main:app"' in dockerfile


def test_nginx_proxies_api_and_gallery_to_backend() -> None:
    nginx = (PROJECT_ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")

    assert "location /api" in nginx
    assert "location = /gallery" in nginx
    assert "location /gallery/" in nginx
    assert "try_files $uri $uri/ /index.html;" in nginx
    assert nginx.count("proxy_pass http://backend:8000;") == 2


def test_root_dockerignore_excludes_secrets_runtime_and_large_tooling() -> None:
    patterns = {
        line.strip()
        for line in (PROJECT_ROOT / ".dockerignore")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {
        ".env",
        ".env.*",
        "**/secrets/",
        "*.pem",
        "*.key",
        "data/",
        "outputs/",
        "gallery/",
        "lora_train/",
        "sd-scripts/",
        ".ai-drawing/",
        "**/.file_sha256_cache.json",
        "**/node_modules/",
        "**/.venv/",
        "docs/",
        "experiments/",
        "mcp-server/",
    }.issubset(patterns)
    assert not {"backend/", "frontend/", "style_presets/", "prompt_library/"} & patterns


def test_frontend_lockfile_matches_package_identity() -> None:
    package = json.loads((PROJECT_ROOT / "frontend" / "package.json").read_text())
    lock = json.loads((PROJECT_ROOT / "frontend" / "package-lock.json").read_text())

    assert lock["lockfileVersion"] == 3
    assert lock["packages"][""]["name"] == package["name"]
    assert lock["packages"][""]["version"] == package["version"]


def test_frontend_build_uses_filtered_root_context_and_npm_ci() -> None:
    frontend = _compose()["services"]["frontend"]
    dockerfile = (PROJECT_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    assert frontend["build"] == {
        "context": ".",
        "dockerfile": "frontend/Dockerfile",
    }
    assert "COPY frontend/package*.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "COPY frontend/ ." in dockerfile
    assert "COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf" in dockerfile
