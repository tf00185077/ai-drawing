from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.prompt_library import FilePromptLibraryProvider
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_models import PromptCategory
from app.schemas.prompt_library import CategorySummary, CategoryWriteRequest


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _category(cid: str, order: int, parent_id: str | None = None) -> dict:
    doc = {
        "schema_version": 1,
        "id": cid,
        "polarity": "positive",
        "name_zh": cid,
        "description_zh": f"{cid} desc",
        "aliases": [],
        "keywords": [],
        "order": order,
        "revision": 1,
        "archived": False,
        "entries": [],
    }
    if parent_id is not None:
        doc["parent_id"] = parent_id
    return doc


@pytest.fixture
def provider(tmp_path: Path) -> FilePromptLibraryProvider:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True)
    (root / "negative").mkdir()
    (root / "combinations").mkdir()
    _write_json(root / "manifest.json", {
        "schema_version": 2, "library_id": "default", "name": "Test",
        "description_zh": "測試", "comma_atomic_version": 1,
        "comma_atomic_migration_required": False,
    })
    return FilePromptLibraryProvider(root)


def test_category_parent_id_defaults_none_and_roundtrips():
    assert PromptCategory(id="clothing", polarity="positive", name_zh="服裝",
                          description_zh="d").parent_id is None
    child = PromptCategory(id="clothing-top", polarity="positive", name_zh="上衣",
                           description_zh="d", parent_id="clothing")
    assert child.parent_id == "clothing"


def test_category_summary_carries_parent_id():
    summary = CategorySummary(id="clothing-top", polarity="positive", name_zh="上衣",
                              description_zh="d", order=10, revision=1, archived=False,
                              entry_count=0, etag="x", parent_id="clothing")
    assert summary.parent_id == "clothing"


def test_catalog_surfaces_parent_id(provider: FilePromptLibraryProvider):
    root = provider.store.root
    _write_json(root / "positive" / "clothing.json", _category("clothing", 10))
    _write_json(root / "positive" / "clothing-top.json",
                _category("clothing-top", 10, parent_id="clothing"))
    catalog = provider.catalog()
    by_id = {c.id: c for c in catalog.categories}
    assert by_id["clothing"].parent_id is None
    assert by_id["clothing-top"].parent_id == "clothing"


def test_category_write_request_accepts_parent_id():
    req = CategoryWriteRequest(name_zh="上衣", description_zh="d", order=10,
                               expected_revision=0, parent_id="clothing")
    assert req.parent_id == "clothing"


def _save(provider, cid, parent_id=None, expected_revision=0):
    return provider.save_category("positive", cid, CategoryWriteRequest(
        name_zh=cid, description_zh="d", order=10,
        expected_revision=expected_revision, parent_id=parent_id))


def test_save_category_persists_valid_parent(provider):
    _save(provider, "clothing")
    _save(provider, "clothing-top", parent_id="clothing")
    stored = provider.get_category("positive", "clothing-top")
    assert stored.category.parent_id == "clothing"


def test_save_category_rejects_missing_parent(provider):
    with pytest.raises(PromptLibraryError) as exc:
        _save(provider, "clothing-top", parent_id="nope")
    assert exc.value.status_code == 422


def test_save_category_rejects_self_parent(provider):
    with pytest.raises(PromptLibraryError):
        _save(provider, "clothing", parent_id="clothing")


def test_save_category_rejects_cross_polarity_parent(provider):
    # negative category as parent of a positive one → rejected
    provider.save_category("negative", "neg-root", CategoryWriteRequest(
        name_zh="n", description_zh="d", order=10, expected_revision=0))
    with pytest.raises(PromptLibraryError):
        _save(provider, "clothing-top", parent_id="neg-root")


def test_save_category_rejects_cycle(provider):
    _save(provider, "a")
    _save(provider, "b", parent_id="a")
    # now try to make a's parent = b → cycle a->b->a
    with pytest.raises(PromptLibraryError):
        provider.save_category("positive", "a", CategoryWriteRequest(
            name_zh="a", description_zh="d", order=10,
            expected_revision=1, parent_id="b"))


from app.core.prompt_library_tree import validate_category_tree


def _summary(cid, order=10, parent_id=None, polarity="positive"):
    return CategorySummary(id=cid, polarity=polarity, name_zh=cid, description_zh="d",
                           order=order, revision=1, archived=False, entry_count=0,
                           etag="x", parent_id=parent_id)


def test_validate_tree_keeps_valid_parents():
    adjusted, diags = validate_category_tree([
        _summary("clothing"), _summary("clothing-top", parent_id="clothing"),
    ])
    assert diags == []
    assert {c.id: c.parent_id for c in adjusted} == {"clothing": None, "clothing-top": "clothing"}


def test_validate_tree_demotes_missing_parent():
    adjusted, diags = validate_category_tree([_summary("top", parent_id="ghost")])
    assert {c.id: c.parent_id for c in adjusted} == {"top": None}
    assert len(diags) == 1 and diags[0].details["category_id"] == "top"


def test_validate_tree_demotes_self_parent():
    adjusted, diags = validate_category_tree([_summary("loop", parent_id="loop")])
    assert {c.id: c.parent_id for c in adjusted} == {"loop": None}
    assert len(diags) == 1 and diags[0].details["category_id"] == "loop"


def test_validate_tree_demotes_cross_polarity_parent():
    adjusted, diags = validate_category_tree([
        _summary("np", polarity="negative"),
        _summary("pos", parent_id="np", polarity="positive"),
    ])
    assert {c.id: c.parent_id for c in adjusted}["pos"] is None
    assert len(diags) == 1


def test_validate_tree_breaks_cycle():
    adjusted, diags = validate_category_tree([
        _summary("a", parent_id="b"), _summary("b", parent_id="a"),
    ])
    # at least one edge demoted so the result is acyclic; a diagnostic emitted
    parents = {c.id: c.parent_id for c in adjusted}
    assert parents["a"] is None or parents["b"] is None
    assert len(diags) >= 1


def test_catalog_demotes_dangling_parent_and_still_loads(provider):
    root = provider.store.root
    _write_json(root / "positive" / "top.json", _category("top", 10, parent_id="ghost"))
    catalog = provider.catalog()
    by_id = {c.id: c for c in catalog.categories}
    assert by_id["top"].parent_id is None
    assert any(d.details.get("category_id") == "top" for d in catalog.diagnostics)
