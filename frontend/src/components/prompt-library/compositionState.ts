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

function parseComposedText(text: string): { text: string; weight: string }[] {
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
  return parts.filter(Boolean).map((part) => {
    const weighted = part.match(/^\((.+):([0-9]*\.?[0-9]+)\)$/);
    return weighted ? { text: weighted[1].trim(), weight: weighted[2] } : { text: part, weight: "" };
  });
}

export function reconcileComposedText(state: CompositionState, nextText: string): CompositionState {
  if (nextText === state.text) return state;
  if (!balancedParentheses(nextText)) {
    return { ...state, text: nextText, warning: "括號尚未閉合；完成輸入後會同步回上方 Prompt。" };
  }
  const parsed = parseComposedText(nextText);
  if (parsed.length === 0) return emptyComposition();
  return rebuild(parsed.map((part, index) => {
    const existing = state.fragments[index];
    if (existing) return { ...existing, text: part.text, weight: part.weight };
    return {
      id: `literal-${++literalSequence}`,
      kind: "literal",
      originalSnapshot: part.text,
      text: part.text,
      weight: part.weight,
      range: { start: 0, end: 0 },
    };
  }));
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
