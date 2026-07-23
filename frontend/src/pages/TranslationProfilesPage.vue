<!-- 翻译配置草稿、命名 Prompt 与已发布版本的统一管理页。 -->
<template>
  <main class="translation-profiles-page app-page" aria-labelledby="translation-profiles-title">
    <WorkbenchPageHeader
      title-id="translation-profiles-title"
      kicker="翻译配置"
      title="翻译配置"
      description="维护配置草稿和命名 Prompt；只有发布并设为默认后，变更才会影响后续新任务。"
      wide
      section-class="page-heading app-page-header"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="confirmReloadAll">刷新</el-button>
      </template>
    </WorkbenchPageHeader>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <el-alert
      v-if="unavailable"
      class="app-page-shell app-page-shell--wide"
      type="warning"
      title="当前部署未启用 MySQL resource service，翻译配置版本管理不可用。"
      :closable="false"
      show-icon
    />

    <section v-else class="profile-grid app-page-shell app-page-shell--wide">
      <WorkbenchPanelCard
        title="配置列表"
        subtitle="选择一个语言方向查看草稿和线上版本。"
        card-class="app-table-card"
      >
        <el-table :data="profiles" :loading="loading" empty-text="暂无翻译配置" @row-click="selectProfile">
          <el-table-column prop="id" label="配置 ID" min-width="180" />
          <el-table-column prop="language_pair" label="语言方向" width="110" />
          <el-table-column prop="default_version" label="默认版本" width="120" />
          <el-table-column prop="target_language" label="目标语言" width="110" />
          <el-table-column prop="domain" label="领域" min-width="180" show-overflow-tooltip />
        </el-table>
      </WorkbenchPanelCard>

      <WorkbenchPanelCard
        title="草稿基础字段"
        subtitle="Prompt 当前指针由下方工作区管理，不再接受自由文本版本号。"
        card-class="profile-draft-card"
        header-class="profile-draft-header"
      >
        <template #actions>
          <el-tag v-if="draft?.snapshot_hash" class="draft-hash-tag mono" effect="plain" :title="draft.snapshot_hash">
            {{ draft.snapshot_hash }}
          </el-tag>
        </template>
        <el-empty v-if="!selectedProfileId" description="请选择翻译配置" :image-size="90" />
        <el-form v-else ref="draftFormRef" :model="draftForm" :rules="draftRules" label-width="140px">
          <el-form-item label="语言方向">
            <el-input :model-value="draft?.language_pair || ''" disabled />
          </el-form-item>
          <el-form-item label="目标语言" prop="target_language">
            <el-input v-model="draftForm.target_language" :disabled="!isAdmin" />
          </el-form-item>
          <el-form-item label="领域" prop="domain">
            <el-input v-model="draftForm.domain" :disabled="!isAdmin" />
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
              <div class="profile-actions app-action-row">
                <el-button
                  type="primary"
                  :loading="savingDraft"
                  :disabled="promptBusy || publishing || loading"
                  @click="saveDraft"
                >
                  保存基础字段
                </el-button>
                <el-button
                  type="success"
                  :loading="publishing"
                  :disabled="isPromptDirty || promptBusy || savingDraft || loading"
                  title="发布前需先保存 Prompt 编辑内容"
                  @click="publishDraft"
                >
                  发布并设默认
                </el-button>
              </div>
            </el-form-item>
          </RoleGate>
        </el-form>
      </WorkbenchPanelCard>
    </section>

    <section v-if="!unavailable" class="app-page-shell app-page-shell--wide">
      <WorkbenchPanelCard
        title="Prompt 工作区"
        subtitle="保存和切换只修改当前草稿；发布并设为默认后，后续新任务才使用新的当前方案。"
        card-class="prompt-card"
        header-class="prompt-card-header"
      >
        <template #actions>
          <el-tag v-if="isPromptDirty" type="warning" effect="plain">有未保存修改</el-tag>
          <el-tag v-else-if="selectedPrompt" type="success" effect="plain">编辑内容已保存</el-tag>
        </template>

        <el-empty v-if="!selectedProfileId || !draft" description="请选择翻译配置" :image-size="90" />
        <template v-else>
          <div class="prompt-status-grid">
            <div>
              <span>语言方向</span>
              <strong class="mono">{{ draft.language_pair }}</strong>
            </div>
            <div>
              <span>草稿当前方案</span>
              <strong>{{ draftActivePrompt?.name || draft.prompt_version }}</strong>
              <small class="mono">{{ draft.prompt_version }}</small>
            </div>
            <div>
              <span>线上当前方案</span>
              <strong>{{ defaultPublishedVersion?.prompt_version || "尚未发布默认版本" }}</strong>
              <small v-if="defaultPublishedVersion" class="mono">
                {{ defaultPublishedVersion.version }} · {{ defaultPublishedVersion.prompt_content_hash }}
              </small>
            </div>
          </div>

          <el-alert
            v-if="!isAdmin"
            class="prompt-readonly-alert"
            type="info"
            title="当前账号为只读模式，可查看 Prompt，但不能保存、切换或删除。"
            :closable="false"
            show-icon
          />

          <div class="prompt-workspace">
            <aside class="prompt-sidebar">
              <label class="field-label" for="translation-profile-prompt-select">Prompt 方案</label>
              <el-select
                id="translation-profile-prompt-select"
                class="prompt-select"
                :model-value="selectedPromptId"
                :disabled="promptBusy"
                filterable
                @change="changePrompt"
              >
                <el-option
                  v-for="prompt in draft.prompt_schemes"
                  :key="prompt.id"
                  :label="`${prompt.name}${prompt.is_active ? '（草稿当前）' : ''}`"
                  :value="prompt.id"
                />
              </el-select>

              <div v-if="selectedPrompt" class="prompt-summary">
                <div class="prompt-tag-row">
                  <el-tag v-if="selectedPrompt.built_in" effect="plain">内置</el-tag>
                  <el-tag v-else type="info" effect="plain">自定义</el-tag>
                  <el-tag v-if="selectedPrompt.is_active" type="success" effect="plain">草稿当前</el-tag>
                  <el-tag
                    v-if="defaultPublishedVersion?.prompt_version === selectedPrompt.id"
                    type="warning"
                    effect="plain"
                  >
                    线上当前
                  </el-tag>
                </div>
                <dl>
                  <div>
                    <dt>Prompt ID</dt>
                    <dd class="mono">{{ selectedPrompt.id }}</dd>
                  </div>
                  <div>
                    <dt>正文 hash</dt>
                    <dd class="mono">{{ selectedPrompt.content_hash }}</dd>
                  </div>
                </dl>
              </div>

              <div class="prompt-sidebar-actions app-action-row">
                <el-button
                  :disabled="!canMutatePrompt || isPromptDirty"
                  :loading="promptAction === 'create'"
                  @click="createPrompt"
                >
                  新建 Prompt
                </el-button>
                <el-button
                  type="success"
                  plain
                  :disabled="!canMutatePrompt || selectedPrompt?.is_active || isPromptDirty"
                  :loading="promptAction === 'activate'"
                  @click="activatePrompt"
                >
                  设为当前方案
                </el-button>
                <el-button
                  type="danger"
                  plain
                  :disabled="!canDeleteSelectedPrompt"
                  :loading="promptAction === 'delete'"
                  @click="deletePrompt"
                >
                  删除 Prompt
                </el-button>
              </div>
              <p class="prompt-action-hint">{{ promptActionHint }}</p>
            </aside>

            <section class="prompt-editor" aria-label="Prompt Markdown 编辑器">
              <el-form ref="promptFormRef" :model="promptForm" :rules="promptRules" label-position="top">
                <el-form-item label="方案名称" prop="name">
                  <el-input
                    v-model="promptForm.name"
                    :disabled="!isAdmin || promptBusy"
                    maxlength="100"
                    show-word-limit
                  />
                </el-form-item>
                <el-form-item label="Markdown 正文" prop="markdown">
                  <el-input
                    v-model="promptForm.markdown"
                    class="prompt-markdown"
                    type="textarea"
                    :autosize="{ minRows: 18, maxRows: 32 }"
                    :disabled="!isAdmin || promptBusy"
                    maxlength="100000"
                    resize="vertical"
                    spellcheck="false"
                  />
                </el-form-item>
                <div class="prompt-editor-footer">
                  <span class="muted">
                    {{ promptForm.markdown.length.toLocaleString("zh-CN") }} / 100,000 字符
                  </span>
                  <el-button
                    type="primary"
                    :disabled="!canMutatePrompt || !isPromptDirty"
                    :loading="promptAction === 'save'"
                    @click="savePrompt"
                  >
                    保存 Prompt
                  </el-button>
                </div>
              </el-form>
            </section>
          </div>
        </template>
      </WorkbenchPanelCard>
    </section>

    <section v-if="!unavailable" class="app-page-shell app-page-shell--wide">
      <WorkbenchPanelCard
        title="已发布版本"
        subtitle="已发布版本中的 Prompt ID 和正文 hash 不可变；可由管理员设默认或回滚。"
        card-class="app-table-card"
      >
        <el-table
          class="published-version-table"
          :data="detail?.versions || []"
          :loading="loading"
          empty-text="暂无已发布版本"
        >
          <el-table-column prop="version" label="版本" width="120" />
          <el-table-column label="默认" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
              <span v-else class="muted">否</span>
            </template>
          </el-table-column>
          <el-table-column prop="language_pair" label="语言方向" width="110" />
          <el-table-column prop="target_language" label="目标语言" width="110" />
          <el-table-column prop="domain" label="领域" min-width="180" show-overflow-tooltip />
          <el-table-column prop="prompt_version" label="Prompt ID" min-width="180" show-overflow-tooltip />
          <el-table-column prop="prompt_content_hash" label="正文 hash" min-width="210" show-overflow-tooltip />
          <el-table-column prop="model" label="模型" min-width="220" show-overflow-tooltip />
          <el-table-column label="发布时间" width="190">
            <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
          </el-table-column>
          <el-table-column v-if="isAdmin" label="管理操作" width="230">
            <template #default="{ row }">
              <RoleGate>
                <span class="version-actions">
                  <el-button link type="warning" :disabled="row.is_default" @click="setDefault(row.version)">
                    设默认
                  </el-button>
                  <el-button link type="danger" @click="rollback(row.version)">回滚</el-button>
                </span>
              </RoleGate>
            </template>
          </el-table-column>
        </el-table>
      </WorkbenchPanelCard>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import { onBeforeRouteLeave, useRoute } from "vue-router";

import { translationProfilesApi } from "@/api/translationProfiles";
import type {
  TranslationProfileDetailResponse,
  TranslationProfileDraftResponse,
  TranslationProfileListItemResponse,
  TranslationProfilePromptSchemeResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

type PromptAction = "" | "create" | "save" | "activate" | "delete";

const auth = useAuthStore();
const route = useRoute();
const isAdmin = computed(() => auth.user?.role === "admin");
const profiles = ref<TranslationProfileListItemResponse[]>([]);
const selectedProfileId = ref("");
const detail = ref<TranslationProfileDetailResponse | null>(null);
const draft = ref<TranslationProfileDraftResponse | null>(null);
const selectedPromptId = ref("");
const loading = ref(false);
const savingDraft = ref(false);
const publishing = ref(false);
const promptAction = ref<PromptAction>("");
const unavailable = ref(false);
const error = ref<ApiClientError | null>(null);
const draftFormRef = ref<FormInstance>();
const promptFormRef = ref<FormInstance>();
let profileLoadSequence = 0;

const draftForm = reactive({
  target_language: "",
  domain: "",
  model: "" as string | null,
  max_pages_per_batch: 20,
  max_chars_per_batch: 60000,
});

const promptForm = reactive({
  name: "",
  markdown: "",
});

const draftRules: FormRules = {
  target_language: [{ required: true, message: "请填写目标语言", trigger: "blur" }],
  domain: [{ required: true, message: "请填写领域", trigger: "blur" }],
  max_pages_per_batch: [{ required: true, message: "请填写每批最大页数", trigger: "change" }],
  max_chars_per_batch: [{ required: true, message: "请填写每批最大字符数", trigger: "change" }],
};

const promptRules: FormRules = {
  name: [
    { required: true, whitespace: true, message: "请填写方案名称", trigger: "blur" },
    { max: 100, message: "方案名称最多 100 个字符", trigger: "blur" },
  ],
  markdown: [
    { required: true, whitespace: true, message: "Prompt Markdown 不能为空", trigger: "blur" },
    { max: 100000, message: "Prompt Markdown 最多 100,000 个字符", trigger: "blur" },
  ],
};

const selectedPrompt = computed<TranslationProfilePromptSchemeResponse | null>(() =>
  draft.value?.prompt_schemes.find((prompt) => prompt.id === selectedPromptId.value) || null,
);
const draftActivePrompt = computed(() =>
  draft.value?.prompt_schemes.find((prompt) => prompt.id === draft.value?.prompt_version) || null,
);
const defaultPublishedVersion = computed(() =>
  detail.value?.versions.find((version) => version.is_default) || null,
);
const isPromptDirty = computed(() => Boolean(
  selectedPrompt.value
  && (
    promptForm.name !== selectedPrompt.value.name
    || promptForm.markdown !== selectedPrompt.value.markdown
  )
));
const promptBusy = computed(() => Boolean(promptAction.value));
const canMutatePrompt = computed(() => Boolean(
  isAdmin.value
  && selectedProfileId.value
  && selectedPrompt.value
  && draft.value?.snapshot_hash
  && !promptBusy.value
  && !savingDraft.value
  && !publishing.value
  && !loading.value
));
const canDeleteSelectedPrompt = computed(() => Boolean(
  canMutatePrompt.value
  && selectedPrompt.value?.deletable
  && !isPromptDirty.value
));
const promptActionHint = computed(() => {
  if (!isAdmin.value) {
    return "只读账号不能修改 Prompt。";
  }
  if (!draft.value?.snapshot_hash) {
    return "草稿快照尚未就绪，暂时不能修改 Prompt。";
  }
  if (isPromptDirty.value) {
    return "请先保存或丢弃当前未保存修改，再执行新建、切换当前方案或删除。";
  }
  if (!selectedPrompt.value?.deletable) {
    return selectedPrompt.value?.delete_disabled_reason || "当前 Prompt 受保护，不能删除。";
  }
  return "删除只会移除当前草稿中从未发布、未引用的自定义 Prompt。";
});

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
    } else if (!profiles.value.some((profile) => profile.id === selectedProfileId.value)) {
      selectedProfileId.value = profiles.value[0]?.id || "";
    }
    if (selectedProfileId.value) {
      await loadSelectedProfile();
    } else {
      detail.value = null;
      draft.value = null;
      selectedPromptId.value = "";
      fillPromptForm(null);
    }
  } catch (caught) {
    setPageError(caught);
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
  if (profile.id === selectedProfileId.value) {
    return;
  }
  if (promptBusy.value || savingDraft.value || publishing.value || loading.value) {
    ElMessage.warning("当前操作完成后再切换翻译配置。");
    return;
  }
  if (!(await confirmDiscardPromptChanges("切换翻译配置会丢弃当前未保存的 Prompt 修改。"))) {
    return;
  }
  selectedProfileId.value = profile.id;
  detail.value = null;
  draft.value = null;
  selectedPromptId.value = "";
  fillPromptForm(null);
  await loadSelectedProfile();
}

async function loadSelectedProfile(preferredPromptId = ""): Promise<void> {
  if (!selectedProfileId.value) {
    return;
  }
  const profileId = selectedProfileId.value;
  const requestSequence = ++profileLoadSequence;
  error.value = null;
  try {
    const [detailResponse, draftResponse] = await Promise.all([
      translationProfilesApi.get(profileId),
      translationProfilesApi.getDraft(profileId),
    ]);
    if (requestSequence !== profileLoadSequence || profileId !== selectedProfileId.value) {
      return;
    }
    detail.value = detailResponse;
    applyDraftResponse(draftResponse, preferredPromptId);
  } catch (caught) {
    if (requestSequence !== profileLoadSequence || profileId !== selectedProfileId.value) {
      return;
    }
    detail.value = null;
    draft.value = null;
    selectedPromptId.value = "";
    fillPromptForm(null);
    setPageError(caught);
  }
}

function applyDraftResponse(
  response: TranslationProfileDraftResponse,
  preferredPromptId = "",
  preservePromptEditor = false,
): void {
  draft.value = response;
  fillDraftForm(response);
  const nextPromptId = response.prompt_schemes.some((prompt) => prompt.id === preferredPromptId)
    ? preferredPromptId
    : response.prompt_version;
  selectedPromptId.value = response.prompt_schemes.some((prompt) => prompt.id === nextPromptId)
    ? nextPromptId
    : response.prompt_schemes[0]?.id || "";
  if (!preservePromptEditor) {
    fillPromptForm(selectedPrompt.value);
  }
}

function fillDraftForm(response: TranslationProfileDraftResponse): void {
  draftForm.target_language = response.target_language;
  draftForm.domain = response.domain;
  draftForm.model = response.model || "";
  draftForm.max_pages_per_batch = response.max_pages_per_batch;
  draftForm.max_chars_per_batch = response.max_chars_per_batch;
}

function fillPromptForm(prompt: TranslationProfilePromptSchemeResponse | null): void {
  promptForm.name = prompt?.name || "";
  promptForm.markdown = prompt?.markdown || "";
  promptFormRef.value?.clearValidate();
}

async function changePrompt(nextPromptId: string): Promise<void> {
  if (nextPromptId === selectedPromptId.value) {
    return;
  }
  if (!(await confirmDiscardPromptChanges("切换 Prompt 会丢弃当前未保存修改。"))) {
    return;
  }
  selectedPromptId.value = nextPromptId;
  fillPromptForm(selectedPrompt.value);
}

async function confirmReloadAll(): Promise<void> {
  if (promptBusy.value || savingDraft.value || publishing.value || loading.value) {
    return;
  }
  if (!(await confirmDiscardPromptChanges("刷新会丢弃当前未保存的 Prompt 修改。"))) {
    return;
  }
  await loadAll();
}

async function confirmDiscardPromptChanges(message: string): Promise<boolean> {
  if (!isPromptDirty.value) {
    return true;
  }
  try {
    await ElMessageBox.confirm(message, "未保存修改", {
      confirmButtonText: "丢弃",
      cancelButtonText: "取消",
      type: "warning",
    });
    return true;
  } catch {
    return false;
  }
}

async function saveDraft(): Promise<void> {
  if (
    !selectedProfileId.value
    || !draft.value
    || promptBusy.value
    || publishing.value
    || loading.value
  ) {
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
      model: draftForm.model || null,
      max_pages_per_batch: draftForm.max_pages_per_batch,
      max_chars_per_batch: draftForm.max_chars_per_batch,
      expected_snapshot_hash: draft.value.snapshot_hash,
    });
    applyDraftResponse(response, selectedPromptId.value, true);
    ElMessage.success("翻译配置基础字段已保存。");
  } catch (caught) {
    handleDraftMutationError(caught);
  } finally {
    savingDraft.value = false;
  }
}

async function createPrompt(): Promise<void> {
  const context = promptMutationContext();
  if (!context || isPromptDirty.value) {
    return;
  }
  let name = "";
  try {
    const result = await ElMessageBox.prompt(
      `新方案会复制“${context.prompt.name}”的 Markdown 正文。`,
      "新建 Prompt",
      {
        inputValue: `${context.prompt.name} 副本`.slice(0, 100),
        inputPlaceholder: "方案名称",
        confirmButtonText: "新建",
        cancelButtonText: "取消",
        inputValidator(value) {
          const normalized = value.trim();
          if (!normalized) {
            return "方案名称不能为空。";
          }
          if (normalized.length > 100) {
            return "方案名称最多 100 个字符。";
          }
          return true;
        },
      },
    );
    name = result.value.trim();
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    throw caught;
  }
  promptAction.value = "create";
  error.value = null;
  try {
    const response = await translationProfilesApi.createPrompt(context.profileId, {
      name,
      source_prompt_id: context.prompt.id,
      expected_snapshot_hash: context.snapshotHash,
    });
    const createdPromptId = response.prompt_schemes.find((prompt) => prompt.name === name)?.id || "";
    applyDraftResponse(response, createdPromptId);
    ElMessage.success("Prompt 已复制到当前草稿。");
  } catch (caught) {
    handleDraftMutationError(caught);
  } finally {
    promptAction.value = "";
  }
}

async function savePrompt(): Promise<void> {
  const context = promptMutationContext();
  if (!context) {
    return;
  }
  const valid = await promptFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  promptAction.value = "save";
  error.value = null;
  try {
    const response = await translationProfilesApi.updatePrompt(context.profileId, context.prompt.id, {
      name: promptForm.name,
      markdown: promptForm.markdown,
      expected_snapshot_hash: context.snapshotHash,
    });
    applyDraftResponse(response, context.prompt.id);
    ElMessage.success("Prompt 已保存到当前草稿。");
  } catch (caught) {
    handleDraftMutationError(caught);
  } finally {
    promptAction.value = "";
  }
}

async function activatePrompt(): Promise<void> {
  const context = promptMutationContext();
  if (!context || context.prompt.is_active || isPromptDirty.value) {
    return;
  }
  promptAction.value = "activate";
  error.value = null;
  try {
    const response = await translationProfilesApi.activatePrompt(context.profileId, context.prompt.id, {
      expected_snapshot_hash: context.snapshotHash,
    });
    applyDraftResponse(response, context.prompt.id);
    ElMessage.success("已设为草稿当前方案；发布后才会影响后续任务。");
  } catch (caught) {
    handleDraftMutationError(caught);
  } finally {
    promptAction.value = "";
  }
}

async function deletePrompt(): Promise<void> {
  const context = promptMutationContext();
  if (!context || !context.prompt.deletable || isPromptDirty.value) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "只会从当前草稿物理移除这个从未发布、未引用的自定义 Prompt；历史版本不会改变。",
      `删除 ${context.prompt.name}`,
      {
        confirmButtonText: "删除 Prompt",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  promptAction.value = "delete";
  error.value = null;
  try {
    const response = await translationProfilesApi.deletePrompt(context.profileId, context.prompt.id, {
      expected_snapshot_hash: context.snapshotHash,
    });
    applyDraftResponse(response, response.prompt_version);
    ElMessage.success("Prompt 已从当前草稿删除。");
  } catch (caught) {
    handleDraftMutationError(caught);
  } finally {
    promptAction.value = "";
  }
}

function promptMutationContext(): {
  profileId: string;
  prompt: TranslationProfilePromptSchemeResponse;
  snapshotHash: string;
} | null {
  if (
    !isAdmin.value
    || !selectedProfileId.value
    || !selectedPrompt.value
    || !draft.value?.snapshot_hash
    || promptBusy.value
  ) {
    return null;
  }
  return {
    profileId: selectedProfileId.value,
    prompt: selectedPrompt.value,
    snapshotHash: draft.value.snapshot_hash,
  };
}

function handleDraftMutationError(caught: unknown): void {
  const normalized = normalizeApiError(caught);
  error.value = normalized;
  if (normalized.status === 409) {
    ElMessage.warning("草稿已被其他管理员更新；当前编辑内容未提交，请复制后刷新并重新应用。");
  }
}

async function publishDraft(): Promise<void> {
  if (
    !selectedProfileId.value
    || promptBusy.value
    || savingDraft.value
    || loading.value
    || isPromptDirty.value
  ) {
    if (isPromptDirty.value) {
      ElMessage.warning("请先保存 Prompt 修改，再发布草稿。");
    }
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
    ElMessage.success("翻译配置已发布并设为默认。");
    await loadAll();
  } catch (caught) {
    setPageError(caught);
  } finally {
    publishing.value = false;
  }
}

async function setDefault(version: string): Promise<void> {
  if (
    !selectedProfileId.value
    || promptBusy.value
    || savingDraft.value
    || publishing.value
    || loading.value
  ) {
    return;
  }
  if (!(await confirmDiscardPromptChanges("切换线上默认版本会刷新页面并丢弃当前未保存的 Prompt 修改。"))) {
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
    setPageError(caught);
  }
}

async function rollback(version: string): Promise<void> {
  if (
    !selectedProfileId.value
    || promptBusy.value
    || savingDraft.value
    || publishing.value
    || loading.value
  ) {
    return;
  }
  if (!(await confirmDiscardPromptChanges("回滚会刷新页面并丢弃当前未保存的 Prompt 修改。"))) {
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
    setPageError(caught);
  }
}

function setPageError(caught: unknown): void {
  const normalized = normalizeApiError(caught);
  if (normalized.status === 503) {
    unavailable.value = true;
  }
  error.value = normalized;
}

function handleBeforeUnload(event: BeforeUnloadEvent): void {
  if (!isPromptDirty.value) {
    return;
  }
  event.preventDefault();
  event.returnValue = "";
}

onBeforeRouteLeave(() => {
  if (!isPromptDirty.value) {
    return true;
  }
  return window.confirm("当前 Prompt 有未保存修改，确定离开吗？");
});

onMounted(() => {
  window.addEventListener("beforeunload", handleBeforeUnload);
  void loadAll();
});

onBeforeUnmount(() => {
  profileLoadSequence += 1;
  window.removeEventListener("beforeunload", handleBeforeUnload);
});
</script>

<style scoped lang="scss">
.translation-profiles-page {
  display: grid;
  align-content: start;
  grid-template-columns: minmax(0, 1fr);
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
}

.profile-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 520px);
  gap: var(--app-space-4);
}

.profile-draft-header,
.prompt-card-header {
  align-items: flex-start;
  flex-wrap: wrap;
}

.profile-draft-header > div,
.prompt-card-header > div {
  flex: 1 1 260px;
  min-width: 0;
}

.draft-hash-tag {
  flex: 0 1 min(100%, 280px);
  max-width: 100%;
}

.draft-hash-tag :deep(.el-tag__content) {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.profile-actions,
.prompt-sidebar-actions,
.prompt-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.prompt-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--app-space-3);
  margin-bottom: var(--app-space-4);
}

.prompt-status-grid > div {
  display: grid;
  gap: var(--app-space-1);
  min-width: 0;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
}

.prompt-status-grid span,
.prompt-status-grid small,
.prompt-summary dt,
.prompt-action-hint {
  color: var(--app-color-text-muted);
}

.prompt-status-grid strong,
.prompt-status-grid small {
  min-width: 0;
  overflow-wrap: anywhere;
}

.prompt-readonly-alert {
  margin-bottom: var(--app-space-4);
}

.prompt-workspace {
  display: grid;
  grid-template-columns: minmax(240px, 0.36fr) minmax(0, 1fr);
  gap: var(--app-space-4);
  align-items: start;
}

.prompt-sidebar,
.prompt-editor {
  min-width: 0;
  padding: var(--app-space-4);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
}

.field-label {
  display: block;
  margin-bottom: var(--app-space-2);
  color: var(--app-color-text);
  font-weight: 700;
}

.prompt-select {
  width: 100%;
}

.prompt-summary {
  display: grid;
  gap: var(--app-space-3);
  margin-top: var(--app-space-4);
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
}

.prompt-summary dl {
  display: grid;
  gap: var(--app-space-3);
  margin: 0;
}

.prompt-summary dl > div {
  display: grid;
  gap: var(--app-space-1);
}

.prompt-summary dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.prompt-sidebar-actions {
  margin-top: var(--app-space-4);
}

.prompt-action-hint {
  margin: var(--app-space-3) 0 0;
  font-size: 13px;
  line-height: 1.55;
}

.prompt-editor :deep(.el-form-item:last-child) {
  margin-bottom: var(--app-space-3);
}

.prompt-markdown :deep(.el-textarea__inner) {
  min-height: 360px;
  font-family: var(--app-font-mono);
  line-height: 1.65;
  tab-size: 2;
}

.prompt-editor-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-3);
}

@media (max-width: 1040px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1024px) {
  .prompt-workspace,
  .prompt-status-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .prompt-sidebar,
  .prompt-editor {
    padding: var(--app-space-3);
  }

  .prompt-sidebar-actions :deep(.el-button),
  .prompt-editor-footer :deep(.el-button) {
    width: 100%;
    margin-left: 0;
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
