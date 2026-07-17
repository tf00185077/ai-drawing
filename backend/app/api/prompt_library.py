"""FastAPI surface for the project-scoped Prompt Library."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.prompt_library import (
    PromptLibraryProvider,
    get_default_prompt_library_provider,
)
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_models import Polarity, ResourceType
from app.schemas.prompt_library import (
    ArchiveRequest,
    CatalogResponse,
    CategoryWriteRequest,
    CombinationSummary,
    CombinationWriteRequest,
    ComposeRequest,
    ComposeResponse,
    EntryWriteRequest,
    SearchResponse,
    VersionedCategory,
    VersionedCombination,
    WriteResponse,
)


router = APIRouter(prefix="/api/prompt-library", tags=["Prompt Library"])
Result = TypeVar("Result")


def _provider() -> PromptLibraryProvider:
    return get_default_prompt_library_provider()


def _call(operation: Callable[..., Result], *args, **kwargs) -> Result:
    try:
        return operation(*args, **kwargs)
    except PromptLibraryError as error:
        raise HTTPException(
            status_code=error.status_code, detail=error.as_dict()
        ) from error


@router.get("/catalog", response_model=CatalogResponse)
def catalog(provider: PromptLibraryProvider = Depends(_provider)) -> CatalogResponse:
    return _call(provider.catalog)


@router.get(
    "/categories/{polarity}/{category_id}", response_model=VersionedCategory
)
def get_category(
    polarity: Polarity,
    category_id: str,
    provider: PromptLibraryProvider = Depends(_provider),
) -> VersionedCategory:
    return _call(provider.get_category, polarity, category_id)


@router.get("/search", response_model=SearchResponse)
def search(
    q: str,
    polarity: Polarity | None = None,
    resource_types: list[ResourceType] = Query(default=[]),
    category_id: str | None = None,
    threshold: int = 45,
    limit: int = 50,
    include_archived: bool = False,
    provider: PromptLibraryProvider = Depends(_provider),
) -> SearchResponse:
    return _call(
        provider.search,
        q,
        polarity=polarity,
        resource_types=resource_types,
        category_id=category_id,
        threshold=threshold,
        limit=limit,
        include_archived=include_archived,
    )


@router.put(
    "/categories/{polarity}/{category_id}", response_model=WriteResponse
)
def save_category(
    polarity: Polarity,
    category_id: str,
    body: CategoryWriteRequest,
    provider: PromptLibraryProvider = Depends(_provider),
) -> WriteResponse:
    return _call(provider.save_category, polarity, category_id, body)


@router.put(
    "/categories/{polarity}/{category_id}/entries/{entry_id}",
    response_model=WriteResponse,
)
def save_entry(
    polarity: Polarity,
    category_id: str,
    entry_id: str,
    body: EntryWriteRequest,
    provider: PromptLibraryProvider = Depends(_provider),
) -> WriteResponse:
    return _call(provider.save_entry, polarity, category_id, entry_id, body)


@router.post("/archive", response_model=WriteResponse)
def archive(
    body: ArchiveRequest,
    provider: PromptLibraryProvider = Depends(_provider),
) -> WriteResponse:
    return _call(provider.archive, body)


@router.post("/compose", response_model=ComposeResponse)
def compose(
    body: ComposeRequest,
    provider: PromptLibraryProvider = Depends(_provider),
) -> ComposeResponse:
    return _call(provider.compose, body)


@router.get("/combinations", response_model=list[CombinationSummary])
def list_combinations(
    provider: PromptLibraryProvider = Depends(_provider),
) -> list[CombinationSummary]:
    return _call(provider.catalog).combinations


@router.get(
    "/combinations/{combination_id}", response_model=VersionedCombination
)
def get_combination(
    combination_id: str,
    provider: PromptLibraryProvider = Depends(_provider),
) -> VersionedCombination:
    return _call(provider.get_combination, combination_id)


@router.put("/combinations/{combination_id}", response_model=WriteResponse)
def save_combination(
    combination_id: str,
    body: CombinationWriteRequest,
    provider: PromptLibraryProvider = Depends(_provider),
) -> WriteResponse:
    return _call(provider.save_combination, combination_id, body)
