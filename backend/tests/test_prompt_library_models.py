import pytest
from pydantic import ValidationError

from app.core.prompt_library_models import (
    PromptCategory,
    PromptEntry,
    PromptEntryRef,
    PromptFragment,
)
from app.core.prompt_library_errors import PromptLibraryError
from app.schemas.prompt_library import ArchiveRequest, EntryWriteRequest


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


def test_fragment_kind_and_reference_must_agree() -> None:
    ref = PromptEntryRef(polarity="positive", category_id="clothing", entry_id="dress")
    assert PromptFragment(kind="entry", ref=ref, snapshot="dress").ref == ref
    with pytest.raises(ValidationError, match="entry fragment requires ref"):
        PromptFragment(kind="entry", snapshot="dress")
    with pytest.raises(ValidationError, match="literal fragment cannot have ref"):
        PromptFragment(kind="literal", ref=ref, snapshot="free text")


def test_error_envelope_has_actionable_details() -> None:
    error = PromptLibraryError.invalid_locator("a/b")

    assert error.status_code == 400
    assert error.as_dict() == {
        "code": "invalid_locator",
        "message": error.message,
        "hint": error.hint,
        "details": {"resource_id": "a/b"},
    }


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
