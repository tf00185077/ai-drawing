import type { PromptPolarity } from "../../types/api";

export type EditableWeight = string;

export interface WorkbenchFragment {
  id: string;
  kind: "entry" | "literal";
  source?: {
    polarity: PromptPolarity;
    categoryId: string;
    entryId: string;
    revision: number;
  };
  originalSnapshot: string;
  text: string;
  weight: EditableWeight;
  range: { start: number; end: number };
}

export type NewWorkbenchFragment = Omit<WorkbenchFragment, "range">;

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

let literalSequence = 0;

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
  return rebuild([...state.fragments, { ...fragment, range: { start: 0, end: 0 } }]);
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

function balancedParentheses(text: string): boolean {
  let depth = 0;
  for (const character of text) {
    if (character === "(") depth += 1;
    if (character === ")") depth -= 1;
    if (depth < 0) return false;
  }
  return depth === 0;
}

function commonPrefix(a: string, b: string): number {
  let index = 0;
  while (index < a.length && index < b.length && a[index] === b[index]) index += 1;
  return index;
}

function commonSuffix(a: string, b: string, prefix: number): number {
  let count = 0;
  while (count < a.length - prefix && count < b.length - prefix && a[a.length - 1 - count] === b[b.length - 1 - count]) count += 1;
  return count;
}

function unwrapRenderedText(value: string, weight: string): string | null {
  if (!weight.trim()) return value.trim();
  const suffix = `:${weight.trim()})`;
  if (!value.startsWith("(") || !value.endsWith(suffix)) return null;
  return value.slice(1, -suffix.length).trim();
}

export function reconcileComposedText(state: CompositionState, nextText: string): CompositionState {
  if (nextText === state.text) return state;
  if (!balancedParentheses(nextText)) {
    return { ...state, text: nextText, warning: "最終文字的括號或權重語法無法同步；已保留手動輸入。" };
  }

  const oldParts = state.fragments.map(renderFragment);
  const nextParts = nextText.split(", ");
  if (nextParts.length === oldParts.length + 1) {
    const insertion = nextParts.findIndex((part, index) => part !== oldParts[index]);
    const position = insertion < 0 ? oldParts.length : insertion;
    const afterMatches = oldParts.slice(position).every((part, index) => part === nextParts[position + index + 1]);
    if (afterMatches && nextParts[position]?.trim()) {
      const literal: WorkbenchFragment = {
        id: `literal-${++literalSequence}`,
        kind: "literal",
        originalSnapshot: nextParts[position].trim(),
        text: nextParts[position].trim(),
        weight: "",
        range: { start: 0, end: 0 },
      };
      const fragments = [...state.fragments];
      fragments.splice(position, 0, literal);
      return rebuild(fragments);
    }
  }

  const prefix = commonPrefix(state.text, nextText);
  const suffix = commonSuffix(state.text, nextText, prefix);
  const oldEnd = state.text.length - suffix;
  const affected = state.fragments.filter((fragment) => prefix <= fragment.range.end && oldEnd >= fragment.range.start);
  if (affected.length === 1) {
    const fragment = affected[0];
    const before = state.text.slice(fragment.range.start, prefix);
    const changed = nextText.slice(prefix, nextText.length - suffix);
    const after = state.text.slice(oldEnd, fragment.range.end);
    const unwrapped = unwrapRenderedText(before + changed + after, fragment.weight);
    if (unwrapped !== null) return setFragmentText(state, fragment.id, unwrapped);
  }

  return { ...state, text: nextText, warning: "這次修改跨越多個片段，已保留手動輸入但未變更來源片段。" };
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
