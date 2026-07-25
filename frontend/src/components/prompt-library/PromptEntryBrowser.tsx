import { useMemo, useState } from "react";
import type { PromptPolarity } from "../../types/api";
import { suspectReason } from "./suspectChinese";

export interface BrowserCategory { id: string; polarity: PromptPolarity; name_zh: string; revision: number; etag: string; archived: boolean }
export interface BrowserEntry { id: string; name_zh: string; prompt: string; description_zh: string; aliases: string[]; keywords: string[]; order: number; revision: number; archived: boolean }

export function promptEntryLabel(entry: Pick<BrowserEntry, "id" | "name_zh" | "prompt">): string {
  return entry.name_zh?.trim() || entry.prompt?.trim() || entry.id;
}

export function promptEntryContent(entry: Pick<BrowserEntry, "id" | "prompt">): string {
  return entry.prompt?.trim() ? entry.prompt : entry.id;
}

interface Props {
  categories: BrowserCategory[];
  activePolarity: PromptPolarity;
  onPolarityChange: (polarity: PromptPolarity) => void;
  selectedCategory: BrowserCategory | null;
  entries: BrowserEntry[];
  onOpenCategory: (category: BrowserCategory) => void;
  onAddEntry: (entry: BrowserEntry) => void;
  onAddLiteral: (text: string) => void;
}

export default function PromptEntryBrowser({ categories, activePolarity, onPolarityChange, selectedCategory, entries, onOpenCategory, onAddEntry, onAddLiteral }: Props) {
  const [query, setQuery] = useState("");
  const [literal, setLiteral] = useState("");
  const visibleEntries = useMemo(() => entries.filter((entry) => !entry.archived && `${entry.name_zh} ${entry.prompt}`.toLowerCase().includes(query.toLowerCase())), [entries, query]);

  return (
    <section className="h-fit rounded-xl border border-slate-700 bg-slate-900/70 p-5">
      <h2 className="text-lg font-semibold text-white">加入 Prompt</h2>
      <div className="mt-4 grid grid-cols-2 rounded-lg bg-slate-800 p-1" aria-label="Prompt 類型">
        {(["positive", "negative"] as const).map((polarity) => <button key={polarity} type="button" aria-pressed={activePolarity === polarity} onClick={() => onPolarityChange(polarity)} className={`rounded-md px-3 py-2 text-sm ${activePolarity === polarity ? "bg-emerald-600 text-white" : "text-slate-400"}`}>{polarity === "positive" ? "正向" : "負向"}</button>)}
      </div>
      <input aria-label="搜尋提示詞" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜尋中文或英文" className="mt-4 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" />
      <div className="mt-3 flex flex-wrap gap-2">{categories.filter((category) => !category.archived && category.polarity === activePolarity).map((category) => <button key={category.id} type="button" onClick={() => onOpenCategory(category)} className={`rounded-lg px-3 py-2 text-sm ${selectedCategory?.id === category.id ? "bg-emerald-700 text-white" : "bg-slate-800 text-slate-300"}`}>{category.name_zh}</button>)}</div>
      <ul className="mt-4 space-y-2">{visibleEntries.map((entry) => {
        const reason = suspectReason(entry.name_zh, entry.prompt);
        const displayName = promptEntryLabel(entry);
        return (
          <li key={entry.id} className="rounded-lg bg-slate-800 p-3">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1 font-medium text-white">
                  {reason && <span title="name_zh 可能沒有有意義的中文對照，建議編輯修正" aria-label={`${displayName} 中文對照可能未填好`} className="text-amber-400">⚠️</span>}
                  <span className="truncate">{displayName}</span>
                </p>
                <p className="mt-1 break-words text-xs text-slate-400">{entry.prompt}</p>
              </div>
              <div className="flex shrink-0 gap-1">
                <button type="button" aria-label={`加入 ${displayName}`} onClick={() => onAddEntry(entry)} className="rounded-md bg-emerald-600 px-2.5 py-1.5 text-sm text-white">加入</button>
              </div>
            </div>
          </li>
        );
      })}</ul>
      <div className="mt-5 border-t border-slate-700 pt-4">
        <label className="text-sm text-slate-400">自由文字<input aria-label="自由文字" value={literal} onChange={(event) => setLiteral(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" /></label>
        <button type="button" disabled={!literal.trim()} onClick={() => { onAddLiteral(literal); setLiteral(""); }} className="mt-2 w-full rounded-lg bg-slate-700 px-3 py-2 text-sm disabled:opacity-40">加入目前{activePolarity === "positive" ? "正向" : "負向"}</button>
      </div>
    </section>
  );
}
