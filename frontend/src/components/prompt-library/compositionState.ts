import type { PromptPolarity } from "../../types/api";

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
  originalSnapshot: string;
  text: string;
  weight: EditableWeight;
  range: { start: number; end: number };
}

export type NewWorkbenchFragment = Omit<WorkbenchFragment, "range" | "displayName"> & {
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

export function emptyComposition(): CompositionState {
  return { fragments: [], text: "", warning: null };
}

function renderFragment(fragment: Pick<WorkbenchFragment, "text" | "weight">): string {
  const text = fragment.text.trim();
  if (!text || fragment.weight.trim() === "") return text;
  return `(${text}:${fragment.weight.trim()})`;
}

function rebuild(fragments: WorkbenchFragment[], warning: string | null = null): CompositionState {
  let cursor = 0;
  const rendered: string[] = [];
  const ranged = fragments
    .filter((fragment) => fragment.text.trim())
    .map((fragment) => {
      const value = renderFragment(fragment);
      const start = cursor;
      cursor += value.length;
      rendered.push(value);
      const result = { ...fragment, range: { start, end: cursor } };
      cursor += 2;
      return result;
    });
  return { fragments: ranged, text: rendered.join(", "), warning };
}

export function appendFragment(state: CompositionState, fragment: NewWorkbenchFragment): CompositionState {
  const displayName = fragment.displayName
    ?? (fragment.kind === "entry" ? fragment.source?.entryId : undefined)
    ?? "自訂文字";
  return rebuild([...state.fragments, { ...fragment, displayName, range: { start: 0, end: 0 } }]);
}

export function setFragmentText(state: CompositionState, id: string, text: string): CompositionState {
  return rebuild(state.fragments.map((fragment) => fragment.id === id ? { ...fragment, text } : fragment));
}

export function setFragmentWeight(state: CompositionState, id: string, weight: string): CompositionState {
  return rebuild(state.fragments.map((fragment) => fragment.id === id ? { ...fragment, weight } : fragment));
}

export function removeFragment(state: CompositionState, id: string): CompositionState {
  return rebuild(state.fragments.filter((fragment) => fragment.id !== id));
}

export function moveFragment(state: CompositionState, id: string, direction: -1 | 1): CompositionState {
  const index = state.fragments.findIndex((fragment) => fragment.id === id);
  const target = index + direction;
  if (index < 0 || target < 0 || target >= state.fragments.length) return state;
  const fragments = [...state.fragments];
  [fragments[index], fragments[target]] = [fragments[target], fragments[index]];
  return rebuild(fragments);
}

export function deserializeFragments(
  apiFragments: readonly ApiPromptFragment[],
  polarity: PromptPolarity,
  idFactory: () => string,
  entryNameByRef: ReadonlyMap<string, string>,
): CompositionState {
  const ordered = apiFragments
    .map((fragment, originalIndex) => ({ fragment, originalIndex }))
    .sort((left, right) => left.fragment.order - right.fragment.order || left.originalIndex - right.originalIndex);

  return rebuild(ordered.map(({ fragment }) => {
    const base: WorkbenchFragment = {
      id: idFactory(),
      kind: fragment.kind,
      displayName: "自訂文字",
      originalSnapshot: fragment.snapshot,
      text: fragment.snapshot,
      weight: fragment.weight === 1 ? "" : String(fragment.weight),
      range: { start: 0, end: 0 },
    };
    if (fragment.kind === "entry" && fragment.ref) {
      const { category_id: categoryId, entry_id: entryId } = fragment.ref;
      base.displayName = entryNameByRef.get(`${polarity}/${categoryId}/${entryId}`) ?? entryId;
      base.source = {
        polarity: fragment.ref.polarity,
        categoryId,
        entryId,
        revision: fragment.source_revision,
      };
    }
    return base;
  }));
}

function balancedParentheses(text: string): boolean {
  let depth = 0;
  for (const character of text) {
    if (character === "(") depth += 1;
    if (character === ")") depth -= 1;
    if (depth < 0) return false;
  }
  return depth === 0;
}

function splitTopLevel(text: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let start = 0;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (character === "(") depth += 1;
    if (character === ")") depth -= 1;
    if (character === "," && depth === 0) {
      parts.push(text.slice(start, index).trim());
      start = index + 1;
    }
  }
  parts.push(text.slice(start).trim());
  return parts.filter(Boolean);
}

type ParsedRawFragment = { text: string; weight: string };

function parseRawFragment(part: string): ParsedRawFragment | { error: string } {
  if (!(part.startsWith("(") && part.endsWith(")"))) return { text: part, weight: "" };

  const inner = part.slice(1, -1);
  let depth = 0;
  let weightSeparator = -1;
  for (let index = 0; index < inner.length; index += 1) {
    const character = inner[index];
    if (character === "(") depth += 1;
    if (character === ")") depth -= 1;
    if (character === ":" && depth === 0) weightSeparator = index;
  }
  if (weightSeparator < 0) return { text: part, weight: "" };

  const fragmentText = inner.slice(0, weightSeparator).trim();
  const rawWeight = inner.slice(weightSeparator + 1).trim();
  const decimalWeight = /^-?(?:\d+(?:\.\d*)?|\.\d+)$/;
  if (!rawWeight || !decimalWeight.test(rawWeight)) {
    return { error: `權重「${rawWeight || "空白"}」必須是有效的十進位數字。` };
  }
  const weight = Number(rawWeight);
  if (weight <= 0) return { error: `權重 ${rawWeight} 必須大於 0。` };
  if (weight > 2) return { error: `權重 ${rawWeight} 必須不大於 2。` };
  if (!fragmentText) return { error: "加權 Prompt 不可為空白。" };
  return { text: fragmentText, weight: rawWeight };
}

export type RawCommitResult =
  | { ok: true; state: CompositionState }
  | { ok: false; state: CompositionState; error: string };

export function commitRawText(
  originalState: CompositionState,
  rawText: string,
  idFactory: () => string,
): RawCommitResult {
  if (!balancedParentheses(rawText)) {
    return { ok: false, state: originalState, error: "Prompt 括號不平衡，請補上缺少的左括號或右括號後再套用。" };
  }
  if (!rawText.trim()) return { ok: true, state: emptyComposition() };

  const parsed: ParsedRawFragment[] = [];
  for (const part of splitTopLevel(rawText)) {
    const result = parseRawFragment(part);
    if ("error" in result) return { ok: false, state: originalState, error: result.error };
    parsed.push(result);
  }

  return {
    ok: true,
    state: rebuild(parsed.map((part) => ({
      id: idFactory(),
      kind: "literal",
      displayName: "自訂文字",
      originalSnapshot: part.text,
      text: part.text,
      weight: part.weight,
      range: { start: 0, end: 0 },
    }))),
  };
}

/** @deprecated Task 8 will replace the UI callback with draft state plus commitRawText. */
export function reconcileComposedText(state: CompositionState, _nextText: string): CompositionState {
  return state;
}

export function serializeFragments(state: CompositionState): ApiPromptFragment[] {
  return state.fragments.map((fragment, index) => {
    const editedEntry = fragment.kind === "entry" && fragment.text !== fragment.originalSnapshot;
    const base: ApiPromptFragment = {
      kind: editedEntry ? "literal" : fragment.kind,
      snapshot: fragment.text,
      weight: fragment.weight.trim() === "" ? 1 : Number(fragment.weight),
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
