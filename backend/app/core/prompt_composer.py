"""Canonical backend rendering for Prompt Library fragments."""

from __future__ import annotations

import json
from collections.abc import Iterable

from app.core.prompt_atomic import atomize_nonblank, render_prompt_atom
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_models import (
    Polarity,
    PromptCategory,
    PromptEntryRef,
    PromptFragment,
)
from app.core.prompt_library_store import PromptLibraryStore
from app.schemas.prompt_library import ComposeRequest, ComposeResponse, PromptWarning


def render_fragment(text: str, weight: float) -> str:
    return render_prompt_atom(text, weight)


class PromptComposer:
    """Resolve entry references and render both prompt polarities exactly once."""

    def __init__(self, store: PromptLibraryStore) -> None:
        self.store = store

    def compose(self, request: ComposeRequest) -> ComposeResponse:
        positive = self._copy_fragments(request.positive)
        negative = self._copy_fragments(request.negative)
        if request.combination_id is not None:
            combination = self.store.read_combination(request.combination_id).model
            positive = [*self._copy_fragments(combination.positive), *positive]
            negative = [*self._copy_fragments(combination.negative), *negative]

        category_documents, _ = self.store.scan_categories()
        categories = {
            (document.model.polarity, document.model.id): document.model
            for document in category_documents
        }
        repaired = False
        warnings: list[PromptWarning] = []
        positive, positive_atomized = self._atomize_compatibility(
            "positive", positive, categories, warnings
        )
        negative, negative_atomized = self._atomize_compatibility(
            "negative", negative, categories, warnings
        )
        resolved_positive, positive_repaired = self._resolve(
            "positive", positive, categories, warnings
        )
        resolved_negative, negative_repaired = self._resolve(
            "negative", negative, categories, warnings
        )
        repaired = (
            positive_atomized
            or negative_atomized
            or positive_repaired
            or negative_repaired
        )
        resolved_positive = self._renumber(resolved_positive)
        resolved_negative = self._renumber(resolved_negative)

        return ComposeResponse(
            positive_prompt=self._render(resolved_positive),
            negative_prompt=self._render(resolved_negative),
            positive=resolved_positive,
            negative=resolved_negative,
            warnings=warnings,
            snapshot_repaired=repaired,
            saved_combination=None,
        )

    def _atomize_compatibility(
        self,
        polarity: Polarity,
        fragments: Iterable[PromptFragment],
        categories: dict[tuple[Polarity, str], PromptCategory],
        warnings: list[PromptWarning],
    ) -> tuple[list[PromptFragment], bool]:
        registry = self._legacy_registry()
        ordered = sorted(
            enumerate(fragments), key=lambda item: (item[1].order, item[0])
        )
        result: list[PromptFragment] = []
        changed = False
        for input_index, (_, fragment) in enumerate(ordered):
            if fragment.kind == "literal" and "," in fragment.snapshot:
                try:
                    atoms = atomize_nonblank(fragment.snapshot)
                except ValueError:
                    positions = [
                        index + 1
                        for index, atom in enumerate(fragment.snapshot.split(","))
                        if not atom.strip()
                    ]
                    raise PromptLibraryError.blank_fragment(
                        polarity=polarity, positions=positions
                    )
                result.extend(
                    fragment.model_copy(
                        deep=True,
                        update={"snapshot": atom, "order": len(result) * 10 + 10},
                    )
                    for atom in atoms
                )
                warnings.append(
                    PromptWarning(
                        code="legacy_literal_atomized",
                        message="A comma-bearing literal was split into atomic prompts.",
                        hint="Review the expanded atoms; the original weight was copied to each.",
                        details={
                            "polarity": polarity,
                            "position": input_index + 1,
                            "count": len(atoms),
                            "weight_policy": "copied_to_each_atom",
                            "resolution": "literal_atoms_created",
                        },
                    )
                )
                changed = True
                continue

            if fragment.kind == "entry" and fragment.ref is not None:
                ref_key = (
                    fragment.ref.polarity,
                    fragment.ref.category_id,
                    fragment.ref.entry_id,
                )
                expansion = registry.get(ref_key)
                if expansion:
                    expanded_keys = [
                        (item.polarity, item.category_id, item.entry_id)
                        for item in expansion
                    ]
                    if len(expanded_keys) != len(set(expanded_keys)):
                        raise PromptLibraryError(
                            code="legacy_reference_duplicate_expansion",
                            message="Reviewed legacy expansion contains duplicate refs.",
                            hint="Correct the reviewed registry; no fragment was composed.",
                            status_code=409,
                            details={"ref": fragment.ref.model_dump(mode="json")},
                        )
                    for locator in expansion:
                        category = categories.get(
                            (locator.polarity, locator.category_id)
                        )
                        entry = next(
                            (
                                candidate
                                for candidate in category.entries
                                if candidate.id == locator.entry_id
                            ),
                            None,
                        ) if category else None
                        if entry is None:
                            raise PromptLibraryError.unresolved_legacy_reference(
                                ref=fragment.ref.model_dump(mode="json")
                            )
                        result.append(
                            PromptFragment(
                                kind="entry",
                                ref=locator,
                                snapshot=entry.prompt,
                                source_revision=entry.revision,
                                weight=fragment.weight,
                                order=len(result) * 10 + 10,
                            )
                        )
                    warnings.append(
                        PromptWarning(
                            code="legacy_reference_expanded",
                            message="A legacy source ref was expanded to reviewed atomic refs.",
                            hint="Review the expanded refs and copied per-atom weight.",
                            ref=fragment.ref,
                            details={
                                "polarity": polarity,
                                "position": input_index + 1,
                                "new_refs": [
                                    item.model_dump(mode="json")
                                    for item in expansion
                                ],
                                "count": len(expansion),
                                "weight_policy": "copied_to_each_atom",
                                "resolution": "reviewed_registry_expansion",
                            },
                        )
                    )
                    changed = True
                    continue
                if "," in fragment.snapshot:
                    raise PromptLibraryError.unresolved_legacy_reference(
                        ref=fragment.ref.model_dump(mode="json")
                    )
            result.append(fragment)
        return result, changed

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
                    deep=True,
                    update={
                        "snapshot": entry.prompt,
                        "source_revision": entry.revision,
                    }
                )
                repaired = True
            resolved.append(fragment)
        return resolved, repaired

    @staticmethod
    def _copy_fragments(
        fragments: Iterable[PromptFragment],
    ) -> list[PromptFragment]:
        return [fragment.model_copy(deep=True) for fragment in fragments]

    @staticmethod
    def _render(fragments: Iterable[PromptFragment]) -> str:
        return ",".join(
            render_fragment(fragment.snapshot, fragment.weight)
            for fragment in fragments
        )

    @staticmethod
    def _renumber(fragments: list[PromptFragment]) -> list[PromptFragment]:
        return [
            fragment.model_copy(update={"order": (index + 1) * 10})
            for index, fragment in enumerate(fragments)
        ]

    def _legacy_registry(
        self,
    ) -> dict[tuple[Polarity, str, str], list[PromptEntryRef]]:
        path = (
            self.store.root
            / "migrations"
            / "comma-atomic-v1"
            / "legacy-ref-registry.json"
        )
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            result: dict[tuple[Polarity, str, str], list[PromptEntryRef]] = {}
            for item in payload.get("expansions", []):
                source = PromptEntryRef.model_validate(item["source"])
                result[
                    (source.polarity, source.category_id, source.entry_id)
                ] = [
                    PromptEntryRef.model_validate(locator)
                    for locator in item["derived"]
                ]
            return result
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise PromptLibraryError.invalid_document(
                "migrations/comma-atomic-v1/legacy-ref-registry.json",
                str(exc),
            ) from exc

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
