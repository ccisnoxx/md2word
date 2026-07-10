<!-- frontend/src/pages/TemplateListPage.vue：Word 模板文档列表。 -->
<template>
  <main class="template-list-page app-page" aria-labelledby="templates-title">
    <WorkbenchPageHeader
      title-id="templates-title"
      kicker="Word 模板文档"
      title="Word 模板文档"
      description="管理 DOCX 模板文件、默认页眉内容、公司 Logo、模板版本和发布流程。"
      wide
      section-class="page-heading app-page-header"
      actions-class="toolbar"
    >
      <template #actions>
        <el-button :icon="Brush" @click="$router.push('/settings/word-page-styles')">Word 页面样式配置</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadTemplates">刷新</el-button>
      </template>
    </WorkbenchPageHeader>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <el-alert
      class="app-page-shell app-page-shell--wide"
      title="模板文档负责 DOCX 文件、默认页眉和 Logo；页面样式配置负责页边距、标题、正文、目录和表格等输出格式。"
      type="info"
      show-icon
      :closable="false"
    />

    <section class="app-page-shell app-page-shell--wide">
      <WorkbenchPanelCard
        title="模板列表"
        subtitle="查看模板文档、布局配置入口和默认版本状态。"
        card-class="app-table-card"
      >
        <div class="table-wrap app-scrollbar-persistent">
        <el-table :data="templates" :loading="loading" empty-text="暂无模板" table-layout="fixed" class="template-table">
          <el-table-column prop="id" label="模板 ID" min-width="140">
          <template #default="{ row }">
            <router-link :to="`/settings/templates/${row.id}`" class="mono">{{ row.id }}</router-link>
          </template>
        </el-table-column>
          <el-table-column prop="name" label="名称" min-width="150" />
          <el-table-column prop="description" label="说明" min-width="180" show-overflow-tooltip />
          <el-table-column prop="version" label="当前版本" width="96" />
          <el-table-column label="默认" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
          <el-table-column label="模板文件" min-width="150">
          <template #default="{ row }">
            <span>{{ row.template.file_name || "-" }}</span>
          </template>
        </el-table-column>
          <el-table-column label="样式配置" min-width="150">
          <template #default="{ row }">
            <router-link :to="`/settings/word-page-styles/${row.id}`">{{ row.layout_config.file_name || "配置页面样式" }}</router-link>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/settings/templates/${row.id}`)">管理文档</el-button>
          </template>
        </el-table-column>
        </el-table>
        </div>
      </WorkbenchPanelCard>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Brush, Refresh } from "@element-plus/icons-vue";

import { templatesApi } from "@/api/templates";
import type { TemplateListItemResponse } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
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
.template-list-page {
  display: grid;
  gap: var(--app-space-4);
}

.template-list-page > .app-page-shell {
  width: 100%;
  max-width: 100%;
}

.table-wrap {
  overflow-x: auto;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.template-table {
  width: 100%;
  min-width: 920px;
}
</style>
