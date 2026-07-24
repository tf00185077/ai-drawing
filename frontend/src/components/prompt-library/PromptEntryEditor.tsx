import { useState } from "react";

export interface EntryEditorValue {
  id: string;
  fields: {
    name_zh: string;
    description_zh: string;
    prompt: string;
    aliases: string[];
    keywords: string[];
    order: number;
  };
}

interface Props {
  mode: "create" | "edit";
  initial?: {
    id?: string;
    name_zh?: string;
    description_zh?: string;
    prompt?: string;
    aliases?: string[];
    keywords?: string[];
    order?: number;
  };
  submitting?: boolean;
  existingIds?: string[];
  onSubmit: (value: EntryEditorValue) => void;
  onCancel: () => void;
}

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function commaSeparated(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

const inputClass = "mt-1 w-full rounded border border-slate-600 bg-slate-900 p-2 text-sm text-white";

export default function PromptEntryEditor({ mode, initial, submitting, existingIds, onSubmit, onCancel }: Props) {
  const [id, setId] = useState(initial?.id ?? "");
  const [nameZh, setNameZh] = useState(initial?.name_zh ?? "");
  const [descriptionZh, setDescriptionZh] = useState(initial?.description_zh ?? "");
  const [prompt, setPrompt] = useState(initial?.prompt ?? "");
  const [aliases, setAliases] = useState((initial?.aliases ?? []).join(", "));
  const [keywords, setKeywords] = useState((initial?.keywords ?? []).join(", "));
  const [order, setOrder] = useState(String(initial?.order ?? 10));
  const [error, setError] = useState<string | null>(null);

  function submit() {
    const trimmedId = (mode === "create" ? id : initial?.id ?? "").trim();
    if (mode === "create" && !SLUG_PATTERN.test(trimmedId)) {
      setError("詞條 ID 只能使用小寫英文字母、數字與單一連字號，例如 detailed-eyes");
      return;
    }
    if (mode === "create" && existingIds?.includes(trimmedId)) {
      setError("此詞條 ID 已存在，請改用編輯或換一個 ID");
      return;
    }
    if (!nameZh.trim() || !descriptionZh.trim() || !prompt.trim()) {
      setError("請填寫中文名稱、說明與英文 prompt");
      return;
    }
    const orderNumber = Number(order);
    if (!Number.isInteger(orderNumber) || orderNumber < 0) {
      setError("排序必須是大於或等於 0 的整數");
      return;
    }
    setError(null);
    onSubmit({
      id: trimmedId,
      fields: {
        name_zh: nameZh.trim(),
        description_zh: descriptionZh.trim(),
        prompt: prompt.trim(),
        aliases: commaSeparated(aliases),
        keywords: commaSeparated(keywords),
        order: orderNumber,
      },
    });
  }

  return (
    <form className="mt-3 space-y-2 rounded-lg border border-slate-600 bg-slate-800/60 p-3" onSubmit={(event) => { event.preventDefault(); submit(); }} noValidate>
      {mode === "create" && (
        <label className="block text-xs text-slate-400">詞條 ID
          <input aria-label="詞條 ID" value={id} onChange={(e) => setId(e.target.value)} className={inputClass} />
        </label>
      )}
      <label className="block text-xs text-slate-400">中文名稱
        <input aria-label="詞條中文名稱" value={nameZh} onChange={(e) => setNameZh(e.target.value)} className={inputClass} />
      </label>
      <label className="block text-xs text-slate-400">說明
        <input aria-label="詞條說明" value={descriptionZh} onChange={(e) => setDescriptionZh(e.target.value)} className={inputClass} />
      </label>
      <label className="block text-xs text-slate-400">英文 prompt
        <input aria-label="詞條英文 prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} className={inputClass} />
      </label>
      <label className="block text-xs text-slate-400">別名（逗號分隔）
        <input aria-label="詞條別名" value={aliases} onChange={(e) => setAliases(e.target.value)} className={inputClass} />
      </label>
      <label className="block text-xs text-slate-400">關鍵字（逗號分隔）
        <input aria-label="詞條關鍵字" value={keywords} onChange={(e) => setKeywords(e.target.value)} className={inputClass} />
      </label>
      <label className="block text-xs text-slate-400">排序
        <input aria-label="詞條排序" type="number" min={0} value={order} onChange={(e) => setOrder(e.target.value)} className={inputClass} />
      </label>
      {error && <p role="alert" className="text-xs text-red-300">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={submitting} className="rounded bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-40">{submitting ? "儲存中…" : "儲存"}</button>
        <button type="button" disabled={submitting} onClick={onCancel} className="rounded bg-slate-700 px-3 py-1.5 text-sm text-slate-200 disabled:opacity-40">取消</button>
      </div>
    </form>
  );
}
