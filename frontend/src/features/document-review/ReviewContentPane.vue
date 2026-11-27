<!-- 文件：frontend/src/features/document-review/ReviewContentPane.vue -->
<!-- 用途：统一复核工作台中栏，展示单块内容（direct 单栏 / 翻译对照）、保护 Token、命中术语、表格参考图与跨列发现摘要。 -->
<template>
  <section class="review-content-pane app-scrollbar-persistent" aria-label="当前块内容与证据对照">
    <div v-if="!selectedBlock" class="content-empty">
      <strong>请从左侧大纲选择一个文档块</strong>
      <p>选中后可在此查看原文/译文对照、表格参考图、保护 Token 核验与结构质量标记。</p>
    </div>

    <template v-else>
      <header class="block-header">
        <div class="block-header-main">
          <div class="block-header-tags">
            <el-tag size="small" effect="plain">{{ reviewBlockTypeText[selectedBlock.block_type] || selectedBlock.block_type }}</el-tag>
            <el-tag size="small" type="info" effect="plain">{{ documentReviewSourcePagesText(selectedBlock.source_spans) }}</el-tag>
            <el-tag size="small" :type="locationBadge.tagType" effect="plain">{{ locationBadge.label }}</el-tag>
          </div>
          <h2 class="block-title mono">{{ selectedBlock.block_id }}</h2>
          <p v-if="locationBadge.detail" class="block-location-detail">{{ locationBadge.detail }}</p>
        </div>

        <div class="block-header-actions">
          <el-button
            v-if="isTranslationJob"
            size="small"
            type="primary"
            plain
            @click="triggerTermProposal()"
          >
            从此段提议术语
          </el-button>
        </div>
      </header>

      <section v-if="selectedBlock.flags.length" class="content-card flags-card" aria-label="当前块质量标记">
        <h3>质量提示（{{ selectedBlock.flags.length }} 项）</h3>
        <ul class="flag-list">
          <li v-for="(flag, index) in selectedBlock.flags" :key="`${flag.code}-${index}`">
            <el-tag
              size="small"
              :type="flag.severity === 'blocker' ? 'danger' : flag.severity === 'warning' ? 'warning' : 'info'"
              effect="plain"
            >
              {{ flag.severity === "blocker" ? "阻断" : flag.severity === "warning" ? "警告" : "提示" }}
            </el-tag>
            <span class="flag-suggestion">{{ documentReviewFlagSuggestion(flag) }}</span>
            <small class="mono flag-code">{{ flag.code }}</small>
          </li>
        </ul>
      </section>

      <ApiErrorAlert :error="blockDetailError" />
      <el-skeleton v-if="blockDetailLoading && !blockDetail" :rows="6" animated />

      <template v-else>
        <!-- 表格参考图区 -->
        <section v-if="selectedBlockReferences.length" class="content-card" aria-label="表格参考图">
          <div class="card-head">
            <h3>表格原始参考图（{{ selectedBlockReferences.length }}）</h3>
            <span class="card-hint">点击图片打开高清缩放灯箱</span>
          </div>
          <div class="reference-grid">
            <article
              v-for="refItem in selectedBlockReferences"
              :key="`${refItem.fragment_id}-${refItem.asset_id || 'none'}`"
              class="reference-item"
            >
              <div class="reference-meta">
                <span class="mono">{{ refItem.fragment_id }}</span>
                <el-tag
                  size="small"
                  :type="refItem.availability === 'available' ? 'success' : 'warning'"
                  effect="plain"
                >
                  {{ refItem.availability === "available" ? "可用" : refItem.availability }}
                </el-tag>
              </div>
              <div v-if="refItem.content_path && tableRefObjectUrls[refItem.content_path]" class="reference-thumb-wrap">
                <button
                  type="button"
                  class="reference-thumb-btn"
                  :aria-label="`放大查看表格参考图 ${refItem.fragment_id}`"
                  @click="$emit('open-lightbox', { url: tableRefObjectUrls[refItem.content_path], title: `${selectedBlock.block_id} · ${refItem.fragment_id}` })"
                >
                  <img
                    :src="tableRefObjectUrls[refItem.content_path]"
                    :alt="`表格参考图 ${refItem.fragment_id}`"
                    class="reference-thumb"
                  />
                </button>
              </div>
              <p v-else-if="refItem.content_path && tableRefLoading[refItem.content_path]" class="reference-status">
                正在加载受鉴权表格参考图…
              </p>
              <p v-else-if="refItem.content_path && tableRefErrors[refItem.content_path]" class="reference-status is-error">
                加载失败：{{ tableRefErrors[refItem.content_path] }}
              </p>
              <p v-else class="reference-status">
                当前参考图不可展示（状态：{{ refItem.availability }} / 源状态：{{ refItem.source_status }}）。
              </p>
            </article>
          </div>
        </section>

        <!-- 文本/分片对照区：direct 单栏，翻译模式源文/译文双栏 -->
        <section class="content-card" aria-label="内容与文本对照">
          <div class="card-head">
            <h3>{{ isTranslationJob ? "源文与最终译文对照" : "文档块内容" }}</h3>
            <span class="card-hint">
              {{ isTranslationJob ? "可选中源文词语后点击右上角「从此段提议术语」" : "原文直转模式仅展示源/最终块文本，不展示无关翻译列" }}
            </span>
          </div>

          <div v-if="!contentPairs.length" class="part-empty">
            {{ selectedBlock.excerpt || "当前块未返回可展开文本分片。" }}
          </div>

          <div v-else class="part-list">
            <article v-for="(pair, idx) in contentPairs" :key="pair.key" class="part-card">
              <header class="part-head">
                <span class="part-kind">{{ partKindLabel(pair.kind) }}</span>
                <span class="mono part-field">{{ pair.field }}{{ pair.index !== null ? `[${pair.index}]` : "" }}</span>
                <span v-if="pair.truncated" class="part-truncated">已截断</span>
              </header>

              <div v-if="isTranslationJob && (pair.sourceText !== null || pair.targetText !== null)" class="translation-compare">
                <div class="compare-col">
                  <span class="compare-label">源文</span>
                  <p class="compare-text">{{ pair.sourceText ?? "（无源文对照）" }}</p>
                </div>
                <div class="compare-col">
                  <span class="compare-label">最终译文</span>
                  <p class="compare-text">{{ pair.targetText ?? "（无目标分片）" }}</p>
                </div>
              </div>
              <p v-else class="single-text">
                {{ pair.targetText ?? pair.sourceText ?? pair.sharedText ?? `（HTML 状态：${pair.htmlState || "无正文"}）` }}
              </p>
              <span v-if="idx === -1" />
            </article>
          </div>

          <div v-if="blockDetail?.next_cursor" class="load-more-parts">
            <el-button size="small" :loading="blockDetailLoading" @click="$emit('load-more-detail')">
              加载更多内容分片
            </el-button>
          </div>
        </section>

        <!-- 仅翻译模式：术语命中与保护 Token 核验 -->
        <section v-if="isTranslationJob && termParts.length" class="content-card" aria-label="当前块命中术语">
          <div class="card-head">
            <h3>命中翻译术语（{{ termParts.length }}）</h3>
            <span class="card-hint">点击术语可快速预填提议抽屉</span>
          </div>
          <div class="term-chip-list">
            <button
              v-for="(term, idx) in termParts"
              :key="`${term.unit_id}-${term.source_term}-${idx}`"
              type="button"
              class="term-chip"
              @click="triggerTermProposal(term.source_term, term.target_term)"
            >
              <strong>{{ term.source_term }}</strong>
              <span>→</span>
              <span>{{ term.target_term }}</span>
              <small v-if="term.version" class="mono">{{ term.version }}</small>
            </button>
          </div>
        </section>

        <section v-if="isTranslationJob && batchParts.length" class="content-card" aria-label="翻译批次与保护 Token 核验">
          <div class="card-head">
            <h3>翻译批次与保护 Token 核验</h3>
          </div>
          <div class="batch-list">
            <article v-for="batch in batchParts" :key="`${batch.batch_id}-${batch.attempt}`" class="batch-card">
              <div class="batch-head">
                <span class="mono">{{ batch.batch_id }} (attempt {{ batch.attempt }})</span>
                <div class="batch-tags">
                  <el-tag size="small" :type="batch.status === 'succeeded' ? 'success' : 'danger'" effect="plain">
                    {{ batch.status === "succeeded" ? "批次成功" : "批次失败" }}
                  </el-tag>
                  <el-tag
                    v-if="batch.integrity_status"
                    size="small"
                    :type="batch.integrity_status === 'passed' ? 'success' : batch.integrity_status === 'failed' ? 'danger' : 'info'"
                    effect="plain"
                  >
                    完整性：{{ batch.integrity_status === "passed" ? "通过" : batch.integrity_status === "failed" ? "失败" : "待校验" }}
                  </el-tag>
                </div>
              </div>
              <p class="batch-meta">
                模型：{{ batch.provider_model || batch.provider_backend || "-" }} ·
                核验项：{{ batch.checked_item_count ?? "-" }}/{{ batch.expected_item_count ?? "-" }}
                <template v-if="batch.failed_item_count"> · 失败项：{{ batch.failed_item_count }}</template>
              </p>
              <div v-if="tokenDiffRows(batch).length" class="token-grid">
                <span
                  v-for="row in tokenDiffRows(batch)"
                  :key="row.key"
                  class="token-pill"
                  :class="{ 'is-mismatch': row.expected !== row.actual }"
                >
                  {{ row.label }}：{{ row.actual }}/{{ row.expected }}
                </span>
              </div>
            </article>
          </div>
        </section>

        <!-- 表格结构与疑似数值跨列发现摘要 -->
        <section v-if="selectedBlockTables.length" class="content-card" aria-label="表格网格与数值列发现">
          <div class="card-head">
            <h3>表格结构与数值列发现（{{ selectedBlockTables.length }}）</h3>
          </div>
          <div class="table-evidence-list">
            <article v-for="tableItem in selectedBlockTables" :key="tableItem.table_id" class="table-evidence-card">
              <div class="table-evidence-head">
                <strong class="mono">{{ tableItem.table_id }}</strong>
                <div class="table-evidence-tags">
                  <el-tag size="small" effect="plain">
                    {{ tableItem.source_grid.rows }} 行 × {{ tableItem.source_grid.columns }} 列
                  </el-tag>
                  <el-tag size="small" type="info" effect="plain">
                    {{ tableRenderStateText[tableItem.render_state] || tableItem.render_state }}
                  </el-tag>
                  <el-tag
                    size="small"
                    :type="tableItem.status === 'blocked' ? 'danger' : tableItem.status === 'warning' ? 'warning' : 'success'"
                    effect="plain"
                  >
                    {{ tableItem.status }}
                  </el-tag>
                </div>
              </div>
              <p class="table-grid-stats">
                表头行：{{ tableItem.source_grid.header_rows.length ? tableItem.source_grid.header_rows.map((r) => r + 1).join("、") : "无" }} ·
                跨行合并：{{ tableItem.source_grid.rowspan_count }} ·
                跨列合并：{{ tableItem.source_grid.colspan_count }} ·
                占位图：{{ tableItem.placeholders.length }}
              </p>

              <div v-if="tableItem.value_column_findings?.length" class="semantics-block">
                <h4>疑似数值跨列归属发现（{{ tableItem.value_column_findings.length }} 处，批准前需人工确认）</h4>
                <ul class="semantics-list">
                  <li v-for="finding in tableItem.value_column_findings" :key="finding.finding_id">
                    <span>第 {{ finding.source_row_index + 1 }} 行 · 值 <strong>{{ finding.value }}</strong>{{ finding.unit ? ` ${finding.unit}` : "" }}</span>
                    <span class="semantics-cols">
                      候选列：{{ finding.columns.map((c) => `列${c.column + 1}(${c.label})`).join(" / ") }}
                    </span>
                  </li>
                </ul>
              </div>

              <div v-if="tableItem.unresolved_value_columns?.length" class="semantics-block">
                <h4>待人工核定的未解析数值列（{{ tableItem.unresolved_value_columns.length }} 处）</h4>
                <ul class="semantics-list">
                  <li v-for="item in tableItem.unresolved_value_columns" :key="item.finding_id">
                    <span>第 {{ item.source_row_index + 1 }} 行 · 第 {{ item.source_cell_index + 1 }} 格</span>
                    <span class="semantics-cols">{{ tableUnresolvedReasonLabel(item.reason_code) }}</span>
                  </li>
                </ul>
              </div>
            </article>
          </div>
        </section>
      </template>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type {
  DocumentJobTableReferenceResponse,
  DocumentQualityTableItemResponse,
  DocumentReviewBatchResponse,
  DocumentReviewBlockDetailResponse,
  DocumentReviewBlockItemResponse,
  DocumentReviewContentPartResponse,
  DocumentReviewTermResponse,
  DocumentReviewTokenCountsResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import type { ApiClientError } from "@/utils/errors";
import { documentReviewFlagSuggestion, documentReviewSourcePagesText } from "@/utils/format";
import {
  formatReviewLocationBadge,
  reviewBlockTypeText,
  tableRenderStateText,
  tableUnresolvedReasonLabel,
  tokenCategoryText,
} from "./documentReviewFormat";

const props = defineProps<{
  selectedBlock: DocumentReviewBlockItemResponse | null;
  blockDetail: DocumentReviewBlockDetailResponse | null;
  blockDetailLoading: boolean;
  blockDetailError: ApiClientError | null;
  selectedBlockTables: DocumentQualityTableItemResponse[];
  selectedBlockReferences: DocumentJobTableReferenceResponse[];
  tableRefObjectUrls: Record<string, string>;
  tableRefLoading: Record<string, boolean>;
  tableRefErrors: Record<string, string>;
  isTranslationJob: boolean;
}>();

const emit = defineEmits<{
  "load-more-detail": [];
  "open-lightbox": [payload: { url: string; title: string }];
  "propose-term": [payload: { sourceTerm: string; targetTerm: string; excerpt: string; contextSummary: string }];
}>();

const locationBadge = computed(() => formatReviewLocationBadge(props.selectedBlock?.location));

type ContentPair = {
  key: string;
  kind: DocumentReviewContentPartResponse["kind"];
  field: string;
  index: number | null;
  sourceText: string | null;
  targetText: string | null;
  sharedText: string | null;
  htmlState: string | null;
  truncated: boolean;
};

const TEXT_PART_KINDS = new Set<DocumentReviewContentPartResponse["kind"]>([
  "text",
  "list_item",
  "caption",
  "footnote",
  "latex",
  "table_text",
  "html_summary",
]);

const contentPairs = computed<ContentPair[]>(() => {
  const items = props.blockDetail?.items ?? [];
  const pairs: ContentPair[] = [];
  const indexMap = new Map<string, ContentPair>();

  for (const part of items) {
    if (!TEXT_PART_KINDS.has(part.kind)) {
      continue;
    }
    const key = `${part.kind}:${part.field}:${part.index ?? ""}:${part.unit_id ?? ""}:${part.fragment_id ?? ""}`;
    let entry = indexMap.get(key);
    if (!entry) {
      entry = {
        key,
        kind: part.kind,
        field: part.field,
        index: part.index ?? null,
        sourceText: null,
        targetText: null,
        sharedText: null,
        htmlState: part.html_state ?? null,
        truncated: part.truncated,
      };
      indexMap.set(key, entry);
      pairs.push(entry);
    }
    if (part.truncated) {
      entry.truncated = true;
    }
    if (part.html_state) {
      entry.htmlState = part.html_state;
    }
    const value = part.text ?? "";
    if (part.side === "source") {
      entry.sourceText = entry.sourceText ? `${entry.sourceText}${value}` : value;
    } else if (part.side === "target") {
      entry.targetText = entry.targetText ? `${entry.targetText}${value}` : value;
    } else {
      entry.sharedText = entry.sharedText ? `${entry.sharedText}${value}` : value;
    }
  }
  return pairs;
});

const termParts = computed<DocumentReviewTermResponse[]>(() =>
  (props.blockDetail?.items ?? [])
    .map((part) => part.term)
    .filter((item): item is DocumentReviewTermResponse => Boolean(item)),
);

const batchParts = computed<DocumentReviewBatchResponse[]>(() => {
  const result: DocumentReviewBatchResponse[] = [];
  const seen = new Set<string>();
  for (const part of props.blockDetail?.items ?? []) {
    if (part.batch) {
      const key = `${part.batch.batch_id}:${part.batch.attempt}`;
      if (!seen.has(key)) {
        seen.add(key);
        result.push(part.batch);
      }
    }
  }
  return result;
});

function partKindLabel(kind: DocumentReviewContentPartResponse["kind"]): string {
  const labels: Record<string, string> = {
    text: "正文",
    list_item: "列表项",
    caption: "题注",
    footnote: "脚注",
    latex: "公式 LaTeX",
    table_text: "表格文本",
    html_summary: "HTML 摘要",
  };
  return labels[kind] || kind;
}

function tokenDiffRows(batch: DocumentReviewBatchResponse): Array<{ key: string; label: string; expected: number; actual: number }> {
  const expected = batch.expected_token_counts;
  const actual = batch.actual_token_counts;
  if (!expected && !actual) {
    return [];
  }
  const keys = Object.keys(tokenCategoryText) as Array<keyof DocumentReviewTokenCountsResponse>;
  return keys
    .map((key) => ({
      key,
      label: tokenCategoryText[key],
      expected: expected?.[key] ?? 0,
      actual: actual?.[key] ?? 0,
    }))
    .filter((row) => row.expected > 0 || row.actual > 0);
}

function triggerTermProposal(prefillSource = "", prefillTarget = ""): void {
  const selectedText = !prefillSource && typeof window !== "undefined"
    ? (window.getSelection()?.toString() || "").trim()
    : "";
  const sourceTerm = prefillSource || (selectedText.length <= 120 ? selectedText : "");
  const firstPair = contentPairs.value[0];
  const excerpt = firstPair?.sourceText || props.selectedBlock?.excerpt || "";
  const pageText = props.selectedBlock ? documentReviewSourcePagesText(props.selectedBlock.source_spans) : "";
  emit("propose-term", {
    sourceTerm,
    targetTerm: prefillTarget,
    excerpt,
    contextSummary: props.selectedBlock ? `块 ${props.selectedBlock.block_id}（${pageText}）` : "",
  });
}
</script>

<style scoped lang="scss">
.review-content-pane {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow-y: auto;
  padding-right: 4px;
}

.content-empty {
  padding: 40px 20px;
  text-align: center;
  border: 1px dashed var(--app-color-border-soft);
  border-radius: var(--app-radius-lg);
  color: var(--app-color-text-muted);
}

.content-empty strong {
  display: block;
  margin-bottom: 6px;
  color: var(--app-color-text);
}

.block-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-lg);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
}

.block-header-main {
  display: grid;
  gap: 6px;
  min-width: 0;
  flex: 1 1 240px;
}

.block-header-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.block-title {
  margin: 0;
  font-size: 16px;
  color: var(--app-color-text);
  overflow-wrap: anywhere;
}

.block-location-detail {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.content-card {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-lg);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
}

.content-card h3 {
  margin: 0;
  font-size: 14px;
  color: var(--app-color-text);
}

.card-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.card-hint {
  color: var(--app-color-text-faint);
  font-size: 12px;
}

.flag-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.flag-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.flag-suggestion {
  color: var(--app-color-text);
}

.flag-code {
  color: var(--app-color-text-faint);
}

.reference-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.reference-item {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
}

.reference-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
}

.reference-thumb-btn {
  display: block;
  width: 100%;
  padding: 0;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-sm);
  background: #ffffff;
  cursor: zoom-in;
  overflow: hidden;
}

.reference-thumb {
  display: block;
  width: 100%;
  max-height: 220px;
  object-fit: contain;
}

.reference-status {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.reference-status.is-error {
  color: var(--app-color-danger, #dc2626);
}

.part-empty {
  padding: 12px;
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
  color: var(--app-color-text);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.part-list {
  display: grid;
  gap: 10px;
}

.part-card {
  display: grid;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
}

.part-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.part-kind {
  font-weight: 700;
  color: var(--app-color-text);
}

.part-field {
  color: var(--app-color-text-faint);
}

.part-truncated {
  margin-left: auto;
  color: var(--app-color-warning, #b45309);
  font-weight: 600;
}

.translation-compare {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.compare-col {
  display: grid;
  gap: 4px;
  padding: 8px 10px;
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
}

.compare-label {
  color: var(--app-color-text-faint);
  font-size: 11px;
  font-weight: 700;
}

.compare-text,
.single-text {
  margin: 0;
  color: var(--app-color-text);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.single-text {
  padding: 8px 10px;
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
}

.load-more-parts {
  display: flex;
  justify-content: center;
}

.term-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.term-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-pill);
  background: var(--app-color-surface-soft);
  color: var(--app-color-text);
  font-size: 12px;
  cursor: pointer;
}

.term-chip:hover {
  border-color: var(--app-color-primary-border);
}

.batch-list,
.table-evidence-list {
  display: grid;
  gap: 10px;
}

.batch-card,
.table-evidence-card {
  display: grid;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
}

.batch-head,
.table-evidence-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.batch-tags,
.table-evidence-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.batch-meta,
.table-grid-stats {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.token-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.token-pill {
  padding: 2px 8px;
  border-radius: var(--app-radius-pill);
  background: var(--app-color-surface);
  border: 1px solid var(--app-color-border-soft);
  font-size: 12px;
  color: var(--app-color-text);
}

.token-pill.is-mismatch {
  border-color: var(--app-color-danger, #dc2626);
  color: var(--app-color-danger, #dc2626);
  font-weight: 700;
}

.semantics-block {
  display: grid;
  gap: 6px;
  padding: 10px;
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
  border: 1px solid var(--app-color-border-soft);
}

.semantics-block h4 {
  margin: 0;
  font-size: 13px;
  color: var(--app-color-warning, #b45309);
}

.semantics-list {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
}

.semantics-cols {
  display: block;
  color: var(--app-color-text-muted);
}

@media (max-width: 720px) {
  .translation-compare {
    grid-template-columns: 1fr;
  }
}
</style>
