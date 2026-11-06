<template>
  <el-card class="page-section review-hints-card card-flat" shadow="never" aria-live="polite">
    <div class="section-header">
      <div>
        <h2 class="section-title">复核位置提示</h2>
        <p class="section-subtitle">{{ reviewHintSummary }}</p>
        <p class="section-subtitle">页码指源 PDF，不能作为 Word 实际页码；此处只读提示，不代表正式复核或发布结论。</p>
      </div>
      <el-button :icon="Refresh" :loading="reviewBlocksLoading" @click="loadReviewBlocks()">刷新提示</el-button>
    </div>
    <ApiErrorAlert :error="reviewBlocksError" :diagnostic-context="jobErrorDiagnosticContext('document_jobs.review_blocks')" />
    <el-alert
      :type="reviewHintsHaveWarnings || reviewBlocksConflict ? 'warning' : 'info'"
      :closable="false"
      show-icon
      :title="reviewHintNotice"
    />
    <ul v-if="reviewHintItems.length" class="review-hint-list" aria-label="源 PDF 复核提示位置">
      <li v-for="item in reviewHintItems" :key="item.block_id" class="review-hint-item">
        <strong>{{ documentReviewSourcePagesText(item.source_spans) }}</strong>
        <span class="mono review-hint-block-id">块 ID：{{ item.block_id }}</span>
        <ul class="review-hint-flags">
          <li v-for="(flag, index) in item.flags" :key="`${flag.code}-${index}`">
            <el-tag size="small" :type="flag.severity === 'blocker' ? 'danger' : flag.severity === 'warning' ? 'warning' : 'info'" effect="plain">
              {{ flag.severity === "blocker" ? "阻断提示" : flag.severity === "warning" ? "警告提示" : "信息提示" }}
            </el-tag>
            <span>{{ documentReviewFlagSuggestion(flag) }}</span>
            <small class="mono">{{ flag.code }}</small>
          </li>
        </ul>
      </li>
    </ul>
    <el-button v-if="reviewHintsAvailable && reviewBlocks?.next_cursor" :loading="reviewBlocksLoading" @click="loadReviewBlocks(true)">
      加载更多提示位置
    </el-button>
  </el-card>
</template>

<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { documentReviewFlagSuggestion, documentReviewSourcePagesText } from "@/utils/format";
import type { UnwrapRef } from "vue";
import type { JobDetailData } from "./useJobDetailData";
import type { JobDetailReviewHints } from "./useJobDetailReviewHints";
const {
  reviewBlocks,
  reviewBlocksLoading,
  reviewBlocksError,
  reviewBlocksConflict,
  reviewHintsAvailable,
  loadReviewBlocks,
  jobErrorDiagnosticContext,
  reviewHintItems,
  reviewHintsHaveWarnings,
  reviewHintSummary,
  reviewHintNotice,
} = defineProps<{
  reviewBlocks: UnwrapRef<JobDetailData["reviewBlocks"]>;
  reviewBlocksLoading: UnwrapRef<JobDetailData["reviewBlocksLoading"]>;
  reviewBlocksError: UnwrapRef<JobDetailData["reviewBlocksError"]>;
  reviewBlocksConflict: UnwrapRef<JobDetailData["reviewBlocksConflict"]>;
  reviewHintsAvailable: UnwrapRef<JobDetailData["reviewHintsAvailable"]>;
  loadReviewBlocks: UnwrapRef<JobDetailData["loadReviewBlocks"]>;
  jobErrorDiagnosticContext: UnwrapRef<JobDetailData["jobErrorDiagnosticContext"]>;
  reviewHintItems: UnwrapRef<JobDetailReviewHints["reviewHintItems"]>;
  reviewHintsHaveWarnings: UnwrapRef<JobDetailReviewHints["reviewHintsHaveWarnings"]>;
  reviewHintSummary: UnwrapRef<JobDetailReviewHints["reviewHintSummary"]>;
  reviewHintNotice: UnwrapRef<JobDetailReviewHints["reviewHintNotice"]>;
}>();
</script>

<style scoped lang="scss">
.review-hint-list,
.review-hint-flags {
  display: grid;
  gap: var(--app-space-3);
  padding-left: 20px;
  overflow-wrap: anywhere;
}

.review-hint-item {
  padding-block: var(--app-space-3);
  border-bottom: 1px solid var(--app-color-border-soft);
}

.review-hint-block-id {
  display: block;
  margin-block: var(--app-space-2);
  color: var(--app-color-text-muted);
}

.review-hint-flags li > span,
.review-hint-flags small {
  margin-left: var(--app-space-2);
}

.review-hint-flags small {
  color: var(--app-color-text-muted);
}
</style>
