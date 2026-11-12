<template>
  <section class="alert-destination-panel app-page-shell app-page-shell--wide" aria-label="告警 destination 配置 dry-run">
    <el-card class="card-flat dashboard-panel app-panel-card app-table-card" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Alert Destination Config Dry Run</h2>
          <p class="section-subtitle">只校验 staged Slack/email/webhook destination 配置，不发送外部通知、不读取 secret value。</p>
        </div>
        <div class="toolbar">
          <el-tag effect="plain">configured={{ alertDestinationReport?.configured_count ?? "-" }}</el-tag>
          <el-tag effect="plain" type="info">selected={{ alertDestinationReport?.selected_count ?? "-" }}</el-tag>
        </div>
      </div>

      <el-alert class="delivery-warning" type="info" title="config dry-run only" :closable="false" show-icon>
        Dry-run 可用当前已选择的 active alert codes 校验 allowlist；即使 destination enabled=true，真实 Slack/email/webhook delivery 仍未实现。
      </el-alert>

      <div class="alert-destination-layout">
        <el-form class="alert-destination-form" label-position="top">
          <el-form-item label="Alert codes">
            <el-input
              :model-value="selectedActiveAlertCodes.join('\n')"
              type="textarea"
              :rows="3"
              readonly
              class="mono"
              placeholder="未选择时仅检查 destination config"
            />
          </el-form-item>
          <el-form-item label="Destination IDs">
            <el-input
              v-model="alertDestinationIdsInput"
              type="textarea"
              :rows="3"
              class="mono"
              placeholder="可选；逗号或换行分隔。留空表示全部 configured destinations。"
            />
          </el-form-item>
        </el-form>

        <aside class="alert-destination-controls app-evidence-panel">
          <div class="metric-row app-key-value-row">
            <span>request alerts</span>
            <strong>{{ selectedActiveAlertCodes.length }}</strong>
          </div>
          <div class="metric-row app-key-value-row">
            <span>destination ids</span>
            <strong>{{ parsedAlertDestinationIds.length || "all" }}</strong>
          </div>
          <div class="delivery-actions">
            <el-button
              :icon="View"
              :loading="alertDestinationLoading"
              @click="dryRunAlertDestinations"
            >
              Dry-run destinations
            </el-button>
          </div>
        </aside>
      </div>

      <section v-if="alertDestinationReport" class="alert-destination-result" aria-label="Alert destination dry-run 结果">
        <div class="section-header">
          <div>
            <h3 class="section-title">Destination Dry Run Result</h3>
            <p class="section-subtitle">
              {{ alertDestinationReport.action_mode }} · generated {{ formatDateTime(alertDestinationReport.generated_at) }}
            </p>
          </div>
          <div class="toolbar">
            <el-tag effect="plain">requested_alerts={{ alertDestinationReport.requested_alert_codes.length }}</el-tag>
            <el-tag effect="plain" type="warning">errors={{ alertDestinationReport.config_errors.length }}</el-tag>
          </div>
        </div>

        <el-alert
          v-if="alertDestinationReport.config_errors.length"
          class="delivery-warning"
          type="warning"
          title="config errors"
          :closable="false"
          show-icon
        >
          <ul class="compact-list">
            <li v-for="configError in alertDestinationReport.config_errors" :key="configError">{{ configError }}</li>
          </ul>
        </el-alert>

        <el-descriptions class="delivery-safety" :column="4" border size="small">
          <el-descriptions-item v-for="item in alertDestinationSafetyItems" :key="item.label" :label="item.label">
            <span class="mono">{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-table :data="alertDestinationReport.destinations" empty-text="暂无 destination dry-run 结果" table-layout="fixed" class="delivery-result-table">
          <el-table-column prop="destination_id" label="Destination" min-width="200">
            <template #default="{ row }"><span class="mono">{{ row.destination_id }}</span></template>
          </el-table-column>
          <el-table-column prop="channel" label="Channel" width="110" />
          <el-table-column prop="status" label="Status" min-width="140">
            <template #default="{ row }">
              <el-tag size="small" :type="alertDestinationStatusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="enabled" label="Enabled" width="100">
            <template #default="{ row }">{{ booleanLabel(row.enabled) }}</template>
          </el-table-column>
          <el-table-column prop="secret_ref" label="Secret Ref" min-width="190">
            <template #default="{ row }"><span class="mono">{{ row.secret_ref || "-" }}</span></template>
          </el-table-column>
          <el-table-column prop="target_label" label="Target" min-width="160" show-overflow-tooltip />
          <el-table-column label="Allowlist Match" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              match={{ row.matched_alert_codes.length }} / blocked={{ row.blocked_alert_codes.length }}
            </template>
          </el-table-column>
          <el-table-column label="Gates" min-width="300" show-overflow-tooltip>
            <template #default="{ row }">{{ row.missing_gates.join(" / ") || "none" }}</template>
          </el-table-column>
        </el-table>
      </section>
    </el-card>
  </section>
</template>

<script setup lang="ts">
// 告警 destination 配置 dry-run。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import { View } from "@element-plus/icons-vue";
import { alertDestinationStatusTag, booleanLabel } from "./opsDashboardFormat";
import type { OpsAlertDelivery } from "./useOpsAlertDelivery";
import type { OpsAlertDestination } from "./useOpsAlertDestination";

const alertDestinationIdsInput = defineModel<UnwrapRef<OpsAlertDestination["alertDestinationIdsInput"]>>("alertDestinationIdsInput", { required: true });
const {
  alertDestinationReport,
  selectedActiveAlertCodes,
  parsedAlertDestinationIds,
  alertDestinationLoading,
  dryRunAlertDestinations,
  alertDestinationSafetyItems,
} = defineProps<{
  alertDestinationReport: UnwrapRef<OpsAlertDestination["alertDestinationReport"]>;
  selectedActiveAlertCodes: UnwrapRef<OpsAlertDelivery["selectedActiveAlertCodes"]>;
  parsedAlertDestinationIds: UnwrapRef<OpsAlertDestination["parsedAlertDestinationIds"]>;
  alertDestinationLoading: UnwrapRef<OpsAlertDestination["alertDestinationLoading"]>;
  dryRunAlertDestinations: UnwrapRef<OpsAlertDestination["dryRunAlertDestinations"]>;
  alertDestinationSafetyItems: UnwrapRef<OpsAlertDestination["alertDestinationSafetyItems"]>;
}>();
</script>

<style scoped lang="scss">
.alert-destination-panel {
  display: grid;
  gap: var(--app-space-4);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.delivery-warning {
  margin-bottom: var(--app-space-4);
}

.delivery-actions {
  display: grid;
  gap: var(--app-space-2);
}

.delivery-actions .el-button {
  width: 100%;
  margin-left: 0;
}

.alert-destination-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: var(--app-space-4);
  align-items: start;
}

.alert-destination-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 var(--app-space-4);
}

.alert-destination-controls {
  gap: var(--app-space-3);
  min-width: 0;
}

.alert-destination-result {
  margin-top: var(--app-space-4);
  padding-top: var(--app-space-4);
  border-top: 1px solid var(--app-color-border);
}

.compact-list {
  margin: 0;
  padding-left: 18px;
}

.delivery-safety {
  margin-bottom: 12px;
}

.delivery-result-table {
  width: 100%;
}

.dashboard-panel {
  border-color: var(--app-color-border);
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

  .alert-destination-layout,
  .alert-destination-form {
    grid-template-columns: 1fr;
  }
}
</style>
