<template>
  <section class="provider-cancellation-panel app-page-shell app-page-shell--wide" aria-label="Provider cancellation fake control">
    <el-card class="card-flat dashboard-panel app-panel-card app-table-card" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Provider Cancellation Fake Control</h2>
          <p class="section-subtitle">只预览或记录 MinerU fake cancellation audit，不调用真实 provider，也不改变本地任务状态。</p>
        </div>
        <div class="toolbar">
          <el-tag effect="plain">{{ providerCancellationForm.targetType }}</el-tag>
          <el-tag effect="plain" type="info">provider={{ providerCancellationForm.provider }}</el-tag>
          <el-tag v-if="providerCancellationSemantics" effect="plain" type="danger">
            {{ providerCancellationSemantics.decision }}
          </el-tag>
        </div>
      </div>

      <el-alert class="delivery-warning" type="warning" title="fake cancellation only" :closable="false" show-icon>
        Fake-cancel 只会在目标 eligible 且未 dedupe 时写入
        <span class="mono">ops.provider_cancellation_fake</span> audit；不会取消 MinerU 任务、不会修改 document job 或 queue。
      </el-alert>

          <slot name="semantics" />

      <div class="provider-cancellation-layout">
        <el-form class="provider-cancellation-form" label-position="top">
          <el-form-item label="Target Type">
            <el-select v-model="providerCancellationForm.targetType">
              <el-option label="document_job" value="document_job" />
            </el-select>
          </el-form-item>
          <el-form-item label="Target ID">
            <el-input
              v-model.trim="providerCancellationForm.targetId"
              placeholder="输入精确 document job ID"
              clearable
              class="mono"
            />
          </el-form-item>
          <el-form-item label="Provider">
            <el-input :model-value="providerCancellationForm.provider" readonly />
          </el-form-item>
          <el-form-item label="Dedupe Window">
            <el-input-number
              v-model="providerCancellationForm.dedupeWindowMinutes"
              :min="1"
              :max="1440"
              :step="15"
              controls-position="right"
            />
            <span class="field-hint">minutes</span>
          </el-form-item>
        </el-form>

        <aside class="provider-cancellation-controls app-evidence-panel">
          <div class="metric-row app-key-value-row">
            <span>preview</span>
            <strong>{{ providerCancellationReport ? providerCancellationReport.outcome : "not run" }}</strong>
          </div>
          <div class="metric-row app-key-value-row">
            <span>eligible</span>
            <strong>{{ providerCancellationReport ? booleanLabel(providerCancellationReport.eligible) : "not reported" }}</strong>
          </div>
          <div class="delivery-actions">
            <el-button
              :icon="View"
              :disabled="!canPreviewProviderCancellation"
              :loading="providerCancellationLoading"
              @click="previewProviderCancellation"
            >
              预览 fake cancellation
            </el-button>
            <el-button
              type="warning"
              :icon="CircleClose"
              :disabled="!canOpenProviderCancellationDialog"
              :loading="providerCancellationLoading"
              @click="openProviderCancellationDialog"
            >
              Fake-cancel
            </el-button>
          </div>
        </aside>
      </div>

          <slot name="result" />
    </el-card>
  </section>
</template>

<script setup lang="ts">
// Provider cancellation fake control：目标表单与 preview/fake-cancel 入口；语义核验与结果通过插槽放入。
import type { UnwrapRef } from "vue";
import { CircleClose, View } from "@element-plus/icons-vue";
import { booleanLabel } from "./opsDashboardFormat";
import type { OpsDashboardData } from "./useOpsDashboardData";
import type { ProviderCancellation } from "./useProviderCancellation";

const {
  providerCancellationForm,
  providerCancellationSemantics,
  providerCancellationReport,
  canPreviewProviderCancellation,
  providerCancellationLoading,
  previewProviderCancellation,
  canOpenProviderCancellationDialog,
  openProviderCancellationDialog,
} = defineProps<{
  providerCancellationForm: UnwrapRef<ProviderCancellation["providerCancellationForm"]>;
  providerCancellationSemantics: UnwrapRef<OpsDashboardData["providerCancellationSemantics"]>;
  providerCancellationReport: UnwrapRef<ProviderCancellation["providerCancellationReport"]>;
  canPreviewProviderCancellation: UnwrapRef<ProviderCancellation["canPreviewProviderCancellation"]>;
  providerCancellationLoading: UnwrapRef<ProviderCancellation["providerCancellationLoading"]>;
  previewProviderCancellation: UnwrapRef<ProviderCancellation["previewProviderCancellation"]>;
  canOpenProviderCancellationDialog: UnwrapRef<ProviderCancellation["canOpenProviderCancellationDialog"]>;
  openProviderCancellationDialog: UnwrapRef<ProviderCancellation["openProviderCancellationDialog"]>;
}>();
</script>

<style scoped lang="scss">
.provider-cancellation-panel {
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

.provider-cancellation-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: var(--app-space-4);
  align-items: start;
}

.provider-cancellation-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 var(--app-space-4);
}

.provider-cancellation-controls {
  gap: var(--app-space-3);
  min-width: 0;
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

  .provider-cancellation-layout,
  .provider-cancellation-form {
    grid-template-columns: 1fr;
  }
}
</style>
