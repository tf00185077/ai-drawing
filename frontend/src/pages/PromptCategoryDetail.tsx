import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getPromptCategory } from "../components/prompt-library/promptLibraryApi";
import type { PromptPolarity, PromptVersionedCategory } from "../types/api";

function isPromptPolarity(value: string | undefined): value is PromptPolarity {
  return value === "positive" || value === "negative";
}

export default function PromptCategoryDetail() {
  const { polarity, categoryId } = useParams();
  const validPolarity = isPromptPolarity(polarity);
  const [category, setCategory] = useState<PromptVersionedCategory | null>(null);
  const [loading, setLoading] = useState(validPolarity);
  const [error, setError] = useState<string | null>(null);

  const loadCategory = useCallback(async () => {
    if (!validPolarity || !categoryId) return;
    setLoading(true);
    setError(null);
    try {
      setCategory(await getPromptCategory(polarity, categoryId));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "分類讀取失敗，請稍後重試");
    } finally {
      setLoading(false);
    }
  }, [categoryId, polarity, validPolarity]);

  useEffect(() => { void loadCategory(); }, [loadCategory]);

  if (!validPolarity || !categoryId) {
    return (
      <section className="max-w-4xl">
        <div role="alert" className="rounded-xl border border-red-500/50 bg-red-500/10 p-5 text-red-200">
          <h1 className="text-xl font-semibold">分類類型無效</h1>
          <p className="mt-2 text-sm">網址中的分類類型必須是 positive 或 negative，請返回分類管理重新選擇。</p>
          <BackLink />
        </div>
      </section>
    );
  }

  if (loading && !category) return <p role="status" className="text-slate-400">載入分類中…</p>;

  if (error && !category) {
    return (
      <section className="max-w-4xl">
        <div role="alert" className="rounded-xl border border-red-500/50 bg-red-500/10 p-5 text-red-200">
          <h1 className="text-xl font-semibold">無法載入分類</h1>
          <p className="mt-2 text-sm">{error}</p>
          <button type="button" onClick={loadCategory} className="mt-4 rounded-lg bg-red-700 px-3 py-2 text-sm text-white hover:bg-red-600">重新載入</button>
        </div>
        <BackLink />
      </section>
    );
  }

  if (!category) return null;
  const { category: details, etag } = category;
  return (
    <div className="max-w-4xl">
      <BackLink />
      {error && <div role="alert" className="mt-4 rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-red-200">{error}</div>}
      <header className="mt-4 rounded-xl border border-slate-700 bg-slate-900/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-emerald-400">{details.polarity === "positive" ? "正向分類" : "負向分類"}</p>
            <h1 className="mt-1 text-2xl font-bold text-white">{details.name_zh}</h1>
          </div>
          <div className="flex gap-2 text-xs">
            <span className="rounded bg-slate-700 px-2 py-1 text-slate-200">Revision {details.revision}</span>
            <span className={`rounded px-2 py-1 ${details.archived ? "bg-amber-700 text-amber-100" : "bg-emerald-700 text-emerald-100"}`}>
              {details.archived ? "已封存" : "使用中"}
            </span>
          </div>
        </div>
        <p className="mt-4 text-slate-300">{details.description_zh}</p>
      </header>

      <section aria-label="分類唯讀資料" className="mt-5 grid gap-4 rounded-xl border border-slate-700 bg-slate-900/60 p-5 sm:grid-cols-2">
        <label className="text-sm text-slate-400">
          分類 ID
          <input aria-label="分類 ID" readOnly value={details.id} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-slate-200" />
        </label>
        <Metadata label="ETag" value={etag} />
        <Metadata label="排序" value={String(details.order)} />
        <Metadata label="項目數" value={String(details.entries.length)} />
        <Metadata label="別名" value={details.aliases.join("、") || "無"} />
        <Metadata label="關鍵字" value={details.keywords.join("、") || "無"} />
      </section>
    </div>
  );
}

function BackLink() {
  return <Link to="/prompt-library/categories" className="mt-4 inline-block text-sm text-emerald-400 hover:underline">返回分類管理</Link>;
}

function Metadata({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-sm text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value}</dd></div>;
}
