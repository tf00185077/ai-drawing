from test_support import activate

_TEST_ROOT = activate()  # MUST precede pytest, Settings, database and app imports.

import pytest
import threading
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def isolated_worker_admission(monkeypatch):
    """A prior TestClient shutdown must not close a later test's fresh runtime."""
    from app.core import queue
    from app.services import lora_trainer, comfyui_history_watcher, watcher

    for module in (queue, lora_trainer, comfyui_history_watcher):
        monkeypatch.setattr(module, "_stop_event", threading.Event())
    monkeypatch.setattr(watcher, "_closing", False)


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch):
    """Memory reset and durable isolation are distinct; bind a fresh real DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db import database
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, 'engine', engine)
    monkeypatch.setattr(database, 'SessionLocal', sessionmaker(bind=engine))
    yield
    engine.dispose()
