<!-- frontend/src/pages/TemplateListPage.vue: Template Profile list for configuration management. -->
<template>
  <main class="template-list-page" aria-labelledby="templates-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Template Profile</p>
        <h1 id="templates-title">模板配置</h1>
        <p>查看当前模板、默认状态和可下载资源。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadTemplates">刷新</el-button>
    </section>

    <ApiErrorAlert :error="error" />

    <el-card class="card-flat" shadow="never">
      <el-table :data="templates" :loading="loading" empty-text="暂无模板">
        <el-table-column prop="id" label="模板 ID" min-width="180">
          <template #default="{ row }">
            <router-link :to="`/settings/templates/${row.id}`" class="mono">{{ row.id }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column prop="version" label="当前版本" width="110" />
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
        <el-table-column label="模板文件" min-width="180">
          <template #default="{ row }">
            <span>{{ row.template.file_name || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/settings/templates/${row.id}`)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Refresh } from "@element-plus/icons-vue";

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
.template-list-page {
  display: grid;
  gap: 16px;
}
</style>
