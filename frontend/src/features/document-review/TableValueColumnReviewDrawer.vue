<!-- 文件：frontend/src/features/document-review/TableValueColumnReviewDrawer.vue -->
<!-- 用途：Admin 可视化表格值列核定抽屉，结合原始参考图缩放拖拽与严格表项校验，按 replay_table_value_columns 幂等发起同包重算新代。 -->
<template>
  <el-drawer
    v-model="controller.visible.value"
    title="表格值列核定模式（同源 MinerU 重算新代）"
    direction="rtl"
    size="min(920px, 96vw)"
    :append-to-body="true"
    class="table-value-review-drawer"
  >
    <div class="table-review-body app-scrollbar-persistent">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="仅支持原文直转（direct）且位于试点名单的任务。提交后将按 action=replay_table_value_columns 直接从原 MinerU 存档重算新一代，严禁包含自动出处（pdf_binding）。"
      />

      <ApiErrorAlert :error="controller.error.value" />
      <p v-if="reasonExplanation" class="replay-reason-explanation">{{ reasonExplanation }}</p>

      <el-alert
        v-if="controller.form.needsReconcile"
        type="warning"
        :closable="false"
        show-icon
        title="上次核定提交结果未确认，已保留同一请求 ID，禁止自动换 key 重试"
      >
        <div class="reconcile-bar">
          <span>保留请求 ID：<strong class="mono">{{ controller.form.requestId }}</strong></span>
          <el-button size="small" type="warning" :loading="controller.reconciling.value" @click="controller.reconcile()">
            对账核定请求
          </el-button>
          <el-button
            v-if="controller.form.notFoundOnReconcile"
            size="small"
            text
            type="primary"
            @click="controller.resetAfterNotFound(latestExpectedSource)"
          >
            确认未受理并重置 ID
          </el-button>
        </div>
      </el-alert>

      <el-alert
        v-if="controller.lastResult.value"
        type="success"
        :closable="false"
        show-icon
        :title="`核定新代已受理：第 ${controller.lastResult.value.accepted_generation + 1} 代（审计 ID：${controller.lastResult.value.audit_id}）`"
      />

      <div v-if="!controller.fragments.value.length" class="empty-findings">
        当前任务未检测到待核定的数值跨列发现或未解析数值列。
      </div>

      <template v-else>
        <!-- 片段切换 -->
        <div v-if="controller.fragments.value.length > 1" class="fragment-tabs">
          <el-radio-group v-model="controller.activeFragmentId.value" size="small">
            <el-radio-button
              v-for="frag in controller.fragments.value"
              :key="frag.fragmentId"
              :value="frag.fragmentId"
            >
              {{ frag.tableId }} · P{{ frag.pageIndex + 1 }} ({{ frag.corrections.length }})
            </el-radio-button>
          </el-radio-group>
        </div>

        <template v-if="activeFragment">
          <!-- 上方：表格原始参考图（滚轮缩放 + 鼠标拖拽平移） -->
          <section class="visual-stage" aria-label="表格原始参考图对比区">
            <div class="stage-toolbar">
              <div>
                <strong>原始表格参考截图</strong>
                <span class="mono stage-sub">{{ activeFragment.fragmentId }} · 源 PDF 第 {{ activeFragment.pageIndex + 1 }} 页</span>
              </div>
              <div class="stage-zoom-controls">
                <el-button size="small" @click="adjustZoom(-25)">-</el-button>
                <span class="zoom-text">{{ zoomPercent }}%</span>
                <el-button size="small" @click="adjustZoom(25)">+</el-button>
                <el-button size="small" text @click="resetPanZoom">重置视图</el-button>
              </div>
            </div>

            <div
              v-if="activeRefUrl"
              class="pan-viewport"
              :class="{ 'is-dragging': dragging }"
              @wheel.prevent="onWheelZoom"
              @pointerdown="startDrag"
              @pointermove="onDragMove"
              @pointerup="endDrag"
              @pointercancel="endDrag"
            >
              <img
                :src="activeRefUrl"
                :alt="`核定参考图 ${activeFragment.fragmentId}`"
                class="pan-image"
                draggable="false"
                :style="panImageStyle"
              />
            </div>
            <div v-else class="stage-unavailable">
              未找到该片段的可展示参考截图（请先在主工作台选中对应表格块或打开源 PDF 第 {{ activeFragment.pageIndex + 1 }} 页对照）。
            </div>
          </section>

          <!-- 中间：待核定跨列发现清单 -->
          <section class="findings-section" aria-label="待核定数值列清单">
            <div class="section-head">
              <h3>待核定单元格（{{ activeFragment.corrections.length }} 项）</h3>
              <span class="section-hint">点击候选值列快捷指派，或手动调整左闭右开列区间 [起始列, 结束列)</span>
            </div>

            <div class="correction-list">
              <article v-for="item in activeFragment.corrections" :key="item.key" class="correction-card">
                <div class="correction-head">
                  <el-checkbox v-model="item.enabled">
                    <strong>第 {{ item.sourceRowIndex + 1 }} 行</strong>
                    · 值 <span class="mono">{{ item.valueText }}</span>
                    <span v-if="item.unitText"> {{ item.unitText }}</span>
                  </el-checkbox>
                  <el-tag v-if="item.reasonCode" size="small" type="warning" effect="plain">
                    {{ tableUnresolvedReasonLabel(item.reasonCode) }}
                  </el-tag>
                </div>

                <div v-if="item.candidateColumns.length" class="candidate-strip">
                  <span>候选列快捷指派：</span>
                  <el-button
                    v-for="cand in item.candidateColumns"
                    :key="`${item.key}-${cand.column}`"
                    size="small"
                    :type="item.targetColumn === cand.column ? 'primary' : 'default'"
                    :plain="item.targetColumn !== cand.column"
                    @click="selectCandidate(item, cand)"
                  >
                    列 {{ cand.column + 1 }} ({{ cand.label }})
                  </el-button>
                </div>

                <div class="correction-grid">
                  <label class="grid-field">
                    <span>源格序号 (source_cell_index)</span>
                    <el-input-number v-model="item.sourceCellIndex" :min="0" :step="1" size="small" controls-position="right" />
                  </label>
                  <label class="grid-field">
                    <span>原起始列 (含)</span>
                    <el-input-number v-model="item.rangeStart" :min="0" :step="1" size="small" controls-position="right" />
                  </label>
                  <label class="grid-field">
                    <span>原结束列 (不含)</span>
                    <el-input-number v-model="item.rangeEnd" :min="1" :step="1" size="small" controls-position="right" />
                  </label>
                  <label class="grid-field">
                    <span>核定目标列 (target_column)</span>
                    <el-input-number v-model="item.targetColumn" :min="0" :step="1" size="small" controls-position="right" />
                  </label>
                  <label class="grid-field">
                    <span>值列角色 (target_header)</span>
                    <el-select v-model="item.targetHeader" size="small">
                      <el-option v-for="hdr in TABLE_VALUE_TARGET_HEADERS" :key="hdr" :label="hdr" :value="hdr" />
                    </el-select>
                  </label>
                  <label class="grid-field grid-field--wide">
                    <span>单元格内容摘要 (content_sha256，64 位 hex)</span>
                    <el-input v-model="item.contentSha256" size="small" placeholder="64 位小写十六进制 SHA256" />
                  </label>
                </div>
              </article>
            </div>
          </section>

          <!-- 片段来源指纹绑定与 JSON 快捷导入 -->
          <section class="provenance-section" aria-label="片段来源指纹绑定">
            <div class="section-head">
              <h3>片段来源指纹绑定（table-value-column-review/v1）</h3>
              <span class="section-hint">
                {{ controller.loadingSourceHash.value ? "正在读取源 PDF SHA256…" : "支持粘贴核定模板 JSON 一键回填，或逐项核对填写" }}
              </span>
            </div>

            <div class="json-import-box">
              <el-input
                v-model="controller.importJsonText.value"
                type="textarea"
                :rows="3"
                placeholder='可选：粘贴 table-value-column-review/v1 JSON（单对象或数组）自动回填来源指纹与单元格 content_sha256'
              />
              <div class="json-import-actions">
                <el-button size="small" @click="controller.applyImportedJson()">导入并回填指纹</el-button>
                <span v-if="controller.importError.value" class="import-error">{{ controller.importError.value }}</span>
              </div>
            </div>

            <div class="provenance-grid">
              <label class="grid-field">
                <span>source_pdf_sha256</span>
                <el-input v-model="activeFragment.sourcePdfSha256" size="small" placeholder="64 位小写 hex" />
              </label>
              <label class="grid-field">
                <span>content_list_sha256</span>
                <el-input v-model="activeFragment.contentListSha256" size="small" placeholder="64 位小写 hex" />
              </label>
              <label class="grid-field">
                <span>raw_html_sha256</span>
                <el-input v-model="activeFragment.rawHtmlSha256" size="small" placeholder="64 位小写 hex" />
              </label>
              <label class="grid-field">
                <span>json_pointer</span>
                <el-input v-model="activeFragment.jsonPointer" size="small" placeholder="例如 /0/0 或 /content_list/0/2" />
              </label>
            </div>
          </section>
        </template>

        <!-- 实时校验清单 -->
        <el-alert
          v-if="!controller.validation.value.valid"
          type="warning"
          :closable="false"
          show-icon
          title="尚有以下核定约束未满足，补齐后即可提交"
        >
          <ul class="validation-list">
            <li v-for="(msg, idx) in controller.validation.value.errors.slice(0, 6)" :key="idx">{{ msg }}</li>
          </ul>
        </el-alert>

        <!-- 核定原因与幂等键 -->
        <section class="submit-meta-section">
          <div class="meta-row">
            <span>幂等请求 ID：<strong class="mono">{{ controller.form.requestId }}</strong></span>
            <span v-if="controller.form.expectedSource">
              锁定来源：第 {{ controller.form.expectedSource.generation + 1 }} 代 · {{ shortHash(controller.form.expectedSource.result_sha256, 12) }}
            </span>
          </div>
          <el-input
            v-model="controller.form.note"
            type="textarea"
            :rows="2"
            maxlength="1000"
            show-word-limit
            :disabled="controller.form.needsReconcile || Boolean(controller.lastResult.value)"
            placeholder="填写人工核定说明（1–1000 字，例如：对照原表截图核定第 4 行 75 uV 归属 TYP 列）"
          />
        </section>
      </template>
    </div>

    <template #footer>
      <div class="drawer-footer">
        <el-button @click="controller.close()">关闭</el-button>
        <el-button
          v-if="!controller.lastResult.value"
          type="primary"
          :loading="controller.submitting.value"
          :disabled="!controller.canSubmit.value"
          @click="controller.submit()"
        >
          提交核定并重算新一代
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type {
  DocumentJobTableReferenceResponse,
  DocumentQualityValueColumnResponse,
  ReviewExpectedSourceRequest,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { shortHash, tableUnresolvedReasonLabel } from "./documentReviewFormat";
import {
  mapValueColumnLabelToTargetHeader,
  TABLE_VALUE_TARGET_HEADERS,
  tableReplayReasonLabel,
  type TableValueCorrectionDraft,
} from "./tableValueColumnReview";
import type { TableValueColumnReviewController } from "./useTableValueColumnReview";

const props = defineProps<{
  controller: TableValueColumnReviewController;
  tableReferences: DocumentJobTableReferenceResponse[];
  tableRefObjectUrls: Record<string, string>;
  latestExpectedSource?: ReviewExpectedSourceRequest | null;
}>();

const zoomPercent = ref(100);
const panX = ref(0);
const panY = ref(0);
const dragging = ref(false);
let dragOriginX = 0;
let dragOriginY = 0;

const activeFragment = computed(() => props.controller.activeFragment.value);

const activeRefUrl = computed(() => {
  const fragmentId = activeFragment.value?.fragmentId;
  if (!fragmentId) {
    return "";
  }
  const matchedRef = props.tableReferences.find((item) => item.fragment_id === fragmentId && item.content_path);
  return matchedRef?.content_path ? props.tableRefObjectUrls[matchedRef.content_path] || "" : "";
});

const reasonExplanation = computed(() => tableReplayReasonLabel(props.controller.error.value?.reasonCode));

const panImageStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoomPercent.value / 100})`,
}));

function adjustZoom(delta: number): void {
  zoomPercent.value = Math.min(250, Math.max(50, zoomPercent.value + delta));
}

function resetPanZoom(): void {
  zoomPercent.value = 100;
  panX.value = 0;
  panY.value = 0;
}

function onWheelZoom(event: WheelEvent): void {
  adjustZoom(event.deltaY < 0 ? 15 : -15);
}

function startDrag(event: PointerEvent): void {
  dragging.value = true;
  dragOriginX = event.clientX - panX.value;
  dragOriginY = event.clientY - panY.value;
}

function onDragMove(event: PointerEvent): void {
  if (!dragging.value) {
    return;
  }
  panX.value = event.clientX - dragOriginX;
  panY.value = event.clientY - dragOriginY;
}

function endDrag(): void {
  dragging.value = false;
}

function selectCandidate(item: TableValueCorrectionDraft, candidate: DocumentQualityValueColumnResponse): void {
  item.targetColumn = candidate.column;
  item.targetHeader = mapValueColumnLabelToTargetHeader(candidate.label);
}

watch(
  () => activeFragment.value?.fragmentId,
  () => {
    resetPanZoom();
  },
);
</script>

<style scoped lang="scss">
.table-review-body {
  display: grid;
  gap: 14px;
  max-height: calc(100vh - 150px);
  overflow-y: auto;
  padding-right: 6px;
}

.replay-reason-explanation {
  margin: 0;
  color: var(--app-color-danger, #dc2626);
  font-size: 13px;
}

.reconcile-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.empty-findings {
  padding: 28px 16px;
  text-align: center;
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.visual-stage,
.findings-section,
.provenance-section,
.submit-meta-section {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
}

.stage-toolbar,
.section-head,
.meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.section-head h3 {
  margin: 0;
  font-size: 14px;
  color: var(--app-color-text);
}

.stage-sub,
.section-hint,
.meta-row {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.stage-sub {
  margin-left: 8px;
}

.stage-zoom-controls {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.zoom-text {
  min-width: 42px;
  text-align: center;
  font-size: 12px;
  color: var(--app-color-text-muted);
}

.pan-viewport {
  position: relative;
  height: 240px;
  overflow: hidden;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-sm);
  background: #ffffff;
  cursor: grab;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
}

.pan-viewport.is-dragging {
  cursor: grabbing;
}

.pan-image {
  max-width: 100%;
  max-height: 100%;
  transform-origin: center center;
  pointer-events: none;
}

.stage-unavailable {
  padding: 16px;
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.correction-list {
  display: grid;
  gap: 10px;
}

.correction-card {
  display: grid;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
}

.correction-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.candidate-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--app-color-text-muted);
}

.correction-grid,
.provenance-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px 10px;
}

.grid-field {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: var(--app-color-text-muted);
}

.grid-field--wide {
  grid-column: 1 / -1;
}

.json-import-box {
  display: grid;
  gap: 6px;
}

.json-import-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.import-error {
  color: var(--app-color-danger, #dc2626);
  font-size: 12px;
}

.validation-list {
  margin: 4px 0 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.5;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
