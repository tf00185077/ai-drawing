import { useEffect, useRef, useState } from "react";
import type { PromptCombinationSummary, PromptFragment, PromptPolarity, PromptVersionedCombination, PromptWarning } from "../../types/api";
import { appendFragment, deserializeFragments, emptyComposition, materializeRawText, moveFragment, removeFragment, serializeFragments, setFragmentText, setFragmentWeight, type CompositionState } from "./compositionState";
import CombinationToolbar from "./CombinationToolbar";
import GenerationPanel, { type GenerationForm } from "./GenerationPanel";
import PromptEntryBrowser, { promptEntryContent, promptEntryLabel, type BrowserCategory, type BrowserEntry } from "./PromptEntryBrowser";
import PromptOverview from "./PromptOverview";
import { composeAndSaveCombination, getPromptCatalog, getPromptCategory, getPromptCombination } from "./promptLibraryApi";

interface DocumentState {
  id: string | null;
  revision: number | null;
  etag: string | null;
  repaired: boolean;
  warnings: string[];
  dirty: boolean;
}

const blankDocument = (): DocumentState => ({ id: null, revision: null, etag: null, repaired: false, warnings: [], dirty: false });
const COMBINATION_ID_PATTERN = /^[\p{L}\p{N}]+(?:-[\p{L}\p{N}]+)*$/u;
const unsafeIdMessage = "組合 ID 只能使用 Unicode 字母、數字與連字號，例如 niji基礎瑟瑟";
const combinationIdLengthMessage = "組合 ID 必須包含 1 到 128 個字元";

async function jsonFetch(url: string) {
  const response = await fetch(url);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return data;
}

const warningMessages = (warnings: readonly PromptWarning[]): string[] => warnings.map((warning) => warning.message);
const categoryKey = (polarity: PromptPolarity, categoryId: string) => `${polarity}/${categoryId}`;
const entryKey = (polarity: PromptPolarity, categoryId: string, entryId: string) => `${polarity}/${categoryId}/${entryId}`;

function referencedCategories(positive: readonly PromptFragment[], negative: readonly PromptFragment[]) {
  const refs = new Map<string, { polarity: PromptPolarity; categoryId: string }>();
  for (const fragments of [positive, negative]) {
    for (const fragment of fragments) {
      if (fragment.kind === "entry" && fragment.ref) {
        const { polarity, category_id: categoryId } = fragment.ref;
        refs.set(categoryKey(polarity, categoryId), { polarity, categoryId });
      }
    }
  }
  return [...refs.values()];
}

async function resolveEntryNames(
  positive: readonly PromptFragment[],
  negative: readonly PromptFragment[],
  retained: ReadonlyMap<string, string> = new Map(),
): Promise<{ labels: Map<string, string>; warnings: string[] }> {
  const labels = new Map(retained);
  const fragments = [...positive, ...negative];
  const refs = referencedCategories(positive, negative).filter(({ polarity, categoryId }) => {
    return fragments.some((item) => item.ref?.polarity === polarity && item.ref.category_id === categoryId
      && !labels.has(entryKey(item.ref.polarity, categoryId, item.ref.entry_id)));
  });
  const results = await Promise.allSettled(refs.map(({ polarity, categoryId }) => getPromptCategory(polarity, categoryId)));
  const warnings: string[] = [];
  results.forEach((result, index) => {
    const ref = refs[index];
    if (result.status === "rejected") {
      warnings.push(`${ref.polarity}/${ref.categoryId} 名稱查詢失敗；已使用詞條 ID。`);
      return;
    }
    for (const entry of result.value.category.entries) {
      const name = entry.name_zh.trim() || entry.prompt.trim() || entry.id;
      labels.set(entryKey(ref.polarity, ref.categoryId, entry.id), name);
    }
  });
  return { labels, warnings };
}

function deserializeWithReferenceLabels(
  fragments: readonly PromptFragment[],
  destinationPolarity: PromptPolarity,
  idFactory: () => string,
  labels: ReadonlyMap<string, string>,
): CompositionState {
  const state = deserializeFragments(fragments, destinationPolarity, idFactory, labels);
  return {
    ...state,
    fragments: state.fragments.map((fragment) => fragment.source ? {
      ...fragment,
      displayName: labels.get(entryKey(fragment.source.polarity, fragment.source.categoryId, fragment.source.entryId))
        ?? fragment.source.entryId,
    } : fragment),
  };
}

export default function PromptWorkbench() {
  const [categories, setCategories] = useState<BrowserCategory[]>([]);
  const [combinations, setCombinations] = useState<PromptCombinationSummary[]>([]);
  const [forms, setForms] = useState<GenerationForm[]>([]);
  const [activePolarity, setActivePolarity] = useState<PromptPolarity>("positive");
  const [category, setCategory] = useState<BrowserCategory | null>(null);
  const [entries, setEntries] = useState<BrowserEntry[]>([]);
  const [positive, setPositive] = useState<CompositionState>(emptyComposition);
  const [negative, setNegative] = useState<CompositionState>(emptyComposition);
  const [document, setDocument] = useState<DocumentState>(blankDocument);
  const [selectedId, setSelectedId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const sequence = useRef(0);
  const operationId = useRef(0);
  const sourceRequestId = useRef(0);
  const labelMap = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    Promise.all([getPromptCatalog(), jsonFetch("/api/workflow-catalog/generation-forms")])
      .then(([catalog, descriptor]) => {
        setCategories(catalog.categories || []);
        setCombinations(catalog.combinations || []);
        setForms(descriptor.items || []);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    return () => {
      sourceRequestId.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!document.dirty) return;
    const guardUnsavedDocument = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", guardUnsavedDocument);
    return () => window.removeEventListener("beforeunload", guardUnsavedDocument);
  }, [document.dirty]);

  function beginOperation() {
    const id = operationId.current + 1;
    operationId.current = id;
    setBusy(true);
    setError("");
    return id;
  }

  function finishOperation(id: number) {
    if (operationId.current === id) setBusy(false);
  }

  function markDirty() {
    operationId.current += 1;
    setBusy(false);
    setDocument((current) => ({ ...current, dirty: true }));
    setSuccess("");
  }

  function nextId(prefix: string) {
    sequence.current += 1;
    return `${prefix}-${sequence.current}`;
  }

  function mutate(
    setter: React.Dispatch<React.SetStateAction<CompositionState>>,
    transform: (state: CompositionState) => CompositionState,
  ) {
    setter((state) => transform(state));
    markDirty();
  }

  function canReplace() {
    if (!document.dirty) return true;
    return window.confirm("目前組合有未儲存變更，確定要取代嗎？");
  }

  async function openCategory(next: BrowserCategory) {
    const requestId = ++sourceRequestId.current;
    setError("");
    setCategory(next);
    setEntries([]);
    try {
      const data = await getPromptCategory(next.polarity, next.id);
      if (sourceRequestId.current !== requestId) return;
      setCategory({ ...data.category, etag: data.etag });
      setEntries(data.category.entries || []);
    } catch (reason) {
      if (sourceRequestId.current === requestId) setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  function changePolarity(polarity: PromptPolarity) {
    sourceRequestId.current += 1;
    setActivePolarity(polarity);
    setCategory(null);
    setEntries([]);
  }

  function addEntry(entry: BrowserEntry) {
    if (!category) return;
    const promptText = promptEntryContent(entry);
    const displayName = promptEntryLabel(entry);
    const item = { id: nextId(`${category.polarity}-${category.id}-${entry.id}`), kind: "entry" as const, displayName, source: { polarity: category.polarity, categoryId: category.id, entryId: entry.id, revision: entry.revision }, originalSnapshot: promptText, text: promptText, weight: "" };
    if (activePolarity === "positive") {
      mutate(setPositive, (state) => appendFragment(state, item));
    } else {
      mutate(setNegative, (state) => appendFragment(state, item));
    }
  }

  function addLiteral(text: string) {
    const item = { id: nextId("literal"), kind: "literal" as const, displayName: "自訂文字", originalSnapshot: text, text, weight: "" };
    if (activePolarity === "positive") {
      mutate(setPositive, (state) => appendFragment(state, item));
    } else {
      mutate(setNegative, (state) => appendFragment(state, item));
    }
  }

  const actions = (
    setter: React.Dispatch<React.SetStateAction<CompositionState>>,
    state: CompositionState,
  ) => ({
    onTextChange: (id: string, text: string) => mutate(setter, (current) => setFragmentText(current, id, text)),
    onWeightChange: (id: string, weight: string) => mutate(setter, (current) => setFragmentWeight(current, id, weight)),
    onMove: (id: string, direction: -1 | 1) => mutate(setter, (current) => moveFragment(current, id, direction)),
    onRemove: (id: string) => mutate(setter, (current) => removeFragment(current, id)),
    onFinalTextChange: (text: string) => {
      setter((current) => materializeRawText(current, text, () => nextId("literal")));
      markDirty();
    },
  });

  function installCombination(saved: PromptVersionedCombination, labels: Map<string, string>, extraWarnings: string[]) {
    const nextPositive = deserializeWithReferenceLabels(saved.combination.positive, "positive", () => nextId("loaded"), labels);
    const nextNegative = deserializeWithReferenceLabels(saved.combination.negative, "negative", () => nextId("loaded"), labels);
    setPositive(nextPositive);
    setNegative(nextNegative);
    labelMap.current = labels;
    setDocument({
      id: saved.combination.id,
      revision: saved.combination.revision,
      etag: saved.etag,
      repaired: saved.repaired,
      warnings: [...warningMessages(saved.warnings), ...extraWarnings],
      dirty: false,
    });
  }

  async function loadCombination() {
    if (!selectedId || !canReplace()) return;
    const id = beginOperation();
    setSuccess("");
    try {
      const detail = await getPromptCombination(selectedId);
      const names = await resolveEntryNames(detail.combination.positive, detail.combination.negative);
      if (operationId.current !== id) return;
      installCombination(detail, names.labels, names.warnings);
    } catch (reason) {
      if (operationId.current === id) setError(reason instanceof Error ? reason.message : String(reason));
    } finally { finishOperation(id); }
  }

  function createBlank() {
    if (!canReplace()) return;
    operationId.current += 1;
    setBusy(false);
    setPositive(emptyComposition());
    setNegative(emptyComposition());
    setDocument(blankDocument());
    setSuccess("");
    setError("");
    labelMap.current = new Map();
  }

  async function saveCombination(saveAs: boolean) {
    const id = ((saveAs || !document.id ? targetId : document.id)?.trim() || "").normalize("NFC");
    if (!id) return;
    if (Array.from(id).length > 128) {
      setError(combinationIdLengthMessage);
      return;
    }
    if (!COMBINATION_ID_PATTERN.test(id)) {
      setError(unsafeIdMessage);
      return;
    }
    setTargetId(id);
    const operation = beginOperation();
    setSuccess("");
    const positiveFragments = serializeFragments(positive);
    const negativeFragments = serializeFragments(negative);
    const expectedRevision = saveAs || !document.id ? 0 : document.revision ?? 0;
    const expectedEtag = saveAs || !document.id ? undefined : document.etag ?? undefined;
    try {
      const data = await composeAndSaveCombination({
        positive: positiveFragments,
        negative: negativeFragments,
        save_as: {
          id,
          name_zh: id,
          description_zh: "Prompt Workbench 儲存組合",
          aliases: [], keywords: [], order: 10,
          expected_revision: expectedRevision,
          ...(expectedEtag ? { expected_etag: expectedEtag } : {}),
          legacy_template: false,
          positive: positiveFragments,
          negative: negativeFragments,
        },
      });
      if (!data.saved_combination) throw new Error("Backend 未回傳已儲存組合");
      const saved = data.saved_combination;
      const names = await resolveEntryNames(saved.combination.positive, saved.combination.negative, labelMap.current);
      if (operationId.current !== operation) return;
      installCombination(saved, names.labels, names.warnings);
      setSelectedId(saved.combination.id);
      setCombinations((items) => {
        if (items.some((item) => item.id === saved.combination.id)) return items;
        return [...items, {
          id: saved.combination.id, name_zh: saved.combination.name_zh, description_zh: saved.combination.description_zh,
          aliases: saved.combination.aliases, keywords: saved.combination.keywords, order: saved.combination.order,
          revision: saved.combination.revision, archived: saved.combination.archived, legacy_template: saved.combination.legacy_template,
          positive_prompt_snapshot: saved.combination.positive_prompt_snapshot, negative_prompt_snapshot: saved.combination.negative_prompt_snapshot,
          etag: saved.etag,
        }];
      });
      setSuccess("組合已儲存");
    } catch (reason) {
      if (operationId.current === operation) setError(reason instanceof Error ? reason.message : String(reason));
    } finally { finishOperation(operation); }
  }

  return (
    <div className="space-y-6">
      <header><h1 className="text-2xl font-bold text-white">Prompt Workbench</h1><p className="mt-1 text-sm text-slate-400">選取詞條後即時建立正向與負向 Prompt，並可在右側微調。</p></header>
      <CombinationToolbar
        combinations={combinations}
        selectedId={selectedId}
        onSelectedIdChange={setSelectedId}
        onLoad={loadCombination}
        onBlank={createBlank}
        document={document}
        targetId={targetId}
        onTargetIdChange={setTargetId}
        onUpdate={() => saveCombination(false)}
        onSaveAs={() => saveCombination(true)}
        busy={busy}
        warnings={document.warnings}
        success={success}
        error={error}
      />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(380px,0.9fr)]">
        <PromptEntryBrowser categories={categories} activePolarity={activePolarity} onPolarityChange={changePolarity} selectedCategory={category} entries={entries} onOpenCategory={openCategory} onAddEntry={addEntry} onAddLiteral={addLiteral} />
        <PromptOverview positive={positive} negative={negative} positiveActions={actions(setPositive, positive)} negativeActions={actions(setNegative, negative)} />
      </div>
      <GenerationPanel forms={forms} positivePrompt={positive.text} negativePrompt={negative.text} />
    </div>
  );
}
