"""Category tree integrity: demote invalid parent links to root with diagnostics."""

from __future__ import annotations

from app.schemas.prompt_library import CategorySummary, PromptLibraryDiagnostic


def _diagnostic(summary: CategorySummary, reason: str, hint: str) -> PromptLibraryDiagnostic:
    return PromptLibraryDiagnostic(
        code="category_parent_demoted",
        message=f"Category '{summary.id}' parent link was ignored: {reason}.",
        hint=hint,
        path=f"{summary.polarity}/{summary.id}",
        details={
            "category_id": summary.id,
            "polarity": summary.polarity,
            "parent_id": summary.parent_id,
            "reason": reason,
        },
    )


def validate_category_tree(
    summaries: list[CategorySummary],
) -> tuple[list[CategorySummary], list[PromptLibraryDiagnostic]]:
    by_key: dict[tuple[str, str], CategorySummary] = {
        (summary.polarity, summary.id): summary for summary in summaries
    }
    demoted: set[tuple[str, str]] = set()
    diagnostics: list[PromptLibraryDiagnostic] = []

    def parent_of(polarity: str, cid: str) -> str | None:
        summary = by_key.get((polarity, cid))
        if summary is None:
            return None
        if (polarity, cid) in demoted:
            return None
        return summary.parent_id

    for summary in summaries:
        parent_id = summary.parent_id
        if parent_id is None:
            continue
        key = (summary.polarity, summary.id)
        parent_key = (summary.polarity, parent_id)
        if parent_id == summary.id:
            demoted.add(key)
            diagnostics.append(_diagnostic(summary, "points to itself",
                                           "Leave the parent empty or pick another category."))
            continue
        if parent_key not in by_key:
            demoted.add(key)
            diagnostics.append(_diagnostic(summary, "parent not found in this polarity",
                                           "Create the parent, or clear the parent link."))
            continue
        # cycle detection: walk up from parent (respecting already-demoted edges)
        seen: set[tuple[str, str]] = set()
        cursor: str | None = parent_id
        cycles = False
        while cursor is not None:
            cursor_key = (summary.polarity, cursor)
            if cursor == summary.id:
                cycles = True
                break
            if cursor_key in seen:
                break
            seen.add(cursor_key)
            cursor = parent_of(summary.polarity, cursor)
        if cycles:
            demoted.add(key)
            diagnostics.append(_diagnostic(summary, "would form a cycle",
                                           "Pick a parent that is not a descendant of this category."))

    adjusted = [
        summary.model_copy(update={"parent_id": None})
        if (summary.polarity, summary.id) in demoted
        else summary
        for summary in summaries
    ]
    return adjusted, diagnostics
