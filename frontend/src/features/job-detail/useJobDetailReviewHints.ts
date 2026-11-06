import { computed } from "vue";
import type { JobDetailData } from "./useJobDetailData";

export function useJobDetailReviewHints(
  data: Pick<
    JobDetailData,
    | "reviewBlocks"
    | "reviewBlocksLoading"
    | "reviewBlocksError"
    | "reviewBlocksConflict"
    | "reviewHintsAvailable"
  >
) {
  const {
    reviewBlocks,
    reviewBlocksLoading,
    reviewBlocksError,
    reviewBlocksConflict,
    reviewHintsAvailable,
  } = data;

  const reviewHintItems = computed(() => reviewHintsAvailable.value ? reviewBlocks.value!.items : []);
  const reviewHintCounts = computed(() => ({
    blocker: reviewHintItems.value.filter((item) => item.flags.some((flag) => flag.severity === "blocker")).length,
    warning: reviewHintItems.value.filter((item) => item.flags.some((flag) => flag.severity === "warning")).length,
    info: reviewHintItems.value.filter((item) => item.flags.some((flag) => flag.severity === "info")).length,
  }));

  const reviewHintsHaveWarnings = computed(() => reviewHintCounts.value.blocker > 0 || reviewHintCounts.value.warning > 0);
  const reviewHintSummary = computed(() => {
    if (!reviewHintsAvailable.value) {
      return "提示位置数量尚未确认";
    }
    const counts = reviewHintCounts.value;
    return `已加载 ${reviewHintItems.value.length} / 共有 ${reviewBlocks.value!.total} 个提示位置；已加载位置中：阻断 ${counts.blocker}、警告 ${counts.warning}、信息 ${counts.info}（同一位置可有多类提示）`;
  });

  const reviewHintNotice = computed(() => {
    if (reviewBlocksLoading.value) {
      return "正在读取提示位置，尚未加载的内容不能据此判断。";
    }
    if (reviewBlocksConflict.value) {
      return "提示来源或内容快照未能确认，已清除旧清单，请刷新提示后再复核。";
    }
    if (reviewBlocksError.value) {
      return "提示读取失败，当前无法确认提示位置；请刷新重试。";
    }
    if (!reviewBlocks.value) {
      return "尚未读取复核位置提示，不能据此判断内容是否存在风险。";
    }
    if (reviewBlocks.value.availability === "not_ready") {
      return "复核内容尚未就绪，不能据此判断内容是否存在风险。";
    }
    if (reviewBlocks.value.availability === "unavailable") {
      return "复核内容当前不可用，不能据此判断内容是否存在风险。";
    }
    if (reviewHintsHaveWarnings.value) {
      return "已加载位置包含警告或阻断提示，请对照源 PDF 逐项复核。";
    }
    if (reviewHintItems.value.length) {
      return "已加载位置仅含信息提示，可供人工核对；这不代表正式复核通过。";
    }
    return "当前来源未返回带提示的位置；这不代表已完成人工复核。";
  });

  return {
    reviewHintItems,
    reviewHintCounts,
    reviewHintsHaveWarnings,
    reviewHintSummary,
    reviewHintNotice,
  };
}

export type JobDetailReviewHints = ReturnType<typeof useJobDetailReviewHints>;
