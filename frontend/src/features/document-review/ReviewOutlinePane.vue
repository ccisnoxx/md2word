<!-- 文件：frontend/src/features/document-review/ReviewOutlinePane.vue -->
<!-- 用途：统一复核工作台左栏，提供源 PDF 页码/块类型/告警级别筛选与 J/K 键盘切块大纲。 -->
<template>
  <aside class="review-outline-pane" aria-label="文档块与告警大纲">
    <div class="outline-filters">
      <div class="outline-filter-row">
        <el-checkbox
          :model-value="filter.problem === 'flagged'"
          @update:model-value="onFlaggedToggle"
        >
          仅看问题块
        </el-checkbox>
        <span class="outline-count">
          {{ blocksResponse ? `${blocks.length} / ${blocksResponse.total}` : "0 / 0" }}
        </span>
      </div>
      <div class="outline-filter-selects">
        <el-select
          v-model="filter.blockType"
          size="small"
          clearable
          placeholder="全部类型"
          aria-label="按块类型筛选"
        >
          <el-option
            v-for="opt in reviewBlockTypeOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select
          v-model="filter.severity"
          size="small"
          aria-label="按告警级别筛选"
        >
          <el-option label="全部级别" value="all" />
          <el-option label="阻断" value="blocker" />
          <el-option label="警告" value="warning" />
          <el-option label="信息" value="info" />
        </el-select>
      </div>
      <el-select
        v-model="filter.sourcePageIndex"
        size="small"
        clearable
        placeholder="全部源 PDF 页"
        aria-label="按源 PDF 页码筛选"
        class="outline-page-select"
      >
        <el-option
          v-for="pageIdx in availableSourcePages"
          :key="pageIdx"
          :label="`源 PDF 第 ${pageIdx + 1} 页`"
          :value="pageIdx"
        />
      </el-select>
    </div>

    <div class="outline-list-scroll app-scrollbar-persistent">
      <ApiErrorAlert :error="blocksError" />
      <el-skeleton v-if="blocksLoading && !blocks.length" :rows="6" animated />

      <div v-else-if="blocksResponse && blocksResponse.availability !== 'available'" class="outline-empty">
        <strong>{{ blocksResponse.availability === "not_ready" ? "复核内容尚未就绪" : "复核大纲暂不可用" }}</strong>
        <p>{{ blocksResponse.reason_code ? `原因码：${blocksResponse.reason_code}` : "当前任务暂无可浏览的 DocumentIR 块。" }}</p>
      </div>

      <div v-else-if="!blocks.length" class="outline-empty">
        <strong>当前筛选下无匹配文档块</strong>
        <p>可取消「仅看问题块」或放宽类型/页码条件后重试。</p>
      </div>

      <ul v-else class="outline-list" role="list">
        <li v-for="item in blocks" :key="item.block_id">
          <button
            type="button"
            class="outline-item"
            :class="{
              'is-active': item.block_id === selectedBlockId,
              'has-blocker': hasSeverity(item, 'blocker'),
              'has-warning': !hasSeverity(item, 'blocker') && hasSeverity(item, 'warning'),
            }"
            :aria-current="item.block_id === selectedBlockId ? 'true' : undefined"
            @click="$emit('select-block', item.block_id)"
          >
            <div class="outline-item-head">
              <span class="outline-page-pill">{{ compactPageBadge(item) }}</span>
              <span class="outline-type-label">{{ reviewBlockTypeText[item.block_type] || item.block_type }}</span>
              <span v-if="item.flags.length" class="outline-flag-count" :class="flagBadgeClass(item)">
                {{ flagBadgeText(item) }}
              </span>
            </div>
            <p class="outline-excerpt">{{ item.excerpt || item.block_id }}</p>
            <span class="outline-block-id mono">{{ item.block_id }}</span>
          </button>
        </li>
      </ul>

      <div v-if="blocksResponse?.next_cursor" class="outline-load-more">
        <el-button size="small" :loading="blocksLoading" @click="$emit('load-more')">
          加载更多文档块
        </el-button>
      </div>
    </div>

    <footer class="outline-footer">
      <span>快捷键：<kbd>J</kbd> 下一块 · <kbd>K</kbd> 上一块</span>
    </footer>
  </aside>
</template>

<script setup lang="ts">
import type { DocumentReviewBlockItemResponse, DocumentReviewBlocksResponse } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import type { ApiClientError } from "@/utils/errors";
import { reviewBlockTypeOptions, reviewBlockTypeText } from "./documentReviewFormat";
import type { ReviewOutlineFilter } from "./useDocumentReviewSession";

const props = defineProps<{
  filter: ReviewOutlineFilter;
  blocksResponse: DocumentReviewBlocksResponse | null;
  blocks: DocumentReviewBlockItemResponse[];
  availableSourcePages: number[];
  selectedBlockId: string;
  blocksLoading: boolean;
  blocksError: ApiClientError | null;
}>();

defineEmits<{
  "select-block": [blockId: string];
  "load-more": [];
}>();

function onFlaggedToggle(checked: string | number | boolean): void {
  props.filter.problem = checked ? "flagged" : "all";
}

function compactPageBadge(item: DocumentReviewBlockItemResponse): string {
  const firstPage = item.source_spans.find((span) => span.source_page_index !== null)?.source_page_index;
  return firstPage !== undefined && firstPage !== null ? `P${firstPage + 1}` : "P?";
}

function hasSeverity(item: DocumentReviewBlockItemResponse, severity: "blocker" | "warning" | "info"): boolean {
  return item.flags.some((flag) => flag.severity === severity);
}

function flagBadgeClass(item: DocumentReviewBlockItemResponse): string {
  if (hasSeverity(item, "blocker")) {
    return "is-blocker";
  }
  if (hasSeverity(item, "warning")) {
    return "is-warning";
  }
  return "is-info";
}

function flagBadgeText(item: DocumentReviewBlockItemResponse): string {
  if (hasSeverity(item, "blocker")) {
    return `阻断 ${item.flags.length}`;
  }
  if (hasSeverity(item, "warning")) {
    return `告警 ${item.flags.length}`;
  }
  return `提示 ${item.flags.length}`;
}
</script>

<style scoped lang="scss">
.review-outline-pane {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-lg);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
  overflow: hidden;
}

.outline-filters {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid var(--app-color-border-soft);
  background: var(--app-color-surface-soft);
  flex: 0 0 auto;
}

.outline-filter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.outline-count {
  color: var(--app-color-text-muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.outline-filter-selects {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.outline-page-select {
  width: 100%;
}

.outline-list-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
}

.outline-empty {
  padding: 20px 10px;
  text-align: center;
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.outline-empty strong {
  display: block;
  margin-bottom: 4px;
  color: var(--app-color-text);
}

.outline-empty p {
  margin: 0;
  line-height: 1.5;
}

.outline-list {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.outline-item {
  width: 100%;
  display: grid;
  gap: 4px;
  padding: 9px 10px;
  text-align: left;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.outline-item:hover {
  border-color: var(--app-color-primary-border);
  background: var(--app-color-surface-soft);
}

.outline-item.is-active {
  border-color: var(--app-color-primary);
  background: var(--app-color-primary-soft, rgba(37, 99, 235, 0.08));
}

.outline-item.has-blocker:not(.is-active) {
  border-left: 3px solid var(--app-color-danger, #dc2626);
}

.outline-item.has-warning:not(.is-active) {
  border-left: 3px solid var(--app-color-warning, #d97706);
}

.outline-item:focus-visible {
  outline: 2px solid var(--app-color-primary);
  outline-offset: 1px;
}

.outline-item-head {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.outline-page-pill {
  flex: 0 0 auto;
  padding: 1px 6px;
  border-radius: var(--app-radius-pill);
  background: var(--app-color-surface-muted, var(--app-color-surface-soft));
  color: var(--app-color-text-muted);
  font-size: 11px;
  font-weight: 700;
}

.outline-type-label {
  color: var(--app-color-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.outline-flag-count {
  margin-left: auto;
  padding: 1px 6px;
  border-radius: var(--app-radius-pill);
  font-size: 11px;
  font-weight: 700;
}

.outline-flag-count.is-blocker {
  background: rgba(220, 38, 38, 0.14);
  color: var(--app-color-danger, #dc2626);
}

.outline-flag-count.is-warning {
  background: rgba(217, 119, 6, 0.14);
  color: var(--app-color-warning, #b45309);
}

.outline-flag-count.is-info {
  background: rgba(37, 99, 235, 0.12);
  color: var(--app-color-primary);
}

.outline-excerpt {
  margin: 0;
  font-size: 13px;
  line-height: 1.4;
  color: var(--app-color-text);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.outline-block-id {
  font-size: 11px;
  color: var(--app-color-text-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.outline-load-more {
  display: flex;
  justify-content: center;
  padding: 10px 0 4px;
}

.outline-footer {
  flex: 0 0 auto;
  padding: 8px 12px;
  border-top: 1px solid var(--app-color-border-soft);
  background: var(--app-color-surface-soft);
  color: var(--app-color-text-faint);
  font-size: 12px;
}

.outline-footer kbd {
  padding: 1px 5px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: 4px;
  background: var(--app-color-surface);
  font-size: 11px;
}
</style>
