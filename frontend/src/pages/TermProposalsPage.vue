<!-- frontend/src/pages/TermProposalsPage.vue: Operator proposal form and admin review queue. -->
<template>
  <main class="term-proposals-page" aria-labelledby="term-proposals-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Term Proposal</p>
        <h1 id="term-proposals-title">术语建议</h1>
        <p>operator 提交规则或翻译术语建议，admin 审核后合并到对应 draft。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadActiveTab">刷新</el-button>
    </section>

    <ApiErrorAlert :error="error" />
    <el-alert
      v-if="errorDetailItems.length"
      class="conflict-alert"
      type="warning"
      title="后端返回的冲突或警告"
      :closable="false"
      show-icon
    >
      <ul class="error-detail-list">
        <li v-for="item in errorDetailItems" :key="item">{{ item }}</li>
      </ul>
    </el-alert>

    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="我的建议" name="mine">
        <TermProposalTable :items="proposals" :categories="categoryMap" :loading="loading" @select="selectProposal" />
      </el-tab-pane>
      <el-tab-pane label="新建建议" name="new">
        <el-card class="card-flat" shadow="never">
          <el-form ref="proposalFormRef" :model="proposalForm" :rules="proposalRules" label-width="110px">
            <el-form-item label="建议类型" prop="intent">
              <el-radio-group v-model="proposalForm.intent" @change="handleIntentChange">
                <el-radio-button label="create">新增</el-radio-button>
                <el-radio-button label="update">编辑</el-radio-button>
                <el-radio-button label="disable">禁用</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="proposalForm.intent !== 'create'" label="目标规则" prop="target_rule_id">
              <el-select v-model="proposalForm.target_rule_id" filterable placeholder="选择现有规则" @change="applyTargetRule">
                <el-option
                  v-for="rule in rules"
                  :key="rule.id"
                  :label="`${rule.source_term} / ${rule.category_name || rule.category_id}`"
                  :value="rule.id"
                />
              </el-select>
            </el-form-item>
            <template v-if="proposalForm.intent !== 'disable'">
              <el-form-item label="原文术语" prop="source_term">
                <el-input v-model="proposalForm.source_term" placeholder="例如 VIN" />
              </el-form-item>
              <el-form-item label="分类" prop="category_id">
                <el-select v-model="proposalForm.category_id" filterable placeholder="选择分类">
                  <el-option
                    v-for="category in categories"
                    :key="category.id"
                    :label="category.name"
                    :value="category.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="展示分段" prop="segments">
                <TermSegmentEditor v-model="proposalForm.segments" />
              </el-form-item>
            </template>
            <el-form-item label="原因说明" prop="reason">
              <el-input v-model="proposalForm.reason" type="textarea" :rows="3" placeholder="说明来源、问题和期望效果。" />
            </el-form-item>
            <el-form-item label="来源任务" prop="source_job_id">
              <el-input v-model="proposalForm.source_job_id" clearable placeholder="可选 job_id" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="submitProposal">提交建议</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
      <el-tab-pane v-if="isAdmin" label="待审核队列" name="review">
        <section class="review-grid">
          <TermProposalTable :items="proposals" :categories="categoryMap" :loading="loading" @select="selectProposal" />
          <el-card class="card-flat" shadow="never">
            <template v-if="selectedProposal">
              <div class="section-header">
                <div>
                  <h2 class="section-title">审核详情</h2>
                  <p class="section-subtitle">当前规则、提交时快照和提议变更并列展示。</p>
                </div>
                <el-tag :type="selectedProposal.status === 'pending_review' ? 'warning' : 'info'" effect="plain">
                  {{ proposalStatusText[selectedProposal.status] }}
                </el-tag>
              </div>

              <el-alert
                v-if="snapshotConflict"
                class="conflict-alert"
                type="warning"
                title="当前规则与提交时快照不一致，请人工判断后再审核；页面不会自动 rebase。"
                :closable="false"
                show-icon
              />

              <div class="review-panels">
                <div>
                  <h3>提议变更</h3>
                  <p><b>类型：</b>{{ proposalIntentText[selectedProposal.intent] }}</p>
                  <p><b>术语：</b>{{ selectedProposal.source_term }}</p>
                  <p><b>分类：</b>{{ categoryName(selectedProposal.category_id) }}</p>
                  <p><b>分段：</b><TermPreview :segments="selectedProposal.segments" /></p>
                  <p><b>原因：</b>{{ selectedProposal.reason }}</p>
                </div>
                <div>
                  <h3>当前规则</h3>
                  <pre>{{ currentRuleText }}</pre>
                </div>
                <div>
                  <h3>提交时快照</h3>
                  <pre>{{ snapshotText }}</pre>
                </div>
              </div>

              <el-input
                v-model="reviewComment"
                class="review-comment"
                type="textarea"
                :rows="3"
                placeholder="审核意见；reject 必填，approve 可选。"
              />
              <div class="toolbar">
                <el-button
                  type="success"
                  :loading="reviewing"
                  :disabled="selectedProposal.status !== 'pending_review'"
                  @click="approveProposal"
                >
                  Approve 并合并 draft
                </el-button>
                <el-button
                  type="primary"
                  :loading="reviewing"
                  :disabled="selectedProposal.status !== 'pending_review'"
                  @click="approveAndPublishProposal"
                >
                  审核并发布默认版本
                </el-button>
                <el-button
                  type="danger"
                  :loading="reviewing"
                  :disabled="selectedProposal.status !== 'pending_review'"
                  @click="rejectProposal"
                >
                  Reject
                </el-button>
              </div>
            </template>
            <el-empty v-else description="请选择一条 proposal" :image-size="90" />
          </el-card>
        </section>
      </el-tab-pane>
      <el-tab-pane v-if="isAdmin" label="全部 proposal" name="all">
        <TermProposalTable :items="proposals" :categories="categoryMap" :loading="loading" @select="selectProposal" />
      </el-tab-pane>
      <el-tab-pane label="翻译术语：我的" name="translation-mine">
        <TranslationTermProposalTable
          :items="translationProposals"
          :loading="loading"
          @select="selectTranslationProposal"
        />
      </el-tab-pane>
      <el-tab-pane v-if="isAdmin" label="翻译术语待审核" name="translation-review">
        <section class="review-grid">
          <TranslationTermProposalTable
            :items="translationProposals"
            :loading="loading"
            @select="selectTranslationProposal"
          />
          <el-card class="card-flat" shadow="never">
            <template v-if="selectedTranslationProposal">
              <div class="section-header">
                <div>
                  <h2 class="section-title">翻译术语审核详情</h2>
                  <p class="section-subtitle">展示提交时绑定版本、提议变更和发布结果。</p>
                </div>
                <el-tag :type="selectedTranslationProposal.status === 'pending' ? 'warning' : 'info'" effect="plain">
                  {{ translationProposalStatusText[selectedTranslationProposal.status] }}
                </el-tag>
              </div>

              <div class="review-panels">
                <div>
                  <h3>提议变更</h3>
                  <p><b>绑定版本：</b>{{ translationObservedVersionLabel }}</p>
                  <p><b>来源任务：</b>{{ selectedTranslationProposal.source_job_id || "-" }}</p>
                  <p><b>来源文件：</b>{{ selectedTranslationProposal.source_file_id || "-" }}</p>
                  <pre>{{ translationChangesText }}</pre>
                </div>
                <div>
                  <h3>发布结果</h3>
                  <p><b>published set：</b>{{ selectedTranslationProposal.published_translation_term_set_id || "-" }}</p>
                  <p><b>published version：</b>{{ selectedTranslationProposal.published_translation_term_version || "-" }}</p>
                  <p><b>review note：</b>{{ selectedTranslationProposal.review_note || "-" }}</p>
                </div>
              </div>

              <el-input
                v-model="translationReviewNote"
                class="review-comment"
                type="textarea"
                :rows="3"
                placeholder="审核意见；reject 必填，approve 可选。"
              />
              <div class="toolbar">
                <el-button
                  type="success"
                  :loading="reviewing"
                  :disabled="selectedTranslationProposal.status !== 'pending'"
                  @click="approveTranslationProposal"
                >
                  Approve 并合并 draft
                </el-button>
                <el-button
                  type="primary"
                  :loading="reviewing"
                  :disabled="selectedTranslationProposal.status !== 'pending'"
                  @click="approveAndPublishTranslationProposal"
                >
                  审核并发布默认版本
                </el-button>
                <el-button
                  type="danger"
                  :loading="reviewing"
                  :disabled="selectedTranslationProposal.status !== 'pending'"
                  @click="rejectTranslationProposal"
                >
                  Reject
                </el-button>
              </div>
            </template>
            <el-empty v-else description="请选择一条 Translation Term Proposal" :image-size="90" />
          </el-card>
        </section>
      </el-tab-pane>
      <el-tab-pane v-if="isAdmin" label="翻译术语全部" name="translation-all">
        <TranslationTermProposalTable
          :items="translationProposals"
          :loading="loading"
          @select="selectTranslationProposal"
        />
      </el-tab-pane>
    </el-tabs>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";

import {
  termProposalsApi,
  translationTermProposalsApi,
  type TermProposalScope,
  type TranslationTermProposalScope,
} from "@/api/termProposals";
import { termRulesApi } from "@/api/termRules";
import type {
  TermRuleCategoryListItemResponse,
  TermRuleProposalIntent,
  TermRuleProposalResponse,
  TermRuleResponse,
  TermRuleSegmentResponse,
  TermRuleSegmentWriteRequest,
  TranslationTermProposalResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import TermPreview from "@/components/TermPreview.vue";
import TermProposalTable from "@/components/TermProposalTable.vue";
import TermSegmentEditor from "@/components/TermSegmentEditor.vue";
import TranslationTermProposalTable from "@/components/TranslationTermProposalTable.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const proposalIntentText: Record<string, string> = {
  create: "新增",
  update: "编辑",
  disable: "禁用",
};

const proposalStatusText: Record<string, string> = {
  pending_review: "待审核",
  approved: "已通过",
  rejected: "已拒绝",
  published: "已发布",
};

const translationProposalStatusText: Record<string, string> = {
  pending: "待审核",
  approved: "已通过",
  rejected: "已拒绝",
  published: "已发布",
};

const auth = useAuthStore();
const isAdmin = computed(() => auth.user?.role === "admin");
const activeTab = ref(isAdmin.value ? "review" : "mine");
const loading = ref(false);
const submitting = ref(false);
const reviewing = ref(false);
const error = ref<ApiClientError | null>(null);
const categories = ref<TermRuleCategoryListItemResponse[]>([]);
const rules = ref<TermRuleResponse[]>([]);
const proposals = ref<TermRuleProposalResponse[]>([]);
const translationProposals = ref<TranslationTermProposalResponse[]>([]);
const selectedProposal = ref<TermRuleProposalResponse | null>(null);
const selectedTranslationProposal = ref<TranslationTermProposalResponse | null>(null);
const currentRule = ref<TermRuleResponse | null>(null);
const reviewComment = ref("");
const translationReviewNote = ref("");
const proposalFormRef = ref<FormInstance>();

const proposalForm = reactive({
  intent: "create" as TermRuleProposalIntent,
  source_term: "",
  category_id: "",
  segments: [
    { segment_text: "V", render_type: "plain" },
    { segment_text: "IN", render_type: "subscript" },
  ] as TermRuleSegmentWriteRequest[],
  reason: "",
  source_job_id: "",
  target_rule_id: "",
});

const categoryMap = computed(() =>
  Object.fromEntries(categories.value.map((category) => [category.id, category.name])),
);

const snapshotText = computed(() => JSON.stringify(selectedProposal.value?.target_rule_snapshot ?? null, null, 2));
const currentRuleText = computed(() => JSON.stringify(currentRule.value ?? null, null, 2));
const translationChangesText = computed(() => JSON.stringify(selectedTranslationProposal.value?.changes ?? [], null, 2));
const translationObservedVersionLabel = computed(() => {
  if (!selectedTranslationProposal.value) {
    return "-";
  }
  return `${selectedTranslationProposal.value.observed_translation_term_set_id || "-"}@${selectedTranslationProposal.value.observed_translation_term_version || "-"}`;
});
const errorDetailItems = computed(() => extractErrorDetailItems(error.value?.raw));
const snapshotConflict = computed(() => {
  if (!selectedProposal.value?.target_rule_id || !selectedProposal.value.target_rule_snapshot || !currentRule.value) {
    return false;
  }
  return JSON.stringify(normalizeRuleSnapshot(currentRule.value)) !== JSON.stringify(selectedProposal.value.target_rule_snapshot);
});

const proposalRules: FormRules = {
  intent: [{ required: true, message: "请选择建议类型", trigger: "change" }],
  target_rule_id: [
    {
      validator: (_rule, value, callback) => {
        if (proposalForm.intent !== "create" && !value) {
          callback(new Error("编辑或禁用 proposal 必须选择现有规则。"));
          return;
        }
        callback();
      },
      trigger: "change",
    },
  ],
  source_term: [
    {
      validator: (_rule, value, callback) => {
        if (proposalForm.intent !== "disable" && !String(value || "").trim()) {
          callback(new Error("请填写原文术语。"));
          return;
        }
        callback();
      },
      trigger: "blur",
    },
  ],
  category_id: [
    {
      validator: (_rule, value, callback) => {
        if (proposalForm.intent !== "disable" && !value) {
          callback(new Error("请选择分类。"));
          return;
        }
        callback();
      },
      trigger: "change",
    },
  ],
  segments: [
    {
      validator: (_rule, value: TermRuleSegmentWriteRequest[], callback) => {
        if (proposalForm.intent !== "disable" && (!value.length || value.some((item) => !item.segment_text.trim()))) {
          callback(new Error("请填写完整分段文本。"));
          return;
        }
        callback();
      },
      trigger: "change",
    },
  ],
  reason: [{ required: true, message: "请填写原因说明", trigger: "blur" }],
};

async function loadReferenceData(): Promise<void> {
  const [categoryResponse, ruleResponse] = await Promise.all([
    termRulesApi.listCategories(),
    termRulesApi.listRules({ page_size: 200, enabled: true }),
  ]);
  categories.value = categoryResponse.items;
  rules.value = ruleResponse.items;
}

async function loadActiveTab(): Promise<void> {
  loading.value = true;
  error.value = null;
  selectedProposal.value = null;
  selectedTranslationProposal.value = null;
  currentRule.value = null;
  try {
    if (activeTab.value.startsWith("translation-")) {
      const scope = translationActiveTabScope();
      translationProposals.value = (await translationTermProposalsApi.list({ scope })).items;
    } else {
      await loadReferenceData();
      const scope = activeTabScope();
      proposals.value = (await termProposalsApi.list({ scope })).items;
    }
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

function activeTabScope(): TermProposalScope {
  if (activeTab.value === "review") {
    return "pending_review";
  }
  if (activeTab.value === "all") {
    return "all";
  }
  return "my";
}

function translationActiveTabScope(): TranslationTermProposalScope {
  if (activeTab.value === "translation-review") {
    return "pending";
  }
  if (activeTab.value === "translation-all") {
    return "all";
  }
  return "my";
}

function handleTabChange(): void {
  if (activeTab.value !== "new") {
    void loadActiveTab();
  }
}

function handleIntentChange(): void {
  if (proposalForm.intent === "create") {
    proposalForm.target_rule_id = "";
  }
}

function categoryName(categoryId: string): string {
  return categoryMap.value[categoryId] || categoryId || "-";
}

function extractErrorDetailItems(raw: unknown): string[] {
  const body = readRecord(raw);
  const detail = readRecord(body?.detail);
  const items: string[] = [];
  for (const key of ["conflicts", "warnings", "errors"]) {
    const value = detail?.[key];
    if (Array.isArray(value)) {
      items.push(...value.map((item) => stringifyDetailItem(item)));
    }
  }
  return items;
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : null;
}

function stringifyDetailItem(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

function applyTargetRule(): void {
  const rule = rules.value.find((item) => item.id === proposalForm.target_rule_id);
  if (!rule) {
    return;
  }
  proposalForm.source_term = rule.source_term;
  proposalForm.category_id = rule.category_id;
  proposalForm.segments = rule.segments.map(segmentToWrite);
}

function segmentToWrite(segment: TermRuleSegmentResponse): TermRuleSegmentWriteRequest {
  return {
    segment_text: segment.segment_text,
    render_type: segment.render_type,
  };
}

function normalizeRuleSnapshot(rule: TermRuleResponse): Record<string, unknown> {
  return {
    id: rule.id,
    category_id: rule.category_id,
    source_term: rule.source_term,
    apply_scope: rule.apply_scope,
    case_sensitive: rule.case_sensitive,
    enabled: rule.enabled,
    priority: rule.priority,
    segments: rule.segments.map((segment) => ({
      segment_text: segment.segment_text,
      render_type: segment.render_type,
    })),
    custom_html: rule.custom_html,
    custom_markdown: rule.custom_markdown,
    notes: rule.notes,
  };
}

async function submitProposal(): Promise<void> {
  const valid = await proposalFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }

  submitting.value = true;
  error.value = null;
  try {
    await termProposalsApi.create({
      intent: proposalForm.intent,
      source_term: proposalForm.intent === "disable" ? null : proposalForm.source_term,
      category_id: proposalForm.intent === "disable" ? null : proposalForm.category_id,
      segments: proposalForm.intent === "disable" ? null : proposalForm.segments,
      reason: proposalForm.reason,
      source_job_id: proposalForm.source_job_id || null,
      target_rule_id: proposalForm.target_rule_id || null,
    });
    ElMessage.success("术语建议已提交。");
    activeTab.value = "mine";
    resetProposalForm();
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    submitting.value = false;
  }
}

function resetProposalForm(): void {
  proposalForm.intent = "create";
  proposalForm.source_term = "";
  proposalForm.category_id = "";
  proposalForm.segments = [
    { segment_text: "V", render_type: "plain" },
    { segment_text: "IN", render_type: "subscript" },
  ];
  proposalForm.reason = "";
  proposalForm.source_job_id = "";
  proposalForm.target_rule_id = "";
}

async function selectProposal(proposal: TermRuleProposalResponse): Promise<void> {
  selectedProposal.value = proposal;
  reviewComment.value = proposal.review_comment || "";
  currentRule.value = null;
  if (proposal.target_rule_id) {
    try {
      currentRule.value = await termRulesApi.getRule(proposal.target_rule_id);
    } catch (caught) {
      error.value = normalizeApiError(caught);
    }
  }
}

function selectTranslationProposal(proposal: TranslationTermProposalResponse): void {
  selectedTranslationProposal.value = proposal;
  translationReviewNote.value = proposal.review_note || "";
}

async function approveProposal(): Promise<void> {
  if (!selectedProposal.value) {
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    await termProposalsApi.approve(selectedProposal.value.id, reviewComment.value);
    ElMessage.success("proposal 已合并到 Term Rule Set draft。");
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

async function approveAndPublishProposal(): Promise<void> {
  if (!selectedProposal.value) {
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    const sourceTerm = selectedProposal.value.source_term;
    await termProposalsApi.approveAndPublish(selectedProposal.value.id, {
      review_comment: reviewComment.value || null,
      publish_reason: `publish approved term rule proposal: ${sourceTerm}`,
    });
    ElMessage.success("proposal 已审核并发布为默认规则版本。");
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

async function rejectProposal(): Promise<void> {
  if (!selectedProposal.value) {
    return;
  }
  if (!reviewComment.value.trim()) {
    ElMessage.warning("Reject 必须填写原因。");
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    await termProposalsApi.reject(selectedProposal.value.id, reviewComment.value);
    ElMessage.success("proposal 已拒绝。");
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

async function approveTranslationProposal(): Promise<void> {
  if (!selectedTranslationProposal.value) {
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    await translationTermProposalsApi.approve(selectedTranslationProposal.value.id, translationReviewNote.value);
    ElMessage.success("Translation Term Proposal 已合并到 draft。");
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

async function approveAndPublishTranslationProposal(): Promise<void> {
  if (!selectedTranslationProposal.value) {
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    await translationTermProposalsApi.approveAndPublish(selectedTranslationProposal.value.id, {
      review_note: translationReviewNote.value || null,
      release_note: `publish approved translation term proposal: ${selectedTranslationProposal.value.id}`,
    });
    ElMessage.success("Translation Term Proposal 已审核并发布为默认版本。");
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

async function rejectTranslationProposal(): Promise<void> {
  if (!selectedTranslationProposal.value) {
    return;
  }
  if (!translationReviewNote.value.trim()) {
    ElMessage.warning("Reject 必须填写原因。");
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    await translationTermProposalsApi.reject(selectedTranslationProposal.value.id, translationReviewNote.value);
    ElMessage.success("Translation Term Proposal 已拒绝。");
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

onMounted(() => {
  void loadActiveTab();
});
</script>

<style scoped lang="scss">
.term-proposals-page {
  display: grid;
  gap: 16px;
}

.review-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 520px);
  gap: 16px;
}

.proposal-table-wrap {
  overflow-x: auto;
}

.conflict-alert,
.review-comment {
  margin-bottom: 12px;
}

.error-detail-list {
  margin: 6px 0 0;
  padding-left: 18px;
}

.review-panels {
  display: grid;
  gap: 12px;
  margin-bottom: 12px;
}

.review-panels h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.review-panels p {
  margin: 6px 0;
}

.review-panels pre {
  overflow: auto;
  max-height: 220px;
  margin: 0;
  padding: 10px;
  border-radius: 8px;
  background: #f8fafc;
  color: #111827;
  font-size: 12px;
}

@media (max-width: 1100px) {
  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>
