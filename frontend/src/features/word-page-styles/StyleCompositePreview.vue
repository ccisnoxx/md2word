<!-- 文件：frontend/src/features/word-page-styles/StyleCompositePreview.vue -->
<!-- 用途：页面样式编辑器右栏，提供紧凑变更摘要卡与微缩 A4 Datasheet 组合近似预览画布（支持双向点击高亮联动）。 -->
<template>
  <aside class="style-right-rail" aria-label="配置变更摘要">
    <WorkbenchPanelCard
      title="变更摘要"
      card-class="change-panel"
      body-class="change-panel-body"
    >
      <template #actions>
        <div class="change-panel-actions">
          <el-tag v-if="editor.isLayoutDirty.value" size="small" type="warning" effect="plain">
            {{ editor.dirtyFieldCount.value }}
          </el-tag>
          <el-button
            v-if="editor.isLayoutDirty.value"
            size="small"
            link
            type="primary"
            @click="editor.dirtyDrawerOpen.value = true"
          >
            完整差异
          </el-button>
        </div>
      </template>

      <p v-if="!editor.isLayoutDirty.value" class="change-empty">当前没有未保存改动。</p>
      <ul v-else class="change-list">
        <li v-for="item in editor.visibleDirtySummaries.value" :key="item.path">
          <button type="button" class="change-jump" @click="editor.setActiveGroup(item.groupName)">
            <strong>{{ item.label }}</strong>
            <span>{{ item.before }} → {{ item.after }}</span>
          </button>
        </li>
      </ul>
      <p v-if="editor.dirtySummaries.value.length > editor.visibleDirtySummaries.value.length" class="change-more">
        还有 {{ editor.dirtySummaries.value.length - editor.visibleDirtySummaries.value.length }} 项改动，点击上方「完整差异」查看全部。
      </p>
      <div class="change-note">
        保存只创建 draft version；完成验证、发布并设为默认后，后续 Word 生成才会使用。
      </div>
    </WorkbenchPanelCard>

    <WorkbenchPanelCard
      title="A4 组合效果示意"
      subtitle="点击画布区块可快速切换对应样式分组；浏览器近似展示不代表 Word 最终分页与字体替换结果。"
      card-class="preview-panel"
    >
      <template #actions>
        <el-tag size="small" type="info" effect="plain">
          当前：{{ editor.layoutGroupTitle(editor.activeLayoutGroup.value) || "-" }}
        </el-tag>
      </template>

      <div
        class="composite-a4-paper"
        :class="{ 'is-zone-active': activeZone === 'page_setup' }"
        :style="preview.paperStyle"
        :data-active-zone="activeZone"
        aria-label="A4 组合近似预览画布"
      >
        <!-- 页眉区 -->
        <button
          type="button"
          class="a4-zone a4-header"
          :class="{ 'is-active': activeZone === 'header', 'is-disabled-zone': !preview.headerEnabled }"
          @click="editor.selectPreviewZone('header')"
        >
          <span :style="preview.headerStyle">
            {{ preview.headerEnabled ? preview.headerText : "页眉未启用（点击编辑）" }}
          </span>
        </button>

        <!-- 主文档内容区 -->
        <div class="a4-body">
          <!-- 型号与分类 -->
          <button
            type="button"
            class="a4-zone a4-identity"
            :class="{ 'is-active': activeZone === 'identity' }"
            @click="editor.selectPreviewZone('identity')"
          >
            <div :style="preview.partNumberStyle">{{ preview.partNumberText }}</div>
            <div :style="preview.categoryStyle">{{ preview.categoryText }}</div>
          </button>

          <!-- 目录示例条 -->
          <button
            type="button"
            class="a4-zone a4-toc"
            :class="{ 'is-active': activeZone === 'toc' }"
            @click="editor.selectPreviewZone('toc')"
          >
            <div :style="preview.tocTitleStyle">{{ preview.tocTitleText }}</div>
            <div :style="preview.tocEntryStyle">{{ preview.tocEntryText }}</div>
          </button>

          <!-- 一/二/三级标题 -->
          <button
            type="button"
            class="a4-zone"
            :class="{ 'is-active': activeZone === 'heading1' }"
            @click="editor.selectPreviewZone('heading1')"
          >
            <div :style="preview.heading1Style">{{ preview.heading1Text }}</div>
          </button>

          <button
            type="button"
            class="a4-zone"
            :class="{ 'is-active': activeZone === 'heading2' }"
            @click="editor.selectPreviewZone('heading2')"
          >
            <div :style="preview.heading2Style">{{ preview.heading2Text }}</div>
          </button>

          <button
            type="button"
            class="a4-zone"
            :class="{ 'is-active': activeZone === 'heading3' }"
            @click="editor.selectPreviewZone('heading3')"
          >
            <div :style="preview.heading3Style">{{ preview.heading3Text }}</div>
          </button>

          <!-- 正文段落 -->
          <button
            type="button"
            class="a4-zone"
            :class="{ 'is-active': activeZone === 'normal' }"
            @click="editor.selectPreviewZone('normal')"
          >
            <p class="a4-paragraph" :style="preview.normalStyle">{{ preview.normalText }}</p>
          </button>

          <!-- 表题 -->
          <button
            type="button"
            class="a4-zone"
            :class="{ 'is-active': activeZone === 'caption' }"
            @click="editor.selectPreviewZone('caption')"
          >
            <div :style="preview.captionStyle">{{ preview.captionText }}</div>
          </button>

          <!-- 参数表 -->
          <button
            type="button"
            class="a4-zone a4-table-zone"
            :class="{ 'is-active': activeZone === 'table' }"
            @click="editor.selectPreviewZone('table')"
          >
            <div class="a4-table-grid" :style="{ borderColor: preview.tableStyles.borderColor }">
              <div class="a4-cell" :style="preview.tableStyles.header">参数</div>
              <div class="a4-cell" :style="preview.tableStyles.header">MIN</div>
              <div class="a4-cell" :style="preview.tableStyles.header">TYP</div>
              <div class="a4-cell" :style="preview.tableStyles.header">MAX</div>

              <div class="a4-cell" :style="preview.tableStyles.cell">失调电压</div>
              <div class="a4-cell" :style="preview.tableStyles.cell">-</div>
              <div class="a4-cell" :style="preview.tableStyles.cell">5 µV</div>
              <div class="a4-cell" :style="preview.tableStyles.cell">75 µV</div>

              <div class="a4-cell" :style="preview.tableStyles.cell">供电电压</div>
              <div class="a4-cell" :style="preview.tableStyles.cell">±2.5 V</div>
              <div class="a4-cell" :style="preview.tableStyles.cell">±15 V</div>
              <div class="a4-cell" :style="preview.tableStyles.cell">±18 V</div>
            </div>
          </button>

          <!-- 表注 -->
          <button
            type="button"
            class="a4-zone"
            :class="{ 'is-active': activeZone === 'table_note' }"
            @click="editor.selectPreviewZone('table_note')"
          >
            <div :style="preview.tableNoteStyle">{{ preview.tableNoteText }}</div>
          </button>
        </div>

        <!-- 页脚与页码 -->
        <button
          type="button"
          class="a4-zone a4-footer"
          :class="{ 'is-active': activeZone === 'footer', 'is-disabled-zone': !preview.footerEnabled }"
          @click="editor.selectPreviewZone('footer')"
        >
          <span :style="preview.footerStyle">{{ preview.footerEnabled ? preview.footerLeftText : "页脚未启用" }}</span>
          <span class="a4-footer-center" :style="preview.footerStyle">
            {{ preview.footerEnabled && preview.footerShowPageNumber ? "1" : "" }}
          </span>
          <span class="a4-footer-right" :style="preview.footerStyle">
            {{ preview.footerEnabled ? preview.footerRightText : "" }}
          </span>
        </button>
      </div>

      <p class="preview-disclaimer">效果示意，最终以该 draft 的真实 Word 验证任务为准。</p>
    </WorkbenchPanelCard>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";

import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import type { WordPageStyleEditor } from "./useWordPageStyleEditor";

const props = defineProps<{
  editor: WordPageStyleEditor;
}>();

const activeZone = computed(() => props.editor.activePreviewZone.value);
const preview = computed(() => props.editor.compositePreview.value);
</script>

<style scoped lang="scss">
.style-right-rail {
  position: sticky;
  top: 86px;
  display: grid;
  gap: var(--app-space-4);
  min-width: 0;
}

.change-panel {
  display: grid;
  gap: var(--app-space-3);
  padding: var(--app-space-4);
}

.change-panel-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.change-empty,
.change-more {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.change-list {
  display: grid;
  gap: 8px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.change-jump {
  width: 100%;
  display: grid;
  gap: 2px;
  padding: 6px 8px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface-soft);
  text-align: left;
  cursor: pointer;
}

.change-jump:hover {
  border-color: var(--app-color-primary-border);
}

.change-jump strong {
  color: var(--app-color-text);
  font-size: 12px;
}

.change-jump span {
  color: var(--app-color-text-muted);
  font-size: 11px;
  overflow-wrap: anywhere;
}

.change-note {
  padding: var(--app-space-3);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.composite-a4-paper {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 6px;
  width: 100%;
  min-height: 360px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  background: #ffffff;
  color: #111827;
  box-shadow: var(--app-shadow-subtle);
  overflow: hidden;
  transition: box-shadow 150ms ease, border-color 150ms ease;
}

.composite-a4-paper.is-zone-active {
  border-color: var(--app-color-primary);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2), var(--app-shadow-subtle);
}

.a4-body {
  display: grid;
  gap: 4px;
  align-content: start;
  flex: 1 1 auto;
}

.a4-zone {
  width: 100%;
  display: block;
  padding: 2px 4px;
  border: 1px solid transparent;
  border-radius: 3px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: border-color 140ms ease, background-color 140ms ease;
}

.a4-zone:hover {
  border-color: rgba(37, 99, 235, 0.35);
  background: rgba(37, 99, 235, 0.04);
}

.a4-zone.is-active {
  border-color: var(--app-color-primary, #2563eb);
  background: rgba(37, 99, 235, 0.09);
}

.a4-zone.is-disabled-zone {
  border-style: dashed;
  border-color: #cbd5e1;
}

.a4-header {
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 3px;
  text-align: center;
}

.a4-identity {
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 3px;
}

.a4-toc {
  background: #f8fafc;
}

.a4-paragraph {
  margin: 0;
}

.a4-table-grid {
  display: grid;
  grid-template-columns: 1.5fr repeat(3, 1fr);
  border-top: 1px solid;
  border-left: 1px solid;
}

.a4-cell {
  padding: 2px 3px;
  border-right: 1px solid;
  border-bottom: 1px solid;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.a4-footer {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 4px;
  border-top: 1px solid #e2e8f0;
  padding-top: 3px;
}

.a4-footer-center {
  text-align: center;
}

.a4-footer-right {
  text-align: right;
}

.preview-disclaimer {
  margin: var(--app-space-2) 0 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 1180px) {
  .style-right-rail {
    position: static;
    grid-column: 1 / -1;
  }
}
</style>
