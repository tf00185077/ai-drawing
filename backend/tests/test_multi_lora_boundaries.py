"""Connected complete-set contract through the real HTTP adapter and queue compiler.

Only the execution client is replaced. No app lifespan, worker, or real prompt runs.
Set MULTI_LORA_HTTP_EXPORT to retain this run's HTTP/compiled evidence for MCP.
"""
from contextlib import asynccontextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.core import queue, workflow
from app.core.style_presets import _parse_preset, compose_preset
from app.core.workflow import apply_params, load_template
from app.main import app

FIXTURE = Path(__file__).parent / "fixtures" / "multi_lora_connected.json"
CONTRACT = json.loads(FIXTURE.read_text())
LOADERS = ("z", "a", "m")  # Deliberately differs from sorted node-id order.


def _assert_no_dangling_links(graph):
    def check(value):
        if isinstance(value, list):
            if len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
                assert value[0] in graph, value
            else:
                for item in value:
                    check(item)
        elif isinstance(value, dict):
            for item in value.values():
                check(item)
    for node in graph.values():
        check(node["inputs"])


def _assert_compiled(graph, case):
    active = [key for key in graph if key in LOADERS]
    assert active == case["active"]
    assert [graph[key]["inputs"]["lora_name"] for key in active] == case["names"]
    for key in ("k", "second"):
        assert graph[key]["inputs"]["model"] == case["model"]
    for key in ("positive", "negative"):
        assert graph[key]["inputs"]["clip"] == case["clip"]
    _assert_no_dangling_links(graph)


@pytest.mark.parametrize("kind", ["ordinary", "mixed", "model_only"])
@pytest.mark.parametrize("case", CONTRACT["cases"], ids=lambda case: case["id"])
def test_connected_complete_set_and_immutable_inputs(kind, case):
    """Catches prefix retention, truncation, id sorting and broken tail/CLIP bypass."""
    original = deepcopy(CONTRACT["workflow"])
    if kind in ("mixed", "model_only"):
        keys = ("a",) if kind == "mixed" else LOADERS
        for key in keys:
            original[key]["class_type"] = "LoraLoaderModelOnly"
            original[key]["inputs"].pop("clip")
            original[key]["inputs"].pop("strength_clip")
        original["m"]["inputs"]["clip"] = ["z", 1] if kind == "mixed" else ["base", 1]
        if kind == "model_only":
            original["m"]["inputs"].pop("clip")
            for key in ("positive", "negative"):
                original[key]["inputs"]["clip"] = ["base", 1]
    before = deepcopy(original)
    request = deepcopy(case["overrides"])
    if case.get("error"):
        with pytest.raises(ValueError, match="defines 4 LoRAs but workflow has 3 loader"):
            apply_params(original, **request)
    else:
        result = apply_params(original, **request)
        want = deepcopy(case)
        if kind == "model_only":
            want["clip"] = ["base", 1]
        _assert_compiled(result, want)
        # Each retained loader preserves its upstream model; CLIP is independent.
        for index, key in enumerate(want["active"]):
            assert result[key]["inputs"]["model"] == (["base", 0] if index == 0 else [LOADERS[index-1], 0])
            if result[key]["class_type"] == "LoraLoaderModelOnly":
                assert "strength_clip" not in result[key]["inputs"]
            else:
                upstream = "base" if index == 0 else ("z" if kind == "mixed" else LOADERS[index-1])
                assert result[key]["inputs"]["clip"] == [upstream, 1]
                if case["id"] == "exact":
                    assert result[key]["inputs"]["strength_model"] == [0.6, 1.0, 0.3][index]
                    assert result[key]["inputs"]["strength_clip"] == [0.6, 1.0, 0.2][index]
        # Deep copy, including nested values, not just the outer dictionary.
        result["positive"]["inputs"]["clip"][0] = "changed"
    assert original == before
    assert request == case["overrides"]


def test_existing_preset_composes_only_selected_model_only_loras():
    """A real two-LoRA recipe must not retain the template's third loader."""
    root = Path(__file__).resolve().parents[2]
    path = root / "style_presets/agent/presets/anima-shattered-dreams-detailer-candidate.json"
    params = compose_preset(_parse_preset(json.loads(path.read_text())), "contract").generation
    original = load_template(params.pop("template"))
    before = deepcopy(original)
    graph = apply_params(original, **params)
    loaders = [node for node in graph.values() if node["class_type"].startswith("LoraLoader")]
    assert [node["inputs"]["lora_name"] for node in loaders] == [
        "ShatteredDreams.safetensors", "Detailer-AnimeBooster.safetensors"]
    assert [node["inputs"]["strength_model"] for node in loaders] == [0.5, 0.5]
    assert all("strength_clip" not in node["inputs"] for node in loaders)
    assert "12" not in graph
    assert graph["7"]["inputs"]["model"] == ["11", 0]
    assert original == before
    _assert_no_dangling_links(graph)


class CaptureExecution:
    def __init__(self):
        self.graphs = []

    def submit_prompt(self, graph):
        self.graphs.append(deepcopy(graph))
        return "offline-intercepted-prompt"

    def __getattr__(self, name):
        raise AssertionError("Unexpected execution operation: " + name)


def test_http_queue_compilation_and_export(monkeypatch, tmp_path):
    """Real route/validation/queue/compiler; intercept only the execution boundary."""
    @asynccontextmanager
    async def forbidden_lifespan(_app):
        raise AssertionError("App lifespan must not run")
        yield

    monkeypatch.setattr(app.router, "lifespan_context", forbidden_lifespan)
    monkeypatch.setattr(queue, "start_worker", lambda: pytest.fail("Worker must not start"))
    original = deepcopy(CONTRACT["workflow"])
    (tmp_path / "offline-contract.json").write_text(json.dumps(original))
    monkeypatch.setattr(workflow, "WORKFLOWS_DIR", tmp_path)
    exports = []
    queue._reset_for_test()
    try:
        client = TestClient(app)  # No context manager: no lifespan/background worker.
        for route in ("/api/generate/", "/api/generate/custom"):
            for case in CONTRACT["cases"]:
                queue._reset_for_test()
                request = {"prompt": "contract", "checkpoint": "base.safetensors", "seed": 42,
                           "batch_size": 1, "execution_target": "worker", **deepcopy(case["overrides"])}
                if case["id"] in ("empty", "short"):
                    request["prompt"] = "contract, mapped style"
                if route.endswith("custom"):
                    request["workflow"] = deepcopy(original)
                else:
                    request["template"] = "offline-contract"
                before = deepcopy(request)
                response = client.post(route, json=request)
                assert response.status_code == 201, response.text
                job_id = response.json()["job_id"]
                pending = queue._pending[0]
                if case["overrides"].get("loras") is not None:
                    assert pending.params["loras"] == [
                        {"strength_model": 1.0, **spec}
                        for spec in case["overrides"]["loras"]
                    ]
                else:
                    assert "loras" not in pending.params
                execution = CaptureExecution()
                queue._process_pending(execution)
                status = client.get("/api/generate/job/" + job_id)
                assert status.status_code == 200
                graph = execution.graphs[0] if execution.graphs else None
                if case.get("error"):
                    assert graph is None  # No truncated request reaches execution.
                    assert status.json()["status"] == "failed"
                    assert "defines 4 LoRAs but workflow has 3 loader" in status.json()["error"]
                    assert status.json()["failure_code"] == "submission_failed"
                else:
                    assert len(execution.graphs) == 1
                    assert status.json()["status"] == "running"
                    _assert_compiled(graph, case)
                    assert graph["k"]["inputs"]["seed"] == 42
                assert request == before
                assert CONTRACT["workflow"] == original
                exports.append({"case": case["id"], "path": route, "request": request,
                                "post_status": response.status_code, "post": response.json(),
                                "get_status": status.status_code, "get": status.json(), "compiled": graph})
        destination = os.environ.get("MULTI_LORA_HTTP_EXPORT")
        if destination:
            Path(destination).write_text(json.dumps({"version": 1,
                "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                "producer": "backend/tests/test_multi_lora_boundaries.py::test_http_queue_compilation_and_export",
                "no_lifespan": True, "execution": "intercepted; no compute", "exchanges": exports}, indent=2) + "\n")
    finally:
        queue._reset_for_test()
