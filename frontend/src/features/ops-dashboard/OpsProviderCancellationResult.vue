<template>
  <section
    v-if="providerCancellationReport"
    class="provider-cancellation-result"
    aria-label="Provider cancellation fake 结果"
  >
    <div class="section-header">
      <div>
        <h3 class="section-title">Provider Cancellation Result</h3>
        <p class="section-subtitle">
          {{ providerCancellationReport.action_mode }} · {{ providerCancellationReport.provider }} ·
          generated {{ formatDateTime(providerCancellationReport.generated_at) }}
        </p>
      </div>
      <div class="toolbar">
        <el-tag :type="providerCancellationOutcomeTag(providerCancellationReport.outcome)" effect="plain">
          {{ providerCancellationReport.outcome }}
        </el-tag>
        <el-tag :type="providerCancellationReport.eligible ? 'success' : 'warning'" effect="plain">
          eligible={{ booleanLabel(providerCancellationReport.eligible) }}
        </el-tag>
        <el-tag :type="providerCancellationReport.audit_event_written ? 'success' : 'info'" effect="plain">
          audit={{ providerCancellationReport.audit_event_written ? "written" : "no" }}
        </el-tag>
      </div>
    </div>

    <el-alert
      v-if="!providerCancellationReportMatchesForm"
      class="delivery-warning"
      type="warning"
      title="preview target changed"
      :closable="false"
      show-icon
    >
      当前输入已不同于最近一次 preview；请重新预览后再 fake-cancel。
    </el-alert>

    <div class="provider-result-grid">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item v-for="item in providerCancellationTargetItems" :key="item.label" :label="item.label">
          <span class="mono">{{ item.value }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-descriptions :column="1" border size="small">
        <el-descriptions-item v-for="item in providerCancellationOperationItems" :key="item.label" :label="item.label">
          <span class="mono">{{ item.value }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <el-descriptions v-if="providerCancellationTargetSummaryItems.length" :column="2" border size="small">
      <el-descriptions-item
        v-for="item in providerCancellationTargetSummaryItems"
        :key="item.label"
        :label="item.label"
      >
        <span class="mono">{{ item.value }}</span>
      </el-descriptions-item>
    </el-descriptions>

    <div class="provider-gates app-evidence-panel">
      <span>Missing gates</span>
      <template v-if="providerCancellationReport.missing_gates.length">
        <el-tag
          v-for="gate in providerCancellationReport.missing_gates"
          :key="gate"
          type="warning"
          effect="plain"
        >
          {{ gate }}
        </el-tag>
      </template>
      <el-tag v-else type="success" effect="plain">none</el-tag>
    </div>

    <el-descriptions class="delivery-safety" :column="4" border size="small">
      <el-descriptions-item v-for="item in providerCancellationSafetyItems" :key="item.label" :label="item.label">
        <span class="mono">{{ item.value }}</span>
      </el-descriptions-item>
    </el-descriptions>

    <el-descriptions :column="2" border size="small">
      <el-descriptions-item label="dedupe_key">
        <span class="mono">{{ providerCancellationReport.dedupe_key || "-" }}</span>
      </el-descriptions-item>
      <el-descriptions-item label="confirmation_phrase">
        <span class="mono">{{ providerCancellationReport.confirmation_phrase }}</span>
      </el-descriptions-item>
    </el-descriptions>
  </section>
</template>

<script setup lang="ts">
// Provider cancellation fake 预览/执行结果。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import { providerCancellationOutcomeTag, booleanLabel } from "./opsDashboardFormat";
import type { ProviderCancellation } from "./useProviderCancellation";

const {
  providerCancellationReport,
  providerCancellationReportMatchesForm,
  providerCancellationTargetItems,
  providerCancellationOperationItems,
  providerCancellationTargetSummaryItems,
  providerCancellationSafetyItems,
} = defineProps<{
  providerCancellationReport: UnwrapRef<ProviderCancellation["providerCancellationReport"]>;
  providerCancellationReportMatchesForm: UnwrapRef<ProviderCancellation["providerCancellationReportMatchesForm"]>;
  providerCancellationTargetItems: UnwrapRef<ProviderCancellation["providerCancellationTargetItems"]>;
  providerCancellationOperationItems: UnwrapRef<ProviderCancellation["providerCancellationOperationItems"]>;
  providerCancellationTargetSummaryItems: UnwrapRef<ProviderCancellation["providerCancellationTargetSummaryItems"]>;
  providerCancellationSafetyItems: UnwrapRef<ProviderCancellation["providerCancellationSafetyItems"]>;
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

.delivery-safety {
  margin-bottom: 12px;
}

.provider-cancellation-result {
  display: grid;
  gap: var(--app-space-3);
  margin-top: var(--app-space-4);
  padding-top: var(--app-space-4);
  border-top: 1px solid var(--app-color-border);
}

.provider-result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.provider-gates {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--app-space-2);
  min-height: 36px;
}

.provider-gates > span {
  color: var(--app-color-text-muted);
  font-size: 13px;
  font-weight: 600;
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

  .provider-result-grid {
    grid-template-columns: 1fr;
  }
}
</style>
