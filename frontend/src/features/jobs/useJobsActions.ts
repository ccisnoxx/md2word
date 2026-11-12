// 任务列表的行级动作、批量动作、下载链接与批量结果 owner；列表刷新委托给 useJobsList。
import { computed, nextTick, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { Router } from "vue-router";

import type { DocumentJobActionId, DocumentJobBulkResponse, DocumentJobResponse } from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import { normalizeJobsBatchResult } from "@/utils/batchResults";
import { copyDownloadLink, openDownloadLink, type DownloadLinkNotice } from "@/utils/download";
import { normalizeApiError } from "@/utils/errors";
import {
  canArchiveDocumentJob,
  canCancelDocumentJob,
  canRetryDocumentJob,
  documentJobDownloadNotice,
  formatDateTime,
  shouldShowDocumentJobAction,
} from "@/utils/format";
import type { JobsList } from "./useJobsList";

export function useJobsActions(list: Pick<JobsList, "error" | "loadJobs" | "selectedJobs">, router: Router) {
  const { error, loadJobs, selectedJobs } = list;
  const batchLoading = ref(false);
  const batchResult = ref<DocumentJobBulkResponse | null>(null);
  const batchResultLabel = ref("");
  const batchResultExpanded = ref(false);
  const lastDownloadLink = ref<DownloadLinkNotice | null>(null);
  const actionPending = ref<Record<string, DocumentJobActionId | undefined>>({});

  const selectedRetryableJobs = computed(() => selectedJobs.value.filter(canRetryDocumentJob));
  const selectedCancelableJobs = computed(() => selectedJobs.value.filter(canCancelDocumentJob));
  const selectedArchivableJobs = computed(() => selectedJobs.value.filter(canArchiveDocumentJob));
  const normalizedBatchResult = computed(() =>
    batchResult.value ? normalizeJobsBatchResult(batchResultLabel.value, batchResult.value) : null,
  );

  function clearBatchResult(): void {
    batchResult.value = null;
  }

  async function handleDownload(job: DocumentJobResponse): Promise<void> {
    if (isActionBusy(job.id)) {
      return;
    }
    setActionPending(job.id, "download");
    try {
      const response = await documentJobsApi.createDownloadUrl(job.id);
      lastDownloadLink.value = {
        label: `任务 ${job.id} 的下载链接已生成`,
        url: response.download_url,
        expiresAt: response.expires_at,
        fileName: response.file.original_filename,
        notice: documentJobDownloadNotice(response),
      };
      await nextTick();
      const opened = openDownloadLink(response.download_url);
      if (opened) {
        ElMessage.warning(`${lastDownloadLink.value.notice}。下载链接已生成，有效期至 ${formatDateTime(response.expires_at)}。`);
      } else {
        ElMessage.warning("浏览器可能拦截了新窗口，页面已显示下载链接。");
      }
    } catch (caught) {
      await handleActionError(caught);
    } finally {
      clearActionPending(job.id);
    }
  }

  async function handleActionError(caught: unknown): Promise<void> {
    const normalized = normalizeApiError(caught);
    error.value = normalized;
    if (normalized.status === 403 || normalized.status === 409 || normalized.status === 503) {
      await loadJobs({ preserveError: true });
      error.value = normalized;
    }
  }

  async function copyLastDownloadLink(): Promise<void> {
    if (!lastDownloadLink.value) {
      return;
    }
    const copied = await copyDownloadLink(lastDownloadLink.value.url);
    if (copied) {
      ElMessage.success("下载链接已复制。");
      return;
    }
    ElMessage.warning("当前浏览器不支持自动复制。");
  }

  async function handleRetry(job: DocumentJobResponse): Promise<void> {
    await router.push({ path: `/jobs/${job.id}`, query: { retry: "1" } });
  }

  async function handleClone(job: DocumentJobResponse): Promise<void> {
    if (isActionBusy(job.id)) {
      return;
    }
    try {
      await ElMessageBox.confirm(
        "重新发起会基于当前任务的源 PDF 创建一个新任务，不会修改原任务，也不会作为 retry 计数。",
        "重新发起为新任务",
        {
          confirmButtonText: "创建新任务",
          cancelButtonText: "返回",
          type: "info",
        },
      );
      setActionPending(job.id, "clone");
      const response = await documentJobsApi.clone(job.id, { reason: "frontend clone from jobs list" });
      ElMessage.success("已创建新任务。");
      await router.push(`/jobs/${response.job_id}`);
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      await handleActionError(caught);
    } finally {
      clearActionPending(job.id);
    }
  }

  async function handleCancel(job: DocumentJobResponse): Promise<void> {
    if (isActionBusy(job.id)) {
      return;
    }
    try {
      await ElMessageBox.confirm(
        "取消会将任务标记为 canceled 并停止后续处理；如果任务已进入外部服务，系统不承诺强制中断该外部处理。文件和事件记录会保留。",
        "取消任务",
        {
          confirmButtonText: "确认取消",
          cancelButtonText: "返回",
          type: "warning",
        },
      );
      setActionPending(job.id, "cancel");
      await documentJobsApi.cancel(job.id);
      ElMessage.success("任务已取消。");
      await loadJobs();
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      await handleActionError(caught);
    } finally {
      clearActionPending(job.id);
    }
  }

  async function handleArchive(job: DocumentJobResponse): Promise<void> {
    if (isActionBusy(job.id)) {
      return;
    }
    try {
      await ElMessageBox.confirm(
        "归档只会把终态任务从默认列表隐藏，不会删除源文件、结果文件或事件记录。开启“含归档”后仍可查看。",
        "归档任务",
        {
          confirmButtonText: "确认归档",
          cancelButtonText: "返回",
          type: "info",
        },
      );
      setActionPending(job.id, "archive");
      await documentJobsApi.archive(job.id);
      ElMessage.success("任务已归档。");
      await loadJobs();
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      await handleActionError(caught);
    } finally {
      clearActionPending(job.id);
    }
  }

  async function handleUnarchive(job: DocumentJobResponse): Promise<void> {
    if (isActionBusy(job.id)) {
      return;
    }
    try {
      await ElMessageBox.confirm(
        "取消归档会让任务重新出现在默认列表中，不会修改文件或事件记录。",
        "取消归档",
        {
          confirmButtonText: "确认取消归档",
          cancelButtonText: "返回",
          type: "info",
        },
      );
      setActionPending(job.id, "unarchive");
      await documentJobsApi.unarchive(job.id);
      ElMessage.success("任务已取消归档。");
      await loadJobs();
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      await handleActionError(caught);
    } finally {
      clearActionPending(job.id);
    }
  }

  async function handleDelete(job: DocumentJobResponse): Promise<void> {
    if (isActionBusy(job.id) || !shouldShowDocumentJobAction(job, "delete")) {
      return;
    }
    setActionPending(job.id, "delete");
    try {
      const preview = await documentJobsApi.previewDelete(job.id);
      const deleteCount = preview.totals.delete || 0;
      const keepCount = preview.totals.keep || 0;
      await ElMessageBox.confirm(
        `删除任务会隐藏该任务并清理可安全删除的关联文件。将删除 ${deleteCount} 个文件，保留 ${keepCount} 个文件；任务 metadata、事件和 audit 会保留。`,
        "删除任务",
        {
          confirmButtonText: "确认删除",
          cancelButtonText: "返回",
          type: "warning",
        },
      );
      await documentJobsApi.delete(job.id, {
        preview_hash: preview.preview_hash,
      });
      ElMessage.success("任务已删除。");
      await loadJobs();
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      await handleActionError(caught);
    } finally {
      clearActionPending(job.id);
    }
  }

  // 调用后端批量重试接口，避免前端逐个发起单任务请求。
  async function handleBatchRetry(): Promise<void> {
    const targets = selectedRetryableJobs.value;
    if (!targets.length) {
      return;
    }
    batchLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.bulkRetry({
        job_ids: targets.map((job) => job.id),
        reason: "frontend batch retry",
      });
      showBatchResult("批量重试", response);
      await loadJobs();
    } catch (caught) {
      await handleActionError(caught);
    } finally {
      batchLoading.value = false;
    }
  }

  // 调用后端批量归档接口，并保留现有归档确认语义。
  async function handleBatchArchive(): Promise<void> {
    const targets = selectedArchivableJobs.value;
    if (!targets.length) {
      return;
    }
    try {
      await ElMessageBox.confirm(
        `将归档 ${targets.length} 个终态任务。归档不是删除，源文件、结果文件和事件记录会保留。`,
        "批量归档任务",
        {
          confirmButtonText: "确认归档",
          cancelButtonText: "返回",
          type: "info",
        },
      );
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      error.value = normalizeApiError(caught);
      return;
    }
    batchLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.bulkArchive({
        job_ids: targets.map((job) => job.id),
      });
      showBatchResult("批量归档", response);
      await loadJobs();
    } catch (caught) {
      await handleActionError(caught);
    } finally {
      batchLoading.value = false;
    }
  }

  async function handleBatchCancel(): Promise<void> {
    const targets = selectedCancelableJobs.value;
    if (!targets.length) {
      return;
    }
    try {
      await ElMessageBox.confirm(
        `将取消 ${targets.length} 个未终态任务。取消不会删除源文件、结果文件或事件记录。`,
        "批量取消任务",
        {
          confirmButtonText: "确认取消",
          cancelButtonText: "返回",
          type: "warning",
        },
      );
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      error.value = normalizeApiError(caught);
      return;
    }
    batchLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.bulkCancel({
        job_ids: targets.map((job) => job.id),
      });
      showBatchResult("批量取消", response);
      await loadJobs();
    } catch (caught) {
      await handleActionError(caught);
    } finally {
      batchLoading.value = false;
    }
  }

  // 用后端聚合结果展示批量操作的成功、失败数量和失败明细。
  function showBatchResult(label: string, result: DocumentJobBulkResponse): void {
    batchResultLabel.value = label;
    batchResult.value = result;
    batchResultExpanded.value = result.failed > 0;
  }

  function setActionPending(jobId: string, action: DocumentJobActionId): void {
    actionPending.value = { ...actionPending.value, [jobId]: action };
  }

  function clearActionPending(jobId: string): void {
    const next = { ...actionPending.value };
    delete next[jobId];
    actionPending.value = next;
  }

  function isActionBusy(jobId: string): boolean {
    return Boolean(actionPending.value[jobId]);
  }
  return {
    batchLoading,
    batchResult,
    batchResultExpanded,
    lastDownloadLink,
    actionPending,
    selectedRetryableJobs,
    selectedCancelableJobs,
    selectedArchivableJobs,
    normalizedBatchResult,
    clearBatchResult,
    handleDownload,
    copyLastDownloadLink,
    handleRetry,
    handleClone,
    handleCancel,
    handleArchive,
    handleUnarchive,
    handleDelete,
    handleBatchRetry,
    handleBatchArchive,
    handleBatchCancel,
  };
}

export type JobsActions = ReturnType<typeof useJobsActions>;
