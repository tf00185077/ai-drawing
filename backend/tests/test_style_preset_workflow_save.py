from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import style_presets as style_presets_api
from app.core.style_presets import DirStylePresetProvider
from app.db.database import Base
from app.db.database import get_db
from app.db.models import GeneratedArtifact, GeneratedImage
from app.main import app
from app.services.style_preset_workflows import (
    StylePresetWorkflowError,
    load_saved_workflow,
    normalize_keywords,
    parse_source_locator,
    resolve_successful_workflow,
    save_successful_workflow,
    sanitize_workflow_prompts,
    workflow_path_for,
)

SOURCE_POSITIVE_PROMPT = "private full round prompt"
SOURCE_NEGATIVE_PROMPT = "private full round negative prompt"


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with factory() as db:
        yield db


@pytest.fixture
def checkpoint_graph() -> dict:
    return {
        "41": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "traditional-xl.safetensors"},
        },
        "72": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["41", 1],
                "text": "a complete round prompt that must disappear",
            },
            "_meta": {"title": "subject prose"},
        },
        "16": {
            "class_type": "ConditioningSetArea",
            "inputs": {
                "conditioning": ["72", 0],
                "width": 832,
                "height": 1216,
                "strength": 0.85,
            },
        },
        "93": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["41", 1],
                "text": "a complete negative round prompt that must disappear",
            },
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 832, "height": 1216, "batch_size": 2},
        },
        "301": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["41", 0],
                "positive": ["16", 0],
                "negative": ["93", 0],
                "latent_image": ["5", 0],
                "seed": 987654321,
                "steps": 31,
                "cfg": 6.25,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
            },
        },
    }


@pytest.fixture
def diffusion_multi_loader_graph() -> dict:
    return {
        "neg-text": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "old negative prose", "clip": ["dual-clip", 0]},
        },
        "vae-loader": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "family.vae.safetensors"},
        },
        "unet-loader": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "family.diffusion.safetensors",
                "weight_dtype": "default",
            },
        },
        "lora-first": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["unet-loader", 0],
                "lora_name": "line.safetensors",
                "strength_model": 0.55,
            },
        },
        "dual-clip": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "encoder-one.safetensors",
                "clip_name2": "encoder-two.safetensors",
                "type": "flux",
            },
        },
        "style-text": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["dual-clip", 0], "text": "old style prose"},
        },
        "detail-text": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["dual-clip", 0], "text": "old detail prose"},
        },
        "positive-merge": {
            "class_type": "ConditioningConcat",
            "inputs": {
                "conditioning_to": ["style-text", 0],
                "conditioning_from": ["detail-text", 0],
            },
        },
        "lora-second": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["lora-first", 0],
                "lora_name": "color.safetensors",
                "strength_model": 0.35,
            },
        },
        "latent": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
        },
        "sampler-advanced": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["lora-second", 0],
                "positive": ["positive-merge", 0],
                "negative": ["neg-text", 0],
                "latent_image": ["latent", 0],
                "noise_seed": 112233,
                "steps": 24,
                "cfg": 4.75,
                "sampler_name": "euler",
                "scheduler": "simple",
                "start_at_step": 0,
                "end_at_step": 24,
                "return_with_leftover_noise": "disable",
            },
        },
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" ink wash,  soft light\nink wash ,, ", ["ink wash", "soft light"]),
        (
            [" ink wash ", "soft light\nfilm grain", "", "ink wash"],
            ["ink wash", "soft light", "film grain"],
        ),
        (None, []),
    ],
)
def test_normalize_keywords_is_syntactic_and_stable(value, expected) -> None:
    assert normalize_keywords(value) == expected


@pytest.mark.parametrize(
    ("raw", "kind", "identifier"),
    [
        (12, "image", 12),
        (" 12 ", "image", 12),
        ("image:12", "image", 12),
        ("artifact:44", "artifact", 44),
        ("job:abc-123", "job", "abc-123"),
        ("abc-123", "job", "abc-123"),
    ],
)
def test_parse_source_locator_accepts_loose_compact_forms(
    raw, kind, identifier
) -> None:
    locator = parse_source_locator(raw)
    assert locator.kind == kind
    assert locator.identifier == identifier


def test_resolve_image_artifact_and_job_sources(
    session, checkpoint_graph
) -> None:
    image = GeneratedImage(
        job_id="completed-job",
        image_path="gallery/result.png",
        workflow_json=json.dumps(checkpoint_graph),
        prompt="private full positive prompt",
        negative_prompt="private full negative prompt",
    )
    artifact = GeneratedArtifact(
        job_id="artifact-job",
        artifact_type="image",
        gallery_path="gallery/artifact.png",
        workflow_json=json.dumps(checkpoint_graph),
        prompt="other private prompt",
        negative_prompt="other private negative",
    )
    session.add_all([image, artifact])
    session.commit()

    by_image = resolve_successful_workflow(session, image.id)
    by_artifact = resolve_successful_workflow(session, f"artifact:{artifact.id}")
    by_job = resolve_successful_workflow(session, "job:completed-job")

    assert (by_image.source_type, by_image.source_id) == ("image", str(image.id))
    assert (by_artifact.source_type, by_artifact.source_id) == (
        "artifact",
        str(artifact.id),
    )
    assert (by_job.source_type, by_job.source_id) == ("job", "completed-job")
    assert by_image.workflow == checkpoint_graph
    assert by_artifact.workflow == checkpoint_graph
    assert by_job.workflow == checkpoint_graph
    assert by_image.source_prompt == "private full positive prompt"
    assert by_image.source_negative_prompt == "private full negative prompt"
    assert by_artifact.source_prompt == "other private prompt"
    assert by_artifact.source_negative_prompt == "other private negative"
    assert by_job.source_prompt == "private full positive prompt"
    assert by_job.source_negative_prompt == "private full negative prompt"


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ("image:404", "source_not_found"),
        ("job:running-job", "source_not_successful"),
        ("artifact:1", "source_not_image"),
        ("image:1", "source_has_no_workflow"),
    ],
)
def test_resolve_rejects_missing_unsuccessful_video_or_graphless_sources(
    session, monkeypatch, source, code
) -> None:
    if source == "artifact:1":
        session.add(
            GeneratedArtifact(
                artifact_type="video",
                gallery_path="clip.mp4",
                workflow_json='{"1":{"class_type":"VHS_VideoCombine","inputs":{}}}',
            )
        )
    elif source == "image:1":
        session.add(GeneratedImage(image_path="legacy.png", workflow_json=None))
    session.commit()
    monkeypatch.setattr(
        "app.services.style_preset_workflows.get_job_status",
        lambda job_id: (
            {"job_id": job_id, "status": "running"}
            if job_id == "running-job"
            else None
        ),
    )

    with pytest.raises(StylePresetWorkflowError) as exc:
        resolve_successful_workflow(session, source)

    assert exc.value.code == code
    assert exc.value.message
    assert exc.value.hint


def test_positive_keywords_are_required(checkpoint_graph) -> None:
    with pytest.raises(StylePresetWorkflowError) as exc:
        sanitize_workflow_prompts(checkpoint_graph, " ,\n", "blur")

    assert exc.value.code == "positive_keywords_required"


def test_empty_negative_keywords_are_valid(checkpoint_graph) -> None:
    sanitized, positive, negative = sanitize_workflow_prompts(
        checkpoint_graph, "ink wash", []
    )

    assert positive == ["ink wash"]
    assert negative == []
    assert sanitized["72"]["inputs"]["text"] == "ink wash"
    assert sanitized["93"]["inputs"]["text"] == ""


def test_sampler_link_traversal_changes_only_reachable_text_and_does_not_mutate(
    checkpoint_graph,
) -> None:
    source_snapshot = copy.deepcopy(checkpoint_graph)

    sanitized, positive, negative = sanitize_workflow_prompts(
        checkpoint_graph,
        ["ink wash", "soft light", "ink wash"],
        "watermark,\nlow quality",
    )

    assert positive == ["ink wash", "soft light"]
    assert negative == ["watermark", "low quality"]
    assert sanitized["72"]["inputs"]["text"] == "ink wash, soft light"
    assert sanitized["93"]["inputs"]["text"] == "watermark, low quality"
    assert checkpoint_graph == source_snapshot
    assert "complete round prompt" not in json.dumps(sanitized)
    assert "complete negative round prompt" not in json.dumps(sanitized)

    expected = copy.deepcopy(source_snapshot)
    expected["72"]["inputs"]["text"] = "ink wash, soft light"
    expected["93"]["inputs"]["text"] = "watermark, low quality"
    assert sanitized == expected


def test_shared_positive_and_negative_encoder_is_rejected(checkpoint_graph) -> None:
    ambiguous = copy.deepcopy(checkpoint_graph)
    ambiguous["301"]["inputs"]["negative"] = ["16", 0]

    with pytest.raises(StylePresetWorkflowError) as exc:
        sanitize_workflow_prompts(ambiguous, "ink wash", "blur")

    assert exc.value.code == "ambiguous_conditioning"


def test_missing_positive_conditioning_is_rejected_without_title_guessing(
    checkpoint_graph,
) -> None:
    missing = copy.deepcopy(checkpoint_graph)
    missing["301"]["inputs"]["positive"] = ["41", 0]
    missing["unlinked-title-match"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": ["41", 1], "text": "positive prompt"},
        "_meta": {"title": "Positive Prompt"},
    }

    with pytest.raises(StylePresetWorkflowError) as exc:
        sanitize_workflow_prompts(missing, "ink wash", "blur")

    assert exc.value.code == "conditioning_not_found"


@pytest.mark.parametrize(
    ("fixture_name", "positive_nodes", "negative_nodes"),
    [
        ("checkpoint_graph", {"72"}, {"93"}),
        (
            "diffusion_multi_loader_graph",
            {"style-text", "detail-text"},
            {"neg-text"},
        ),
    ],
)
def test_structurally_different_graphs_use_the_same_reachability_sanitizer(
    request, fixture_name, positive_nodes, negative_nodes
) -> None:
    graph = request.getfixturevalue(fixture_name)
    original = copy.deepcopy(graph)

    sanitized, _, _ = sanitize_workflow_prompts(
        graph, "graphic lines, muted palette", "text artifacts"
    )

    for node_id in positive_nodes:
        assert sanitized[node_id]["inputs"]["text"] == "graphic lines, muted palette"
    for node_id in negative_nodes:
        assert sanitized[node_id]["inputs"]["text"] == "text artifacts"

    for node_id, node in original.items():
        if node_id in positive_nodes | negative_nodes:
            node = copy.deepcopy(node)
            node["inputs"]["text"] = sanitized[node_id]["inputs"]["text"]
        assert sanitized[node_id] == node
    assert graph == original


def _provider_with_preset(tmp_path) -> DirStylePresetProvider:
    provider = DirStylePresetProvider(
        tmp_path / "style_presets" / "agent", project_root=tmp_path
    )
    provider.create_preset(
        {
            "id": "creator-a",
            "name": "Creator A",
            "base_prompt": "declarative recipe remains unchanged",
            "negative_prompt": "declarative negative remains unchanged",
            "profiles": {
                "portrait": {
                    "prompt_prefix": "upper body",
                    "params": {"steps": 32},
                }
            },
        },
        create_note=False,
    )
    return provider


def _add_successful_image(
    session,
    workflow: dict,
    *,
    prompt: str | None = SOURCE_POSITIVE_PROMPT,
    negative_prompt: str | None = SOURCE_NEGATIVE_PROMPT,
) -> GeneratedImage:
    row = GeneratedImage(
        job_id="successful-job",
        image_path="gallery/success.png",
        workflow_json=json.dumps(workflow),
        prompt=prompt,
        negative_prompt=negative_prompt,
    )
    session.add(row)
    session.commit()
    return row


def test_orphan_text_encoder_with_exact_source_prompt_is_rejected_without_write(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    leaking_graph = copy.deepcopy(checkpoint_graph)
    leaking_graph["orphan-prompt"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["41", 1],
            "text": SOURCE_POSITIVE_PROMPT,
        },
    }
    image = _add_successful_image(session, leaking_graph)

    with pytest.raises(StylePresetWorkflowError) as exc:
        save_successful_workflow(
            session,
            provider,
            preset_id="creator-a",
            profile=None,
            source=image.id,
            prompt_keywords="ink wash",
            negative_prompt_keywords="watermark",
        )

    assert exc.value.code == "prompt_confidentiality_unproven"
    assert exc.value.detail()["message"]
    assert exc.value.detail()["hint"]
    assert not (provider.agent_dir / "workflows").exists()


def test_graph_conditioning_is_confidentiality_evidence_when_record_metadata_is_missing(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    leaking_graph = copy.deepcopy(checkpoint_graph)
    leaking_graph["72"]["inputs"]["text"] = SOURCE_POSITIVE_PROMPT
    leaking_graph["93"]["inputs"]["text"] = SOURCE_NEGATIVE_PROMPT
    leaking_graph["orphan-prompt"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": ["41", 1], "text": SOURCE_POSITIVE_PROMPT},
    }
    image = _add_successful_image(
        session, leaking_graph, prompt=None, negative_prompt=None
    )

    with pytest.raises(StylePresetWorkflowError) as exc:
        save_successful_workflow(
            session,
            provider,
            preset_id="creator-a",
            profile=None,
            source=image.id,
            prompt_keywords="ink wash",
            negative_prompt_keywords="watermark",
        )

    assert exc.value.code == "prompt_confidentiality_unproven"
    assert not (provider.agent_dir / "workflows").exists()


@pytest.mark.parametrize(
    ("missing_node", "orphan_text", "prompt", "negative_prompt"),
    [
        ("72", "private positive prompt", None, ""),
        ("93", "private negative prompt", "recorded positive prompt", None),
    ],
    ids=["positive-evidence-missing", "negative-evidence-missing"],
)
def test_each_prompt_polarity_requires_evidence_or_explicit_empty_metadata(
    tmp_path,
    session,
    checkpoint_graph,
    missing_node,
    orphan_text,
    prompt,
    negative_prompt,
) -> None:
    provider = _provider_with_preset(tmp_path)
    graph = copy.deepcopy(checkpoint_graph)
    graph["72"]["inputs"]["text"] = "recorded positive prompt"
    graph["93"]["inputs"]["text"] = "recorded negative prompt"
    graph[missing_node]["inputs"]["text"] = ""
    graph["orphan-prompt"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": ["41", 1], "text": orphan_text},
    }
    image = _add_successful_image(
        session,
        graph,
        prompt=prompt,
        negative_prompt=negative_prompt,
    )

    with pytest.raises(StylePresetWorkflowError) as exc:
        save_successful_workflow(
            session,
            provider,
            preset_id="creator-a",
            profile=None,
            source=image.id,
            prompt_keywords="ink wash",
            negative_prompt_keywords="watermark",
        )

    assert exc.value.code == "prompt_confidentiality_unproven"
    assert not (provider.agent_dir / "workflows").exists()


def test_linked_primitive_and_string_prompt_carriers_are_replaced_safely(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    linked_graph = copy.deepcopy(checkpoint_graph)
    linked_graph["positive-carrier"] = {
        "class_type": "PrimitiveNode",
        "inputs": {"value": SOURCE_POSITIVE_PROMPT},
    }
    linked_graph["negative-carrier"] = {
        "class_type": "String",
        "inputs": {"text": SOURCE_NEGATIVE_PROMPT},
    }
    linked_graph["72"]["inputs"]["text"] = ["positive-carrier", 0]
    linked_graph["93"]["inputs"]["text"] = ["negative-carrier", 0]
    image = _add_successful_image(session, linked_graph)

    saved = save_successful_workflow(
        session,
        provider,
        preset_id="creator-a",
        profile=None,
        source=image.id,
        prompt_keywords="ink wash, soft light",
        negative_prompt_keywords="watermark",
    )

    target = tmp_path / saved.workflow_path
    raw = json.loads(target.read_text(encoding="utf-8"))
    assert raw["72"]["inputs"]["text"] == ["positive-carrier", 0]
    assert raw["93"]["inputs"]["text"] == ["negative-carrier", 0]
    assert raw["positive-carrier"]["inputs"]["value"] == "ink wash, soft light"
    assert raw["negative-carrier"]["inputs"]["text"] == "watermark"
    serialized = target.read_text(encoding="utf-8")
    assert SOURCE_POSITIVE_PROMPT not in serialized
    assert SOURCE_NEGATIVE_PROMPT not in serialized


def test_source_prompt_may_be_intentionally_preserved_in_target_carriers(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    graph = copy.deepcopy(checkpoint_graph)
    graph["72"]["inputs"]["text"] = SOURCE_POSITIVE_PROMPT
    graph["93"]["inputs"]["text"] = SOURCE_NEGATIVE_PROMPT
    image = _add_successful_image(session, graph)

    saved = save_successful_workflow(
        session,
        provider,
        preset_id="creator-a",
        profile=None,
        source=image.id,
        prompt_keywords=SOURCE_POSITIVE_PROMPT,
        negative_prompt_keywords=SOURCE_NEGATIVE_PROMPT,
    )

    raw = json.loads((tmp_path / saved.workflow_path).read_text(encoding="utf-8"))
    assert raw["72"]["inputs"]["text"] == SOURCE_POSITIVE_PROMPT
    assert raw["93"]["inputs"]["text"] == SOURCE_NEGATIVE_PROMPT


def test_equal_target_prompt_does_not_hide_a_metadata_copy(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    graph = copy.deepcopy(checkpoint_graph)
    graph["72"]["inputs"]["text"] = SOURCE_POSITIVE_PROMPT
    graph["93"]["inputs"]["text"] = SOURCE_NEGATIVE_PROMPT
    graph["301"]["_meta"] = {"source_prompt": SOURCE_POSITIVE_PROMPT}
    image = _add_successful_image(session, graph)

    with pytest.raises(StylePresetWorkflowError) as exc:
        save_successful_workflow(
            session,
            provider,
            preset_id="creator-a",
            profile=None,
            source=image.id,
            prompt_keywords=SOURCE_POSITIVE_PROMPT,
            negative_prompt_keywords=SOURCE_NEGATIVE_PROMPT,
        )

    assert exc.value.code == "prompt_confidentiality_unproven"
    assert not (provider.agent_dir / "workflows").exists()


def test_linked_prompt_carrier_with_non_conditioning_consumer_is_rejected(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    linked_graph = copy.deepcopy(checkpoint_graph)
    linked_graph["positive-carrier"] = {
        "class_type": "PrimitiveNode",
        "inputs": {"value": SOURCE_POSITIVE_PROMPT},
    }
    linked_graph["72"]["inputs"]["text"] = ["positive-carrier", 0]
    linked_graph["unrelated-consumer"] = {
        "class_type": "PreviewText",
        "inputs": {"text": ["positive-carrier", 0]},
    }
    image = _add_successful_image(session, linked_graph)

    with pytest.raises(StylePresetWorkflowError) as exc:
        save_successful_workflow(
            session,
            provider,
            preset_id="creator-a",
            profile=None,
            source=image.id,
            prompt_keywords="ink wash",
            negative_prompt_keywords="watermark",
        )

    assert exc.value.code == "prompt_confidentiality_unproven"
    assert not (provider.agent_dir / "workflows").exists()


def test_metadata_prompt_copy_is_rejected_without_replacing_existing_file(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    clean_graph = copy.deepcopy(checkpoint_graph)
    clean_graph["72"]["inputs"]["text"] = SOURCE_POSITIVE_PROMPT
    clean_graph["93"]["inputs"]["text"] = SOURCE_NEGATIVE_PROMPT
    clean_image = _add_successful_image(session, clean_graph)
    first = save_successful_workflow(
        session,
        provider,
        preset_id="creator-a",
        profile=None,
        source=clean_image.id,
        prompt_keywords="known good",
        negative_prompt_keywords="known negative",
    )
    target = tmp_path / first.workflow_path
    before = target.read_bytes()

    leaking_graph = copy.deepcopy(clean_graph)
    leaking_graph["301"]["_meta"] = {
        "source_prompt": f"recorded source={SOURCE_POSITIVE_PROMPT}",
        "source_negative_prompt": (
            f"recorded source={SOURCE_NEGATIVE_PROMPT}"
        ),
    }
    leaking_image = _add_successful_image(session, leaking_graph)

    with pytest.raises(StylePresetWorkflowError) as exc:
        save_successful_workflow(
            session,
            provider,
            preset_id="creator-a",
            profile=None,
            source=leaking_image.id,
            prompt_keywords="replacement",
            negative_prompt_keywords="replacement negative",
        )

    assert exc.value.code == "prompt_confidentiality_unproven"
    assert target.read_bytes() == before
    assert list(target.parent.glob("*.tmp")) == []


def test_persisted_raw_graph_contains_neither_exact_source_prompt(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    graph = copy.deepcopy(checkpoint_graph)
    graph["72"]["inputs"]["text"] = SOURCE_POSITIVE_PROMPT
    graph["93"]["inputs"]["text"] = SOURCE_NEGATIVE_PROMPT
    image = _add_successful_image(session, graph)

    saved = save_successful_workflow(
        session,
        provider,
        preset_id="creator-a",
        profile=None,
        source=image.id,
        prompt_keywords="ink wash",
        negative_prompt_keywords="watermark",
    )

    serialized = (tmp_path / saved.workflow_path).read_text(encoding="utf-8")
    assert SOURCE_POSITIVE_PROMPT not in serialized
    assert SOURCE_NEGATIVE_PROMPT not in serialized


def test_save_uses_conventional_base_and_profile_paths(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    image = _add_successful_image(session, checkpoint_graph)

    base = save_successful_workflow(
        session,
        provider,
        preset_id="creator-a",
        profile=None,
        source=image.id,
        prompt_keywords="ink wash",
        negative_prompt_keywords="watermark",
    )
    portrait = save_successful_workflow(
        session,
        provider,
        preset_id="creator-a",
        profile="portrait",
        source=f"job:{image.job_id}",
        prompt_keywords=["graphic lines", "muted palette"],
        negative_prompt_keywords=[],
    )

    assert base.workflow_path == (
        "style_presets/agent/workflows/creator-a/__base__.api.json"
    )
    assert portrait.workflow_path == (
        "style_presets/agent/workflows/creator-a/portrait.api.json"
    )
    assert workflow_path_for(provider, "creator-a", None) == (
        tmp_path
        / "style_presets"
        / "agent"
        / "workflows"
        / "creator-a"
        / "__base__.api.json"
    )
    assert workflow_path_for(provider, "creator-a", "portrait").name == (
        "portrait.api.json"
    )

    raw = json.loads(
        workflow_path_for(provider, "creator-a", None).read_text(encoding="utf-8")
    )
    assert raw["72"]["inputs"]["text"] == "ink wash"
    assert raw["93"]["inputs"]["text"] == "watermark"
    assert set(raw) == set(checkpoint_graph)
    assert "source" not in raw
    assert "manifest" not in raw
    assert "snapshot_id" not in raw
    assert "sha256" not in raw

    recipe = provider.get_preset("creator-a")
    assert recipe.base_prompt == "declarative recipe remains unchanged"
    assert recipe.negative_prompt == "declarative negative remains unchanged"


@pytest.mark.parametrize(
    ("preset_id", "profile", "code"),
    [
        ("missing", None, "preset_not_found"),
        ("creator-a", "missing", "profile_not_found"),
    ],
)
def test_unknown_preset_or_profile_writes_nothing(
    tmp_path,
    session,
    checkpoint_graph,
    preset_id,
    profile,
    code,
) -> None:
    provider = _provider_with_preset(tmp_path)
    image = _add_successful_image(session, checkpoint_graph)

    with pytest.raises(StylePresetWorkflowError) as exc:
        save_successful_workflow(
            session,
            provider,
            preset_id=preset_id,
            profile=profile,
            source=image.id,
            prompt_keywords="ink wash",
            negative_prompt_keywords="",
        )

    assert exc.value.code == code
    assert not (provider.agent_dir / "workflows").exists()


def test_source_and_sanitizer_failures_do_not_create_or_replace_files(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    image = _add_successful_image(session, checkpoint_graph)
    first = save_successful_workflow(
        session,
        provider,
        preset_id="creator-a",
        profile=None,
        source=image.id,
        prompt_keywords="known good",
        negative_prompt_keywords="known negative",
    )
    target = tmp_path / first.workflow_path
    before = target.read_bytes()

    for source, positive in (("image:404", "replacement"), (image.id, " ,\n")):
        with pytest.raises(StylePresetWorkflowError):
            save_successful_workflow(
                session,
                provider,
                preset_id="creator-a",
                profile=None,
                source=source,
                prompt_keywords=positive,
                negative_prompt_keywords="replacement negative",
            )
        assert target.read_bytes() == before


def test_atomic_replace_parses_temp_file_before_publication(
    tmp_path, session, checkpoint_graph, monkeypatch
) -> None:
    provider = _provider_with_preset(tmp_path)
    image = _add_successful_image(session, checkpoint_graph)
    first = save_successful_workflow(
        session,
        provider,
        preset_id="creator-a",
        profile=None,
        source=image.id,
        prompt_keywords="first",
        negative_prompt_keywords="first negative",
    )
    target = tmp_path / first.workflow_path
    before = target.read_bytes()
    replace_calls: list[tuple[object, object]] = []

    import app.services.style_preset_workflows as service

    real_replace = service.os.replace

    def spy_replace(source, destination):
        replace_calls.append((source, destination))
        return real_replace(source, destination)

    monkeypatch.setattr(service.os, "replace", spy_replace)
    save_successful_workflow(
        session,
        provider,
        preset_id="creator-a",
        profile=None,
        source=image.id,
        prompt_keywords="second",
        negative_prompt_keywords="second negative",
    )

    assert len(replace_calls) == 1
    temporary, destination = map(lambda value: str(value), replace_calls[0])
    assert destination == str(target)
    assert str(target.parent) in temporary
    assert json.loads(target.read_text(encoding="utf-8"))["72"]["inputs"][
        "text"
    ] == "second"
    assert target.read_bytes() != before
    assert list(target.parent.glob("*.tmp")) == []

    stable = target.read_bytes()
    monkeypatch.setattr(service.json, "load", lambda stream: [])
    with pytest.raises(StylePresetWorkflowError) as exc:
        save_successful_workflow(
            session,
            provider,
            preset_id="creator-a",
            profile=None,
            source=image.id,
            prompt_keywords="must not publish",
            negative_prompt_keywords="must not publish",
        )
    assert exc.value.code == "invalid_workflow_graph"
    assert target.read_bytes() == stable
    assert list(target.parent.glob("*.tmp")) == []


def test_load_saved_workflow_returns_raw_graph_and_missing_is_repairable(
    tmp_path, session, checkpoint_graph
) -> None:
    provider = _provider_with_preset(tmp_path)
    image = _add_successful_image(session, checkpoint_graph)
    save_successful_workflow(
        session,
        provider,
        preset_id="creator-a",
        profile="portrait",
        source=image.id,
        prompt_keywords="ink wash",
        negative_prompt_keywords="",
    )

    raw = load_saved_workflow(provider, "creator-a", "portrait")
    assert raw["72"]["inputs"]["text"] == "ink wash"
    assert raw["93"]["inputs"]["text"] == ""

    with pytest.raises(StylePresetWorkflowError) as exc:
        load_saved_workflow(provider, "creator-a", None)
    assert exc.value.code == "saved_workflow_not_found"


@pytest.fixture
def workflow_api_client(
    tmp_path, session, checkpoint_graph
) -> tuple[TestClient, DirStylePresetProvider, GeneratedImage]:
    provider = _provider_with_preset(tmp_path)
    image = _add_successful_image(session, checkpoint_graph)
    app.dependency_overrides[style_presets_api._provider] = lambda: provider
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app), provider, image
    finally:
        app.dependency_overrides.pop(style_presets_api._provider, None)
        app.dependency_overrides.pop(get_db, None)


def test_save_and_raw_get_api_contract(workflow_api_client) -> None:
    client, provider, image = workflow_api_client
    response = client.post(
        "/api/style-presets/creator-a/workflow/save",
        json={
            "source": f"image:{image.id}",
            "profile": "portrait",
            "prompt_keywords": "ink wash, soft light",
            "negative_prompt_keywords": ["watermark", "low quality"],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data == {
        "preset_id": "creator-a",
        "profile": "portrait",
        "source": {"type": "image", "id": str(image.id)},
        "workflow_path": (
            "style_presets/agent/workflows/creator-a/portrait.api.json"
        ),
        "prompt_keywords": ["ink wash", "soft light"],
        "negative_prompt_keywords": ["watermark", "low quality"],
        "retest_required": True,
    }
    assert "private full round prompt" not in response.text
    assert "workflow_json" not in response.text

    raw_response = client.get(
        "/api/style-presets/creator-a/workflow",
        params={"profile": "portrait"},
    )
    assert raw_response.status_code == 200
    assert raw_response.json() == load_saved_workflow(
        provider, "creator-a", "portrait"
    )
    assert raw_response.json()["301"]["inputs"]["seed"] == 987654321


@pytest.mark.parametrize(
    ("method", "path", "payload", "status", "code"),
    [
        (
            "post",
            "/api/style-presets/missing/workflow/save",
            {
                "source": 1,
                "prompt_keywords": "ink wash",
                "negative_prompt_keywords": "",
            },
            404,
            "preset_not_found",
        ),
        (
            "post",
            "/api/style-presets/creator-a/workflow/save",
            {
                "source": "image:404",
                "prompt_keywords": "ink wash",
                "negative_prompt_keywords": "",
            },
            404,
            "source_not_found",
        ),
        (
            "get",
            "/api/style-presets/creator-a/workflow",
            None,
            404,
            "saved_workflow_not_found",
        ),
    ],
)
def test_workflow_api_errors_are_stable_and_repairable(
    workflow_api_client, method, path, payload, status, code
) -> None:
    client, _, _ = workflow_api_client
    response = (
        getattr(client, method)(path, json=payload)
        if payload is not None
        else getattr(client, method)(path)
    )

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert response.json()["detail"]["message"]
    assert response.json()["detail"]["hint"]


def test_save_api_rejects_caller_controlled_path(workflow_api_client) -> None:
    client, _, image = workflow_api_client
    response = client.post(
        "/api/style-presets/creator-a/workflow/save",
        json={
            "source": image.id,
            "prompt_keywords": "ink wash",
            "negative_prompt_keywords": "",
            "workflow_path": "../../outside.api.json",
        },
    )

    assert response.status_code == 422
