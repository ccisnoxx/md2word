<template>
  <section class="alert-delivery-panel app-page-shell app-page-shell--wide" aria-label="告警 fake outbox 投递">
    <WorkbenchPanelCard
      title="Alert Delivery"
      subtitle="Fake outbox 保持本地 audit；Phase 7 pilot 只允许固定 Slack webhook target。"
      card-class="dashboard-panel app-table-card"
    >
      <template #actions>
        <div class="toolbar">
          <el-tag effect="plain">active={{ activeOpsAlerts.length }}</el-tag>
          <el-tag effect="plain" type="info">selected={{ selectedActiveAlertCodes.length }}</el-tag>
          <el-tag v-if="alertDeliveryContract" effect="plain" type="warning">
            contract={{ alertDeliveryContract.contract_version }}
          </el-tag>
        </div>
      </template>

      <el-alert class="delivery-warning" type="warning" title="fake delivery only" :closable="false" show-icon>
        Fake-send 会写入 <span class="mono">ops.alert_delivery_fake</span> audit；后端 safety metadata 会保持 external delivery 为 false。
      </el-alert>

      <section v-if="alertDeliveryContract" class="adapter-contract-panel app-evidence-panel" aria-label="alert delivery adapter contract">
        <div class="section-header">
          <div>
            <h3 class="section-title">Adapter Contract</h3>
            <p class="section-subtitle">
              {{ alertDeliveryContract.fake_adapter_id }} · {{ alertDeliveryContract.fake_adapter_mode }} ·
              generated {{ formatDateTime(alertDeliveryContract.generated_at) }}
            </p>
          </div>
          <div class="toolbar">
            <el-tag effect="plain">destinations={{ alertDeliveryContract.destination_count }}</el-tag>
            <el-tag effect="plain" type="info">channels={{ alertDeliveryContract.real_channels.join(",") }}</el-tag>
            <el-tag effect="plain" type="warning">real_send=gated</el-tag>
          </div>
        </div>

        <el-descriptions class="delivery-safety" :column="3" border size="small">
          <el-descriptions-item v-for="item in alertDeliveryContractSafetyItems" :key="item.label" :label="item.label">
            <span class="mono">{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <div class="contract-grid">
          <article class="contract-card app-compact-card">
            <h4>Parity Checks</h4>
            <el-tag
              v-for="item in alertDeliveryContractParityItems"
              :key="item.label"
              :type="item.value === 'true' ? 'success' : 'danger'"
              effect="plain"
            >
              {{ item.label }}={{ item.value }}
            </el-tag>
          </article>
          <article class="contract-card app-compact-card">
            <h4>Required Audit Fields</h4>
            <el-tag v-for="field in alertDeliveryContract.required_audit_fields" :key="field" effect="plain">
              {{ field }}
            </el-tag>
          </article>
          <article class="contract-card app-compact-card">
            <h4>Blocking Reasons</h4>
            <el-tag v-for="reason in alertDeliveryContract.blocking_reasons" :key="reason" type="warning" effect="plain">
              {{ reason }}
            </el-tag>
          </article>
        </div>
      </section>

      <div class="alert-delivery-layout">
        <div class="alert-delivery-list">
          <div class="delivery-selection-bar">
            <el-checkbox
              :model-value="allActiveAlertsSelected"
              :indeterminate="someActiveAlertsSelected"
              :disabled="activeOpsAlerts.length === 0"
              @change="toggleAllAlertDeliverySelection(Boolean($event))"
            >
              选择全部当前告警
            </el-checkbox>
            <span>{{ selectedActiveAlertCodes.length }} / {{ activeOpsAlerts.length }}</span>
          </div>

          <el-table :data="activeOpsAlerts" empty-text="暂无 active ops alerts" table-layout="fixed" class="delivery-alert-table">
            <el-table-column label="" width="54">
              <template #default="{ row }">
                <el-checkbox
                  :model-value="isAlertDeliverySelected(row.code)"
                  :aria-label="`select ${row.code}`"
                  @change="toggleAlertDeliverySelection(row.code, Boolean($event))"
                />
              </template>
            </el-table-column>
            <el-table-column label="Alert" min-width="240">
              <template #default="{ row }">
                <div class="action-title">
                  <span class="mono">{{ row.code }}</span>
                  <small>{{ row.title }}</small>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="Severity" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="opsAlertSeverityTagType(row.severity)" effect="plain">{{ row.severity }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="source" label="Source" min-width="120" />
            <el-table-column prop="count" label="Count" width="90" />
            <el-table-column prop="suggested_action" label="Suggested Action" min-width="260" show-overflow-tooltip />
          </el-table>
        </div>

        <aside class="alert-delivery-controls app-evidence-panel">
          <el-form label-position="top">
            <el-form-item label="Channel">
              <el-input model-value="local_outbox" readonly />
            </el-form-item>
            <el-form-item label="Dedupe Window">
              <el-input-number
                v-model="alertDeliveryDedupeWindow"
                :min="1"
                :max="1440"
                :step="15"
                controls-position="right"
              />
              <span class="field-hint">minutes</span>
            </el-form-item>
          </el-form>

          <div class="delivery-actions">
            <el-button
              :icon="View"
              :disabled="!canPreviewAlertDelivery"
              :loading="alertDeliveryLoading"
              @click="previewAlertDelivery"
            >
              预览 fake outbox
            </el-button>
            <el-button
              type="warning"
              :icon="Bell"
              :disabled="!canOpenAlertDeliveryDialog"
              :loading="alertDeliveryLoading"
              @click="openAlertDeliveryDialog"
            >
              Fake-send
            </el-button>
          </div>
        </aside>
      </div>
        <slot name="pilot" />

        <slot name="result" />
    </WorkbenchPanelCard>
  </section>
</template>

<script setup lang="ts">
// 告警 fake outbox 投递：adapter 合同、active alert 选择与 fake-send 控件；pilot 与结果区通过插槽放入。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import { Bell, View } from "@element-plus/icons-vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import { opsAlertSeverityTagType } from "./opsDashboardFormat";
import type { OpsAlertDelivery } from "./useOpsAlertDelivery";
import type { OpsDashboardData } from "./useOpsDashboardData";

const alertDeliveryDedupeWindow = defineModel<UnwrapRef<OpsAlertDelivery["alertDeliveryDedupeWindow"]>>("alertDeliveryDedupeWindow", { required: true });
const {
  activeOpsAlerts,
  selectedActiveAlertCodes,
  alertDeliveryContract,
  alertDeliveryContractSafetyItems,
  alertDeliveryContractParityItems,
  allActiveAlertsSelected,
  someActiveAlertsSelected,
  toggleAllAlertDeliverySelection,
  isAlertDeliverySelected,
  toggleAlertDeliverySelection,
  canPreviewAlertDelivery,
  alertDeliveryLoading,
  previewAlertDelivery,
  canOpenAlertDeliveryDialog,
  openAlertDeliveryDialog,
} = defineProps<{
  activeOpsAlerts: UnwrapRef<OpsDashboardData["activeOpsAlerts"]>;
  selectedActiveAlertCodes: UnwrapRef<OpsAlertDelivery["selectedActiveAlertCodes"]>;
  alertDeliveryContract: UnwrapRef<OpsDashboardData["alertDeliveryContract"]>;
  alertDeliveryContractSafetyItems: UnwrapRef<OpsAlertDelivery["alertDeliveryContractSafetyItems"]>;
  alertDeliveryContractParityItems: UnwrapRef<OpsAlertDelivery["alertDeliveryContractParityItems"]>;
  allActiveAlertsSelected: UnwrapRef<OpsAlertDelivery["allActiveAlertsSelected"]>;
  someActiveAlertsSelected: UnwrapRef<OpsAlertDelivery["someActiveAlertsSelected"]>;
  toggleAllAlertDeliverySelection: UnwrapRef<OpsAlertDelivery["toggleAllAlertDeliverySelection"]>;
  isAlertDeliverySelected: UnwrapRef<OpsAlertDelivery["isAlertDeliverySelected"]>;
  toggleAlertDeliverySelection: UnwrapRef<OpsAlertDelivery["toggleAlertDeliverySelection"]>;
  canPreviewAlertDelivery: UnwrapRef<OpsAlertDelivery["canPreviewAlertDelivery"]>;
  alertDeliveryLoading: UnwrapRef<OpsAlertDelivery["alertDeliveryLoading"]>;
  previewAlertDelivery: UnwrapRef<OpsAlertDelivery["previewAlertDelivery"]>;
  canOpenAlertDeliveryDialog: UnwrapRef<OpsAlertDelivery["canOpenAlertDeliveryDialog"]>;
  openAlertDeliveryDialog: UnwrapRef<OpsAlertDelivery["openAlertDeliveryDialog"]>;
}>();
</script>

<style scoped lang="scss">
.alert-delivery-panel {
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

.alert-delivery-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: var(--app-space-4);
  align-items: start;
}

.alert-delivery-list,
.alert-delivery-controls,
.adapter-contract-panel {
  min-width: 0;
}

.adapter-contract-panel {
  margin-bottom: var(--app-space-4);
}

.contract-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.contract-card {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: var(--app-space-2);
  min-width: 0;
}

.contract-card h4 {
  flex-basis: 100%;
  margin: 0;
  color: var(--app-color-text);
  font-size: 13px;
}

.delivery-selection-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-3);
  min-height: 38px;
  margin-bottom: var(--app-space-3);
  padding: var(--app-space-2) var(--app-space-3);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.alert-delivery-controls {
  gap: var(--app-space-3);
}

.field-hint {
  margin-left: var(--app-space-2);
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.delivery-actions {
  display: grid;
  gap: var(--app-space-2);
}

.delivery-actions .el-button {
  width: 100%;
  margin-left: 0;
}

.delivery-safety {
  margin-bottom: 12px;
}

.delivery-alert-table {
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

.action-title {
  display: grid;
  gap: 3px;
}

.action-title small {
  color: var(--app-color-text-muted);
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar,
  .delivery-selection-bar {
    justify-content: flex-start;
  }

  .alert-delivery-layout,
  .contract-grid {
    grid-template-columns: 1fr;
  }
}
</style>
