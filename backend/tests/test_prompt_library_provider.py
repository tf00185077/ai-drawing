from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

import pytest
from filelock import FileLock

from app.core.prompt_library import FilePromptLibraryProvider
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_models import PromptCategory, PromptCombination
from app.core.prompt_library_store import PromptLibraryStore


@pytest.fixture
def library_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True)
    (root / "negative").mkdir()
    (root / "combinations").mkdir()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "library_id": "default",
                "name": "Test Prompt Library",
                "description_zh": "測試用提示詞資料庫",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def entry_dict(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "id": "dress",
        "name_zh": "洋裝",
        "description_zh": "測試洋裝條目",
        "prompt": "dress",
        "aliases": ["連身裙"],
        "keywords": ["wardrobe"],
        "order": 10,
        "revision": 1,
        "archived": False,
    }
    return values | overrides


def category_dict(
    category_id: str, polarity: str, *, entries: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": category_id,
        "polarity": polarity,
        "name_zh": "服裝",
        "description_zh": "測試服裝分類",
        "aliases": ["outfit"],
        "keywords": ["clothing"],
        "order": 10,
        "revision": 1,
        "archived": False,
        "entries": entries,
    }


def write_category(
    root: Path,
    polarity: str,
    category_id: str,
    *,
    entries: list[dict[str, object]],
    document_id: str | None = None,
    document_polarity: str | None = None,
) -> Path:
    path = root / polarity / f"{category_id}.json"
    path.write_text(
        json.dumps(
            category_dict(
                document_id or category_id,
                document_polarity or polarity,
                entries=entries,
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def combination_dict(combination_id: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": combination_id,
        "name_zh": "測試組合",
        "description_zh": "測試提示詞組合",
        "aliases": [],
        "keywords": [],
        "order": 10,
        "revision": 1,
        "archived": False,
        "legacy_template": False,
        "positive": [],
        "negative": [],
        "positive_prompt_snapshot": "",
        "negative_prompt_snapshot": "",
    }


def write_combination(root: Path, filename: str, document_id: str | None = None) -> Path:
    path = root / "combinations" / f"{filename}.json"
    path.write_text(
        json.dumps(combination_dict(document_id or filename), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def create_directory_link(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (NotImplementedError, OSError):
        pass
    if os.name != "nt":
        pytest.skip("directory symlinks are unavailable in this environment")
    result = subprocess.run(
        ["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("creating a Windows junction requires unavailable privileges")


def test_catalog_loads_valid_category_from_temporary_library(library_root: Path) -> None:
    write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    provider = FilePromptLibraryProvider(library_root)

    catalog = provider.catalog()

    assert catalog.manifest.library_id == "default"
    assert [(item.polarity, item.id, item.entry_count) for item in catalog.categories] == [
        ("positive", "clothing", 1)
    ]
    assert catalog.diagnostics == []


def test_catalog_keeps_valid_files_and_reports_bad_neighbor(library_root: Path) -> None:
    write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    (library_root / "positive" / "broken.json").write_text("{not-json", encoding="utf-8")
    provider = FilePromptLibraryProvider(library_root)

    catalog = provider.catalog()

    assert [item.id for item in catalog.categories] == ["clothing"]
    assert catalog.diagnostics[0].code == "invalid_json"
    assert catalog.diagnostics[0].path == "positive/broken.json"


def test_catalog_reports_id_filename_mismatch_without_hiding_neighbors(library_root: Path) -> None:
    write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    write_category(
        library_root,
        "positive",
        "mismatched",
        document_id="other-category",
        entries=[entry_dict()],
    )

    catalog = FilePromptLibraryProvider(library_root).catalog()

    assert [item.id for item in catalog.categories] == ["clothing"]
    assert catalog.diagnostics[0].code == "id_filename_mismatch"
    assert catalog.diagnostics[0].path == "positive/mismatched.json"


def test_catalog_reports_polarity_mismatch_without_hiding_neighbors(library_root: Path) -> None:
    write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    write_category(
        library_root,
        "positive",
        "wrong-polarity",
        document_polarity="negative",
        entries=[entry_dict()],
    )

    catalog = FilePromptLibraryProvider(library_root).catalog()

    assert [item.id for item in catalog.categories] == ["clothing"]
    assert catalog.diagnostics[0].code == "polarity_mismatch"
    assert catalog.diagnostics[0].path == "positive/wrong-polarity.json"


def test_catalog_reports_combination_filename_mismatch(library_root: Path) -> None:
    write_combination(library_root, "mismatched", document_id="other-combination")

    catalog = FilePromptLibraryProvider(library_root).catalog()

    assert catalog.combinations == []
    assert catalog.diagnostics[0].code == "id_filename_mismatch"
    assert catalog.diagnostics[0].path == "combinations/mismatched.json"


def test_catalog_rejects_file_symlink_before_reading_external_document(library_root: Path) -> None:
    write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    outside = library_root.parent / "outside.json"
    outside.write_text(
        json.dumps(category_dict("external", "positive", entries=[entry_dict()])),
        encoding="utf-8",
    )
    try:
        os.symlink(outside, library_root / "positive" / "external.json")
    except (NotImplementedError, OSError):
        pytest.skip("file symlinks are unavailable in this environment")

    catalog = FilePromptLibraryProvider(library_root).catalog()

    assert [item.id for item in catalog.categories] == ["clothing"]
    assert catalog.diagnostics[-1].code == "unsafe_path"
    assert catalog.diagnostics[-1].path == "positive/external.json"


@pytest.mark.parametrize("directory", ["positive", "negative", "combinations"])
def test_catalog_rejects_linked_library_directories(
    library_root: Path, directory: str
) -> None:
    linked = library_root / directory
    linked.rmdir()
    outside = library_root.parent / f"outside-{directory}"
    outside.mkdir()
    if directory == "combinations":
        (outside / "external.json").write_text(
            json.dumps(combination_dict("external")), encoding="utf-8"
        )
    else:
        (outside / "external.json").write_text(
            json.dumps(category_dict("external", directory, entries=[entry_dict()])),
            encoding="utf-8",
        )
    create_directory_link(linked, outside)

    catalog = FilePromptLibraryProvider(library_root).catalog()

    assert catalog.categories == []
    assert catalog.combinations == []
    assert catalog.diagnostics[0].code == "unsafe_path"
    assert catalog.diagnostics[0].path == directory


def test_replace_json_rejects_nested_write_below_linked_parent(library_root: Path) -> None:
    linked_parent = library_root / "positive"
    linked_parent.rmdir()
    outside = library_root.parent / "outside-positive-write"
    outside.mkdir()
    create_directory_link(linked_parent, outside)
    category = PromptCategory.model_validate(
        category_dict("x", "positive", entries=[entry_dict()])
    )

    with pytest.raises(PromptLibraryError) as caught:
        PromptLibraryStore(library_root).replace_json(
            linked_parent / "missing-parent" / "x.json", category
        )

    assert caught.value.code == "invalid_document"
    assert not (outside / "missing-parent" / "x.json").exists()


def test_replace_json_creates_missing_normal_library_directories(library_root: Path) -> None:
    (library_root / "positive").rmdir()
    (library_root / "combinations").rmdir()
    store = PromptLibraryStore(library_root)
    category = PromptCategory.model_validate(
        category_dict("clothing", "positive", entries=[entry_dict()])
    )
    combination = PromptCombination.model_validate(combination_dict("portrait"))

    store.replace_json(store.category_path("positive", "clothing"), category)
    store.replace_json(store.combination_path("portrait"), combination)

    assert (library_root / "positive" / "clothing.json").is_file()
    assert (library_root / "combinations" / "portrait.json").is_file()


def test_store_does_not_leak_internal_location_mismatch(library_root: Path) -> None:
    write_category(
        library_root,
        "positive",
        "clothing",
        document_id="other-category",
        entries=[entry_dict()],
    )

    with pytest.raises(PromptLibraryError) as caught:
        PromptLibraryStore(library_root).read_category("positive", "clothing")

    assert caught.value.code == "invalid_document"


def test_external_byte_change_updates_etag_without_trusting_mtime(library_root: Path) -> None:
    path = write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    provider = FilePromptLibraryProvider(library_root)
    first = provider.get_category("positive", "clothing")
    stat = path.stat()
    path.write_text(
        path.read_text(encoding="utf-8").replace("dress", "skirt"), encoding="utf-8"
    )
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert (path.stat().st_mtime_ns, path.stat().st_size) == (stat.st_mtime_ns, stat.st_size)

    second = provider.get_category("positive", "clothing")

    assert second.etag != first.etag
    assert second.category.entries[0].prompt == "skirt"


def test_store_retries_when_the_file_changes_between_read_and_stat(
    library_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    original_read_bytes = Path.read_bytes
    changed = False
    read_count = 0

    def read_then_change(candidate: Path) -> bytes:
        nonlocal changed, read_count
        raw = original_read_bytes(candidate)
        read_count += 1
        if candidate == path and not changed:
            changed = True
            candidate.write_bytes(raw.replace(b"dress", b"skirt"))
        return raw

    monkeypatch.setattr(Path, "read_bytes", read_then_change)

    document = PromptLibraryStore(library_root).read_category("positive", "clothing")

    assert changed is True
    assert read_count >= 4
    assert document.model.entries[0].prompt == "skirt"


def test_concurrent_reader_cannot_overwrite_newer_cached_snapshot(
    library_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    provider = FilePromptLibraryProvider(library_root)
    original_read_bytes = Path.read_bytes
    stale_started = threading.Event()
    release_stale = threading.Event()
    fresh_finished = threading.Event()
    errors: list[BaseException] = []

    def delayed_stale_read(candidate: Path) -> bytes:
        raw = original_read_bytes(candidate)
        if candidate == path and threading.current_thread().name == "stale-reader":
            stale_started.set()
            assert release_stale.wait(timeout=5)
        return raw

    monkeypatch.setattr(Path, "read_bytes", delayed_stale_read)

    def stale_reader() -> None:
        try:
            provider.get_category("positive", "clothing")
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    def fresh_reader() -> None:
        try:
            provider.get_category("positive", "clothing")
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)
        finally:
            fresh_finished.set()

    stale = threading.Thread(target=stale_reader, name="stale-reader")
    stale.start()
    assert stale_started.wait(timeout=5)
    path.write_text(path.read_text(encoding="utf-8").replace("dress", "skirt"), encoding="utf-8")
    fresh = threading.Thread(target=fresh_reader, name="fresh-reader")
    fresh.start()
    fresh_finished.wait(timeout=0.25)
    release_stale.set()
    stale.join(timeout=5)
    fresh.join(timeout=5)

    assert errors == []
    assert not stale.is_alive() and not fresh.is_alive()
    cached = provider._cache[path.resolve()]
    assert cached.model.entries[0].prompt == "skirt"


@pytest.mark.parametrize("category_id", ["../secret", "a/b", "A"])
def test_get_category_rejects_unsafe_locator(
    library_root: Path, category_id: str
) -> None:
    provider = FilePromptLibraryProvider(library_root)

    with pytest.raises(PromptLibraryError) as caught:
        provider.get_category("positive", category_id)  # type: ignore[arg-type]

    assert caught.value.code == "invalid_locator"


def test_replace_json_is_validated_and_writes_stable_utf8_document(library_root: Path) -> None:
    store = PromptLibraryStore(library_root)
    path = store.category_path("positive", "clothing")
    category = PromptCategory.model_validate(
        category_dict("clothing", "positive", entries=[entry_dict()])
    )

    etag = store.replace_json(path, category)

    raw = path.read_bytes()
    assert etag
    assert raw.endswith(b"\n")
    assert b"\\u670d" not in raw
    assert json.loads(raw) == category.model_dump(mode="json")
    assert list(path.parent.glob("*.tmp")) == []


def test_locked_translates_file_lock_timeout(library_root: Path) -> None:
    held_lock = FileLock(library_root / ".lock")
    held_lock.acquire()
    try:
        with pytest.raises(PromptLibraryError) as caught:
            with PromptLibraryStore(library_root, lock_timeout=0).locked():
                pass
    finally:
        held_lock.release()

    assert caught.value.code == "lock_timeout"


def test_replace_json_cleans_up_temp_file_after_replace_failure(
    library_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = PromptLibraryStore(library_root)
    path = store.category_path("positive", "clothing")
    path.write_text("original", encoding="utf-8")
    category = PromptCategory.model_validate(
        category_dict("clothing", "positive", entries=[entry_dict()])
    )

    def failed_replace(source: Path, destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("app.core.prompt_library_store.os.replace", failed_replace)

    with pytest.raises(OSError, match="replace failed"):
        store.replace_json(path, category)

    assert path.read_text(encoding="utf-8") == "original"
    assert list(path.parent.glob("*.tmp")) == []
