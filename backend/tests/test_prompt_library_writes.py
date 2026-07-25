from __future__ import annotations

import json
from pathlib import Path

import pytest
from filelock import FileLock

from app.core.prompt_library import FilePromptLibraryProvider
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_models import PromptEntryRef, PromptFragment
from app.schemas.prompt_library import (
    ArchiveRequest,
    CategoryWriteRequest,
    CombinationWriteRequest,
    EntryWriteRequest,
    LiteralConversionAcknowledgeRequest,
    RestoreRequest,
)
from app.schemas.prompt_library_migration import (
    LegacyRefLocator,
    ProvenanceResolutionRequest,
)


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def provider(tmp_path: Path) -> FilePromptLibraryProvider:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True)
    (root / "negative").mkdir()
    (root / "combinations").mkdir()
    _write_json(
        root / "manifest.json",
        {
            "schema_version": 2,
            "library_id": "default",
            "name": "Test Prompt Library",
            "description_zh": "測試提示詞庫",
            "comma_atomic_version": 1,
            "comma_atomic_migration_required": False,
        },
    )
    _write_json(
        root / "positive" / "clothing.json",
        {
            "schema_version": 1,
            "id": "clothing",
            "polarity": "positive",
            "name_zh": "服裝",
            "description_zh": "服裝提示詞",
            "aliases": ["outfit"],
            "keywords": ["clothing"],
            "order": 10,
            "revision": 1,
            "archived": False,
            "entries": [
                {
                    "id": "dress",
                    "name_zh": "洋裝",
                    "description_zh": "一件式裙裝",
                    "prompt": "dress",
                    "aliases": ["連身裙"],
                    "keywords": ["wardrobe"],
                    "order": 10,
                    "revision": 1,
                    "archived": False,
                }
            ],
        },
    )
    _write_json(
        root / "combinations" / "portrait-dress.json",
        {
            "schema_version": 1,
            "id": "portrait-dress",
            "name_zh": "洋裝肖像",
            "description_zh": "測試組合",
            "aliases": [],
            "keywords": [],
            "order": 10,
            "revision": 1,
            "archived": False,
            "legacy_template": False,
            "positive": [
                {
                    "kind": "literal",
                    "snapshot": "1girl",
                    "weight": 1.0,
                    "order": 10,
                },
                {
                    "kind": "entry",
                    "ref": {
                        "polarity": "positive",
                        "category_id": "clothing",
                        "entry_id": "dress",
                    },
                    "snapshot": "dress",
                    "source_revision": 1,
                    "weight": 1.0,
                    "order": 20,
                },
            ],
            "negative": [],
            "positive_prompt_snapshot": "1girl, dress",
            "negative_prompt_snapshot": "",
        },
    )
    return FilePromptLibraryProvider(root)


def entry_write(**overrides: object) -> EntryWriteRequest:
    values: dict[str, object] = {
        "name_zh": "洋裝",
        "description_zh": "一件式裙裝",
        "prompt": "dress",
        "aliases": ["連身裙"],
        "keywords": ["wardrobe"],
        "order": 10,
        "expected_revision": 1,
        "expected_etag": None,
    }
    return EntryWriteRequest.model_validate(values | overrides)


def write_unknown_legacy_combination(provider: FilePromptLibraryProvider) -> None:
    _write_json(
        provider.root / "combinations" / "unknown-legacy.json",
        {
            "schema_version": 1,
            "id": "unknown-legacy",
            "name_zh": "未知舊來源",
            "description_zh": "測試阻擋來源診斷",
            "aliases": [],
            "keywords": [],
            "order": 30,
            "revision": 1,
            "archived": False,
            "legacy_template": False,
            "positive": [
                {
                    "kind": "entry",
                    "ref": {
                        "polarity": "positive",
                        "category_id": "removed",
                        "entry_id": "legacy-group",
                    },
                    "snapshot": "a, b",
                    "source_revision": 1,
                    "weight": 1.2,
                    "order": 10,
                }
            ],
            "negative": [],
            "positive_prompt_snapshot": "(a, b:1.2)",
            "negative_prompt_snapshot": "",
        },
    )


def test_existing_write_requires_matching_revision_and_etag(provider) -> None:
    current = provider.get_category("positive", "clothing")
    with pytest.raises(PromptLibraryError) as revision:
        provider.save_entry(
            "positive",
            "clothing",
            "dress",
            entry_write(expected_revision=999, expected_etag=current.etag),
        )
    assert revision.value.code == "revision_conflict"

    path = provider.root / "positive" / "clothing.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(PromptLibraryError) as external:
        provider.save_entry(
            "positive",
            "clothing",
            "dress",
            entry_write(
                expected_revision=current.category.revision,
                expected_etag=current.etag,
            ),
        )
    assert external.value.code == "external_change"


def test_create_requires_revision_zero_and_no_etag(provider) -> None:
    request = CategoryWriteRequest(
        name_zh="姿勢",
        description_zh="姿勢提示詞",
        expected_revision=1,
    )
    with pytest.raises(PromptLibraryError) as caught:
        provider.save_category("positive", "poses", request)
    assert caught.value.code == "revision_conflict"


def test_metadata_only_category_update_preserves_entries(provider) -> None:
    current = provider.get_category("positive", "clothing")
    saved = provider.save_category(
        "positive",
        "clothing",
        CategoryWriteRequest(
            name_zh="衣著",
            description_zh="更新後描述",
            aliases=["outfit"],
            keywords=["clothing"],
            order=20,
            expected_revision=current.category.revision,
            expected_etag=current.etag,
        ),
    )
    assert saved.category is not None
    assert saved.category.category.revision == 2
    assert [entry.id for entry in saved.category.category.entries] == ["dress"]


def test_entry_correction_repairs_referencing_combinations(provider) -> None:
    category = provider.get_category("positive", "clothing")
    saved = provider.save_entry(
        "positive",
        "clothing",
        "dress",
        entry_write(
            prompt="evening dress",
            expected_revision=category.category.revision,
            expected_etag=category.etag,
        ),
    )
    combination = provider.get_combination("portrait-dress")
    referenced = next(item for item in combination.combination.positive if item.ref)
    assert referenced.snapshot == "evening dress"
    assert referenced.source_revision == saved.entry_revision
    assert combination.combination.positive_prompt_snapshot == "1girl,evening dress"
    assert saved.affected_combinations == ["portrait-dress"]


def test_lazy_read_repairs_partial_eager_update(provider) -> None:
    category_path = provider.root / "positive" / "clothing.json"
    category = json.loads(category_path.read_text(encoding="utf-8"))
    category["revision"] = 2
    category["entries"][0]["revision"] = 2
    category["entries"][0]["prompt"] = "corrected dress"
    _write_json(category_path, category)

    combination_path = provider.root / "combinations" / "portrait-dress.json"
    before = json.loads(combination_path.read_text(encoding="utf-8"))["revision"]
    loaded = provider.get_combination("portrait-dress")
    assert loaded.repaired is True
    assert loaded.combination.revision == before + 1
    assert loaded.combination.positive_prompt_snapshot == "1girl,corrected dress"


def test_unresolved_legacy_ref_loads_literal_fallback_without_persisting(
    provider: FilePromptLibraryProvider,
) -> None:
    write_unknown_legacy_combination(provider)
    path = provider.root / "combinations" / "unknown-legacy.json"
    before = path.read_bytes()

    loaded = provider.get_combination("unknown-legacy")

    assert [item.kind for item in loaded.combination.positive] == [
        "literal",
        "literal",
    ]
    assert [item.snapshot for item in loaded.combination.positive] == ["a", " b"]
    assert [item.weight for item in loaded.combination.positive] == [1.2, 1.2]
    assert loaded.combination.positive_prompt_snapshot == "(a:1.2),( b:1.2)"
    assert [item.code for item in loaded.warnings] == [
        "legacy_reference_unresolved"
    ]
    assert len(loaded.blocking_diagnostics) == 1
    assert loaded.blocking_diagnostics[0].polarity == "positive"
    assert loaded.blocking_diagnostics[0].fallback_start_position == 1
    assert loaded.blocking_diagnostics[0].fallback_count == 2
    assert loaded.document_context_token
    assert path.read_bytes() == before


def test_ordinary_update_and_save_as_cannot_drop_blocking_diagnostic(
    provider: FilePromptLibraryProvider,
) -> None:
    write_unknown_legacy_combination(provider)
    loaded = provider.get_combination("unknown-legacy")
    edited_literals = [
        PromptFragment(kind="literal", snapshot="edited", order=10)
    ]

    with pytest.raises(PromptLibraryError) as update:
        provider.save_combination(
            "unknown-legacy",
            CombinationWriteRequest(
                name_zh="未知舊來源",
                description_zh="普通編輯不是確認",
                positive=edited_literals,
                expected_revision=loaded.combination.revision,
                expected_etag=loaded.etag,
            ),
        )
    assert update.value.code == "unresolved_legacy_provenance"

    with pytest.raises(PromptLibraryError) as save_as:
        provider.save_combination(
            "copied-legacy",
            CombinationWriteRequest(
                name_zh="複製舊來源",
                description_zh="另存也不可繞過",
                positive=edited_literals,
                expected_revision=0,
                source_combination_id="unknown-legacy",
            ),
        )
    assert save_as.value.code == "unresolved_legacy_provenance"
    assert not (provider.root / "combinations" / "copied-legacy.json").exists()


def test_explicit_literal_conversion_token_allows_update(
    provider: FilePromptLibraryProvider,
) -> None:
    write_unknown_legacy_combination(provider)
    loaded = provider.get_combination("unknown-legacy")
    assert loaded.document_context_token is not None
    acknowledgement = provider.acknowledge_literal_conversion(
        "unknown-legacy",
        LiteralConversionAcknowledgeRequest(
            document_context_token=loaded.document_context_token
        ),
    )

    saved = provider.save_combination(
        "unknown-legacy",
        CombinationWriteRequest(
            name_zh="未知舊來源",
            description_zh="已明示轉為文字",
            positive=loaded.combination.positive,
            expected_revision=loaded.combination.revision,
            expected_etag=loaded.etag,
            document_context_token=loaded.document_context_token,
            literal_conversion_token=acknowledgement.literal_conversion_token,
        ),
    )

    assert saved.combination is not None
    assert saved.combination.blocking_diagnostics == []
    assert [item.kind for item in saved.combination.combination.positive] == [
        "literal",
        "literal",
    ]


def test_tampered_conversion_token_and_partial_resolution_fail_closed(
    provider: FilePromptLibraryProvider,
) -> None:
    write_unknown_legacy_combination(provider)
    loaded = provider.get_combination("unknown-legacy")
    assert loaded.document_context_token is not None
    acknowledgement = provider.acknowledge_literal_conversion(
        "unknown-legacy",
        LiteralConversionAcknowledgeRequest(
            document_context_token=loaded.document_context_token
        ),
    )
    request_values = {
        "name_zh": "未知舊來源",
        "description_zh": "不可接受竄改 token",
        "positive": loaded.combination.positive,
        "expected_revision": loaded.combination.revision,
        "expected_etag": loaded.etag,
        "document_context_token": loaded.document_context_token,
    }

    with pytest.raises(PromptLibraryError) as tampered:
        provider.save_combination(
            "unknown-legacy",
            CombinationWriteRequest(
                **request_values,
                literal_conversion_token=(
                    acknowledgement.literal_conversion_token + "tampered"
                ),
            ),
        )
    assert tampered.value.code == "invalid_document_resolution_token"

    with pytest.raises(PromptLibraryError) as partial:
        provider.save_combination(
            "unknown-legacy",
            CombinationWriteRequest(**request_values),
        )
    assert partial.value.code == "unresolved_legacy_provenance"


def test_explicit_replacement_ref_resolves_block(
    provider: FilePromptLibraryProvider,
) -> None:
    write_unknown_legacy_combination(provider)
    loaded = provider.get_combination("unknown-legacy")
    assert loaded.document_context_token is not None
    diagnostic_id = loaded.blocking_diagnostics[0].id
    replacement = PromptEntryRef(
        polarity="positive",
        category_id="clothing",
        entry_id="dress",
    )

    saved = provider.save_combination(
        "unknown-legacy",
        CombinationWriteRequest(
            name_zh="替換舊來源",
            description_zh="使用明確詞庫來源",
            positive=[
                PromptFragment(
                    kind="entry",
                    ref=replacement,
                    snapshot="dress",
                    source_revision=1,
                    order=10,
                )
            ],
            expected_revision=loaded.combination.revision,
            expected_etag=loaded.etag,
            document_context_token=loaded.document_context_token,
            provenance_resolutions=[
                ProvenanceResolutionRequest(
                    document_context_token=loaded.document_context_token,
                    diagnostic_id=diagnostic_id,
                    action="replacement_entries",
                    replacement_refs=[
                        LegacyRefLocator(
                            polarity="positive",
                            category_id="clothing",
                            entry_id="dress",
                        )
                    ],
                )
            ],
        ),
    )

    assert saved.combination is not None
    assert saved.combination.combination.positive[0].ref == replacement


def test_unrelated_ref_cannot_resolve_while_diagnostic_fallback_remains(
    provider: FilePromptLibraryProvider,
) -> None:
    write_unknown_legacy_combination(provider)
    loaded = provider.get_combination("unknown-legacy")
    assert loaded.document_context_token is not None
    diagnostic_id = loaded.blocking_diagnostics[0].id
    replacement = PromptEntryRef(
        polarity="positive",
        category_id="clothing",
        entry_id="dress",
    )

    with pytest.raises(PromptLibraryError) as captured:
        provider.save_combination(
            "unknown-legacy",
            CombinationWriteRequest(
                name_zh="錯誤替換",
                description_zh="fallback 仍在，額外 ref 不算替換",
                positive=[
                    *loaded.combination.positive,
                    PromptFragment(
                        kind="entry",
                        ref=replacement,
                        snapshot="dress",
                        source_revision=1,
                        order=30,
                    ),
                ],
                expected_revision=loaded.combination.revision,
                expected_etag=loaded.etag,
                document_context_token=loaded.document_context_token,
                provenance_resolutions=[
                    ProvenanceResolutionRequest(
                        document_context_token=loaded.document_context_token,
                        diagnostic_id=diagnostic_id,
                        action="replacement_entries",
                        replacement_refs=[
                            LegacyRefLocator(
                                polarity="positive",
                                category_id="clothing",
                                entry_id="dress",
                            )
                        ],
                    )
                ],
            ),
        )

    assert captured.value.code == "unresolved_legacy_provenance"


def test_replacement_preserves_unrelated_equal_literal(
    provider: FilePromptLibraryProvider,
) -> None:
    write_unknown_legacy_combination(provider)
    path = provider.root / "combinations" / "unknown-legacy.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["positive"].insert(
        0,
        {
            "kind": "literal",
            "snapshot": "a",
            "weight": 1.0,
            "order": 5,
        },
    )
    _write_json(path, document)
    loaded = provider.get_combination("unknown-legacy")
    diagnostic = loaded.blocking_diagnostics[0]
    replacement = PromptEntryRef(
        polarity="positive",
        category_id="clothing",
        entry_id="dress",
    )

    saved = provider.save_combination(
        "unknown-legacy",
        CombinationWriteRequest(
            name_zh="保留同文 literal",
            description_zh="只替換診斷範圍",
            positive=[
                loaded.combination.positive[0],
                PromptFragment(
                    kind="entry",
                    ref=replacement,
                    snapshot="dress",
                    source_revision=1,
                    order=20,
                ),
            ],
            expected_revision=loaded.combination.revision,
            expected_etag=loaded.etag,
            document_context_token=loaded.document_context_token,
            provenance_resolutions=[
                ProvenanceResolutionRequest(
                    document_context_token=loaded.document_context_token,
                    diagnostic_id=diagnostic.id,
                    action="replacement_entries",
                    replacement_refs=[
                        LegacyRefLocator(
                            polarity="positive",
                            category_id="clothing",
                            entry_id="dress",
                        )
                    ],
                )
            ],
        ),
    )

    assert [
        (fragment.kind, fragment.snapshot)
        for fragment in saved.combination.combination.positive
    ] == [("literal", "a"), ("entry", "dress")]


def test_archive_entry_uses_parent_token_and_marks_entry_archived(provider) -> None:
    current = provider.get_category("positive", "clothing")
    saved = provider.archive(
        ArchiveRequest(
            resource_type="entry",
            resource_id="dress",
            polarity="positive",
            category_id="clothing",
            expected_revision=current.category.revision,
            expected_etag=current.etag,
        )
    )
    assert saved.entry is not None and saved.entry.archived is True
    assert saved.category is not None and saved.category.category.revision == 2


@pytest.mark.parametrize("resource_type", ["category", "combination"])
def test_archive_marks_top_level_resource_archived(provider, resource_type: str) -> None:
    if resource_type == "category":
        current = provider.get_category("positive", "clothing")
        request = ArchiveRequest(
            resource_type="category",
            resource_id="clothing",
            polarity="positive",
            expected_revision=current.category.revision,
            expected_etag=current.etag,
        )
    else:
        current = provider.get_combination("portrait-dress")
        request = ArchiveRequest(
            resource_type="combination",
            resource_id="portrait-dress",
            expected_revision=current.combination.revision,
            expected_etag=current.etag,
        )

    saved = provider.archive(request)

    if resource_type == "category":
        assert saved.category is not None and saved.category.category.archived is True
    else:
        assert saved.combination is not None
        assert saved.combination.combination.archived is True


def test_combination_create_composes_snapshots(provider) -> None:
    saved = provider.save_combination(
        "new-combination",
        CombinationWriteRequest(
            name_zh="新組合",
            description_zh="新提示詞組合",
            positive=[
                {
                    "kind": "literal",
                    "snapshot": "masterpiece",
                    "order": 10,
                }
            ],
            expected_revision=0,
        ),
    )
    assert saved.combination is not None
    assert saved.combination.combination.revision == 1
    assert saved.combination.combination.positive_prompt_snapshot == "masterpiece"


def test_stale_lock_timeout_maps_to_domain_error(provider) -> None:
    held_lock = FileLock(provider.root / ".lock")
    held_lock.acquire()
    provider.store.lock_timeout = 0
    try:
        with pytest.raises(PromptLibraryError) as caught:
            provider.save_category(
                "positive",
                "poses",
                CategoryWriteRequest(
                    name_zh="姿勢",
                    description_zh="姿勢提示詞",
                    expected_revision=0,
                ),
            )
    finally:
        held_lock.release()
    assert caught.value.code == "lock_timeout"


def _archive_category(provider: FilePromptLibraryProvider):
    current = provider.get_category("positive", "clothing")
    return provider.archive(
        ArchiveRequest(
            resource_type="category",
            resource_id="clothing",
            polarity="positive",
            expected_revision=current.category.revision,
            expected_etag=current.etag,
        )
    )


def _archive_entry(provider: FilePromptLibraryProvider):
    current = provider.get_category("positive", "clothing")
    return provider.archive(
        ArchiveRequest(
            resource_type="entry",
            resource_id="dress",
            polarity="positive",
            category_id="clothing",
            expected_revision=current.category.revision,
            expected_etag=current.etag,
        )
    )


def test_archive_then_restore_category_increments_version_and_changes_etag(provider) -> None:
    archived = _archive_category(provider)
    assert archived.category is not None

    restored = provider.restore(
        RestoreRequest(
            resource_type="category",
            resource_id="clothing",
            polarity="positive",
            expected_revision=archived.category.category.revision,
            expected_etag=archived.category.etag,
        )
    )

    assert restored.category is not None
    assert restored.category.category.archived is False
    assert restored.category.category.revision == archived.category.category.revision + 1
    assert restored.category.etag != archived.category.etag


def test_restore_category_preserves_entry_archive_state_and_revision(provider) -> None:
    archived_entry = _archive_entry(provider)
    assert archived_entry.category is not None and archived_entry.entry is not None
    archived_category = provider.archive(
        ArchiveRequest(
            resource_type="category",
            resource_id="clothing",
            polarity="positive",
            expected_revision=archived_entry.category.category.revision,
            expected_etag=archived_entry.category.etag,
        )
    )
    assert archived_category.category is not None

    restored = provider.restore(
        RestoreRequest(
            resource_type="category",
            resource_id="clothing",
            polarity="positive",
            expected_revision=archived_category.category.category.revision,
            expected_etag=archived_category.category.etag,
        )
    )

    assert restored.category is not None
    entry = restored.category.category.entries[0]
    assert entry.archived is True
    assert entry.revision == archived_entry.entry.revision


def test_archive_then_restore_entry_increments_entry_and_parent_versions(provider) -> None:
    archived = _archive_entry(provider)
    assert archived.category is not None and archived.entry is not None

    restored = provider.restore(
        RestoreRequest(
            resource_type="entry",
            resource_id="dress",
            polarity="positive",
            category_id="clothing",
            expected_revision=archived.category.category.revision,
            expected_etag=archived.category.etag,
        )
    )

    assert restored.category is not None and restored.entry is not None
    assert restored.entry.archived is False
    assert restored.entry.revision == archived.entry.revision + 1
    assert restored.entry_revision == restored.entry.revision
    assert restored.category.category.revision == archived.category.category.revision + 1
    assert restored.category.etag != archived.category.etag
    assert restored.affected_combinations == []


@pytest.mark.parametrize(
    ("expected_revision_delta", "expected_etag", "code"),
    [(1, "current", "revision_conflict"), (0, "stale", "external_change")],
)
def test_restore_rejects_stale_parent_token_without_mutation(
    provider, expected_revision_delta: int, expected_etag: str, code: str
) -> None:
    archived = _archive_entry(provider)
    assert archived.category is not None
    path = provider.root / "positive" / "clothing.json"
    before = path.read_bytes()

    with pytest.raises(PromptLibraryError) as caught:
        provider.restore(
            RestoreRequest(
                resource_type="entry",
                resource_id="dress",
                polarity="positive",
                category_id="clothing",
                expected_revision=(
                    archived.category.category.revision + expected_revision_delta
                ),
                expected_etag=(
                    archived.category.etag if expected_etag == "current" else expected_etag
                ),
            )
        )

    assert caught.value.code == code
    assert path.read_bytes() == before


@pytest.mark.parametrize("resource_type", ["category", "entry"])
def test_restore_rejects_already_active_resource_without_mutation(
    provider, resource_type: str
) -> None:
    current = provider.get_category("positive", "clothing")
    path = provider.root / "positive" / "clothing.json"
    before = path.read_bytes()

    with pytest.raises(PromptLibraryError) as caught:
        provider.restore(
            RestoreRequest(
                resource_type=resource_type,
                resource_id="clothing" if resource_type == "category" else "dress",
                polarity="positive",
                category_id="clothing" if resource_type == "entry" else None,
                expected_revision=current.category.revision,
                expected_etag=current.etag,
            )
        )

    assert caught.value.code == "resource_already_active"
    assert path.read_bytes() == before


def test_restore_missing_entry_returns_not_found_without_mutation(provider) -> None:
    current = provider.get_category("positive", "clothing")
    path = provider.root / "positive" / "clothing.json"
    before = path.read_bytes()

    with pytest.raises(PromptLibraryError) as caught:
        provider.restore(
            RestoreRequest(
                resource_type="entry",
                resource_id="missing",
                polarity="positive",
                category_id="clothing",
                expected_revision=current.category.revision,
                expected_etag=current.etag,
            )
        )

    assert caught.value.code == "not_found"
    assert path.read_bytes() == before


def test_restore_entry_rejects_archived_parent_without_mutation(provider) -> None:
    archived_entry = _archive_entry(provider)
    assert archived_entry.category is not None
    archived_category = provider.archive(
        ArchiveRequest(
            resource_type="category",
            resource_id="clothing",
            polarity="positive",
            expected_revision=archived_entry.category.category.revision,
            expected_etag=archived_entry.category.etag,
        )
    )
    assert archived_category.category is not None
    path = provider.root / "positive" / "clothing.json"
    before = path.read_bytes()

    with pytest.raises(PromptLibraryError) as caught:
        provider.restore(
            RestoreRequest(
                resource_type="entry",
                resource_id="dress",
                polarity="positive",
                category_id="clothing",
                expected_revision=archived_category.category.category.revision,
                expected_etag=archived_category.category.etag,
            )
        )

    assert caught.value.code == "parent_category_archived"
    assert caught.value.details == {
        "polarity": "positive",
        "category_id": "clothing",
        "entry_id": "dress",
    }
    assert path.read_bytes() == before


def test_restore_checks_concurrency_before_active_or_parent_state(provider) -> None:
    current = provider.get_category("positive", "clothing")
    with pytest.raises(PromptLibraryError) as active_conflict:
        provider.restore(
            RestoreRequest(
                resource_type="category",
                resource_id="clothing",
                polarity="positive",
                expected_revision=current.category.revision + 1,
                expected_etag=current.etag,
            )
        )
    assert active_conflict.value.code == "revision_conflict"

    archived_entry = _archive_entry(provider)
    assert archived_entry.category is not None
    archived_category = provider.archive(
        ArchiveRequest(
            resource_type="category",
            resource_id="clothing",
            polarity="positive",
            expected_revision=archived_entry.category.category.revision,
            expected_etag=archived_entry.category.etag,
        )
    )
    assert archived_category.category is not None
    with pytest.raises(PromptLibraryError) as parent_conflict:
        provider.restore(
            RestoreRequest(
                resource_type="entry",
                resource_id="dress",
                polarity="positive",
                category_id="clothing",
                expected_revision=archived_category.category.category.revision + 1,
                expected_etag=archived_category.category.etag,
            )
        )
    assert parent_conflict.value.code == "revision_conflict"
