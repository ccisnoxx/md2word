// 文件：frontend/src/features/document-review/useTableValueColumnReview.ts
// 用途：管理可视化表格值列核定抽屉的状态、来源 PDF SHA256 自动补全、严格校验与幂等新代提交流程。
import { computed, reactive, ref, type Ref } from "vue";
import { ElMessage } from "element-plus";

import { documentJobsApi } from "@/api/documentJobs";
import { filesApi } from "@/api/files";
import type {
  DocumentJobNewGenerationResponse,
  DocumentQualityTableItemResponse,
  ReviewExpectedSourceRequest,
} from "@/api/types";
import { isAmbiguousWriteError, normalizeApiError, type ApiClientError } from "@/utils/errors";
import { generateCanonicalUuid } from "@/utils/uuid";
import {
  applyProvenanceJsonToDrafts,
  buildInitialFragmentDrafts,
  normalizeHexSha256,
  validateAndBuildTableValueReviews,
  type TableValueFragmentDraft,
} from "./tableValueColumnReview";

const STORAGE_PREFIX = "md2word.table_replay_req.";

type PersistedReplayPending = {
  requestId: string;
  note: string;
  expectedSource: ReviewExpectedSourceRequest;
  needsReconcile: boolean;
};

function storageKey(jobId: string): string {
  return `${STORAGE_PREFIX}${jobId}`;
}

function loadPending(jobId: string): PersistedReplayPending | null {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(storageKey(jobId));
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedReplayPending>;
    if (typeof parsed.requestId === "string" && parsed.requestId.length === 36 && parsed.expectedSource) {
      return {
        requestId: parsed.requestId,
        note: typeof parsed.note === "string" ? parsed.note : "",
        expectedSource: parsed.expectedSource,
        needsReconcile: Boolean(parsed.needsReconcile),
      };
    }
  } catch {
    return null;
  }
  return null;
}

function savePending(jobId: string, state: PersistedReplayPending): void {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  try {
    window.sessionStorage.setItem(storageKey(jobId), JSON.stringify(state));
  } catch {
    // 忽略受限存储写入失败，内存状态仍保留本次幂等键。
  }
}

function clearPending(jobId: string): void {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  try {
    window.sessionStorage.removeItem(storageKey(jobId));
  } catch {
    // 忽略清理异常。
  }
}

export function useTableValueColumnReview(options: {
  jobId: Ref<string>;
  sourcePdfFileId: Ref<string | null>;
  onAccepted?: (response: DocumentJobNewGenerationResponse) => void | Promise<void>;
}) {
  const visible = ref(false);
  const submitting = ref(false);
  const reconciling = ref(false);
  const loadingSourceHash = ref(false);
  const error = ref<ApiClientError | null>(null);
  const importError = ref<string>("");
  const importJsonText = ref<string>("");
  const lastResult = ref<DocumentJobNewGenerationResponse | null>(null);
  const fragments = ref<TableValueFragmentDraft[]>([]);
  const activeFragmentId = ref<string>("");

  const form = reactive({
    requestId: "",
    note: "",
    expectedSource: null as ReviewExpectedSourceRequest | null,
    needsReconcile: false,
    notFoundOnReconcile: false,
  });

  const validation = computed(() => validateAndBuildTableValueReviews(fragments.value));
  const activeFragment = computed(
    () => fragments.value.find((item) => item.fragmentId === activeFragmentId.value) ?? fragments.value[0] ?? null,
  );
  const canSubmit = computed(() =>
    Boolean(
      form.expectedSource
      && form.requestId
      && form.note.trim().length >= 1
      && form.note.trim().length <= 1000
      && validation.value.valid
      && !submitting.value
      && !reconciling.value
      && !form.needsReconcile,
    ),
  );

  async function hydrateSourcePdfSha256(): Promise<void> {
    const fileId = options.sourcePdfFileId.value;
    if (!fileId) {
      return;
    }
    loadingSourceHash.value = true;
    try {
      const fileMeta = await filesApi.get(fileId);
      const hex = normalizeHexSha256(fileMeta.checksum_sha256);
      if (hex) {
        for (const fragment of fragments.value) {
          if (!fragment.sourcePdfSha256) {
            fragment.sourcePdfSha256 = hex;
          }
        }
      }
    } catch {
      // 文件元数据不可用时保留手动输入框，不阻断页面。
    } finally {
      loadingSourceHash.value = false;
    }
  }

  function open(tables: DocumentQualityTableItemResponse[], expectedSource: ReviewExpectedSourceRequest): void {
    error.value = null;
    importError.value = "";
    lastResult.value = null;
    form.notFoundOnReconcile = false;

    fragments.value = buildInitialFragmentDrafts(tables);
    activeFragmentId.value = fragments.value[0]?.fragmentId ?? "";

    const saved = loadPending(options.jobId.value);
    if (saved && saved.needsReconcile) {
      form.requestId = saved.requestId;
      form.note = saved.note;
      form.expectedSource = saved.expectedSource;
      form.needsReconcile = true;
    } else {
      form.requestId = generateCanonicalUuid();
      form.note = "";
      form.expectedSource = { ...expectedSource };
      form.needsReconcile = false;
    }

    visible.value = true;
    void hydrateSourcePdfSha256();
  }

  function close(): void {
    visible.value = false;
  }

  function applyImportedJson(): boolean {
    importError.value = "";
    const result = applyProvenanceJsonToDrafts(importJsonText.value, fragments.value);
    if (!result.ok) {
      importError.value = result.error || "导入失败。";
      return false;
    }
    ElMessage.success(`已回填 ${result.appliedFragments} 个片段与 ${result.appliedCorrections} 条单元格核定指纹。`);
    return true;
  }

  function resetAfterNotFound(latestExpectedSource?: ReviewExpectedSourceRequest | null): void {
    clearPending(options.jobId.value);
    error.value = null;
    lastResult.value = null;
    form.requestId = generateCanonicalUuid();
    form.needsReconcile = false;
    form.notFoundOnReconcile = false;
    if (latestExpectedSource) {
      form.expectedSource = { ...latestExpectedSource };
    }
  }

  async function submit(): Promise<DocumentJobNewGenerationResponse | null> {
    if (!form.expectedSource) {
      return null;
    }
    const trimmedNote = form.note.trim();
    if (!trimmedNote || trimmedNote.length > 1000) {
      ElMessage.warning("请填写 1 至 1000 字的核定原因说明。");
      return null;
    }
    const checked = validation.value;
    if (!checked.valid) {
      ElMessage.warning(checked.errors[0] || "请先修正核定字段校验错误。");
      return null;
    }

    const targetJobId = options.jobId.value;
    if (!form.requestId) {
      form.requestId = generateCanonicalUuid();
    }
    submitting.value = true;
    error.value = null;
    form.notFoundOnReconcile = false;

    savePending(targetJobId, {
      requestId: form.requestId,
      note: trimmedNote,
      expectedSource: form.expectedSource,
      needsReconcile: true,
    });

    try {
      const response = await documentJobsApi.requestNewGeneration(targetJobId, {
        request_id: form.requestId,
        note: trimmedNote,
        expected_source: form.expectedSource,
        action: "replay_table_value_columns",
        table_value_column_reviews: checked.reviews,
      });
      clearPending(targetJobId);
      form.needsReconcile = false;
      lastResult.value = response;
      ElMessage.success(
        response.replayed
          ? `已对账表格值列核定新代请求（第 ${response.accepted_generation + 1} 代）。`
          : `已提交表格值列核定新代请求（第 ${response.accepted_generation + 1} 代），后台将从同源 MinerU 存档重算。`,
      );
      await options.onAccepted?.(response);
      return response;
    } catch (caught) {
      const normalized = normalizeApiError(caught);
      error.value = normalized;
      if (isAmbiguousWriteError(normalized) || normalized.accepted === true) {
        form.needsReconcile = true;
        savePending(targetJobId, {
          requestId: normalized.generationRequestId || form.requestId,
          note: trimmedNote,
          expectedSource: form.expectedSource,
          needsReconcile: true,
        });
        if (normalized.generationRequestId) {
          form.requestId = normalized.generationRequestId;
        }
      } else {
        clearPending(targetJobId);
        form.needsReconcile = false;
      }
      return null;
    } finally {
      submitting.value = false;
    }
  }

  async function reconcile(): Promise<DocumentJobNewGenerationResponse | null> {
    if (!form.requestId) {
      return null;
    }
    const targetJobId = options.jobId.value;
    reconciling.value = true;
    error.value = null;
    form.notFoundOnReconcile = false;
    try {
      const response = await documentJobsApi.getGenerationRequest(targetJobId, form.requestId);
      clearPending(targetJobId);
      form.needsReconcile = false;
      lastResult.value = response;
      ElMessage.success(`对账完成：核定新代已被受理（第 ${response.accepted_generation + 1} 代）。`);
      await options.onAccepted?.(response);
      return response;
    } catch (caught) {
      const normalized = normalizeApiError(caught);
      error.value = normalized;
      if (normalized.status === 404) {
        form.notFoundOnReconcile = true;
      }
      return null;
    } finally {
      reconciling.value = false;
    }
  }

  return {
    visible,
    submitting,
    reconciling,
    loadingSourceHash,
    error,
    importError,
    importJsonText,
    lastResult,
    fragments,
    activeFragmentId,
    activeFragment,
    form,
    validation,
    canSubmit,
    open,
    close,
    applyImportedJson,
    submit,
    reconcile,
    resetAfterNotFound,
  };
}

export type TableValueColumnReviewController = ReturnType<typeof useTableValueColumnReview>;
