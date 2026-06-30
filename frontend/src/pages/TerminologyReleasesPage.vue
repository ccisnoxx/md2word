<!-- File: frontend/src/pages/TerminologyReleasesPage.vue -->
<!-- Purpose: Manage terminology governance package releases across term sets, rules, and applicability scopes. -->
<template>
  <main class="terminology-releases-page app-page" aria-labelledby="terminology-releases-title">
    <WorkbenchPageHeader
      title-id="terminology-releases-title"
      kicker="术语发布"
      title="术语发布"
      description="发布“术语集 + 规则配置 + 适用范围”的治理包，统一管理版本、范围和发布前校验。"
      wide
      section-class="page-heading app-page-header"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </template>
    </WorkbenchPageHeader>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <section class="release-grid app-page-shell app-page-shell--wide">
      <WorkbenchPanelCard
        title="发布列表"
        subtitle="每条记录对应一个治理包版本；回滚只关闭当前生效版本。"
        card-class="app-table-card"
      >
        <template #actions>
          <el-tag effect="plain">共 {{ releases.length }} 条</el-tag>
        </template>
        <el-table :data="releases" :loading="loading" empty-text="暂无术语发布">
          <el-table-column label="治理包" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <button type="button" class="link-button mono" @click="openDetail(row)">{{ row.id }}@{{ row.version }}</button>
            </template>
          </el-table-column>
          <el-table-column label="范围" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">{{ scopeLabel(row.scope) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'info'" effect="plain">
                {{ row.status === "active" ? "生效中" : "已回滚" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="发布时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">详情</el-button>
              <el-button link type="primary" @click="copyRelease(row)">复制为新发布</el-button>
              <el-button link type="warning" :disabled="row.status !== 'active'" @click="rollbackRelease(row)">回滚</el-button>
            </template>
          </el-table-column>
        </el-table>
      </WorkbenchPanelCard>

      <WorkbenchPanelCard
        title="当前生效范围"
        subtitle="按项目、语言对和内容类型查看当前 active 治理包。"
        card-class="active-scope-card"
      >
        <el-empty v-if="!activeReleases.length" description="暂无生效范围" :image-size="90" />
        <div v-else class="active-scope-list">
          <button
            v-for="item in activeReleases"
            :key="`${item.id}@${item.version}`"
            type="button"
            class="active-scope-item"
            @click="openDetail(item)"
          >
            <span>{{ scopeLabel(item.scope) }}</span>
            <strong>{{ item.id }}@{{ item.version }}</strong>
            <small>术语 {{ assetLabel(item.translation_term_set) }} · 规则 {{ assetLabel(item.term_rule_set) }}</small>
          </button>
        </div>
      </WorkbenchPanelCard>
    </section>

    <section class="app-page-shell app-page-shell--wide">
      <WorkbenchPanelCard
        title="新增发布向导"
        subtitle="按步骤选择术语集版本、规则配置、适用范围并完成发布前校验。"
        card-class="release-wizard"
      >

      <el-steps :active="wizardStep" finish-status="success" simple>
        <el-step title="选择术语集版本" />
        <el-step title="选择规则配置" />
        <el-step title="设置适用范围" />
        <el-step title="发布前校验" />
        <el-step title="确认发布" />
      </el-steps>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="130px" class="wizard-form">
        <template v-if="wizardStep === 0">
          <el-form-item label="术语集" prop="translation_term_set_id">
            <el-select v-model="form.translation_term_set_id" filterable placeholder="选择翻译术语集" @change="handleTermSetChange">
              <el-option v-for="item in termSets" :key="item.set_id" :label="`${item.set_id} (${item.language_pair})`" :value="item.set_id" />
            </el-select>
          </el-form-item>
          <el-form-item label="术语集版本" prop="translation_term_version">
            <el-select v-model="form.translation_term_version" filterable placeholder="选择已发布版本">
              <el-option
                v-for="version in termSetVersions"
                :key="version.version"
                :label="`${version.version} · ${version.term_count} 词条${version.is_default ? ' · 默认' : ''}`"
                :value="version.version"
              />
            </el-select>
          </el-form-item>
        </template>

        <template v-else-if="wizardStep === 1">
          <el-form-item label="规则集" prop="term_rule_set_id">
            <el-select v-model="form.term_rule_set_id" filterable placeholder="选择术语规则配置" @change="handleRuleSetChange">
              <el-option v-for="item in ruleSets" :key="item.id" :label="item.id" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="规则版本" prop="term_rule_set_version">
            <el-select v-model="form.term_rule_set_version" filterable placeholder="选择已发布版本">
              <el-option
                v-for="version in ruleSetVersions"
                :key="version.version"
                :label="`${version.version} · ${version.rule_count} 条规则${version.is_default ? ' · 默认' : ''}`"
                :value="version.version"
              />
            </el-select>
          </el-form-item>
        </template>

        <template v-else-if="wizardStep === 2">
          <div class="scope-grid">
            <el-form-item label="项目" prop="scope.project">
              <el-input v-model="form.scope.project" placeholder="例如 electronics，全部范围用 *" />
            </el-form-item>
            <el-form-item label="语言对" prop="scope.language_pair">
              <el-input v-model="form.scope.language_pair" placeholder="例如 en2zh" />
            </el-form-item>
            <el-form-item label="内容类型" prop="scope.content_type">
              <el-input v-model="form.scope.content_type" placeholder="例如 datasheet，全部范围用 *" />
            </el-form-item>
          </div>
        </template>

        <template v-else-if="wizardStep === 3">
          <div class="preflight-header">
            <el-button type="primary" :loading="preflighting" @click="runPreflight">运行发布前校验</el-button>
            <el-tag v-if="preflight" :type="preflight.blocking ? 'danger' : 'success'" effect="plain">
              {{ preflight.blocking ? "校验阻断" : "校验通过" }}
            </el-tag>
          </div>
          <div v-if="preflight" class="governance-summary-grid app-governance-grid">
            <article class="summary-metric app-governance-metric"><span>错误</span><strong>{{ preflight.summary.error_count }}</strong></article>
            <article class="summary-metric app-governance-metric"><span>冲突</span><strong>{{ preflight.summary.conflict_count }}</strong></article>
            <article class="summary-metric app-governance-metric"><span>告警</span><strong>{{ preflight.summary.warning_count }}</strong></article>
            <article class="summary-metric app-governance-metric"><span>可发布词条</span><strong>{{ preflight.summary.publishable_term_count }}</strong></article>
          </div>
          <el-table :data="preflightFindings" empty-text="暂无校验结果">
            <el-table-column label="级别" width="110">
              <template #default="{ row }">
                <el-tag :type="findingTagType(row.severity)" effect="plain">{{ severityText(row.severity) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="code" label="代码" width="220" show-overflow-tooltip />
            <el-table-column prop="message" label="说明" min-width="260" show-overflow-tooltip />
          </el-table>
        </template>

        <template v-else>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="术语集">{{ form.translation_term_set_id }}@{{ form.translation_term_version }}</el-descriptions-item>
            <el-descriptions-item label="规则配置">{{ form.term_rule_set_id }}@{{ form.term_rule_set_version }}</el-descriptions-item>
            <el-descriptions-item label="适用范围">{{ scopeLabel(form.scope) }}</el-descriptions-item>
            <el-descriptions-item label="校验状态">{{ preflight?.blocking ? "阻断" : "通过" }}</el-descriptions-item>
          </el-descriptions>
          <el-form-item label="发布说明" prop="release_note" class="release-note-item">
            <el-input v-model="form.release_note" type="textarea" :rows="3" placeholder="说明本次治理包发布原因和影响范围。" />
          </el-form-item>
        </template>
      </el-form>

      <div class="wizard-actions app-action-row">
        <el-button :disabled="wizardStep === 0" @click="wizardStep -= 1">上一步</el-button>
        <el-button v-if="wizardStep < 4" type="primary" @click="nextStep">下一步</el-button>
        <el-button v-else type="success" :disabled="!preflight || preflight.blocking" :loading="publishing" @click="publishRelease">
          确认发布
        </el-button>
      </div>
      </WorkbenchPanelCard>
    </section>

    <el-drawer v-model="detailDrawer.visible" title="术语发布详情" size="620px">
      <template v-if="detailDrawer.release">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="治理包">{{ detailDrawer.release.id }}@{{ detailDrawer.release.version }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detailDrawer.release.status === "active" ? "生效中" : "已回滚" }}</el-descriptions-item>
          <el-descriptions-item label="范围">{{ scopeLabel(detailDrawer.release.scope) }}</el-descriptions-item>
          <el-descriptions-item label="术语集">{{ assetLabel(detailDrawer.release.translation_term_set) }}</el-descriptions-item>
          <el-descriptions-item label="规则配置">{{ assetLabel(detailDrawer.release.term_rule_set) }}</el-descriptions-item>
          <el-descriptions-item label="发布说明">{{ detailDrawer.release.release_note || "-" }}</el-descriptions-item>
        </el-descriptions>
        <section class="detail-section">
          <h3>校验报告</h3>
          <el-table :data="detailFindings" empty-text="暂无校验结果">
            <el-table-column label="级别" width="90">
              <template #default="{ row }">{{ severityText(row.severity) }}</template>
            </el-table-column>
            <el-table-column prop="code" label="代码" width="210" show-overflow-tooltip />
            <el-table-column prop="message" label="说明" min-width="260" show-overflow-tooltip />
          </el-table>
        </section>
      </template>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";

import { terminologyReleasesApi } from "@/api/terminologyReleases";
import { termRuleSetsApi } from "@/api/termRuleSets";
import { translationTermSetsApi } from "@/api/translationTermSets";
import type {
  TerminologyReleaseAssetResponse,
  TerminologyReleaseCreateRequest,
  TerminologyReleaseFindingResponse,
  TerminologyReleaseResponse,
  TerminologyReleaseScopeRequest,
  TerminologyReleaseValidationReportResponse,
  TermRuleSetDetailResponse,
  TermRuleSetListItemResponse,
  TranslationTermSetDetailResponse,
  TranslationTermSetListItemResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

const releases = ref<TerminologyReleaseResponse[]>([]);
const termSets = ref<TranslationTermSetListItemResponse[]>([]);
const ruleSets = ref<TermRuleSetListItemResponse[]>([]);
const selectedTermSetDetail = ref<TranslationTermSetDetailResponse | null>(null);
const selectedRuleSetDetail = ref<TermRuleSetDetailResponse | null>(null);
const loading = ref(false);
const preflighting = ref(false);
const publishing = ref(false);
const error = ref<ApiClientError | null>(null);
const wizardStep = ref(0);
const preflight = ref<TerminologyReleaseValidationReportResponse | null>(null);
const formRef = ref<FormInstance>();

const form = reactive<TerminologyReleaseCreateRequest>({
  translation_term_set_id: "",
  translation_term_version: "",
  term_rule_set_id: "",
  term_rule_set_version: "",
  scope: {
    project: "electronics",
    language_pair: "en2zh",
    content_type: "datasheet",
  },
  release_note: "",
  source_release_id: null,
  source_release_version: null,
});

const detailDrawer = reactive({
  visible: false,
  release: null as TerminologyReleaseResponse | null,
});

const rules: FormRules = {
  translation_term_set_id: [{ required: true, message: "请选择术语集", trigger: "change" }],
  translation_term_version: [{ required: true, message: "请选择术语集版本", trigger: "change" }],
  term_rule_set_id: [{ required: true, message: "请选择规则配置", trigger: "change" }],
  term_rule_set_version: [{ required: true, message: "请选择规则版本", trigger: "change" }],
  "scope.project": [{ required: true, message: "请填写项目", trigger: "blur" }],
  "scope.language_pair": [{ required: true, message: "请填写语言对", trigger: "blur" }],
  "scope.content_type": [{ required: true, message: "请填写内容类型", trigger: "blur" }],
};

const wizardStepFields: Record<number, string[]> = {
  0: ["translation_term_set_id", "translation_term_version"],
  1: ["term_rule_set_id", "term_rule_set_version"],
  2: ["scope.project", "scope.language_pair", "scope.content_type"],
};

const activeReleases = computed(() => releases.value.filter((item) => item.status === "active"));
const termSetVersions = computed(() => selectedTermSetDetail.value?.versions || []);
const ruleSetVersions = computed(() => selectedRuleSetDetail.value?.versions || []);
const preflightFindings = computed(() => {
  if (!preflight.value) {
    return [];
  }
  return [...preflight.value.errors, ...preflight.value.conflicts, ...preflight.value.warnings];
});
const detailFindings = computed(() => {
  const report = detailDrawer.release?.validation_report;
  if (!report) {
    return [];
  }
  return [...report.errors, ...report.conflicts, ...report.warnings];
});

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [releaseResponse, termSetResponse, ruleSetResponse] = await Promise.all([
      terminologyReleasesApi.list(),
      translationTermSetsApi.list(),
      termRuleSetsApi.list(),
    ]);
    releases.value = releaseResponse.items;
    termSets.value = termSetResponse.items;
    ruleSets.value = ruleSetResponse.items;
    await ensureSelectedDetails();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function ensureSelectedDetails(): Promise<void> {
  if (!form.translation_term_set_id && termSets.value.length) {
    form.translation_term_set_id = termSets.value[0].set_id;
  }
  if (!form.term_rule_set_id && ruleSets.value.length) {
    form.term_rule_set_id = ruleSets.value[0].id;
  }
  if (form.translation_term_set_id) {
    await loadTermSetDetail(form.translation_term_set_id);
  }
  if (form.term_rule_set_id) {
    await loadRuleSetDetail(form.term_rule_set_id);
  }
}

async function handleTermSetChange(value: string): Promise<void> {
  form.translation_term_version = "";
  preflight.value = null;
  await loadTermSetDetail(value);
}

async function handleRuleSetChange(value: string): Promise<void> {
  form.term_rule_set_version = "";
  preflight.value = null;
  await loadRuleSetDetail(value);
}

async function loadTermSetDetail(setId: string): Promise<void> {
  selectedTermSetDetail.value = await translationTermSetsApi.get(setId);
  const versions = selectedTermSetDetail.value.versions.map((item) => item.version);
  if (!versions.includes(form.translation_term_version)) {
    form.translation_term_version = selectedTermSetDetail.value.default_version || versions[0] || "";
  }
}

async function loadRuleSetDetail(setId: string): Promise<void> {
  selectedRuleSetDetail.value = await termRuleSetsApi.get(setId);
  const versions = selectedRuleSetDetail.value.versions.map((item) => item.version);
  if (!versions.includes(form.term_rule_set_version)) {
    form.term_rule_set_version = selectedRuleSetDetail.value.default_version || versions[0] || "";
  }
}

async function nextStep(): Promise<void> {
  if (wizardStep.value <= 2) {
    const valid = await validateWizardStep(wizardStep.value);
    if (!valid) {
      return;
    }
  }
  if (wizardStep.value === 3 && !preflight.value) {
    await runPreflight();
    if (!preflight.value) {
      return;
    }
  }
  wizardStep.value += 1;
}

async function runPreflight(): Promise<void> {
  const valid = await validateFullWizard();
  if (!valid) {
    return;
  }
  preflighting.value = true;
  error.value = null;
  try {
    preflight.value = await terminologyReleasesApi.preflight(normalizedForm());
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    preflighting.value = false;
  }
}

async function publishRelease(): Promise<void> {
  if (!preflight.value || preflight.value.blocking) {
    return;
  }
  publishing.value = true;
  error.value = null;
  try {
    const response = await terminologyReleasesApi.publish(normalizedForm());
    ElMessage.success("术语治理包已发布。");
    resetWizard();
    await loadAll();
    openDetail(response);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    publishing.value = false;
  }
}

async function rollbackRelease(row: TerminologyReleaseResponse): Promise<void> {
  const confirmed = await ElMessageBox.confirm(`确认回滚 ${row.id}@${row.version}？`, "回滚术语发布", { type: "warning" }).catch(() => false);
  if (!confirmed) {
    return;
  }
  try {
    const response = await terminologyReleasesApi.rollback(row.id);
    ElMessage.success("术语发布已回滚。");
    await loadAll();
    openDetail(response);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function validateWizardStep(step: number): Promise<boolean> {
  const fields = wizardStepFields[step];
  if (!fields?.length) {
    return true;
  }
  return validateFields(fields);
}

async function validateFullWizard(): Promise<boolean> {
  return validateFields(Object.values(wizardStepFields).flat());
}

async function validateFields(fields: string[]): Promise<boolean> {
  if (!formRef.value) {
    return false;
  }
  return new Promise((resolve) => {
    formRef.value?.validateField(fields, (valid) => {
      resolve(Boolean(valid));
    });
  });
}

async function copyRelease(row: TerminologyReleaseResponse): Promise<void> {
  try {
    const response = await terminologyReleasesApi.copy(row.id, row.version);
    Object.assign(form, response.draft);
    await ensureSelectedDetails();
    preflight.value = null;
    wizardStep.value = 0;
    ElMessage.success("已复制为新发布草稿。");
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

function openDetail(row: TerminologyReleaseResponse): void {
  detailDrawer.release = row;
  detailDrawer.visible = true;
}

function resetWizard(): void {
  wizardStep.value = 0;
  preflight.value = null;
  form.release_note = "";
  form.source_release_id = null;
  form.source_release_version = null;
}

function normalizedForm(): TerminologyReleaseCreateRequest {
  return {
    ...form,
    release_note: form.release_note?.trim() || null,
    scope: normalizeScope(form.scope),
  };
}

function normalizeScope(scope: TerminologyReleaseScopeRequest): TerminologyReleaseScopeRequest {
  return {
    project: scope.project.trim(),
    language_pair: scope.language_pair.trim(),
    content_type: scope.content_type.trim(),
  };
}

function scopeLabel(scope: TerminologyReleaseScopeRequest): string {
  return `${scope.project} / ${scope.language_pair} / ${scope.content_type}`;
}

function assetLabel(asset: TerminologyReleaseAssetResponse): string {
  return `${asset.resource_id}@${asset.version}`;
}

function severityText(severity: TerminologyReleaseFindingResponse["severity"]): string {
  const labels = { error: "硬错误", conflict: "高风险冲突", warning: "提示" };
  return labels[severity];
}

function findingTagType(severity: TerminologyReleaseFindingResponse["severity"]): "danger" | "warning" | "info" {
  if (severity === "error" || severity === "conflict") {
    return "danger";
  }
  return "warning";
}

onMounted(() => {
  void loadAll();
});
</script>

<style scoped lang="scss">
.terminology-releases-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
}

.release-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
  gap: var(--app-space-4);
}

.active-scope-list {
  display: grid;
  gap: var(--app-space-2);
}

.active-scope-item {
  cursor: pointer;
  display: grid;
  gap: 4px;
  width: 100%;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  text-align: left;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.active-scope-item:hover,
.active-scope-item:focus-visible {
  border-color: var(--app-color-primary-border);
  background: var(--app-color-primary-soft);
}

.active-scope-item small {
  color: var(--app-color-text-muted);
}

.release-wizard {
  display: grid;
  gap: var(--app-space-4);
}

.wizard-form {
  display: grid;
  gap: var(--app-space-3);
  padding-top: var(--app-space-3);
}

.scope-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.preflight-header {
  display: flex;
  align-items: center;
  gap: var(--app-space-3);
  margin-bottom: var(--app-space-3);
}

.wizard-actions {
  justify-content: flex-end;
}

.release-note-item {
  margin-top: var(--app-space-4);
}

.detail-section {
  display: grid;
  gap: var(--app-space-3);
  margin-top: var(--app-space-4);
}

.detail-section h3 {
  margin: 0;
  font-size: 15px;
}

.link-button {
  cursor: pointer;
  border: 0;
  background: transparent;
  color: var(--app-color-primary);
  font: inherit;
  text-align: left;
}

@media (max-width: 960px) {
  .release-grid,
  .scope-grid {
    grid-template-columns: 1fr;
  }
}
</style>
