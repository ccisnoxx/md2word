// 清理执行 owner：retention 计划、候选选择、物理删除与 manual cleanup run 的预览/确认/执行。
import { computed, reactive, ref, type Ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { filesApi } from "@/api/files";
import type {
  FileRetentionCandidateResponse,
  FileRetentionCleanupRunResponse,
  FileRetentionDeleteResponse,
  FileRetentionPlanResponse,
} from "@/api/types";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import {
  type StatusTag,
} from "./retentionFormat";
import type { RetentionHistory } from "./useRetentionHistory";

export function useRetentionCleanup(
  error: Ref<ApiClientError | null>,
  history: Pick<RetentionHistory, "loadCleanupRunHistory" | "showCleanupRunHistory">,
) {
  const { loadCleanupRunHistory, showCleanupRunHistory } = history;
  const plan = ref<FileRetentionPlanResponse | null>(null);
  const loading = ref(false);
  const marking = ref(false);
  const selectedCandidates = ref<FileRetentionCandidateResponse[]>([]);
  const deleteReport = ref<FileRetentionDeleteResponse | null>(null);
  const cleanupRunReport = ref<FileRetentionCleanupRunResponse | null>(null);
  const previewing = ref(false);
  const deleting = ref(false);
  const cleanupPreviewing = ref(false);
  const cleanupExecuting = ref(false);

  const deleteDialog = reactive({
    visible: false,
    reason: "",
    confirmation: "",
  });

  const cleanupRunDialog = reactive({
    visible: false,
    reason: "",
    confirmation: "",
  });

  const CLEANUP_RUN_MAX_FILES = 50;
  const candidateCount = computed(() => plan.value?.candidates.length ?? 0);

  const markableCount = computed(() => (
    plan.value?.candidates.filter((candidate) => candidate.status === "uploaded").length ?? 0
  ));

  const selectedFileIds = computed(() => selectedCandidates.value.map((candidate) => candidate.file_id));

  const deletablePreviewCount = computed(() => (
    deleteReport.value?.items.filter((item) => item.outcome === "deletable").length ?? 0
  ));

  const canOpenDeleteDialog = computed(() => (
    selectedFileIds.value.length > 0
    && deleteReport.value?.action_mode === "delete_preview"
    && fileIdsMatchCurrentSelection(deleteReport.value.requested_file_ids)
    && deletablePreviewCount.value > 0
  ));

  const canSubmitPhysicalDelete = computed(() => (
    canOpenDeleteDialog.value
    && deleteReport.value !== null
    && deleteDialog.reason.trim().length > 0
    && deleteDialog.confirmation === deleteReport.value.confirmation_phrase
  ));

  const cleanupDeletablePreviewCount = computed(() => (
    cleanupRunReport.value?.physical_delete.items.filter((item) => item.outcome === "deletable").length ?? 0
  ));

  const canOpenCleanupRunDialog = computed(() => (
    selectedFileIds.value.length > 0
    && cleanupRunReport.value?.action_mode === "cleanup_preview"
    && fileIdsMatchCurrentSelection(cleanupRunReport.value.requested_file_ids)
    && cleanupDeletablePreviewCount.value > 0
  ));

  const canSubmitCleanupRun = computed(() => (
    canOpenCleanupRunDialog.value
    && cleanupRunReport.value !== null
    && cleanupRunDialog.reason.trim().length > 0
    && cleanupRunDialog.confirmation === cleanupRunReport.value.confirmation_phrase
  ));

  const cleanupRunSafetyEntries = computed(() => {
    if (!cleanupRunReport.value) {
      return [];
    }
    const safety = cleanupRunReport.value.safety;
    return [
      { label: "scheduler_loop_executed", value: safety.scheduler_loop_executed, type: safety.scheduler_loop_executed ? "danger" : "success" },
      { label: "provider_calls_executed", value: safety.provider_calls_executed, type: safety.provider_calls_executed ? "danger" : "success" },
      { label: "s3_delete_executed", value: safety.s3_delete_executed, type: safety.s3_delete_executed ? "danger" : "success" },
      { label: "physical_delete_executed", value: safety.physical_delete_executed, type: safety.physical_delete_executed ? "warning" : "info" },
      { label: "physical_delete_contract_reused", value: safety.physical_delete_contract_reused, type: safety.physical_delete_contract_reused ? "success" : "danger" },
      { label: "audit_events_written", value: safety.audit_events_written, type: safety.audit_events_written ? "warning" : "info" },
      { label: "history_recorded", value: safety.history_recorded, type: safety.history_recorded ? "success" : "danger" },
      { label: "signed_plan_created", value: safety.signed_plan_created, type: safety.signed_plan_created ? "success" : "danger" },
      { label: "signed_plan_verified", value: safety.signed_plan_verified, type: safety.signed_plan_verified ? "success" : "info" },
    ] satisfies Array<{ label: string; value: boolean; type: StatusTag }>;
  });

  // 读取当前 retention dry-run 计划，可在执行后保留结果报告用于审计查看。
  async function loadPlan(preserveDeleteReport = false, preserveCleanupRunReport = false): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      plan.value = await filesApi.getRetentionPlan();
      selectedCandidates.value = [];
      if (!preserveDeleteReport) {
        deleteReport.value = null;
      }
      if (!preserveCleanupRunReport) {
        cleanupRunReport.value = null;
      }
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      loading.value = false;
    }
  }

  // 将当前过期候选标记为 expired，但不执行物理删除。
  async function markExpired(): Promise<void> {
    if (markableCount.value === 0) {
      return;
    }
    try {
      await ElMessageBox.confirm(
        "该操作只会把当前 uploaded 过期候选的 metadata 状态标记为 expired，不会删除任何文件内容。",
        "标记过期文件",
        {
          confirmButtonText: "标记 expired",
          cancelButtonText: "取消",
          type: "warning",
        },
      );
    } catch {
      return;
    }

    marking.value = true;
    error.value = null;
    try {
      const response = await filesApi.markRetentionExpired();
      plan.value = response;
      selectedCandidates.value = [];
      deleteReport.value = null;
      cleanupRunReport.value = null;
      ElMessage.success(`已标记 ${response.marked_file_ids.length} 个文件。`);
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      marking.value = false;
    }
  }

  // 记录表格选择，选择变化会清空已有 dry-run 结果。
  function handleSelectionChange(rows: FileRetentionCandidateResponse[]): void {
    selectedCandidates.value = rows;
    deleteReport.value = null;
    cleanupRunReport.value = null;
    cleanupRunDialog.visible = false;
  }

  // 对当前选择的文件执行物理删除 dry-run。
  async function previewPhysicalDelete(): Promise<void> {
    if (selectedFileIds.value.length === 0) {
      return;
    }
    previewing.value = true;
    error.value = null;
    try {
      const response = await filesApi.previewRetentionDelete({ file_ids: selectedFileIds.value });
      deleteReport.value = response;
      ElMessage.success(`已预览 ${response.items.length} 个文件，deletable=${response.totals.deletable ?? 0}。`);
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      previewing.value = false;
    }
  }

  // 对当前选择的文件执行 manual cleanup-run preview，不执行删除、不写审计，并读取 durable history。
  async function previewCleanupRun(): Promise<void> {
    if (selectedFileIds.value.length === 0) {
      return;
    }
    cleanupPreviewing.value = true;
    error.value = null;
    try {
      const response = await filesApi.previewRetentionCleanupRun({
        file_ids: selectedFileIds.value,
        max_files: CLEANUP_RUN_MAX_FILES,
      });
      cleanupRunReport.value = response;
      await showCleanupRunHistory(response.run_id);
      await loadCleanupRunHistory();
      ElMessage.success(`cleanup run 已预览 ${response.physical_delete.items.length} 个文件，deletable=${response.physical_delete.totals.deletable ?? 0}。`);
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      cleanupPreviewing.value = false;
    }
  }

  // 打开物理删除确认框，要求用户重新输入 reason 和确认短语。
  function openPhysicalDeleteDialog(): void {
    if (!canOpenDeleteDialog.value) {
      ElMessage.warning("请先对当前选择执行物理删除预览。");
      return;
    }
    deleteDialog.reason = "";
    deleteDialog.confirmation = "";
    deleteDialog.visible = true;
  }

  // 打开 cleanup-run 执行确认框，要求 reason 和后端返回的确认短语。
  function openCleanupRunDialog(): void {
    if (!canOpenCleanupRunDialog.value) {
      ElMessage.warning("请先对当前选择执行 cleanup run preview。");
      return;
    }
    cleanupRunDialog.reason = "";
    cleanupRunDialog.confirmation = "";
    cleanupRunDialog.visible = true;
  }

  // 执行 selected expired 文件物理删除，并刷新 retention plan。
  async function executePhysicalDelete(): Promise<void> {
    if (!canSubmitPhysicalDelete.value || !deleteReport.value) {
      return;
    }
    deleting.value = true;
    error.value = null;
    try {
      const response = await filesApi.deleteExpiredRetentionFiles({
        file_ids: deleteReport.value.requested_file_ids,
        reason: deleteDialog.reason,
        confirmation: deleteDialog.confirmation,
      });
      deleteReport.value = response;
      cleanupRunReport.value = null;
      deleteDialog.visible = false;
      await loadPlan(true);
      ElMessage.success(`物理删除完成：deleted=${response.totals.deleted ?? 0}，skipped=${response.totals.skipped ?? 0}。`);
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      deleting.value = false;
    }
  }

  // 执行带 preview_hash 的 manual cleanup run，并显示同一 run_id 的 durable history。
  async function executeCleanupRun(): Promise<void> {
    if (!canSubmitCleanupRun.value || !cleanupRunReport.value) {
      return;
    }
    cleanupExecuting.value = true;
    error.value = null;
    try {
      const response = await filesApi.executeRetentionCleanupRun({
        run_id: cleanupRunReport.value.run_id,
        file_ids: cleanupRunReport.value.requested_file_ids,
        max_files: cleanupRunReport.value.max_files,
        preview_hash: cleanupRunReport.value.preview_hash,
        plan_id: cleanupRunReport.value.cleanup_plan?.plan_id ?? null,
        plan_signature: cleanupRunReport.value.cleanup_plan?.signature ?? null,
        reason: cleanupRunDialog.reason,
        confirmation: cleanupRunDialog.confirmation,
      });
      cleanupRunReport.value = response;
      cleanupRunDialog.visible = false;
      deleteReport.value = null;
      await loadPlan(false, true);
      await loadCleanupRunHistory();
      await showCleanupRunHistory(response.run_id);
      ElMessage.success(`cleanup run 完成：deleted=${response.physical_delete.totals.deleted ?? 0}，skipped=${response.physical_delete.totals.skipped ?? 0}。`);
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      cleanupExecuting.value = false;
    }
  }

  // 读取 totals 中的数值，缺失时展示 0。
  function totalValue(key: string): number {
    return plan.value?.totals[key] ?? 0;
  }

  // 读取物理删除 report totals 中的数值，缺失时展示 0。
  function totalDeleteValue(key: string): number {
    return deleteReport.value?.totals[key] ?? 0;
  }

  // 读取 cleanup-run physical_delete totals 中的数值，缺失时展示 0。
  function cleanupTotalValue(key: string): number {
    return cleanupRunReport.value?.physical_delete.totals[key] ?? 0;
  }

  // 判断当前选择是否仍匹配某次 preview 请求的精确 file_id 顺序。
  function fileIdsMatchCurrentSelection(requestedFileIds: string[]): boolean {
    return selectedFileIds.value.join("\n") === requestedFileIds.join("\n");
  }

  return {
    plan,
    loading,
    marking,
    selectedCandidates,
    deleteReport,
    cleanupRunReport,
    previewing,
    deleting,
    cleanupPreviewing,
    cleanupExecuting,
    deleteDialog,
    cleanupRunDialog,
    CLEANUP_RUN_MAX_FILES,
    candidateCount,
    markableCount,
    selectedFileIds,
    deletablePreviewCount,
    canOpenDeleteDialog,
    canSubmitPhysicalDelete,
    cleanupDeletablePreviewCount,
    canOpenCleanupRunDialog,
    canSubmitCleanupRun,
    cleanupRunSafetyEntries,
    loadPlan,
    markExpired,
    handleSelectionChange,
    previewPhysicalDelete,
    previewCleanupRun,
    openPhysicalDeleteDialog,
    openCleanupRunDialog,
    executePhysicalDelete,
    executeCleanupRun,
    totalValue,
    totalDeleteValue,
    cleanupTotalValue,
    fileIdsMatchCurrentSelection,
  };
}

export type RetentionCleanup = ReturnType<typeof useRetentionCleanup>;
