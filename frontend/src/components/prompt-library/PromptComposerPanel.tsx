import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CompositionState, WorkbenchFragment } from "./compositionState";
import { distinctCategoriesOf, LITERAL_GROUP_KEY } from "./compositionState";

const PAGE_SIZE = 9;
const ALL_KEY = "__all__";

interface Props {
  title: "Positive Prompt" | "Negative Prompt";
  state: CompositionState;
  arrangement: "auto" | "manual";
  categoryInfoOf: (
    fragment: WorkbenchFragment,
  ) => { key: string; displayName: string; order: number } | null;
  onReapplySort: () => void;
  onFinalTextChange: (text: string) => void;
  onTextChange: (id: string, text: string) => void;
  onWeightChange: (id: string, weight: string) => void;
  onMove: (id: string, direction: -1 | 1) => void;
  onRemove: (id: string) => void;
}

export default function PromptComposerPanel({
  title,
  state,
  arrangement,
  categoryInfoOf,
  onReapplySort,
  onFinalTextChange,
  onTextChange,
  onWeightChange,
  onMove,
  onRemove,
}: Props) {
  const polarity = title === "Positive Prompt" ? "positive" : "negative";
  const [filterKey, setFilterKey] = useState<string>(ALL_KEY);
  const [page, setPage] = useState(0);
  const [pendingCardFocus, setPendingCardFocus] = useState<number | null>(null);
  const finalTextarea = useRef<HTMLTextAreaElement>(null);
  const pendingSelection = useRef<{
    start: number;
    end: number;
    direction: "forward" | "backward" | "none";
  } | null>(null);

  const matchesFilter = (fragment: WorkbenchFragment) => {
    if (filterKey === ALL_KEY) return true;
    const info = categoryInfoOf(fragment);
    if (filterKey === LITERAL_GROUP_KEY) return info === null;
    return info?.key === filterKey;
  };

  const filterOptions = distinctCategoriesOf(state.fragments, categoryInfoOf);
  const filtered = state.fragments.filter(matchesFilter);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageFragments = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  // Reset to page 1 when the filter changes; clamp when the page count shrinks.
  useEffect(() => { setPage(0); }, [filterKey]);
  useEffect(() => { if (page >= pageCount) setPage(pageCount - 1); }, [page, pageCount]);
  // If the active filter no longer exists (its last fragment removed), fall back to 全部.
  useEffect(() => {
    if (filterKey === ALL_KEY) return;
    const stillPresent = filterKey === LITERAL_GROUP_KEY
      ? state.fragments.some((fragment) => categoryInfoOf(fragment) === null)
      : filterOptions.some((option) => option.key === filterKey);
    if (!stillPresent) setFilterKey(ALL_KEY);
  }, [filterKey, filterOptions, state.fragments, categoryInfoOf]);

  useEffect(() => {
    const focusInvalid = (event: Event) => {
      const detail = (event as CustomEvent<{ polarity: string; position: number }>).detail;
      if (detail.polarity !== polarity) return;
      setFilterKey(ALL_KEY);
      setPage(Math.floor((detail.position - 1) / PAGE_SIZE));
      setPendingCardFocus(detail.position);
    };
    window.addEventListener("prompt-workbench-focus", focusInvalid);
    return () => window.removeEventListener("prompt-workbench-focus", focusInvalid);
  }, [polarity]);

  useLayoutEffect(() => {
    if (pendingCardFocus === null) return;
    const selector = `textarea[data-polarity="${polarity}"][data-segment-position="${pendingCardFocus}"]`;
    document.querySelector<HTMLTextAreaElement>(selector)?.focus();
    setPendingCardFocus(null);
  }, [pendingCardFocus, polarity, state.fragments, page]);

  useLayoutEffect(() => {
    const selection = pendingSelection.current;
    const textarea = finalTextarea.current;
    if (!selection || !textarea || document.activeElement !== textarea) return;
    const clamp = (value: number) => Math.min(value, textarea.value.length);
    textarea.setSelectionRange(clamp(selection.start), clamp(selection.end), selection.direction);
    pendingSelection.current = null;
  }, [state.text, state.fragments]);

  const filterButtonClass = (active: boolean) =>
    `rounded-full px-3 py-1 text-xs ${active ? "bg-emerald-700 text-white" : "bg-slate-800 text-slate-300"}`;

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="mt-1 text-xs text-slate-500">篩選檢視 · 最終文字</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-slate-800 px-2 py-1 text-xs text-slate-400">
            {state.fragments.length} 個片段
          </span>
          <span
            className={`rounded-full px-2 py-1 text-xs ${
              arrangement === "auto" ? "bg-emerald-900/60 text-emerald-300" : "bg-slate-800 text-slate-400"
            }`}
          >
            {arrangement === "auto" ? "已自動排序" : "手動排序"}
          </span>
          <button
            type="button"
            aria-label={`${title} 重新套用推薦排序`}
            onClick={onReapplySort}
            className="rounded-md bg-sky-700 px-2 py-1 text-xs text-white"
          >
            重新套用推薦排序
          </button>
        </div>
      </div>

      <div role="group" aria-label={`${title} 分類篩選`} className="mt-3 flex flex-wrap gap-2">
        <button type="button" aria-pressed={filterKey === ALL_KEY} onClick={() => setFilterKey(ALL_KEY)} className={filterButtonClass(filterKey === ALL_KEY)}>全部</button>
        {filterOptions.map((option) => (
          <button key={option.key} type="button" aria-pressed={filterKey === option.key} onClick={() => setFilterKey(option.key)} className={filterButtonClass(filterKey === option.key)}>
            {option.displayName}
          </button>
        ))}
      </div>

      <div data-testid="prompt-option-grid" className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
        {state.fragments.length === 0 && (
          <p className="col-span-full rounded-lg border border-dashed border-slate-700 p-3 text-sm text-slate-500">尚未加入 Prompt</p>
        )}
        {pageFragments.map((fragment) => {
          const index = state.fragments.indexOf(fragment);
          const label = fragment.displayName;
          const categoryLabel = categoryInfoOf(fragment)?.displayName ?? "自訂文字";
          const invalid = fragment.snapshotRaw.trim() === "" || fragment.renderedRaw.trim() === "";
          return (
            <div
              key={fragment.id}
              className={`rounded-lg border bg-slate-800/70 p-3 ${invalid ? "border-red-500" : "border-slate-700"}`}
            >
              <div className="mb-2 flex flex-wrap items-center gap-2 text-sm font-medium text-slate-200">
                <span className="rounded-full bg-slate-900 px-2 py-0.5 text-xs text-slate-400">{categoryLabel}</span>
                <span>{label}</span>
                <span className="text-xs text-slate-500">第 {index + 1} 段</span>
                {invalid && (
                  <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-xs text-red-300">必須填寫</span>
                )}
              </div>
              <label className="block text-xs text-slate-400">內容
                <textarea
                  data-polarity={polarity}
                  data-segment-position={index + 1}
                  aria-invalid={invalid}
                  aria-label={`${label} 內容`}
                  value={fragment.snapshotRaw}
                  onChange={(event) => onTextChange(fragment.id, event.target.value)}
                  className="mt-1 min-h-16 w-full resize-y rounded-md border border-slate-600 bg-slate-950 p-2 text-sm text-white"
                />
              </label>
              <div className="mt-2 flex flex-wrap items-end gap-2">
                <label className="text-xs text-slate-400">權重
                  <input
                    aria-label={`${label} 權重`}
                    type="number"
                    min="0.01"
                    max="2"
                    step="0.1"
                    placeholder="未設定"
                    value={fragment.weight}
                    onChange={(event) => onWeightChange(fragment.id, event.target.value)}
                    className="mt-1 block w-24 rounded-md border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
                  />
                </label>
                <div className="flex w-full justify-between">
                  <div className="flex gap-2">
                    <button type="button" disabled={index === 0} onClick={() => onMove(fragment.id, -1)} className="rounded-md bg-slate-700 px-2 py-1.5 text-xs disabled:opacity-40">上移</button>
                    <button type="button" disabled={index === state.fragments.length - 1} onClick={() => onMove(fragment.id, 1)} className="rounded-md bg-slate-700 px-2 py-1.5 text-xs disabled:opacity-40">下移</button>
                  </div>
                  <button type="button" onClick={() => onRemove(fragment.id)} className="rounded-md bg-red-950 px-2 py-1.5 text-xs text-red-300">刪除</button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {pageCount > 1 && (
        <nav aria-label={`${title} 分頁`} className="mt-3 flex items-center justify-center gap-3">
          <button type="button" aria-label="上一頁" disabled={page === 0} onClick={() => setPage((value) => value - 1)} className="rounded-md bg-slate-700 px-3 py-1.5 text-xs disabled:opacity-40">上一頁</button>
          <span className="text-xs text-slate-400">{page + 1} / {pageCount}</span>
          <button type="button" aria-label="下一頁" disabled={page === pageCount - 1} onClick={() => setPage((value) => value + 1)} className="rounded-md bg-slate-700 px-3 py-1.5 text-xs disabled:opacity-40">下一頁</button>
        </nav>
      )}

      <label className="mt-4 block text-sm font-medium text-slate-300">最終文字
        <textarea
          ref={finalTextarea}
          aria-label={`${title} 最終文字`}
          value={state.text}
          onChange={(event) => {
            pendingSelection.current = {
              start: event.currentTarget.selectionStart,
              end: event.currentTarget.selectionEnd,
              direction: event.currentTarget.selectionDirection,
            };
            onFinalTextChange(event.currentTarget.value);
          }}
          className="mt-2 min-h-28 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-sm text-slate-100 focus:border-emerald-600 focus:outline-none"
        />
      </label>
      {state.warning && <p className="mt-2 text-xs text-amber-300">{state.warning}</p>}
    </section>
  );
}
