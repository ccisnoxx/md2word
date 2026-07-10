<!-- frontend/src/pages/MinerUConfigPage.vue: 管理员轮换 MinerU API 密钥的独立配置页。 -->
<template>
  <main class="mineru-config-page app-page" aria-labelledby="mineru-config-title">
    <WorkbenchPageHeader
      title-id="mineru-config-title"
      kicker="配置中心"
      title="MinerU 配置"
      description="轮换 PDF 解析链路使用的 MinerU API 密钥，新请求无需重启即可生效。"
    >
      <template #actions>
        <div class="header-actions">
          <el-tag :type="statusTagType" effect="plain">
            key={{ statusText }}
          </el-tag>
          <el-button :icon="Refresh" :loading="loading" @click="loadConfig">刷新</el-button>
        </div>
      </template>
    </WorkbenchPageHeader>

    <ApiErrorAlert class="app-page-shell" :error="error" :diagnostic-context="errorDiagnosticContext" />

    <section class="config-grid app-page-shell">
      <WorkbenchPanelCard
        title="密钥轮换"
        subtitle="保存时只校验非空，不调用 MinerU；新值会覆盖当前运行时配置。"
        card-class="app-panel"
      >
        <el-form label-position="top" class="token-form" @submit.prevent="submit">
          <el-form-item label="新的 API 密钥">
            <el-input
              v-model="form.api_token"
              type="password"
              name="mineru_api_token"
              autocomplete="new-password"
              :maxlength="4096"
              placeholder="输入新的 MinerU API 密钥"
            />
          </el-form-item>

          <p class="security-note">
            页面不会回显当前密钥，也不保留历史值。保存成功后输入框会立即清空。
          </p>

          <div class="form-actions">
            <el-button
              type="primary"
              :icon="Check"
              :loading="saving"
              :disabled="submitDisabled"
              native-type="submit"
            >
              更新密钥
            </el-button>
          </div>
        </el-form>
      </WorkbenchPanelCard>

      <WorkbenchPanelCard
        title="当前状态"
        subtitle="仅展示配置状态和轮换元数据，不展示任何密钥字符。"
        card-class="app-panel"
      >
        <el-descriptions v-loading="loading" :column="1" border>
          <el-descriptions-item label="API 密钥">
            {{ statusText }}
          </el-descriptions-item>
          <el-descriptions-item label="配置来源">{{ sourceText }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDateTime(config?.updated_at || null) }}</el-descriptions-item>
          <el-descriptions-item label="更新人">{{ config?.updated_by || "-" }}</el-descriptions-item>
        </el-descriptions>
      </WorkbenchPanelCard>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Check, Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { mineruConfigApi, type MinerUConfigResponse } from "@/api/mineruConfig";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

const config = ref<MinerUConfigResponse | null>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref<ApiClientError | null>(null);
const errorDiagnosticContext = { route: "/settings/mineru", operation: "mineru_config" };
const form = reactive({ api_token: "" });

const submitDisabled = computed(() => !form.api_token.trim());
const statusText = computed(() => {
  if (!config.value) {
    return "unknown";
  }
  return config.value.api_token_configured ? "configured" : "missing";
});
const statusTagType = computed(() => {
  if (!config.value) {
    return "info";
  }
  return config.value.api_token_configured ? "success" : "warning";
});
const sourceText = computed(() => {
  if (!config.value) {
    return "-";
  }
  return config.value.source === "runtime_config" ? "配置中心运行时文件" : "环境变量 MINERU_API_TOKEN";
});

async function loadConfig(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    config.value = await mineruConfigApi.get();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  const apiToken = form.api_token.trim();
  if (!apiToken) {
    ElMessage.warning("请输入非空的 MinerU API 密钥。");
    return;
  }
  saving.value = true;
  error.value = null;
  try {
    config.value = await mineruConfigApi.update({ api_token: apiToken });
    form.api_token = "";
    ElMessage.success("MinerU 密钥已更新，后续新请求将立即使用新配置。");
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  void loadConfig();
});
</script>

<style scoped>
.mineru-config-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
}

.header-actions,
.form-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.config-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: var(--app-space-4);
}

.token-form {
  display: grid;
  gap: var(--app-space-3);
}

.security-note {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: var(--app-font-size-sm);
  line-height: 1.7;
}

@media (max-width: 860px) {
  .config-grid {
    grid-template-columns: 1fr;
  }

  .header-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
