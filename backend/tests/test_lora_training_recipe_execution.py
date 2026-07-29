"""Offline dataset TOML, argv, and execution-evidence fixture tests."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.schemas.lora_train import (
    ComponentIdentity,
    EvidenceValue,
    RecipeCompilationContext,
    RecipePolicySnapshot,
    TrainerCapabilitySnapshot,
)
from app.services import lora_trainer
from app.services.lora_training_recipe import compile_training_recipe


def _capability() -> TrainerCapabilitySnapshot:
    return TrainerCapabilitySnapshot(
        platform="unknown",
        status="unavailable",
        reason="trainer runtime was not inspectable",
        python_version="3.11.9",
        supported_mixed_precision=("no",),
    )


def _compiled(family: str, *, train_text_encoder: bool, save_cadence: int):
    checkpoint = f"models/{family}.safetensors"
    context = RecipeCompilationContext(
        dataset_hash="d" * 64,
        profile_hash="e" * 64,
        profile_model_family=family,
        approved_trigger_token="sks",
        image_count=11,
        policy=RecipePolicySnapshot(
            default_checkpoint=checkpoint,
            default_anima_qwen3="models/qwen3",
            default_anima_vae="models/anima-vae.safetensors",
            default_anima_t5_tokenizer_path="models/t5-tokenizer",
            resolution=512,
            batch_size=4,
            learning_rate="1e-4",
            keep_tokens=1,
            num_repeats=10,
            mixed_precision="no",
            network_dim=32,
            network_alpha=16,
        ),
        capability=_capability(),
        component_identities={
            "checkpoint": ComponentIdentity(
                kind="checkpoint",
                requested_locator=checkpoint,
                resolved_locator=f"D:/resolved/{family}.safetensors",
                verification_status="unverified",
                reason="offline fixture",
            )
        },
    )
    recipe = {
        "model": {"family": family},
        "scope": {"train_text_encoder": train_text_encoder},
        "dataset": {
            "resolution": 512,
            "batch_size": 2,
            "keep_tokens": 2,
            "num_repeats": 3,
            "enable_bucket": True,
            "bucket_no_upscale": True,
            "min_bucket_reso": 256,
            "max_bucket_reso": 1024,
            "bucket_reso_steps": 64,
        },
        "optimization": {
            "epochs": 3,
            "learning_rate": "1e-4",
            "denoiser_learning_rate": "8e-5",
            "gradient_accumulation_steps": 2,
            "optimizer": "Lion",
            "optimizer_args": {
                "weight_decay": 0.01,
                "betas": "0.9,0.99",
            },
            "scheduler": "cosine",
            "scheduler_args": {"num_cycles": 1},
            "warmup": {"mode": "steps", "value": 7},
            "seed": 42,
            "mixed_precision": "no",
        },
        "caching": {
            "cache_latents": True,
            "cache_to_disk": True,
        },
        "execution": {
            "max_data_loader_n_workers": 2,
            "persistent_data_loader_workers": True,
            "save_every_n_epochs": save_cadence,
        },
    }
    if train_text_encoder:
        recipe["optimization"]["text_encoder_lr"] = (
            ["2e-5", "3e-5"] if family == "sdxl" else "2e-5"
        )
        recipe["caching"]["cache_text_encoder_outputs"] = False
    return compile_training_recipe(
        recipe,
        context=context,
        policy_source="preflight_policy",
        seed_factory=lambda: 999,
    )


def test_dataset_toml_is_exact_and_contains_every_bucket_control(
    tmp_path: Path,
) -> None:
    compiled = _compiled("sd15", train_text_encoder=False, save_cadence=2)
    image_dir = tmp_path / "dataset"

    content = lora_trainer.build_dataset_toml(
        compiled.effective,
        image_dir=image_dir,
    )

    assert content == (
        "[general]\n"
        "shuffle_caption = true\n"
        'caption_extension = ".txt"\n'
        "keep_tokens = 2\n"
        "\n"
        "[[datasets]]\n"
        "resolution = 512\n"
        "batch_size = 2\n"
        "enable_bucket = true\n"
        "bucket_no_upscale = true\n"
        "min_bucket_reso = 256\n"
        "max_bucket_reso = 1024\n"
        "bucket_reso_steps = 64\n"
        "\n"
        "  [[datasets.subsets]]\n"
        f'  image_dir = {json.dumps(image_dir.as_posix())}\n'
        '  class_tokens = "sks"\n'
        "  num_repeats = 3\n"
    )


@pytest.mark.parametrize(
    ("family", "train_text_encoder", "save_cadence", "family_args"),
    [
        (
            "sd15",
            False,
            2,
            [
                "--network_train_unet_only",
                "--save_every_n_epochs",
                "2",
            ],
        ),
        (
            "sdxl",
            True,
            0,
            [
                "--text_encoder_lr1",
                "0.00002",
                "--text_encoder_lr2",
                "0.00003",
            ],
        ),
        (
            "anima",
            True,
            0,
            [
                "--qwen3",
                "models/qwen3",
                "--vae",
                "models/anima-vae.safetensors",
                "--t5_tokenizer_path",
                "models/t5-tokenizer",
                "--text_encoder_lr",
                "0.00002",
            ],
        ),
    ],
)
def test_exact_argv_fixture_covers_all_v1_controls_for_each_family(
    tmp_path: Path,
    family: str,
    train_text_encoder: bool,
    save_cadence: int,
    family_args: list[str],
) -> None:
    compiled = _compiled(
        family,
        train_text_encoder=train_text_encoder,
        save_cadence=save_cadence,
    )
    sd_scripts = tmp_path / "sd-scripts"
    dataset_config = tmp_path / "dataset.toml"
    output_dir = tmp_path / "output"
    script = {
        "sd15": "train_network.py",
        "sdxl": "sdxl_train_network.py",
        "anima": "anima_train_network.py",
    }[family]
    expected = [
        "trainer-python",
        "-m",
        "accelerate",
        "launch",
        "--num_cpu_threads_per_process",
        "1",
        str(sd_scripts / script),
        "--pretrained_model_name_or_path",
        f"models/{family}.safetensors",
        "--dataset_config",
        str(dataset_config),
        "--output_dir",
        str(output_dir),
        "--output_name",
        "fixture",
        "--network_module",
        "networks.lora_anima" if family == "anima" else "networks.lora",
        "--network_dim",
        "32",
        "--network_alpha",
        "16",
        "--max_train_epochs",
        "3",
        "--learning_rate",
        "0.0001",
        "--unet_lr",
        "0.00008",
        *family_args,
        "--gradient_accumulation_steps",
        "2",
        "--max_data_loader_n_workers",
        "2",
        "--persistent_data_loader_workers",
        "--optimizer_type",
        "Lion",
        "--optimizer_args",
        "betas=0.9,0.99",
        "weight_decay=0.01",
        "--lr_scheduler",
        "cosine",
        "--lr_scheduler_args",
        "num_cycles=1",
        "--lr_warmup_steps",
        "7",
        "--seed",
        "42",
        "--save_model_as",
        "safetensors",
        "--mixed_precision",
        "no",
        "--cache_latents",
        "--cache_latents_to_disk",
        "--gradient_checkpointing",
    ]

    argv = lora_trainer.build_training_argv(
        compiled.effective,
        launcher_argv=("trainer-python", "-m", "accelerate", "launch"),
        sd_scripts_path=sd_scripts,
        dataset_config_path=dataset_config,
        output_dir=output_dir,
        output_name="fixture",
    )

    assert argv == expected
    assert ("--network_train_unet_only" in argv) is (not train_text_encoder)
    assert ("--save_every_n_epochs" in argv) is (save_cadence > 0)


def test_text_cache_disk_flags_expand_only_for_enabled_cache_kind(
    tmp_path: Path,
) -> None:
    compiled = _compiled("sdxl", train_text_encoder=False, save_cadence=1)
    argv = lora_trainer.build_training_argv(
        compiled.effective,
        launcher_argv=("accelerate", "launch"),
        sd_scripts_path=tmp_path,
        dataset_config_path=tmp_path / "dataset.toml",
        output_dir=tmp_path / "output",
        output_name="cache",
    )

    assert "--cache_latents_to_disk" in argv
    assert "--cache_text_encoder_outputs" in argv
    assert "--cache_text_encoder_outputs_to_disk" in argv


def test_settings_mutation_after_compilation_cannot_change_toml_or_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiled = _compiled("sd15", train_text_encoder=False, save_cadence=2)
    kwargs = {
        "launcher_argv": ("accelerate", "launch"),
        "sd_scripts_path": tmp_path / "sd-scripts",
        "dataset_config_path": tmp_path / "dataset.toml",
        "output_dir": tmp_path / "output",
        "output_name": "immutable",
    }
    before_toml = lora_trainer.build_dataset_toml(
        compiled.effective,
        image_dir=tmp_path / "images",
    )
    before_argv = lora_trainer.build_training_argv(compiled.effective, **kwargs)
    monkeypatch.setattr(
        lora_trainer,
        "get_settings",
        lambda: SimpleNamespace(
            lora_batch_size=32,
            lora_save_every_n_epochs=99,
            lora_mixed_precision="bf16",
            lora_learning_rate="9",
        ),
    )

    assert lora_trainer.build_dataset_toml(
        compiled.effective,
        image_dir=tmp_path / "images",
    ) == before_toml
    assert lora_trainer.build_training_argv(compiled.effective, **kwargs) == before_argv


def test_component_identity_and_execution_evidence_are_explicit(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.safetensors"
    checkpoint.write_bytes(b"checkpoint")
    identity = lora_trainer.collect_component_identity(
        kind="checkpoint",
        requested_locator="alias/checkpoint",
        resolved_path=checkpoint,
        allow_unverified=False,
        digest_resolver=lambda _path: "a" * 64,
    )
    capability = _capability()
    evidence = lora_trainer.build_execution_evidence(
        argv=("accelerate", "launch", "train_network.py"),
        dataset_config_content="[general]\n",
        launcher=EvidenceValue(status="verified", value="accelerate"),
        capability=capability,
        sd_scripts_revision=EvidenceValue(
            status="unavailable",
            reason="not a git checkout",
        ),
    )

    assert identity.verification_status == "verified"
    assert identity.size_bytes == len(b"checkpoint")
    assert identity.sha256 == "a" * 64
    assert evidence.status == "unverified"
    assert evidence.argv == ("accelerate", "launch", "train_network.py")
    assert evidence.dataset_config_sha256 is not None
    assert evidence.sd_scripts_revision.status == "unavailable"


def test_capability_inspection_failure_is_redacted() -> None:
    secret = "TOKEN_DO_NOT_ECHO"

    def failing_runner(*_args, **_kwargs):
        raise RuntimeError(secret)

    capability = lora_trainer.inspect_trainer_capability(
        "trainer-python",
        runner=failing_runner,
    )

    assert capability.platform == "unknown"
    assert capability.status == "unavailable"
    assert secret not in capability.reason


def test_capability_inspection_accepts_only_sanitized_known_values() -> None:
    payload = json.dumps(
        {
            "platform": "cuda",
            "torch_version": "2.7.0+cu128",
            "accelerate_version": "1.11.0",
            "python_version": "3.11.9",
            "supported_mixed_precision": ["no", "fp16", "bf16", "evil"],
            "secret": "must be discarded",
        }
    )

    capability = lora_trainer.inspect_trainer_capability(
        "trainer-python",
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=payload,
        ),
    )

    assert capability.model_dump() == {
        "platform": "cuda",
        "status": "verified",
        "reason": None,
        "torch_version": "2.7.0+cu128",
        "accelerate_version": "1.11.0",
        "python_version": "3.11.9",
        "supported_mixed_precision": ("no", "fp16", "bf16"),
    }


def test_launcher_selection_and_revision_evidence_are_bounded(
    tmp_path: Path,
) -> None:
    python_executable = tmp_path / "venv" / "python.exe"
    accelerate_executable = python_executable.parent / "accelerate.exe"
    python_executable.parent.mkdir(parents=True)
    python_executable.write_bytes(b"")
    accelerate_executable.write_bytes(b"")

    launcher_argv, launcher = lora_trainer.select_accelerate_launcher(
        str(python_executable)
    )
    revision = lora_trainer.collect_sd_scripts_revision(
        tmp_path,
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="a" * 40 + "\n",
        ),
    )

    assert launcher_argv == (str(accelerate_executable.resolve()), "launch")
    assert launcher.status == "verified"
    assert revision == EvidenceValue(status="verified", value="a" * 40)


def test_revision_failure_does_not_echo_process_output(tmp_path: Path) -> None:
    secret = "SECRET_REVISION_OUTPUT"
    revision = lora_trainer.collect_sd_scripts_revision(
        tmp_path,
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout=secret,
        ),
    )

    assert revision.status == "unavailable"
    assert secret not in (revision.reason or "")
