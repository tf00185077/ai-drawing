"""Canonical backend rendering for Prompt Library fragments."""

from __future__ import annotations

import math
from collections.abc import Iterable

from app.core.prompt_library_models import (
    Polarity,
    PromptCategory,
    PromptEntryRef,
    PromptFragment,
)
from app.core.prompt_library_store import PromptLibraryStore
from app.schemas.prompt_library import ComposeRequest, ComposeResponse, PromptWarning


def render_fragment(text: str, weight: float) -> str:
    clean = text.strip().strip(",").strip()
    if not clean:
        return ""
    if math.isclose(weight, 1.0):
        return clean
    rendered_weight = f"{weight:.3f}".rstrip("0").rstrip(".")
    return f"({clean}:{rendered_weight})"


class PromptComposer:
    """Resolve entry references and render both prompt polarities exactly once."""

    def __init__(self, store: PromptLibraryStore) -> None:
        self.store = store

    def compose(self, request: ComposeRequest) -> ComposeResponse:
        positive = list(request.positive)
        negative = list(request.negative)
        if request.combination_id is not None:
            combination = self.store.read_combination(request.combination_id).model
            positive = [*combination.positive, *positive]
            negative = [*combination.negative, *negative]

        category_documents, _ = self.store.scan_categories()
        categories = {
            (document.model.polarity, document.model.id): document.model
            for document in category_documents
        }
        repaired = False
        warnings: list[PromptWarning] = []
        resolved_positive, positive_repaired = self._resolve(
            "positive", positive, categories, warnings
        )
        resolved_negative, negative_repaired = self._resolve(
            "negative", negative, categories, warnings
        )
        repaired = positive_repaired or negative_repaired

        return ComposeResponse(
            positive_prompt=self._render(resolved_positive),
            negative_prompt=self._render(resolved_negative),
            positive=resolved_positive,
            negative=resolved_negative,
            warnings=warnings,
            snapshot_repaired=repaired,
            saved_combination=None,
        )

    def _resolve(
        self,
        polarity: Polarity,
        fragments: Iterable[PromptFragment],
        categories: dict[tuple[Polarity, str], PromptCategory],
        warnings: list[PromptWarning],
    ) -> tuple[list[PromptFragment], bool]:
        ordered = sorted(
            enumerate(fragments), key=lambda item: (item[1].order, item[0])
        )
        resolved: list[PromptFragment] = []
        seen: set[tuple[Polarity, str, str]] = set()
        repaired = False

        for _, fragment in ordered:
            if fragment.kind == "literal":
                resolved.append(fragment)
                continue

            ref = fragment.ref
            assert ref is not None
            ref_key = (ref.polarity, ref.category_id, ref.entry_id)
            if ref_key in seen:
                warnings.append(self._duplicate_warning(ref))
                continue
            seen.add(ref_key)

            category = categories.get((polarity, ref.category_id))
            entry = None
            if category is not None:
                entry = next(
                    (
                        candidate
                        for candidate in category.entries
                        if candidate.id == ref.entry_id
                    ),
                    None,
                )
            if category is None or entry is None or ref.polarity != polarity:
                warnings.append(self._missing_warning(ref))
                resolved.append(fragment)
                continue
            if category.archived or entry.archived:
                warnings.append(
                    self._archived_warning(
                        ref,
                        category_archived=category.archived,
                        entry_archived=entry.archived,
                    )
                )
                resolved.append(fragment)
                continue

            if (
                fragment.snapshot != entry.prompt
                or fragment.source_revision != entry.revision
            ):
                fragment = fragment.model_copy(
                    update={
                        "snapshot": entry.prompt,
                        "source_revision": entry.revision,
                    }
                )
                repaired = True
            resolved.append(fragment)
        return resolved, repaired

    @staticmethod
    def _render(fragments: Iterable[PromptFragment]) -> str:
        rendered = [
            text
            for fragment in fragments
            if (text := render_fragment(fragment.snapshot, fragment.weight))
        ]
        return ", ".join(rendered)

    @staticmethod
    def _duplicate_warning(ref: PromptEntryRef) -> PromptWarning:
        return PromptWarning(
            code="duplicate_reference",
            message="A later fragment references an entry already used in this polarity.",
            hint=(
                "Keep the first fragment or change its order and weight instead of "
                "repeating the ref."
            ),
            ref=ref,
            details={"resolution": "first_reference_kept"},
        )

    @staticmethod
    def _missing_warning(ref: PromptEntryRef) -> PromptWarning:
        return PromptWarning(
            code="missing_reference",
            message="The referenced Prompt Library entry is unavailable.",
            hint="The stored snapshot was kept; restore the entry or replace this fragment.",
            ref=ref,
            details={"resolution": "snapshot_kept"},
        )

    @staticmethod
    def _archived_warning(
        ref: PromptEntryRef, *, category_archived: bool, entry_archived: bool
    ) -> PromptWarning:
        return PromptWarning(
            code="archived_reference",
            message="The referenced category or entry is archived.",
            hint="The stored snapshot was kept; unarchive the resource or replace this fragment.",
            ref=ref,
            details={
                "category_archived": category_archived,
                "entry_archived": entry_archived,
                "resolution": "snapshot_kept",
            },
        )
