import { useEffect, useRef, useState } from "react";
import type { CompositionState, RawCommitResult } from "./compositionState";

const PAGE_SIZE = 6;

interface Props {
  title: "Positive Prompt" | "Negative Prompt";
  state: CompositionState;
  onTextChange: (id: string, text: string) => void;
  onWeightChange: (id: string, weight: string) => void;
  onMove: (id: string, direction: -1 | 1) => void;
  onRemove: (id: string) => void;
  onCommitRawText: (raw: string) => RawCommitResult;
  onRawDraftStateChange: (open: boolean) => void;
  rawResetVersion: number;
}

export default function PromptComposerPanel({
  title,
  state,
  onTextChange,
  onWeightChange,
  onMove,
  onRemove,
  onCommitRawText,
  onRawDraftStateChange,
  rawResetVersion,
}: Props) {
  const [page, setPage] = useState(0);
  const [editingRaw, setEditingRaw] = useState(false);
  const [rawDraft, setRawDraft] = useState("");
  const [rawError, setRawError] = useState("");
  const rawStateCallback = useRef(onRawDraftStateChange);
  const previousResetVersion = useRef(rawResetVersion);
  const pageCount = Math.max(1, Math.ceil(state.fragments.length / PAGE_SIZE));
  const visibleFragments = state.fragments.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  rawStateCallback.current = onRawDraftStateChange;

  useEffect(() => {
    if (page >= pageCount) setPage(pageCount - 1);
  }, [page, pageCount]);

  useEffect(() => () => rawStateCallback.current(false), []);

  useEffect(() => {
    if (rawResetVersion === previousResetVersion.current) return;
    previousResetVersion.current = rawResetVersion;
    setEditingRaw(false);
    setRawDraft("");
    setRawError("");
    rawStateCallback.current(false);
  }, [rawResetVersion]);

  function openRawEditor() {
    setRawDraft(state.text);
    setRawError("");
    setEditingRaw(true);
    onRawDraftStateChange(true);
  }

  function closeRawEditor() {
    setEditingRaw(false);
    setRawDraft("");
    setRawError("");
    onRawDraftStateChange(false);
  }

  function applyRawDraft() {
    const result = onCommitRawText(rawDraft);
    if (result.ok === false) {
      setRawError(result.error);
      return;
    }
    closeRawEditor();
  }

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="mt-1 text-xs text-slate-500">{editingRaw ? "自由文字模式" : "片段模式"}</p>
        </div>
        <span className="rounded-full bg-slate-800 px-2 py-1 text-xs text-slate-400">{state.fragments.length} 個片段</span>
      </div>

      {!editingRaw ? (
        <>
          <div data-testid="prompt-option-grid" className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {state.fragments.length === 0 && <p className="rounded-lg border border-dashed border-slate-700 p-3 text-sm text-slate-500">尚未加入 Prompt</p>}
            {visibleFragments.map((fragment, pageIndex) => {
              const index = page * PAGE_SIZE + pageIndex;
              const label = fragment.displayName;
              const editedCopy = fragment.kind === "entry" && fragment.text !== fragment.originalSnapshot;
              return (
                <div key={fragment.id} className="rounded-lg border border-slate-700 bg-slate-800/70 p-3">
                  <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200">
                    <span>{label}</span>
                    {editedCopy && <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs text-amber-300">自訂副本</span>}
                  </div>
                  <label className="block text-xs text-slate-400">內容
                    <textarea aria-label={`${label} 內容`} value={fragment.text} onChange={(event) => onTextChange(fragment.id, event.target.value)} className="mt-1 min-h-16 w-full resize-y rounded-md border border-slate-600 bg-slate-950 p-2 text-sm text-white" />
                  </label>
                  <div className="mt-2 flex flex-wrap items-end gap-2">
                    <label className="text-xs text-slate-400">權重
                      <input aria-label={`${label} 權重`} type="number" min="0.01" max="2" step="0.1" placeholder="未設定" value={fragment.weight} onChange={(event) => onWeightChange(fragment.id, event.target.value)} className="mt-1 block w-24 rounded-md border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white" />
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
            <textarea aria-label={`${title} 最終文字`} readOnly value={state.text} className="mt-2 min-h-28 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-sm text-slate-300" />
          </label>
          <button type="button" onClick={openRawEditor} className="mt-2 rounded-md bg-slate-700 px-3 py-2 text-sm text-slate-100">自由文字模式</button>
        </>
      ) : (
        <div className="mt-3 rounded-lg border border-emerald-500/30 bg-slate-800/60 p-3">
          <label className="block text-sm font-medium text-slate-200">自由文字草稿
            <textarea aria-label={`${title} 自由文字草稿`} value={rawDraft} onChange={(event) => setRawDraft(event.target.value)} className="mt-2 min-h-36 w-full resize-y rounded-lg border border-emerald-600 bg-slate-950 p-3 font-mono text-sm text-slate-100 focus:outline-none" />
          </label>
          {rawError && <p role="alert" className="mt-2 text-sm text-red-300">{rawError}</p>}
          <p className="mt-2 text-xs text-slate-400">變更只會保留在草稿；按「套用」後才會取代目前片段。</p>
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" onClick={closeRawEditor} className="rounded-md bg-slate-700 px-3 py-2 text-sm">取消</button>
            <button type="button" onClick={applyRawDraft} className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white">套用</button>
          </div>
        </div>
      )}
      {state.warning && <p className="mt-2 text-xs text-amber-300">{state.warning}</p>}
    </section>
  );
}
