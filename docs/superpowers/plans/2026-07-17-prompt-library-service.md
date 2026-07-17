# Prompt Library Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project-scoped, Git-shareable bilingual Prompt Library, including safe JSON persistence, fuzzy search, prompt composition, saved combinations, CRUD/archive APIs, a 300–450-entry starter catalog, and the legacy prompt-template adapter.

**Architecture:** Store one versioned UTF-8 JSON document per category and saved combination under the project-root `prompt_library/` folder. A long-lived typed provider owns reads, diagnostics, search, composition, optimistic concurrency, file locking, atomic writes, and snapshot repair; FastAPI and later MCP/UI consumers use the same provider contract. Malformed files are isolated as diagnostics, while writes require both revision and raw-byte SHA-256 etag checks.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, `filelock>=3.29.7,<4.0.0`, JSON/SQLite-free persistence, pytest.

---

## Plan-set position and prerequisite

This is plan 1 of 3. Complete it before:

1. `2026-07-17-prompt-workbench-generation.md`
2. `2026-07-17-prompt-library-agent-tools.md`

The approved design is `docs/superpowers/specs/2026-07-17-prompt-library-workbench-design.md`.

## Locked file structure

### Create

- `backend/app/core/prompt_library_models.py` — persisted manifest/category/entry/reference/fragment/combination models and invariants.
- `backend/app/core/prompt_library_errors.py` — domain exceptions with `code`, `message`, `hint`, HTTP status, and details.
- `backend/app/core/prompt_library_store.py` — path confinement, raw-byte etags, validated JSON reads, lock acquisition, and atomic replacement.
- `backend/app/core/prompt_composer.py` — ordered reference resolution, weight rendering, warnings, and repair decisions.
- `backend/app/core/prompt_search.py` — NFKC normalization, weighted fuzzy scoring, and deterministic sorting.
- `backend/app/core/prompt_library_writes.py` — revision/etag preconditions and eager combination propagation.
- `backend/app/core/prompt_library.py` — provider protocol, file provider facade, cache invalidation, lazy repair, and singleton factory.
- `backend/app/schemas/prompt_library.py` — HTTP request/response DTOs only.
- `backend/app/api/prompt_library.py` — `/api/prompt-library` routes and dependency override point.
- `backend/tests/test_prompt_library_models.py`
- `backend/tests/test_prompt_library_provider.py`
- `backend/tests/test_prompt_library_writes.py`
- `backend/tests/test_prompt_composer.py`
- `backend/tests/test_prompt_search.py`
- `backend/tests/test_prompt_library_api.py`
- `backend/tests/test_prompt_library_seed.py`
- `prompt_library/manifest.json`
- `prompt_library/positive/*.json`, `prompt_library/negative/*.json`, and `prompt_library/combinations/*.json` listed in Task 6.

### Modify

- `backend/app/config.py:53-177` — configure and normalize `prompt_library_dir` and lock timeout.
- `backend/requirements.txt:1-17` — add the cross-platform lock dependency.
- `.env.example:19-21` — document the project-relative library path.
- `docker-compose.yml:4-18` — mount the root library into the backend container.
- `backend/app/main.py:65-90` — register the router.
- `backend/app/core/prompt_templates.py:11-90` — retain variable utilities but source legacy templates from combinations.
- `backend/app/api/prompt_templates.py:23-55` — inject the file-backed adapter.
- `backend/tests/test_prompt_templates.py:42-93` — prove compatibility and source-of-truth behavior.
- `docs/PROGRESS.md` — record completion of this independently testable backend stage.

## Public contract locked for plans 2 and 3

Use these names without renaming them later:

```python
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


Polarity = Literal["positive", "negative"]
ResourceType = Literal["category", "entry", "combination"]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PromptLibraryManifest(StrictModel):
    schema_version: Literal[1] = 1
    library_id: Slug
    name: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)


class PromptEntry(StrictModel):
    id: Slug
    name_zh: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int = Field(default=10, ge=0)
    revision: int = Field(default=1, ge=1)
    archived: bool = False


class PromptCategory(StrictModel):
    schema_version: Literal[1] = 1
    id: Slug
    polarity: Polarity
    name_zh: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int = Field(default=10, ge=0)
    revision: int = Field(default=1, ge=1)
    archived: bool = False
    entries: list[PromptEntry] = Field(default_factory=list)


class PromptEntryRef(StrictModel):
    polarity: Polarity
    category_id: Slug
    entry_id: Slug


class PromptFragment(StrictModel):
    kind: Literal["entry", "literal"]
    ref: PromptEntryRef | None = None
    snapshot: str
    source_revision: int | None = None
    weight: float = Field(default=1.0, gt=0.0, le=2.0)
    order: int = Field(default=10, ge=0)


class PromptCombination(StrictModel):
    schema_version: Literal[1] = 1
    id: Slug
    name_zh: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int = Field(default=10, ge=0)
    revision: int = Field(default=1, ge=1)
    archived: bool = False
    legacy_template: bool = False
    positive: list[PromptFragment] = Field(default_factory=list)
    negative: list[PromptFragment] = Field(default_factory=list)
    positive_prompt_snapshot: str = ""
    negative_prompt_snapshot: str = ""


class PromptWarning(StrictModel):
    code: str
    message: str
    hint: str
    ref: PromptEntryRef | None = None
    details: dict[str, object] = Field(default_factory=dict)


class ConcurrencyToken(StrictModel):
    expected_revision: int = Field(ge=0)
    expected_etag: str | None = None


class CategoryWriteRequest(ConcurrencyToken):
    name_zh: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int = Field(default=10, ge=0)


class CombinationWriteRequest(CategoryWriteRequest):
    legacy_template: bool = False
    positive: list[PromptFragment] = Field(default_factory=list)
    negative: list[PromptFragment] = Field(default_factory=list)


class CombinationSaveIntent(CombinationWriteRequest):
    id: Slug


class VersionedCombination(StrictModel):
    combination: PromptCombination
    etag: str
    repaired: bool = False
    warnings: list[PromptWarning] = Field(default_factory=list)


class ComposeRequest(StrictModel):
    combination_id: Slug | None = None
    positive: list[PromptFragment] = Field(default_factory=list)
    negative: list[PromptFragment] = Field(default_factory=list)
    save_as: CombinationSaveIntent | None = None

class ComposeResponse(StrictModel):
    positive_prompt: str
    negative_prompt: str
    positive: list[PromptFragment]
    negative: list[PromptFragment]
    warnings: list[PromptWarning]
    snapshot_repaired: bool
    saved_combination: VersionedCombination | None = None
```

Write endpoints accept flat bodies. Category and combination creation use `expected_revision=0` and omit `expected_etag`; every update/archive uses the current file revision and etag. Entry operations use the parent category file's token.

`combination_id` imports the current, lazily repaired saved combination into composition. Supplied positive and negative fragments are appended to the imported lanes and then normalized by `(order, input index)`; this lets an agent or UI load a common combination and add one-off text without binding it to workflow state.

---

### Task 1: Persisted models, API DTOs, configuration, and container visibility

**Files:**

- Create: `backend/app/core/prompt_library_models.py`
- Create: `backend/app/core/prompt_library_errors.py`
- Create: `backend/app/schemas/prompt_library.py`
- Modify: `backend/app/config.py:53-177`
- Modify: `backend/requirements.txt:1-17`
- Modify: `.env.example:19-21`
- Modify: `docker-compose.yml:4-18`
- Test: `backend/tests/test_prompt_library_models.py`
- Test: `backend/tests/test_config_paths.py`

- [ ] **Step 1: Write failing model and configuration tests**

Create `backend/tests/test_prompt_library_models.py` with tests that exercise the actual persisted invariants:

```python
import pytest
from pydantic import ValidationError

from app.core.prompt_library_models import (
    PromptCategory,
    PromptEntry,
    PromptEntryRef,
    PromptFragment,
)


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
```

Append this exact path assertion to `backend/tests/test_config_paths.py`:

```python
def test_prompt_library_dir_is_project_root_relative(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_LIBRARY_DIR", "prompt_library-test")
    settings = Settings()
    assert Path(settings.prompt_library_dir).is_absolute()
    assert Path(settings.prompt_library_dir).name == "prompt_library-test"
```

- [ ] **Step 2: Run the focused tests and confirm the failure**

Run:

```powershell
python -m pytest backend/tests/test_prompt_library_models.py backend/tests/test_config_paths.py -q
```

Expected: collection fails because `app.core.prompt_library_models` does not exist, and the new setting assertion fails.

- [ ] **Step 3: Add strict persisted models and API DTOs**

Implement the models with `ConfigDict(extra="forbid")`, `Field(default_factory=list)`, a slug pattern of `^[a-z0-9]+(?:-[a-z0-9]+)*$`, `schema_version=1`, non-empty Chinese metadata, non-empty English output, revisions starting at 1, duplicate-entry validation, and the fragment validator shown below:

```python
@model_validator(mode="after")
def validate_kind(self) -> "PromptFragment":
    if self.kind == "entry" and self.ref is None:
        raise ValueError("entry fragment requires ref")
    if self.kind == "literal" and self.ref is not None:
        raise ValueError("literal fragment cannot have ref")
    if self.kind == "literal" and self.source_revision is not None:
        raise ValueError("literal fragment cannot have source_revision")
    if not self.snapshot.strip():
        raise ValueError("fragment snapshot cannot be empty")
    return self
```

Persisted classes in `prompt_library_models.py` must be exactly:

```text
PromptLibraryManifest
PromptEntry
PromptCategory
PromptEntryRef
PromptFragment
PromptCombination
```

API classes in `schemas/prompt_library.py` must be exactly:

```text
PromptWarning
PromptLibraryDiagnostic
CategorySummary
CombinationSummary
CatalogResponse
SearchHit
SearchResponse
CategoryWriteRequest
EntryWriteRequest
CombinationWriteRequest
CombinationSaveIntent
ArchiveRequest
ComposeRequest
ComposeResponse
VersionedCategory
VersionedCombination
WriteResponse
```

Use these exact concurrency and mutation fields:

```python
class ConcurrencyToken(BaseModel):
    expected_revision: int = Field(ge=0)
    expected_etag: str | None = None


class CategoryWriteRequest(ConcurrencyToken):
    name_zh: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int = Field(default=10, ge=0)


class EntryWriteRequest(CategoryWriteRequest):
    prompt: str = Field(min_length=1)


class CombinationWriteRequest(CategoryWriteRequest):
    legacy_template: bool = False
    positive: list[PromptFragment] = Field(default_factory=list)
    negative: list[PromptFragment] = Field(default_factory=list)


class CombinationSaveIntent(CombinationWriteRequest):
    id: Slug


class ArchiveRequest(ConcurrencyToken):
    resource_type: ResourceType
    resource_id: Slug
    polarity: Polarity | None = None
    category_id: Slug | None = None
```

Create `PromptLibraryError` and named constructors for `not_found`, `invalid_locator`, `revision_conflict`, `external_change`, `invalid_document`, and `lock_timeout`. Each instance must expose `status_code` and:

```python
def as_dict(self) -> dict[str, object]:
    return {
        "code": self.code,
        "message": self.message,
        "hint": self.hint,
        "details": self.details,
    }
```

- [ ] **Step 4: Wire configuration, dependency, and Docker mount**

Add to `Settings` and its normalizer:

```python
prompt_library_dir: str = _project_root_path("prompt_library")
prompt_library_lock_timeout: float = 5.0

self.prompt_library_dir = _resolve_project_path(self.prompt_library_dir)
```

Add `filelock>=3.29.7,<4.0.0` to `backend/requirements.txt`, add `PROMPT_LIBRARY_DIR=./prompt_library` under the output paths in `.env.example`, and add this exact compose configuration:

```yaml
    volumes:
      - ./outputs:/app/outputs
      - ./lora_train:/app/lora_train
      - ./backend/workflows:/app/workflows
      - ./prompt_library:/app/prompt_library
    environment:
      - DATABASE_URL=sqlite:///./auto_draw.db
      - PROMPT_LIBRARY_DIR=/app/prompt_library
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m pytest backend/tests/test_prompt_library_models.py backend/tests/test_config_paths.py -q
```

Expected: all selected tests pass.

Commit:

```powershell
git add backend/app/core/prompt_library_models.py backend/app/core/prompt_library_errors.py backend/app/schemas/prompt_library.py backend/app/config.py backend/requirements.txt .env.example docker-compose.yml backend/tests/test_prompt_library_models.py backend/tests/test_config_paths.py
git commit -m "feat: define prompt library contracts"
```

### Task 2: Safe JSON store, cache-aware reads, and isolated diagnostics

**Files:**

- Create: `backend/app/core/prompt_library_store.py`
- Create: `backend/app/core/prompt_library.py`
- Test: `backend/tests/test_prompt_library_provider.py`

- [ ] **Step 1: Write failing provider tests**

Create fixtures under each test's `tmp_path`; do not read the repository seed in unit tests. Cover valid loading, malformed-neighbor isolation, id/filename mismatch, polarity mismatch, etag changes, and path traversal:

```python
def test_catalog_keeps_valid_files_and_reports_bad_neighbor(library_root: Path) -> None:
    write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    (library_root / "positive" / "broken.json").write_text("{not-json", encoding="utf-8")
    provider = FilePromptLibraryProvider(library_root)

    catalog = provider.catalog()

    assert [item.id for item in catalog.categories] == ["clothing"]
    assert catalog.diagnostics[0].code == "invalid_json"
    assert catalog.diagnostics[0].path == "positive/broken.json"


def test_external_byte_change_updates_etag_without_trusting_mtime(library_root: Path) -> None:
    path = write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    provider = FilePromptLibraryProvider(library_root)
    first = provider.get_category("positive", "clothing")
    stat = path.stat()
    path.write_text(path.read_text(encoding="utf-8").replace("dress", "gown"), encoding="utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    second = provider.get_category("positive", "clothing")

    assert second.etag != first.etag


@pytest.mark.parametrize("category_id", ["../secret", "a/b", "A"])
def test_get_category_rejects_unsafe_locator(library_root: Path, category_id: str) -> None:
    provider = FilePromptLibraryProvider(library_root)
    with pytest.raises(PromptLibraryError) as caught:
        provider.get_category("positive", category_id)
    assert caught.value.code == "invalid_locator"
```

- [ ] **Step 2: Run the provider tests and confirm failure**

Run:

```powershell
python -m pytest backend/tests/test_prompt_library_provider.py -q
```

Expected: collection fails because the provider/store modules do not exist.

- [ ] **Step 3: Implement path confinement, etags, reads, and atomic replacement**

`PromptLibraryStore` must expose these concrete operations:

```python
class PromptLibraryStore:
    def __init__(self, root: Path, lock_timeout: float = 5.0) -> None
    def category_path(self, polarity: Polarity, category_id: str) -> Path
    def combination_path(self, combination_id: str) -> Path
    def read_manifest(self) -> PromptLibraryManifest
    def read_category(self, polarity: Polarity, category_id: str) -> StoredDocument[PromptCategory]
    def read_combination(self, combination_id: str) -> StoredDocument[PromptCombination]
    def scan_categories(self) -> tuple[list[StoredDocument[PromptCategory]], list[PromptLibraryDiagnostic]]
    def scan_combinations(self) -> tuple[list[StoredDocument[PromptCombination]], list[PromptLibraryDiagnostic]]
    def locked(self) -> ContextManager[None]
    def replace_json(self, path: Path, model: BaseModel) -> str
```

Use raw bytes for the etag:

```python
def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
```

Constrain paths before access:

```python
def _confined(self, parent: Path, resource_id: str) -> Path:
    if re.fullmatch(SLUG_PATTERN, resource_id) is None:
        raise PromptLibraryError.invalid_locator(resource_id)
    candidate = (parent / f"{resource_id}.json").resolve()
    try:
        candidate.relative_to(parent.resolve())
    except ValueError as exc:
        raise PromptLibraryError.invalid_locator(resource_id) from exc
    return candidate
```

`replace_json` must serialize with `ensure_ascii=False`, `indent=2`, a final newline, validate the just-serialized bytes through the expected Pydantic model before replacing, write a named temporary file in `path.parent`, flush, `os.fsync`, close, `os.replace`, and remove an un-replaced temporary file in `finally`. Acquire `FileLock(root / ".lock", timeout=lock_timeout)` in `locked()` and translate `filelock.Timeout` to `lock_timeout`.

- [ ] **Step 4: Implement the long-lived read provider**

Define `PromptLibraryProvider` as a Protocol and `FilePromptLibraryProvider` as its implementation. Protect the document cache with `threading.RLock`; use `(mtime_ns, size, sha256)` to invalidate cached models, and always hash when `(mtime_ns, size)` is unchanged so same-stat manual edits are detected. `catalog()` must return valid resources and diagnostics instead of raising for a malformed neighbor.

Create one cached default provider:

```python
@lru_cache(maxsize=8)
def _provider_for(root: str, lock_timeout: float) -> FilePromptLibraryProvider:
    return FilePromptLibraryProvider(Path(root), lock_timeout=lock_timeout)


def get_default_prompt_library_provider() -> FilePromptLibraryProvider:
    settings = get_settings()
    return _provider_for(settings.prompt_library_dir, settings.prompt_library_lock_timeout)
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m pytest backend/tests/test_prompt_library_provider.py -q
```

Expected: all provider tests pass and the malformed file is reported without hiding the valid category.

Commit:

```powershell
git add backend/app/core/prompt_library_store.py backend/app/core/prompt_library.py backend/tests/test_prompt_library_provider.py
git commit -m "feat: add file-backed prompt library provider"
```

### Task 3: Prompt composition and weighted fuzzy search

**Files:**

- Create: `backend/app/core/prompt_composer.py`
- Create: `backend/app/core/prompt_search.py`
- Modify: `backend/app/core/prompt_library.py`
- Test: `backend/tests/test_prompt_composer.py`
- Test: `backend/tests/test_prompt_search.py`

- [ ] **Step 1: Write failing composer tests**

Cover stable order, duplicate-reference handling, literals, weights, current-reference correction, archived/missing snapshot fallback, and both polarities:

```python
def test_compose_resolves_current_prompt_and_formats_weight(provider) -> None:
    request = ComposeRequest(
        positive=[
            fragment("clothing", "dress", snapshot="typo", source_revision=1, order=20, weight=1.2),
            PromptFragment(kind="literal", snapshot="1girl", order=10),
        ],
        negative=[negative_fragment("quality", "low-quality", snapshot="low quality")],
    )

    result = provider.compose(request)

    assert result.positive_prompt == "1girl, (dress:1.2)"
    assert result.negative_prompt == "low quality"
    assert result.positive[1].snapshot == "dress"
    assert result.snapshot_repaired is True


def test_first_duplicate_reference_wins_but_literals_are_kept(provider) -> None:
    ref = fragment("clothing", "dress", snapshot="dress")
    result = provider.compose(ComposeRequest(positive=[ref, ref.model_copy(), literal("soft light"), literal("soft light")]))
    assert result.positive_prompt == "dress, soft light, soft light"
    assert [warning.code for warning in result.warnings] == ["duplicate_reference"]


def test_missing_reference_uses_snapshot_with_warning(provider) -> None:
    missing = fragment("clothing", "missing", snapshot="blue coat")
    result = provider.compose(ComposeRequest(positive=[missing]))
    assert result.positive_prompt == "blue coat"
    assert result.warnings[0].code == "missing_reference"


def test_compose_imports_saved_combination_then_appends_literals(provider) -> None:
    result = provider.compose(
        ComposeRequest(
            combination_id="portrait-dress",
            positive=[PromptFragment(kind="literal", snapshot="soft lighting", order=30)],
        )
    )
    assert result.positive_prompt == "1girl, dress, soft lighting"
```

- [ ] **Step 2: Write failing fuzzy-search tests**

```python
def test_search_matches_chinese_description_and_english_alias(provider) -> None:
    zh = provider.search("裙裝", polarity="positive")
    en = provider.search("one piece", polarity="positive")
    assert zh.results[0].id == "dress"
    assert "description_zh" in zh.results[0].matched_fields
    assert en.results[0].id == "dress"
    assert "aliases" in en.results[0].matched_fields


def test_search_is_deterministic_and_excludes_archived(provider) -> None:
    first = provider.search("dress", limit=50)
    second = provider.search("dress", limit=50)
    assert [(hit.resource_type, hit.id, hit.score) for hit in first.results] == [
        (hit.resource_type, hit.id, hit.score) for hit in second.results
    ]
    assert all(not hit.archived for hit in first.results)


def test_description_fuzzy_match_scores_below_exact_prompt(provider) -> None:
    result = provider.search("dress")
    exact = next(hit for hit in result.results if hit.id == "dress")
    description_only = next(hit for hit in result.results if hit.id == "wardrobe-guide")
    assert exact.score > description_only.score >= 45
```

- [ ] **Step 3: Run both files and confirm failure**

Run:

```powershell
python -m pytest backend/tests/test_prompt_composer.py backend/tests/test_prompt_search.py -q
```

Expected: collection fails because the composer/search modules do not exist.

- [ ] **Step 4: Implement composition exactly once on the backend**

If `combination_id` is present, load its lazily repaired positive/negative fragments before appending request fragments. Sort `(order, original_index)`. Keep the first occurrence of each entry ref and emit `duplicate_reference` for later occurrences; never deduplicate literals. A ref is active only when both its category and entry are active. Resolve active refs to the latest prompt and revision. Archived-category, archived-entry, or missing refs keep their stored snapshot and emit `archived_reference` or `missing_reference`. Render fragments with:

```python
def render_fragment(text: str, weight: float) -> str:
    clean = text.strip().strip(",").strip()
    if not clean:
        return ""
    if math.isclose(weight, 1.0):
        return clean
    rendered_weight = f"{weight:.3f}".rstrip("0").rstrip(".")
    return f"({clean}:{rendered_weight})"
```

Join non-empty output with `", "`. Return repaired fragments, structured warnings, and `snapshot_repaired=True` when an active ref changes either snapshot or `source_revision`.

- [ ] **Step 5: Implement the specified fuzzy ranking**

Normalize with NFKC, `casefold()`, punctuation-to-space conversion, and collapsed whitespace. Preserve CJK characters. Field weights are:

```python
FIELD_WEIGHTS = {
    "name_zh": 1.0,
    "prompt": 1.0,
    "aliases": 1.0,
    "positive_prompt_snapshot": 0.9,
    "negative_prompt_snapshot": 0.9,
    "keywords": 0.9,
    "description_zh": 0.75,
    "category_context": 0.6,
}
```

Base similarity is exact `100`, token/prefix `90`, substring `80`, otherwise `min(79, round(SequenceMatcher(None, query, value).ratio() * 79))`. A field contributes only if its weighted score is at least the request threshold (default `45`). Sort by descending score, then polarity, category order, resource order, `name_zh`, and id. Default limit is `50`; maximum is `200`.

Run:

```powershell
python -m pytest backend/tests/test_prompt_composer.py backend/tests/test_prompt_search.py -q
```

Expected: all selected tests pass.

Commit:

```powershell
git add backend/app/core/prompt_composer.py backend/app/core/prompt_search.py backend/app/core/prompt_library.py backend/tests/test_prompt_composer.py backend/tests/test_prompt_search.py
git commit -m "feat: compose and search prompt resources"
```

### Task 4: Optimistic writes, archive, eager propagation, and lazy repair

**Files:**

- Create: `backend/app/core/prompt_library_writes.py`
- Modify: `backend/app/core/prompt_library.py`
- Test: `backend/tests/test_prompt_library_writes.py`

- [ ] **Step 1: Write failing concurrency and propagation tests**

```python
def test_existing_write_requires_matching_revision_and_etag(provider) -> None:
    current = provider.get_category("positive", "clothing")
    with pytest.raises(PromptLibraryError) as revision:
        provider.save_entry("positive", "clothing", "dress", entry_write(expected_revision=999, expected_etag=current.etag))
    assert revision.value.code == "revision_conflict"

    manually_edit_without_revision(provider.root / "positive" / "clothing.json")
    with pytest.raises(PromptLibraryError) as external:
        provider.save_entry("positive", "clothing", "dress", entry_write(expected_revision=current.category.revision, expected_etag=current.etag))
    assert external.value.code == "external_change"


def test_entry_correction_repairs_referencing_combinations(provider) -> None:
    category = provider.get_category("positive", "clothing")
    saved = provider.save_entry(
        "positive",
        "clothing",
        "dress",
        entry_write(prompt="evening dress", expected_revision=category.category.revision, expected_etag=category.etag),
    )
    combination = provider.get_combination("portrait-dress")
    referenced = next(item for item in combination.combination.positive if item.ref)
    assert referenced.snapshot == "evening dress"
    assert referenced.source_revision == saved.entry_revision
    assert combination.combination.positive_prompt_snapshot == "1girl, evening dress"
    assert saved.affected_combinations == ["portrait-dress"]


def test_lazy_read_repairs_partial_eager_update(provider) -> None:
    simulate_category_written_before_combination(provider.root)
    before = raw_combination_revision(provider.root, "portrait-dress")
    loaded = provider.get_combination("portrait-dress")
    assert loaded.repaired is True
    assert loaded.combination.revision == before + 1
    assert loaded.combination.positive_prompt_snapshot == "1girl, corrected dress"
```

Also test create requires revision `0` and no etag, metadata-only category updates preserve entries, entry operations use parent tokens, archive sets `archived=true`, and stale lock timeout maps to `lock_timeout`.

- [ ] **Step 2: Run the write tests and confirm failure**

Run:

```powershell
python -m pytest backend/tests/test_prompt_library_writes.py -q
```

Expected: tests fail because write coordinator methods are absent.

- [ ] **Step 3: Implement precondition checks under the file lock**

After acquiring `.lock`, re-read raw bytes, revision, and etag. Enforce:

```python
def assert_precondition(*, exists: bool, actual_revision: int | None, actual_etag: str | None,
                        expected_revision: int, expected_etag: str | None) -> None:
    if not exists:
        if expected_revision != 0 or expected_etag is not None:
            raise PromptLibraryError.revision_conflict(expected_revision, None)
        return
    if expected_revision != actual_revision:
        raise PromptLibraryError.revision_conflict(expected_revision, actual_revision)
    if expected_etag is None or expected_etag != actual_etag:
        raise PromptLibraryError.external_change(expected_etag, actual_etag)
```

Category create writes revision 1 and empty entries. Category update increments the category revision and preserves existing entries. Entry create writes revision 1; entry update increments only that entry revision; either operation also increments the parent category revision. Combination create writes revision 1; update increments its revision. Archive increments the owning file revision.

- [ ] **Step 4: Implement snapshot propagation and lazy repair**

When any entry update increments its revision, first atomically replace the category, then scan combinations while the same file lock is held. For every active matching ref, replace `snapshot` with the current prompt and `source_revision` with the new entry revision, recompose both snapshots, increment the combination revision once, and atomically replace that combination. Return affected combination ids sorted lexically.

`get_combination()` must compare all active refs with current entries. If stale, reacquire the lock, re-read, repair, increment revision once, replace, and return the new etag with `repaired=True`. A missing external file keeps the snapshot and warning; it does not block the read.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m pytest backend/tests/test_prompt_library_writes.py backend/tests/test_prompt_composer.py -q
```

Expected: all selected tests pass.

Commit:

```powershell
git add backend/app/core/prompt_library_writes.py backend/app/core/prompt_library.py backend/tests/test_prompt_library_writes.py
git commit -m "feat: add versioned prompt library writes"
```

### Task 5: FastAPI Prompt Library surface

**Files:**

- Create: `backend/app/api/prompt_library.py`
- Modify: `backend/app/main.py:65-90`
- Test: `backend/tests/test_prompt_library_api.py`

- [ ] **Step 1: Write endpoint contract tests with a temporary provider override**

Use `app.dependency_overrides[prompt_library_api._provider]` so tests never mutate the repository library. Cover every route and error envelope:

```python
def test_catalog_search_and_detail(client_with_prompt_library) -> None:
    catalog = client_with_prompt_library.get("/api/prompt-library/catalog")
    search = client_with_prompt_library.get("/api/prompt-library/search", params={"q": "裙裝", "polarity": "positive"})
    detail = client_with_prompt_library.get("/api/prompt-library/categories/positive/clothing")
    assert catalog.status_code == search.status_code == detail.status_code == 200
    assert catalog.json()["categories"][0]["etag"]
    assert search.json()["results"][0]["matched_fields"]
    assert detail.json()["category"]["entries"][0]["prompt"] == "dress"


def test_entry_write_conflict_is_actionable(client_with_prompt_library) -> None:
    response = client_with_prompt_library.put(
        "/api/prompt-library/categories/positive/clothing/entries/dress",
        json=entry_body(expected_revision=999, expected_etag="stale"),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "revision_conflict"
    assert response.json()["detail"]["message"]
    assert response.json()["detail"]["hint"]


def test_compose_can_optionally_save_combination(client_with_prompt_library) -> None:
    response = client_with_prompt_library.post(
        "/api/prompt-library/compose",
        json={
            "positive": [entry_fragment_body("positive", "clothing", "dress")],
            "negative": [],
            "save_as": {
                "id": "my-dress",
                "name_zh": "我的洋裝",
                "description_zh": "常用洋裝提示詞",
                "aliases": [],
                "keywords": [],
                "expected_revision": 0,
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["positive_prompt"] == "dress"
    assert response.json()["saved_combination"]["combination"]["id"] == "my-dress"
```

- [ ] **Step 2: Run API tests and confirm failure**

Run:

```powershell
python -m pytest backend/tests/test_prompt_library_api.py -q
```

Expected: tests fail with 404 because the router is not registered.

- [ ] **Step 3: Implement the exact route table**

Register prefix `/api/prompt-library` and these routes:

```text
GET  /catalog
GET  /categories/{polarity}/{category_id}
GET  /search
PUT  /categories/{polarity}/{category_id}
PUT  /categories/{polarity}/{category_id}/entries/{entry_id}
POST /archive
POST /compose
GET  /combinations
GET  /combinations/{combination_id}
PUT  /combinations/{combination_id}
```

The dependency is:

```python
def _provider() -> PromptLibraryProvider:
    return get_default_prompt_library_provider()
```

Catch `PromptLibraryError` once in a small `_call()` helper and raise `HTTPException(status_code=error.status_code, detail=error.as_dict())`. Let Pydantic request validation use FastAPI's normal 422 response. Search query parameters are `q`, `polarity`, `resource_types: list[ResourceType] = Query(default=[])`, `category_id`, `threshold=45`, `limit=50`, and `include_archived=false`.

- [ ] **Step 4: Register the router and verify OpenAPI**

Import `prompt_library` in `backend/app/main.py`, call `app.include_router(prompt_library.router)`, and add an API test asserting all ten paths appear in `app.openapi()["paths"]`.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m pytest backend/tests/test_prompt_library_api.py backend/tests/test_main.py -q
```

Expected: all selected tests pass.

Commit:

```powershell
git add backend/app/api/prompt_library.py backend/app/main.py backend/tests/test_prompt_library_api.py
git commit -m "feat: expose prompt library API"
```

### Task 6: Curated bilingual starter catalog and legacy combination data

**Files:**

- Create: `prompt_library/manifest.json`
- Create: `prompt_library/positive/subjects.json`
- Create: `prompt_library/positive/appearance.json`
- Create: `prompt_library/positive/expressions.json`
- Create: `prompt_library/positive/clothing.json`
- Create: `prompt_library/positive/accessories.json`
- Create: `prompt_library/positive/actions.json`
- Create: `prompt_library/positive/poses.json`
- Create: `prompt_library/positive/camera-angles.json`
- Create: `prompt_library/positive/composition.json`
- Create: `prompt_library/positive/lighting.json`
- Create: `prompt_library/positive/styles.json`
- Create: `prompt_library/positive/environment.json`
- Create: `prompt_library/positive/quality-details.json`
- Create: `prompt_library/positive/colors-textures.json`
- Create: `prompt_library/negative/quality.json`
- Create: `prompt_library/negative/anatomy.json`
- Create: `prompt_library/negative/face-hands.json`
- Create: `prompt_library/negative/composition.json`
- Create: `prompt_library/negative/clothing-colors.json`
- Create: `prompt_library/negative/artifacts.json`
- Create: `prompt_library/negative/text-watermark.json`
- Create: `prompt_library/negative/duplicates.json`
- Create: `prompt_library/combinations/portrait.json`
- Create: `prompt_library/combinations/portrait-detail.json`
- Create: `prompt_library/combinations/character.json`
- Test: `backend/tests/test_prompt_library_seed.py`

- [ ] **Step 1: Write the repository-data quality gate**

`backend/tests/test_prompt_library_seed.py` must load the default project folder through `FilePromptLibraryProvider` and assert:

```python
import re


EXPECTED_POSITIVE = {
    "subjects": 15,
    "appearance": 18,
    "expressions": 15,
    "clothing": 22,
    "accessories": 34,
    "actions": 18,
    "poses": 32,
    "camera-angles": 32,
    "composition": 15,
    "lighting": 18,
    "styles": 18,
    "environment": 24,
    "quality-details": 16,
    "colors-textures": 18,
}
EXPECTED_NEGATIVE = {
    "quality": 14,
    "anatomy": 14,
    "face-hands": 16,
    "composition": 14,
    "clothing-colors": 10,
    "artifacts": 10,
    "text-watermark": 10,
    "duplicates": 10,
}


def test_seed_catalog_is_complete_bilingual_and_clean() -> None:
    provider = FilePromptLibraryProvider(PROJECT_ROOT / "prompt_library")
    catalog = provider.catalog()
    assert catalog.diagnostics == []
    counts = {(item.polarity, item.id): item.entry_count for item in catalog.categories}
    assert {key: counts[("positive", key)] for key in EXPECTED_POSITIVE} == EXPECTED_POSITIVE
    assert {key: counts[("negative", key)] for key in EXPECTED_NEGATIVE} == EXPECTED_NEGATIVE
    assert 300 <= sum(counts.values()) <= 450

    ids: set[tuple[str, str, str]] = set()
    for summary in catalog.categories:
        loaded = provider.get_category(summary.polarity, summary.id).category
        assert loaded.revision == 1
        assert loaded.name_zh.strip() and loaded.description_zh.strip()
        for item in loaded.entries:
            key = (loaded.polarity, loaded.id, item.id)
            assert key not in ids
            ids.add(key)
            assert item.name_zh.strip() and item.description_zh.strip()
            assert item.prompt.strip()
            assert re.search(r"[\u3400-\u9fff]", item.prompt) is None
            assert item.aliases and item.keywords
            assert item.revision == 1 and item.archived is False
```

- [ ] **Step 2: Run the seed test and confirm failure**

Run:

```powershell
python -m pytest backend/tests/test_prompt_library_seed.py -q
```

Expected: fails because `prompt_library/manifest.json` and category files are absent.

- [ ] **Step 3: Author the exact manifest and category shape**

Use this manifest:

```json
{
  "schema_version": 1,
  "library_id": "default",
  "name": "AI Drawing Prompt Library",
  "description_zh": "AI Drawing 專案共用的中英雙語提示詞庫"
}
```

Each category file must use the approved schema, revision 1, stable `order` increments of 10, and the exact entry count listed above. Every entry needs a distinct kebab-case id, Chinese name, Chinese explanation, English `prompt`, at least one alias, at least one search keyword, revision 1, and `archived=false`. Prefer atomic prompt fragments such as `dress`, `front view`, or `soft lighting`; do not place workflow, checkpoint, LoRA, seed, or sampler settings in the catalog.

- [ ] **Step 4: Add the three legacy combinations as literal fragments**

Store `legacy_template=true` and preserve these exact legacy strings:

```text
portrait        -> 1girl, {人物}, {風格}, solo
portrait-detail -> 1girl, {人物}, {風格}, solo, {細節}
character       -> {trigger} {人物}, {風格}
```

Each combination has one positive literal fragment, no negative fragment, matching prompt snapshots, order values `10`, `20`, and `30`, revision 1, and bilingual metadata. These are the only initial combinations flagged as legacy.

- [ ] **Step 5: Review content, run the gate, and commit**

Review every category for duplicate IDs, duplicate English output, mistranslation, overly broad fragments, and misplaced polarity. Then run:

```powershell
python -m pytest backend/tests/test_prompt_library_seed.py -q
```

Expected: the seed gate passes with exactly 393 active entries, 22 category files, no diagnostics, and three legacy combinations.

Commit:

```powershell
git add prompt_library backend/tests/test_prompt_library_seed.py
git commit -m "feat: seed bilingual prompt library"
```

### Task 7: Legacy `/api/prompt-templates` adapter

**Files:**

- Modify: `backend/app/core/prompt_templates.py:11-90`
- Modify: `backend/app/api/prompt_templates.py:23-55`
- Modify: `backend/tests/test_prompt_templates.py:42-93`

- [ ] **Step 1: Rewrite legacy tests to demand the file-backed source**

Keep the existing variable extraction/application tests. Replace provider assertions with:

```python
def test_legacy_provider_lists_only_flagged_combinations(tmp_prompt_library) -> None:
    provider = DefaultPromptTemplateProvider(prompt_library=tmp_prompt_library)
    ids = [item.id for item in provider.list_all()]
    assert ids == ["character", "portrait", "portrait-detail"]
    assert "ordinary-combination" not in ids


def test_legacy_provider_reflects_external_combination_correction(tmp_prompt_library) -> None:
    provider = DefaultPromptTemplateProvider(prompt_library=tmp_prompt_library)
    update_literal_snapshot(tmp_prompt_library.root, "portrait", "1person, {人物}, {風格}, solo")
    assert provider.get("portrait").template == "1person, {人物}, {風格}, solo"
```

Retain API tests for list, apply, and unknown id.

- [ ] **Step 2: Run the legacy test and confirm the hard-coded provider fails**

Run:

```powershell
python -m pytest backend/tests/test_prompt_templates.py -q
```

Expected: the external-correction and ordinary-combination filtering tests fail against the hard-coded rows.

- [ ] **Step 3: Replace only the storage source**

Keep `PromptTemplate`, `PromptTemplateProvider`, `extract_variables`, and `apply_variables`. Implement `DefaultPromptTemplateProvider` with an injected `PromptLibraryProvider` defaulting to `get_default_prompt_library_provider()`. Map only `legacy_template=true` combinations:

```python
def _to_template(combination: PromptCombination) -> PromptTemplate:
    text = combination.positive_prompt_snapshot
    return PromptTemplate(
        id=combination.id,
        name=combination.name_zh,
        template=text,
        variables=extract_variables(text),
    )
```

Sort by id for stable legacy output. Do not retain a hard-coded fallback list. Update the API dependency so tests can override either adapter or underlying provider without mutating repository JSON.

- [ ] **Step 4: Run compatibility tests**

Run:

```powershell
python -m pytest backend/tests/test_prompt_templates.py backend/tests/test_prompt_library_seed.py -q
```

Expected: both files pass; legacy list/apply behavior is unchanged while data comes from combinations.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/core/prompt_templates.py backend/app/api/prompt_templates.py backend/tests/test_prompt_templates.py
git commit -m "refactor: adapt prompt templates to prompt library"
```

### Task 8: Backend stage regression, documentation, and clean-tree checkpoint

**Files:**

- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Run all Prompt Library tests together**

```powershell
python -m pytest backend/tests/test_prompt_library_models.py backend/tests/test_prompt_library_provider.py backend/tests/test_prompt_library_writes.py backend/tests/test_prompt_composer.py backend/tests/test_prompt_search.py backend/tests/test_prompt_library_api.py backend/tests/test_prompt_library_seed.py backend/tests/test_prompt_templates.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run the backend regression suite**

```powershell
python -m pytest backend/tests/ -x -q
```

Expected: the suite exits 0 with no first failure.

- [ ] **Step 3: Exercise the mounted folder in a container configuration check**

```powershell
docker compose config
```

Expected: output contains `/app/prompt_library` as both a bind-mount target and `PROMPT_LIBRARY_DIR`.

- [ ] **Step 4: Update progress with evidence**

Add a dated `Prompt Library service` entry to `docs/PROGRESS.md` recording: file-backed schema/provider, 393-entry bilingual seed, fuzzy search, positive/negative composition, revision+etag writes, snapshot repair, legacy adapter, API routes, and the exact test commands/results from Steps 1–3. Mark UI, workflow generation, and MCP parity as remaining plan-set stages.

- [ ] **Step 5: Commit the stage checkpoint**

```powershell
git add docs/PROGRESS.md
git commit -m "docs: record prompt library service progress"
git status --short
```

Expected: the commit succeeds and `git status --short` prints no uncommitted files.
