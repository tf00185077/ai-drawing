from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_training_status_is_not_an_automation_runbook():
    docs = PROJECT_ROOT / "docs"
    assert not (docs / "lora-training-agent-handoff-runbook.md").exists()
    assert not (docs / "lora-methods").exists()
    text = (docs / "training-status.md").read_text(encoding="utf-8")
    assert "not a training runbook" in text
    assert "not accepted as a complete" in text or "not accepted as a complete" in (
        PROJECT_ROOT / "README.md"
    ).read_text(encoding="utf-8")


def test_training_status_distinguishes_submitted_smoke_from_completed_artifact():
    text = (PROJECT_ROOT / "docs" / "training-status.md").read_text(encoding="utf-8")
    assert "artifact=None" in text
    assert "submitted" in text
    assert "registration error" in text
    assert "Valid safetensors" in text


def test_training_role_and_execution_are_deferred():
    text = (PROJECT_ROOT / "docs" / "training-status.md").read_text(encoding="utf-8")
    assert "team/roles/lora-training.md" in text
    assert "The role is not yet created or activated" in text
    assert "does not grant permission to train" in text
