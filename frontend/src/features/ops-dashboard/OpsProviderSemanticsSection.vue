<template>
  <section
    v-if="providerCancellationSemantics"
    class="provider-semantics-panel app-evidence-panel"
    aria-label="Provider cancellation semantics verification"
  >
    <div class="section-header">
      <div>
        <h3 class="section-title">Semantics Verification</h3>
        <p class="section-subtitle">
          {{ providerCancellationSemantics.verification_status }} · checked {{ providerCancellationSemantics.checked_on }} ·
          generated {{ formatDateTime(providerCancellationSemantics.generated_at) }}
        </p>
      </div>
      <div class="toolbar">
        <el-tag effect="plain" type="info">sources={{ providerCancellationSemantics.sources.length }}</el-tag>
        <el-tag effect="plain" :type="providerCancellationSemantics.real_provider_cancel_allowed ? 'success' : 'danger'">
          real_cancel={{ booleanLabel(providerCancellationSemantics.real_provider_cancel_allowed) }}
        </el-tag>
        <el-tag effect="plain" :type="providerCancellationSemantics.public_docs_support_real_cancel ? 'success' : 'danger'">
          docs_support={{ booleanLabel(providerCancellationSemantics.public_docs_support_real_cancel) }}
        </el-tag>
      </div>
    </div>

    <el-descriptions class="delivery-safety" :column="4" border size="small">
      <el-descriptions-item v-for="item in providerCancellationSemanticsSafetyItems" :key="item.label" :label="item.label">
        <span class="mono">{{ item.value }}</span>
      </el-descriptions-item>
    </el-descriptions>

    <div class="provider-gates app-evidence-panel">
      <span>Blocking reasons</span>
      <el-tag
        v-for="reason in providerCancellationSemantics.blocking_reasons"
        :key="reason"
        type="warning"
        effect="plain"
      >
        {{ reason }}
      </el-tag>
    </div>

    <el-table :data="providerCancellationSemantics.sources" empty-text="暂无语义核查来源" table-layout="fixed">
      <el-table-column prop="label" label="Source" min-width="180" />
      <el-table-column prop="url" label="URL" min-width="260">
        <template #default="{ row }">
          <a :href="row.url" target="_blank" rel="noreferrer" class="mono">{{ row.url }}</a>
        </template>
      </el-table-column>
      <el-table-column prop="finding" label="Finding" min-width="360" show-overflow-tooltip />
    </el-table>
  </section>
</template>

<script setup lang="ts">
// Provider cancellation 语义核验结论（只读）。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import { booleanLabel } from "./opsDashboardFormat";
import type { OpsDashboardData } from "./useOpsDashboardData";
import type { ProviderCancellation } from "./useProviderCancellation";

const {
  providerCancellationSemantics,
  providerCancellationSemanticsSafetyItems,
} = defineProps<{
  providerCancellationSemantics: UnwrapRef<OpsDashboardData["providerCancellationSemantics"]>;
  providerCancellationSemanticsSafetyItems: UnwrapRef<ProviderCancellation["providerCancellationSemanticsSafetyItems"]>;
}>();
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.delivery-safety {
  margin-bottom: 12px;
}

.provider-semantics-panel {
  margin-bottom: var(--app-space-4);
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
}
</style>
