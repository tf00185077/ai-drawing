from __future__ import annotations
import json
from pathlib import Path
import pytest
from app.core.prompt_library import FilePromptLibraryProvider
from app.core.prompt_library_errors import PromptLibraryError
from app.schemas.prompt_library import MoveEntryRequest


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _cat(cid: str, entries: list[dict]) -> dict:
    return {"schema_version": 1, "id": cid, "polarity": "positive", "name_zh": cid,
            "description_zh": "d", "aliases": [], "keywords": [], "order": 10,
            "revision": 1, "archived": False, "entries": entries}


def _entry(eid: str, prompt: str) -> dict:
    return {"id": eid, "name_zh": eid, "description_zh": "d", "prompt": prompt,
            "aliases": [], "keywords": [], "order": 10, "revision": 1, "archived": False}


@pytest.fixture
def provider(tmp_path: Path) -> FilePromptLibraryProvider:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True); (root / "negative").mkdir(); (root / "combinations").mkdir()
    _write(root / "manifest.json", {"schema_version": 2, "library_id": "default", "name": "T",
            "description_zh": "測試", "comma_atomic_version": 1, "comma_atomic_migration_required": False})
    _write(root / "positive" / "src.json", _cat("src", [_entry("dress", "dress"), _entry("skirt", "skirt")]))
    _write(root / "positive" / "dst.json", _cat("dst", [_entry("hat", "hat")]))
    return FilePromptLibraryProvider(root)


def _req(
    to: str, prompt: str = "dress", name: str = "洋裝", rev: int = 1,
    etag: str | None = None,
) -> MoveEntryRequest:
    return MoveEntryRequest(to_category_id=to, name_zh=name, description_zh="d", prompt=prompt,
                            aliases=[], keywords=[], order=10, expected_revision=rev,
                            expected_etag=etag)


def test_move_removes_from_source_adds_to_dest_with_edits(provider):
    src_etag = provider.get_category("positive", "src").etag
    resp = provider.move_entry("positive", "src", "dress", _req("dst", name="洋裝(改)", etag=src_etag))
    src = provider.get_category("positive", "src")
    dst = provider.get_category("positive", "dst")
    assert [e.id for e in src.category.entries] == ["skirt"]
    assert src.category.revision == 2
    moved = next(e for e in dst.category.entries if e.id == "dress")
    assert moved.name_zh == "洋裝(改)" and dst.category.revision == 2
    assert resp.entry.id == "dress"


def test_move_to_same_category_is_in_place_edit(provider):
    src_etag = provider.get_category("positive", "src").etag
    provider.move_entry("positive", "src", "dress", _req("src", name="原地改", etag=src_etag))
    src = provider.get_category("positive", "src")
    assert next(e for e in src.category.entries if e.id == "dress").name_zh == "原地改"
    assert [e.id for e in src.category.entries] == ["dress", "skirt"]


def test_move_rejects_id_conflict_without_writing(provider):
    # give dst its own "dress" (dst rev 1->2); src is untouched (rev still 1)
    dst_etag = provider.get_category("positive", "dst").etag
    provider.save_entry(
        "positive", "dst", "dress",
        _req("dst", prompt="dress", name="dst洋裝", etag=dst_etag),
    )
    src_etag = provider.get_category("positive", "src").etag
    with pytest.raises(PromptLibraryError) as exc:
        provider.move_entry("positive", "src", "dress", _req("dst", etag=src_etag))  # src expected_revision=1
    assert exc.value.status_code == 422
    # src still has dress (not written away)
    assert any(e.id == "dress" for e in provider.get_category("positive", "src").category.entries)


def test_move_entry_not_found(provider):
    src_etag = provider.get_category("positive", "src").etag
    with pytest.raises(PromptLibraryError) as exc:
        provider.move_entry("positive", "src", "ghost", _req("dst", prompt="ghost", name="無", etag=src_etag))
    assert exc.value.status_code == 404


def test_move_target_not_found(provider):
    src_etag = provider.get_category("positive", "src").etag
    with pytest.raises(PromptLibraryError) as exc:
        provider.move_entry("positive", "src", "dress", _req("nope", etag=src_etag))
    assert exc.value.status_code == 404


def test_move_stale_source_revision_409(provider):
    with pytest.raises(PromptLibraryError) as exc:
        provider.move_entry("positive", "src", "dress", _req("dst", rev=99))
    assert exc.value.status_code == 409
