from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import prompt_library as prompt_library_api
from app.core.prompt_library import FilePromptLibraryProvider
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_migration_control import (
    CommaAtomicMigrationControl,
    MigrationPrivilege,
)
from app.schemas.prompt_library import (
    ArchiveRequest,
    CategoryWriteRequest,
    CombinationWriteRequest,
    ComposeRequest,
    EntryWriteRequest,
    RestoreRequest,
)
from app.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREDECESSOR_MANIFEST = (
    PROJECT_ROOT / "backend/tests/fixtures/comma_atomic_predecessor_manifest.base64"
)


def legacy_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True)
    (root / "negative").mkdir()
    (root / "combinations").mkdir()
    (root / "manifest.json").write_bytes(
        base64.b64decode(PREDECESSOR_MANIFEST.read_text(encoding="ascii"))
    )
    # A provider guard must reject before attempting to parse this file.
    (root / "positive" / "broken.json").write_text("{not-json", encoding="utf-8")
    return root


def test_bootstrap_creates_required_marker_before_provider_access(tmp_path: Path) -> None:
    root = legacy_root(tmp_path)

    provider = FilePromptLibraryProvider(root)

    status = provider.migration_status()
    assert status.model_dump() == {
        "state": "required",
        "marker_present": True,
        "comma_atomic_ready": False,
        "atomic_enforcement_active": False,
        "run_id": None,
        "data_validated": False,
    }
    marker = json.loads((root / ".comma-atomic-migration.json").read_text())
    assert marker["state"] == "required"


def test_every_provider_operation_fails_closed_before_catalog_access(
    tmp_path: Path,
) -> None:
    provider = FilePromptLibraryProvider(legacy_root(tmp_path))
    operations = [
        lambda: provider.catalog(),
        lambda: provider.search("anything"),
        lambda: provider.get_category("positive", "broken"),
        lambda: provider.get_combination("broken"),
        lambda: provider.compose(ComposeRequest()),
        lambda: provider.save_category(
            "positive",
            "new",
            CategoryWriteRequest(
                expected_revision=0,
                name_zh="新增",
                description_zh="新增分類",
            ),
        ),
        lambda: provider.save_entry(
            "positive",
            "broken",
            "entry",
            EntryWriteRequest(
                expected_revision=0,
                name_zh="項目",
                description_zh="項目說明",
                prompt="atom",
            ),
        ),
        lambda: provider.save_combination(
            "blocked",
            CombinationWriteRequest(
                expected_revision=0,
                name_zh="組合",
                description_zh="組合說明",
            ),
        ),
        lambda: provider.archive(
            ArchiveRequest(
                resource_type="category",
                resource_id="broken",
                polarity="positive",
                expected_revision=1,
                expected_etag="etag",
            )
        ),
        lambda: provider.restore(
            RestoreRequest(
                resource_type="category",
                resource_id="broken",
                polarity="positive",
                expected_revision=1,
                expected_etag="etag",
            )
        ),
        lambda: provider.acknowledge_literal_conversion(
            "blocked",
            {"document_context_token": "opaque"},
        ),
    ]

    for operation in operations:
        with pytest.raises(PromptLibraryError) as captured:
            operation()
        assert captured.value.code == "comma_atomic_migration_unavailable"
        assert captured.value.status_code == 503

    assert provider._cache == {}


def test_status_is_independent_but_every_ordinary_api_route_fails_closed(
    tmp_path: Path,
) -> None:
    provider = FilePromptLibraryProvider(legacy_root(tmp_path))
    app.dependency_overrides[prompt_library_api._provider] = lambda: provider
    client = TestClient(app)
    operations = [
        ("GET", "/api/prompt-library/catalog", None),
        ("GET", "/api/prompt-library/search?q=anything", None),
        ("GET", "/api/prompt-library/categories/positive/broken", None),
        (
            "PUT",
            "/api/prompt-library/categories/positive/new",
            {
                "expected_revision": 0,
                "name_zh": "新增",
                "description_zh": "新增分類",
            },
        ),
        (
            "PUT",
            "/api/prompt-library/categories/positive/broken/entries/entry",
            {
                "expected_revision": 0,
                "name_zh": "項目",
                "description_zh": "項目說明",
                "prompt": "atom",
            },
        ),
        (
            "POST",
            "/api/prompt-library/archive",
            {
                "resource_type": "category",
                "resource_id": "broken",
                "polarity": "positive",
                "expected_revision": 1,
                "expected_etag": "etag",
            },
        ),
        (
            "POST",
            "/api/prompt-library/restore",
            {
                "resource_type": "category",
                "resource_id": "broken",
                "polarity": "positive",
                "expected_revision": 1,
                "expected_etag": "etag",
            },
        ),
        ("POST", "/api/prompt-library/compose", {"positive": [], "negative": []}),
        ("GET", "/api/prompt-library/combinations", None),
        ("GET", "/api/prompt-library/combinations/blocked", None),
        (
            "PUT",
            "/api/prompt-library/combinations/blocked",
            {
                "expected_revision": 0,
                "name_zh": "組合",
                "description_zh": "組合說明",
            },
        ),
        (
            "POST",
            "/api/prompt-library/combinations/blocked/acknowledge-literal-conversion",
            {"document_context_token": "opaque"},
        ),
    ]
    try:
        status = client.get("/api/prompt-library/migration-status")
        assert status.status_code == 200
        assert status.json()["state"] == "required"
        assert status.json()["comma_atomic_ready"] is False

        for method, path, payload in operations:
            response = client.request(method, path, json=payload)
            assert response.status_code == 503, (method, path, response.text)
            assert (
                response.json()["detail"]["code"]
                == "comma_atomic_migration_unavailable"
            )
    finally:
        app.dependency_overrides.pop(prompt_library_api._provider, None)

    assert provider._cache == {}


def test_privileged_path_requires_control_issued_capability_and_lock(
    tmp_path: Path,
) -> None:
    control = CommaAtomicMigrationControl(legacy_root(tmp_path))
    control.bootstrap()
    forged = MigrationPrivilege(nonce="forged")

    with pytest.raises(PromptLibraryError, match="privilege"):
        with control.locked(forged):
            pass

    privilege = control.issue_privilege()
    with control.locked(privilege) as marker:
        assert marker is not None
        assert marker.state == "required"
        assert control.lock_path.exists()


def test_migration_lock_has_one_owner_and_times_out_other_controls(
    tmp_path: Path,
) -> None:
    root = legacy_root(tmp_path)
    owner = CommaAtomicMigrationControl(root, lock_timeout=0.01)
    owner.bootstrap()
    contender = CommaAtomicMigrationControl(root, lock_timeout=0.01)

    with owner.locked(owner.issue_privilege()):
        with pytest.raises(PromptLibraryError) as captured:
            with contender.locked(contender.issue_privilege()):
                pass

    assert captured.value.code == "lock_timeout"


def test_migration_lock_is_outside_the_prompt_library_tree(
    tmp_path: Path,
) -> None:
    root = legacy_root(tmp_path)
    control = CommaAtomicMigrationControl(root)

    assert not control.lock_path.is_relative_to(root)
    assert control.lock_path != root / ".prompt-library.lock"
    with control.locked(control.issue_privilege()):
        assert control.lock_path.exists()
        assert not (root / ".prompt-library.lock").exists()


def test_finalized_atomic_manifest_has_no_marker_and_is_ready(tmp_path: Path) -> None:
    root = legacy_root(tmp_path)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "library_id": "default",
                "name": "Atomic",
                "description_zh": "原子提示詞庫",
                "comma_atomic_version": 1,
                "comma_atomic_migration_required": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    provider = FilePromptLibraryProvider(root)

    assert provider.migration_status().model_dump() == {
        "state": "finalized",
        "marker_present": False,
        "comma_atomic_ready": True,
        "atomic_enforcement_active": True,
        "run_id": None,
        "data_validated": True,
    }
