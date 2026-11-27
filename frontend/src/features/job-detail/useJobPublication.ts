// 文件：frontend/src/features/job-detail/useJobPublication.ts
// 用途：管理任务详情页「发布与交付」Tab 的发布前检查、幂等发布提交与不可变最终件下载。
import { computed, reactive, ref, watch, type Ref } from "vue";
import { ElMessage } from "element-plus";

import { documentJobsApi } from "@/api/documentJobs";
import type {
  DocumentJobResponse,
  DocumentPublicationDownloadUrlResponse,
  DocumentPublicationRecordResponse,
  DocumentPublicationsResponse,
  PublicationExpectedSource,
} from "@/api/types";
import { copyDownloadLink, openDownloadLink } from "@/utils/download";
import { isAmbiguousWriteError, normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";
import { generateCanonicalUuid } from "@/utils/uuid";

const PUBLISH_STORAGE_PREFIX = "md2word.publish_req.";

type PersistedPublishPending = {
  requestId: string;
  note: string;
  expectedSource: PublicationExpectedSource;
};

function readPendingPublish(jobId: string): PersistedPublishPending | null {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(`${PUBLISH_STORAGE_PREFIX}${jobId}`);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedPublishPending>;
    if (typeof parsed.requestId === "string" && parsed.requestId.length === 36 && parsed.expectedSource) {
      return {
        requestId: parsed.requestId,
        note: typeof parsed.note === "string" ? parsed.note : "",
        expectedSource: parsed.expectedSource,
      };
    }
  } catch {
    return null;
  }
  return null;
}

function savePendingPublish(jobId: string, state: PersistedPublishPending): void {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  try {
    window.sessionStorage.setItem(`${PUBLISH_STORAGE_PREFIX}${jobId}`, JSON.stringify(state));
  } catch {
    // 忽略受限存储写入失败，内存仍保留同一幂等键。
  }
}

function clearPendingPublish(jobId: string): void {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  try {
    window.sessionStorage.removeItem(`${PUBLISH_STORAGE_PREFIX}${jobId}`);
  } catch {
    // 忽略清理异常。
  }
}

export function useJobPublication(options: {
  jobId: Ref<string>;
  job: Ref<DocumentJobResponse | null>;
  activeTab: Ref<string>;
  onPublished?: () => void | Promise<void>;
}) {
  const publications = ref<DocumentPublicationsResponse | null>(null);
  const loading = ref(false);
  const error = ref<ApiClientError | null>(null);
  const publishDialogVisible = ref(false);
  const publishing = ref(false);
  const publishError = ref<ApiClientError | null>(null);
  const downloadingPublicationId = ref<string | null>(null);
  const lastFinalDeliveryDownload = ref<DocumentPublicationDownloadUrlResponse | null>(null);

  const publishForm = reactive({
    requestId: "",
    note: "",
    expectedSource: null as PublicationExpectedSource | null,
    ambiguousFailure: false,
  });

  let requestSeq = 0;

  const publishAction = computed(
    () => publications.value?.available_actions.publish ?? options.job.value?.available_actions.publish ?? null,
  );
  const newGenerationActionState = computed(
    () => publications.value?.available_actions.new_generation ?? options.job.value?.available_actions.new_generation ?? null,
  );

  // 严格以后端 available_actions.publish.enabled 为唯一发布按钮门禁，绝不在前端重算资格。
  const publishEnabled = computed(
    () => publishAction.value?.enabled === true && Boolean(publications.value?.expected_source),
  );
  const canSubmitPublish = computed(() =>
    Boolean(
      publishForm.expectedSource
      && publishForm.requestId
      && publishForm.note.trim().length >= 1
      && publishForm.note.trim().length <= 1000
      && !publishing.value,
    ),
  );

  async function load(targetJobId = options.jobId.value): Promise<void> {
    if (!targetJobId) {
      return;
    }
    const seq = ++requestSeq;
    loading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.listPublications(targetJobId);
      if (seq === requestSeq && targetJobId === options.jobId.value) {
        publications.value = response;
      }
    } catch (caught) {
      if (seq === requestSeq && targetJobId === options.jobId.value) {
        error.value = normalizeApiError(caught);
      }
    } finally {
      if (seq === requestSeq && targetJobId === options.jobId.value) {
        loading.value = false;
      }
    }
  }

  function openPublishDialog(): void {
    const source = publications.value?.expected_source;
    if (!source) {
      ElMessage.warning("尚未读取到最新发布来源，请先刷新发布状态。");
      return;
    }
    publishError.value = null;
    const saved = readPendingPublish(options.jobId.value);
    if (saved) {
      // 上次发布写请求结果未知时，必须恢复同一 UUID 重放，绝不自动更换幂等键。
      publishForm.requestId = saved.requestId;
      publishForm.note = saved.note;
      publishForm.expectedSource = saved.expectedSource;
      publishForm.ambiguousFailure = true;
    } else {
      publishForm.requestId = generateCanonicalUuid();
      publishForm.note = "";
      publishForm.expectedSource = { ...source };
      publishForm.ambiguousFailure = false;
    }
    publishDialogVisible.value = true;
  }

  function resetPublishKey(): void {
    clearPendingPublish(options.jobId.value);
    publishError.value = null;
    publishForm.ambiguousFailure = false;
    publishForm.requestId = generateCanonicalUuid();
    if (publications.value?.expected_source) {
      publishForm.expectedSource = { ...publications.value.expected_source };
    }
  }

  async function submitPublish(): Promise<boolean> {
    if (!publishForm.expectedSource) {
      return false;
    }
    const trimmedNote = publishForm.note.trim();
    if (!trimmedNote || trimmedNote.length > 1000) {
      ElMessage.warning("请填写 1 至 1000 字的发布备注。");
      return false;
    }
    const targetJobId = options.jobId.value;
    if (!publishForm.requestId) {
      publishForm.requestId = generateCanonicalUuid();
    }
    publishing.value = true;
    publishError.value = null;
    savePendingPublish(targetJobId, {
      requestId: publishForm.requestId,
      note: trimmedNote,
      expectedSource: publishForm.expectedSource,
    });
    try {
      await documentJobsApi.publish(targetJobId, {
        request_id: publishForm.requestId,
        note: trimmedNote,
        expected_source: publishForm.expectedSource,
      });
      clearPendingPublish(targetJobId);
      publishForm.ambiguousFailure = false;
      publishDialogVisible.value = false;
      ElMessage.success("正式发布成功，已登记不可变最终交付件记录。");
      await load(targetJobId);
      await options.onPublished?.();
      return true;
    } catch (caught) {
      const normalized = normalizeApiError(caught);
      publishError.value = normalized;
      if (isAmbiguousWriteError(normalized)) {
        publishForm.ambiguousFailure = true;
      } else {
        // 明确 4xx（校验失败/409 来源冲突/权限不足）未提交发布，允许调整或刷新后重新提交。
        clearPendingPublish(targetJobId);
        publishForm.ambiguousFailure = false;
      }
      return false;
    } finally {
      publishing.value = false;
    }
  }

  async function downloadFinalDelivery(record: DocumentPublicationRecordResponse): Promise<void> {
    const targetJobId = options.jobId.value;
    if (!targetJobId) {
      return;
    }
    downloadingPublicationId.value = record.publication_id;
    error.value = null;
    try {
      const response = await documentJobsApi.createPublicationDownloadUrl(targetJobId, record.publication_id);
      lastFinalDeliveryDownload.value = response;
      const opened = openDownloadLink(response.download_url);
      if (opened) {
        ElMessage.success(`最终交付件下载链接已签发，有效期至 ${formatDateTime(response.expires_at)}。`);
      } else {
        ElMessage.warning("浏览器拦截了新窗口，请在下方最终交付件提示栏点击打开链接。");
      }
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      downloadingPublicationId.value = null;
    }
  }

  async function copySha256(checksum: string): Promise<void> {
    const copied = await copyDownloadLink(checksum);
    if (copied) {
      ElMessage.success("SHA256 校验值已复制。");
      return;
    }
    ElMessage.warning("当前浏览器不支持自动复制。");
  }

  function reset(): void {
    requestSeq += 1;
    publications.value = null;
    loading.value = false;
    error.value = null;
    publishDialogVisible.value = false;
    publishError.value = null;
    lastFinalDeliveryDownload.value = null;
  }

  // 仅当用户进入「发布与交付」Tab 时按需拉取 /publications，避免无关 Tab 与旧烟雾用例额外请求。
  watch(
    () => [options.activeTab.value, options.jobId.value, options.job.value?.retry_count, options.job.value?.result_file_id] as const,
    ([tab], previous) => {
      const [prevTab, prevJobId, prevRetry, prevResult] = previous ?? [];
      if (
        previous
        && (options.jobId.value !== prevJobId
          || options.job.value?.retry_count !== prevRetry
          || options.job.value?.result_file_id !== prevResult)
      ) {
        publications.value = null;
        lastFinalDeliveryDownload.value = null;
      }
      if (tab === "publication" && options.jobId.value && (tab !== prevTab || !publications.value)) {
        void load(options.jobId.value);
      }
    },
    { immediate: true },
  );

  return {
    publications,
    loading,
    error,
    publishAction,
    newGenerationActionState,
    publishEnabled,
    publishDialogVisible,
    publishing,
    publishError,
    publishForm,
    canSubmitPublish,
    downloadingPublicationId,
    lastFinalDeliveryDownload,
    load,
    openPublishDialog,
    resetPublishKey,
    submitPublish,
    downloadFinalDelivery,
    copySha256,
    reset,
  };
}

export type JobPublicationState = ReturnType<typeof useJobPublication>;
