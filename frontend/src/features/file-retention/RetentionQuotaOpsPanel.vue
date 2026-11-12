<template>
  <div v-loading="quotaOpsLoading" class="quota-ops-panel" aria-label="quota enforcement ops summary">
    <div class="section-header">
      <div>
        <h3 class="section-title">Quota Enforcement Ops</h3>
        <p class="section-subtitle">只读展示真实阻断 readiness、rollback 开关建议和最近 quota enforcement audit replay。</p>
      </div>
      <div class="toolbar">
        <el-tag v-if="quotaOpsSummary" effect="plain" :type="quotaOpsReadinessTag(quotaOpsSummary.enforcement_ready)">
          enforcement_ready={{ String(quotaOpsSummary.enforcement_ready) }}
        </el-tag>
        <el-tag v-if="quotaOpsSummary" effect="plain" :type="quotaOpsSummary.kill_switch_enabled ? 'warning' : 'success'">
          kill_switch={{ String(quotaOpsSummary.kill_switch_enabled) }}
        </el-tag>
        <el-tag v-if="quotaOpsSummary" effect="plain">
          replay={{ quotaOpsSummary.audit_replay.length }}/{{ quotaOpsSummary.audit_replay_total }}
        </el-tag>
        <el-button :loading="quotaOpsLoading" @click="loadQuotaPolicyOpsSummary">刷新 ops</el-button>
      </div>
    </div>

    <div v-if="quotaOpsSummary" class="quota-result-grid app-compact-grid">
      <article class="quota-result-card app-compact-card">
        <span>Current Used</span>
        <strong>{{ formatBytes(quotaOpsSummary.usage.current_used_size_bytes) }}</strong>
        <small>{{ formatRatio(quotaOpsSummary.usage.current_usage_ratio) }} of quota</small>
      </article>
      <article class="quota-result-card app-compact-card">
        <span>Policy</span>
        <strong>{{ quotaOpsSummary.policy.status }}</strong>
        <small>generated={{ formatDateTime(quotaOpsSummary.generated_at) }}</small>
      </article>
      <article class="quota-result-card app-compact-card">
        <span>Current Block</span>
        <strong>{{ String(quotaOpsSummary.current_usage_would_block) }}</strong>
        <small>warn={{ String(quotaOpsSummary.current_usage_would_warn) }}</small>
      </article>
      <article class="quota-result-card app-compact-card">
        <span>Replay Limit</span>
        <strong>{{ quotaOpsSummary.audit_replay_limit }}</strong>
        <small>truncated={{ String(quotaOpsSummary.audit_replay_truncated) }}</small>
      </article>
    </div>

    <div v-if="quotaOpsSummary?.reasons.length" class="quota-reason-list">
      <el-tag v-for="reason in quotaOpsSummary.reasons" :key="reason" effect="plain">
        {{ reason }}
      </el-tag>
    </div>

    <div v-if="quotaOpsSummary" class="safety-grid" aria-label="quota ops safety flags">
      <el-tag
        v-for="item in quotaOpsSafetyEntries"
        :key="item.label"
        :type="item.type"
        effect="plain"
      >
        {{ item.label }}={{ String(item.value) }}
      </el-tag>
    </div>

    <div v-if="quotaOpsSummary" class="quota-ops-subsection">
      <h4 class="subsection-title">Rollback Options</h4>
      <el-table :data="quotaOpsSummary.rollback_options" empty-text="暂无 rollback 选项" table-layout="fixed">
        <el-table-column prop="option_id" label="Option" min-width="170" />
        <el-table-column prop="env_var" label="Env Var" min-width="230">
          <template #default="{ row }"><span class="mono">{{ row.env_var }}</span></template>
        </el-table-column>
        <el-table-column prop="target_value" label="Target" width="100">
          <template #default="{ row }"><span class="mono">{{ row.target_value }}</span></template>
        </el-table-column>
        <el-table-column prop="current_value" label="Current" width="110">
          <template #default="{ row }"><span class="mono">{{ row.current_value }}</span></template>
        </el-table-column>
        <el-table-column prop="currently_effective" label="Effective" width="110">
          <template #default="{ row }">
            <el-tag :type="row.currently_effective ? 'success' : 'info'" size="small" effect="plain">
              {{ String(row.currently_effective) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="effect" label="Effect" min-width="260" show-overflow-tooltip />
      </el-table>
    </div>

    <div v-if="quotaOpsSummary" class="quota-ops-subsection">
      <h4 class="subsection-title">Audit Replay</h4>
      <el-table :data="quotaOpsSummary.audit_replay" empty-text="暂无 quota enforcement 审计事件" table-layout="fixed">
        <el-table-column prop="created_at" label="Created" min-width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="Action" min-width="210">
          <template #default="{ row }"><span class="mono">{{ row.action }}</span></template>
        </el-table-column>
        <el-table-column prop="outcome" label="Outcome" width="120">
          <template #default="{ row }">
            <el-tag :type="quotaAuditOutcomeTag(row.outcome)" size="small" effect="plain">{{ row.outcome || "-" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="trace_id" label="Trace" min-width="180">
          <template #default="{ row }"><span class="mono">{{ row.trace_id }}</span></template>
        </el-table-column>
        <el-table-column label="Usage" min-width="190">
          <template #default="{ row }">
            {{ formatBytes(row.projected_used_size_bytes) }} / {{ formatBytes(row.quota_bytes) }}
          </template>
        </el-table-column>
        <el-table-column prop="override_applied" label="Override" width="110">
          <template #default="{ row }">
            <el-tag :type="row.override_applied ? 'warning' : 'info'" size="small" effect="plain">
              {{ String(row.override_applied ?? false) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="Reason" min-width="260" show-overflow-tooltip />
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
// quota enforcement ops summary：rollback 与 audit replay 只读展示。
import type { UnwrapRef } from "vue";
import { formatBytes, formatDateTime } from "@/utils/format";
import { formatRatio, quotaOpsReadinessTag, quotaAuditOutcomeTag } from "./retentionFormat";
import type { RetentionCapacity } from "./useRetentionCapacity";

const {
  quotaOpsLoading,
  quotaOpsSummary,
  loadQuotaPolicyOpsSummary,
  quotaOpsSafetyEntries,
} = defineProps<{
  quotaOpsLoading: UnwrapRef<RetentionCapacity["quotaOpsLoading"]>;
  quotaOpsSummary: UnwrapRef<RetentionCapacity["quotaOpsSummary"]>;
  loadQuotaPolicyOpsSummary: UnwrapRef<RetentionCapacity["loadQuotaPolicyOpsSummary"]>;
  quotaOpsSafetyEntries: UnwrapRef<RetentionCapacity["quotaOpsSafetyEntries"]>;
}>();
</script>

<style scoped lang="scss">
.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.quota-result-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.quota-result-card {
  min-height: 86px;
}

.quota-result-card strong {
  font-size: 18px;
}

.quota-reason-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.quota-ops-panel {
  display: grid;
  gap: var(--app-space-3);
  padding-top: var(--app-space-3);
  border-top: 1px solid var(--app-color-border);
}

.quota-ops-subsection {
  display: grid;
  gap: var(--app-space-2);
  min-width: 0;
}

.safety-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.section-title {
  margin: 0;
}

.section-subtitle {
  margin: var(--app-space-1) 0 0;
}

.subsection-title {
  margin: 0;
  color: var(--app-color-text);
  font-size: 14px;
}

.mono {
  font-family: var(--app-font-mono);
  font-size: 12px;
}

@media (max-width: 920px) {
  .quota-result-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
