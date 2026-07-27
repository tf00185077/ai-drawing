import { useCallback, useEffect, useRef, useState } from "react";
import type { PromptBlockingDocumentDiagnostic, PromptCombinationSummary, PromptEntryRef, PromptFragment, PromptPolarity, PromptProvenanceResolution, PromptVersionedCombination, PromptWarning } from "../../types/api";
import { appendFragment, appendFragmentsDeduped, appendLiteralText, blankSegmentMessage, blankSegmentPreflight, buildLiteralLabelIndex, deserializeFragments, emptyComposition, materializeRawText, moveFragment, removeFragment, replaceDiagnosticFallback, resolveLiteralDisplayLabel, serializeFragments, setFragmentText, setFragmentWeight, sortFragmentsByRecommendation, tagDiagnosticFallback, type CompositionState, type LiteralLabelIndex, type WorkbenchFragment } from "./compositionState";
import CombinationToolbar from "./CombinationToolbar";
import GenerationPanel, { type GenerationForm } from "./GenerationPanel";
import PromptEntryBrowser, { promptEntryContent, promptEntryLabel, type BrowserCategory, type BrowserEntry } from "./PromptEntryBrowser";
import PromptOverview from "./PromptOverview";
import { acknowledgeLiteralConversion, composeAndSaveCombination, getPromptCatalog, getPromptCategory, getPromptCombination, getPromptLibraryMigrationStatus } from "./promptLibraryApi";

interface DocumentState {
  id: string | null;
  revision: number | null;
  etag: string | null;
  repaired: boolean;
  warnings: string[];
  dirty: boolean;
  blockingDiagnostics: PromptBlockingDocumentDiagnostic[];
  documentContextToken: string | null;
  literalConversionToken: string | null;
  provenanceResolutions: PromptProvenanceResolution[];
  metadata: {
    nameZh: string;
    descriptionZh: string;
    aliases: string[];
    keywords: string[];
    order: number;
    legacyTemplate: boolean;
  } | null;
}

const blankDocument = (): DocumentState => ({
  id: null,
  revision: null,
  etag: null,
  repaired: false,
  warnings: [],
  dirty: false,
  blockingDiagnostics: [],
  documentContextToken: null,
  literalConversionToken: null,
  provenanceResolutions: [],
  metadata: null,
});
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
  literalLabel: (snapshotRaw: string) => string,
): CompositionState {
  const state = deserializeFragments(fragments, destinationPolarity, idFactory, labels, literalLabel);
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
  const [readiness, setReadiness] = useState<"checking" | "blocked" | "ready">("checking");
  const [readinessMessage, setReadinessMessage] = useState("");
  const [categories, setCategories] = useState<BrowserCategory[]>([]);
  const [combinations, setCombinations] = useState<PromptCombinationSummary[]>([]);
  const [forms, setForms] = useState<GenerationForm[]>([]);
  const [activePolarity, setActivePolarity] = useState<PromptPolarity>("positive");
  const [category, setCategory] = useState<BrowserCategory | null>(null);
  const [entries, setEntries] = useState<BrowserEntry[]>([]);
  const [positive, setPositive] = useState<CompositionState>(emptyComposition);
  const [negative, setNegative] = useState<CompositionState>(emptyComposition);
  const [arrangement, setArrangement] = useState<{ positive: "auto" | "manual"; negative: "auto" | "manual" }>({
    positive: "auto",
    negative: "auto",
  });
  const [categoryMeta, setCategoryMeta] = useState<Map<string, { order: number; nameZh: string }>>(new Map());
  const entryOrderByRef = useRef<Map<string, number>>(new Map());
  const categoryPathOrders = useRef<Map<string, number[]>>(new Map());
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
  const literalLabelIndex = useRef<LiteralLabelIndex>(new Map());

  useEffect(() => {
    let active = true;
    getPromptLibraryMigrationStatus()
      .then(async (status) => {
        if (!active) return;
        if (
          !status.comma_atomic_ready ||
          !status.atomic_enforcement_active ||
          status.marker_present
        ) {
          setReadiness("blocked");
          setReadinessMessage(
            `Prompt Library 原子化遷移尚未完成（${status.state}）；編輯器保持停用。`,
          );
          return;
        }
        const [catalog, descriptor] = await Promise.all([
          getPromptCatalog(),
          jsonFetch("/api/workflow-catalog/generation-forms"),
        ]);
        if (!active) return;
        setCategories(catalog.categories || []);
        setCombinations(catalog.combinations || []);
        setForms(descriptor.items || []);
        const meta = new Map<string, { order: number; nameZh: string }>();
        (catalog.categories || []).forEach((item) =>
          meta.set(`${item.polarity}/${item.id}`, { order: item.order, nameZh: item.name_zh }),
        );
        setCategoryMeta(meta);
        const orderByKey = new Map<string, { order: number; parentId: string | null }>();
        (catalog.categories || []).forEach((item) =>
          orderByKey.set(`${item.polarity}/${item.id}`, {
            order: item.order,
            parentId: item.parent_id ?? null,
          }),
        );
        const pathOrders = new Map<string, number[]>();
        const pathFor = (polarity: string, id: string, guard: Set<string>): number[] => {
          const key = `${polarity}/${id}`;
          const cached = pathOrders.get(key);
          if (cached) return cached;
          const node = orderByKey.get(key);
          if (!node || guard.has(key)) return [];
          guard.add(key);
          const parentPath = node.parentId ? pathFor(polarity, node.parentId, guard) : [];
          const path = [...parentPath, node.order];
          pathOrders.set(key, path);
          return path;
        };
        orderByKey.forEach((_value, key) => {
          const slash = key.indexOf("/");
          pathFor(key.slice(0, slash), key.slice(slash + 1), new Set());
        });
        categoryPathOrders.current = pathOrders;
        const categoryResults = await Promise.allSettled(
          (catalog.categories || []).map((item) =>
            getPromptCategory(item.polarity, item.id),
          ),
        );
        if (!active) return;
        if (categoryResults.every((result) => result.status === "fulfilled")) {
          const allEntries = categoryResults.flatMap((result) =>
            result.status === "fulfilled" ? result.value.category.entries : [],
          );
          literalLabelIndex.current = buildLiteralLabelIndex(allEntries);
          const labels = new Map<string, string>();
          categoryResults.forEach((result) => {
            if (result.status !== "fulfilled") return;
            result.value.category.entries.forEach((entry) => {
              labels.set(
                entryKey(
                  result.value.category.polarity,
                  result.value.category.id,
                  entry.id,
                ),
                (entry.name_zh ?? "").trim() ||
                  (entry.prompt ?? "").trim() ||
                  entry.id ||
                  "自訂文字",
              );
            });
          });
          labelMap.current = labels;
          const orders = new Map<string, number>();
          categoryResults.forEach((result) => {
            if (result.status !== "fulfilled") return;
            const cat = result.value.category;
            cat.entries.forEach((entry) => orders.set(`${cat.polarity}/${cat.id}/${entry.id}`, entry.order));
          });
          entryOrderByRef.current = orders;
        } else {
          literalLabelIndex.current = new Map();
        }
        setReadiness("ready");
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    return () => {
      active = false;
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

  const rankOf = useCallback(
    (fragment: WorkbenchFragment): number[] => {
      if (fragment.kind !== "entry" || !fragment.source) return [Number.POSITIVE_INFINITY];
      const catKey = `${fragment.source.polarity}/${fragment.source.categoryId}`;
      const path = categoryPathOrders.current.get(catKey);
      if (!path || path.length === 0) return [Number.POSITIVE_INFINITY];
      const entryOrder = entryOrderByRef.current.get(`${catKey}/${fragment.source.entryId}`) ?? 10;
      return [...path, entryOrder];
    },
    [],
  );

  const categoryInfoOf = useCallback(
    (fragment: WorkbenchFragment) => {
      if (fragment.kind !== "entry" || !fragment.source) return null;
      const catKey = `${fragment.source.polarity}/${fragment.source.categoryId}`;
      const meta = categoryMeta.get(catKey);
      if (!meta) return null;
      return { key: fragment.source.categoryId, displayName: meta.nameZh, order: meta.order };
    },
    [categoryMeta],
  );

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
    const item = {
      id: nextId(`${category.polarity}-${category.id}-${entry.id}`),
      kind: "entry" as const,
      displayName,
      source: {
        polarity: category.polarity,
        categoryId: category.id,
        entryId: entry.id,
        revision: entry.revision,
      },
      sourceSnapshotRaw: promptText,
      snapshotRaw: promptText,
      weight: "",
      userAddedSource: true,
    };
    const setter = activePolarity === "positive" ? setPositive : setNegative;
    mutate(setter, (state) => {
      const appended = appendFragment(state, item);
      return arrangement[activePolarity] === "auto"
        ? sortFragmentsByRecommendation(appended, rankOf)
        : appended;
    });
  }

  function addLiteral(text: string) {
    const append = (state: CompositionState) =>
      appendLiteralText(
        state,
        text,
        () => nextId("literal"),
        (snapshot) =>
          resolveLiteralDisplayLabel(snapshot, literalLabelIndex.current),
      );
    const setter = activePolarity === "positive" ? setPositive : setNegative;
    mutate(setter, (state) => {
      const appended = append(state);
      return arrangement[activePolarity] === "auto"
        ? sortFragmentsByRecommendation(appended, rankOf)
        : appended;
    });
  }

  const actions = (
    polarity: PromptPolarity,
    setter: React.Dispatch<React.SetStateAction<CompositionState>>,
  ) => ({
    onTextChange: (id: string, text: string) => mutate(setter, (current) =>
      setFragmentText(
        current,
        id,
        text,
        (snapshot) => resolveLiteralDisplayLabel(snapshot, literalLabelIndex.current),
        () => nextId("literal"),
      )),
    onWeightChange: (id: string, weight: string) => mutate(setter, (current) => setFragmentWeight(current, id, weight)),
    onMove: (id: string, direction: -1 | 1) => {
      mutate(setter, (current) => moveFragment(current, id, direction));
      setArrangement((current) => ({ ...current, [polarity]: "manual" }));
    },
    onRemove: (id: string) => mutate(setter, (current) => removeFragment(current, id)),
    onFinalTextChange: (text: string) => {
      setter((current) => materializeRawText(
        current,
        text,
        () => nextId("literal"),
        (snapshot) => resolveLiteralDisplayLabel(snapshot, literalLabelIndex.current),
      ));
      markDirty();
    },
    onReapplySort: () => {
      mutate(setter, (current) => sortFragmentsByRecommendation(current, rankOf));
      setArrangement((current) => ({ ...current, [polarity]: "auto" }));
    },
  });

  function installCombination(saved: PromptVersionedCombination, labels: Map<string, string>, extraWarnings: string[]) {
    const literalLabel = (snapshot: string) => resolveLiteralDisplayLabel(snapshot, literalLabelIndex.current);
    let nextPositive = deserializeWithReferenceLabels(saved.combination.positive, "positive", () => nextId("loaded"), labels, literalLabel);
    let nextNegative = deserializeWithReferenceLabels(saved.combination.negative, "negative", () => nextId("loaded"), labels, literalLabel);
    for (const diagnostic of saved.blocking_diagnostics || []) {
      if (diagnostic.polarity === "positive") {
        nextPositive = tagDiagnosticFallback(
          nextPositive,
          diagnostic.id,
          diagnostic.fallback_start_position,
          diagnostic.fallback_count,
        );
      } else {
        nextNegative = tagDiagnosticFallback(
          nextNegative,
          diagnostic.id,
          diagnostic.fallback_start_position,
          diagnostic.fallback_count,
        );
      }
    }
    setPositive(nextPositive);
    setNegative(nextNegative);
    setArrangement({ positive: "manual", negative: "manual" });
    labelMap.current = labels;
    setDocument({
      id: saved.combination.id,
      revision: saved.combination.revision,
      etag: saved.etag,
      repaired: saved.repaired,
      warnings: [...warningMessages(saved.warnings), ...extraWarnings],
      dirty: false,
      blockingDiagnostics: saved.blocking_diagnostics || [],
      documentContextToken: saved.document_context_token || null,
      literalConversionToken: null,
      provenanceResolutions: [],
      metadata: {
        nameZh: saved.combination.name_zh,
        descriptionZh: saved.combination.description_zh,
        aliases: [...saved.combination.aliases],
        keywords: [...saved.combination.keywords],
        order: saved.combination.order,
        legacyTemplate: saved.combination.legacy_template,
      },
    });
  }

  async function appendCombination() {
    if (!selectedId) return;
    const id = beginOperation();
    setSuccess("");
    try {
      const detail = await getPromptCombination(selectedId);
      const names = await resolveEntryNames(
        detail.combination.positive,
        detail.combination.negative,
        labelMap.current,
      );
      if (operationId.current !== id) return;
      const literalLabel = (snapshot: string) => resolveLiteralDisplayLabel(snapshot, literalLabelIndex.current);
      const loadedPositive = deserializeWithReferenceLabels(detail.combination.positive, "positive", () => nextId("loaded"), names.labels, literalLabel);
      const loadedNegative = deserializeWithReferenceLabels(detail.combination.negative, "negative", () => nextId("loaded"), names.labels, literalLabel);
      labelMap.current = names.labels;
      setPositive((current) => {
        const merged = appendFragmentsDeduped(current, loadedPositive.fragments);
        return arrangement.positive === "auto" ? sortFragmentsByRecommendation(merged, rankOf) : merged;
      });
      setNegative((current) => {
        const merged = appendFragmentsDeduped(current, loadedNegative.fragments);
        return arrangement.negative === "auto" ? sortFragmentsByRecommendation(merged, rankOf) : merged;
      });
      setDocument({ ...blankDocument(), dirty: true, warnings: [...warningMessages(detail.warnings), ...names.warnings] });
      setSuccess("已加入組合到目前工作區（未儲存草稿）");
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
    setArrangement({ positive: "auto", negative: "auto" });
    setDocument(blankDocument());
    setSuccess("");
    setError("");
    labelMap.current = new Map();
  }

  async function saveCombination(saveAs: boolean) {
    const preflightError = runBlankPreflight();
    if (preflightError) return;
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
    const metadata = document.metadata ?? {
      nameZh: id,
      descriptionZh: "Prompt Workbench 儲存組合",
      aliases: [],
      keywords: [],
      order: 10,
      legacyTemplate: false,
    };
    try {
      const data = await composeAndSaveCombination({
        positive: positiveFragments,
        negative: negativeFragments,
        save_as: {
          id,
          name_zh: metadata.nameZh,
          description_zh: metadata.descriptionZh,
          aliases: [...metadata.aliases],
          keywords: [...metadata.keywords],
          order: metadata.order,
          expected_revision: expectedRevision,
          ...(expectedEtag ? { expected_etag: expectedEtag } : {}),
          legacy_template: metadata.legacyTemplate,
          positive: positiveFragments,
          negative: negativeFragments,
          ...(document.id ? { source_combination_id: document.id } : {}),
          ...(document.documentContextToken
            ? { document_context_token: document.documentContextToken }
            : {}),
          ...(document.literalConversionToken
            ? { literal_conversion_token: document.literalConversionToken }
            : {}),
          ...(document.provenanceResolutions.length > 0
            ? { provenance_resolutions: document.provenanceResolutions }
            : {}),
        },
      });
      if (!data.saved_combination) throw new Error("Backend 未回傳已儲存組合");
      const saved = data.saved_combination;
      if (
        data.positive_prompt !== positive.text ||
        data.negative_prompt !== negative.text
      ) {
        throw new Error("Backend canonical rendered atoms 與目前最終文字不一致；未清除未儲存狀態。");
      }
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

  function runBlankPreflight(): string | null {
    const invalid = blankSegmentPreflight(positive, negative);
    if (invalid.length === 0) return null;
    const message = blankSegmentMessage(invalid);
    setError(message);
    const first = invalid[0];
    window.dispatchEvent(
      new CustomEvent("prompt-workbench-focus", { detail: first }),
    );
    return message;
  }

  async function acknowledgeBlockedLiterals() {
    if (!document.id || !document.documentContextToken) return;
    const operation = beginOperation();
    try {
      const response = await acknowledgeLiteralConversion(
        document.id,
        document.documentContextToken,
      );
      if (operationId.current !== operation) return;
      setDocument((current) => ({
        ...current,
        literalConversionToken: response.literal_conversion_token,
      }));
      setSuccess("已明示確認：儲存時把未知舊來源轉為自訂文字。");
    } catch (reason) {
      if (operationId.current === operation) {
        setError(reason instanceof Error ? reason.message : String(reason));
      }
    } finally {
      finishOperation(operation);
    }
  }

  function resolveBlockedWithCurrentRefs(
    diagnostic: PromptBlockingDocumentDiagnostic,
  ) {
    if (!document.documentContextToken) return;
    const lane = diagnostic.polarity === "positive" ? positive : negative;
    const candidates = lane.fragments.filter(
      (fragment) =>
        fragment.kind === "entry" &&
        fragment.source &&
        fragment.userAddedSource,
    );
    const refs = candidates.map((fragment): PromptEntryRef => ({
        polarity: fragment.source!.polarity,
        category_id: fragment.source!.categoryId,
        entry_id: fragment.source!.entryId,
      }));
    if (refs.length === 0) {
      setError("請先在此診斷的 prompt 側從詞庫加入至少一個新的替代來源詞條。");
      return;
    }
    const replaced = replaceDiagnosticFallback(
      lane,
      diagnostic.id,
      candidates.map((fragment) => fragment.id),
    );
    if (replaced === lane) {
      setError("找不到此診斷對應的 fallback；請重新載入組合後再選擇替代來源。");
      return;
    }
    if (diagnostic.polarity === "positive") {
      setPositive(replaced);
    } else {
      setNegative(replaced);
    }
    operationId.current += 1;
    setBusy(false);
    setDocument((current) => ({
      ...current,
      dirty: true,
      literalConversionToken: null,
      provenanceResolutions: [
        ...current.provenanceResolutions.filter(
          (resolution) => resolution.diagnostic_id !== diagnostic.id,
        ),
        {
          document_context_token: current.documentContextToken!,
          diagnostic_id: diagnostic.id,
          action: "replacement_entries",
          replacement_refs: refs,
        },
      ],
    }));
    setSuccess("已用新選擇的詞庫來源取代此診斷的 fallback；下一次 Update/Save As 會由 Backend 驗證。");
  }

  if (readiness !== "ready") {
    return (
      <section className="rounded-xl border border-amber-500/40 bg-slate-900 p-6">
        <h1 className="text-2xl font-bold text-white">Prompt Workbench</h1>
        <p role="status" className="mt-3 text-amber-200">
          {readiness === "checking" ? "正在確認 Prompt Library 原子化狀態…" : readinessMessage}
        </p>
        {error && <p role="alert" className="mt-3 text-red-300">{error}</p>}
      </section>
    );
  }

  return (
    <div className="space-y-6">
      <header><h1 className="text-2xl font-bold text-white">Prompt Workbench</h1><p className="mt-1 text-sm text-slate-400">每個 ASCII 逗號都會建立一個 prompt；括號、引號與權重語法內的逗號也不例外。</p></header>
      <CombinationToolbar
        combinations={combinations}
        selectedId={selectedId}
        onSelectedIdChange={setSelectedId}
        onLoad={appendCombination}
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
      {document.blockingDiagnostics.length > 0 && (
        <section className="rounded-xl border border-amber-500/50 bg-amber-500/10 p-4">
          <h2 className="font-semibold text-amber-100">舊來源尚未解決</h2>
          <p className="mt-1 text-sm text-amber-200">普通內容編輯不代表同意失去來源。請明示選擇替代詞庫來源，或確認轉為自訂文字。</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {document.blockingDiagnostics.map((diagnostic) => (
              <button
                key={diagnostic.id}
                type="button"
                onClick={() => resolveBlockedWithCurrentRefs(diagnostic)}
                className="rounded-md bg-sky-700 px-3 py-2 text-sm text-white"
              >
                使用目前加入的詞庫來源解決此診斷
              </button>
            ))}
            <button type="button" onClick={acknowledgeBlockedLiterals} className="rounded-md bg-amber-700 px-3 py-2 text-sm text-white">明示轉為自訂文字</button>
          </div>
        </section>
      )}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(380px,0.9fr)]">
        <PromptEntryBrowser categories={categories} activePolarity={activePolarity} onPolarityChange={changePolarity} selectedCategory={category} entries={entries} onOpenCategory={openCategory} onAddEntry={addEntry} onAddLiteral={addLiteral} />
        <PromptOverview
          positive={positive}
          negative={negative}
          positiveActions={actions("positive", setPositive)}
          negativeActions={actions("negative", setNegative)}
          positiveArrangement={arrangement.positive}
          negativeArrangement={arrangement.negative}
          categoryInfoOf={categoryInfoOf}
        />
      </div>
      <GenerationPanel forms={forms} positivePrompt={positive.text} negativePrompt={negative.text} preflight={runBlankPreflight} />
    </div>
  );
}
