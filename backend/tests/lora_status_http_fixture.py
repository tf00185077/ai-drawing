"""Offline real service -> FastAPI -> JSON fixture, also consumed by the UI test."""
from test_support import activate
activate()

import json
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.services import lora_trainer


def response_payload():
    def job(serial, folder):
        return SimpleNamespace(
            job_id=f"job-{serial}", folder=folder, output_name="水彩 旅人",
            resolved_output_name=f"水彩 旅人_{serial:03d}", output_serial=serial,
            run_locator=f"水彩 旅人_{serial:03d}__20261027T030000Z",
            output_config_hash="a" * 64,
        )
    running = lora_trainer._RunningJob(job(2, "dataset-a"), None, 0.5, 1, 2)
    with patch.object(lora_trainer, "_running", running), patch.object(
        lora_trainer, "_queue", [job(3, "dataset-b")]
    ), patch.object(lora_trainer, "_last_result", None):
        response = TestClient(app).get("/api/lora-train/status")
    assert response.status_code == 200
    return response.json()


if __name__ == "__main__":
    print(json.dumps(response_payload(), ensure_ascii=False))
