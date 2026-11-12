// Provider cancellation fake control owner：目标表单、dry-run 预览与 fake-cancel 审计写入。
import { computed, ref } from "vue";

import { opsProviderCancellationsApi } from "@/api/opsProviderCancellations";
import type {
  OpsProviderCancellationPreviewRequest,
  OpsProviderCancellationProvider,
  OpsProviderCancellationResponse,
  OpsProviderCancellationTargetType,
} from "@/api/types";
import { normalizeApiError } from "@/utils/errors";
import {
  type DetailItem,
  booleanLabel,
  recordDetailItems,
} from "./opsDashboardFormat";
import type { OpsDashboardData } from "./useOpsDashboardData";

export function useProviderCancellation(
  data: Pick<OpsDashboardData, "error" | "providerCancellationSemantics">,
) {
  const { error, providerCancellationSemantics } = data;
  const providerCancellationForm = ref<{
    targetType: OpsProviderCancellationTargetType;
    targetId: string;
    provider: OpsProviderCancellationProvider;
    dedupeWindowMinutes: number;
  }>({
    targetType: "document_job",
    targetId: "",
    provider: "mineru",
    dedupeWindowMinutes: 60,
  });

  const providerCancellationLoading = ref(false);
  const providerCancellationReport = ref<OpsProviderCancellationResponse | null>(null);

  const providerCancellationDialog = ref({
    visible: false,
    reason: "",
    confirmation: "",
  });

  const providerCancellationSemanticsSafetyItems = computed<DetailItem[]>(() => {
    const safety = providerCancellationSemantics.value?.safety;
    return [
      { label: "read_only", value: booleanLabel(safety?.read_only ?? null) },
      { label: "real_cancel", value: booleanLabel(safety?.real_provider_cancel_executed ?? null) },
      { label: "provider_calls", value: booleanLabel(safety?.provider_calls_executed ?? null) },
      { label: "local_job_mutated", value: booleanLabel(safety?.local_job_mutated ?? null) },
      { label: "queue_mutated", value: booleanLabel(safety?.queue_mutated ?? null) },
      { label: "cleanup", value: booleanLabel(safety?.cleanup_executed ?? null) },
      { label: "delete", value: booleanLabel(safety?.delete_executed ?? null) },
      { label: "conversion_workflow", value: booleanLabel(safety?.conversion_workflow_executed ?? null) },
      { label: "audit_events", value: booleanLabel(safety?.audit_events_written ?? null) },
      { label: "secret_values", value: booleanLabel(safety?.secret_values_exposed ?? null) },
    ];
  });

  const providerCancellationTargetId = computed(() => providerCancellationForm.value.targetId.trim());

  const providerCancellationConfirmationPhrase = computed(() => (
    providerCancellationReport.value?.confirmation_phrase || "FAKE CANCEL PROVIDER OPERATION"
  ));

  const providerCancellationReportMatchesForm = computed(() => {
    const report = providerCancellationReport.value;
    if (!report) {
      return false;
    }
    return report.target.target_type === providerCancellationForm.value.targetType
      && report.target.target_id === providerCancellationTargetId.value
      && report.provider === providerCancellationForm.value.provider
      && report.dedupe_window_minutes === providerCancellationForm.value.dedupeWindowMinutes;
  });

  const canPreviewProviderCancellation = computed(() => (
    providerCancellationTargetId.value.length > 0 && !providerCancellationLoading.value
  ));

  const canOpenProviderCancellationDialog = computed(() => (
    Boolean(providerCancellationReport.value?.eligible)
    && providerCancellationReportMatchesForm.value
    && !providerCancellationLoading.value
  ));

  const canFakeCancelProviderCancellation = computed(() => (
    canOpenProviderCancellationDialog.value
    && providerCancellationDialog.value.reason.trim().length > 0
    && providerCancellationDialog.value.confirmation === providerCancellationConfirmationPhrase.value
  ));

  const providerCancellationTargetItems = computed<DetailItem[]>(() => {
    const target = providerCancellationReport.value?.target;
    return [
      { label: "target_type", value: target?.target_type || "not reported" },
      { label: "target_id", value: target?.target_id || "not reported" },
      { label: "exists", value: booleanLabel(target?.exists ?? null) },
      { label: "status", value: target?.status || "not reported" },
      { label: "stage", value: target?.stage || "not reported" },
    ];
  });

  const providerCancellationOperationItems = computed<DetailItem[]>(() => {
    const operation = providerCancellationReport.value?.provider_operation;
    return [
      { label: "provider", value: operation?.provider || "not reported" },
      { label: "operation_id", value: operation?.operation_id || "not reported" },
      { label: "data_id", value: operation?.data_id || "not reported" },
      { label: "operation_type", value: operation?.operation_type || "not reported" },
    ];
  });

  const providerCancellationTargetSummaryItems = computed<DetailItem[]>(() => (
    recordDetailItems(providerCancellationReport.value?.target.summary ?? {})
  ));

  const providerCancellationSafetyItems = computed<DetailItem[]>(() => {
    const safety = providerCancellationReport.value?.safety;
    return [
      { label: "real_provider_cancel", value: booleanLabel(safety?.real_provider_cancel_executed ?? null) },
      { label: "provider_calls", value: booleanLabel(safety?.provider_calls_executed ?? null) },
      { label: "local_job_mutated", value: booleanLabel(safety?.local_job_mutated ?? null) },
      { label: "queue_mutated", value: booleanLabel(safety?.queue_mutated ?? null) },
      { label: "cleanup", value: booleanLabel(safety?.cleanup_executed ?? null) },
      { label: "delete", value: booleanLabel(safety?.delete_executed ?? null) },
      { label: "conversion_workflow", value: booleanLabel(safety?.conversion_workflow_executed ?? null) },
      { label: "audit_events", value: booleanLabel(safety?.audit_events_written ?? null) },
    ];
  });

  const providerCancellationDialogTarget = computed(() => {
    const target = providerCancellationReport.value?.target;
    if (!target) {
      return "-";
    }
    return `${target.target_type}:${target.target_id}`;
  });

  const providerCancellationDialogOperation = computed(() => {
    const operation = providerCancellationReport.value?.provider_operation;
    if (!operation) {
      return "-";
    }
    return `${operation.provider}:${operation.operation_id || "missing"}:${operation.data_id || "missing"}`;
  });

  // 构建 provider cancellation 请求 payload，统一固定 mineru provider 和 exact target。
  function buildProviderCancellationPayload(): OpsProviderCancellationPreviewRequest {
    return {
      target_type: providerCancellationForm.value.targetType,
      target_id: providerCancellationTargetId.value,
      provider: providerCancellationForm.value.provider,
      dedupe_window_minutes: providerCancellationForm.value.dedupeWindowMinutes,
    };
  }

  // 调用 provider cancellation dry-run preview，不写审计、不调用真实 provider。
  async function previewProviderCancellation(): Promise<void> {
    if (!canPreviewProviderCancellation.value) {
      return;
    }
    providerCancellationLoading.value = true;
    error.value = null;
    try {
      providerCancellationReport.value = await opsProviderCancellationsApi.preview(buildProviderCancellationPayload());
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      providerCancellationLoading.value = false;
    }
  }

  // 打开 provider fake-cancel 确认对话框，并清空上一次输入。
  function openProviderCancellationDialog(): void {
    providerCancellationDialog.value = {
      visible: true,
      reason: "",
      confirmation: "",
    };
  }

  // 调用 provider fake-cancel 合同，只写审计，不调用真实 provider 或修改任务状态。
  async function fakeCancelProviderCancellation(): Promise<void> {
    if (!canFakeCancelProviderCancellation.value) {
      return;
    }
    providerCancellationLoading.value = true;
    error.value = null;
    try {
      providerCancellationReport.value = await opsProviderCancellationsApi.fakeCancel({
        ...buildProviderCancellationPayload(),
        reason: providerCancellationDialog.value.reason,
        confirmation: providerCancellationDialog.value.confirmation,
      });
      providerCancellationDialog.value.visible = false;
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      providerCancellationLoading.value = false;
    }
  }

  return {
    providerCancellationForm,
    providerCancellationLoading,
    providerCancellationReport,
    providerCancellationDialog,
    providerCancellationSemanticsSafetyItems,
    providerCancellationTargetId,
    providerCancellationConfirmationPhrase,
    providerCancellationReportMatchesForm,
    canPreviewProviderCancellation,
    canOpenProviderCancellationDialog,
    canFakeCancelProviderCancellation,
    providerCancellationTargetItems,
    providerCancellationOperationItems,
    providerCancellationTargetSummaryItems,
    providerCancellationSafetyItems,
    providerCancellationDialogTarget,
    providerCancellationDialogOperation,
    buildProviderCancellationPayload,
    previewProviderCancellation,
    openProviderCancellationDialog,
    fakeCancelProviderCancellation,
  };
}

export type ProviderCancellation = ReturnType<typeof useProviderCancellation>;
