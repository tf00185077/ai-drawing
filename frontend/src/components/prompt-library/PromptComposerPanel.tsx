import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CompositionState, WorkbenchFragment } from "./compositionState";
import { groupFragmentsByCategory } from "./compositionState";

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
  const [pendingCardFocus, setPendingCardFocus] = useState<number | null>(null);
  const finalTextarea = useRef<HTMLTextAreaElement>(null);
  const pendingSelection = useRef<{
    start: number;
    end: number;
    direction: "forward" | "backward" | "none";
  } | null>(null);

  useEffect(() => {
    const focusInvalid = (event: Event) => {
      const detail = (event as CustomEvent<{ polarity: string; position: number }>).detail;
      if (detail.polarity !== polarity) return;
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
  }, [pendingCardFocus, polarity, state.fragments]);

  useLayoutEffect(() => {
    const selection = pendingSelection.current;
    const textarea = finalTextarea.current;
    if (!selection || !textarea || document.activeElement !== textarea) return;
    const clamp = (value: number) => Math.min(value, textarea.value.length);
    textarea.setSelectionRange(clamp(selection.start), clamp(selection.end), selection.direction);
    pendingSelection.current = null;
  }, [state.text, state.fragments]);

  const groups = groupFragmentsByCategory(state.fragments, categoryInfoOf ?? (() => null));

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="mt-1 text-xs text-slate-500">依分類分區檢視 · 最終文字</p>
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

      <div data-testid="prompt-option-grid" className="mt-3 space-y-4">
        {state.fragments.length === 0 && (
          <p className="rounded-lg border border-dashed border-slate-700 p-3 text-sm text-slate-500">尚未加入 Prompt</p>
        )}
        {groups.map((group) => (
          <div key={group.key} data-testid={`prompt-group-${group.key}`}>
            <h4 className="mb-2 border-b border-slate-700 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
              {group.displayName}
              <span className="ml-2 text-slate-500">{group.fragments.length}</span>
            </h4>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {group.fragments.map((fragment) => {
                const index = state.fragments.indexOf(fragment);
                const label = fragment.displayName;
                const invalid = fragment.snapshotRaw.trim() === "" || fragment.renderedRaw.trim() === "";
                return (
                  <div
                    key={fragment.id}
                    className={`rounded-lg border bg-slate-800/70 p-3 ${invalid ? "border-red-500" : "border-slate-700"}`}
                  >
                    <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200">
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
                          <button
                            type="button"
                            disabled={index === 0}
                            onClick={() => onMove(fragment.id, -1)}
                            className="rounded-md bg-slate-700 px-2 py-1.5 text-xs disabled:opacity-40"
                          >
                            上移
                          </button>
                          <button
                            type="button"
                            disabled={index === state.fragments.length - 1}
                            onClick={() => onMove(fragment.id, 1)}
                            className="rounded-md bg-slate-700 px-2 py-1.5 text-xs disabled:opacity-40"
                          >
                            下移
                          </button>
                        </div>
                        <button
                          type="button"
                          onClick={() => onRemove(fragment.id)}
                          className="rounded-md bg-red-950 px-2 py-1.5 text-xs text-red-300"
                        >
                          刪除
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

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
