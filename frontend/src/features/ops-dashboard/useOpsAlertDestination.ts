// 告警 destination 配置 dry-run owner：不发送外部通知、不写审计。
import { computed, ref } from "vue";

import { opsAlertDestinationsApi } from "@/api/opsAlertDestinations";
import type {
  OpsAlertDestinationDryRunResponse,
} from "@/api/types";
import { normalizeApiError } from "@/utils/errors";
import {
  type DetailItem,
  parseAlertDestinationIds,
  booleanLabel,
} from "./opsDashboardFormat";
import type { OpsDashboardData } from "./useOpsDashboardData";
import type { OpsAlertDelivery } from "./useOpsAlertDelivery";

export function useOpsAlertDestination(
  data: Pick<OpsDashboardData, "error">,
  alertDelivery: Pick<OpsAlertDelivery, "selectedActiveAlertCodes">,
) {
  const { error } = data;
  const { selectedActiveAlertCodes } = alertDelivery;
  const alertDestinationIdsInput = ref("");
  const alertDestinationLoading = ref(false);
  const alertDestinationReport = ref<OpsAlertDestinationDryRunResponse | null>(null);
  const parsedAlertDestinationIds = computed(() => parseAlertDestinationIds(alertDestinationIdsInput.value));

  const alertDestinationSafetyItems = computed<DetailItem[]>(() => {
    const safety = alertDestinationReport.value?.safety;
    return [
      { label: "read_only", value: booleanLabel(safety?.read_only ?? null) },
      { label: "external_delivery", value: booleanLabel(safety?.external_delivery_executed ?? null) },
      { label: "provider_calls", value: booleanLabel(safety?.provider_calls_executed ?? null) },
      { label: "cleanup", value: booleanLabel(safety?.cleanup_executed ?? null) },
      { label: "delete", value: booleanLabel(safety?.delete_executed ?? null) },
      { label: "conversion_workflow", value: booleanLabel(safety?.conversion_workflow_executed ?? null) },
      { label: "audit_events", value: booleanLabel(safety?.audit_events_written ?? null) },
      { label: "secret_values_exposed", value: booleanLabel(safety?.secret_values_exposed ?? null) },
    ];
  });

  // 调用 alert destination config dry-run，不发送外部通知或写审计。
  async function dryRunAlertDestinations(): Promise<void> {
    alertDestinationLoading.value = true;
    error.value = null;
    try {
      alertDestinationReport.value = await opsAlertDestinationsApi.dryRun({
        alert_codes: [...selectedActiveAlertCodes.value],
        destination_ids: parsedAlertDestinationIds.value,
      });
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      alertDestinationLoading.value = false;
    }
  }

  return {
    alertDestinationIdsInput,
    alertDestinationLoading,
    alertDestinationReport,
    parsedAlertDestinationIds,
    alertDestinationSafetyItems,
    dryRunAlertDestinations,
  };
}

export type OpsAlertDestination = ReturnType<typeof useOpsAlertDestination>;
