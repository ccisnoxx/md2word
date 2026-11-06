import { computed } from "vue";
import { summarizeTranslationBatches, translationBatchOutcomeTagType, translationBatchOutcomeText } from "@/utils/translationBatches";
import { supportsJobTranslationQa } from "./jobDetailFormat";
import type { JobDetailData } from "./useJobDetailData";

export function useJobDetailBatches(
  data: Pick<
    JobDetailData,
    | "job"
    | "translationBatches"
    | "translationBatchGeneration"
    | "translationBatchExecution"
    | "translationBatchesLoading"
    | "translationBatchesError"
  >
) {
  const {
    job,
    translationBatches,
    translationBatchGeneration,
    translationBatchExecution,
    translationBatchesLoading,
    translationBatchesError,
  } = data;

  const translationBatchSummary = computed(() => summarizeTranslationBatches(
    translationBatches.value,
    translationBatchExecution.value,
  ));

  const translationBatchSummaryItems = computed(() => [
    { label: "总批次", value: String(translationBatchSummary.value.total) },
    { label: "有效叶", value: String(translationBatchSummary.value.leafCount) },
    { label: "成功", value: String(translationBatchSummary.value.succeeded) },
    { label: "运行中", value: String(translationBatchSummary.value.active) },
    { label: "失败", value: String(translationBatchSummary.value.failed) },
    { label: "已拆分", value: String(translationBatchSummary.value.split) },
    { label: "需关注", value: String(translationBatchSummary.value.attention) },
    { label: "items", value: String(translationBatchSummary.value.itemCount) },
    { label: "AI logs", value: String(translationBatchSummary.value.aiCallLogCount) },
    { label: "generation", value: translationBatchGeneration.value === null ? "-" : String(translationBatchGeneration.value) },
    { label: "预算", value: translationBatchSummary.value.providerCallBudget === null ? "-" : String(translationBatchSummary.value.providerCallBudget) },
  ]);

  const translationBatchConclusion = computed(() => {
    if (!translationBatchSummary.value.executionAvailable || !translationBatchExecution.value) {
      if (translationBatches.value.length) {
        return {
          type: "info" as const,
          title: "详细结论不可用",
          description: "当前 API 未返回 execution 摘要，页面保留批次诊断；不会据此推导发布或下载资格。",
          reason: "",
        };
      }
      return null;
    }
    const execution = translationBatchExecution.value;
    const title = translationBatchOutcomeText(execution) || "翻译批次状态未知";
    const type = translationBatchOutcomeTagType(execution);
    const reason = execution.reason_code
      ? `${execution.reason_code}${execution.reason_message ? `: ${execution.reason_message}` : ""}`
      : "";
    const description = execution.outcome === "failed"
      ? "当前代未生成可交付 Word；部分批次只保留在受控诊断路径。"
      : execution.outcome === "retrying"
        ? "后端正在同一 generation 自动恢复失败叶子，成功批次不会重复调用。"
        : execution.outcome === "completed"
          ? "所有翻译批次已完成；可用的下载和发布操作请以任务页面提示为准。"
          : "当前代结论由后端 execution 摘要提供。页面不根据批次数量自行改变任务动作。";
    return { type, title, description, reason };
  });

  const translationBatchHealthText = computed(() => {
    if (!supportsJobTranslationQa(job.value)) {
      return "不适用";
    }
    if (translationBatchesLoading.value) {
      return "加载中";
    }
    if (translationBatchesError.value) {
      return "加载失败";
    }
    if (!translationBatchSummary.value.executionAvailable) {
      return translationBatches.value.length ? "详细结论不可用" : "暂无批次";
    }
    if (translationBatchSummary.value.outcome === "retrying") {
      return "自动重试中";
    }
    if (translationBatchSummary.value.outcome === "failed") {
      return "翻译失败，未生成可交付 Word";
    }
    if (!translationBatchSummary.value.total) {
      return translationBatchSummary.value.outcome === "completed" ? "翻译批次已完成" : "暂无批次";
    }
    if (translationBatchSummary.value.failed || translationBatchSummary.value.attention) {
      return `需关注 ${translationBatchSummary.value.attention} / ${translationBatchSummary.value.total}`;
    }
    return `成功 ${translationBatchSummary.value.succeeded} / ${translationBatchSummary.value.total}`;
  });

  return {
    translationBatchSummaryItems,
    translationBatchConclusion,
    translationBatchHealthText,
  };
}

export type JobDetailBatches = ReturnType<typeof useJobDetailBatches>;
