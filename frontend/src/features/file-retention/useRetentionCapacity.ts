// 容量与配额 owner：storage usage 估算、quota policy dry-run 与 quota enforcement ops summary。
import { computed, reactive, ref, type Ref } from "vue";
import { ElMessage } from "element-plus";

import { filesApi } from "@/api/files";
import type {
  FileQuotaPolicyDryRunResponse,
  FileQuotaPolicyOpsSummaryResponse,
  FileStorageUsageResponse,
} from "@/api/types";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import {
  type StatusTag,
} from "./retentionFormat";

export function useRetentionCapacity(
  error: Ref<ApiClientError | null>,
) {
  const storageUsage = ref<FileStorageUsageResponse | null>(null);
  const storageLoading = ref(false);
  const quotaPolicyReport = ref<FileQuotaPolicyDryRunResponse | null>(null);
  const quotaPolicyLoading = ref(false);

  const quotaPolicyForm = reactive({
    size_bytes: 10 * 1024 * 1024,
    file_type: "source_pdf",
    filename: "quota-dry-run.pdf",
  });

  const quotaOpsSummary = ref<FileQuotaPolicyOpsSummaryResponse | null>(null);
  const quotaOpsLoading = ref(false);
  const storageQuotaStatus = computed(() => String(storageUsage.value?.quota.status ?? "not_configured"));

  const quotaPolicySafetyEntries = computed(() => {
    if (!quotaPolicyReport.value) {
      return [];
    }
    const safety = quotaPolicyReport.value.safety;
    return [
      { label: "read_only", value: safety.read_only, type: safety.read_only ? "success" : "danger" },
      { label: "upload_authorization_created", value: safety.upload_authorization_created, type: safety.upload_authorization_created ? "danger" : "success" },
      { label: "upload_content_written", value: safety.upload_content_written, type: safety.upload_content_written ? "danger" : "success" },
      { label: "upload_blocking_executed", value: safety.upload_blocking_executed, type: safety.upload_blocking_executed ? "danger" : "success" },
      { label: "metadata_mutated", value: safety.metadata_mutated, type: safety.metadata_mutated ? "danger" : "success" },
      { label: "audit_events_written", value: safety.audit_events_written, type: safety.audit_events_written ? "warning" : "info" },
      { label: "provider_calls_executed", value: safety.provider_calls_executed, type: safety.provider_calls_executed ? "danger" : "success" },
      { label: "delete_executed", value: safety.delete_executed, type: safety.delete_executed ? "danger" : "success" },
      { label: "conversion_workflow_executed", value: safety.conversion_workflow_executed, type: safety.conversion_workflow_executed ? "danger" : "success" },
    ] satisfies Array<{ label: string; value: boolean; type: StatusTag }>;
  });

  const quotaOpsSafetyEntries = computed(() => {
    if (!quotaOpsSummary.value) {
      return [];
    }
    const safety = quotaOpsSummary.value.safety;
    return [
      { label: "read_only", value: safety.read_only, type: safety.read_only ? "success" : "danger" },
      { label: "upload_authorization_created", value: safety.upload_authorization_created, type: safety.upload_authorization_created ? "danger" : "success" },
      { label: "upload_content_written", value: safety.upload_content_written, type: safety.upload_content_written ? "danger" : "success" },
      { label: "upload_blocking_executed", value: safety.upload_blocking_executed, type: safety.upload_blocking_executed ? "danger" : "success" },
      { label: "metadata_mutated", value: safety.metadata_mutated, type: safety.metadata_mutated ? "danger" : "success" },
      { label: "audit_events_written", value: safety.audit_events_written, type: safety.audit_events_written ? "warning" : "info" },
      { label: "provider_calls_executed", value: safety.provider_calls_executed, type: safety.provider_calls_executed ? "danger" : "success" },
      { label: "delete_executed", value: safety.delete_executed, type: safety.delete_executed ? "danger" : "success" },
      { label: "cleanup_executed", value: safety.cleanup_executed, type: safety.cleanup_executed ? "danger" : "success" },
      { label: "scheduler_loop_executed", value: safety.scheduler_loop_executed, type: safety.scheduler_loop_executed ? "danger" : "success" },
      { label: "conversion_workflow_executed", value: safety.conversion_workflow_executed, type: safety.conversion_workflow_executed ? "danger" : "success" },
    ] satisfies Array<{ label: string; value: boolean; type: StatusTag }>;
  });

  // 读取 document_files storage usage 只读估算。
  async function loadStorageUsage(): Promise<void> {
    storageLoading.value = true;
    error.value = null;
    try {
      storageUsage.value = await filesApi.getStorageUsage();
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      storageLoading.value = false;
    }
  }

  // 运行 quota policy dry-run，不创建上传授权、不改变真实上传阻断策略。
  async function runQuotaPolicyDryRun(): Promise<void> {
    quotaPolicyLoading.value = true;
    error.value = null;
    try {
      quotaPolicyReport.value = await filesApi.dryRunQuotaPolicy({
        filename: quotaPolicyForm.filename.trim() || null,
        file_type: quotaPolicyForm.file_type,
        size_bytes: quotaPolicyForm.size_bytes,
      });
      ElMessage.success(`quota dry-run 完成：would_block=${String(quotaPolicyReport.value.would_block)}。`);
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      quotaPolicyLoading.value = false;
    }
  }

  // 读取 quota enforcement ops summary；只显示 rollback 和 audit replay，不执行回滚。
  async function loadQuotaPolicyOpsSummary(): Promise<void> {
    quotaOpsLoading.value = true;
    error.value = null;
    try {
      quotaOpsSummary.value = await filesApi.getQuotaPolicyOpsSummary({ replay_limit: 20 });
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      quotaOpsLoading.value = false;
    }
  }

  // 读取 storage usage totals 中的数值，缺失时展示 0。
  function storageTotalValue(key: string): number {
    return storageUsage.value?.totals[key] ?? 0;
  }

  // 读取 storage usage reclaim 中的数字字段，非数字字段按 0 处理。
  function storageReclaimValue(key: string): number {
    const value = storageUsage.value?.reclaim[key];
    return typeof value === "number" ? value : 0;
  }

  return {
    storageUsage,
    storageLoading,
    quotaPolicyReport,
    quotaPolicyLoading,
    quotaPolicyForm,
    quotaOpsSummary,
    quotaOpsLoading,
    storageQuotaStatus,
    quotaPolicySafetyEntries,
    quotaOpsSafetyEntries,
    loadStorageUsage,
    runQuotaPolicyDryRun,
    loadQuotaPolicyOpsSummary,
    storageTotalValue,
    storageReclaimValue,
  };
}

export type RetentionCapacity = ReturnType<typeof useRetentionCapacity>;
