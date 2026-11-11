<template>
  <section v-if="alertDeliveryReport" class="alert-delivery-result" aria-label="告警投递结果">
    <div class="section-header">
      <div>
        <h3 class="section-title">Delivery Result</h3>
        <p class="section-subtitle">
          {{ alertDeliveryReport.action_mode }} · {{ alertDeliveryReport.delivery_id }} ·
          generated {{ formatDateTime(alertDeliveryReport.generated_at) }}
        </p>
      </div>
      <div class="toolbar">
        <el-tag effect="plain">requested={{ alertDeliveryTotal("requested") }}</el-tag>
        <el-tag effect="plain" type="success">fake={{ alertDeliveryTotal("fake_delivered") }}</el-tag>
        <el-tag effect="plain" type="success">sent={{ alertDeliveryTotal("sent") }}</el-tag>
        <el-tag effect="plain" type="warning">deduped={{ alertDeliveryTotal("deduped") }}</el-tag>
        <el-tag effect="plain" type="warning">blocked={{ alertDeliveryTotal("blocked") }}</el-tag>
        <el-tag effect="plain" type="warning">rate={{ alertDeliveryTotal("rate_limited") }}</el-tag>
        <el-tag effect="plain" type="danger">failed={{ alertDeliveryTotal("failed") }}</el-tag>
      </div>
    </div>

    <el-descriptions class="delivery-safety" :column="3" border size="small">
      <el-descriptions-item v-for="item in alertDeliverySafetyItems" :key="item.label" :label="item.label">
        <span class="mono">{{ item.value }}</span>
      </el-descriptions-item>
    </el-descriptions>

    <el-table :data="alertDeliveryReport.items" empty-text="暂无 fake delivery 结果" table-layout="fixed" class="delivery-result-table">
      <el-table-column prop="alert_code" label="Alert Code" min-width="230">
        <template #default="{ row }"><span class="mono">{{ row.alert_code }}</span></template>
      </el-table-column>
      <el-table-column prop="destination_id" label="Destination" min-width="180">
        <template #default="{ row }"><span class="mono">{{ row.destination_id || "-" }}</span></template>
      </el-table-column>
      <el-table-column prop="outcome" label="Outcome" min-width="150">
        <template #default="{ row }">
          <el-tag size="small" :type="alertDeliveryOutcomeTag(row.outcome)" effect="plain">{{ row.outcome }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="audit_event_written" label="Audit" width="110">
        <template #default="{ row }">{{ row.audit_event_written ? "written" : "no" }}</template>
      </el-table-column>
      <el-table-column prop="dedupe_key" label="Dedupe Key" min-width="240">
        <template #default="{ row }"><span class="mono">{{ row.dedupe_key || "-" }}</span></template>
      </el-table-column>
      <el-table-column label="Adapter" min-width="220">
        <template #default="{ row }">
          <span class="mono">{{ adapterResultLabel(row.adapter_result) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="Missing Gates" min-width="260" show-overflow-tooltip>
        <template #default="{ row }">{{ row.missing_gates?.join(" / ") || "none" }}</template>
      </el-table-column>
      <el-table-column prop="reason" label="Reason" min-width="280" show-overflow-tooltip />
    </el-table>
  </section>
</template>

<script setup lang="ts">
// 告警投递预览/执行结果与逐条 outcome。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import { adapterResultLabel, alertDeliveryOutcomeTag } from "./opsDashboardFormat";
import type { OpsAlertDelivery } from "./useOpsAlertDelivery";

const {
  alertDeliveryReport,
  alertDeliveryTotal,
  alertDeliverySafetyItems,
} = defineProps<{
  alertDeliveryReport: UnwrapRef<OpsAlertDelivery["alertDeliveryReport"]>;
  alertDeliveryTotal: UnwrapRef<OpsAlertDelivery["alertDeliveryTotal"]>;
  alertDeliverySafetyItems: UnwrapRef<OpsAlertDelivery["alertDeliverySafetyItems"]>;
}>();
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.alert-delivery-result {
  min-width: 0;
}

.alert-delivery-result {
  margin-top: var(--app-space-4);
  padding-top: var(--app-space-4);
  border-top: 1px solid var(--app-color-border);
}

.delivery-safety {
  margin-bottom: 12px;
}

.delivery-result-table {
  width: 100%;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
  margin-bottom: var(--app-space-3);
}

.mono {
  font-family: var(--app-font-mono);
  font-size: 12px;
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar {
    justify-content: flex-start;
  }
}
</style>
