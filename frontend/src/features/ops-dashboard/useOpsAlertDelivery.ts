// 告警投递 owner：active alert 选择、fake outbox 预览/发送与 Phase 7 Slack real-send gates。
import { computed, ref } from "vue";

import { opsAlertDeliveriesApi } from "@/api/opsAlertDeliveries";
import type {
  OpsAlertDeliveryResponse,
} from "@/api/types";
import { normalizeApiError } from "@/utils/errors";
import {
  type DetailItem,
  REAL_ALERT_DELIVERY_DESTINATION_ID,
  REAL_ALERT_DELIVERY_SECRET_REF,
  REAL_ALERT_DELIVERY_TARGET_LABEL,
  REAL_ALERT_DELIVERY_ALERT_CODE,
  REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE,
  REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES,
  REAL_ALERT_DELIVERY_RATE_LIMIT_PER_HOUR,
  REAL_ALERT_DELIVERY_TIMEOUT_SECONDS,
  buildRealAlertDeliveryPayload,
  booleanLabel,
  recordDetailItems,
} from "./opsDashboardFormat";
import type { OpsDashboardData } from "./useOpsDashboardData";

export function useOpsAlertDelivery(
  data: Pick<OpsDashboardData, "error" | "alertDeliveryContract" | "activeOpsAlerts" | "activeOpsAlertCodes" | "integrationCapabilityRows">,
) {
  const { error, alertDeliveryContract, activeOpsAlerts, activeOpsAlertCodes, integrationCapabilityRows } = data;
  const selectedAlertDeliveryCodes = ref<string[]>([]);
  const alertDeliveryDedupeWindow = ref(60);
  const alertDeliveryLoading = ref(false);
  const alertDeliveryReport = ref<OpsAlertDeliveryResponse | null>(null);

  const alertDeliveryDialog = ref({
    visible: false,
    reason: "",
    confirmation: "",
  });

  const realAlertDeliveryDialog = ref({
    visible: false,
    reason: "",
    confirmation: "",
  });

  const selectedActiveAlertCodes = computed(() => {
    const activeCodes = new Set(activeOpsAlertCodes.value);
    return selectedAlertDeliveryCodes.value.filter((code) => activeCodes.has(code));
  });

  const alertDeliveryCapability = computed(() => (
    integrationCapabilityRows.value.find((capability) => capability.capability_id === "alert_delivery") || null
  ));

  const alertDeliveryCapabilityReady = computed(() => alertDeliveryCapability.value?.ready === true);
  const realAlertDeliveryPilotActive = computed(() => activeOpsAlertCodes.value.includes(REAL_ALERT_DELIVERY_ALERT_CODE));

  const realAlertDeliveryPreviewPassed = computed(() => (
    alertDeliveryReport.value?.action_mode === "real_send_preview"
    && alertDeliveryReport.value.items.some((item) => item.outcome === "deliverable")
    && alertDeliveryReport.value.items.every((item) => item.missing_gates.length === 0)
  ));

  const realAlertDeliveryGateText = computed(() => {
    if (!realAlertDeliveryPilotActive.value) {
      return `等待活跃告警 ${REAL_ALERT_DELIVERY_ALERT_CODE} 后才能预览 real-send。`;
    }
    if (!alertDeliveryCapabilityReady.value) {
      const reasons = alertDeliveryCapability.value?.blocking_reasons || [];
      return reasons.length ? `alert_delivery capability 未就绪：${reasons.join("，")}` : "alert_delivery capability 未就绪。";
    }
    if (!realAlertDeliveryPreviewPassed.value) {
      return "必须先完成一次无 missing gates 的 real-send preview，才能打开 real-send 确认。";
    }
    return "";
  });

  const allActiveAlertsSelected = computed(() => (
    activeOpsAlerts.value.length > 0 && selectedActiveAlertCodes.value.length === activeOpsAlerts.value.length
  ));

  const someActiveAlertsSelected = computed(() => (
    selectedActiveAlertCodes.value.length > 0 && selectedActiveAlertCodes.value.length < activeOpsAlerts.value.length
  ));

  const alertDeliveryConfirmationPhrase = computed(() => alertDeliveryReport.value?.confirmation_phrase || "SEND FAKE OPS ALERTS");

  const canPreviewAlertDelivery = computed(() => (
    selectedActiveAlertCodes.value.length > 0 && !alertDeliveryLoading.value
  ));

  const canOpenAlertDeliveryDialog = computed(() => (
    selectedActiveAlertCodes.value.length > 0 && !alertDeliveryLoading.value
  ));

  const canFakeSendAlertDelivery = computed(() => (
    canOpenAlertDeliveryDialog.value
    && alertDeliveryDialog.value.reason.trim().length > 0
    && alertDeliveryDialog.value.confirmation === alertDeliveryConfirmationPhrase.value
  ));

  const canPreviewRealAlertDelivery = computed(() => (
    realAlertDeliveryPilotActive.value && alertDeliveryCapabilityReady.value && !alertDeliveryLoading.value
  ));

  const canOpenRealAlertDeliveryDialog = computed(() => (
    canPreviewRealAlertDelivery.value && realAlertDeliveryPreviewPassed.value
  ));

  const canRealSendAlertDelivery = computed(() => (
    canOpenRealAlertDeliveryDialog.value
    && realAlertDeliveryDialog.value.reason.trim().length > 0
    && realAlertDeliveryDialog.value.confirmation === REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE
  ));

  const alertDeliverySafetyItems = computed<DetailItem[]>(() => {
    const safety = alertDeliveryReport.value?.safety;
    return [
      { label: "external_delivery", value: booleanLabel(safety?.external_delivery_executed ?? null) },
      { label: "provider_calls", value: booleanLabel(safety?.provider_calls_executed ?? null) },
      { label: "cleanup", value: booleanLabel(safety?.cleanup_executed ?? null) },
      { label: "delete", value: booleanLabel(safety?.delete_executed ?? null) },
      { label: "conversion_workflow", value: booleanLabel(safety?.conversion_workflow_executed ?? null) },
      { label: "audit_events", value: booleanLabel(safety?.audit_events_written ?? null) },
      { label: "secret_values", value: booleanLabel(safety?.secret_values_exposed ?? null) },
    ];
  });

  const realAlertDeliveryPilotItems = computed<DetailItem[]>(() => [
    { label: "destination_id", value: REAL_ALERT_DELIVERY_DESTINATION_ID },
    { label: "secret_ref", value: REAL_ALERT_DELIVERY_SECRET_REF },
    { label: "target_label", value: REAL_ALERT_DELIVERY_TARGET_LABEL },
    { label: "alert_code", value: REAL_ALERT_DELIVERY_ALERT_CODE },
    { label: "confirmation", value: REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE },
    { label: "dedupe_minutes", value: String(REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES) },
    { label: "rate_limit_hour", value: String(REAL_ALERT_DELIVERY_RATE_LIMIT_PER_HOUR) },
    { label: "timeout_seconds", value: String(REAL_ALERT_DELIVERY_TIMEOUT_SECONDS) },
  ]);

  const realAlertDeliveryRollbackItems = computed<DetailItem[]>(() => {
    const rollback = alertDeliveryReport.value?.rollback;
    if (rollback && Object.keys(rollback).length > 0) {
      return recordDetailItems(rollback);
    }
    return [
      { label: "disable_flag", value: "INTEGRATION_ALERT_DELIVERY_ENABLED=false" },
      { label: "enable_kill_switch", value: "INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=true" },
      { label: "restore_dry_run", value: "INTEGRATION_ALERT_DELIVERY_DRY_RUN=true" },
      { label: "disable_destination", value: REAL_ALERT_DELIVERY_DESTINATION_ID },
      { label: "remove_or_rotate_secret_ref", value: REAL_ALERT_DELIVERY_SECRET_REF },
    ];
  });

  const alertDeliveryContractSafetyItems = computed<DetailItem[]>(() => {
    const safety = alertDeliveryContract.value?.safety;
    return [
      { label: "read_only", value: booleanLabel(safety?.read_only ?? null) },
      { label: "provider_calls", value: booleanLabel(safety?.provider_calls_executed ?? null) },
      { label: "external_delivery", value: booleanLabel(safety?.external_delivery_executed ?? null) },
      { label: "audit_events", value: booleanLabel(safety?.audit_events_written ?? null) },
      { label: "cleanup", value: booleanLabel(safety?.cleanup_executed ?? null) },
      { label: "delete", value: booleanLabel(safety?.delete_executed ?? null) },
      { label: "conversion_workflow", value: booleanLabel(safety?.conversion_workflow_executed ?? null) },
      { label: "secret_values", value: booleanLabel(safety?.secret_values_exposed ?? null) },
    ];
  });

  const alertDeliveryContractParityItems = computed<DetailItem[]>(() => (
    Object.entries(alertDeliveryContract.value?.parity_checks ?? {}).map(([label, value]) => ({
      label,
      value: String(value),
    }))
  ));

  // 判断某个 active alert 是否已被选中进入 fake delivery 请求。
  function isAlertDeliverySelected(alertCode: string): boolean {
    return selectedActiveAlertCodes.value.includes(alertCode);
  }

  // 更新单个 alert code 的选择状态，保持 exact-target 列表不重复。
  function toggleAlertDeliverySelection(alertCode: string, checked: boolean): void {
    const current = new Set(selectedActiveAlertCodes.value);
    if (checked) {
      current.add(alertCode);
    } else {
      current.delete(alertCode);
    }
    selectedAlertDeliveryCodes.value = Array.from(current);
  }

  // 在当前 active alerts 范围内全选或清空 fake delivery 目标。
  function toggleAllAlertDeliverySelection(checked: boolean): void {
    selectedAlertDeliveryCodes.value = checked ? [...activeOpsAlertCodes.value] : [];
  }

  // 刷新后移除已经不再 active 的 alert code，避免向后端发送 stale target。
  function pruneAlertDeliverySelection(activeCodes: string[]): void {
    const activeCodeSet = new Set(activeCodes);
    selectedAlertDeliveryCodes.value = selectedAlertDeliveryCodes.value.filter((code) => activeCodeSet.has(code));
  }

  // 构建 alert delivery 请求 payload，统一固定 local_outbox channel。
  function buildAlertDeliveryPayload(): { alert_codes: string[]; channel: "local_outbox"; dedupe_window_minutes: number } {
    return {
      alert_codes: [...selectedActiveAlertCodes.value],
      channel: "local_outbox",
      dedupe_window_minutes: alertDeliveryDedupeWindow.value,
    };
  }

  // 调用后端 dry-run preview，不写审计、不发送外部通知。
  async function previewAlertDelivery(): Promise<void> {
    alertDeliveryLoading.value = true;
    error.value = null;
    try {
      alertDeliveryReport.value = await opsAlertDeliveriesApi.preview(buildAlertDeliveryPayload());
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      alertDeliveryLoading.value = false;
    }
  }

  // 打开 fake-send 确认对话框，并清空上一次输入。
  function openAlertDeliveryDialog(): void {
    alertDeliveryDialog.value = {
      visible: true,
      reason: "",
      confirmation: "",
    };
  }

  // 调用 fake-send 合同，只记录 local outbox audit，不触发真实通知。
  async function fakeSendAlertDelivery(): Promise<void> {
    if (!canFakeSendAlertDelivery.value) {
      return;
    }
    alertDeliveryLoading.value = true;
    error.value = null;
    try {
      alertDeliveryReport.value = await opsAlertDeliveriesApi.fakeSend({
        ...buildAlertDeliveryPayload(),
        reason: alertDeliveryDialog.value.reason,
        confirmation: alertDeliveryDialog.value.confirmation,
      });
      alertDeliveryDialog.value.visible = false;
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      alertDeliveryLoading.value = false;
    }
  }

  // 预览 Phase 7 real-send gates；后端不会解析 secret 或调用 provider。
  async function previewRealAlertDelivery(): Promise<void> {
    if (!canPreviewRealAlertDelivery.value) {
      return;
    }
    alertDeliveryLoading.value = true;
    error.value = null;
    try {
      alertDeliveryReport.value = await opsAlertDeliveriesApi.previewRealSend(buildRealAlertDeliveryPayload());
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      alertDeliveryLoading.value = false;
    }
  }

  // 打开 Phase 7 real-send 确认对话框，并清空上一次输入。
  function openRealAlertDeliveryDialog(): void {
    realAlertDeliveryDialog.value = {
      visible: true,
      reason: "",
      confirmation: "",
    };
  }

  // 调用 Phase 7 real-send endpoint；真实 provider 调用仍由后端 gates 严格控制。
  async function realSendAlertDelivery(): Promise<void> {
    if (!canRealSendAlertDelivery.value) {
      return;
    }
    alertDeliveryLoading.value = true;
    error.value = null;
    try {
      alertDeliveryReport.value = await opsAlertDeliveriesApi.realSend({
        ...buildRealAlertDeliveryPayload(),
        reason: realAlertDeliveryDialog.value.reason,
        confirmation: realAlertDeliveryDialog.value.confirmation,
      });
      realAlertDeliveryDialog.value.visible = false;
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      alertDeliveryLoading.value = false;
    }
  }

  // 读取 alert delivery totals，缺失字段按 0 展示。
  function alertDeliveryTotal(key: string): number {
    return alertDeliveryReport.value?.totals[key] ?? 0;
  }

  return {
    selectedAlertDeliveryCodes,
    alertDeliveryDedupeWindow,
    alertDeliveryLoading,
    alertDeliveryReport,
    alertDeliveryDialog,
    realAlertDeliveryDialog,
    selectedActiveAlertCodes,
    alertDeliveryCapability,
    alertDeliveryCapabilityReady,
    realAlertDeliveryPilotActive,
    realAlertDeliveryPreviewPassed,
    realAlertDeliveryGateText,
    allActiveAlertsSelected,
    someActiveAlertsSelected,
    alertDeliveryConfirmationPhrase,
    canPreviewAlertDelivery,
    canOpenAlertDeliveryDialog,
    canFakeSendAlertDelivery,
    canPreviewRealAlertDelivery,
    canOpenRealAlertDeliveryDialog,
    canRealSendAlertDelivery,
    alertDeliverySafetyItems,
    realAlertDeliveryPilotItems,
    realAlertDeliveryRollbackItems,
    alertDeliveryContractSafetyItems,
    alertDeliveryContractParityItems,
    isAlertDeliverySelected,
    toggleAlertDeliverySelection,
    toggleAllAlertDeliverySelection,
    pruneAlertDeliverySelection,
    buildAlertDeliveryPayload,
    previewAlertDelivery,
    openAlertDeliveryDialog,
    fakeSendAlertDelivery,
    previewRealAlertDelivery,
    openRealAlertDeliveryDialog,
    realSendAlertDelivery,
    alertDeliveryTotal,
  };
}

export type OpsAlertDelivery = ReturnType<typeof useOpsAlertDelivery>;
