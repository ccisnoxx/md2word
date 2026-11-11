// 任务恢复 owner：registry preview、确认后复用 document-jobs 既有端点或 replay 执行。
import { computed, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { documentJobsApi } from "@/api/documentJobs";
import { opsRecoveryActionsApi } from "@/api/opsRecoveryActions";
import type {
  DocumentJobResponse,
  OpsRecoveryActionPreviewResponse,
} from "@/api/types";
import { normalizeApiError } from "@/utils/errors";
import {
  type DetailItem,
  type OpsJobRecoveryAction,
  jobRecoveryActionId,
  jobRecoveryActionLabel,
  jobRecoveryActionKey,
  readNumber,
  readBoolean,
  booleanLabel,
  displayValue,
  secondsLabel,
} from "./opsDashboardFormat";
import type { OpsDashboardData } from "./useOpsDashboardData";

export function useOpsJobRecovery(
  data: Pick<OpsDashboardData, "error" | "loadDashboard">,
) {
  const { error, loadDashboard } = data;
  const jobRecoveryPreview = ref<OpsRecoveryActionPreviewResponse | null>(null);
  const selectedJobRecoveryAction = ref<OpsJobRecoveryAction | null>(null);
  const jobRecoveryPreviewLoadingKey = ref("");
  const jobRecoveryExecuting = ref(false);

  const jobRecoveryRiskItems = computed(() => {
    const risk = jobRecoveryPreview.value?.risk_flags;
    if (!risk) {
      return [];
    }
    return [
      { label: "metadata", value: risk.mutates_metadata },
      { label: "queue", value: risk.mutates_queue },
      { label: "provider", value: risk.calls_provider },
      { label: "notification", value: risk.sends_notification },
      { label: "delete", value: risk.deletes_data },
    ];
  });

  const jobRecoveryTargetSummaryItems = computed<DetailItem[]>(() => {
    const summary = jobRecoveryPreview.value?.target.summary || {};
    return [
      { label: "callback replayable", value: displayValue(summary["callback_replayable_messages"]) },
      { label: "callback failed", value: displayValue(summary["callback_failed_messages"]) },
      { label: "oldest callback", value: secondsLabel(readNumber(summary["callback_oldest_replayable_age_seconds"])) },
      { label: "stale job", value: booleanLabel(readBoolean(summary["stale_job_detected"])) },
      { label: "worker backend", value: displayValue(summary["worker_backend"]) },
    ];
  });

  const canExecutePreviewedJobRecovery = computed(() => {
    const preview = jobRecoveryPreview.value;
    if (!preview || !selectedJobRecoveryAction.value || jobRecoveryExecuting.value) {
      return false;
    }
    return preview.eligible
      && preview.target.exists
      && !preview.risk_flags.calls_provider
      && !preview.risk_flags.sends_notification
      && !preview.risk_flags.deletes_data;
  });

  function isPreviewingJobAction(jobId: string, action: OpsJobRecoveryAction): boolean {
    return jobRecoveryPreviewLoadingKey.value === jobRecoveryActionKey(jobId, action);
  }

  function isExecutingJobAction(jobId: string, action: OpsJobRecoveryAction): boolean {
    return jobRecoveryExecuting.value
      && selectedJobRecoveryAction.value === action
      && jobRecoveryPreview.value?.target.target_id === jobId;
  }

  async function previewJobRecoveryAction(job: DocumentJobResponse, action: OpsJobRecoveryAction): Promise<void> {
    jobRecoveryPreviewLoadingKey.value = jobRecoveryActionKey(job.id, action);
    error.value = null;
    try {
      selectedJobRecoveryAction.value = action;
      jobRecoveryPreview.value = await opsRecoveryActionsApi.preview({
        action_id: jobRecoveryActionId(action),
        target_type: "document_job",
        target_id: job.id,
      });
      if (!jobRecoveryPreview.value.eligible) {
        ElMessage.warning(`当前任务不可${jobRecoveryActionLabel(action)}。`);
      }
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      jobRecoveryPreviewLoadingKey.value = "";
    }
  }

  async function executePreviewedJobRecovery(): Promise<void> {
    const preview = jobRecoveryPreview.value;
    const action = selectedJobRecoveryAction.value;
    if (!preview || !action || !canExecutePreviewedJobRecovery.value) {
      return;
    }
    const jobId = preview.target.target_id;
    const confirmationText = action === "replay"
      ? `将对任务 ${jobId} 执行重放。该操作只投递 Worker 或清理终态 callback，不会在本次 HTTP 请求中调用 provider。`
      : `将对任务 ${jobId} 执行${jobRecoveryActionLabel(action)}。该操作复用 document-jobs 既有端点，不会调用 provider 或删除文件。`;
    try {
      await ElMessageBox.confirm(
        confirmationText,
        `确认${jobRecoveryActionLabel(action)}`,
        { type: action === "cancel" ? "warning" : "info" },
      );
    } catch {
      return;
    }

    jobRecoveryExecuting.value = true;
    error.value = null;
    try {
      if (action === "retry") {
        await documentJobsApi.retry(jobId, { reason: "ops dashboard recovery preview" });
      } else if (action === "cancel") {
        await documentJobsApi.cancel(jobId);
      } else if (action === "archive") {
        await documentJobsApi.archive(jobId);
      } else {
        const response = await opsRecoveryActionsApi.execute({
          action_id: jobRecoveryActionId(action),
          target_type: "document_job",
          target_id: jobId,
          reason: "ops dashboard replay execution",
        });
        ElMessage.success(
          `Replay 已执行：queued=${response.queued_task_id || "none"}，ignored=${response.ignored_callback_messages}。`,
        );
      }
      if (action !== "replay") {
        ElMessage.success(`任务已${jobRecoveryActionLabel(action)}。`);
      }
      jobRecoveryPreview.value = null;
      selectedJobRecoveryAction.value = null;
      await loadDashboard();
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      jobRecoveryExecuting.value = false;
    }
  }

  return {
    jobRecoveryPreview,
    selectedJobRecoveryAction,
    jobRecoveryPreviewLoadingKey,
    jobRecoveryExecuting,
    jobRecoveryRiskItems,
    jobRecoveryTargetSummaryItems,
    canExecutePreviewedJobRecovery,
    isPreviewingJobAction,
    isExecutingJobAction,
    previewJobRecoveryAction,
    executePreviewedJobRecovery,
  };
}

export type OpsJobRecovery = ReturnType<typeof useOpsJobRecovery>;
