<!-- File: frontend/src/pages/TermRuleSetPage.vue -->
<!-- Purpose: Provide Admin Term Rule Set draft governance, diff, preflight, and publish workflows. -->
<template>
  <main class="term-rule-set-page app-page" aria-labelledby="term-rule-set-title">
    <section class="page-heading app-page-header app-page-shell app-page-shell--wide">
      <div>
        <p class="page-kicker">Term Rule Set</p>
        <h1 id="term-rule-set-title" class="page-title">术语规则集</h1>
        <p class="page-description">维护 draft 规则，查看 diff 和发布前校验；发布或切默认后才影响后续默认版本。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </section>

    <TerminologyWorkbenchNav class="app-page-shell app-page-shell--wide" active="draft-publish" />

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <el-alert
      class="app-page-shell app-page-shell--wide"
      v-if="unavailable"
      type="warning"
      title="当前部署未启用 MySQL resource service，Term Rule Set 版本管理不可用。"
      :closable="false"
      show-icon
    />

    <el-alert
      v-if="governanceContextVisible && !unavailable"
      class="governance-context-alert app-page-shell app-page-shell--wide"
      type="info"
      title="Proposal 治理上下文"
      :closable="false"
      show-icon
    >
      <div class="governance-context-body">
        <span>proposal: {{ governanceProposalId || "-" }}</span>
        <span>source_term: {{ governanceSourceTerm || "-" }}</span>
        <span>target_rule: {{ governanceTargetRuleId || "-" }}</span>
        <el-button link type="primary" @click="returnToProposalReview">返回 proposal 审核页</el-button>
      </div>
    </el-alert>

    <section v-if="!unavailable" class="rule-set-grid app-page-shell app-page-shell--wide">
      <el-card class="app-panel-card" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">规则集选择</h2>
            <p class="section-subtitle">按现有规则集管理，不新建规则集。</p>
          </div>
        </div>
        <el-select v-model="selectedSetId" :disabled="loading" placeholder="选择规则集" @change="loadSelectedSet">
          <el-option v-for="item in sets" :key="item.id" :label="item.id" :value="item.id" />
        </el-select>
      </el-card>

      <el-card class="app-panel-card" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Draft 摘要</h2>
            <p class="section-subtitle">结构化编辑只修改 draft，不刷新 runtime YAML。</p>
          </div>
          <el-tag v-if="draft?.snapshot_hash" effect="plain" class="mono">{{ draft.snapshot_hash }}</el-tag>
        </div>
        <dl class="summary-list">
          <div><dt>base version</dt><dd>{{ draft?.base_version || "-" }}</dd></div>
          <div><dt>rule_count</dt><dd>{{ draft?.rule_count ?? "-" }}</dd></div>
          <div><dt>enabled_rule_count</dt><dd>{{ draft?.enabled_rule_count ?? "-" }}</dd></div>
        </dl>
      </el-card>

      <el-card class="app-panel-card" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Preflight</h2>
            <p class="section-subtitle">Blocking errors 会阻止发布。</p>
          </div>
          <el-tag :type="preflightStatusType" effect="plain">
            {{ preflightStatusLabel }}
          </el-tag>
        </div>
        <dl class="summary-list">
          <div><dt>errors</dt><dd>{{ preflightReport?.summary.error_count ?? "-" }}</dd></div>
          <div><dt>warnings</dt><dd>{{ preflightReport?.summary.warning_count ?? "-" }}</dd></div>
          <div><dt>conflicts</dt><dd>{{ preflightReport?.summary.conflict_count ?? "-" }}</dd></div>
        </dl>
        <RoleGate>
          <el-button
            type="primary"
            :disabled="!selectedSetId || Boolean(preflightReport?.blocking)"
            @click="openPublishDialog"
          >
            发布 draft
          </el-button>
        </RoleGate>
      </el-card>
    </section>

    <RoleGate>
      <TermRuleDraftRulePanel
        v-if="!unavailable"
        :selected-set-id="selectedSetId"
        :categories="categories"
        :filters="draftRuleFilters"
        :rules="draftRules"
        :total="draftRuleTotal"
        :loading="draftRulesLoading"
        :deleting-rule-id="deletingRuleId"
        :toggling-rule-id="togglingRuleId"
        @create="openCreateRuleDialog"
        @edit="openEditRuleDialog"
        @toggle="toggleRule"
        @delete="deleteRule"
        @search="searchDraftRules"
        @reset="resetDraftRuleFilters"
        @load="loadDraftRules"
      />
    </RoleGate>

    <TermRuleGovernanceReports
      v-if="!unavailable"
      :diff-report="diffReport"
      :preflight-report="preflightReport"
      :diff-loading="diffLoading"
      :preflight-loading="preflightLoading"
      @refresh="loadGovernanceReports"
    />

    <TermRulePublishedVersionsPanel
      v-if="!unavailable"
      :versions="detail?.versions || []"
      :loading="loading"
      :is-admin="isAdmin"
      @set-default="setDefault"
      @rollback="rollback"
    />

    <RoleGate>
      <TermRuleApprovedProposalsPanel
        v-if="!unavailable"
        :items="approvedProposals"
        :categories="categoryMap"
        :loading="loading"
        @select="openApprovedProposal"
      />
    </RoleGate>

    <RoleGate>
      <TermRuleYamlFallbackPanel
        v-if="!unavailable"
        v-model:yaml-text="yamlText"
        :saving="savingYaml"
        @save="saveYamlDraft"
      />
    </RoleGate>

    <TermRuleDraftRuleDialog
      ref="ruleDialogRef"
      v-model:visible="ruleDialog.visible"
      :title="ruleDialogTitle"
      :form="ruleForm"
      :rules="ruleRules"
      :categories="categories"
      :saving="savingRule"
      @save="saveRule"
    />

    <TermRulePublishDialog
      ref="publishDialogRef"
      v-model:visible="publishDialog.visible"
      :form="publishDialog.form"
      :rules="publishRules"
      :preflight-report="preflightReport"
      :publishing="publishing"
      @publish="publishDraft"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { termProposalsApi } from "@/api/termProposals";
import { termRulesApi } from "@/api/termRules";
import { termRuleSetsApi } from "@/api/termRuleSets";
import type {
  TermRuleCategoryListItemResponse,
  TermRuleProposalResponse,
  TermRuleResponse,
  TermRuleSetDetailResponse,
  TermRuleSetDiffResponse,
  TermRuleSetDraftResponse,
  TermRuleSetListItemResponse,
  TermRuleSetPreflightResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import TermRuleApprovedProposalsPanel from "@/components/TermRuleApprovedProposalsPanel.vue";
import TermRuleGovernanceReports from "@/components/TermRuleGovernanceReports.vue";
import TermRuleDraftRuleDialog from "@/components/TermRuleDraftRuleDialog.vue";
import TermRuleDraftRulePanel, { type DraftRuleFilters } from "@/components/TermRuleDraftRulePanel.vue";
import TermRulePublishDialog, { type TermRulePublishFormState } from "@/components/TermRulePublishDialog.vue";
import TermRulePublishedVersionsPanel from "@/components/TermRulePublishedVersionsPanel.vue";
import TermRuleYamlFallbackPanel from "@/components/TermRuleYamlFallbackPanel.vue";
import TerminologyWorkbenchNav from "@/components/TerminologyWorkbenchNav.vue";
import {
  buildTermRuleMutationPayload,
  createEmptyRuleForm,
  isAdvancedRule,
  validateTermRuleSegments,
  type RuleDialogVariant,
  type RuleFormState,
} from "@/composables/useTermRuleForm";
import {
  termRulePreflightStatusLabel,
  termRulePreflightStatusType,
} from "@/composables/useTermRuleGovernanceDisplay";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

type RuleDialogMode = "create" | "edit";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const isAdmin = computed(() => auth.user?.role === "admin");
const sets = ref<TermRuleSetListItemResponse[]>([]);
const selectedSetId = ref("");
const detail = ref<TermRuleSetDetailResponse | null>(null);
const draft = ref<TermRuleSetDraftResponse | null>(null);
const yamlText = ref("");
const approvedProposals = ref<TermRuleProposalResponse[]>([]);
const categories = ref<TermRuleCategoryListItemResponse[]>([]);
const draftRules = ref<TermRuleResponse[]>([]);
const draftRuleTotal = ref(0);
const diffReport = ref<TermRuleSetDiffResponse | null>(null);
const preflightReport = ref<TermRuleSetPreflightResponse | null>(null);
const loading = ref(false);
const draftRulesLoading = ref(false);
const diffLoading = ref(false);
const preflightLoading = ref(false);
const publishing = ref(false);
const savingYaml = ref(false);
const savingRule = ref(false);
const deletingRuleId = ref("");
const togglingRuleId = ref("");
const unavailable = ref(false);
const error = ref<ApiClientError | null>(null);
const publishDialogRef = ref<{ validate: () => Promise<boolean> }>();
const ruleDialogRef = ref<{ validate: () => Promise<boolean> }>();

const draftRuleFilters = reactive<DraftRuleFilters>({
  page: 1,
  pageSize: 20,
  categoryId: "",
  enabled: "all",
  keyword: "",
});

const ruleDialog = reactive({
  visible: false,
  mode: "create" as RuleDialogMode,
  variant: "basic" as RuleDialogVariant,
  ruleId: "",
});

const ruleForm = reactive<RuleFormState>(createEmptyRuleForm());

const publishDialog = reactive<{ visible: boolean; form: TermRulePublishFormState }>({
  visible: false,
  form: {
    publish_reason: "",
  },
});

const publishRules: FormRules = {
  publish_reason: [{ required: true, message: "请填写发布说明", trigger: "blur" }],
};

const ruleRules: FormRules = {
  source_term: [{ required: true, message: "请填写 source term", trigger: "blur" }],
  category_id: [{ required: true, message: "请选择分类", trigger: "change" }],
};

const categoryMap = computed(() =>
  Object.fromEntries(categories.value.map((category) => [category.id, category.name])),
);
const governanceProposalId = computed(() => queryString("proposal_id"));
const governanceTargetRuleId = computed(() => queryString("target_rule_id"));
const governanceSourceTerm = computed(() => queryString("source_term"));
const governanceReturnTab = computed(() => queryString("return_tab") || "review");
const governanceContextVisible = computed(() =>
  Boolean(governanceProposalId.value || governanceTargetRuleId.value || governanceSourceTerm.value),
);

const ruleDialogTitle = computed(() => {
  if (ruleDialog.mode === "edit") {
    return "编辑 draft rule";
  }
  return ruleDialog.variant === "advanced" ? "新增高级 draft rule" : "新增 draft rule";
});

const preflightStatusLabel = computed(() => {
  return termRulePreflightStatusLabel(preflightReport.value);
});

const preflightStatusType = computed(() => {
  return termRulePreflightStatusType(preflightReport.value);
});

// 把接口错误 raw payload 当作普通对象读取。
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

// 从当前 route query 中读取单值字符串，供 proposal 治理上下文使用。
function queryString(key: string): string {
  const value = route.query[key];
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

// 把 proposal 页传来的上下文应用到治理页，只做定位和筛选，不隐式修改 draft。
function applyGovernanceRouteContext(): void {
  const requestedSetId = queryString("set_id");
  if (requestedSetId && sets.value.some((item) => item.id === requestedSetId)) {
    selectedSetId.value = requestedSetId;
  } else {
    selectedSetId.value ||= sets.value[0]?.id || "";
  }

  const sourceTerm = governanceSourceTerm.value;
  if (sourceTerm) {
    draftRuleFilters.keyword = sourceTerm;
    draftRuleFilters.page = 1;
  }
}

// 加载规则集、分类、当前选择下的 draft 上下文。
async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  unavailable.value = false;
  try {
    const [setResponse, categoryResponse] = await Promise.all([
      termRuleSetsApi.list(),
      termRulesApi.listCategories(),
    ]);
    sets.value = setResponse.items;
    categories.value = categoryResponse.items;
    applyGovernanceRouteContext();
    if (selectedSetId.value) {
      await loadSelectedSet();
    }
    if (auth.user?.role === "admin") {
      await loadApprovedUnpublishedProposals();
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

// 加载已 approve 但尚未随 Term Rule Set 发布的 proposal，匹配卡片文案。
async function loadApprovedUnpublishedProposals(): Promise<void> {
  approvedProposals.value = (await termProposalsApi.list({ scope: "approved_unpublished" })).items;
}

// 切换规则集后刷新详情、draft、diff、preflight 和规则列表。
async function loadSelectedSet(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const [detailResponse, draftResponse] = await Promise.all([
    termRuleSetsApi.get(selectedSetId.value),
    termRuleSetsApi.getDraft(selectedSetId.value),
  ]);
  detail.value = detailResponse;
  applyDraft(draftResponse);
  await Promise.all([loadDraftRules(), loadGovernanceReports()]);
}

// 使用 draft response 同步页面上的 draft 摘要和 YAML 兜底文本。
function applyDraft(nextDraft: TermRuleSetDraftResponse): void {
  draft.value = nextDraft;
  yamlText.value = nextDraft.yaml_text;
}

// 将启用状态筛选转换为后端查询参数。
function enabledParam(): boolean | undefined {
  if (draftRuleFilters.enabled === "enabled") {
    return true;
  }
  if (draftRuleFilters.enabled === "disabled") {
    return false;
  }
  return undefined;
}

// 加载当前 draft 的结构化规则列表。
async function loadDraftRules(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  draftRulesLoading.value = true;
  try {
    const response = await termRuleSetsApi.listDraftRules(selectedSetId.value, {
      page: draftRuleFilters.page,
      page_size: draftRuleFilters.pageSize,
      category_id: draftRuleFilters.categoryId || undefined,
      enabled: enabledParam(),
      q: draftRuleFilters.keyword.trim() || undefined,
    });
    draftRules.value = response.items;
    draftRuleTotal.value = response.total;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    draftRulesLoading.value = false;
  }
}

// 从第一页按当前筛选重新查询 draft rules。
function searchDraftRules(): void {
  draftRuleFilters.page = 1;
  void loadDraftRules();
}

// 清空 draft rule 筛选条件并重新加载。
function resetDraftRuleFilters(): void {
  draftRuleFilters.page = 1;
  draftRuleFilters.categoryId = "";
  draftRuleFilters.enabled = "all";
  draftRuleFilters.keyword = "";
  void loadDraftRules();
}

// 同步 diff 和 preflight 报告。
async function loadGovernanceReports(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  diffLoading.value = true;
  preflightLoading.value = true;
  try {
    const [diffResponse, preflightResponse] = await Promise.all([
      termRuleSetsApi.diff(selectedSetId.value, { from: "default", to: "draft" }),
      termRuleSetsApi.preflight(selectedSetId.value),
    ]);
    diffReport.value = diffResponse;
    preflightReport.value = preflightResponse;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    diffLoading.value = false;
    preflightLoading.value = false;
  }
}

// draft 写入后刷新摘要、规则列表、diff 和 preflight。
async function refreshAfterDraftMutation(nextDraft?: TermRuleSetDraftResponse): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  if (nextDraft) {
    applyDraft(nextDraft);
  } else {
    applyDraft(await termRuleSetsApi.getDraft(selectedSetId.value));
  }
  await Promise.all([loadDraftRules(), loadGovernanceReports()]);
}

function currentDraftSnapshotHash(): string | null {
  return draft.value?.snapshot_hash || null;
}

async function handleDraftMutationError(caught: unknown): Promise<void> {
  const normalized = normalizeApiError(caught);
  error.value = normalized;
  if (normalized.status === 409 && normalized.code === "draft_snapshot_conflict") {
    ElMessage.warning("当前 draft 已被其他修改更新，已刷新最新内容，请重新确认后保存。");
    await refreshAfterDraftMutation();
  }
}

// 打开新增规则对话框。
function openCreateRuleDialog(variant: RuleDialogVariant = "basic"): void {
  Object.assign(ruleForm, createEmptyRuleForm(variant), {
    category_id: categories.value[0]?.id || "",
  });
  ruleDialog.mode = "create";
  ruleDialog.variant = variant;
  ruleDialog.ruleId = "";
  ruleDialog.visible = true;
}

// 打开编辑规则对话框并填充当前规则字段。
function openEditRuleDialog(rule: TermRuleResponse): void {
  Object.assign(ruleForm, {
    source_term: rule.source_term,
    category_id: rule.category_id,
    apply_scope: rule.apply_scope,
    case_sensitive: rule.case_sensitive,
    enabled: rule.enabled,
    priority: rule.priority,
    segments: rule.segments.map((segment) => ({
      segment_text: segment.segment_text,
      render_type: segment.render_type,
    })),
    custom_html: rule.custom_html || "",
    custom_markdown: rule.custom_markdown || "",
    notes: rule.notes || "",
  });
  ruleDialog.mode = "edit";
  ruleDialog.variant = isAdvancedRule(rule) ? "advanced" : "basic";
  ruleDialog.ruleId = rule.id;
  ruleDialog.visible = true;
}

// 保存新增或编辑后的 draft rule。
async function saveRule(): Promise<void> {
  const segmentError = validateTermRuleSegments(ruleForm.segments);
  if (!selectedSetId.value || segmentError) {
    if (segmentError) {
      ElMessage.error(segmentError);
    }
    return;
  }
  const valid = await ruleDialogRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  savingRule.value = true;
  error.value = null;
  try {
    const payload = buildTermRuleMutationPayload(ruleForm, currentDraftSnapshotHash());
    const response =
      ruleDialog.mode === "create"
        ? await termRuleSetsApi.createDraftRule(selectedSetId.value, payload)
        : await termRuleSetsApi.updateDraftRule(selectedSetId.value, ruleDialog.ruleId, payload);
    ElMessage.success(ruleDialog.mode === "create" ? "Draft rule 已新增。" : "Draft rule 已保存。");
    ruleDialog.visible = false;
    await refreshAfterDraftMutation(response.draft);
  } catch (caught) {
    await handleDraftMutationError(caught);
  } finally {
    savingRule.value = false;
  }
}

// 快速启用或停用一条 draft rule。
async function toggleRule(rule: TermRuleResponse): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  togglingRuleId.value = rule.id;
  error.value = null;
  try {
    const response = await termRuleSetsApi.updateDraftRule(selectedSetId.value, rule.id, {
      expected_snapshot_hash: currentDraftSnapshotHash(),
      enabled: !rule.enabled,
    });
    ElMessage.success(rule.enabled ? "Draft rule 已停用。" : "Draft rule 已启用。");
    await refreshAfterDraftMutation(response.draft);
  } catch (caught) {
    await handleDraftMutationError(caught);
  } finally {
    togglingRuleId.value = "";
  }
}

// 删除一条 draft rule；只影响 draft，不做真实文件删除。
async function deleteRule(rule: TermRuleResponse): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "该操作只会从当前 draft 移除规则，不会删除任何文件或历史 published version。",
      `删除 ${rule.source_term}`,
      {
        confirmButtonText: "删除 draft rule",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  deletingRuleId.value = rule.id;
  error.value = null;
  try {
    const response = await termRuleSetsApi.deleteDraftRule(selectedSetId.value, rule.id, currentDraftSnapshotHash());
    ElMessage.success("Draft rule 已删除。");
    await refreshAfterDraftMutation(response.draft);
  } catch (caught) {
    await handleDraftMutationError(caught);
  } finally {
    deletingRuleId.value = "";
  }
}

// 刷新 preflight 后打开发布对话框。
async function openPublishDialog(): Promise<void> {
  publishDialog.form.publish_reason = "";
  await loadGovernanceReports();
  publishDialog.visible = true;
}

// 从 publish 错误中提取结构化 preflight report。
function extractPreflightReport(apiError: ApiClientError): TermRuleSetPreflightResponse | null {
  if (!isRecord(apiError.raw) || !isRecord(apiError.raw.detail)) {
    return null;
  }
  const detail = apiError.raw.detail;
  if (detail.code !== "term_rule_set_preflight_failed" || !isRecord(detail.report)) {
    return null;
  }
  return detail.report as TermRuleSetPreflightResponse;
}

// 发布当前 draft；blocking preflight 会保持对话框打开并展示 report。
async function publishDraft(): Promise<void> {
  if (!selectedSetId.value || preflightReport.value?.blocking) {
    return;
  }
  const valid = await publishDialogRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  publishing.value = true;
  error.value = null;
  try {
    await termRuleSetsApi.publish(selectedSetId.value, {
      make_default: true,
      publish_reason: publishDialog.form.publish_reason,
    });
    ElMessage.success("Term Rule Set draft 已发布。");
    publishDialog.visible = false;
    await loadAll();
  } catch (caught) {
    const normalized = normalizeApiError(caught);
    const report = extractPreflightReport(normalized);
    if (report) {
      preflightReport.value = report;
    }
    error.value = normalized;
  } finally {
    publishing.value = false;
  }
}

// 把指定 published version 设为默认版本。
async function setDefault(version: string): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm("将该 published version 切换为默认术语规则集版本。", `设默认 ${version}`, {
      confirmButtonText: "设默认",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  error.value = null;
  try {
    await termRuleSetsApi.setDefault(selectedSetId.value, version);
    ElMessage.success("默认术语规则集已切换。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

// Rollback 只切默认指针到指定 published version。
async function rollback(version: string): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm("Rollback 会基于该版本恢复规则集，请确认这是已发布版本。", `Rollback ${version}`, {
      confirmButtonText: "Rollback",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  error.value = null;
  try {
    await termRuleSetsApi.rollback(selectedSetId.value, { version });
    ElMessage.success("已完成 rollback。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

// 保存完整 YAML draft 兜底入口。
async function saveYamlDraft(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  savingYaml.value = true;
  error.value = null;
  try {
    const response = await termRuleSetsApi.updateDraft(selectedSetId.value, {
      expected_snapshot_hash: currentDraftSnapshotHash(),
      yaml_text: yamlText.value,
    });
    ElMessage.success("YAML draft 已保存。");
    await refreshAfterDraftMutation(response);
  } catch (caught) {
    await handleDraftMutationError(caught);
  } finally {
    savingYaml.value = false;
  }
}

// 从治理上下文返回 proposal 审核页，并保留 proposal_id 深链定位。
function returnToProposalReview(): void {
  const query: Record<string, string> = {
    tab: governanceReturnTab.value,
  };
  if (governanceProposalId.value) {
    query.proposal_id = governanceProposalId.value;
  }
  void router.push({ name: "term-proposals", query });
}

// 已 approve 待核对列表行点击后回到 proposal 全量列表，因为 approved 不在 review 队列。
function openApprovedProposal(proposal: TermRuleProposalResponse): void {
  void router.push({
    name: "term-proposals",
    query: {
      tab: "all",
      proposal_id: proposal.id,
    },
  });
}

watch(() => route.fullPath, () => {
  void loadAll();
}, { immediate: true });
</script>

<style scoped lang="scss">
.term-rule-set-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
}

.rule-set-grid {
  display: grid;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr) minmax(260px, 340px);
  gap: var(--app-space-4);
}

.governance-context-alert {
  margin-bottom: 4px;
}

.governance-context-body {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2) var(--app-space-4);
  align-items: center;
}

.summary-list {
  display: grid;
  gap: var(--app-space-2);
  margin: 0 0 var(--app-space-4);
}

.summary-list div {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: var(--app-space-2);
}

.summary-list dt {
  color: var(--app-color-text-muted);
}

.summary-list dd {
  margin: 0;
  font-weight: 650;
  word-break: break-word;
}

@media (max-width: 1120px) {
  .rule-set-grid {
    grid-template-columns: 1fr;
  }
}

</style>
