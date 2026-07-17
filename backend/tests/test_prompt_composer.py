from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.prompt_library import FilePromptLibraryProvider
from app.core.prompt_library_models import PromptEntryRef, PromptFragment
from app.schemas.prompt_library import ComposeRequest


@pytest.fixture
def library_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompt_library"
    for directory in ("positive", "negative", "combinations"):
        (root / directory).mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "library_id": "default",
                "name": "Test Prompt Library",
                "description_zh": "測試提示詞資料庫",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def entry(
    entry_id: str,
    prompt: str,
    *,
    revision: int = 1,
    archived: bool = False,
) -> dict[str, object]:
    return {
        "id": entry_id,
        "name_zh": entry_id,
        "description_zh": f"{entry_id} description",
        "prompt": prompt,
        "aliases": [],
        "keywords": [],
        "order": 10,
        "revision": revision,
        "archived": archived,
    }


def write_category(
    root: Path,
    polarity: str,
    category_id: str,
    entries: list[dict[str, object]],
    *,
    archived: bool = False,
) -> None:
    document = {
        "schema_version": 1,
        "id": category_id,
        "polarity": polarity,
        "name_zh": category_id,
        "description_zh": f"{category_id} description",
        "aliases": [],
        "keywords": [],
        "order": 10,
        "revision": 1,
        "archived": archived,
        "entries": entries,
    }
    (root / polarity / f"{category_id}.json").write_text(
        json.dumps(document, ensure_ascii=False), encoding="utf-8"
    )


def ref_fragment(
    polarity: str,
    category_id: str,
    entry_id: str,
    *,
    snapshot: str,
    source_revision: int | None = 1,
    order: int = 10,
    weight: float = 1.0,
) -> PromptFragment:
    return PromptFragment(
        kind="entry",
        ref=PromptEntryRef(
            polarity=polarity, category_id=category_id, entry_id=entry_id
        ),
        snapshot=snapshot,
        source_revision=source_revision,
        order=order,
        weight=weight,
    )


def literal(text: str, *, order: int = 10, weight: float = 1.0) -> PromptFragment:
    return PromptFragment(kind="literal", snapshot=text, order=order, weight=weight)


@pytest.fixture
def provider(library_root: Path) -> FilePromptLibraryProvider:
    write_category(
        library_root,
        "positive",
        "clothing",
        [entry("dress", "dress", revision=3)],
    )
    write_category(
        library_root,
        "negative",
        "quality",
        [entry("low-quality", "low quality", revision=2)],
    )
    return FilePromptLibraryProvider(library_root)


def write_combination(root: Path) -> None:
    document = {
        "schema_version": 1,
        "id": "portrait-dress",
        "name_zh": "洋裝人像",
        "description_zh": "常用人像",
        "aliases": [],
        "keywords": [],
        "order": 10,
        "revision": 1,
        "archived": False,
        "legacy_template": False,
        "positive": [
            literal("1girl", order=10).model_dump(mode="json"),
            ref_fragment(
                "positive", "clothing", "dress", snapshot="old dress", order=20
            ).model_dump(mode="json"),
        ],
        "negative": [
            ref_fragment(
                "negative", "quality", "low-quality", snapshot="low quality"
            ).model_dump(mode="json")
        ],
        "positive_prompt_snapshot": "1girl, old dress",
        "negative_prompt_snapshot": "low quality",
    }
    (root / "combinations" / "portrait-dress.json").write_text(
        json.dumps(document, ensure_ascii=False), encoding="utf-8"
    )


def test_compose_resolves_current_prompt_and_formats_weight(
    provider: FilePromptLibraryProvider,
) -> None:
    request = ComposeRequest(
        positive=[
            ref_fragment(
                "positive",
                "clothing",
                "dress",
                snapshot="typo",
                source_revision=1,
                order=20,
                weight=1.2,
            ),
            literal("1girl", order=10),
        ],
        negative=[
            ref_fragment(
                "negative", "quality", "low-quality", snapshot="low quality"
            )
        ],
    )

    result = provider.compose(request)

    assert result.positive_prompt == "1girl, (dress:1.2)"
    assert result.negative_prompt == "low quality"
    assert result.positive[1].snapshot == "dress"
    assert result.positive[1].source_revision == 3
    assert result.negative[0].source_revision == 2
    assert result.snapshot_repaired is True


def test_stable_order_uses_input_index_when_orders_are_equal(
    provider: FilePromptLibraryProvider,
) -> None:
    result = provider.compose(
        ComposeRequest(
            positive=[
                literal("second", order=20),
                literal("first", order=10),
                literal("third", order=20),
            ]
        )
    )

    assert result.positive_prompt == "first, second, third"
    assert [fragment.snapshot for fragment in result.positive] == [
        "first",
        "second",
        "third",
    ]


def test_first_duplicate_reference_wins_but_literals_are_kept(
    provider: FilePromptLibraryProvider,
) -> None:
    first = ref_fragment(
        "positive", "clothing", "dress", snapshot="dress", weight=1.1
    )
    duplicate = first.model_copy(update={"weight": 1.7})

    result = provider.compose(
        ComposeRequest(
            positive=[first, duplicate, literal("soft light"), literal("soft light")]
        )
    )

    assert result.positive_prompt == "(dress:1.1), soft light, soft light"
    assert [warning.code for warning in result.warnings] == ["duplicate_reference"]
    assert result.warnings[0].ref == first.ref


def test_missing_reference_uses_snapshot_with_structured_warning(
    provider: FilePromptLibraryProvider,
) -> None:
    missing = ref_fragment(
        "positive", "clothing", "missing", snapshot="blue coat"
    )

    result = provider.compose(ComposeRequest(positive=[missing]))

    assert result.positive_prompt == "blue coat"
    assert result.positive == [missing]
    assert result.snapshot_repaired is False
    assert result.warnings[0].code == "missing_reference"
    assert result.warnings[0].message
    assert result.warnings[0].hint
    assert result.warnings[0].ref == missing.ref


@pytest.mark.parametrize(
    ("category_archived", "entry_archived"), [(True, False), (False, True)]
)
def test_archived_category_or_entry_uses_snapshot(
    library_root: Path, category_archived: bool, entry_archived: bool
) -> None:
    write_category(
        library_root,
        "positive",
        "clothing",
        [entry("dress", "current dress", revision=4, archived=entry_archived)],
        archived=category_archived,
    )
    provider = FilePromptLibraryProvider(library_root)
    original = ref_fragment(
        "positive", "clothing", "dress", snapshot="saved dress", source_revision=1
    )

    result = provider.compose(ComposeRequest(positive=[original]))

    assert result.positive_prompt == "saved dress"
    assert result.positive == [original]
    assert result.snapshot_repaired is False
    assert [warning.code for warning in result.warnings] == ["archived_reference"]


def test_compose_imports_repaired_saved_combination_then_appends_request_fragments(
    provider: FilePromptLibraryProvider, library_root: Path
) -> None:
    write_combination(library_root)

    result = provider.compose(
        ComposeRequest(
            combination_id="portrait-dress",
            positive=[literal("soft lighting", order=30)],
            negative=[literal("watermark", order=20)],
        )
    )

    assert result.positive_prompt == "1girl, dress, soft lighting"
    assert result.negative_prompt == "low quality, watermark"
    assert result.snapshot_repaired is True


def test_compose_result_is_deeply_isolated_from_cache_request_and_disk(
    provider: FilePromptLibraryProvider, library_root: Path
) -> None:
    write_combination(library_root)
    request_fragment = literal("soft lighting", order=30)
    request = ComposeRequest(
        combination_id="portrait-dress", positive=[request_fragment]
    )
    cached_before = provider.get_combination("portrait-dress").combination

    result = provider.compose(request)

    assert result.positive[0] is not cached_before.positive[0]
    assert result.positive[1] is not cached_before.positive[1]
    assert result.positive[1].ref is not cached_before.positive[1].ref
    assert result.positive[2] is not request_fragment
    assert result.positive[2] is not request.positive[0]

    result.positive[0].snapshot = "mutated literal"
    assert result.positive[1].ref is not None
    result.positive[1].ref.entry_id = "mutated-ref"
    result.positive[2].snapshot = "mutated request"

    cached_after = provider.get_combination("portrait-dress").combination
    disk = json.loads(
        (library_root / "combinations" / "portrait-dress.json").read_text(
            encoding="utf-8"
        )
    )
    next_result = provider.compose(request)

    assert cached_after.positive[0].snapshot == "1girl"
    assert cached_after.positive[1].ref is not None
    assert cached_after.positive[1].ref.entry_id == "dress"
    assert disk["positive"][0]["snapshot"] == "1girl"
    assert disk["positive"][1]["ref"]["entry_id"] == "dress"
    assert request_fragment.snapshot == "soft lighting"
    assert request.positive[0].snapshot == "soft lighting"
    assert next_result.positive_prompt == "1girl, dress, soft lighting"


@pytest.mark.parametrize(
    ("text", "weight", "rendered"),
    [
        (" , detailed, ", 1.0, "detailed"),
        ("detail", 1.2344, "(detail:1.234)"),
        ("detail", 1.2, "(detail:1.2)"),
        ("detail", 0.875, "(detail:0.875)"),
    ],
)
def test_compose_formats_fragment_weights_exactly(
    provider: FilePromptLibraryProvider, text: str, weight: float, rendered: str
) -> None:
    result = provider.compose(
        ComposeRequest(positive=[literal(text, weight=weight)])
    )

    assert result.positive_prompt == rendered
