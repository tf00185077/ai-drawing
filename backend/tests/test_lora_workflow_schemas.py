"""LoRA dataset/training workflow schema contracts."""

from app.schemas.lora_train import (
    CaptionChange,
    DatasetInspectResponse,
    DatasetItem,
    DatasetListResponse,
    DatasetPrepareRequest,
    DatasetPrepareResponse,
    DatasetValidateRequest,
    DatasetValidateResponse,
    LoraRegistrationResponse,
    LoraSmokeTestResponse,
    LoraTrainCancelResponse,
    LoraTrainJobStatusResponse,
    LoraTrainLogsResponse,
    TrainStartRequest,
    ValidationIssue,
)


def test_lora_workflow_schemas_serialize_expected_fields() -> None:
    """新 workflow schemas 保留 MCP/API 所需的結構化欄位。"""
    item = DatasetItem(
        folder="character/miku",
        image_count=2,
        caption_count=1,
        missing_caption_count=1,
        dataset_hash="hash-a",
        locked=False,
        trigger_token_candidates=["miku_token"],
    )
    listed = DatasetListResponse(datasets=[item]).model_dump()
    assert listed["datasets"][0]["folder"] == "character/miku"
    assert listed["datasets"][0]["dataset_hash"] == "hash-a"

    inspected = DatasetInspectResponse(
        folder="character/miku",
        image_count=2,
        caption_count=1,
        missing_caption_count=1,
        dataset_hash="hash-a",
        locked=False,
        files=[],
        trigger_token_candidates=["miku_token"],
        validation=DatasetValidateResponse(
            ok=False,
            folder="character/miku",
            normalized_trigger_token="miku_token",
            dataset_hash="hash-a",
            image_count=2,
            caption_count=1,
            missing_caption_count=1,
            warnings=[],
            errors=[ValidationIssue(code="missing_caption", message="missing", path="b.png")],
            locked=False,
        ),
    ).model_dump()
    assert inspected["validation"]["errors"][0]["code"] == "missing_caption"

    prepare_request = DatasetPrepareRequest(
        folder="character/miku",
        trigger_token="Miku Token!",
        dry_run=True,
        use_ai_cleanup=False,
    )
    assert prepare_request.trigger_token == "Miku Token!"

    prepared = DatasetPrepareResponse(
        ok=True,
        folder="character/miku",
        normalized_trigger_token="miku_token",
        changes=[CaptionChange(path="a.txt", before="solo", after="miku_token, solo", changed=True)],
        changed_count=1,
        unchanged_count=0,
        dataset_hash_before="hash-a",
        dataset_hash_after=None,
        backup_id=None,
        restored_files=[],
    ).model_dump()
    assert prepared["changes"][0]["after"].startswith("miku_token")

    validate_request = DatasetValidateRequest(
        folder="character/miku",
        trigger_token="miku_token",
        expected_dataset_hash="hash-a",
    )
    assert validate_request.expected_dataset_hash == "hash-a"

    start_request = TrainStartRequest(
        folder="character/miku",
        checkpoint="model.safetensors",
        trigger_token="miku_token",
        expected_dataset_hash="hash-a",
    )
    assert start_request.trigger_token == "miku_token"
    assert start_request.expected_dataset_hash == "hash-a"

    job = LoraTrainJobStatusResponse(
        ok=True,
        job_id="job-1",
        folder="character/miku",
        status="completed",
        stage="completed",
        progress=1.0,
        current_epoch=3,
        total_epochs=3,
        dataset_hash="hash-a",
        normalized_trigger_token="miku_token",
        log_path="/tmp/job.log",
        output_path="/tmp/out.safetensors",
        registered_lora_name="out.safetensors",
    ).model_dump()
    assert job["registered_lora_name"] == "out.safetensors"

    logs = LoraTrainLogsResponse(ok=True, job_id="job-1", lines=["epoch 1/3"], truncated=False)
    cancel = LoraTrainCancelResponse(ok=True, job_id="job-1", status="cancelled")
    registered = LoraRegistrationResponse(ok=True, job_id="job-1", registered_lora_name="out.safetensors")
    smoke = LoraSmokeTestResponse(
        ok=True,
        job_id="job-1",
        registered_lora_name="out.safetensors",
        smoke_test_status="submitted",
        generation_job_id="gen-1",
    )
    assert logs.model_dump()["lines"] == ["epoch 1/3"]
    assert cancel.status == "cancelled"
    assert registered.registered_lora_name == "out.safetensors"
    assert smoke.generation_job_id == "gen-1"
