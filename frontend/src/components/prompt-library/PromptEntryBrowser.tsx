import { useEffect, useMemo, useState } from "react";
import type { PromptPolarity } from "../../types/api";
import { ancestorChain, childCategories } from "./categoryTree";
import { suspectReason } from "./suspectChinese";

export interface BrowserCategory { id: string; polarity: PromptPolarity; name_zh: string; revision: number; etag: string; archived: boolean; parent_id?: string | null; order: number }
export interface BrowserEntry { id: string; name_zh: string; prompt: string; description_zh: string; aliases: string[]; keywords: string[]; order: number; revision: number; archived: boolean }

export function promptEntryLabel(entry: Pick<BrowserEntry, "id" | "name_zh" | "prompt">): string {
  return entry.name_zh?.trim() || entry.prompt?.trim() || entry.id;
}
export function promptEntryContent(entry: Pick<BrowserEntry, "id" | "prompt">): string {
  return entry.prompt?.trim() ? entry.prompt : entry.id;
}

const PAGE_SIZE = 30;

interface Props {
  categories: BrowserCategory[];
  activePolarity: PromptPolarity;
  onPolarityChange: (polarity: PromptPolarity) => void;
  selectedCategory: BrowserCategory | null;
  entries: BrowserEntry[];
  allEntries: { category: BrowserCategory; entry: BrowserEntry }[];
  onOpenCategory: (category: BrowserCategory) => void;
  onAddEntry: (category: BrowserCategory, entry: BrowserEntry) => void;
  onAddLiteral: (text: string) => void;
}

function EntryChip({ category, entry, pathLabel, onAdd }: { category: BrowserCategory; entry: BrowserEntry; pathLabel?: string; onAdd: (category: BrowserCategory, entry: BrowserEntry) => void }) {
  const reason = suspectReason(entry.name_zh, entry.prompt);
  const displayName = promptEntryLabel(entry);
  return (
    <button
      type="button"
      title={entry.prompt}
      aria-label={`加入 ${displayName}`}
      onClick={() => onAdd(category, entry)}
      className="inline-flex max-w-[16rem] items-center gap-1 rounded-full border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:border-emerald-500 hover:bg-slate-700"
    >
      {reason && <span title="name_zh 可能沒有有意義的中文對照，建議編輯修正" aria-label={`${displayName} 中文對照可能未填好`} className="text-amber-400">⚠️</span>}
      {pathLabel && <span className="text-xs text-slate-500">{pathLabel}·</span>}
      <span className="truncate">{displayName}</span>
    </button>
  );
}

export default function PromptEntryBrowser({ categories, activePolarity, onPolarityChange, selectedCategory, entries, allEntries, onOpenCategory, onAddEntry, onAddLiteral }: Props) {
  const [query, setQuery] = useState("");
  const [literal, setLiteral] = useState("");
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const polarityCategories = useMemo(
    () => categories.filter((category) => !category.archived && category.polarity === activePolarity),
    [categories, activePolarity],
  );

  const trimmedQuery = query.trim().toLowerCase();
  const searching = trimmedQuery !== "";

  // Cross-tree search results (whole polarity), else the current category's entries.
  const searchResults = useMemo(() => {
    if (!searching) return [];
    return allEntries.filter(
      ({ category, entry }) =>
        category.polarity === activePolarity &&
        !category.archived &&
        !entry.archived &&
        `${entry.name_zh} ${entry.prompt}`.toLowerCase().includes(trimmedQuery),
    );
  }, [allEntries, activePolarity, searching, trimmedQuery]);

  const currentCategory = useMemo(
    () => polarityCategories.find((category) => category.id === currentId) ?? null,
    [polarityCategories, currentId],
  );
  const folders = useMemo(() => childCategories(polarityCategories, currentId), [polarityCategories, currentId]);
  const breadcrumb = useMemo(
    () => (currentId ? ancestorChain(polarityCategories, currentId) : []),
    [polarityCategories, currentId],
  );
  const currentEntries = useMemo(
    () => (currentCategory ? entries.filter((entry) => !entry.archived) : []),
    [entries, currentCategory],
  );

  const listForPaging = searching ? searchResults : currentEntries;
  useEffect(() => { setPage(0); }, [trimmedQuery, currentId, activePolarity]);
  const pageCount = Math.max(1, Math.ceil(listForPaging.length / PAGE_SIZE));
  useEffect(() => { if (page >= pageCount) setPage(pageCount - 1); }, [page, pageCount]);
  const pageStart = page * PAGE_SIZE;

  const jumpTo = (category: BrowserCategory) => {
    setCurrentId(category.id);
    onOpenCategory(category);
  };
  const pathLabelOf = (category: BrowserCategory) =>
    ancestorChain(polarityCategories, category.id).map((node) => node.name_zh).join(" › ");

  const changePolarity = (polarity: PromptPolarity) => {
    setCurrentId(null);
    onPolarityChange(polarity);
  };

  return (
    <section className="h-fit rounded-xl border border-slate-700 bg-slate-900/70 p-5">
      <h2 className="text-lg font-semibold text-white">加入 Prompt</h2>
      <div className="mt-4 grid grid-cols-2 rounded-lg bg-slate-800 p-1" aria-label="Prompt 類型">
        {(["positive", "negative"] as const).map((polarity) => <button key={polarity} type="button" aria-pressed={activePolarity === polarity} onClick={() => changePolarity(polarity)} className={`rounded-md px-3 py-2 text-sm ${activePolarity === polarity ? "bg-emerald-600 text-white" : "text-slate-400"}`}>{polarity === "positive" ? "正向" : "負向"}</button>)}
      </div>
      <input aria-label="搜尋提示詞" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜尋整棵樹（中文或英文）" className="mt-4 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" />

      {!searching && (
        <nav aria-label="分類路徑" className="mt-3 flex flex-wrap items-center gap-1 text-sm">
          <button type="button" onClick={() => setCurrentId(null)} className={`rounded px-2 py-1 ${currentId === null ? "text-white" : "text-emerald-400 hover:underline"}`}>頂層</button>
          {breadcrumb.map((node) => (
            <span key={node.id} className="flex items-center gap-1">
              <span className="text-slate-600">›</span>
              <button type="button" onClick={() => jumpTo(node)} className={`rounded px-2 py-1 ${node.id === currentId ? "text-white" : "text-emerald-400 hover:underline"}`}>{node.name_zh}</button>
            </span>
          ))}
        </nav>
      )}

      {!searching && folders.length > 0 && (
        <div data-testid="prompt-folder-chips" className="mt-3 flex flex-wrap gap-2">
          {folders.map((folder) => (
            <button key={folder.id} type="button" onClick={() => jumpTo(folder)} className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-300 hover:bg-slate-700">
              📁 {folder.name_zh}
            </button>
          ))}
        </div>
      )}

      <div data-testid="prompt-entry-chips" className="mt-4 flex flex-wrap gap-2">
        {searching && searchResults.length === 0 && <p className="text-sm text-slate-500">沒有符合的詞條</p>}
        {!searching && currentCategory === null && folders.length === 0 && <p className="text-sm text-slate-500">尚無分類</p>}
        {!searching && currentCategory !== null && currentEntries.length === 0 && folders.length === 0 && <p className="text-sm text-slate-500">此分類尚無詞條</p>}
        {searching
          ? searchResults.slice(pageStart, pageStart + PAGE_SIZE).map(({ category, entry }) => (
              <EntryChip key={`${category.id}/${entry.id}`} category={category} entry={entry} pathLabel={pathLabelOf(category)} onAdd={onAddEntry} />
            ))
          : currentCategory !== null
            ? currentEntries.slice(pageStart, pageStart + PAGE_SIZE).map((entry) => (
                <EntryChip key={entry.id} category={currentCategory} entry={entry} onAdd={onAddEntry} />
              ))
            : null}
      </div>
      {pageCount > 1 && (
        <nav aria-label="詞條分頁" className="mt-3 flex items-center justify-center gap-3">
          <button type="button" aria-label="上一頁" disabled={page === 0} onClick={() => setPage((value) => value - 1)} className="rounded-md bg-slate-700 px-3 py-1.5 text-xs disabled:opacity-40">上一頁</button>
          <span className="text-xs text-slate-400">{page + 1} / {pageCount}</span>
          <button type="button" aria-label="下一頁" disabled={page === pageCount - 1} onClick={() => setPage((value) => value + 1)} className="rounded-md bg-slate-700 px-3 py-1.5 text-xs disabled:opacity-40">下一頁</button>
        </nav>
      )}

      <div className="mt-5 border-t border-slate-700 pt-4">
        <label className="text-sm text-slate-400">自由文字<input aria-label="自由文字" value={literal} onChange={(event) => setLiteral(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" /></label>
        <button type="button" disabled={!literal.trim()} onClick={() => { onAddLiteral(literal); setLiteral(""); }} className="mt-2 w-full rounded-lg bg-slate-700 px-3 py-2 text-sm disabled:opacity-40">加入目前{activePolarity === "positive" ? "正向" : "負向"}</button>
      </div>
    </section>
  );
}
