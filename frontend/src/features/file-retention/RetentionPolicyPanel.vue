<template>
  <section class="retention-table-section app-filter-panel app-table-card app-page-shell app-page-shell--wide" aria-label="保留策略治理">
    <div class="section-header">
      <div>
        <h2 class="section-title">保留策略</h2>
        <p class="section-subtitle">策略发布后只影响后续新文件的 expires_at；历史文件只提供 impact preview，不自动回填。</p>
      </div>
      <div class="toolbar">
        <el-tag effect="plain">fallback={{ policyList?.fallback_retention_days ?? "-" }} days</el-tag>
        <el-button :loading="policyLoading" @click="loadPolicies">刷新策略</el-button>
        <el-button type="primary" @click="openCreatePolicyDialog">新增 draft</el-button>
      </div>
    </div>

    <el-table
      v-loading="policyLoading"
      :data="policyList?.items || []"
      empty-text="暂无保留策略"
      class="retention-table"
      table-layout="fixed"
      row-key="policy_id"
    >
      <el-table-column prop="name" label="Name" min-width="210" />
      <el-table-column prop="scope_type" label="Scope" min-width="150">
        <template #default="{ row }">
          <span>{{ row.scope_type }}</span>
          <span v-if="row.file_type" class="mono">:{{ row.file_type }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="retention_days" label="Days" width="90" />
      <el-table-column prop="status" label="Status" width="120">
        <template #default="{ row }">
          <el-tag size="small" :type="policyStatusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_default" label="Default" width="110">
        <template #default="{ row }">{{ row.is_default ? "yes" : "no" }}</template>
      </el-table-column>
      <el-table-column prop="matching_file_count" label="Matches" width="110" />
      <el-table-column prop="updated_at" label="Updated" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="Actions" min-width="340" fixed="right">
        <template #default="{ row }">
          <el-button size="small" :disabled="row.status !== 'draft'" @click="openEditPolicyDialog(row)">编辑</el-button>
          <el-button size="small" @click="previewPolicyImpact(row)">影响预览</el-button>
          <el-button size="small" type="success" :disabled="row.status !== 'draft'" @click="publishPolicy(row)">发布</el-button>
          <el-button size="small" :disabled="row.status !== 'published' || row.is_default" @click="setDefaultPolicy(row)">设默认</el-button>
          <el-button size="small" type="warning" :disabled="row.status === 'disabled'" @click="disablePolicy(row)">禁用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="policyList?.effective.length" class="effective-policy-grid">
      <el-tag
        v-for="item in policyList.effective"
        :key="item.file_type || item.reason"
        effect="plain"
        :type="item.source === 'published_policy' ? 'success' : 'info'"
      >
        {{ item.file_type }}={{ item.retention_days }}d · {{ item.source }}
      </el-tag>
    </div>
  </section>

  <section v-if="policyImpact" class="retention-table-section app-filter-panel app-table-card app-page-shell app-page-shell--wide" aria-label="保留策略影响预览">
    <div class="section-header">
      <div>
        <h2 class="section-title">策略影响预览</h2>
        <p class="section-subtitle">
          {{ policyImpact.policy.name }} · generated {{ formatDateTime(policyImpact.generated_at) }} ·
          不修改历史 expires_at。
        </p>
      </div>
      <div class="toolbar">
        <el-tag type="info" effect="plain">matching={{ policyImpact.totals.matching_files ?? 0 }}</el-tag>
        <el-tag type="warning" effect="plain">would_expire={{ policyImpact.totals.would_be_expired ?? 0 }}</el-tag>
        <el-tag type="danger" effect="plain">would_change={{ policyImpact.totals.would_change_expires_at ?? 0 }}</el-tag>
      </div>
    </div>

    <el-table :data="policyImpact.items" empty-text="暂无影响预览" class="retention-table" table-layout="fixed">
      <el-table-column prop="file_id" label="File ID" min-width="180">
        <template #default="{ row }"><span class="mono">{{ row.file_id }}</span></template>
      </el-table-column>
      <el-table-column prop="file_type" label="Type" min-width="140" />
      <el-table-column prop="status" label="Status" width="110" />
      <el-table-column prop="current_expires_at" label="Current Expires" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.current_expires_at) }}</template>
      </el-table-column>
      <el-table-column prop="projected_expires_at" label="Projected Expires" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.projected_expires_at) }}</template>
      </el-table-column>
      <el-table-column prop="would_be_expired" label="Would Expire" width="120">
        <template #default="{ row }">{{ row.would_be_expired ? "yes" : "no" }}</template>
      </el-table-column>
      <el-table-column prop="would_change_expires_at" label="Would Change" width="130">
        <template #default="{ row }">{{ row.would_change_expires_at ? "yes" : "no" }}</template>
      </el-table-column>
    </el-table>
  </section>

</template>

<script setup lang="ts">
// 保留策略治理与影响预览。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import { policyStatusTag } from "./retentionFormat";
import type { RetentionPolicy } from "./useRetentionPolicy";

const {
  policyList,
  policyLoading,
  loadPolicies,
  openCreatePolicyDialog,
  openEditPolicyDialog,
  previewPolicyImpact,
  publishPolicy,
  setDefaultPolicy,
  disablePolicy,
  policyImpact,
} = defineProps<{
  policyList: UnwrapRef<RetentionPolicy["policyList"]>;
  policyLoading: UnwrapRef<RetentionPolicy["policyLoading"]>;
  loadPolicies: UnwrapRef<RetentionPolicy["loadPolicies"]>;
  openCreatePolicyDialog: UnwrapRef<RetentionPolicy["openCreatePolicyDialog"]>;
  openEditPolicyDialog: UnwrapRef<RetentionPolicy["openEditPolicyDialog"]>;
  previewPolicyImpact: UnwrapRef<RetentionPolicy["previewPolicyImpact"]>;
  publishPolicy: UnwrapRef<RetentionPolicy["publishPolicy"]>;
  setDefaultPolicy: UnwrapRef<RetentionPolicy["setDefaultPolicy"]>;
  disablePolicy: UnwrapRef<RetentionPolicy["disablePolicy"]>;
  policyImpact: UnwrapRef<RetentionPolicy["policyImpact"]>;
}>();
</script>

<style scoped lang="scss">
.retention-table-section {
  min-width: 0;
}

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

.effective-policy-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  margin-top: var(--app-space-1);
}

.section-title {
  margin: 0;
}

.section-subtitle {
  margin: var(--app-space-1) 0 0;
}

.retention-table {
  width: 100%;
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
}
</style>
