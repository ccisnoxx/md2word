<!-- frontend/src/pages/WordPageStyleListPage.vue: Admin entry for Word page style configuration. -->
<template>
  <main class="word-style-list-page app-page" aria-labelledby="word-style-title">
    <section class="page-heading app-page-header app-page-shell app-page-shell--wide">
      <div>
        <p class="page-kicker">Word 页面样式配置</p>
        <h1 id="word-style-title" class="page-title">Word 页面样式配置</h1>
        <p class="page-description">可视化维护 Word 输出中的页边距、标题、目录、正文、表格和页眉页脚文字样式。</p>
      </div>
      <div class="toolbar">
        <el-button :icon="Document" @click="$router.push('/settings/templates')">Word 模板文档</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadTemplates">刷新</el-button>
      </div>
    </section>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <el-alert
      class="app-page-shell app-page-shell--wide"
      title="公司 Logo、默认页眉内容和 DOCX 文件由 Word 模板文档维护；这里仅维护后续生成 Word 时应用的页面排版样式。"
      type="info"
      show-icon
      :closable="false"
    />

    <el-card class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <el-table class="word-style-table" :data="templates" :loading="loading" empty-text="暂无模板">
        <el-table-column prop="id" label="模板 ID" min-width="170">
          <template #default="{ row }">
            <router-link :to="`/settings/word-page-styles/${row.id}`" class="mono">{{ row.id }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="模板名称" min-width="180" />
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
        <el-table-column label="样式配置文件" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.layout_config.file_name || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模板文档" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <router-link :to="`/settings/templates/${row.id}`">{{ row.template.file_name || "查看文档" }}</router-link>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button class="row-action-button" link type="primary" :icon="Brush" @click="$router.push(`/settings/word-page-styles/${row.id}`)">
              配置样式
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Brush, Document, Refresh } from "@element-plus/icons-vue";

import { templatesApi } from "@/api/templates";
import type { TemplateListItemResponse } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const templates = ref<TemplateListItemResponse[]>([]);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);

async function loadTemplates(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    templates.value = (await templatesApi.list()).items;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadTemplates();
});
</script>

<style scoped lang="scss">
.word-style-list-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
}

:deep(.word-style-table .cell) {
  min-width: 0;
}

:deep(.word-style-table .row-action-button) {
  max-width: 100%;
  white-space: nowrap;
}
</style>
