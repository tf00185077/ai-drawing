import pytest
from pydantic import ValidationError

from app.core.prompt_library_models import (
    PromptCategory,
    PromptCombination,
    PromptEntry,
    PromptEntryRef,
    PromptFragment,
    PromptLibraryManifest,
)
from app.core.prompt_library_errors import PromptLibraryError
from app.schemas.prompt_library import ArchiveRequest, ComposeRequest, EntryWriteRequest


def entry(**overrides):
    values = {
        "id": "dress",
        "name_zh": "連身裙",
        "description_zh": "一件式裙裝",
        "prompt": "dress",
        "aliases": ["洋裝", "one-piece dress"],
        "keywords": ["服裝", "wardrobe"],
        "order": 10,
        "revision": 1,
        "archived": False,
    }
    return PromptEntry.model_validate(values | overrides)


def test_category_rejects_duplicate_entry_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate entry id"):
        PromptCategory(
            schema_version=1,
            id="clothing",
            polarity="positive",
            name_zh="服裝",
            description_zh="服裝提示詞",
            aliases=[],
            keywords=[],
            order=10,
            revision=1,
            archived=False,
            entries=[entry(), entry(prompt="evening dress")],
        )


@pytest.mark.parametrize("bad_id", ["Dress", "two words", "../escape", "a/b"])
def test_slug_fields_reject_unsafe_ids(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        entry(id=bad_id)


def test_combination_ids_accept_safe_unicode_but_reject_unsafe_paths() -> None:
    combination = PromptCombination(
        id="niji基礎瑟瑟",
        name_zh="Niji 基礎瑟瑟",
        description_zh="Niji 基礎提示詞",
    )
    assert combination.id == "niji基礎瑟瑟"

    for bad_id in ("兩 個", "../逃逸", "a/b", "a\\b", ".", "-開頭", "結尾-"):
        with pytest.raises(ValidationError):
            PromptCombination(
                id=bad_id,
                name_zh="不安全",
                description_zh="不安全組合 ID",
            )


def test_fragment_kind_and_reference_must_agree() -> None:
    ref = PromptEntryRef(polarity="positive", category_id="clothing", entry_id="dress")
    assert PromptFragment(kind="entry", ref=ref, snapshot="dress").ref == ref
    with pytest.raises(ValidationError, match="entry fragment requires ref"):
        PromptFragment(kind="entry", snapshot="dress")
    with pytest.raises(ValidationError, match="literal fragment cannot have ref"):
        PromptFragment(kind="literal", ref=ref, snapshot="free text")


def test_persisted_models_reject_extra_fields_and_invalid_versions_or_revisions() -> None:
    with pytest.raises(ValidationError):
        entry(unexpected=True)
    with pytest.raises(ValidationError):
        PromptLibraryManifest(
            library_id="default",
            name="AI Drawing Prompt Library",
            description_zh="提示詞資料庫",
            unexpected=True,
        )
    with pytest.raises(ValidationError):
        PromptCategory(
            schema_version=2,
            id="clothing",
            polarity="positive",
            name_zh="服裝",
            description_zh="服裝提示詞",
        )
    with pytest.raises(ValidationError):
        entry(revision=0)
    with pytest.raises(ValidationError):
        PromptCombination(
            schema_version=2,
            id="portrait",
            name_zh="肖像",
            description_zh="肖像提示詞組合",
        )


def test_fragment_rejects_blank_snapshots_and_literal_source_revisions() -> None:
    with pytest.raises(ValidationError, match="fragment snapshot cannot be empty"):
        PromptFragment(kind="literal", snapshot="   ")
    with pytest.raises(ValidationError, match="literal fragment cannot have source_revision"):
        PromptFragment(kind="literal", snapshot="free text", source_revision=1)


def test_error_envelope_has_actionable_details() -> None:
    error = PromptLibraryError.invalid_locator("a/b")

    assert error.status_code == 400
    assert error.as_dict() == {
        "code": "invalid_locator",
        "message": error.message,
        "hint": error.hint,
        "details": {"resource_id": "a/b"},
    }


@pytest.mark.parametrize(
    ("error", "code", "status_code"),
    [
        (PromptLibraryError.not_found("entry", "dress"), "not_found", 404),
        (PromptLibraryError.invalid_locator("a/b"), "invalid_locator", 400),
        (PromptLibraryError.revision_conflict(2, 1), "revision_conflict", 409),
        (PromptLibraryError.external_change("before", "after"), "external_change", 409),
        (PromptLibraryError.invalid_document("positive/clothing.json", "bad JSON"), "invalid_document", 422),
        (PromptLibraryError.lock_timeout(5.0), "lock_timeout", 423),
    ],
)
def test_named_errors_have_structured_http_envelopes(
    error: PromptLibraryError, code: str, status_code: int
) -> None:
    assert error.code == code
    assert error.status_code == status_code
    assert error.as_dict()["code"] == code
    assert error.as_dict()["message"]
    assert error.as_dict()["hint"]


def test_write_dtos_enforce_concurrency_and_reject_unknown_fields() -> None:
    request = EntryWriteRequest(
        expected_revision=0,
        name_zh="連身裙",
        description_zh="一件式裙裝",
        prompt="dress",
    )
    assert request.expected_etag is None
    assert ArchiveRequest(
        expected_revision=1,
        resource_type="entry",
        resource_id="dress",
        polarity="positive",
        category_id="clothing",
    ).resource_id == "dress"
    with pytest.raises(ValidationError):
        EntryWriteRequest(
            expected_revision=0,
            name_zh="連身裙",
            description_zh="一件式裙裝",
            prompt="dress",
            unexpected=True,
        )
    with pytest.raises(ValidationError):
        EntryWriteRequest(
            expected_revision=-1,
            name_zh="連身裙",
            description_zh="一件式裙裝",
            prompt="dress",
        )
    with pytest.raises(ValidationError):
        ComposeRequest(unexpected=True)
