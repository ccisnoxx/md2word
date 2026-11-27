<!-- 文件：frontend/src/pages/WordPageStyleDetailPage.vue -->
<!-- 用途：Word 页面样式配置详情薄页面壳，按后端白名单 schema 编排紧凑页头、大类栏、样式表单与 A4 组合近似预览。 -->
<template>
  <main class="word-style-page app-page" aria-labelledby="word-style-title">
    <StyleEditorHeader :template-id="props.templateId" :editor="editor" />

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="editor.error.value" />

    <el-alert
      v-if="!editor.layoutConfig.value && !editor.layoutConfigLoading.value"
      class="app-page-shell app-page-shell--wide"
      title="未加载到模板页面样式配置"
      type="warning"
      show-icon
      :closable="false"
    />

    <template v-if="editor.layoutConfig.value">
      <section class="style-workbench app-page-shell app-page-shell--wide" aria-label="Word 页面样式编辑器">
        <StyleCategoryRail :editor="editor" />
        <StyleFormPanel :editor="editor" />
        <StyleCompositePreview :editor="editor" />
      </section>
    </template>

    <StyleDirtyDiffDrawer :editor="editor" />
  </main>
</template>

<script setup lang="ts">
import { toRef } from "vue";
import { useRouter } from "vue-router";

import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import StyleCategoryRail from "@/features/word-page-styles/StyleCategoryRail.vue";
import StyleCompositePreview from "@/features/word-page-styles/StyleCompositePreview.vue";
import StyleDirtyDiffDrawer from "@/features/word-page-styles/StyleDirtyDiffDrawer.vue";
import StyleEditorHeader from "@/features/word-page-styles/StyleEditorHeader.vue";
import StyleFormPanel from "@/features/word-page-styles/StyleFormPanel.vue";
import { useWordPageStyleEditor } from "@/features/word-page-styles/useWordPageStyleEditor";

const props = defineProps<{
  templateId: string;
}>();

const editor = useWordPageStyleEditor(toRef(props, "templateId"), useRouter());
</script>

<style scoped lang="scss">
.word-style-page {
  display: grid;
  gap: var(--app-space-4);
}

.style-workbench {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) 330px;
  gap: var(--app-space-4);
  align-items: start;
}

@media (max-width: 1180px) {
  .style-workbench {
    grid-template-columns: 200px minmax(0, 1fr);
  }
}

@media (max-width: 820px) {
  .style-workbench {
    grid-template-columns: 1fr;
  }
}
</style>
