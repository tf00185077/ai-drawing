import { useEffect, useState } from "react";
import type { CompositionState } from "./compositionState";

const PAGE_SIZE = 5;

interface Props {
  title: "Positive Prompt" | "Negative Prompt";
  state: CompositionState;
  onTextChange: (id: string, text: string) => void;
  onWeightChange: (id: string, weight: string) => void;
  onMove: (id: string, direction: -1 | 1) => void;
  onRemove: (id: string) => void;
  onComposedTextChange: (text: string) => void;
}

export default function PromptComposerPanel({ title, state, onTextChange, onWeightChange, onMove, onRemove, onComposedTextChange }: Props) {
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(state.fragments.length / PAGE_SIZE));
  const visibleFragments = state.fragments.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  useEffect(() => {
    if (page >= pageCount) setPage(pageCount - 1);
  }, [page, pageCount]);

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-white">{title}</h3>
        <span className="rounded-full bg-slate-800 px-2 py-1 text-xs text-slate-400">{state.fragments.length} 個片段</span>
      </div>
      <div data-testid="prompt-option-grid" className="mt-3 grid grid-cols-3 gap-2">
        {state.fragments.length === 0 && <p className="rounded-lg border border-dashed border-slate-700 p-3 text-sm text-slate-500">尚未加入 Prompt</p>}
        {visibleFragments.map((fragment, pageIndex) => {
          const index = page * PAGE_SIZE + pageIndex;
          const label = fragment.source?.entryId === "masterpiece" ? "高品質" : fragment.source?.entryId === "blurry" ? "模糊" : `片段 ${index + 1}`;
          return (
            <div key={fragment.id} className="rounded-lg border border-slate-700 bg-slate-800/70 p-3">
              <label className="block text-xs text-slate-400">{label} 內容
                <textarea aria-label={`${label} 內容`} value={fragment.text} onChange={(event) => onTextChange(fragment.id, event.target.value)} className="mt-1 min-h-16 w-full resize-y rounded-md border border-slate-600 bg-slate-950 p-2 text-sm text-white" />
              </label>
              <div className="mt-2 flex flex-wrap items-end gap-2">
                <label className="text-xs text-slate-400">{label} 權重
                  <input aria-label={`${label} 權重`} type="number" min="0.01" max="2" step="0.1" placeholder="未設定" value={fragment.weight} onChange={(event) => onWeightChange(fragment.id, event.target.value)} className="mt-1 block w-24 rounded-md border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white" />
                </label>
                <button type="button" disabled={index === 0} onClick={() => onMove(fragment.id, -1)} className="rounded-md bg-slate-700 px-2 py-1.5 text-xs disabled:opacity-40">上移</button>
                <button type="button" disabled={index === state.fragments.length - 1} onClick={() => onMove(fragment.id, 1)} className="rounded-md bg-slate-700 px-2 py-1.5 text-xs disabled:opacity-40">下移</button>
                <button type="button" onClick={() => onRemove(fragment.id)} className="rounded-md bg-red-950 px-2 py-1.5 text-xs text-red-300">刪除</button>
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
        <textarea aria-label={`${title} 最終文字`} value={state.text} onChange={(event) => onComposedTextChange(event.target.value)} className="mt-2 min-h-28 w-full resize-y rounded-lg border border-slate-600 bg-slate-950 p-3 font-mono text-sm text-slate-100 focus:border-emerald-500 focus:outline-none" />
      </label>
      {state.warning && <p className="mt-2 text-xs text-amber-300">{state.warning}</p>}
    </section>
  );
}
