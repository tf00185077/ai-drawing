import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  PromptCategorySummary,
  PromptLibraryCatalogResponse,
  PromptLibraryWriteResponse,
  PromptPolarity,
} from "../types/api";
import PromptWorkbench from "../components/prompt-library/PromptWorkbench";

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function commaSeparated(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function apiErrorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const message = (detail as { message?: unknown }).message;
    const hint = (detail as { hint?: unknown }).hint;
    if (typeof message === "string" && typeof hint === "string") {
      return `${message}（${hint}）`;
    }
    if (typeof message === "string") return message;
  }
  return fallback;
}

export default function PromptLibrary() {
  const [catalog, setCatalog] = useState<PromptCategorySummary[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const [polarity, setPolarity] = useState<PromptPolarity>("positive");
  const [categoryId, setCategoryId] = useState("");
  const [nameZh, setNameZh] = useState("");
  const [descriptionZh, setDescriptionZh] = useState("");
  const [aliases, setAliases] = useState("");
  const [keywords, setKeywords] = useState("");
  const [order, setOrder] = useState("10");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState<PromptCategorySummary | null>(null);

  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const response = await fetch("/api/prompt-library/catalog");
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(apiErrorMessage(data, `分類清單載入失敗: ${response.status}`));
      }
      setCatalog((data as PromptLibraryCatalogResponse).categories ?? []);
    } catch (error) {
      setCatalogError(error instanceof Error ? error.message : "分類清單載入失敗");
    } finally {
      setCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  const visibleCategories = useMemo(
    () => catalog.filter((category) => category.polarity === polarity && !category.archived),
    [catalog, polarity],
  );

  const createCategory = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const id = categoryId.trim();
      const name = nameZh.trim();
      const description = descriptionZh.trim();
      const orderNumber = Number(order);

      setSubmitError(null);
      setSuccess(null);

      if (!SLUG_PATTERN.test(id)) {
        setSubmitError("分類 ID 只能使用小寫英文字母、數字與單一連字號，例如 street-scenes");
        return;
      }
      if (!name || !description) {
        setSubmitError("請填寫中文名稱與分類說明");
        return;
      }
      if (!Number.isInteger(orderNumber) || orderNumber < 0) {
        setSubmitError("排序必須是大於或等於 0 的整數");
        return;
      }

      setSubmitting(true);
      try {
        const response = await fetch(
          `/api/prompt-library/categories/${polarity}/${encodeURIComponent(id)}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name_zh: name,
              description_zh: description,
              aliases: commaSeparated(aliases),
              keywords: commaSeparated(keywords),
              order: orderNumber,
              expected_revision: 0,
            }),
          },
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(apiErrorMessage(data, `建立分類失敗: ${response.status}`));
        }

        const created = (data as PromptLibraryWriteResponse).category?.category;
        if (!created) throw new Error("伺服器未回傳新分類資料");
        setSuccess(created);
        setCategoryId("");
        setNameZh("");
        setDescriptionZh("");
        setAliases("");
        setKeywords("");
        await loadCatalog();
      } catch (error) {
        setSubmitError(error instanceof Error ? error.message : "建立分類失敗");
      } finally {
        setSubmitting(false);
      }
    },
    [aliases, categoryId, descriptionZh, keywords, loadCatalog, nameZh, order, polarity],
  );

  return (
    <div className="max-w-6xl">
      <h1 className="text-2xl font-bold text-white">Prompt 分類管理</h1>
      <p className="mt-1 text-slate-400">
        建立可重用的正向或負向 Prompt 分類。分類建立後會立即寫入專案 Prompt Library。
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(360px,1fr)]">
        <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">現有分類</h2>
              <p className="text-sm text-slate-500">切換類型可確認ID是否已被使用。</p>
            </div>
            <PolarityTabs value={polarity} onChange={setPolarity} />
          </div>

          {catalogLoading ? (
            <p className="mt-5 text-slate-500">載入分類中…</p>
          ) : catalogError ? (
            <div className="mt-5 rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-300">
              <p>{catalogError}</p>
              <button type="button" onClick={loadCatalog} className="mt-2 text-red-200 underline">
                重新載入
              </button>
            </div>
          ) : (
            <div className="mt-5">
              <p className="mb-3 text-sm text-slate-400">
                {polarity === "positive" ? "正向" : "負向"}分類：{visibleCategories.length} 個
              </p>
              <ul className="grid gap-2 sm:grid-cols-2">
                {visibleCategories.map((category) => (
                  <li key={`${category.polarity}-${category.id}`} className="rounded-lg border border-slate-700 bg-slate-800/60 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-medium text-slate-100">{category.name_zh}</span>
                      <span className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-300">{category.entry_count}</span>
                    </div>
                    <code className="mt-1 block text-xs text-emerald-400">{category.id}</code>
                    <p className="mt-2 text-sm text-slate-400">{category.description_zh}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
          <h2 className="text-lg font-semibold text-white">新增分類</h2>
          <p className="mt-1 text-sm text-slate-500">新分類建立時revision固定從0開始。</p>

          <form className="mt-5 space-y-4" onSubmit={createCategory} noValidate>
            <div>
              <span className="mb-2 block text-sm text-slate-400">分類類型</span>
              <PolarityTabs value={polarity} onChange={setPolarity} />
            </div>
            <TextField
              id="category-id"
              label="分類 ID"
              value={categoryId}
              onChange={setCategoryId}
              placeholder="例如 street-scenes"
              hint="僅限小寫英文字母、數字及連字號；建立後用於API與檔名。"
              required
            />
            <TextField
              id="category-name"
              label="中文名稱"
              value={nameZh}
              onChange={setNameZh}
              placeholder="例如 街景"
              required
            />
            <TextField
              id="category-description"
              label="分類說明"
              value={descriptionZh}
              onChange={setDescriptionZh}
              placeholder="例如 都市、商店街與道路場景提示詞"
              textarea
              required
            />
            <TextField
              id="category-aliases"
              label="別名"
              value={aliases}
              onChange={setAliases}
              placeholder="例如 urban scene, street scene"
              hint="多個值以逗號分隔。"
            />
            <TextField
              id="category-keywords"
              label="搜尋關鍵字"
              value={keywords}
              onChange={setKeywords}
              placeholder="例如 街道, 城市, 商店街"
              hint="多個值以逗號分隔。"
            />
            <TextField
              id="category-order"
              label="排序"
              value={order}
              onChange={setOrder}
              type="number"
              min={0}
              required
            />

            {submitError && (
              <div role="alert" className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-300">
                {submitError}
              </div>
            )}
            {success && (
              <div role="status" className="rounded-lg border border-emerald-500/50 bg-emerald-500/10 p-3 text-sm text-emerald-300">
                已建立{success.polarity === "positive" ? "正向" : "負向"}分類「{success.name_zh}」（{success.id}）
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-slate-600"
            >
              {submitting ? "建立中…" : "建立分類"}
            </button>
          </form>
        </section>
      </div>
      <PromptWorkbench />
    </div>
  );
}

function PolarityTabs({
  value,
  onChange,
}: {
  value: PromptPolarity;
  onChange: (value: PromptPolarity) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-slate-700 bg-slate-800 p-1" aria-label="分類類型">
      {(["positive", "negative"] as const).map((item) => (
        <button
          key={item}
          type="button"
          aria-pressed={value === item}
          onClick={() => onChange(item)}
          className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
            value === item ? "bg-emerald-600 text-white" : "text-slate-400 hover:text-white"
          }`}
        >
          {item === "positive" ? "正向" : "負向"}
        </button>
      ))}
    </div>
  );
}

function TextField({
  id,
  label,
  value,
  onChange,
  placeholder,
  hint,
  textarea = false,
  type = "text",
  min,
  required = false,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  hint?: string;
  textarea?: boolean;
  type?: string;
  min?: number;
  required?: boolean;
}) {
  const className =
    "w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none";
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm text-slate-400">
        {label}
        {required && <span className="ml-1 text-amber-400">*</span>}
      </label>
      {textarea ? (
        <textarea
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className={`${className} min-h-24 resize-y`}
          required={required}
        />
      ) : (
        <input
          id={id}
          type={type}
          min={min}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className={className}
          required={required}
        />
      )}
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
