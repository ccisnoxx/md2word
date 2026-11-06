import { computed } from "vue";
import type { DocumentFileSummaryResponse, DocumentJobActionId, DocumentJobResponse, DocumentJobStage } from "@/api/types";
import {
  buildDocumentJobDiagnosticRecommendation,
  buildDocumentJobQualityEvidence,
  formatDateTime,
  documentJobActionDisabledReason,
  isActiveJobStatus,
  isDocumentJobActionEnabled,
  jobStageText,
  jobStatusText,
  shouldShowDocumentJobAction,
} from "@/utils/format";
import { readDegradedPages, readSourcePageCounts, sourcePageCountLine } from "@/utils/degradedPages";
import { usesTranslationResources, parseDate, secondsLabel, canDownloadFile, fileAvailabilityText } from "./jobDetailFormat";
import type { JobDetailData } from "./useJobDetailData";
import type { JobDetailReviewHints } from "./useJobDetailReviewHints";
import type { JobDetailResources } from "./useJobDetailResources";
import type { JobDetailBatches } from "./useJobDetailBatches";

export function useJobDetailDiagnostics(
  data: Pick<
    JobDetailData,
    | "job"
    | "events"
    | "files"
    | "callbackSummary"
    | "filesLoading"
    | "callbackSummaryLoading"
    | "eventLevelFilter"
    | "eventStageFilter"
    | "error"
    | "eventsError"
    | "filesError"
    | "callbackSummaryError"
    | "translationBatchesError"
    | "reviewHintsAvailable"
  >,
  review: Pick<JobDetailReviewHints, "reviewHintsHaveWarnings" | "reviewHintNotice">,
  resources: Pick<JobDetailResources, "sourceFilename">,
  batches: Pick<JobDetailBatches, "translationBatchHealthText">
) {
  const {
    job,
    events,
    files,
    callbackSummary,
    filesLoading,
    callbackSummaryLoading,
    eventLevelFilter,
    eventStageFilter,
    error,
    eventsError,
    filesError,
    callbackSummaryError,
    translationBatchesError,
    reviewHintsAvailable,
  } = data;

  const { reviewHintsHaveWarnings, reviewHintNotice } = review;

  const { sourceFilename } = resources;

  const { translationBatchHealthText } = batches;

  type DiagnosticEvidenceItem = {
    label: string;
    value: string;
    helper: string;
    mono?: boolean;
  };

  const filteredEvents = computed(() =>
    events.value.filter((event) => {
      if (eventLevelFilter.value && event.level !== eventLevelFilter.value) {
        return false;
      }
      if (eventStageFilter.value && event.stage !== eventStageFilter.value) {
        return false;
      }
      return true;
    }),
  );

  const latestErrorEvent = computed(() => [...events.value].reverse().find((event) => event.level === "error") || null);
  const degradedPages = computed(() => readDegradedPages(job.value?.quality_summary));
  const sourcePageLine = computed(() => sourcePageCountLine(readSourcePageCounts(job.value?.quality_summary)));
  const failureSummary = computed(() => {
    if (!job.value) {
      return "任务处理失败。";
    }
    const stage = job.value.failed_stage || job.value.stage || "unknown";
    const code = job.value.error_code || "unknown";
    return `任务在 ${jobStageText[stage as DocumentJobStage] || stage} 阶段失败，错误码 ${code}。`;
  });

  const failureHelpText = computed(() => {
    const code = job.value?.error_code || "";
    const retryAction = job.value?.available_actions.retry;
    const retryEnabled = retryAction?.enabled === true;
    const retryDisabledReason = retryAction?.disabled_reason || "后端未允许重试。";
    const retryGuidance = retryEnabled
      ? "当前后端允许重试，可从动作区发起。"
      : `当前后端未开放重试：${retryDisabledReason}`;
    if (code === "document_job_invalid_input") {
      return "输入文件或任务参数不满足后端校验。请换一个 PDF 或联系管理员确认输入限制。";
    }
    if (job.value?.failed_stage === "parsing") {
      return `PDF 解析阶段失败。${retryGuidance} 请把错误码和 trace_id 交给技术运营排查 MinerU 或文件内容问题。`;
    }
    if (job.value?.failed_stage === "uploading") {
      return `结果保存阶段失败，通常与对象存储或文件登记有关。${retryGuidance}`;
    }
    return retryGuidance;
  });

  const runningNotice = computed(() => {
    if (!job.value || !isActiveJobStatus(job.value.status)) {
      return "";
    }
    const timeoutAt = parseDate(job.value.timeout_at);
    if (timeoutAt && timeoutAt.getTime() <= Date.now()) {
      return "任务已超过预计超时时间，仍会继续轮询；请刷新事件流，必要时联系技术运营。";
    }
    const updatedAt = parseDate(job.value.updated_at);
    if (updatedAt && Date.now() - updatedAt.getTime() > 10 * 60 * 1000) {
      return "任务已超过 10 分钟没有状态更新，请查看事件流或稍后刷新。";
    }
    return "任务处理中，页面会自动轮询，终态后停止。";
  });

  const runningNoticeType = computed<"info" | "warning">(() => {
    if (!job.value || !isActiveJobStatus(job.value.status)) {
      return "info";
    }
    const timeoutAt = parseDate(job.value.timeout_at);
    const updatedAt = parseDate(job.value.updated_at);
    if ((timeoutAt && timeoutAt.getTime() <= Date.now()) || (updatedAt && Date.now() - updatedAt.getTime() > 10 * 60 * 1000)) {
      return "warning";
    }
    return "info";
  });

  const downloadHint = computed(() => {
    if (job.value?.status !== "succeeded") {
      return "";
    }
    return isDocumentJobActionEnabled(job.value, "download")
      ? "后端当前允许获取下载链接；下载分类与警告以当次签发结果为准。"
      : `当前不可下载：${documentJobActionDisabledReason(job.value, "download")}`;
  });

  const callbackSummaryItems = computed(() => [
    { label: "待处理 pending", value: String(callbackStatusCount("pending")) },
    { label: "处理中 running", value: String(callbackStatusCount("running")) },
    { label: "已处理 processed", value: String(callbackStatusCount("processed")) },
    { label: "失败 failed", value: String(callbackStatusCount("failed")) },
    { label: "已忽略 ignored", value: String(callbackStatusCount("ignored")) },
    { label: "可重放 replayable", value: String(callbackSummary.value?.replayable_count ?? 0) },
    { label: "最早可重放", value: secondsLabel(callbackSummary.value?.oldest_replayable_age_seconds ?? null) },
  ]);

  const latestTraceId = computed(() => latestErrorEvent.value?.trace_id || "-");
  const dispositionAlertType = computed<"success" | "warning" | "error" | "info">(() => {
    if (job.value?.status === "failed") {
      return "error";
    }
    if (job.value?.status === "succeeded") {
      return reviewHintsHaveWarnings.value ? "warning" : reviewHintsAvailable.value ? "success" : "info";
    }
    if (job.value?.status === "canceled" || isJobStale.value) {
      return "warning";
    }
    return "info";
  });

  const isJobStale = computed(() => {
    if (!job.value || !isActiveJobStatus(job.value.status)) {
      return false;
    }
    const updatedAt = parseDate(job.value.updated_at);
    return Boolean(updatedAt && Date.now() - updatedAt.getTime() > 10 * 60 * 1000);
  });

  const dispositionTitle = computed(() => {
    if (!job.value) {
      return "任务状态未知";
    }
    if (job.value.status === "failed") {
      return `任务失败：${job.value.error_code || "unknown_error"}`;
    }
    if (isJobStale.value) {
      return "任务长时间未更新";
    }
    if (job.value.status === "succeeded") {
      if (reviewHintsHaveWarnings.value) {
        return "任务已完成，存在需复核的警告提示";
      }
      return reviewHintsAvailable.value ? "任务已完成" : "任务已完成，复核提示尚未确认";
    }
    if (job.value.status === "canceled") {
      return "任务已取消，文件和事件记录仍保留";
    }
    return "任务处理中";
  });

  const dispositionDescription = computed(() => {
    if (!job.value) {
      return "";
    }
    if (job.value.status === "failed") {
      return `${failureHelpText.value} 查看下方动作禁用原因和诊断页签可获得更完整事件线索。`;
    }
    if (isJobStale.value) {
      return "该任务仍处于活跃状态，但更新时间已超过 10 分钟。请先刷新事件流和回调摘要，必要时联系技术运营。";
    }
    if (job.value.status === "succeeded") {
      return `任务结果已登记。${reviewHintNotice.value} ${downloadHint.value}`;
    }
    if (job.value.status === "canceled") {
      return "取消不会删除源文件、结果文件或事件记录；如需复跑，请按后端返回的重新发起可用性处理。";
    }
    return "页面会自动轮询任务详情。若进入停滞状态，会在这里显示排障提示。";
  });

  const dispositionFacts = computed(() => {
    if (!job.value) {
      return [];
    }
    return [
      { label: "状态", value: jobStatusText[job.value.status] || job.value.status },
      { label: "阶段", value: jobStageText[job.value.stage] || job.value.stage },
      { label: "进度", value: `${job.value.progress}%` },
      { label: "最近更新", value: formatDateTime(job.value.updated_at) },
      { label: "失败阶段", value: job.value.failed_stage ? jobStageText[job.value.failed_stage] || job.value.failed_stage : "-" },
      { label: "错误码", value: job.value.error_code || "-", mono: true },
      { label: "trace_id", value: latestTraceId.value, mono: true },
      { label: "回调", value: callbackHealthText.value },
      ...(usesTranslationResources(job.value) ? [{ label: "Provider 批次", value: translationBatchHealthText.value }] : []),
      { label: "质量", value: qualityDispositionText.value },
      { label: "文件", value: fileAvailabilitySummary.value },
    ];
  });

  const taskActionOrder: DocumentJobActionId[] = ["download", "retry", "clone", "cancel", "archive", "unarchive", "delete", "publish"];

  const actionSummaries = computed(() => {
    if (!job.value) {
      return [];
    }
    const labels: Record<DocumentJobActionId, string> = {
      download: "下载",
      retry: "重试",
      clone: "重新发起",
      cancel: "取消",
      archive: "归档",
      unarchive: "取消归档",
      delete: "删除",
      publish: "发布",
      new_generation: "发起新代",
    };
    return taskActionOrder
      .filter((action) => shouldShowDocumentJobAction(job.value as DocumentJobResponse, action))
      .map((action) => ({
        key: action,
        label: labels[action],
        enabled: isDocumentJobActionEnabled(job.value as DocumentJobResponse, action),
        reason: documentJobActionDisabledReason(job.value as DocumentJobResponse, action),
      }));
  });

  const callbackHealthText = computed(() => {
    if (callbackSummaryLoading.value) {
      return "加载中";
    }
    if (callbackSummaryError.value) {
      return "加载失败";
    }
    if (!callbackSummary.value) {
      return "暂无摘要";
    }
    const failed = callbackStatusCount("failed");
    const replayable = callbackSummary.value.replayable_count;
    if (failed || replayable) {
      return `failed ${failed} · replayable ${replayable}`;
    }
    return `pending ${callbackStatusCount("pending")} · processed ${callbackStatusCount("processed")}`;
  });

  const fileAvailabilitySummary = computed(() => {
    if (filesLoading.value) {
      return "加载中";
    }
    if (filesError.value) {
      return "加载失败";
    }
    if (!files.value.length) {
      return "暂无登记文件";
    }
    const downloadableCount = files.value.filter(canDownloadFile).length;
    return `${downloadableCount}/${files.value.length} 可下载`;
  });

  const qualityEvidence = computed(() => (job.value ? buildDocumentJobQualityEvidence(job.value, files.value) : null));
  const callbackProblemCount = computed(() =>
    (callbackSummary.value?.recent_problem_messages.length ?? 0)
    + callbackStatusCount("failed")
    + (callbackSummary.value?.replayable_count ?? 0),
  );

  const diagnosticRecommendation = computed(() => {
    if (!job.value) {
      return null;
    }
    return buildDocumentJobDiagnosticRecommendation({
      job: job.value,
      isStale: isJobStale.value,
      callbackProblemCount: callbackProblemCount.value,
      missingResult: qualityEvidence.value?.status === "missing_output",
      latestErrorMessage: latestErrorEvent.value?.message || null,
    });
  });

  const diagnosticSummaryFacts = computed(() => {
    if (!job.value) {
      return [];
    }
    return [
      { label: "当前结果", value: jobStatusText[job.value.status] || job.value.status },
      { label: "当前阶段", value: jobStageText[job.value.stage] || job.value.stage },
      { label: "停止/失败阶段", value: job.value.failed_stage ? jobStageText[job.value.failed_stage] || job.value.failed_stage : "-" },
      { label: "错误码", value: job.value.error_code || "-", mono: true },
      { label: "trace_id", value: latestTraceId.value, mono: true },
      { label: "最近更新", value: formatDateTime(job.value.updated_at) },
    ];
  });

  const diagnosticEvidenceItems = computed<DiagnosticEvidenceItem[]>(() => {
    if (!job.value) {
      return [];
    }
    const sourceFile = findJobFile("source_pdf", job.value.source_file_id);
    const resultFile = findJobFile("generated_word", job.value.result_file_id);
    const documentIrFile = findJobFile("document_ir", job.value.document_ir_file_id);
    const latestEvent = latestErrorEvent.value;
    return [
      {
        label: "源文件",
        value: sourceFile?.id || job.value.source_file_id || "-",
        helper: sourceFile?.original_filename || sourceFilename.value || "任务源文件 ID",
        mono: true,
      },
      {
        label: "生成结果",
        value: resultFile?.id || job.value.result_file_id || "-",
        helper: resultFile ? fileAvailabilityText(resultFile) : "未找到 generated_word 文件记录",
        mono: true,
      },
      {
        label: "DocumentIR",
        value: documentIrFile?.id || job.value.document_ir_file_id || "-",
        helper: documentIrFile ? fileAvailabilityText(documentIrFile) : "未找到 DocumentIR 文件记录",
        mono: true,
      },
      {
        label: "回调问题",
        value: callbackHealthText.value,
        helper: callbackSummaryError.value ? "回调摘要加载失败，可单独刷新" : "failed / replayable / pending 由后端摘要返回",
      },
      {
        label: "最近错误事件",
        value: latestEvent?.event_type || "-",
        helper: latestEvent
          ? `${latestEvent.message}${latestEvent.trace_id ? ` · trace_id=${latestEvent.trace_id}` : ""}`
          : "暂无错误级别（error）事件",
        mono: true,
      },
    ];
  });

  const diagnosticPreviewEvents = computed(() => {
    const important = events.value.filter((event) => event.level === "error" || event.level === "warning");
    const source = important.length ? important : events.value;
    return source.slice(-4).reverse();
  });

  const diagnosticRecoveryItems = computed(() => [
    filesError.value ? "files" : "",
    callbackSummaryError.value ? "callback" : "",
    eventsError.value ? "events" : "",
    translationBatchesError.value ? "translation_batches" : "",
  ].filter(Boolean));

  const qualityDispositionText = computed(() => {
    if (filesLoading.value) {
      return "加载中";
    }
    if (filesError.value) {
      return "加载失败";
    }
    if (!qualityEvidence.value) {
      return "暂无";
    }
    if (qualityEvidence.value.status === "manual_review_required_with_flags") {
      return `自动标记 ${qualityEvidence.value.flags.length} 项`;
    }
    if (qualityEvidence.value.status === "manual_review_required") {
      return "待人工复核";
    }
    if (qualityEvidence.value.status === "missing_output") {
      return "缺少结果文件";
    }
    return "待生成";
  });

  function callbackStatusCount(status: string): number {
    return callbackSummary.value?.status_counts[status] ?? 0;
  }

  function findJobFile(fileType: string, preferredId?: string | null): DocumentFileSummaryResponse | null {
    if (preferredId) {
      const preferred = files.value.find((file) => file.id === preferredId && file.file_type === fileType);
      if (preferred) {
        return preferred;
      }
    }
    return files.value.find((file) => file.file_type === fileType) || null;
  }

  return {
    filteredEvents,
    latestErrorEvent,
    degradedPages,
    sourcePageLine,
    failureSummary,
    failureHelpText,
    runningNotice,
    runningNoticeType,
    downloadHint,
    callbackSummaryItems,
    dispositionAlertType,
    dispositionTitle,
    dispositionDescription,
    dispositionFacts,
    actionSummaries,
    qualityEvidence,
    diagnosticRecommendation,
    diagnosticSummaryFacts,
    diagnosticEvidenceItems,
    diagnosticPreviewEvents,
    diagnosticRecoveryItems,
  };
}

export type JobDetailDiagnostics = ReturnType<typeof useJobDetailDiagnostics>;
