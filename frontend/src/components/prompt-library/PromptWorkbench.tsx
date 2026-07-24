import { useEffect, useState } from "react";
import type { PromptPolarity } from "../../types/api";
import { appendFragment, emptyComposition, moveFragment, reconcileComposedText, removeFragment, serializeFragments, setFragmentText, setFragmentWeight, type CompositionState } from "./compositionState";
import GenerationPanel, { type GenerationForm } from "./GenerationPanel";
import PromptEntryBrowser, { type BrowserCategory, type BrowserEntry } from "./PromptEntryBrowser";
import type { EntryEditorValue } from "./PromptEntryEditor";
import PromptOverview from "./PromptOverview";

interface CombinationVersion {
  revision: number;
  etag?: string;
}

const COMBINATION_ID_PATTERN = /^[\p{L}\p{N}]+(?:-[\p{L}\p{N}]+)*$/u;

function responseErrorMessage(data: unknown, status: number): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string" && message) return message;
  }
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      const location = Array.isArray((item as { loc?: unknown }).loc)
        ? ((item as { loc: unknown[] }).loc).filter((part) => part !== "body").join(".")
        : "request";
      const message = (item as { msg?: unknown }).msg;
      return typeof message === "string" ? [`${location}：${message}`] : [];
    });
    if (messages.length) return messages.join("；");
  }
  return `HTTP ${status}`;
}

async function jsonFetch(url: string) {
  const response = await fetch(url);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(responseErrorMessage(data, response.status));
  return data;
}

export default function PromptWorkbench() {
  const [categories, setCategories] = useState<BrowserCategory[]>([]);
  const [forms, setForms] = useState<GenerationForm[]>([]);
  const [activePolarity, setActivePolarity] = useState<PromptPolarity>("positive");
  const [category, setCategory] = useState<BrowserCategory | null>(null);
  const [entries, setEntries] = useState<BrowserEntry[]>([]);
  const [positive, setPositive] = useState<CompositionState>(emptyComposition);
  const [negative, setNegative] = useState<CompositionState>(emptyComposition);
  const [error, setError] = useState("");
  const [sequence, setSequence] = useState(0);
  const [saveId, setSaveId] = useState("");
  const [saveStatus, setSaveStatus] = useState("");
  const [combinationVersions, setCombinationVersions] = useState<Record<string, CombinationVersion>>({});

  useEffect(() => {
    Promise.all([jsonFetch("/api/prompt-library/catalog"), jsonFetch("/api/workflow-catalog/generation-forms")])
      .then(([catalog, descriptor]) => {
        setCategories(catalog.categories || []);
        setForms(descriptor.items || []);
        setCombinationVersions(Object.fromEntries((catalog.combinations || []).map((item: { id: string; revision: number; etag?: string }) => [item.id, { revision: item.revision, etag: item.etag }])));
      })
      .catch((reason) => setError(String(reason.message || reason)));
  }, []);

  async function openCategory(next: BrowserCategory) {
    setError("");
    try {
      const data = await jsonFetch(`/api/prompt-library/categories/${next.polarity}/${next.id}`);
      setCategory({ ...data.category, etag: data.etag });
      setEntries(data.category.entries || []);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  function changePolarity(polarity: PromptPolarity) {
    setActivePolarity(polarity);
    setCategory(null);
    setEntries([]);
  }

  function addEntry(entry: BrowserEntry) {
    if (!category) return;
    const nextSequence = sequence + 1;
    setSequence(nextSequence);
    const fragment = { id: `${category.polarity}-${category.id}-${entry.id}-${nextSequence}`, kind: "entry" as const, source: { polarity: category.polarity, categoryId: category.id, entryId: entry.id, revision: entry.revision }, originalSnapshot: entry.prompt, text: entry.prompt, weight: "" };
    (activePolarity === "positive" ? setPositive : setNegative)((state) => appendFragment(state, fragment));
  }

  function addLiteral(text: string) {
    const nextSequence = sequence + 1;
    setSequence(nextSequence);
    const fragment = { id: `literal-${nextSequence}`, kind: "literal" as const, originalSnapshot: text, text, weight: "" };
    (activePolarity === "positive" ? setPositive : setNegative)((state) => appendFragment(state, fragment));
  }

  const actions = (setter: React.Dispatch<React.SetStateAction<CompositionState>>) => ({
    onTextChange: (id: string, text: string) => setter((state) => setFragmentText(state, id, text)),
    onWeightChange: (id: string, weight: string) => setter((state) => setFragmentWeight(state, id, weight)),
    onMove: (id: string, direction: -1 | 1) => setter((state) => moveFragment(state, id, direction)),
    onRemove: (id: string) => setter((state) => removeFragment(state, id)),
    onComposedTextChange: (text: string) => setter((state) => reconcileComposedText(state, text)),
  });

  async function saveCombination() {
    const id = saveId.trim();
    if (!id) return;
    setError("");
    setSaveStatus("");
    if (!COMBINATION_ID_PATTERN.test(id)) {
      setError("組合 ID 只能使用 Unicode 字母、數字與連字號，例如 niji基礎瑟瑟");
      return;
    }
    const positiveFragments = serializeFragments(positive);
    const negativeFragments = serializeFragments(negative);
    const currentVersion = combinationVersions[id];
    try {
      const response = await fetch("/api/prompt-library/compose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          positive: positiveFragments,
          negative: negativeFragments,
          save_as: {
            id,
            name_zh: id,
            description_zh: "Prompt Workbench 儲存組合",
            expected_revision: currentVersion?.revision ?? 0,
            ...(currentVersion?.etag ? { expected_etag: currentVersion.etag } : {}),
            aliases: [],
            keywords: [],
            order: 10,
            positive: positiveFragments,
            negative: negativeFragments,
          },
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(responseErrorMessage(data, response.status));
      const saved = data?.saved_combination;
      if (saved?.combination?.revision) {
        setCombinationVersions((versions) => ({
          ...versions,
          [id]: { revision: saved.combination.revision, etag: saved.etag },
        }));
      }
      setSaveStatus("組合已儲存");
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  async function saveEntry(value: EntryEditorValue, mode: "create" | "edit") {
    if (!category) return;
    setError("");
    const body = {
      ...value.fields,
      expected_revision: category.revision,
      ...(category.etag ? { expected_etag: category.etag } : {}),
    };
    const response = await fetch(`/api/prompt-library/categories/${category.polarity}/${category.id}/entries/${encodeURIComponent(value.id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = data?.detail?.message || `HTTP ${response.status}`;
      setError(String(message));
      throw new Error(String(message));
    }
    await openCategory(category);
  }

  async function archiveEntry(entry: BrowserEntry) {
    if (!category) return;
    setError("");
    const body = {
      resource_type: "entry",
      resource_id: entry.id,
      polarity: category.polarity,
      category_id: category.id,
      expected_revision: category.revision,
      ...(category.etag ? { expected_etag: category.etag } : {}),
    };
    const response = await fetch("/api/prompt-library/archive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = data?.detail?.message || `HTTP ${response.status}`;
      setError(String(message));
      throw new Error(String(message));
    }
    await openCategory(category);
  }

  return (
    <div className="space-y-6">
      <header><h1 className="text-2xl font-bold text-white">Prompt Workbench</h1><p className="mt-1 text-sm text-slate-400">選取詞條後即時建立正向與負向 Prompt，並可在右側微調。</p></header>
      {error && <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(380px,0.9fr)]">
        <PromptEntryBrowser categories={categories} activePolarity={activePolarity} onPolarityChange={changePolarity} selectedCategory={category} entries={entries} onOpenCategory={openCategory} onAddEntry={addEntry} onAddLiteral={addLiteral} onSaveEntry={saveEntry} onArchiveEntry={archiveEntry} />
        <PromptOverview positive={positive} negative={negative} positiveActions={actions(setPositive)} negativeActions={actions(setNegative)} />
      </div>
      <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1 text-sm text-slate-400">組合 ID<input aria-label="組合 ID" aria-describedby="combination-id-help" value={saveId} onChange={(event) => setSaveId(event.target.value)} placeholder="例如 niji基礎瑟瑟" className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" /><span id="combination-id-help" className="mt-1 block text-xs text-slate-500">允許 Unicode 字母、數字與連字號；不允許空白或路徑符號</span></label>
          <button type="button" disabled={!saveId.trim()} onClick={saveCombination} className="rounded-lg bg-emerald-600 px-5 py-2.5 font-medium text-white disabled:bg-slate-700">儲存組合</button>
        </div>
        {saveStatus && <p className="mt-2 text-sm text-emerald-300">{saveStatus}</p>}
      </section>
      <GenerationPanel forms={forms} positivePrompt={positive.text} negativePrompt={negative.text} />
    </div>
  );
}
