<!-- 文件：frontend/src/features/word-page-styles/StyleEditorHeader.vue -->
<!-- 用途：压缩版页面样式编辑器顶部操作条，将长文件路径与 SHA256 收纳进「版本元信息」Popover，释放首屏空间。 -->
<template>
  <WorkbenchPageHeader
    title-id="word-style-title"
    kicker="Word 页面样式配置"
    title="Word 页面样式配置"
    :description="`${editor.template.value?.name || templateId}：维护后续 Word 生成时应用的页面排版样式。`"
    wide
    section-class="style-hero app-page-header"
    actions-class="style-actions app-action-row"
  >
    <template #actions>
      <el-select
        v-model="editor.selectedTemplateId.value"
        class="template-switcher"
        filterable
        aria-label="选择模板"
        @change="editor.changeTemplate"
      >
        <el-option
          v-for="item in editor.templates.value"
          :key="item.id"
          :label="`${item.name}${item.is_default ? '（默认）' : ''}`"
          :value="item.id"
        />
      </el-select>
      <el-select
        v-model="editor.selectedVersion.value"
        class="version-switcher"
        aria-label="选择模板版本"
        @change="editor.changeVersion"
      >
        <el-option
          v-for="item in editor.templateVersions.value"
          :key="item.template_version_id"
          :label="`v${item.version} · ${editor.versionStatusLabel(item.status)}${item.is_default ? '（默认）' : ''}${item.legacy_internal_only ? ' · 仅供内部使用' : ''}`"
          :value="item.version"
        />
      </el-select>
      <el-popover
        v-if="editor.layoutConfig.value"
        placement="bottom-end"
        :width="400"
        trigger="click"
      >
        <template #reference>
          <el-button :icon="InfoFilled">版本元信息</el-button>
        </template>
        <div class="version-meta-popover">
          <h4>当前配置版本元信息</h4>
          <dl>
            <div v-for="[fieldName, value] in editor.layoutMetaEntries.value" :key="fieldName">
              <dt>{{ editor.layoutMetaLabel(fieldName) }}</dt>
              <dd>{{ String(value ?? "-") }}</dd>
            </div>
            <div>
              <dt>配置来源路径</dt>
              <dd class="mono">{{ editor.layoutConfig.value.source_path || "-" }}</dd>
            </div>
            <div>
              <dt>配置 SHA256</dt>
              <dd class="mono">{{ editor.layoutConfig.value.config_sha256 || "-" }}</dd>
            </div>
          </dl>
        </div>
      </el-popover>
      <el-button :icon="Document" @click="editor.openTemplateDocument()">模板文档</el-button>
      <el-button
        v-if="editor.layoutConfig.value?.status === 'draft'"
        :disabled="editor.isLegacyInternalVersion.value"
        @click="editor.openValidationFlow()"
      >
        创建验证任务
      </el-button>
      <el-button :icon="Refresh" :loading="editor.loading.value || editor.layoutConfigLoading.value" @click="editor.confirmReloadAll()">
        刷新
      </el-button>
      <el-button :disabled="!editor.isLayoutDirty.value || editor.layoutConfigSaving.value" @click="editor.resetLayoutConfigForm()">
        撤销
      </el-button>
      <el-button
        type="primary"
        :loading="editor.layoutConfigSaving.value"
        :disabled="!editor.layoutConfig.value || !editor.isLayoutDirty.value"
        @click="editor.saveLayoutConfigVersion()"
      >
        保存为草稿版本
      </el-button>
    </template>
  </WorkbenchPageHeader>

  <section v-if="editor.layoutConfig.value" class="compact-status-bar app-page-shell app-page-shell--wide" aria-label="样式版本状态摘要">
    <div class="compact-status-pills">
      <el-tag size="small" effect="plain">
        版本：{{ editor.layoutConfig.value.template_version_id || `v${editor.layoutConfig.value.version}` }}
      </el-tag>
      <el-tag
        size="small"
        :type="editor.isLegacyInternalVersion.value || editor.layoutConfig.value.status === 'draft' ? 'warning' : 'success'"
        effect="plain"
      >
        {{ editor.isLegacyInternalVersion.value ? "仅供内部使用" : editor.layoutConfig.value.status === "draft" ? "草稿版本" : "已发布版本" }}
      </el-tag>
      <el-tag size="small" type="info" effect="plain">
        分组：{{ editor.layoutGroupEntries.value.length }} 项
      </el-tag>
      <el-tag
        size="small"
        :type="editor.isLayoutDirty.value ? 'warning' : 'success'"
        effect="plain"
      >
        {{ editor.isLayoutDirty.value ? `未保存改动：${editor.dirtyFieldCount.value}` : "无未保存改动" }}
      </el-tag>
      <el-button
        v-if="editor.isLayoutDirty.value"
        size="small"
        link
        type="primary"
        @click="editor.dirtyDrawerOpen.value = true"
      >
        查看全部差异
      </el-button>
    </div>
    <p class="compact-boundary-note">
      公司 Logo、默认页眉内容和 DOCX 文件由 Word 模板文档维护；启用页脚覆盖后，可在这里配置左右静态文字和居中页码。
    </p>
  </section>
</template>

<script setup lang="ts">
import { Document, InfoFilled, Refresh } from "@element-plus/icons-vue";

import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import type { WordPageStyleEditor } from "./useWordPageStyleEditor";

defineProps<{
  templateId: string;
  editor: WordPageStyleEditor;
}>();
</script>

<style scoped lang="scss">
.style-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.template-switcher {
  width: 220px;
}

.version-switcher {
  width: 175px;
}

.compact-status-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  padding: 10px 14px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
}

.compact-status-pills {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.compact-boundary-note {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.version-meta-popover {
  display: grid;
  gap: 8px;
}

.version-meta-popover h4 {
  margin: 0;
  font-size: 14px;
  color: var(--app-color-text);
}

.version-meta-popover dl {
  display: grid;
  gap: 8px;
  margin: 0;
}

.version-meta-popover dt {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.version-meta-popover dd {
  margin: 2px 0 0;
  color: var(--app-color-text);
  font-size: 12px;
  overflow-wrap: anywhere;
}

@media (max-width: 820px) {
  .style-actions,
  .template-switcher,
  .version-switcher {
    width: 100%;
  }
}
</style>
