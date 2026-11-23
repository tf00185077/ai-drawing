"""Public LoRA routes and log sinks, with fake spawn and synthetic secrets only."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.lora_train import EvidenceValue
from app.services import lora_trainer, lora_parameters
from app.services.lora_dataset import DatasetServiceError
from tests.lora_status_http_fixture import response_payload
from tests.test_lora_delivery import isolated_worker, write_lora

MARKER = "SYNTHETIC_CREDENTIAL_14"
PRIVATE = "/private/SYNTHETIC_PRIVATE_14"
WINDOWS = "C:\\Private\\SYNTHETIC_WINDOWS_14\\model.safetensors"
RAW_ERROR = f"API_TOKEN={MARKER}; launch at {PRIVATE}; {WINDOWS}"


def assert_safe(*values):
    for value in values:
        text = value if isinstance(value, str) else json.dumps(value)
        for marker in (MARKER, "SYNTHETIC_PRIVATE_14", "SYNTHETIC_WINDOWS_14"):
            assert marker not in text


def test_real_service_aggregate_serialization_carries_names_and_identity():
    payload = response_payload()
    for job, serial, folder in [(payload["current_job"], 2, "dataset-a"), (payload["queue"][0], 3, "dataset-b")]:
        assert job["folder"] == folder
        assert job["output_name"] == "水彩 旅人"
        assert job["resolved_output_name"] == f"水彩 旅人_{serial:03d}"
        assert job["output_serial"] == serial
        assert job["run_locator"] == f"水彩 旅人_{serial:03d}__20261027T030000Z"
        assert job["output_config_hash"] == "a" * 64


@pytest.mark.parametrize("legacy", [False, True], ids=["allocated", "legacy"])
def test_durable_http_projects_all_execution_fields_without_mutating_internal(isolated_worker, legacy):
    w = isolated_worker
    envelope = json.loads(lora_trainer._recipe_envelope_json(w.job.recipe))
    envelope["effective"]["model"]["checkpoint"] = PRIVATE + "/checkpoint"
    envelope["requested"]["model"] = {"checkpoint": WINDOWS}
    envelope["component_identities"]["checkpoint"].update(
        requested_locator=WINDOWS, resolved_locator=PRIVATE + "/checkpoint", reason=RAW_ERROR,
    )
    evidence = lora_trainer.build_execution_evidence(
        argv=(PRIVATE + "/python", "--checkpoint=" + WINDOWS),
        dataset_config_content='image_dir = "' + PRIVATE + '/data"\n',
        launcher=EvidenceValue(status="unverified", value=WINDOWS, reason=RAW_ERROR),
        capability=w.job.recipe.capability, sd_scripts_revision=EvidenceValue(status="unavailable", reason=RAW_ERROR),
    ).model_dump(mode="json")
    lora_trainer._update_persistent_job(
        w.job.job_id, recipe_json=json.dumps(envelope), execution_evidence_json=json.dumps(evidence),
        output_path=PRIVATE + "/result", log_path=WINDOWS,
        params_json=json.dumps({"checkpoint": WINDOWS, "epochs": 5, "raw": RAW_ERROR}),
        **({"run_locator": None, "resolved_output_name": None, "output_serial": None, "output_name": None} if legacy else {}),
    )
    before = lora_trainer.get_job_status(w.job.job_id)
    response = TestClient(app).get("/api/lora-train/jobs/" + w.job.job_id)
    assert response.status_code == 200
    public = response.json()
    assert_safe(public)
    assert "redacted" in public["execution_evidence"]["reason"]
    assert public["execution_evidence"]["dataset_config_sha256"] == evidence["dataset_config_sha256"]
    assert public["params"]["epochs"] == 5
    assert lora_trainer.get_job_status(w.job.job_id) == before
    assert before["execution_evidence"]["argv"] == evidence["argv"]
    assert before["execution_evidence"]["dataset_config_content"] == evidence["dataset_config_content"]
    if legacy:
        assert public["run_locator"] is public["output_name"] is public["resolved_output_name"] is public["output_serial"] is None
        assert "redacted" in public["output_path"]
    else:
        assert public["output_path"] == f"output/runs/{w.job.run_locator}/artifacts/旅人.safetensors"


@pytest.mark.parametrize("kind", ["generic", "trainer", "dataset", "unknown-code"])
@pytest.mark.parametrize("phase", ["launch", "registration"])
def test_failure_sinks_use_classification_without_exception_text(isolated_worker, monkeypatch, caplog, capsys, kind, phase):
    w = isolated_worker
    def failure():
        if kind == "generic":
            return OSError(RAW_ERROR)
        cls = DatasetServiceError if kind == "dataset" else lora_trainer.TrainerServiceError
        code = RAW_ERROR if kind == "unknown-code" else "dataset_locked" if kind == "dataset" else "output_missing"
        return cls(code, RAW_ERROR, {"nested": {"traceback": RAW_ERROR}, "current_dataset_hash": RAW_ERROR})
    def fail(*args, **kwargs):
        w.event.set()
        try:
            raise RuntimeError("inner " + RAW_ERROR)
        except RuntimeError as cause:
            raise failure() from cause
    def spawn(**kwargs):
        write_lora(w.root / "artifacts" / "旅人.safetensors")
        return SimpleNamespace(stdout=iter([]), returncode=0, wait=lambda: w.event.set())
    monkeypatch.setattr(lora_trainer, "_run_training_subprocess", fail if phase == "launch" else spawn)
    if phase == "registration":
        monkeypatch.setattr(lora_trainer, "_register_output_lora", fail)
    lora_trainer._queue.append(w.job)
    lora_trainer._worker_loop()
    internal = lora_trainer.get_job_status(w.job.job_id)
    client = TestClient(app)
    result = client.get("/api/lora-train/jobs/" + w.job.job_id).json()
    logs = client.get("/api/lora-train/jobs/" + w.job.job_id + "/logs").json()
    aggregate = client.get("/api/lora-train/status").json()
    run_log = (w.root / "logs/training.log").read_text()
    assert_safe(internal["error_message"], internal["error_details"], result, logs, aggregate, run_log, caplog.text, capsys.readouterr().out)
    assert all(record.exc_info is None for record in caplog.records)
    assert internal["status"] == "failed" and not aggregate["last_result"]["success"]
    assert result["error_code"] and result["error_message"] and result["error_details"]["hint"]
    assert result["error_details"]["phase"] in {"prepared", "registering"}
    assert result["error_details"]["classification"]
    assert aggregate["last_result"]["error_code"] == result["error_code"]
    assert aggregate["last_result"]["error_details"]["hint"]
    assert w.callbacks == []
    snapshot = json.loads((w.root / "training-parameters.json").read_text())
    assert_safe(snapshot, (w.root / "training-parameters.md").read_text())
    assert snapshot["trainer_process"] == ("not started" if phase == "launch" else "spawned")
    assert bool(snapshot["started_utc"]) == (phase == "registration")
    assert internal["execution_evidence"]["argv"]
    assert str(w.root / "artifacts") in internal["execution_evidence"]["argv"]
    assert str(w.root.parent.parent.parent / w.job.folder) in internal["execution_evidence"]["dataset_config_content"]
    assert w.root.exists() and w.job.resolved_output_name == "旅人"


def test_trainer_stdout_exception_is_not_logged_or_replayed(isolated_worker, monkeypatch, caplog, capsys):
    w = isolated_worker
    monkeypatch.setattr(lora_trainer, "_run_training_subprocess", lambda **kw: SimpleNamespace(
        stdout=iter(["epoch 1/2 " + RAW_ERROR, "Traceback: " + RAW_ERROR]), returncode=1, wait=lambda: w.event.set(),
    ))
    lora_trainer._queue.append(w.job)
    lora_trainer._worker_loop()
    result = lora_trainer.get_job_status(w.job.job_id)
    assert result["status"] == "failed" and result["error_code"] == "kohya_failed"
    assert_safe(result, lora_trainer.get_status(), (w.root / "logs/training.log").read_text(), caplog.text, capsys.readouterr().out)
    assert w.callbacks == []


def test_callback_exception_keeps_registered_artifact_truth_and_safe_logs(isolated_worker, monkeypatch, caplog):
    w = isolated_worker
    def callback(*args):
        raise RuntimeError(RAW_ERROR)
    def spawn(**kwargs):
        write_lora(w.root / "artifacts/旅人.safetensors")
        return SimpleNamespace(stdout=iter([]), returncode=0, wait=lambda: w.event.set())
    monkeypatch.setattr(lora_trainer, "_on_complete_callbacks", [callback])
    monkeypatch.setattr(lora_trainer, "_run_training_subprocess", spawn)
    lora_trainer._queue.append(w.job)
    lora_trainer._worker_loop()
    result = lora_trainer.get_job_status(w.job.job_id)
    assert result["status"] == "completed" and result["registration_status"] == "registered"
    assert_safe(caplog.text, (w.root / "logs/training.log").read_text())
    assert "completion_callback_failed" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("kind", ["trainer", "dataset", "generic"])
def test_start_http_errors_never_echo_typed_messages_or_nested_details(monkeypatch, kind):
    def enqueue(*args, **kwargs):
        cls = {"trainer": lora_trainer.TrainerServiceError, "dataset": DatasetServiceError, "generic": ValueError}[kind]
        raise cls("dataset_locked", RAW_ERROR, {"nested": RAW_ERROR}) if kind != "generic" else cls(RAW_ERROR)
    monkeypatch.setattr(lora_trainer, "enqueue", enqueue)
    response = TestClient(app).post("/api/lora-train/start", json={
        "folder": "fixture", "output_name": "旅人", "expected_dataset_hash": "a" * 64, "expected_profile_hash": "b" * 64, "recipe": {},
    })
    assert response.status_code in {400, 409}
    assert_safe(response.text)
    assert response.json()["detail"]["code"] and response.json()["detail"]["hint"]


@pytest.mark.parametrize('operation', ['cancel', 'smoke'])
def test_operation_exceptions_are_safe_in_http_and_persistence(isolated_worker, monkeypatch, operation):
    w = isolated_worker
    def fail(*args, **kwargs):
        raise OSError(RAW_ERROR)
    if operation == 'cancel':
        lora_trainer._update_persistent_job(w.job.job_id, status='running', stage='training')
        monkeypatch.setattr(lora_trainer, '_running', lora_trainer._RunningJob(w.job, SimpleNamespace(terminate=fail), 0, None, 1))
    else:
        lora_trainer._update_persistent_job(w.job.job_id, status='completed', stage='completed', registered_lora_name=f'AI-Drawing/{w.job.run_locator}/旅人.safetensors')
        monkeypatch.setattr(lora_trainer, 'submit_generation', fail)
    response = TestClient(app).post('/api/lora-train/jobs/' + w.job.job_id + ('/cancel' if operation == 'cancel' else '/smoke-test'), json={})
    if operation == 'cancel':
        assert response.status_code == 400
        assert response.json()['detail']['code'] == 'job_cancel_failed'
        assert response.json()['detail']['hint']
    else:
        assert response.status_code == 200
        assert response.json()['smoke_test_status'] == 'submission_unknown'
        assert response.json()['error_code'] == 'smoke_submission_unknown'
        assert response.json()['hint']
        assert lora_trainer.get_job_status(w.job.job_id)['smoke_test_status']=='submission_unknown'
    assert_safe(response.text, lora_trainer.get_job_status(w.job.job_id))


def test_preflight_metadata_is_public_but_start_payload_remains_exact(isolated_worker, monkeypatch):
    from app.schemas.lora_train import TrainingDecisionPreflightResponse, TrainingStartPayload, ComponentIdentity
    from app.services import lora_training_decision
    w = isolated_worker
    start = TrainingStartPayload(folder='fixture', output_name='旅人', expected_dataset_hash='a' * 64, expected_profile_hash='b' * 64, recipe={'model': {'checkpoint': 'chosen-model.safetensors'}})
    result = TrainingDecisionPreflightResponse(
        folder='fixture', decision='train', output_name='旅人', start_payload=start,
        component_identities={'checkpoint': ComponentIdentity(kind='checkpoint', verification_status='unverified', resolved_locator=WINDOWS, reason=RAW_ERROR)},
    )
    monkeypatch.setattr(lora_training_decision, 'decide_training_preflight', lambda *a, **kw: result)
    response = TestClient(app).post('/api/lora-train/datasets/training-decision-preflight', json={'folder':'fixture', 'output_name':'旅人'})
    assert response.status_code == 200
    assert_safe(response.text)
    assert response.json()['start_payload'] == start.model_dump(mode='json')
    assert result.component_identities['checkpoint'].resolved_locator == WINDOWS


def test_profile_json_read_error_becomes_safe_public_assessment(isolated_worker, monkeypatch):
    from pathlib import Path
    w = isolated_worker
    dataset = Path(w.settings.lora_train_dir) / w.job.folder
    profile = dataset / '.lora-dataset.json'
    profile.write_text('{}')
    original = Path.read_text
    def read(path, *args, **kwargs):
        if path == profile:
            raise OSError(RAW_ERROR)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    response = TestClient(app).get('/api/lora-train/datasets/' + w.job.folder + '/metadata')
    assert response.status_code == 200
    assert response.json()['valid'] is False
    assert response.json()['errors'][0]['code'] == 'invalid_profile_json'
    assert_safe(response.text)
    assert response.json()['errors'][0]['details']['hint']


def test_preflight_recipe_exception_is_a_safe_blocking_assessment(monkeypatch):
    from app.schemas.lora_train import TrainingDecisionPreflightResponse
    from app.services import lora_training_decision
    from app.services.lora_training_recipe import RecipeError
    issue = lora_training_decision._recipe_issue(RecipeError('recipe_validation_failed', RAW_ERROR, RAW_ERROR, {'nested': RAW_ERROR}))
    result = TrainingDecisionPreflightResponse(folder='fixture', decision='do_not_train', blocking_issues=[issue])
    monkeypatch.setattr(lora_training_decision, 'decide_training_preflight', lambda *a, **kw: result)
    response = TestClient(app).post('/api/lora-train/datasets/training-decision-preflight', json={'folder':'fixture', 'output_name':'旅人'})
    assert response.status_code == 200 and response.json()['decision'] == 'do_not_train'
    assert response.json()['blocking_issues'][0]['code'] == 'recipe_validation_failed'
    assert response.json()['blocking_issues'][0]['details']['hint']
    assert_safe(response.text)


def test_preflight_validation_does_not_echo_rejected_private_input():
    response = TestClient(app).post('/api/lora-train/datasets/training-decision-preflight', json={'folder':'fixture', 'output_name':RAW_ERROR})
    assert response.status_code == 422
    assert_safe(response.text)


def test_legacy_failure_and_log_tail_are_safe_without_rewriting_record(isolated_worker, monkeypatch):
    w = isolated_worker
    (w.root / "logs/training.log").write_text("legacy " + RAW_ERROR + "\nepoch 1/2\n")
    lora_trainer._update_persistent_job(w.job.job_id, run_locator=None, error_code="unexpected_error", error_message=RAW_ERROR, error_details={"raw": RAW_ERROR}, registration_error=RAW_ERROR, smoke_test_error=RAW_ERROR)
    client = TestClient(app)
    job = client.get("/api/lora-train/jobs/" + w.job.job_id)
    logs = client.get("/api/lora-train/jobs/" + w.job.job_id + "/logs?lines=1")
    assert_safe(job.text, logs.text)
    assert logs.json()["truncated"] is True
    assert "redacted" in logs.json()["lines"][0] or "progress" in logs.json()["lines"][0]
    assert lora_trainer.get_job_status(w.job.job_id)["error_message"] == RAW_ERROR
    def fail(*args):
        raise PermissionError(RAW_ERROR)
    monkeypatch.setattr(lora_trainer, "_tail_lines", fail)
    response = client.get("/api/lora-train/jobs/" + w.job.job_id + "/logs")
    assert response.json()["ok"] is False and response.json()["error_code"] == "log_read_failed"
    assert_safe(response.text)
