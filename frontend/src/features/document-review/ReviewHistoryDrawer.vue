<!-- 文件：frontend/src/features/document-review/ReviewHistoryDrawer.vue -->
<!-- 用途：展示不可变追加的文档复核历史记录，包含绑定摘要、来源类型与语义报告确认指纹。 -->
<template>
  <el-drawer
    v-model="open"
    title="文档复核历史"
    direction="rtl"
    size="min(520px, 94vw)"
    :append-to-body="true"
  >
    <div class="history-drawer-body app-scrollbar-persistent">
      <div class="history-toolbar">
        <span class="history-meta">
          {{ history ? `共观察至第 #${history.through_sequence} 条记录` : "加载复核历史" }}
        </span>
        <el-button size="small" :icon="Refresh" :loading="loading" @click="$emit('refresh')">刷新</el-button>
      </div>

      <ApiErrorAlert :error="error" />
      <el-skeleton v-if="loading && !history" :rows="6" animated />

      <div v-else-if="!history?.items.length" class="history-empty">
        当前任务尚无人工复核提交记录。
      </div>

      <ul v-else class="history-list" aria-label="文档复核历史记录">
        <li v-for="item in history.items" :key="item.id" class="history-item">
          <div class="history-item-head">
            <div class="history-item-title">
              <strong class="mono">#{{ item.sequence }}</strong>
              <el-tag size="small" :type="jobReviewStatusTagType(item.record_status)" effect="plain">
                {{ jobReviewStatusText[item.record_status] || item.record_status }}
              </el-tag>
              <el-tag size="small" type="info" effect="plain">
                {{ item.origin === "legacy_import" ? "历史导入" : "实时提交" }}
              </el-tag>
            </div>
            <span class="history-time">{{ formatDateTime(item.reviewed_at) }}</span>
          </div>

          <p v-if="item.issue_type" class="history-field">
            <span>问题归因：</span>
            <strong>{{ reviewIssueTypeText[item.issue_type] || item.issue_type }}</strong>
          </p>
          <p v-if="item.note" class="history-note">{{ item.note }}</p>

          <dl class="history-facts">
            <div>
              <dt>复核人</dt>
              <dd>{{ item.reviewed_by || "-" }}</dd>
            </div>
            <div>
              <dt>绑定代次</dt>
              <dd>第 {{ item.binding.generation + 1 }} 代（{{ item.binding.binding_state }}）</dd>
            </div>
            <div>
              <dt>主件摘要</dt>
              <dd class="mono">{{ shortHash(item.binding.result_sha256, 16) }}</dd>
            </div>
            <div v-if="item.binding.acknowledged_table_semantics_report_sha256">
              <dt>语义报告确认</dt>
              <dd class="mono">{{ shortHash(item.binding.acknowledged_table_semantics_report_sha256, 16) }}</dd>
            </div>
          </dl>
        </li>
      </ul>

      <div v-if="history?.next_cursor" class="history-more">
        <el-button :loading="loading" @click="$emit('load-more')">加载更早记录</el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";

import type { DocumentReviewHistoryResponse } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import type { ApiClientError } from "@/utils/errors";
import { formatDateTime, jobReviewStatusTagType, jobReviewStatusText } from "@/utils/format";
import { reviewIssueTypeText, shortHash } from "./documentReviewFormat";

const open = defineModel<boolean>({ required: true });

defineProps<{
  history: DocumentReviewHistoryResponse | null;
  loading: boolean;
  error: ApiClientError | null;
}>();

defineEmits<{
  refresh: [];
  "load-more": [];
}>();
</script>

<style scoped lang="scss">
.history-drawer-body {
  display: grid;
  gap: 12px;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
  padding-right: 4px;
}

.history-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.history-meta {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.history-empty {
  padding: 24px 12px;
  text-align: center;
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.history-list {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.history-item {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
}

.history-item-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.history-item-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.history-time {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.history-field {
  margin: 0;
  font-size: 13px;
  color: var(--app-color-text-muted);
}

.history-note {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.history-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 12px;
  margin: 0;
  font-size: 12px;
}

.history-facts dt {
  color: var(--app-color-text-faint);
}

.history-facts dd {
  margin: 2px 0 0;
  color: var(--app-color-text);
  overflow-wrap: anywhere;
}

.history-more {
  display: flex;
  justify-content: center;
}
</style>
