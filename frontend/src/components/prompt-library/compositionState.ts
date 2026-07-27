import type { PromptEntry, PromptPolarity } from "../../types/api";

export type EditableWeight = string;

export interface WorkbenchFragment {
  id: string;
  kind: "entry" | "literal";
  displayName: string;
  source?: {
    polarity: PromptPolarity;
    categoryId: string;
    entryId: string;
    revision?: number;
  };
  /** Exact unweighted Backend snapshot. */
  snapshotRaw: string;
  /** Snapshot captured when a genuine entry ref was installed. */
  sourceSnapshotRaw: string;
  weight: EditableWeight;
  /** Derived exact visible atom. Never persisted as a separate field. */
  renderedRaw: string;
  range: { start: number; end: number };
  /** Presentation-only linkage for an unresolved legacy fallback. */
  blockingDiagnosticId?: string;
  /** True only for a genuine source entry added by the current user. */
  userAddedSource?: boolean;
}

export type NewWorkbenchFragment = Omit<
  WorkbenchFragment,
  "range" | "renderedRaw" | "displayName"
> & {
  displayName?: string;
};

export interface CompositionState {
  fragments: WorkbenchFragment[];
  text: string;
  warning: string | null;
}

export interface ApiPromptFragment {
  kind: "entry" | "literal";
  ref?: { polarity: PromptPolarity; category_id: string; entry_id: string };
  snapshot: string;
  source_revision?: number;
  weight: number;
  order: number;
}

export type LiteralLabelIndex = ReadonlyMap<string, readonly PromptEntry[]>;

export interface BlankSegmentLocation {
  polarity: PromptPolarity;
  position: number;
}

export function emptyComposition(): CompositionState {
  return { fragments: [], text: "", warning: null };
}

export function canonicalWeightString(weight: EditableWeight): string {
  const trimmed = weight.trim();
  if (trimmed === "") return "";
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric)) return trimmed;
  return numeric.toFixed(3).replace(/\.?0+$/u, "");
}

function normalizedWeight(weight: EditableWeight): number {
  const canonical = canonicalWeightString(weight);
  return canonical === "" ? 1 : Number(canonical);
}

export function renderFragment(
  fragment: Pick<WorkbenchFragment, "snapshotRaw" | "weight">,
): string {
  const weight = normalizedWeight(fragment.weight);
  if (weight === 1) return fragment.snapshotRaw;
  return `(${fragment.snapshotRaw}:${canonicalWeightString(fragment.weight)})`;
}

function rebuild(
  fragments: WorkbenchFragment[],
  warning: string | null = null,
): CompositionState {
  let cursor = 0;
  const rendered: string[] = [];
  const ranged = fragments.map((fragment) => {
    const renderedRaw = renderFragment(fragment);
    const start = cursor;
    cursor += renderedRaw.length;
    rendered.push(renderedRaw);
    const result = {
      ...fragment,
      renderedRaw,
      range: { start, end: cursor },
    };
    cursor += 1;
    return result;
  });
  return { fragments: ranged, text: rendered.join(","), warning };
}

export function appendFragment(
  state: CompositionState,
  fragment: NewWorkbenchFragment,
): CompositionState {
  const displayName =
    fragment.displayName ??
    (fragment.kind === "entry" ? fragment.source?.entryId : undefined) ??
    "自訂文字";
  return rebuild([
    ...state.fragments,
    {
      ...fragment,
      displayName,
      renderedRaw: "",
      range: { start: 0, end: 0 },
    },
  ]);
}

export function appendLiteralText(
  state: CompositionState,
  snapshotRaw: string,
  idFactory: () => string,
  literalLabel: (snapshotRaw: string) => string = () => "自訂文字",
): CompositionState {
  const rawText =
    state.fragments.length === 0
      ? snapshotRaw
      : `${state.text},${snapshotRaw}`;
  return materializeRawText(state, rawText, idFactory, literalLabel);
}

/**
 * Reconcile the exact textarea value against exact rendered atoms.
 *
 * Only non-overlapping common prefix/suffix atoms keep structured identity.
 * Every changed middle atom is an exact weight-one literal.
 */
export function materializeRawText(
  originalState: CompositionState,
  rawText: string,
  idFactory: () => string,
  literalLabel: (snapshotRaw: string) => string = () => "自訂文字",
): CompositionState {
  if (rawText === "") return emptyComposition();

  const editedAtoms = rawText.split(",");
  const previous = originalState.fragments;
  let prefix = 0;
  while (
    prefix < editedAtoms.length &&
    prefix < previous.length &&
    editedAtoms[prefix] === previous[prefix].renderedRaw
  ) {
    prefix += 1;
  }
  let suffix = 0;
  while (
    suffix < editedAtoms.length - prefix &&
    suffix < previous.length - prefix &&
    editedAtoms[editedAtoms.length - 1 - suffix] ===
      previous[previous.length - 1 - suffix].renderedRaw
  ) {
    suffix += 1;
  }

  const fragments: WorkbenchFragment[] = previous
    .slice(0, prefix)
    .map((fragment) => ({ ...fragment }));
  const changedAtoms = editedAtoms.slice(prefix, editedAtoms.length - suffix);
  const changedPrevious = previous.slice(prefix, previous.length - suffix);
  changedAtoms.forEach((snapshotRaw, index) => {
    const reusable =
      changedAtoms.length === 1 &&
      changedPrevious.length === 1 &&
      changedPrevious[0].kind === "literal"
        ? changedPrevious[0]
        : undefined;
    fragments.push({
      id: reusable?.id ?? idFactory(),
      kind: "literal",
      displayName: literalLabel(snapshotRaw),
      snapshotRaw,
      sourceSnapshotRaw: snapshotRaw,
      weight: "",
      renderedRaw: snapshotRaw,
      range: { start: 0, end: 0 },
      blockingDiagnosticId:
        changedAtoms.length === changedPrevious.length
          ? changedPrevious[index]?.blockingDiagnosticId
          : undefined,
    });
  });
  if (suffix > 0) {
    fragments.push(
      ...previous
        .slice(previous.length - suffix)
        .map((fragment) => ({ ...fragment })),
    );
  }
  const rebuilt = rebuild(fragments);
  // Changed atoms are exact weight-one literals, so this is an invariant.
  if (rebuilt.text !== rawText) {
    throw new Error("comma-atomic reconciliation changed the textarea value");
  }
  return rebuilt;
}

export function setFragmentText(
  state: CompositionState,
  id: string,
  snapshotRaw: string,
  literalLabel: (snapshotRaw: string) => string = () => "自訂文字",
  idFactory: () => string = () => `${id}-comma-${crypto.randomUUID()}`,
): CompositionState {
  const fragments: WorkbenchFragment[] = [];
  for (const fragment of state.fragments) {
    if (fragment.id !== id) {
      fragments.push(fragment);
      continue;
    }
    for (const [index, atom] of snapshotRaw.split(",").entries()) {
      fragments.push({
        ...fragment,
        id: index === 0 ? fragment.id : idFactory(),
        kind: "literal",
        source: undefined,
        userAddedSource: false,
        displayName: literalLabel(atom),
        snapshotRaw: atom,
        sourceSnapshotRaw: atom,
      });
    }
  }
  return rebuild(fragments);
}

export function setFragmentWeight(
  state: CompositionState,
  id: string,
  weight: string,
): CompositionState {
  return rebuild(
    state.fragments.map((fragment) =>
      fragment.id === id ? { ...fragment, weight } : fragment,
    ),
  );
}

export function removeFragment(
  state: CompositionState,
  id: string,
): CompositionState {
  return rebuild(state.fragments.filter((fragment) => fragment.id !== id));
}

export function moveFragment(
  state: CompositionState,
  id: string,
  direction: -1 | 1,
): CompositionState {
  const index = state.fragments.findIndex((fragment) => fragment.id === id);
  const target = index + direction;
  if (index < 0 || target < 0 || target >= state.fragments.length) return state;
  const fragments = [...state.fragments];
  [fragments[index], fragments[target]] = [
    fragments[target],
    fragments[index],
  ];
  return rebuild(fragments);
}

export function deserializeFragments(
  apiFragments: readonly ApiPromptFragment[],
  polarity: PromptPolarity,
  idFactory: () => string,
  entryNameByRef: ReadonlyMap<string, string>,
  literalLabel: (snapshotRaw: string) => string = () => "自訂文字",
): CompositionState {
  const ordered = apiFragments
    .map((fragment, originalIndex) => ({ fragment, originalIndex }))
    .sort(
      (left, right) =>
        left.fragment.order - right.fragment.order ||
        left.originalIndex - right.originalIndex,
    );

  return rebuild(
    ordered.map(({ fragment }) => {
      const base: WorkbenchFragment = {
        id: idFactory(),
        kind: fragment.kind,
        displayName: literalLabel(fragment.snapshot),
        snapshotRaw: fragment.snapshot,
        sourceSnapshotRaw: fragment.snapshot,
        weight:
          fragment.weight === 1
            ? ""
            : canonicalWeightString(String(fragment.weight)),
        renderedRaw: "",
        range: { start: 0, end: 0 },
      };
      if (fragment.kind === "entry" && fragment.ref) {
        const { category_id: categoryId, entry_id: entryId } = fragment.ref;
        base.displayName =
          entryNameByRef.get(
            `${fragment.ref.polarity}/${categoryId}/${entryId}`,
          ) ?? "自訂文字";
        base.source = {
          polarity: fragment.ref.polarity,
          categoryId,
          entryId,
          revision: fragment.source_revision,
        };
      }
      return base;
    }),
  );
}

export function serializeFragments(
  state: CompositionState,
): ApiPromptFragment[] {
  return state.fragments.map((fragment, index) => {
    const base: ApiPromptFragment = {
      kind: fragment.kind,
      snapshot: fragment.snapshotRaw,
      weight: normalizedWeight(fragment.weight),
      order: (index + 1) * 10,
    };
    if (base.kind === "entry" && fragment.source) {
      base.ref = {
        polarity: fragment.source.polarity,
        category_id: fragment.source.categoryId,
        entry_id: fragment.source.entryId,
      };
      base.source_revision = fragment.source.revision;
    }
    return base;
  });
}

export function tagDiagnosticFallback(
  state: CompositionState,
  diagnosticId: string,
  startPosition: number,
  count: number,
): CompositionState {
  const startIndex = startPosition - 1;
  return rebuild(
    state.fragments.map((fragment, index) =>
      index >= startIndex && index < startIndex + count
        ? { ...fragment, blockingDiagnosticId: diagnosticId }
        : fragment,
    ),
  );
}

export function replaceDiagnosticFallback(
  state: CompositionState,
  diagnosticId: string,
  replacementIds: readonly string[],
): CompositionState {
  const fallbackIndexes = state.fragments.flatMap((fragment, index) =>
    fragment.blockingDiagnosticId === diagnosticId ? [index] : [],
  );
  if (fallbackIndexes.length === 0) return state;
  const replacementSet = new Set(replacementIds);
  const replacements = state.fragments
    .filter((fragment) => replacementSet.has(fragment.id))
    .map((fragment) => ({
      ...fragment,
      blockingDiagnosticId: undefined,
      userAddedSource: false,
    }));
  if (replacements.length === 0) return state;
  const firstFallback = fallbackIndexes[0];
  const insertionIndex = state.fragments
    .slice(0, firstFallback)
    .filter(
      (fragment) =>
        fragment.blockingDiagnosticId !== diagnosticId &&
        !replacementSet.has(fragment.id),
    ).length;
  const remaining = state.fragments.filter(
    (fragment) =>
      fragment.blockingDiagnosticId !== diagnosticId &&
      !replacementSet.has(fragment.id),
  );
  remaining.splice(insertionIndex, 0, ...replacements);
  return rebuild(remaining);
}

export function normalizeDisplayMatch(value: string | undefined | null): string {
  return (value ?? "")
    .normalize("NFKC")
    .trim()
    .replace(/\s+/gu, " ")
    .toLocaleLowerCase("und");
}

export function buildLiteralLabelIndex(
  entries: readonly PromptEntry[],
): Map<string, PromptEntry[]> {
  const index = new Map<string, PromptEntry[]>();
  entries.forEach((entry) => {
    const key = normalizeDisplayMatch(entry.prompt);
    const matches = index.get(key) ?? [];
    matches.push(entry);
    index.set(key, matches);
  });
  return index;
}

export function resolveLiteralDisplayLabel(
  snapshotRaw: string | undefined | null,
  index: LiteralLabelIndex,
): string {
  if (!(snapshotRaw ?? "").trim()) return "自訂文字";
  const matches = index.get(normalizeDisplayMatch(snapshotRaw)) ?? [];
  if (matches.length !== 1) return "自訂文字";
  return matches[0].name_zh.trim() || matches[0].prompt.trim() || "自訂文字";
}

export function blankSegmentPreflight(
  positive: CompositionState,
  negative: CompositionState,
): BlankSegmentLocation[] {
  const result: BlankSegmentLocation[] = [];
  ([
    ["positive", positive],
    ["negative", negative],
  ] as const).forEach(([polarity, state]) => {
    state.fragments.forEach((fragment, index) => {
      if (
        fragment.snapshotRaw.trim() === "" ||
        fragment.renderedRaw.trim() === ""
      ) {
        result.push({ polarity, position: index + 1 });
      }
    });
  });
  return result;
}

export function blankSegmentMessage(
  locations: readonly BlankSegmentLocation[],
): string {
  const format = (polarity: PromptPolarity) => {
    const positions = locations
      .filter((item) => item.polarity === polarity)
      .map((item) => item.position);
    if (positions.length === 0) return "";
    return `${polarity === "positive" ? "正向" : "負向"}第 ${positions.join("、")} 段`;
  };
  const summary = [format("positive"), format("negative")]
    .filter(Boolean)
    .join("；");
  return `${summary}：每個 ASCII 逗號都會建立一個 prompt；請填入內容或移除該空白段。`;
}

function compareRankKey(a: number[], b: number[]): number {
  const length = Math.min(a.length, b.length);
  for (let index = 0; index < length; index += 1) {
    if (a[index] < b[index]) return -1;
    if (a[index] > b[index]) return 1;
  }
  return a.length - b.length;
}

export function sortFragmentsByRecommendation(
  state: CompositionState,
  rankOf: (fragment: WorkbenchFragment) => number[],
): CompositionState {
  const ranked = state.fragments.map((fragment, index) => ({
    fragment,
    index,
    rank: rankOf(fragment),
  }));
  ranked.sort(
    (left, right) => compareRankKey(left.rank, right.rank) || left.index - right.index,
  );
  return rebuild(ranked.map((item) => item.fragment));
}

export const LITERAL_GROUP_KEY = "__literal__";

export function appendFragmentsDeduped(
  target: CompositionState,
  incoming: readonly WorkbenchFragment[],
): CompositionState {
  const seen = new Set<string>();
  const refKey = (fragment: WorkbenchFragment) =>
    fragment.kind === "entry" && fragment.source
      ? `${fragment.source.polarity}/${fragment.source.categoryId}/${fragment.source.entryId}`
      : null;
  for (const fragment of target.fragments) {
    const key = refKey(fragment);
    if (key) seen.add(key);
  }
  const additions: WorkbenchFragment[] = [];
  for (const fragment of incoming) {
    const key = refKey(fragment);
    if (key) {
      if (seen.has(key)) continue;
      seen.add(key);
    }
    additions.push(fragment);
  }
  if (additions.length === 0) return target;
  return rebuild([...target.fragments, ...additions]);
}

export function distinctCategoriesOf(
  fragments: readonly WorkbenchFragment[],
  categoryInfoOf: (
    fragment: WorkbenchFragment,
  ) => { key: string; displayName: string; order: number } | null,
  literalLabel = "自訂文字",
): { key: string; displayName: string; order: number }[] {
  const byKey = new Map<string, { key: string; displayName: string; order: number }>();
  let hasLiteral = false;
  fragments.forEach((fragment) => {
    const info = categoryInfoOf(fragment);
    if (!info) {
      hasLiteral = true;
      return;
    }
    if (!byKey.has(info.key)) byKey.set(info.key, info);
  });
  const result = [...byKey.values()].sort((left, right) => left.order - right.order);
  if (hasLiteral) {
    result.push({ key: LITERAL_GROUP_KEY, displayName: literalLabel, order: Number.POSITIVE_INFINITY });
  }
  return result;
}
