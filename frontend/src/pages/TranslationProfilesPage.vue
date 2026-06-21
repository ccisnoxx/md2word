<!-- frontend/src/pages/TranslationProfilesPage.vue: Translation Profile list, draft basics and version actions. -->
<template>
  <main class="translation-profiles-page app-page" aria-labelledby="translation-profiles-title">
    <section class="page-heading app-page-header app-page-shell app-page-shell--wide">
      <div>
        <p class="page-kicker">翻译配置</p>
        <h1 id="translation-profiles-title" class="page-title">翻译配置</h1>
        <p class="page-description">只管理基础字段草稿、发布、设默认和回滚；不提供提示词正文编辑。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </section>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <el-alert
      class="app-page-shell app-page-shell--wide"
      v-if="unavailable"
      type="warning"
      title="当前部署未启用 MySQL resource service，翻译配置版本管理不可用。"
      :closable="false"
      show-icon
    />

    <section v-else class="profile-grid app-page-shell app-page-shell--wide">
      <el-card class="app-panel-card app-table-card" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">配置列表</h2>
            <p class="section-subtitle">选择一个配置查看详情。</p>
          </div>
        </div>
        <el-table :data="profiles" :loading="loading" empty-text="暂无翻译配置" @row-click="selectProfile">
          <el-table-column prop="id" label="配置 ID" min-width="180" />
          <el-table-column prop="default_version" label="默认版本" width="120" />
          <el-table-column prop="target_language" label="目标语言" width="120" />
          <el-table-column prop="domain" label="领域" min-width="180" show-overflow-tooltip />
        </el-table>
      </el-card>

      <el-card class="app-panel-card" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">草稿基础字段</h2>
            <p class="section-subtitle">开放目标语言、领域、提示词版本、模型和批次限制。</p>
          </div>
          <el-tag v-if="draft?.snapshot_hash" class="mono" effect="plain">{{ draft.snapshot_hash }}</el-tag>
        </div>
        <el-empty v-if="!selectedProfileId" description="请选择翻译配置" :image-size="90" />
        <el-form v-else ref="draftFormRef" :model="draftForm" :rules="draftRules" label-width="160px">
          <el-form-item label="目标语言" prop="target_language">
            <el-input v-model="draftForm.target_language" :disabled="!isAdmin" />
          </el-form-item>
          <el-form-item label="领域" prop="domain">
            <el-input v-model="draftForm.domain" :disabled="!isAdmin" />
          </el-form-item>
          <el-form-item label="提示词版本" prop="prompt_version">
            <el-input v-model="draftForm.prompt_version" :disabled="!isAdmin" />
          </el-form-item>
          <el-form-item label="模型" prop="model">
            <el-input v-model="draftForm.model" :disabled="!isAdmin" placeholder="可为空" />
          </el-form-item>
          <el-form-item label="每批最大页数" prop="max_pages_per_batch">
            <el-input-number v-model="draftForm.max_pages_per_batch" :disabled="!isAdmin" :min="1" :max="500" />
          </el-form-item>
          <el-form-item label="每批最大字符数" prop="max_chars_per_batch">
            <el-input-number v-model="draftForm.max_chars_per_batch" :disabled="!isAdmin" :min="1" :max="500000" />
          </el-form-item>
          <RoleGate>
            <el-form-item>
              <el-button type="primary" :loading="savingDraft" @click="saveDraft">保存草稿</el-button>
              <el-button type="success" :loading="publishing" @click="publishDraft">发布并设默认</el-button>
            </el-form-item>
          </RoleGate>
        </el-form>
      </el-card>
    </section>

    <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">已发布版本</h2>
          <p class="section-subtitle">可查看版本并由管理员执行设默认或回滚。</p>
        </div>
      </div>
      <el-table class="published-version-table" :data="detail?.versions || []" :loading="loading" empty-text="暂无已发布版本">
        <el-table-column prop="version" label="版本" width="120" />
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
        <el-table-column prop="target_language" label="目标语言" width="120" />
        <el-table-column prop="domain" label="领域" min-width="180" show-overflow-tooltip />
        <el-table-column prop="prompt_version" label="提示词版本" min-width="180" show-overflow-tooltip />
        <el-table-column prop="model" label="模型" min-width="230" show-overflow-tooltip />
        <el-table-column label="发布时间" width="190">
          <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="管理操作" width="230">
          <template #default="{ row }">
            <RoleGate>
              <span class="version-actions">
                <el-button link type="warning" :disabled="row.is_default" @click="setDefault(row.version)">设默认</el-button>
                <el-button link type="danger" @click="rollback(row.version)">回滚</el-button>
              </span>
            </RoleGate>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import { useRoute } from "vue-router";

import { translationProfilesApi } from "@/api/translationProfiles";
import type {
  TranslationProfileDetailResponse,
  TranslationProfileDraftResponse,
  TranslationProfileListItemResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

const auth = useAuthStore();
const route = useRoute();
const isAdmin = computed(() => auth.user?.role === "admin");
const profiles = ref<TranslationProfileListItemResponse[]>([]);
const selectedProfileId = ref("");
const detail = ref<TranslationProfileDetailResponse | null>(null);
const draft = ref<TranslationProfileDraftResponse | null>(null);
const loading = ref(false);
const savingDraft = ref(false);
const publishing = ref(false);
const unavailable = ref(false);
const error = ref<ApiClientError | null>(null);
const draftFormRef = ref<FormInstance>();

const draftForm = reactive({
  target_language: "",
  domain: "",
  prompt_version: "",
  model: "" as string | null,
  max_pages_per_batch: 20,
  max_chars_per_batch: 60000,
});

const draftRules: FormRules = {
  target_language: [{ required: true, message: "请填写目标语言", trigger: "blur" }],
  domain: [{ required: true, message: "请填写领域", trigger: "blur" }],
  prompt_version: [{ required: true, message: "请填写提示词版本", trigger: "blur" }],
  max_pages_per_batch: [{ required: true, message: "请填写每批最大页数", trigger: "change" }],
  max_chars_per_batch: [{ required: true, message: "请填写每批最大字符数", trigger: "change" }],
};

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  unavailable.value = false;
  try {
    const response = await translationProfilesApi.list();
    profiles.value = response.items;
    const requestedProfileId = queryString("profile_id");
    if (requestedProfileId && profiles.value.some((profile) => profile.id === requestedProfileId)) {
      selectedProfileId.value = requestedProfileId;
    } else {
      selectedProfileId.value ||= profiles.value[0]?.id || "";
    }
    if (selectedProfileId.value) {
      await loadSelectedProfile();
    }
  } catch (caught) {
    const normalized = normalizeApiError(caught);
    if (normalized.status === 503) {
      unavailable.value = true;
    }
    error.value = normalized;
  } finally {
    loading.value = false;
  }
}

function queryString(key: string): string {
  const value = route.query[key];
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

async function selectProfile(profile: TranslationProfileListItemResponse): Promise<void> {
  selectedProfileId.value = profile.id;
  await loadSelectedProfile();
}

async function loadSelectedProfile(): Promise<void> {
  if (!selectedProfileId.value) {
    return;
  }
  const [detailResponse, draftResponse] = await Promise.all([
    translationProfilesApi.get(selectedProfileId.value),
    translationProfilesApi.getDraft(selectedProfileId.value),
  ]);
  detail.value = detailResponse;
  draft.value = draftResponse;
  fillDraftForm(draftResponse);
}

function fillDraftForm(response: TranslationProfileDraftResponse): void {
  draftForm.target_language = response.target_language;
  draftForm.domain = response.domain;
  draftForm.prompt_version = response.prompt_version;
  draftForm.model = response.model || "";
  draftForm.max_pages_per_batch = response.max_pages_per_batch;
  draftForm.max_chars_per_batch = response.max_chars_per_batch;
}

async function saveDraft(): Promise<void> {
  if (!selectedProfileId.value) {
    return;
  }
  const valid = await draftFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  savingDraft.value = true;
  error.value = null;
  try {
    const response = await translationProfilesApi.updateDraft(selectedProfileId.value, {
      target_language: draftForm.target_language,
      domain: draftForm.domain,
      prompt_version: draftForm.prompt_version,
      model: draftForm.model || null,
      max_pages_per_batch: draftForm.max_pages_per_batch,
      max_chars_per_batch: draftForm.max_chars_per_batch,
    });
    draft.value = response;
    fillDraftForm(response);
    ElMessage.success("翻译配置草稿已保存。");
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    savingDraft.value = false;
  }
}

async function publishDraft(): Promise<void> {
  if (!selectedProfileId.value) {
    return;
  }
  const valid = await draftFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  publishing.value = true;
  error.value = null;
  try {
    await translationProfilesApi.publish(selectedProfileId.value, { make_default: true });
    ElMessage.success("翻译配置已发布。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    publishing.value = false;
  }
}

async function setDefault(version: string): Promise<void> {
  if (!selectedProfileId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm("将该已发布版本切换为默认翻译配置版本。", `设默认 ${version}`, {
      confirmButtonText: "设默认",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  error.value = null;
  try {
    await translationProfilesApi.setDefault(selectedProfileId.value, version);
    ElMessage.success("默认翻译配置已切换。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function rollback(version: string): Promise<void> {
  if (!selectedProfileId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm("回滚会基于该版本恢复翻译配置，请确认这是已发布版本。", `回滚 ${version}`, {
      confirmButtonText: "回滚",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  error.value = null;
  try {
    await translationProfilesApi.rollback(selectedProfileId.value, { version });
    ElMessage.success("已完成回滚。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

onMounted(() => {
  void loadAll();
});
</script>

<style scoped lang="scss">
.translation-profiles-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
}

.profile-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 520px);
  gap: var(--app-space-4);
}

@media (max-width: 1040px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}

:deep(.published-version-table .cell) {
  min-width: 0;
}

:deep(.published-version-table .version-actions) {
  display: inline-flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: var(--app-space-2);
  max-width: 100%;
}

:deep(.published-version-table .version-actions .el-button + .el-button) {
  margin-left: 0;
}
</style>
