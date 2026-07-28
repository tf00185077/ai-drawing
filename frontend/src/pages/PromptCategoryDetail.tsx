import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import PromptEntryEditor, { type EntryEditorValue } from "../components/prompt-library/PromptEntryEditor";
import {
  archivePromptResource,
  getPromptCatalog,
  getPromptCategory,
  putPromptCategory,
  putPromptEntry,
  restorePromptResource,
} from "../components/prompt-library/promptLibraryApi";
import { ancestorChain, descendantIds, orderedCategoryRows } from "../components/prompt-library/categoryTree";
import type { PromptCategory, PromptCategorySummary, PromptEntry, PromptPolarity, PromptVersionedCategory } from "../types/api";

function isPromptPolarity(value: string | undefined): value is PromptPolarity {
  return value === "positive" || value === "negative";
}
function commaSeparated(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}
type CategoryDraft = Pick<PromptCategory, "name_zh" | "description_zh"> & { aliases: string; keywords: string; order: string; parentId: string };
type OpenEditor = { mode: "create" } | { mode: "edit"; entry: PromptEntry };
const fieldClass = "mt-1 w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-slate-200 disabled:opacity-50";
const actionClass = "rounded-lg px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-40";

function draftFrom(category: PromptCategory): CategoryDraft {
  return {
    name_zh: category.name_zh,
    description_zh: category.description_zh,
    aliases: category.aliases.join(", "),
    keywords: category.keywords.join(", "),
    order: String(category.order),
    parentId: category.parent_id ?? "",
  };
}

export default function PromptCategoryDetail() {
  const { polarity, categoryId } = useParams();
  const validPolarity = isPromptPolarity(polarity);
  const [category, setCategory] = useState<PromptVersionedCategory | null>(null);
  const [categoryDraft, setCategoryDraft] = useState<CategoryDraft | null>(null);
  const [loading, setLoading] = useState(validPolarity);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [retryGeneration, setRetryGeneration] = useState(0);
  const [entryFilter, setEntryFilter] = useState<"active" | "archived">("active");
  const [editor, setEditor] = useState<OpenEditor | null>(null);
  const [categories, setCategories] = useState<PromptCategorySummary[]>([]);
  const requestGeneration = useRef(0);
  const operationGeneration = useRef(0);

  useEffect(() => {
    let active = true;
    void getPromptCatalog().then((data) => { if (active) setCategories(data.categories ?? []); }).catch(() => {});
    return () => { active = false; };
  }, [retryGeneration]);

  useEffect(() => {
    operationGeneration.current += 1;
    const requestId = ++requestGeneration.current;
    setCategory(null);
    setCategoryDraft(null);
    setError(null);
    setNotice(null);
    setEditor(null);
    setBusy(false);
    if (!validPolarity || !categoryId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    void getPromptCategory(polarity, categoryId)
      .then((loadedCategory) => {
        if (requestGeneration.current === requestId) {
          setCategory(loadedCategory);
          setCategoryDraft(draftFrom(loadedCategory.category));
        }
      })
      .catch((loadError: unknown) => {
        if (requestGeneration.current === requestId) setError(messageOf(loadError, "分類讀取失敗，請稍後重試"));
      })
      .finally(() => {
        if (requestGeneration.current === requestId) setLoading(false);
      });
    return () => {
      if (requestGeneration.current === requestId) requestGeneration.current += 1;
    };
  }, [categoryId, polarity, retryGeneration, validPolarity]);

  async function mutate(
    operation: () => Promise<{ affected_combinations: string[] }>,
    options?: { closeEditor?: boolean; showAffectedCombinations?: boolean },
  ) {
    if (busy) return;
    const operationId = ++operationGeneration.current;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const response = await operation();
      if (operationGeneration.current !== operationId) return;
      const reloadId = ++requestGeneration.current;
      setLoading(true);
      const loadedCategory = await getPromptCategory(
        polarity as PromptPolarity,
        categoryId as string,
      );
      if (operationGeneration.current === operationId && requestGeneration.current === reloadId) {
        setCategory(loadedCategory);
        setCategoryDraft(draftFrom(loadedCategory.category));
        setLoading(false);
        if (options?.closeEditor) setEditor(null);
        setNotice(options?.showAffectedCombinations && response.affected_combinations.length > 0
          ? `已同步更新 ${response.affected_combinations.length} 個組合：${response.affected_combinations.join("、")}`
          : null);
        void getPromptCatalog()
          .then((data) => {
            if (operationGeneration.current === operationId && requestGeneration.current === reloadId) {
              setCategories(data.categories ?? []);
            }
          })
          .catch(() => {});
      }
    } catch (mutationError: unknown) {
      if (operationGeneration.current === operationId) {
        setError(messageOf(mutationError, "操作失敗，請確認資料後重試"));
        setLoading(false);
      }
    } finally {
      if (operationGeneration.current === operationId) setBusy(false);
    }
  }

  if (!validPolarity || !categoryId) {
    return <section className="max-w-4xl"><div role="alert" className="rounded-xl border border-red-500/50 bg-red-500/10 p-5 text-red-200"><h1 className="text-xl font-semibold">分類類型無效</h1><p className="mt-2 text-sm">網址中的分類類型必須是 positive 或 negative，請返回分類管理重新選擇。</p><BackLink /></div></section>;
  }
  if (loading && !category) return <p role="status" className="text-slate-400">載入分類中…</p>;
  if (error && !category) {
    return <section className="max-w-4xl"><div role="alert" className="rounded-xl border border-red-500/50 bg-red-500/10 p-5 text-red-200"><h1 className="text-xl font-semibold">無法載入分類</h1><p className="mt-2 text-sm">{error}</p><button type="button" onClick={() => setRetryGeneration((value) => value + 1)} className="mt-4 rounded-lg bg-red-700 px-3 py-2 text-sm text-white">重新載入</button></div><BackLink /></section>;
  }
  if (!category || !categoryDraft) return null;

  const currentPolarity: PromptPolarity = polarity;
  const currentCategoryId: string = categoryId;
  const { category: details, etag } = category;
  const token = { expected_revision: details.revision, expected_etag: etag };
  const entries = details.entries.filter((entry) => entry.archived === (entryFilter === "archived"));
  const samePolarityCategories = categories.filter((c) => c.polarity === currentPolarity);
  const excludedParentIds = descendantIds(samePolarityCategories, currentCategoryId);

  function saveCategory() {
    const order = Number(categoryDraft!.order);
    if (!categoryDraft!.name_zh.trim() || !categoryDraft!.description_zh.trim()) {
      setError("請填寫分類中文名稱與說明");
      return;
    }
    if (categoryDraft!.order.trim() === "" || !Number.isInteger(order) || order < 0) {
      setError("分類排序必須是大於或等於 0 的整數");
      return;
    }
    void mutate(() => putPromptCategory(currentPolarity, currentCategoryId, {
      name_zh: categoryDraft!.name_zh.trim(),
      description_zh: categoryDraft!.description_zh.trim(),
      aliases: commaSeparated(categoryDraft!.aliases),
      keywords: commaSeparated(categoryDraft!.keywords),
      order,
      parent_id: categoryDraft!.parentId ? categoryDraft!.parentId : null,
      ...token,
    }));
  }
  function saveEntry(value: EntryEditorValue) {
    void mutate(() => putPromptEntry(currentPolarity, currentCategoryId, value.id, { ...value.fields, ...token }), {
      closeEditor: true,
      showAffectedCombinations: true,
    });
  }
  function archiveCategory() {
    if (!window.confirm(`確定要封存分類「${details.name_zh}」嗎？`)) return;
    void mutate(() => archivePromptResource({ resource_type: "category", resource_id: currentCategoryId, polarity: currentPolarity, ...token }));
  }
  function restoreCategory() {
    void mutate(() => restorePromptResource({ resource_type: "category", resource_id: currentCategoryId, polarity: currentPolarity, ...token }));
  }
  function archiveEntry(entry: PromptEntry) {
    if (!window.confirm(`確定要封存詞條「${entry.name_zh}」嗎？`)) return;
    void mutate(() => archivePromptResource({ resource_type: "entry", resource_id: entry.id, category_id: currentCategoryId, polarity: currentPolarity, ...token }));
  }
  function restoreEntry(entry: PromptEntry) {
    if (details.archived) return;
    void mutate(() => restorePromptResource({ resource_type: "entry", resource_id: entry.id, category_id: currentCategoryId, polarity: currentPolarity, ...token }));
  }

  return (
    <div className="max-w-4xl">
      <BackLink />
      {error && <div role="alert" className="mt-4 rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-red-200">{error}</div>}
      {notice && <div role="status" className="mt-4 rounded-lg border border-emerald-500/50 bg-emerald-500/10 p-3 text-emerald-200">{notice}</div>}
      <header className="mt-4 rounded-xl border border-slate-700 bg-slate-900/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm text-emerald-400">{details.polarity === "positive" ? "正向分類" : "負向分類"}</p><h1 className="mt-1 text-2xl font-bold text-white">{details.name_zh}</h1></div><div className="flex gap-2 text-xs"><span className="rounded bg-slate-700 px-2 py-1 text-slate-200">Revision {details.revision}</span><span className={`rounded px-2 py-1 ${details.archived ? "bg-amber-700 text-amber-100" : "bg-emerald-700 text-emerald-100"}`}>{details.archived ? "已封存" : "使用中"}</span></div></div>
        {categories.length > 0 && (
          <nav aria-label="分類路徑" className="mt-2 text-xs text-slate-400">
            {ancestorChain(categories.filter((c) => c.polarity === details.polarity), details.id)
              .map((node) => node.name_zh)
              .join(" › ")}
          </nav>
        )}
      </header>

      <section aria-label="分類資料編輯" className="mt-5 rounded-xl border border-slate-700 bg-slate-900/60 p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="分類 ID"><input aria-label="分類 ID" readOnly value={details.id} className={fieldClass} /></Field>
          <Field label="父分類">
            <select
              aria-label="父分類"
              disabled={busy}
              value={categoryDraft.parentId}
              onChange={(event) => setCategoryDraft({ ...categoryDraft, parentId: event.target.value })}
              className={fieldClass}
            >
              <option value="">（無，作為頂層）</option>
              {orderedCategoryRows(
                categories.filter(
                  (item) =>
                    item.polarity === currentPolarity &&
                    !item.archived &&
                    item.id !== currentCategoryId &&
                    !excludedParentIds.has(item.id),
                ),
              ).map(({ category: option, depth }) => (
                <option key={option.id} value={option.id}>
                  {`${"　".repeat(depth)}${option.name_zh}`}
                </option>
              ))}
            </select>
          </Field>
          <Field label="中文名稱"><input aria-label="分類中文名稱" disabled={busy} value={categoryDraft.name_zh} onChange={(event) => setCategoryDraft({ ...categoryDraft, name_zh: event.target.value })} className={fieldClass} /></Field>
          <Field label="說明"><input aria-label="分類說明" disabled={busy} value={categoryDraft.description_zh} onChange={(event) => setCategoryDraft({ ...categoryDraft, description_zh: event.target.value })} className={fieldClass} /></Field>
          <Field label="別名（逗號分隔）"><input aria-label="分類別名" disabled={busy} value={categoryDraft.aliases} onChange={(event) => setCategoryDraft({ ...categoryDraft, aliases: event.target.value })} className={fieldClass} /></Field>
          <Field label="關鍵字（逗號分隔）"><input aria-label="分類關鍵字" disabled={busy} value={categoryDraft.keywords} onChange={(event) => setCategoryDraft({ ...categoryDraft, keywords: event.target.value })} className={fieldClass} /></Field>
          <Field label="排序"><input aria-label="分類排序" type="number" min={0} disabled={busy} value={categoryDraft.order} onChange={(event) => setCategoryDraft({ ...categoryDraft, order: event.target.value })} className={fieldClass} /></Field>
        </div>
        <div className="mt-4 flex gap-2"><button type="button" disabled={busy} onClick={saveCategory} className={`${actionClass} bg-emerald-600`}>{busy ? "處理中…" : "儲存分類"}</button>{details.archived ? <button type="button" disabled={busy} onClick={restoreCategory} className={`${actionClass} bg-sky-600`}>恢復分類</button> : <button type="button" disabled={busy} onClick={archiveCategory} className={`${actionClass} bg-amber-700`}>封存分類</button>}</div>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2"><Metadata label="ETag" value={etag} /><Metadata label="項目數" value={String(details.entries.length)} /></dl>
      </section>

      <section aria-label="詞條管理" className="mt-5 rounded-xl border border-slate-700 bg-slate-900/60 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold text-white">詞條管理</h2><button type="button" disabled={busy || editor !== null} onClick={() => setEditor({ mode: "create" })} className={`${actionClass} bg-emerald-600`}>新增詞條</button></div>
        <div className="mt-4 flex gap-2"><FilterButton active={entryFilter === "active"} disabled={busy} onClick={() => setEntryFilter("active")}>使用中詞條</FilterButton><FilterButton active={entryFilter === "archived"} disabled={busy} onClick={() => setEntryFilter("archived")}>已封存詞條</FilterButton></div>
        {editor?.mode === "create" && <PromptEntryEditor key="create" mode="create" submitting={busy} existingIds={details.entries.map((entry) => entry.id)} onSubmit={saveEntry} onCancel={() => setEditor(null)} />}
        <div className="mt-4 space-y-3">
          {entries.map((entry) => <article key={entry.id} className="rounded-lg border border-slate-700 bg-slate-800/50 p-4"><div className="flex flex-wrap justify-between gap-3"><div><h3 className="font-semibold text-white">{entry.name_zh}</h3><p className="text-xs text-slate-500">{entry.id} · Revision {entry.revision}</p><p className="mt-2 text-sm text-slate-300">{entry.prompt}</p></div><div className="flex items-start gap-2">{!entry.archived && <button type="button" aria-label={`編輯 ${entry.id}`} disabled={busy || editor !== null} onClick={() => setEditor({ mode: "edit", entry })} className={`${actionClass} bg-sky-700`}>編輯</button>}{entry.archived ? <button type="button" disabled={busy || details.archived} onClick={() => restoreEntry(entry)} className={`${actionClass} bg-emerald-700`}>恢復</button> : <button type="button" disabled={busy} onClick={() => archiveEntry(entry)} className={`${actionClass} bg-amber-700`}>封存</button>}</div></div>{entry.archived && details.archived && <p className="mt-2 text-sm text-amber-300">請先恢復分類</p>}{editor?.mode === "edit" && editor.entry.id === entry.id && <PromptEntryEditor key={entry.id} mode="edit" initial={entry} submitting={busy} onSubmit={saveEntry} onCancel={() => setEditor(null)} />}</article>)}
          {entries.length === 0 && <p className="text-sm text-slate-400">此篩選條件下沒有詞條。</p>}
        </div>
      </section>
    </div>
  );
}

function messageOf(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}
function BackLink() {
  return <Link to="/prompt-library/categories" className="mt-4 inline-block text-sm text-emerald-400 hover:underline">返回分類管理</Link>;
}
function Metadata({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value}</dd></div>;
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="text-sm text-slate-400">{label}{children}</label>;
}
function FilterButton({ active, disabled, onClick, children }: { active: boolean; disabled: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" disabled={disabled} onClick={onClick} className={`rounded px-3 py-1.5 text-sm disabled:opacity-40 ${active ? "bg-emerald-700 text-white" : "bg-slate-700 text-slate-300"}`}>{children}</button>;
}
