<template>
  <section v-if="s3DeleteContract" class="s3-delete-contract-panel app-page-shell app-page-shell--wide" aria-label="S3 delete LocalStack fake parity contract">
    <el-card class="card-flat dashboard-panel app-panel-card app-table-card" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">S3 Delete Adapter Contract</h2>
          <p class="section-subtitle">
            {{ s3DeleteContract.fake_adapter_id }} · {{ s3DeleteContract.fake_adapter_mode }} ·
            generated {{ formatDateTime(s3DeleteContract.generated_at) }}
          </p>
        </div>
        <div class="toolbar">
          <el-tag effect="plain">contract={{ s3DeleteContract.contract_version }}</el-tag>
          <el-tag effect="plain" type="warning">retention_fake={{ s3DeleteContract.fake_file_retention_contract_version }}</el-tag>
          <el-tag effect="plain" type="danger">real_delete=false</el-tag>
        </div>
      </div>

      <el-alert class="delivery-warning" type="warning" title="contract only" :closable="false" show-icon>
        LocalStack profile 和 file-retention fake contract 只用于 parity evidence；此页面不会执行真实 S3 delete、LocalStack delete、cleanup execute 或 scheduler execute。
      </el-alert>

      <el-descriptions class="delivery-safety" :column="4" border size="small">
        <el-descriptions-item v-for="item in s3DeleteContractSafetyItems" :key="item.label" :label="item.label">
          <span class="mono">{{ item.value }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <div class="contract-grid">
        <article class="contract-card app-compact-card">
          <h4>LocalStack Profile</h4>
          <el-tag v-for="item in s3DeleteLocalStackItems" :key="item.label" effect="plain">
            {{ item.label }}={{ item.value }}
          </el-tag>
        </article>
        <article class="contract-card app-compact-card">
          <h4>Storage Summary</h4>
          <el-tag v-for="item in s3DeleteStorageItems" :key="item.label" effect="plain">
            {{ item.label }}={{ item.value }}
          </el-tag>
        </article>
        <article class="contract-card app-compact-card">
          <h4>Parity Checks</h4>
          <el-tag
            v-for="item in s3DeleteContractParityItems"
            :key="item.label"
            :type="item.value === 'true' ? 'success' : 'danger'"
            effect="plain"
          >
            {{ item.label }}={{ item.value }}
          </el-tag>
        </article>
        <article class="contract-card app-compact-card">
          <h4>Required Audit Fields</h4>
          <el-tag v-for="field in s3DeleteContract.required_audit_fields" :key="field" effect="plain">
            {{ field }}
          </el-tag>
        </article>
        <article class="contract-card app-compact-card">
          <h4>Blocking Reasons</h4>
          <el-tag v-for="reason in s3DeleteContract.blocking_reasons" :key="reason" type="warning" effect="plain">
            {{ reason }}
          </el-tag>
        </article>
      </div>
    </el-card>
  </section>
</template>

<script setup lang="ts">
// S3 delete LocalStack fake parity 合同（只读）。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import type { OpsDashboardData } from "./useOpsDashboardData";
import type { OpsHealthView } from "./useOpsHealthView";

const {
  s3DeleteContract,
  s3DeleteContractSafetyItems,
  s3DeleteLocalStackItems,
  s3DeleteStorageItems,
  s3DeleteContractParityItems,
} = defineProps<{
  s3DeleteContract: UnwrapRef<OpsDashboardData["s3DeleteContract"]>;
  s3DeleteContractSafetyItems: UnwrapRef<OpsHealthView["s3DeleteContractSafetyItems"]>;
  s3DeleteLocalStackItems: UnwrapRef<OpsHealthView["s3DeleteLocalStackItems"]>;
  s3DeleteStorageItems: UnwrapRef<OpsHealthView["s3DeleteStorageItems"]>;
  s3DeleteContractParityItems: UnwrapRef<OpsHealthView["s3DeleteContractParityItems"]>;
}>();
</script>

<style scoped lang="scss">
.s3-delete-contract-panel {
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

.delivery-safety {
  margin-bottom: 12px;
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

  .contract-grid {
    grid-template-columns: 1fr;
  }
}
</style>
