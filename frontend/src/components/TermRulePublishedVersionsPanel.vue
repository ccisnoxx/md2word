<!-- File: frontend/src/components/TermRulePublishedVersionsPanel.vue -->
<!-- Purpose: Render published Term Rule Set versions and admin pointer actions. -->
<template>
  <el-card class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">已发布版本</h2>
        <p class="section-subtitle">设默认和回滚只允许使用已发布版本。</p>
      </div>
    </div>
    <el-table :data="versions" :loading="loading" empty-text="暂无已发布版本">
      <el-table-column prop="version" label="版本" width="120" />
      <el-table-column label="默认" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
          <span v-else class="muted">否</span>
        </template>
      </el-table-column>
      <el-table-column prop="rule_count" label="规则数" width="100" />
      <el-table-column prop="enabled_rule_count" label="启用规则" width="110" />
      <el-table-column prop="snapshot_hash" label="快照哈希" min-width="180" show-overflow-tooltip />
      <el-table-column label="发布时间" width="190">
        <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
      </el-table-column>
      <el-table-column prop="publish_reason" label="发布说明" min-width="180" show-overflow-tooltip />
      <el-table-column v-if="isAdmin" label="管理操作" width="210" fixed="right">
        <template #default="{ row }">
          <RoleGate>
            <el-button link type="warning" :disabled="row.is_default" @click="emit('set-default', row.version)">
              设默认
            </el-button>
            <el-button link type="danger" @click="emit('rollback', row.version)">回滚</el-button>
          </RoleGate>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import type { TermRuleSetVersionResponse } from "@/api/types";
import RoleGate from "@/components/RoleGate.vue";
import { formatDateTime } from "@/utils/format";

defineProps<{
  versions: TermRuleSetVersionResponse[];
  loading: boolean;
  isAdmin: boolean;
}>();

const emit = defineEmits<{
  "set-default": [version: string];
  rollback: [version: string];
}>();
</script>
