<template>
  <div class="quota-dry-run-panel app-evidence-panel" aria-label="quota policy dry-run">
    <div class="section-header">
      <div>
        <h3 class="section-title">Quota Policy Dry Run</h3>
        <p class="section-subtitle">只预演拟上传文件的 warning/block 结果；不创建上传授权，不改变真实上传阻断策略。</p>
      </div>
      <div class="toolbar">
        <el-tag v-if="quotaPolicyReport" effect="plain" :type="quotaPolicyStatusTag(quotaPolicyReport.policy.status)">
          policy={{ quotaPolicyReport.policy.status }}
        </el-tag>
        <el-tag v-if="quotaPolicyReport" effect="plain" :type="quotaPolicyReport.would_block ? 'danger' : quotaPolicyReport.would_warn ? 'warning' : 'success'">
          would_block={{ String(quotaPolicyReport.would_block) }}
        </el-tag>
        <el-button :loading="quotaPolicyLoading" @click="runQuotaPolicyDryRun">运行 dry-run</el-button>
      </div>
    </div>

    <el-form class="quota-dry-run-form" label-position="top">
      <el-form-item label="Proposed Size">
        <el-input-number
          v-model="quotaPolicyForm.size_bytes"
          :min="0"
          :step="1024 * 1024"
          :precision="0"
          controls-position="right"
        />
      </el-form-item>
      <el-form-item label="File Type">
        <el-select v-model="quotaPolicyForm.file_type" filterable>
          <el-option v-for="fileType in fileTypeOptions" :key="fileType" :label="fileType" :value="fileType" />
        </el-select>
      </el-form-item>
      <el-form-item label="Filename">
        <el-input v-model="quotaPolicyForm.filename" clearable placeholder="quota-dry-run.pdf" @keyup.enter="runQuotaPolicyDryRun" />
      </el-form-item>
    </el-form>

    <div v-if="quotaPolicyReport" class="quota-result-grid app-compact-grid">
      <article class="quota-result-card app-compact-card">
        <span>Current Used</span>
        <strong>{{ formatBytes(quotaPolicyReport.usage.current_used_size_bytes) }}</strong>
        <small>{{ formatRatio(quotaPolicyReport.usage.current_usage_ratio) }} of quota</small>
      </article>
      <article class="quota-result-card app-compact-card">
        <span>Projected Used</span>
        <strong>{{ formatBytes(quotaPolicyReport.usage.projected_used_size_bytes) }}</strong>
        <small>{{ formatRatio(quotaPolicyReport.usage.projected_usage_ratio) }} after proposed upload</small>
      </article>
      <article class="quota-result-card app-compact-card">
        <span>Thresholds</span>
        <strong>{{ formatBytes(quotaPolicyReport.policy.quota_bytes) }}</strong>
        <small>
          warn={{ formatRatio(quotaPolicyReport.policy.warning_threshold_ratio) }} ·
          block={{ formatRatio(quotaPolicyReport.policy.block_threshold_ratio) }}
        </small>
      </article>
      <article class="quota-result-card app-compact-card">
        <span>Upload Max</span>
        <strong>{{ formatBytes(quotaPolicyReport.policy.upload_max_bytes) }}</strong>
        <small>proposed={{ formatBytes(quotaPolicyReport.usage.proposed_upload_size_bytes) }}</small>
      </article>
    </div>

    <div v-if="quotaPolicyReport" class="safety-grid" aria-label="quota dry-run safety flags">
      <el-tag
        v-for="item in quotaPolicySafetyEntries"
        :key="item.label"
        :type="item.type"
        effect="plain"
      >
        {{ item.label }}={{ String(item.value) }}
      </el-tag>
    </div>

    <div v-if="quotaPolicyReport?.reasons.length" class="quota-reason-list">
      <el-tag v-for="reason in quotaPolicyReport.reasons" :key="reason" effect="plain">
        {{ reason }}
      </el-tag>
    </div>

  <slot name="ops" />
  </div>
</template>

<script setup lang="ts">
// quota policy dry-run 面板；ops summary 通过 ops 插槽放入。
import type { UnwrapRef } from "vue";
import { formatBytes } from "@/utils/format";
import { fileTypeOptions, formatRatio, quotaPolicyStatusTag } from "./retentionFormat";
import type { RetentionCapacity } from "./useRetentionCapacity";

const {
  quotaPolicyReport,
  quotaPolicyLoading,
  runQuotaPolicyDryRun,
  quotaPolicyForm,
  quotaPolicySafetyEntries,
} = defineProps<{
  quotaPolicyReport: UnwrapRef<RetentionCapacity["quotaPolicyReport"]>;
  quotaPolicyLoading: UnwrapRef<RetentionCapacity["quotaPolicyLoading"]>;
  runQuotaPolicyDryRun: UnwrapRef<RetentionCapacity["runQuotaPolicyDryRun"]>;
  quotaPolicyForm: UnwrapRef<RetentionCapacity["quotaPolicyForm"]>;
  quotaPolicySafetyEntries: UnwrapRef<RetentionCapacity["quotaPolicySafetyEntries"]>;
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

.quota-dry-run-panel {
  min-width: 0;
}

.quota-dry-run-form {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) minmax(220px, 2fr);
  gap: var(--app-space-3);
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

@media (max-width: 920px) {
  .quota-dry-run-form,
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
