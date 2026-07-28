import type {
  FastApiValidationError,
  CommaAtomicMigrationStatus,
  PromptArchiveRequest,
  PromptCategoryWriteRequest,
  PromptComposeRequest,
  PromptComposeResponse,
  PromptEntryWriteRequest,
  PromptLibraryCatalogResponse,
  PromptLibraryWriteResponse,
  PromptLiteralConversionAcknowledgeResponse,
  PromptPolarity,
  PromptRestoreRequest,
  PromptVersionedCategory,
  PromptVersionedCombination,
} from "../../types/api";

const API_ROOT = "/api/prompt-library";
const jsonHeaders = { "Content-Type": "application/json" };

const segment = (value: string): string => encodeURIComponent(value);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isValidationError = (value: unknown): value is FastApiValidationError =>
  isRecord(value) && Array.isArray(value.loc) && typeof value.msg === "string";

export function promptLibraryErrorMessage(data: unknown, status: number): string {
  if (isRecord(data)) {
    const { detail } = data;
    if (isRecord(detail) && typeof detail.message === "string") {
      const hint = typeof detail.hint === "string" ? detail.hint.trim() : "";
      return hint ? `${detail.message}（${hint}）` : detail.message;
    }
    if (Array.isArray(detail)) {
      const messages = detail.filter(isValidationError).map((error) => {
        const path = error.loc[0] === "body" ? error.loc.slice(1) : error.loc;
        const label = path.map(String).join(".");
        return label ? `${label}：${error.msg}` : error.msg;
      });
      if (messages.length > 0) return messages.join("；");
    }
  }
  return `Prompt Library 請求失敗（HTTP ${status}），請稍後重試`;
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(promptLibraryErrorMessage(data, response.status));
  return data as T;
}

const jsonWrite = (method: "PUT" | "POST", body: unknown): RequestInit => ({
  method,
  headers: jsonHeaders,
  body: JSON.stringify(body),
});

const categoryWriteBody = (input: PromptCategoryWriteRequest): PromptCategoryWriteRequest => ({
  name_zh: input.name_zh,
  description_zh: input.description_zh,
  aliases: input.aliases,
  keywords: input.keywords,
  order: input.order,
  expected_revision: input.expected_revision,
  ...(input.expected_etag !== undefined ? { expected_etag: input.expected_etag } : {}),
});

export function getPromptCatalog(): Promise<PromptLibraryCatalogResponse> {
  return requestJson<PromptLibraryCatalogResponse>(`${API_ROOT}/catalog`);
}

export function getPromptLibraryMigrationStatus(): Promise<CommaAtomicMigrationStatus> {
  return requestJson<CommaAtomicMigrationStatus>(`${API_ROOT}/migration-status`);
}

export function getPromptCategory(
  polarity: PromptPolarity,
  categoryId: string,
): Promise<PromptVersionedCategory> {
  return requestJson<PromptVersionedCategory>(
    `${API_ROOT}/categories/${segment(polarity)}/${segment(categoryId)}`,
  );
}

export function putPromptCategory(
  polarity: PromptPolarity,
  categoryId: string,
  input: PromptCategoryWriteRequest,
): Promise<PromptLibraryWriteResponse> {
  const body: PromptCategoryWriteRequest = {
    ...categoryWriteBody(input),
    ...(input.parent_id !== undefined ? { parent_id: input.parent_id } : {}),
  };
  return requestJson<PromptLibraryWriteResponse>(
    `${API_ROOT}/categories/${segment(polarity)}/${segment(categoryId)}`,
    jsonWrite("PUT", body),
  );
}

export function putPromptEntry(
  polarity: PromptPolarity,
  categoryId: string,
  entryId: string,
  input: PromptEntryWriteRequest,
): Promise<PromptLibraryWriteResponse> {
  const body: PromptEntryWriteRequest = {
    ...categoryWriteBody(input),
    prompt: input.prompt,
  };
  return requestJson<PromptLibraryWriteResponse>(
    `${API_ROOT}/categories/${segment(polarity)}/${segment(categoryId)}/entries/${segment(entryId)}`,
    jsonWrite("PUT", body),
  );
}

export function archivePromptResource(
  input: PromptArchiveRequest,
): Promise<PromptLibraryWriteResponse> {
  const body: PromptArchiveRequest = {
    resource_type: input.resource_type,
    resource_id: input.resource_id,
    expected_revision: input.expected_revision,
    ...(input.expected_etag !== undefined ? { expected_etag: input.expected_etag } : {}),
    ...(input.polarity !== undefined ? { polarity: input.polarity } : {}),
    ...(input.category_id !== undefined ? { category_id: input.category_id } : {}),
  };
  return requestJson<PromptLibraryWriteResponse>(
    `${API_ROOT}/archive`,
    jsonWrite("POST", body),
  );
}

export function restorePromptResource(
  input: PromptRestoreRequest,
): Promise<PromptLibraryWriteResponse> {
  const body: PromptRestoreRequest = {
    resource_type: input.resource_type,
    resource_id: input.resource_id,
    polarity: input.polarity,
    expected_revision: input.expected_revision,
    ...(input.expected_etag !== undefined ? { expected_etag: input.expected_etag } : {}),
    ...(input.category_id !== undefined ? { category_id: input.category_id } : {}),
  };
  return requestJson<PromptLibraryWriteResponse>(
    `${API_ROOT}/restore`,
    jsonWrite("POST", body),
  );
}

export function getPromptCombination(combinationId: string): Promise<PromptVersionedCombination> {
  return requestJson<PromptVersionedCombination>(
    `${API_ROOT}/combinations/${segment(combinationId)}`,
  );
}

export function acknowledgeLiteralConversion(
  combinationId: string,
  documentContextToken: string,
): Promise<PromptLiteralConversionAcknowledgeResponse> {
  return requestJson<PromptLiteralConversionAcknowledgeResponse>(
    `${API_ROOT}/combinations/${segment(combinationId)}/acknowledge-literal-conversion`,
    jsonWrite("POST", { document_context_token: documentContextToken }),
  );
}

export function composeAndSaveCombination(
  input: PromptComposeRequest,
): Promise<PromptComposeResponse> {
  const saveAs = input.save_as
    ? {
        id: input.save_as.id,
        name_zh: input.save_as.name_zh,
        description_zh: input.save_as.description_zh,
        aliases: input.save_as.aliases,
        keywords: input.save_as.keywords,
        order: input.save_as.order,
        expected_revision: input.save_as.expected_revision,
        ...(input.save_as.expected_etag !== undefined
          ? { expected_etag: input.save_as.expected_etag }
          : {}),
        legacy_template: input.save_as.legacy_template,
        positive: input.save_as.positive,
        negative: input.save_as.negative,
        ...(input.save_as.source_combination_id !== undefined
          ? { source_combination_id: input.save_as.source_combination_id }
          : {}),
        ...(input.save_as.document_context_token !== undefined
          ? { document_context_token: input.save_as.document_context_token }
          : {}),
        ...(input.save_as.literal_conversion_token !== undefined
          ? { literal_conversion_token: input.save_as.literal_conversion_token }
          : {}),
        ...(input.save_as.provenance_resolutions !== undefined
          ? { provenance_resolutions: input.save_as.provenance_resolutions }
          : {}),
      }
    : undefined;
  const body: PromptComposeRequest = {
    ...(input.combination_id !== undefined ? { combination_id: input.combination_id } : {}),
    positive: input.positive,
    negative: input.negative,
    ...(saveAs !== undefined ? { save_as: saveAs } : {}),
  };
  return requestJson<PromptComposeResponse>(
    `${API_ROOT}/compose`,
    jsonWrite("POST", body),
  );
}
