<!-- File: frontend/src/pages/TermProposalsPage.vue -->
<!-- Purpose: Render operator proposal forms and admin review queues for term governance. -->
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
              <el-input
                v-model="proposalForm.source_job_id"
                :disabled="termRuleContextLocked"
                clearable
                placeholder="可选 job_id"
              />
            </el-form-item>
            <div v-if="termRuleContextVisible" class="proposal-context-summary">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="来源任务">
                  <router-link
                    v-if="proposalForm.source_job_id"
                    class="context-link"
                    :to="{ name: 'job-detail', params: { jobId: proposalForm.source_job_id } }"
                  >
                    {{ proposalForm.source_job_id }}
                  </router-link>
                  <span v-else>-</span>
                </el-descriptions-item>
                <el-descriptions-item label="来源文件">{{ proposalForm.source_file_id || "-" }}</el-descriptions-item>
                <el-descriptions-item label="Observed Set">
                  {{ proposalForm.observed_term_rule_set_id || "-" }}
                </el-descriptions-item>
                <el-descriptions-item label="Observed Version">
                  {{ proposalForm.observed_term_rule_version || "-" }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="submitProposal">提交建议</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
      <el-tab-pane label="翻译术语新建" name="translation-new">
        <el-card class="card-flat" shadow="never">
          <el-form
            ref="translationProposalFormRef"
            :model="translationProposalForm"
            :rules="translationProposalRules"
            label-width="110px"
          >
            <el-form-item label="动作" prop="action">
              <el-radio-group v-model="translationProposalForm.action" @change="handleTranslationActionChange">
                <el-radio-button value="add">新增</el-radio-button>
                <el-radio-button value="update">编辑</el-radio-button>
                <el-radio-button value="delete">删除</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="原文术语" prop="source_term">
              <el-input v-model="translationProposalForm.source_term" placeholder="例如 FPGA" />
            </el-form-item>
            <el-form-item v-if="translationProposalForm.action !== 'delete'" label="目标译文" prop="target_term">
              <el-input v-model="translationProposalForm.target_term" placeholder="例如 现场可编程门阵列" />
            </el-form-item>
            <el-form-item label="原因说明">
              <el-input
                v-model="translationProposalForm.note"
                type="textarea"
                :rows="3"
                placeholder="说明来源、问题和期望译法。"
              />
            </el-form-item>
            <el-form-item label="来源任务" prop="source_job_id">
              <el-input
                v-model="translationProposalForm.source_job_id"
                :disabled="translationContextLocked"
                clearable
                placeholder="可选 job_id"
              />
            </el-form-item>
            <div v-if="translationContextVisible" class="proposal-context-summary">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="来源任务">
                  <router-link
                    v-if="translationProposalForm.source_job_id"
                    class="context-link"
                    :to="{ name: 'job-detail', params: { jobId: translationProposalForm.source_job_id } }"
                  >
                    {{ translationProposalForm.source_job_id }}
                  </router-link>
                  <span v-else>-</span>
                </el-descriptions-item>
                <el-descriptions-item label="来源文件">{{ translationProposalForm.source_file_id || "-" }}</el-descriptions-item>
                <el-descriptions-item label="Observed Set">
                  {{ translationProposalForm.observed_translation_term_set_id || "-" }}
                </el-descriptions-item>
                <el-descriptions-item label="Observed Version">
                  {{ translationProposalForm.observed_translation_term_version || "-" }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="submitTranslationProposal">
                提交翻译术语建议
              </el-button>
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
                  <p>
                    <b>来源任务：</b>
                    <router-link
                      v-if="selectedProposal.source_job_id"
                      class="context-link"
                      :to="{ name: 'job-detail', params: { jobId: selectedProposal.source_job_id } }"
                    >
                      {{ selectedProposal.source_job_id }}
                    </router-link>
                    <span v-else>-</span>
                  </p>
                  <p><b>来源文件：</b>{{ selectedProposal.source_file_id || "-" }}</p>
                  <p><b>绑定版本：</b>{{ selectedTermRuleObservedVersionLabel }}</p>
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
                  <p>
                    <b>来源任务：</b>
                    <router-link
                      v-if="selectedTranslationProposal.source_job_id"
                      class="context-link"
                      :to="{ name: 'job-detail', params: { jobId: selectedTranslationProposal.source_job_id } }"
                    >
                      {{ selectedTranslationProposal.source_job_id }}
                    </router-link>
                    <span v-else>-</span>
                  </p>
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
import { computed, reactive, ref, watch } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import { useRoute } from "vue-router";

import {
  termProposalsApi,
  translationTermProposalsApi,
  type TermProposalScope,
  type TranslationTermProposalScope,
} from "@/api/termProposals";
import { termRulesApi } from "@/api/termRules";
import type {
  TermRuleCategoryListItemResponse,
  TermRuleProposalConflictItemResponse,
  TermRuleProposalConflictResponse,
  TermRuleProposalIntent,
  TermRuleProposalResponse,
  TermRuleResponse,
  TermRuleSegmentResponse,
  TermRuleSegmentWriteRequest,
  TranslationTermProposalAction,
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

const route = useRoute();
const auth = useAuthStore();
const isAdmin = computed(() => auth.user?.role === "admin");
const activeTab = ref(initialActiveTab());
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
const translationProposalFormRef = ref<FormInstance>();
const termRuleContextLocked = ref(false);
const translationContextLocked = ref(false);

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
  source_file_id: "",
  page_number: null as number | null,
  context_before: "",
  context_after: "",
  observed_term_rule_set_id: "",
  observed_term_rule_version: "",
  target_rule_id: "",
});

const translationProposalForm = reactive({
  action: "add" as TranslationTermProposalAction,
  source_term: "",
  target_term: "",
  note: "",
  source_job_id: "",
  source_file_id: "",
  observed_translation_term_set_id: "",
  observed_translation_term_version: "",
});

const categoryMap = computed(() =>
  Object.fromEntries(categories.value.map((category) => [category.id, category.name])),
);

const termRuleContextVisible = computed(() =>
  Boolean(
    proposalForm.source_job_id ||
    proposalForm.source_file_id ||
    proposalForm.observed_term_rule_set_id ||
    proposalForm.observed_term_rule_version,
  ),
);
const translationContextVisible = computed(() =>
  Boolean(
    translationProposalForm.source_job_id ||
    translationProposalForm.source_file_id ||
    translationProposalForm.observed_translation_term_set_id ||
    translationProposalForm.observed_translation_term_version,
  ),
);
const snapshotText = computed(() => JSON.stringify(selectedProposal.value?.target_rule_snapshot ?? null, null, 2));
const currentRuleText = computed(() => JSON.stringify(currentRule.value ?? null, null, 2));
const translationChangesText = computed(() => JSON.stringify(selectedTranslationProposal.value?.changes ?? [], null, 2));
const selectedTermRuleObservedVersionLabel = computed(() => {
  if (!selectedProposal.value) {
    return "-";
  }
  return `${selectedProposal.value.observed_term_rule_set_id || "-"}@${selectedProposal.value.observed_term_rule_version || "-"}`;
});
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

const translationProposalRules: FormRules = {
  action: [{ required: true, message: "请选择动作", trigger: "change" }],
  source_term: [
    {
      validator: (_rule, value, callback) => {
        if (!String(value || "").trim()) {
          callback(new Error("请填写原文术语。"));
          return;
        }
        callback();
      },
      trigger: "blur",
    },
  ],
  target_term: [
    {
      validator: (_rule, value, callback) => {
        if (translationProposalForm.action === "add" && !String(value || "").trim()) {
          callback(new Error("新增翻译术语必须填写目标译文。"));
          return;
        }
        callback();
      },
      trigger: "blur",
    },
  ],
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
    if (activeTab.value === "new") {
      await loadReferenceData();
      return;
    }
    if (activeTab.value === "translation-new") {
      return;
    }
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
  if (activeTab.value === "new") {
    void loadReferenceData();
    return;
  }
  if (activeTab.value === "translation-new") {
    return;
  }
  void loadActiveTab();
}

function handleIntentChange(): void {
  if (proposalForm.intent === "create") {
    proposalForm.target_rule_id = "";
  }
}

function categoryName(categoryId: string): string {
  return categoryMap.value[categoryId] || categoryId || "-";
}

// 从后端错误 payload 中提取结构化冲突、告警和旧字符串 detail。
function extractErrorDetailItems(raw: unknown): string[] {
  const body = readRecord(raw);
  const detail = readRecord(body?.detail);
  if (isTermRuleProposalConflictDetail(detail)) {
    return detail.conflicts.map((item) => formatTermRuleProposalConflictItem(item));
  }

  const items: string[] = [];
  for (const key of ["conflicts", "warnings", "errors"]) {
    const value = detail?.[key];
    if (Array.isArray(value)) {
      items.push(...value.map((item) => formatDetailItem(item)));
    }
  }
  return items;
}

// 判断未知值是否为对象，作为后端错误 payload 的读取边界。
function readRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : null;
}

// 读取非空字符串字段，避免 UI 展示空白上下文。
function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

// 识别 Term Rule Proposal 的结构化 409 响应。
function isTermRuleProposalConflictDetail(value: Record<string, unknown> | null): value is TermRuleProposalConflictResponse {
  return (
    value?.code === "term_rule_proposal_conflict" &&
    Array.isArray(value.conflicts)
  );
}

// 识别单条 Term Rule Proposal 结构化冲突，兼容 detail.conflicts[] 被单独遍历的场景。
function isTermRuleProposalConflictItem(value: unknown): value is TermRuleProposalConflictItemResponse {
  const record = readRecord(value);
  return Boolean(
    record &&
    readString(record.type) &&
    readString(record.message) &&
    readString(record.proposal_id) &&
    readString(record.source_term) &&
    readString(record.category_id),
  );
}

// 将结构化冲突压缩成一行稳定摘要，供页面顶部错误区展示。
function formatTermRuleProposalConflictItem(item: TermRuleProposalConflictItemResponse): string {
  const typeText: Record<string, string> = {
    stale_target_rule: "目标规则已变化",
    missing_target_rule: "目标规则不存在",
    source_term_segments_conflict: "同名术语分段冲突",
  };
  const context = [
    `proposal ${item.proposal_id}`,
    `target rule ${item.target_rule_id || "-"}`,
    `source_term ${item.source_term}`,
    `category ${categoryName(item.category_id)}`,
  ];
  const currentRuleText = item.current_rule
    ? `当前规则 ${item.current_rule.source_term} (${item.current_rule.id})`
    : "当前规则 -";
  return `${typeText[item.type] || item.type}: ${item.message}（${context.join("；")}；${currentRuleText}）`;
}

// 格式化后端 detail 数组项；结构化对象优先读 message，未知对象保留 JSON。
function formatDetailItem(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (isTermRuleProposalConflictItem(value)) {
    return formatTermRuleProposalConflictItem(value);
  }
  const record = readRecord(value);
  const message = readString(record?.message);
  if (message) {
    return message;
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

function queryString(key: string): string {
  const value = route.query[key];
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

// 根据路由 query 打开指定 tab，支持从治理页面跳转到翻译术语审核流。
function initialActiveTab(): string {
  const tab = queryString("tab");
  if (["new", "translation-new", "mine", "all", "translation-mine", "translation-review", "translation-all"].includes(tab)) {
    return tab;
  }
  return isAdmin.value ? "review" : "mine";
}

// 将任务详情或治理页面传入的上下文写入当前 proposal 表单/tab。
function applyRouteProposalContext(): void {
  const tab = queryString("tab");
  if (tab === "new") {
    resetProposalForm();
    proposalForm.source_job_id = queryString("source_job_id");
    proposalForm.source_file_id = queryString("source_file_id");
    proposalForm.observed_term_rule_set_id = queryString("observed_term_rule_set_id");
    proposalForm.observed_term_rule_version = queryString("observed_term_rule_version");
    termRuleContextLocked.value = Boolean(proposalForm.source_job_id);
    activeTab.value = "new";
    return;
  }
  if (tab === "translation-new") {
    resetTranslationProposalForm();
    translationProposalForm.source_job_id = queryString("source_job_id");
    translationProposalForm.source_file_id = queryString("source_file_id");
    translationProposalForm.observed_translation_term_set_id = queryString("observed_translation_term_set_id");
    translationProposalForm.observed_translation_term_version = queryString("observed_translation_term_version");
    translationContextLocked.value = Boolean(translationProposalForm.source_job_id);
    activeTab.value = "translation-new";
    return;
  }
  if (["mine", "all", "translation-mine", "translation-review", "translation-all"].includes(tab)) {
    activeTab.value = tab;
  }
  termRuleContextLocked.value = false;
  translationContextLocked.value = false;
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
      source_file_id: proposalForm.source_file_id || null,
      page_number: proposalForm.page_number,
      context_before: proposalForm.context_before || null,
      context_after: proposalForm.context_after || null,
      observed_term_rule_set_id: proposalForm.observed_term_rule_set_id || null,
      observed_term_rule_version: proposalForm.observed_term_rule_version || null,
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
  proposalForm.source_file_id = "";
  proposalForm.page_number = null;
  proposalForm.context_before = "";
  proposalForm.context_after = "";
  proposalForm.observed_term_rule_set_id = "";
  proposalForm.observed_term_rule_version = "";
  proposalForm.target_rule_id = "";
  termRuleContextLocked.value = false;
}

function resetTranslationProposalForm(): void {
  translationProposalForm.action = "add";
  translationProposalForm.source_term = "";
  translationProposalForm.target_term = "";
  translationProposalForm.note = "";
  translationProposalForm.source_job_id = "";
  translationProposalForm.source_file_id = "";
  translationProposalForm.observed_translation_term_set_id = "";
  translationProposalForm.observed_translation_term_version = "";
  translationContextLocked.value = false;
}

function handleTranslationActionChange(): void {
  if (translationProposalForm.action === "delete") {
    translationProposalForm.target_term = "";
  }
}

async function submitTranslationProposal(): Promise<void> {
  const valid = await translationProposalFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }

  submitting.value = true;
  error.value = null;
  try {
    await translationTermProposalsApi.create({
      language_pair: "en2zh",
      source_job_id: translationProposalForm.source_job_id || null,
      source_file_id: translationProposalForm.source_file_id || null,
      observed_translation_term_set_id: translationProposalForm.observed_translation_term_set_id || null,
      observed_translation_term_version: translationProposalForm.observed_translation_term_version || null,
      changes: [
        {
          action: translationProposalForm.action,
          source_term: translationProposalForm.source_term,
          target_term: translationProposalForm.action === "delete" ? null : translationProposalForm.target_term || null,
          note: translationProposalForm.note || null,
        },
      ],
    });
    ElMessage.success("翻译术语建议已提交。");
    activeTab.value = "translation-mine";
    resetTranslationProposalForm();
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    submitting.value = false;
  }
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

watch(() => route.fullPath, () => {
  applyRouteProposalContext();
  void loadActiveTab();
}, { immediate: true });
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
