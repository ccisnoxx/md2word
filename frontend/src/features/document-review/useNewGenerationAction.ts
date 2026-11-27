// 文件：frontend/src/features/document-review/useNewGenerationAction.ts
// 用途：封装 Admin 标准同任务新代（POST /new-generation）与客户端 UUID 幂等键对账（GET /generation-requests/{id}）。
import { computed, reactive, ref, type Ref } from "vue";
import { ElMessage } from "element-plus";

import { documentJobsApi } from "@/api/documentJobs";
import type {
  DocumentJobNewGenerationResponse,
  ReviewExpectedSourceRequest,
} from "@/api/types";
import { isAmbiguousWriteError, normalizeApiError, type ApiClientError } from "@/utils/errors";
import { generateCanonicalUuid } from "@/utils/uuid";

const STORAGE_PREFIX = "md2word.new_gen_req.";

type PersistedPendingRequest = {
  requestId: string;
  note: string;
  expectedSource: ReviewExpectedSourceRequest;
  needsReconcile: boolean;
};

function storageKey(jobId: string): string {
  return `${STORAGE_PREFIX}${jobId}`;
}

function loadPendingRequest(jobId: string): PersistedPendingRequest | null {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(storageKey(jobId));
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedPendingRequest>;
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

function savePendingRequest(jobId: string, state: PersistedPendingRequest): void {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  try {
    window.sessionStorage.setItem(storageKey(jobId), JSON.stringify(state));
  } catch {
    // 忽略受限环境写入失败，内存状态仍保留本次幂等键。
  }
}

function clearPendingRequest(jobId: string): void {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  try {
    window.sessionStorage.removeItem(storageKey(jobId));
  } catch {
    // 忽略清理失败。
  }
}

export function useNewGenerationAction(options: {
  jobId: Ref<string>;
  onAccepted?: (response: DocumentJobNewGenerationResponse) => void | Promise<void>;
}) {
  const visible = ref(false);
  const submitting = ref(false);
  const reconciling = ref(false);
  const error = ref<ApiClientError | null>(null);
  const lastResult = ref<DocumentJobNewGenerationResponse | null>(null);

  const form = reactive({
    requestId: "",
    note: "",
    expectedSource: null as ReviewExpectedSourceRequest | null,
    needsReconcile: false,
    notFoundOnReconcile: false,
  });

  const canSubmit = computed(() =>
    Boolean(
      form.expectedSource
      && form.requestId
      && form.note.trim().length >= 1
      && form.note.trim().length <= 1000
      && !submitting.value
      && !reconciling.value
      && !form.needsReconcile,
    ),
  );

  function open(expectedSource: ReviewExpectedSourceRequest): void {
    error.value = null;
    lastResult.value = null;
    form.notFoundOnReconcile = false;
    const saved = loadPendingRequest(options.jobId.value);
    if (saved && saved.needsReconcile) {
      // 上次写请求结果未知时，必须恢复同一幂等键进入对账，绝不自动换 key。
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
  }

  function close(): void {
    visible.value = false;
  }

  function resetAfterNotFound(latestExpectedSource?: ReviewExpectedSourceRequest | null): void {
    clearPendingRequest(options.jobId.value);
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
      ElMessage.warning("请填写 1 至 1000 字的新代原因说明。");
      return null;
    }
    const targetJobId = options.jobId.value;
    if (!form.requestId) {
      form.requestId = generateCanonicalUuid();
    }
    submitting.value = true;
    error.value = null;
    form.notFoundOnReconcile = false;

    // 请求发出前持久化同一 UUID，防止 503/500 或网络中断后丢失幂等键。
    savePendingRequest(targetJobId, {
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
      });
      clearPendingRequest(targetJobId);
      form.needsReconcile = false;
      lastResult.value = response;
      ElMessage.success(
        response.replayed
          ? `已对账同一新代请求（第 ${response.accepted_generation + 1} 代）。`
          : `已受理同任务新代请求（第 ${response.accepted_generation + 1} 代）。`,
      );
      await options.onAccepted?.(response);
      return response;
    } catch (caught) {
      const normalized = normalizeApiError(caught);
      error.value = normalized;
      if (isAmbiguousWriteError(normalized) || normalized.accepted === true) {
        form.needsReconcile = true;
        savePendingRequest(targetJobId, {
          requestId: normalized.generationRequestId || form.requestId,
          note: trimmedNote,
          expectedSource: form.expectedSource,
          needsReconcile: true,
        });
        if (normalized.generationRequestId) {
          form.requestId = normalized.generationRequestId;
        }
      } else {
        // 明确 4xx（参数/冲突/权限拒绝）说明请求未被受理，可保留输入供用户修正或刷新来源。
        clearPendingRequest(targetJobId);
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
      clearPendingRequest(targetJobId);
      form.needsReconcile = false;
      lastResult.value = response;
      ElMessage.success(`对账完成：新代请求已被受理（第 ${response.accepted_generation + 1} 代）。`);
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
    error,
    lastResult,
    form,
    canSubmit,
    open,
    close,
    submit,
    reconcile,
    resetAfterNotFound,
  };
}

export type NewGenerationAction = ReturnType<typeof useNewGenerationAction>;
