"""Deterministic weighted fuzzy search for Prompt Library resources."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.core.prompt_library_models import (
    Polarity,
    PromptCategory,
    PromptCombination,
    ResourceType,
)
from app.core.prompt_library_store import PromptLibraryStore
from app.schemas.prompt_library import SearchHit, SearchResponse


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


def normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    separated = "".join(
        " " if char.isspace() or unicodedata.category(char).startswith("P") else char
        for char in normalized
    )
    return " ".join(separated.split())


def base_similarity(query: str, value: str) -> int:
    if query == value:
        return 100
    value_tokens = value.split()
    if value.startswith(query) or query in value_tokens:
        return 90
    if query in value:
        return 80
    return min(79, round(SequenceMatcher(None, query, value).ratio() * 79))


@dataclass(frozen=True)
class _Candidate:
    hit: SearchHit
    category_order: int
    resource_order: int
    fields: dict[str, list[str]]


class PromptSearchIndex:
    """Build a fresh safe-store view and rank matches deterministically."""

    def __init__(self, store: PromptLibraryStore) -> None:
        self.store = store

    def search(
        self,
        query: str,
        *,
        polarity: Polarity | None = None,
        resource_type: ResourceType | None = None,
        include_archived: bool = False,
        threshold: int = 45,
        limit: int = 50,
    ) -> SearchResponse:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        if not 0 <= threshold <= 100:
            raise ValueError("threshold must be between 0 and 100")
        normalized_query = normalize_search_text(query)
        if not normalized_query:
            return SearchResponse()

        ranked: list[tuple[_Candidate, int, list[str]]] = []
        for candidate in self._candidates(
            polarity=polarity,
            resource_type=resource_type,
            include_archived=include_archived,
        ):
            score, matched_fields = self._score(
                normalized_query, candidate.fields, threshold
            )
            if matched_fields:
                ranked.append((candidate, score, matched_fields))

        ranked.sort(
            key=lambda item: (
                -item[1],
                item[0].hit.polarity or "",
                item[0].category_order,
                item[0].resource_order,
                item[0].hit.name_zh,
                item[0].hit.id,
            )
        )
        return SearchResponse(
            results=[
                candidate.hit.model_copy(
                    update={"score": score, "matched_fields": matched_fields}
                )
                for candidate, score, matched_fields in ranked[:limit]
            ]
        )

    def _candidates(
        self,
        *,
        polarity: Polarity | None,
        resource_type: ResourceType | None,
        include_archived: bool,
    ) -> list[_Candidate]:
        category_documents, _ = self.store.scan_categories()
        combination_documents, _ = self.store.scan_combinations()
        candidates: list[_Candidate] = []
        for document in category_documents:
            category = document.model
            if polarity is not None and category.polarity != polarity:
                continue
            if resource_type in (None, "category") and (
                include_archived or not category.archived
            ):
                candidates.append(self._category_candidate(category))
            if resource_type in (None, "entry"):
                candidates.extend(
                    self._entry_candidates(category, include_archived=include_archived)
                )
        if polarity is None and resource_type in (None, "combination"):
            candidates.extend(
                self._combination_candidate(document.model)
                for document in combination_documents
                if include_archived or not document.model.archived
            )
        return candidates

    @staticmethod
    def _category_candidate(category: PromptCategory) -> _Candidate:
        return _Candidate(
            hit=SearchHit(
                resource_type="category",
                id=category.id,
                polarity=category.polarity,
                category_id=category.id,
                name_zh=category.name_zh,
                description_zh=category.description_zh,
                aliases=category.aliases,
                keywords=category.keywords,
                archived=category.archived,
                score=0,
            ),
            category_order=category.order,
            resource_order=category.order,
            fields={
                "name_zh": [category.name_zh],
                "aliases": category.aliases,
                "keywords": category.keywords,
                "description_zh": [category.description_zh],
            },
        )

    @staticmethod
    def _entry_candidates(
        category: PromptCategory, *, include_archived: bool
    ) -> list[_Candidate]:
        context = [
            category.name_zh,
            category.description_zh,
            *category.aliases,
            *category.keywords,
        ]
        return [
            _Candidate(
                hit=SearchHit(
                    resource_type="entry",
                    id=entry.id,
                    polarity=category.polarity,
                    category_id=category.id,
                    name_zh=entry.name_zh,
                    description_zh=entry.description_zh,
                    prompt=entry.prompt,
                    aliases=entry.aliases,
                    keywords=entry.keywords,
                    archived=category.archived or entry.archived,
                    score=0,
                ),
                category_order=category.order,
                resource_order=entry.order,
                fields={
                    "name_zh": [entry.name_zh],
                    "prompt": [entry.prompt],
                    "aliases": entry.aliases,
                    "keywords": entry.keywords,
                    "description_zh": [entry.description_zh],
                    "category_context": context,
                },
            )
            for entry in category.entries
            if include_archived or not (category.archived or entry.archived)
        ]

    @staticmethod
    def _combination_candidate(combination: PromptCombination) -> _Candidate:
        return _Candidate(
            hit=SearchHit(
                resource_type="combination",
                id=combination.id,
                name_zh=combination.name_zh,
                description_zh=combination.description_zh,
                aliases=combination.aliases,
                keywords=combination.keywords,
                archived=combination.archived,
                score=0,
            ),
            category_order=combination.order,
            resource_order=combination.order,
            fields={
                "name_zh": [combination.name_zh],
                "aliases": combination.aliases,
                "keywords": combination.keywords,
                "description_zh": [combination.description_zh],
                "positive_prompt_snapshot": [combination.positive_prompt_snapshot],
                "negative_prompt_snapshot": [combination.negative_prompt_snapshot],
            },
        )

    @staticmethod
    def _score(
        query: str, fields: dict[str, list[str]], threshold: int
    ) -> tuple[int, list[str]]:
        field_scores: list[tuple[str, int]] = []
        for field_name, weight in FIELD_WEIGHTS.items():
            values = fields.get(field_name, [])
            similarities = [
                base_similarity(query, normalized)
                for value in values
                if (normalized := normalize_search_text(value))
            ]
            if not similarities:
                continue
            weighted = round(max(similarities) * weight)
            if weighted >= threshold:
                field_scores.append((field_name, weighted))
        if not field_scores:
            return 0, []
        return max(score for _, score in field_scores), [
            field_name for field_name, _ in field_scores
        ]
