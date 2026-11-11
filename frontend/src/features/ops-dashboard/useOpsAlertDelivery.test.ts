import { computed, ref } from "vue";
import { describe, expect, it, vi } from "vitest";

import { useOpsAlertDelivery } from "./useOpsAlertDelivery";

vi.mock("@/api/opsAlertDeliveries", () => ({ opsAlertDeliveriesApi: {} }));

function setup(activeCodes: string[]) {
  const active = ref(activeCodes);
  const delivery = useOpsAlertDelivery({
    error: ref(null),
    alertDeliveryContract: ref(null),
    activeOpsAlerts: computed(() => active.value.map((code) => ({ code })) as never),
    activeOpsAlertCodes: computed(() => active.value),
    integrationCapabilityRows: computed(() => []),
  });
  return { active, delivery };
}

describe("useOpsAlertDelivery 告警选择", () => {
  it("只把仍 active 的告警计入选择，刷新后修剪已消失的告警", () => {
    const { active, delivery } = setup(["a", "b"]);
    delivery.toggleAllAlertDeliverySelection(true);
    expect(delivery.selectedActiveAlertCodes.value).toEqual(["a", "b"]);
    expect(delivery.allActiveAlertsSelected.value).toBe(true);

    active.value = ["b", "c"];
    expect(delivery.selectedActiveAlertCodes.value).toEqual(["b"]);
    expect(delivery.someActiveAlertsSelected.value).toBe(true);
    delivery.pruneAlertDeliverySelection(active.value);
    expect(delivery.selectedAlertDeliveryCodes.value).toEqual(["b"]);
  });

  it("单项切换以 active 选择为基准，不重复加入", () => {
    const { delivery } = setup(["a", "b"]);
    delivery.toggleAlertDeliverySelection("a", true);
    delivery.toggleAlertDeliverySelection("a", true);
    delivery.toggleAlertDeliverySelection("b", true);
    delivery.toggleAlertDeliverySelection("a", false);
    expect(delivery.selectedAlertDeliveryCodes.value).toEqual(["b"]);
    expect(delivery.buildAlertDeliveryPayload()).toMatchObject({ alert_codes: ["b"], channel: "local_outbox" });
  });
});
