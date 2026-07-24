from __future__ import annotations

import copy
import json
from typing import cast
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import style_presets as style_presets_api
from app.core import queue
from app.core.comfyui import ComfyUIError
from app.core.queue import submit_saved_workflow
from app.core.style_presets import DirStylePresetProvider
from app.main import app


@pytest.fixture
def saved_graph() -> dict:
    return {
        "model": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "generic-family.safetensors",
                "weight_dtype": "default",
            },
        },
        "positive": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["clip", 0], "text": "ink wash, graphic lines"},
        },
        "negative": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["clip", 0], "text": "watermark"},
        },
        "clip": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "encoder-a.safetensors",
                "clip_name2": "encoder-b.safetensors",
                "type": "flux",
            },
        },
        "latent": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": 896, "height": 1152, "batch_size": 2},
        },
        "sampler": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["model", 0],
                "positive": ["positive", 0],
                "negative": ["negative", 0],
                "latent_image": ["latent", 0],
                "noise_seed": 456789,
                "steps": 27,
                "cfg": 4.5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "start_at_step": 0,
                "end_at_step": 27,
                "return_with_leftover_noise": "disable",
            },
        },
    }


class _CapturingComfy:
    def __init__(self) -> None:
        self.submitted: dict | None = None

    def submit_prompt(self, graph: dict) -> str:
        self.submitted = copy.deepcopy(graph)
        return "prompt-verbatim"


class _SequencedSubmitComfy:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.submitted: list[dict] = []

    def submit_prompt(self, graph: dict) -> str:
        self.submitted.append(copy.deepcopy(graph))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return cast(str, outcome)


def test_saved_workflow_queue_submits_deeply_equal_graph_without_apply_params(
    saved_graph,
) -> None:
    queue._reset_for_test()
    original = copy.deepcopy(saved_graph)
    comfy = _CapturingComfy()

    job_id = submit_saved_workflow(saved_graph)
    saved_graph["sampler"]["inputs"]["noise_seed"] = -1

    with (
        patch(
            "app.core.queue.apply_params",
            side_effect=AssertionError("apply_params must not run"),
        ) as apply_params,
        patch(
            "app.core.queue.get_settings",
            side_effect=AssertionError("defaults must not be read"),
        ),
    ):
        queue._process_pending(comfy)

    assert apply_params.call_count == 0
    assert comfy.submitted == original
    assert queue._running is not None
    assert queue._running.job_id == job_id
    assert queue._running.params["workflow"] == original
    assert queue._running.params["workflow_json"] == original
    assert queue._running.params["workflow_json"] is not comfy.submitted
    for forbidden in (
        "prompt",
        "negative_prompt",
        "seed",
        "steps",
        "cfg",
        "width",
        "height",
        "sampler_name",
        "scheduler",
        "checkpoint",
        "lora",
        "loras",
        "diffusion_model",
        "text_encoder",
        "vae",
    ):
        assert forbidden not in queue._running.params


def _non_json_http_status_error() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://comfy.invalid/prompt")
    response = httpx.Response(
        400,
        request=request,
        headers={"content-type": "text/html"},
        content=b"<html>bad request</html>",
    )
    return httpx.HTTPStatusError(
        "Client error '400 Bad Request' for url 'http://comfy.invalid/prompt'",
        request=request,
        response=response,
    )


@pytest.mark.parametrize(
    ("submit_error", "expected_error"),
    [
        (_non_json_http_status_error(), "400 Bad Request"),
        (KeyError("prompt_id"), "prompt_id"),
        (RuntimeError("unexpected submit failure"), "unexpected submit failure"),
    ],
    ids=["non-json-http-4xx", "missing-prompt-id", "unexpected-exception"],
)
def test_saved_workflow_submit_failure_is_terminal_and_next_job_proceeds(
    saved_graph,
    submit_error,
    expected_error,
) -> None:
    queue._reset_for_test()
    first_job_id = submit_saved_workflow(saved_graph)
    second_job_id = submit_saved_workflow(saved_graph)
    comfy = _SequencedSubmitComfy([submit_error, "prompt-after-failure"])

    queue._process_pending(comfy)

    failed = queue.get_job_status(first_job_id)
    assert failed is not None
    assert failed["status"] == "failed"
    assert expected_error in failed["error"]
    assert failed["node_errors"] == []
    assert failed["recording_error"] is None
    assert failed["is_custom"] is True
    assert queue._running is None
    assert [
        item["job_id"] for item in queue.get_status()["queue_pending"]
    ] == [second_job_id]

    queue._process_pending(comfy)

    next_status = queue.get_job_status(second_job_id)
    assert next_status is not None
    assert next_status["status"] == "running"
    assert next_status["prompt_id"] == "prompt-after-failure"
    assert queue._running is not None
    assert queue._running.job_id == second_job_id
    assert len(comfy.submitted) == 2


@pytest.mark.parametrize("malformed_prompt_id", [None, "", [], {}])
def test_saved_workflow_malformed_prompt_id_is_terminal_and_releases_slot(
    saved_graph, malformed_prompt_id
) -> None:
    queue._reset_for_test()
    first_job_id = submit_saved_workflow(saved_graph)
    second_job_id = submit_saved_workflow(saved_graph)
    comfy = _SequencedSubmitComfy(
        [malformed_prompt_id, "prompt-after-malformed"]
    )

    queue._process_pending(comfy)

    failed = queue.get_job_status(first_job_id)
    assert failed is not None
    assert failed["status"] == "failed"
    assert "prompt_id" in failed["error"]
    assert queue._running is None

    queue._process_pending(comfy)
    next_status = queue.get_job_status(second_job_id)
    assert next_status is not None
    assert next_status["prompt_id"] == "prompt-after-malformed"


def test_saved_workflow_malformed_node_errors_cannot_block_slot_release(
    saved_graph,
) -> None:
    queue._reset_for_test()
    first_job_id = submit_saved_workflow(saved_graph)
    second_job_id = submit_saved_workflow(saved_graph)
    malformed = ComfyUIError(
        "bad workflow",
        node_errors=cast(dict[str, str], ["not", "a", "mapping"]),
    )
    comfy = _SequencedSubmitComfy(
        [malformed, "prompt-after-malformed-errors"]
    )

    queue._process_pending(comfy)

    failed = queue.get_job_status(first_job_id)
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["node_errors"] == []
    assert queue._running is None

    queue._process_pending(comfy)
    next_status = queue.get_job_status(second_job_id)
    assert next_status is not None
    assert next_status["prompt_id"] == "prompt-after-malformed-errors"


def test_existing_custom_submission_still_uses_apply_params(saved_graph) -> None:
    queue._reset_for_test()
    comfy = _CapturingComfy()
    queue.submit_custom({"workflow": saved_graph, "prompt": "existing contract"})

    with (
        patch("app.core.queue.get_settings") as settings,
        patch(
            "app.core.queue.apply_params",
            return_value=copy.deepcopy(saved_graph),
        ) as apply_params,
    ):
        settings.return_value.gallery_dir = "."
        settings.return_value.controlnet_default_pose_image = ""
        settings.return_value.lora_sdxl = False
        queue._process_pending(comfy)

    apply_params.assert_called_once()
    assert apply_params.call_args.kwargs["prompt"] == "existing contract"


@pytest.fixture
def retest_client(tmp_path, saved_graph):
    agent_dir = tmp_path / "style_presets" / "agent"
    provider = DirStylePresetProvider(agent_dir, project_root=tmp_path)
    provider.create_preset(
        {
            "id": "creator-a",
            "name": "Creator A",
            "profiles": {"portrait": {"params": {"steps": 30}}},
        },
        create_note=False,
    )
    target = (
        agent_dir / "workflows" / "creator-a" / "portrait.api.json"
    )
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(saved_graph, ensure_ascii=False), encoding="utf-8"
    )
    app.dependency_overrides[style_presets_api._provider] = lambda: provider
    try:
        yield TestClient(app), saved_graph
    finally:
        app.dependency_overrides.pop(style_presets_api._provider, None)


def test_retest_route_queues_server_owned_saved_graph_verbatim(
    retest_client,
) -> None:
    client, saved_graph = retest_client

    with patch(
        "app.api.style_presets.submit_saved_workflow",
        return_value="saved-workflow-job",
    ) as submit:
        response = client.post(
            "/api/style-presets/creator-a/workflow/test",
            json={"profile": "portrait"},
        )

    assert response.status_code == 202
    assert response.json() == {
        "preset_id": "creator-a",
        "profile": "portrait",
        "job_id": "saved-workflow-job",
        "status": "queued",
    }
    submit.assert_called_once_with(saved_graph)


def test_retest_route_missing_saved_graph_is_repairable(retest_client) -> None:
    client, _ = retest_client

    with patch("app.api.style_presets.submit_saved_workflow") as submit:
        response = client.post(
            "/api/style-presets/creator-a/workflow/test",
            json={},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "saved_workflow_not_found",
        "message": (
            "No saved workflow exists for preset creator-a profile __base__."
        ),
        "hint": "Explicitly save a successful generation workflow first.",
    }
    submit.assert_not_called()
