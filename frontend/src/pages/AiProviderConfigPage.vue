<!-- frontend/src/pages/AiProviderConfigPage.vue: Admin AI provider runtime configuration page. -->
<template>
  <main class="ai-provider-page app-page" aria-labelledby="ai-provider-title">
    <section class="app-page-header app-page-shell">
      <div>
        <p class="page-kicker">配置中心</p>
        <h1 id="ai-provider-title" class="page-title">AI 配置</h1>
        <p class="page-description">配置翻译链路使用的 OpenAI-compatible provider。</p>
      </div>
      <div class="header-actions">
        <el-tag :type="config?.api_key_configured ? 'success' : 'warning'" effect="plain">
          key={{ config?.api_key_configured ? "configured" : "missing" }}
        </el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="loadConfig">刷新</el-button>
      </div>
    </section>

    <ApiErrorAlert class="app-page-shell" :error="error" :diagnostic-context="errorDiagnosticContext" />

    <section class="config-grid app-page-shell">
      <el-card class="app-panel" shadow="never">
        <template #header>
          <div class="section-header">
            <div>
              <h2 class="section-title">Provider</h2>
              <p class="section-subtitle">当前来源：{{ sourceText }}</p>
            </div>
          </div>
        </template>

        <el-form label-position="top" class="provider-form" @submit.prevent="submit">
          <el-form-item label="Backend">
            <el-select v-model="form.backend" class="full-control">
              <el-option label="disabled" value="disabled" />
              <el-option label="openai_compatible" value="openai_compatible" />
            </el-select>
          </el-form-item>

          <el-form-item label="Base URL">
            <el-input v-model="form.base_url" placeholder="https://api.example.com/v1" clearable />
          </el-form-item>

          <el-form-item label="Model">
            <el-input v-model="form.model" placeholder="deepseek-v4-flash" clearable />
          </el-form-item>

          <div class="numeric-row">
            <el-form-item label="Timeout 秒">
              <el-input-number v-model="form.timeout_seconds" :min="1" :max="600" controls-position="right" />
            </el-form-item>
            <el-form-item label="Max tokens">
              <el-input-number v-model="form.max_output_tokens" :min="1" :max="200000" controls-position="right" />
            </el-form-item>
          </div>

          <el-form-item label="API Key">
            <el-input v-model="form.api_key" type="password" show-password clearable placeholder="留空则保留当前运行时 key" />
          </el-form-item>

          <el-checkbox v-model="form.clear_api_key">清除已保存的运行时 API Key</el-checkbox>

          <div class="form-actions">
            <el-button type="primary" :icon="Check" :loading="saving" native-type="submit">保存配置</el-button>
          </div>
        </el-form>
      </el-card>

      <el-card class="app-panel" shadow="never">
        <template #header>
          <div class="section-header">
            <div>
              <h2 class="section-title">当前状态</h2>
              <p class="section-subtitle">密钥只显示脱敏状态。</p>
            </div>
          </div>
        </template>

        <el-descriptions v-loading="loading" :column="1" border>
          <el-descriptions-item label="Backend">{{ config?.backend || "-" }}</el-descriptions-item>
          <el-descriptions-item label="Base URL">{{ config?.base_url || "-" }}</el-descriptions-item>
          <el-descriptions-item label="Model">{{ config?.model || "-" }}</el-descriptions-item>
          <el-descriptions-item label="API Key">{{ config?.api_key_mask || "-" }}</el-descriptions-item>
          <el-descriptions-item label="Timeout">{{ config?.timeout_seconds ?? "-" }}</el-descriptions-item>
          <el-descriptions-item label="Max tokens">{{ config?.max_output_tokens ?? "-" }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDateTime(config?.updated_at || null) }}</el-descriptions-item>
          <el-descriptions-item label="更新人">{{ config?.updated_by || "-" }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Check, Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import {
  aiProviderConfigApi,
  type AiProviderBackend,
  type AiProviderConfigResponse,
} from "@/api/aiProviderConfig";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

type AiProviderForm = {
  backend: AiProviderBackend;
  base_url: string;
  model: string;
  timeout_seconds: number;
  max_output_tokens: number;
  api_key: string;
  clear_api_key: boolean;
};

const config = ref<AiProviderConfigResponse | null>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref<ApiClientError | null>(null);
const errorDiagnosticContext = { route: "/settings/ai-provider", operation: "ai_provider_config" };

const form = reactive<AiProviderForm>({
  backend: "disabled",
  base_url: "",
  model: "",
  timeout_seconds: 120,
  max_output_tokens: 12000,
  api_key: "",
  clear_api_key: false,
});

const sourceText = computed(() => (config.value?.source === "runtime_config" ? "前端运行时配置" : "环境变量配置"));

async function loadConfig(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const response = await aiProviderConfigApi.get();
    config.value = response;
    applyConfigToForm(response);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  saving.value = true;
  error.value = null;
  try {
    const nextConfig = await aiProviderConfigApi.update({
      backend: form.backend,
      base_url: optionalText(form.base_url),
      model: optionalText(form.model),
      timeout_seconds: form.timeout_seconds,
      max_output_tokens: form.max_output_tokens,
      ...(form.api_key.trim() ? { api_key: form.api_key.trim() } : {}),
      clear_api_key: form.clear_api_key,
    });
    config.value = nextConfig;
    applyConfigToForm(nextConfig);
    ElMessage.success("AI 配置已保存。");
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    saving.value = false;
  }
}

function applyConfigToForm(nextConfig: AiProviderConfigResponse): void {
  form.backend = nextConfig.backend;
  form.base_url = nextConfig.base_url || "";
  form.model = nextConfig.model || "";
  form.timeout_seconds = nextConfig.timeout_seconds;
  form.max_output_tokens = nextConfig.max_output_tokens;
  form.api_key = "";
  form.clear_api_key = false;
}

function optionalText(value: string): string | null {
  const normalized = value.trim();
  return normalized || null;
}

onMounted(() => {
  void loadConfig();
});
</script>

<style scoped>
.ai-provider-page {
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
  grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.7fr);
  gap: var(--app-space-4);
}

.provider-form {
  display: grid;
  gap: var(--app-space-2);
}

.full-control {
  width: 100%;
}

.numeric-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--app-space-3);
}

:deep(.el-input-number) {
  width: 100%;
}

@media (max-width: 860px) {
  .config-grid,
  .numeric-row {
    grid-template-columns: 1fr;
  }

  .header-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
