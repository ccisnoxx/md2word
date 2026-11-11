<template>
  <section class="adapter-contract-panel app-evidence-panel" aria-label="Phase 7 Slack webhook pilot">
    <div class="section-header">
      <div>
        <h3 class="section-title">Phase 7 Slack Pilot</h3>
        <p class="section-subtitle">
          {{ REAL_ALERT_DELIVERY_DESTINATION_ID }} · {{ REAL_ALERT_DELIVERY_ALERT_CODE }} ·
          {{ REAL_ALERT_DELIVERY_TARGET_LABEL }}
        </p>
      </div>
      <div class="toolbar">
        <el-tag :type="realAlertDeliveryPilotActive ? 'success' : 'warning'" effect="plain">
          alert_active={{ booleanLabel(realAlertDeliveryPilotActive) }}
        </el-tag>
        <el-tag :type="integrationCapabilityStatusTag(alertDeliveryCapability?.status || 'blocked')" effect="plain">
          gate={{ alertDeliveryCapability?.status || "blocked" }}
        </el-tag>
        <el-tag :type="alertDeliveryCapability?.kill_switch_active ? 'danger' : 'info'" effect="plain">
          kill={{ booleanLabel(alertDeliveryCapability?.kill_switch_active ?? null) }}
        </el-tag>
      </div>
    </div>

    <el-alert class="delivery-warning" type="warning" title="controlled real-send" :closable="false" show-icon>
      Real-send 必须匹配固定 confirmation phrase；preview 不解析 secret、不调用 provider。
    </el-alert>
    <el-alert
      v-if="realAlertDeliveryGateText"
      class="delivery-warning"
      type="info"
      :title="realAlertDeliveryGateText"
      :closable="false"
      show-icon
    />

    <el-descriptions class="delivery-safety" :column="4" border size="small">
      <el-descriptions-item v-for="item in realAlertDeliveryPilotItems" :key="item.label" :label="item.label">
        <span class="mono">{{ item.value }}</span>
      </el-descriptions-item>
    </el-descriptions>

    <div class="contract-grid">
      <article class="contract-card app-compact-card">
        <h4>Control Gates</h4>
        <el-tag
          v-for="reason in alertDeliveryCapability?.blocking_reasons || []"
          :key="reason"
          type="warning"
          effect="plain"
        >
          {{ reason }}
        </el-tag>
        <el-tag v-if="(alertDeliveryCapability?.blocking_reasons || []).length === 0" type="success" effect="plain">
          ready
        </el-tag>
      </article>
      <article class="contract-card app-compact-card">
        <h4>Rollback</h4>
        <el-tag v-for="item in realAlertDeliveryRollbackItems" :key="item.label" effect="plain">
          {{ item.label }}={{ item.value }}
        </el-tag>
      </article>
    </div>

    <div class="delivery-actions">
      <el-button
        :icon="View"
        :disabled="!canPreviewRealAlertDelivery"
        :loading="alertDeliveryLoading"
        @click="previewRealAlertDelivery"
      >
        Preview real-send gates
      </el-button>
      <el-button
        type="danger"
        :icon="Bell"
        :disabled="!canOpenRealAlertDeliveryDialog"
        :loading="alertDeliveryLoading"
        @click="openRealAlertDeliveryDialog"
      >
        Real-send
      </el-button>
    </div>
  </section>
</template>

<script setup lang="ts">
// Phase 7 Slack webhook pilot：real-send gates、preview 与确认入口。
import type { UnwrapRef } from "vue";
import { Bell, View } from "@element-plus/icons-vue";
import { REAL_ALERT_DELIVERY_DESTINATION_ID, REAL_ALERT_DELIVERY_TARGET_LABEL, REAL_ALERT_DELIVERY_ALERT_CODE, integrationCapabilityStatusTag, booleanLabel } from "./opsDashboardFormat";
import type { OpsAlertDelivery } from "./useOpsAlertDelivery";

const {
  realAlertDeliveryPilotActive,
  alertDeliveryCapability,
  realAlertDeliveryGateText,
  realAlertDeliveryPilotItems,
  realAlertDeliveryRollbackItems,
  canPreviewRealAlertDelivery,
  alertDeliveryLoading,
  previewRealAlertDelivery,
  canOpenRealAlertDeliveryDialog,
  openRealAlertDeliveryDialog,
} = defineProps<{
  realAlertDeliveryPilotActive: UnwrapRef<OpsAlertDelivery["realAlertDeliveryPilotActive"]>;
  alertDeliveryCapability: UnwrapRef<OpsAlertDelivery["alertDeliveryCapability"]>;
  realAlertDeliveryGateText: UnwrapRef<OpsAlertDelivery["realAlertDeliveryGateText"]>;
  realAlertDeliveryPilotItems: UnwrapRef<OpsAlertDelivery["realAlertDeliveryPilotItems"]>;
  realAlertDeliveryRollbackItems: UnwrapRef<OpsAlertDelivery["realAlertDeliveryRollbackItems"]>;
  canPreviewRealAlertDelivery: UnwrapRef<OpsAlertDelivery["canPreviewRealAlertDelivery"]>;
  alertDeliveryLoading: UnwrapRef<OpsAlertDelivery["alertDeliveryLoading"]>;
  previewRealAlertDelivery: UnwrapRef<OpsAlertDelivery["previewRealAlertDelivery"]>;
  canOpenRealAlertDeliveryDialog: UnwrapRef<OpsAlertDelivery["canOpenRealAlertDeliveryDialog"]>;
  openRealAlertDeliveryDialog: UnwrapRef<OpsAlertDelivery["openRealAlertDeliveryDialog"]>;
}>();
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.delivery-warning {
  margin-bottom: var(--app-space-4);
}

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

  .contract-grid {
    grid-template-columns: 1fr;
  }
}
</style>
