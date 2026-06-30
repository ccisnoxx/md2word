<!-- File: frontend/src/pages/TermProposalsPage.vue -->
<!-- Purpose: Render operator proposal forms and admin review queues for term governance. -->
<template>
  <main class="term-proposals-page app-page" aria-labelledby="term-proposals-title">
    <WorkbenchPageHeader
      title-id="term-proposals-title"
      kicker="术语建议"
      title="术语建议"
      description="操作员提交规则或翻译术语建议，管理员审核后合并到对应草稿。"
      wide
      section-class="page-heading app-page-header"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="loadActiveTab">刷新</el-button>
      </template>
    </WorkbenchPageHeader>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />
    <el-alert
      v-if="errorDetailItems.length"
      class="conflict-alert app-page-shell app-page-shell--wide"
      type="warning"
      title="后端返回的冲突或警告"
      :closable="false"
      show-icon
    >
      <ul class="error-detail-list">
        <li v-for="item in errorDetailItems" :key="item">{{ item }}</li>
      </ul>
    </el-alert>
    <el-alert
      v-if="focusNoticeVisible"
      class="focus-notice app-page-shell app-page-shell--wide"
      type="info"
      title="队列定位提示"
      :closable="false"
      show-icon
    >
      {{ focusNotice }}
    </el-alert>

    <el-tabs v-model="activeTab" class="app-panel-card app-page-shell app-page-shell--wide proposal-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="我的建议" name="mine">
        <TermProposalTable
          :items="proposals"
          :categories="categoryMap"
          :loading="loading"
          :selected-id="selectedTermProposalId"
          @select="selectProposal"
        />
      </el-tab-pane>
      <el-tab-pane label="新建建议" name="new">
        <WorkbenchPanelCard card-class="app-panel-card">
          <el-form ref="proposalFormRef" :model="proposalForm" :rules="proposalRules" label-width="110px">
            <el-alert
              v-if="termRuleSuggestionMode"
              class="proposal-mode-alert"
              type="info"
              title="术语规则建议"
              :closable="false"
              show-icon
            >
              你提交的是术语规则建议，审核通过后由术语管理员转为正式规则草稿。
            </el-alert>
            <el-form-item label="建议类型" prop="intent">
              <el-radio-group v-model="proposalForm.intent" @change="handleIntentChange">
                <el-radio-button value="create">新增</el-radio-button>
                <el-radio-button value="update">编辑</el-radio-button>
                <el-radio-button value="disable">禁用</el-radio-button>
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
            <div v-if="termRuleContextVisible" class="proposal-context-summary app-evidence-panel">
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
                <el-descriptions-item label="提交时规则集">
                  {{ proposalForm.observed_term_rule_set_id || "-" }}
                </el-descriptions-item>
                <el-descriptions-item label="提交时版本">
                  {{ proposalForm.observed_term_rule_version || "-" }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="submitProposal">提交建议</el-button>
            </el-form-item>
          </el-form>
        </WorkbenchPanelCard>
      </el-tab-pane>
      <el-tab-pane label="翻译术语新建" name="translation-new">
        <WorkbenchPanelCard card-class="app-panel-card">
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
            <div v-if="translationContextVisible" class="proposal-context-summary app-evidence-panel">
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
                <el-descriptions-item label="提交时术语集">
                  {{ translationProposalForm.observed_translation_term_set_id || "-" }}
                </el-descriptions-item>
                <el-descriptions-item label="提交时版本">
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
        </WorkbenchPanelCard>
      </el-tab-pane>
      <el-tab-pane v-if="isAdmin" label="待审核队列" name="review">
        <section class="review-grid">
          <div class="review-list-panel">
            <WorkbenchPanelCard
              title="批量审核"
              subtitle="仅待审核建议可勾选；不提供批量发布。"
              card-class="app-panel-card batch-review-card"
              body-class="batch-review-body"
            >
              <template #actions>
                <el-tag effect="plain">已选 {{ bulkSelectedCount }}</el-tag>
              </template>
              <el-input
                v-model="bulkReviewComment"
                class="review-comment"
                type="textarea"
                :rows="2"
                placeholder="批量审核意见；拒绝必填，通过可选。"
              />
              <div class="toolbar app-action-row">
                <el-button
                  type="success"
                  :loading="bulkReviewing"
                  :disabled="!bulkSelectedCount || reviewing"
                  @click="bulkApproveProposals"
                >
                  批量通过
                </el-button>
                <el-button
                  type="danger"
                  :loading="bulkReviewing"
                  :disabled="!bulkSelectedCount || reviewing"
                  @click="bulkRejectProposals"
                >
                  批量拒绝
                </el-button>
              </div>
              <el-alert
                v-if="bulkResult"
                class="bulk-result-alert"
                :type="bulkResult.failed ? 'warning' : 'success'"
                :title="bulkResultTitle"
                :closable="true"
                show-icon
                @close="bulkResult = null"
              >
                <ul v-if="bulkFailureItems.length" class="error-detail-list">
                  <li v-for="item in bulkFailureItems" :key="item.proposal_id">
                    {{ formatBulkFailureItem(item) }}
                  </li>
                </ul>
              </el-alert>
            </WorkbenchPanelCard>
            <TermProposalTable
              ref="termReviewTableRef"
              :items="proposals"
              :categories="categoryMap"
              :loading="loading"
              :selected-id="selectedTermProposalId"
              selectable
              @select="selectProposal"
              @selection-change="handleTermBulkSelectionChange"
            />
          </div>
          <WorkbenchPanelCard card-class="app-panel-card" body-class="review-detail-card-body">
            <template v-if="selectedProposal">
              <WorkbenchSectionHeader
                title="审核详情"
                subtitle="当前规则、提交时快照和提议变更并列展示。"
              >
                <template #extra>
                  <el-tag :type="selectedProposal.status === 'pending_review' ? 'warning' : 'info'" effect="plain">
                    {{ proposalStatusText(selectedProposal.status) }}
                  </el-tag>
                </template>
              </WorkbenchSectionHeader>

              <el-alert
                v-if="snapshotConflict"
                class="conflict-alert"
                type="warning"
                title="当前规则与提交时快照不一致，请人工判断后再审核；页面不会自动重定基线。"
                :closable="false"
                show-icon
              >
                <el-button class="alert-action" link type="primary" @click="openGovernanceForSelectedProposal">
                  去术语规则集治理页处理
                </el-button>
              </el-alert>

              <div class="review-panels app-review-grid">
                <div>
                  <h3>提议变更</h3>
                  <p><b>类型：</b>{{ proposalIntentText(selectedProposal.intent) }}</p>
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
                  <el-button
                    class="governance-link-button"
                    type="primary"
                    plain
                    @click="openGovernanceForSelectedProposal"
                  >
                    打开术语规则治理上下文
                  </el-button>
                </div>
                <div>
                  <h3>当前规则</h3>
                  <p>用于人工比对是否仍与提交时一致。</p>
                  <el-collapse class="technical-collapse">
                    <el-collapse-item title="查看技术字段">
                      <pre class="app-technical-block">{{ currentRuleText }}</pre>
                    </el-collapse-item>
                  </el-collapse>
                </div>
                <div>
                  <h3>提交时快照</h3>
                  <p>后端审核时会用它识别过期修改。</p>
                  <el-collapse class="technical-collapse">
                    <el-collapse-item title="查看技术字段">
                      <pre class="app-technical-block">{{ snapshotText }}</pre>
                    </el-collapse-item>
                  </el-collapse>
                </div>
              </div>

              <el-input
                v-model="reviewComment"
                class="review-comment"
                type="textarea"
                :rows="3"
                placeholder="审核意见；拒绝必填，通过可选。"
              />
              <div class="toolbar app-action-row">
                <el-button
                  type="success"
                  :loading="reviewing"
                  :disabled="selectedProposal.status !== 'pending_review'"
                  @click="approveProposal"
                >
                  通过并合并草稿
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
                  拒绝
                </el-button>
              </div>
            </template>
            <el-empty v-else description="请选择一条建议" :image-size="90" />
          </WorkbenchPanelCard>
        </section>
      </el-tab-pane>
      <el-tab-pane v-if="isAdmin" label="全部建议" name="all">
        <TermProposalTable
          :items="proposals"
          :categories="categoryMap"
          :loading="loading"
          :selected-id="selectedTermProposalId"
          @select="selectProposal"
        />
      </el-tab-pane>
      <el-tab-pane label="翻译术语：我的" name="translation-mine">
        <TranslationTermProposalTable
          :items="translationProposals"
          :loading="loading"
          :selected-id="selectedTranslationProposalId"
          @select="selectTranslationProposal"
        />
      </el-tab-pane>
      <el-tab-pane v-if="isAdmin" label="翻译术语待审核" name="translation-review">
        <section class="review-grid">
          <div class="review-list-panel">
            <WorkbenchPanelCard
              title="批量审核"
              subtitle="仅待审核翻译术语建议可勾选；不提供批量发布。"
              card-class="app-panel-card batch-review-card"
              body-class="batch-review-body"
            >
              <template #actions>
                <el-tag effect="plain">已选 {{ translationBulkSelectedCount }}</el-tag>
              </template>
              <el-input
                v-model="translationBulkReviewNote"
                class="review-comment"
                type="textarea"
                :rows="2"
                placeholder="批量审核意见；拒绝必填，通过可选。"
              />
              <div class="toolbar app-action-row">
                <el-button
                  type="success"
                  :loading="bulkReviewing"
                  :disabled="!translationBulkSelectedCount || reviewing"
                  @click="bulkApproveTranslationProposals"
                >
                  批量通过
                </el-button>
                <el-button
                  type="danger"
                  :loading="bulkReviewing"
                  :disabled="!translationBulkSelectedCount || reviewing"
                  @click="bulkRejectTranslationProposals"
                >
                  批量拒绝
                </el-button>
              </div>
              <el-alert
                v-if="translationBulkResult"
                class="bulk-result-alert"
                :type="translationBulkResult.failed ? 'warning' : 'success'"
                :title="translationBulkResultTitle"
                :closable="true"
                show-icon
                @close="translationBulkResult = null"
              >
                <ul v-if="translationBulkFailureItems.length" class="error-detail-list">
                  <li v-for="item in translationBulkFailureItems" :key="item.proposal_id">
                    {{ formatTranslationBulkFailureItem(item) }}
                  </li>
                </ul>
              </el-alert>
            </WorkbenchPanelCard>
            <TranslationTermProposalTable
              ref="translationReviewTableRef"
              :items="translationProposals"
              :loading="loading"
              :selected-id="selectedTranslationProposalId"
              selectable
              @select="selectTranslationProposal"
              @selection-change="handleTranslationBulkSelectionChange"
            />
          </div>
          <WorkbenchPanelCard card-class="app-panel-card" body-class="review-detail-card-body">
            <template v-if="selectedTranslationProposal">
              <WorkbenchSectionHeader
                title="翻译术语审核详情"
                subtitle="展示提交时绑定版本、提议变更和发布结果。"
              >
                <template #extra>
                  <el-tag :type="selectedTranslationProposal.status === 'pending' ? 'warning' : 'info'" effect="plain">
                    {{ proposalStatusText(selectedTranslationProposal.status) }}
                  </el-tag>
                </template>
              </WorkbenchSectionHeader>

              <div class="review-panels app-review-grid">
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
                  <ul class="change-list">
                    <li v-for="(change, index) in selectedTranslationProposal.changes" :key="index">
                      <b>{{ translationProposalActionText(change.action) }}</b>
                      <span>{{ change.source_term || "-" }}</span>
                      <span v-if="change.target_term">→ {{ change.target_term }}</span>
                      <small v-if="change.note">{{ change.note }}</small>
                    </li>
                  </ul>
                  <el-collapse class="technical-collapse">
                    <el-collapse-item title="查看技术字段">
                      <pre class="app-technical-block">{{ translationChangesText }}</pre>
                    </el-collapse-item>
                  </el-collapse>
                  <el-button
                    class="governance-link-button"
                    type="primary"
                    plain
                    @click="openTranslationGovernanceForSelectedProposal"
                  >
                    打开翻译术语集治理上下文
                  </el-button>
                </div>
                <div>
                  <h3>发布结果</h3>
                  <p><b>发布到术语集：</b>{{ selectedTranslationProposal.published_translation_term_set_id || "-" }}</p>
                  <p><b>发布版本：</b>{{ selectedTranslationProposal.published_translation_term_version || "-" }}</p>
                  <p><b>审核备注：</b>{{ selectedTranslationProposal.review_note || "-" }}</p>
                </div>
              </div>

              <el-input
                v-model="translationReviewNote"
                class="review-comment"
                type="textarea"
                :rows="3"
                placeholder="审核意见；拒绝必填，通过可选。"
              />
              <div class="toolbar app-action-row">
                <el-button
                  type="success"
                  :loading="reviewing"
                  :disabled="selectedTranslationProposal.status !== 'pending'"
                  @click="approveTranslationProposal"
                >
                  通过并合并草稿
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
                  拒绝
                </el-button>
              </div>
            </template>
            <el-empty v-else description="请选择一条翻译术语建议" :image-size="90" />
          </WorkbenchPanelCard>
        </section>
      </el-tab-pane>
      <el-tab-pane v-if="isAdmin" label="翻译术语全部" name="translation-all">
        <TranslationTermProposalTable
          :items="translationProposals"
          :loading="loading"
          :selected-id="selectedTranslationProposalId"
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
import { useRoute, useRouter } from "vue-router";

import {
  termProposalsApi,
  translationTermProposalsApi,
  type TermProposalScope,
  type TranslationTermProposalScope,
} from "@/api/termProposals";
import { termRuleSetsApi } from "@/api/termRuleSets";
import { termRulesApi } from "@/api/termRules";
import type {
  TermRuleCategoryListItemResponse,
  TermRuleProposalBulkItemResponse,
  TermRuleProposalBulkResponse,
  TermRuleProposalConflictItemResponse,
  TermRuleProposalConflictResponse,
  TermRuleProposalIntent,
  TermRuleProposalResponse,
  TermRuleResponse,
  TermRuleSegmentResponse,
  TermRuleSegmentWriteRequest,
  TranslationTermProposalBulkItemResponse,
  TranslationTermProposalBulkResponse,
  TranslationTermProposalCompatibilityFindingResponse,
  TranslationTermProposalConflictResponse,
  TranslationTermProposalAction,
  TranslationTermProposalResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import TermPreview from "@/components/TermPreview.vue";
import TermProposalTable from "@/components/TermProposalTable.vue";
import TermSegmentEditor from "@/components/TermSegmentEditor.vue";
import TranslationTermProposalTable from "@/components/TranslationTermProposalTable.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import WorkbenchSectionHeader from "@/components/WorkbenchSectionHeader.vue";
import { useAuthStore } from "@/stores/auth";
import { proposalIntentText, proposalStatusText, translationProposalActionText } from "@/utils/displayText";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

type ProposalTab =
  | "mine"
  | "new"
  | "review"
  | "all"
  | "translation-mine"
  | "translation-new"
  | "translation-review"
  | "translation-all";
type TermQueueTab = "mine" | "review" | "all";
type TranslationQueueTab = "translation-mine" | "translation-review" | "translation-all";
const DEFAULT_TERM_RULE_SET_ID = "electronics-default";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const isAdmin = computed(() => auth.user?.role === "admin");
const activeTab = ref(initialActiveTab());
const loading = ref(false);
const submitting = ref(false);
const reviewing = ref(false);
const bulkReviewing = ref(false);
const error = ref<ApiClientError | null>(null);
const categories = ref<TermRuleCategoryListItemResponse[]>([]);
const rules = ref<TermRuleResponse[]>([]);
const proposals = ref<TermRuleProposalResponse[]>([]);
const translationProposals = ref<TranslationTermProposalResponse[]>([]);
const selectedTermProposalId = ref("");
const selectedTranslationProposalId = ref("");
const selectedProposal = ref<TermRuleProposalResponse | null>(null);
const selectedTranslationProposal = ref<TranslationTermProposalResponse | null>(null);
const currentRule = ref<TermRuleResponse | null>(null);
const reviewComment = ref("");
const bulkReviewComment = ref("");
const translationReviewNote = ref("");
const translationBulkReviewNote = ref("");
const bulkSelectedProposals = ref<TermRuleProposalResponse[]>([]);
const bulkResult = ref<TermRuleProposalBulkResponse | null>(null);
const translationBulkSelectedProposals = ref<TranslationTermProposalResponse[]>([]);
const translationBulkResult = ref<TranslationTermProposalBulkResponse | null>(null);
const focusNotice = ref("");
const routeFocusProposalId = ref("");
const skipNextTabChangeLoad = ref(false);
const proposalFormRef = ref<FormInstance>();
const translationProposalFormRef = ref<FormInstance>();
const termRuleContextLocked = ref(false);
const translationContextLocked = ref(false);
const termRuleSuggestionMode = ref(false);
const termReviewTableRef = ref<InstanceType<typeof TermProposalTable> & { clearSelection: () => void }>();
const translationReviewTableRef = ref<InstanceType<typeof TranslationTermProposalTable> & { clearSelection: () => void }>();

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
const focusNoticeVisible = computed(() =>
  Boolean(focusNotice.value) && (isTermQueueTab(activeTab.value) || isTranslationQueueTab(activeTab.value)),
);
const errorDetailItems = computed(() => extractErrorDetailItems(error.value?.raw));
const bulkSelectedCount = computed(() => bulkSelectedProposals.value.length);
const bulkFailureItems = computed(() => bulkResult.value?.items.filter((item) => !item.ok) || []);
const bulkResultTitle = computed(() => {
  if (!bulkResult.value) {
    return "";
  }
  const actionText = bulkResult.value.action === "approve" ? "批量通过" : "批量拒绝";
  return `${actionText} 完成：成功 ${bulkResult.value.succeeded}，失败 ${bulkResult.value.failed}，总计 ${bulkResult.value.total}`;
});
const translationBulkSelectedCount = computed(() => translationBulkSelectedProposals.value.length);
const translationBulkFailureItems = computed(() => translationBulkResult.value?.items.filter((item) => !item.ok) || []);
const translationBulkResultTitle = computed(() => {
  if (!translationBulkResult.value) {
    return "";
  }
  const actionText = translationBulkResult.value.action === "approve" ? "批量通过" : "批量拒绝";
  return `${actionText} 完成：成功 ${translationBulkResult.value.succeeded}，失败 ${translationBulkResult.value.failed}，总计 ${translationBulkResult.value.total}`;
});
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
          callback(new Error("编辑或禁用建议必须选择现有规则。"));
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

// 加载 proposal 表单所需的 draft 分类和规则，避免版本化模式下引用 legacy rule/category。
async function loadReferenceData(): Promise<void> {
  const [categoryResponse, ruleResponse] = await Promise.all([
    termRulesApi.listCategories(),
    termRuleSetsApi.listDraftRules(DEFAULT_TERM_RULE_SET_ID, { page_size: 200, enabled: true }),
  ]);
  categories.value = categoryResponse.items;
  rules.value = ruleResponse.items;
}

// 识别所有受支持的 proposal tab，避免 query/tab 判断分散在多个分支里。
function isProposalTab(tab: string): tab is ProposalTab {
  return [
    "mine",
    "new",
    "review",
    "all",
    "translation-mine",
    "translation-new",
    "translation-review",
    "translation-all",
  ].includes(tab);
}

// 区分 Term Rule form tab，避免 form context 与 queue focus 逻辑互相污染。
function isTermFormTab(tab: string): tab is "new" {
  return tab === "new";
}

// 区分 Translation form tab，确保 proposal_id 不会误作用于表单模式。
function isTranslationFormTab(tab: string): tab is "translation-new" {
  return tab === "translation-new";
}

// 区分 Term Rule queue tab，给 scope/focus/fallback 使用统一入口。
function isTermQueueTab(tab: string): tab is TermQueueTab {
  return tab === "mine" || tab === "review" || tab === "all";
}

// 区分 Translation queue tab，避免手写 startsWith 带来的隐式耦合。
function isTranslationQueueTab(tab: string): tab is TranslationQueueTab {
  return tab === "translation-mine" || tab === "translation-review" || tab === "translation-all";
}

// 只有 review 队列支持自动回退到 all 队列，其余 tab 保持用户原意不扩视野。
function fallbackTabFor(tab: ProposalTab): ProposalTab | null {
  if (tab === "review") {
    return "all";
  }
  if (tab === "translation-review") {
    return "translation-all";
  }
  return null;
}

// admin 默认进 review，operator 默认进 mine，作为 route 缺省值。
function defaultTab(): ProposalTab {
  return isAdmin.value ? "review" : "mine";
}

// 读取 route 中请求的 tab，并在未知值时回退到当前角色的默认 tab。
function requestedRouteTab(): ProposalTab {
  const tab = queryString("tab");
  return isProposalTab(tab) ? tab : defaultTab();
}

// 统一处理代码内主动切换 tab 的场景，避免与 el-tabs 的 tab-change 重复加载。
function setActiveTabSilently(tab: ProposalTab): void {
  if (activeTab.value === tab) {
    return;
  }
  skipNextTabChangeLoad.value = true;
  activeTab.value = tab;
}

// 清理 Term Rule 审核详情，但保留 remembered id，便于后续 queue 恢复。
function clearTermSelection(): void {
  selectedProposal.value = null;
  currentRule.value = null;
  reviewComment.value = "";
}

// 清理 Term Rule 批量勾选状态，避免刷新或切 tab 后保留过期选择。
function clearTermBulkSelection(): void {
  bulkSelectedProposals.value = [];
  termReviewTableRef.value?.clearSelection();
}

// 清理 Translation 批量勾选状态，避免刷新或切 tab 后保留过期选择。
function clearTranslationBulkSelection(): void {
  translationBulkSelectedProposals.value = [];
  translationReviewTableRef.value?.clearSelection();
}

// 清理 Translation 审核详情，但保留 remembered id，便于后续 queue 恢复。
function clearTranslationSelection(): void {
  selectedTranslationProposal.value = null;
  translationReviewNote.value = "";
}

// 从当前 term 列表中恢复选中项；找不到时只清空详情，不报错。
async function restoreTermSelection(targetId: string): Promise<boolean> {
  const proposal = proposals.value.find((item) => item.id === targetId);
  if (!proposal) {
    clearTermSelection();
    return false;
  }
  await selectProposal(proposal);
  return true;
}

// 从当前 translation 列表中恢复选中项；找不到时只清空详情。
function restoreTranslationSelection(targetId: string): boolean {
  const proposal = translationProposals.value.find((item) => item.id === targetId);
  if (!proposal) {
    clearTranslationSelection();
    return false;
  }
  selectTranslationProposal(proposal);
  return true;
}

// 根据当前 tab 把 Term Rule queue 映射到后端 scope。
function termScopeForTab(tab: TermQueueTab): TermProposalScope {
  if (tab === "review") {
    return "pending_review";
  }
  if (tab === "all") {
    return "all";
  }
  return "my";
}

// 根据当前 tab 把 Translation queue 映射到后端 scope。
function translationScopeForTab(tab: TranslationQueueTab): TranslationTermProposalScope {
  if (tab === "translation-review") {
    return "pending";
  }
  if (tab === "translation-all") {
    return "all";
  }
  return "my";
}

// 统一生成 deep-link 未命中时的轻量提示，避免 route/fallback 行为静默发生。
function missingProposalNotice(targetId: string): string {
  return `未在当前列表中定位到建议 ${targetId}。`;
}

// 显式说明因 deep-link 不在 review 队列而回退到 all 队列，减少 admin 的困惑。
function fallbackProposalNotice(targetId: string, tab: ProposalTab): string {
  if (tab === "translation-review") {
    return `目标建议 ${targetId} 不在翻译术语待审核队列，已切换到翻译术语全部列表。`;
  }
  return `目标建议 ${targetId} 不在待审核队列，已切换到全部建议列表。`;
}

// 在一次加载周期里解析 term queue 的 deep-link / remembered-id / review fallback。
async function resolveTermQueueFocus(tab: TermQueueTab): Promise<void> {
  const targetId = routeFocusProposalId.value || selectedTermProposalId.value;
  if (!targetId) {
    clearTermSelection();
    return;
  }

  if (await restoreTermSelection(targetId)) {
    return;
  }

  const fallbackTab = routeFocusProposalId.value ? fallbackTabFor(tab) : null;
  if (fallbackTab === "all") {
    setActiveTabSilently(fallbackTab);
    proposals.value = (await termProposalsApi.list({ scope: termScopeForTab(fallbackTab) })).items;
    if (await restoreTermSelection(targetId)) {
      focusNotice.value = fallbackProposalNotice(targetId, tab);
      return;
    }
  }

  if (routeFocusProposalId.value) {
    focusNotice.value = missingProposalNotice(targetId);
  }
}

// 在一次加载周期里解析 translation queue 的 deep-link / remembered-id / review fallback。
async function resolveTranslationQueueFocus(tab: TranslationQueueTab): Promise<void> {
  const targetId = routeFocusProposalId.value || selectedTranslationProposalId.value;
  if (!targetId) {
    clearTranslationSelection();
    return;
  }

  if (restoreTranslationSelection(targetId)) {
    return;
  }

  const fallbackTab = routeFocusProposalId.value ? fallbackTabFor(tab) : null;
  if (fallbackTab === "translation-all") {
    setActiveTabSilently(fallbackTab);
    translationProposals.value = (await translationTermProposalsApi.list({ scope: translationScopeForTab(fallbackTab) })).items;
    if (restoreTranslationSelection(targetId)) {
      focusNotice.value = fallbackProposalNotice(targetId, tab);
      return;
    }
  }

  if (routeFocusProposalId.value) {
    focusNotice.value = missingProposalNotice(targetId);
  }
}

// 按当前 tab 加载 form 或 queue，并在 queue 场景里恢复 deep-link / remembered selection。
async function loadActiveTab(): Promise<void> {
  const currentTab = activeTab.value;
  loading.value = true;
  error.value = null;
  focusNotice.value = "";
  clearTermBulkSelection();
  clearTranslationBulkSelection();
  try {
    if (isTermFormTab(currentTab)) {
      bulkResult.value = null;
      translationBulkResult.value = null;
      clearTermSelection();
      clearTranslationSelection();
      await loadReferenceData();
      return;
    }
    if (isTranslationFormTab(currentTab)) {
      bulkResult.value = null;
      translationBulkResult.value = null;
      clearTermSelection();
      clearTranslationSelection();
      return;
    }
    if (isTranslationQueueTab(currentTab)) {
      bulkResult.value = null;
      clearTermSelection();
      const scope = translationScopeForTab(currentTab);
      translationProposals.value = (await translationTermProposalsApi.list({ scope })).items;
      await resolveTranslationQueueFocus(currentTab);
      return;
    }

    clearTranslationSelection();
    translationBulkResult.value = null;
    await loadReferenceData();
    const scope = termScopeForTab(currentTab);
    proposals.value = (await termProposalsApi.list({ scope })).items;
    await resolveTermQueueFocus(currentTab);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

// 只把用户手动 tab 切换当成新的本地意图，清空 route focus 并重载当前 tab。
function handleTabChange(): void {
  if (skipNextTabChangeLoad.value) {
    skipNextTabChangeLoad.value = false;
    return;
  }
  routeFocusProposalId.value = "";
  focusNotice.value = "";
  if (activeTab.value !== "new") {
    termRuleSuggestionMode.value = false;
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
  if (isTranslationTermProposalConflictDetail(detail)) {
    return detail.conflicts.map((item) => formatTranslationProposalConflictFinding(item));
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

// 识别 Translation Proposal 的结构化 409 响应。
function isTranslationTermProposalConflictDetail(value: Record<string, unknown> | null): value is TranslationTermProposalConflictResponse {
  return (
    value?.code === "translation_term_proposal_conflict" &&
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
    `建议 ${item.proposal_id}`,
    `目标规则 ${item.target_rule_id || "-"}`,
    `原文术语 ${item.source_term}`,
    `分类 ${categoryName(item.category_id)}`,
  ];
  const currentRuleText = item.current_rule
    ? `当前规则 ${item.current_rule.source_term} (${item.current_rule.id})`
    : "当前规则 -";
  return `${typeText[item.type] || item.type}: ${item.message}（${context.join("；")}；${currentRuleText}）`;
}

// 识别 Translation Proposal compatibility-style finding，兼容 detail.conflicts[] 被单独遍历。
function isTranslationProposalConflictFinding(value: unknown): value is TranslationTermProposalCompatibilityFindingResponse {
  const record = readRecord(value);
  return Boolean(
    record &&
    readString(record.severity) &&
    readString(record.code) &&
    readString(record.message),
  );
}

// 将 Translation conflict finding 压缩成一行，保留当前 draft 与 observed entry 的关键差异。
function formatTranslationProposalConflictFinding(
  item: TranslationTermProposalCompatibilityFindingResponse,
  proposalId?: string,
): string {
  const currentEntry = readRecord(item.current_entry);
  const observedEntry = readRecord(item.observed_entry);
  const context = [
    proposalId ? `建议 ${proposalId}` : "",
    item.normalized_source_term ? `术语 ${item.normalized_source_term}` : "",
    item.action ? `动作 ${translationProposalActionText(item.action)}` : "",
  ].filter(Boolean);
  const currentTarget = readString(currentEntry?.target_term) || "-";
  const observedTarget = readString(observedEntry?.target_term) || "-";
  return `${item.code}: ${item.message}（${context.join("；")}；当前译文 ${currentTarget}；证据译文 ${observedTarget}）`;
}

// 格式化后端 detail 数组项；结构化对象优先读 message，未知对象保留 JSON。
function formatDetailItem(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (isTermRuleProposalConflictItem(value)) {
    return formatTermRuleProposalConflictItem(value);
  }
  if (isTranslationProposalConflictFinding(value)) {
    return formatTranslationProposalConflictFinding(value);
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

// 根据路由 query 打开指定 tab，支持从治理页面跳转到审核或新建入口。
function initialActiveTab(): ProposalTab {
  return requestedRouteTab();
}

// 将任务详情或治理页面传入的上下文写入当前 proposal 表单/tab。
function applyRouteProposalContext(): void {
  const tab = requestedRouteTab();
  if (isTermFormTab(tab)) {
    resetProposalForm();
    termRuleSuggestionMode.value = queryString("proposal_type") === "term_rule_suggestion";
    if (termRuleSuggestionMode.value) {
      proposalForm.intent = "create";
      proposalForm.reason = queryString("reason") || "术语规则建议：";
    }
    proposalForm.source_job_id = queryString("source_job_id");
    proposalForm.source_file_id = queryString("source_file_id");
    proposalForm.observed_term_rule_set_id = queryString("observed_term_rule_set_id");
    proposalForm.observed_term_rule_version = queryString("observed_term_rule_version");
    termRuleContextLocked.value = Boolean(proposalForm.source_job_id);
    setActiveTabSilently("new");
    return;
  }
  if (isTranslationFormTab(tab)) {
    resetTranslationProposalForm();
    translationProposalForm.source_job_id = queryString("source_job_id");
    translationProposalForm.source_file_id = queryString("source_file_id");
    translationProposalForm.observed_translation_term_set_id = queryString("observed_translation_term_set_id");
    translationProposalForm.observed_translation_term_version = queryString("observed_translation_term_version");
    translationContextLocked.value = Boolean(translationProposalForm.source_job_id);
    setActiveTabSilently("translation-new");
    return;
  }
  termRuleContextLocked.value = false;
  translationContextLocked.value = false;
  setActiveTabSilently(tab);
}

// 提交 Term Rule proposal 后切回 mine，并丢弃旧的 route focus。
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
    routeFocusProposalId.value = "";
    selectedTermProposalId.value = "";
    setActiveTabSilently("mine");
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
  termRuleSuggestionMode.value = false;
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

// 提交 Translation proposal 后切回 mine，避免继承旧 deep-link 选中态。
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
    routeFocusProposalId.value = "";
    selectedTranslationProposalId.value = "";
    setActiveTabSilently("translation-mine");
    resetTranslationProposalForm();
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    submitting.value = false;
  }
}

// 选中 Term Rule proposal，并在详情侧补齐当前规则快照。
async function selectProposal(proposal: TermRuleProposalResponse): Promise<void> {
  routeFocusProposalId.value = "";
  selectedTermProposalId.value = proposal.id;
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

// 同步 Term Rule review tab 的批量勾选结果。
function handleTermBulkSelectionChange(selection: TermRuleProposalResponse[]): void {
  bulkSelectedProposals.value = selection;
}

// 读取当前批量选择的 proposal IDs，避免请求使用过期 table 行对象。
function selectedBulkProposalIds(): string[] {
  return bulkSelectedProposals.value.map((proposal) => proposal.id);
}

// 批量响应后刷新队列，并优先定位第一条失败项供继续治理。
async function handleBulkReviewResponse(response: TermRuleProposalBulkResponse): Promise<void> {
  bulkResult.value = response;
  const firstFailed = response.items.find((item) => !item.ok);
  selectedTermProposalId.value = firstFailed?.proposal_id || "";
  routeFocusProposalId.value = "";
  if (!firstFailed) {
    clearTermSelection();
    bulkReviewComment.value = "";
  }
  clearTermBulkSelection();
  if (response.failed) {
    ElMessage.warning(`批量审核完成：成功 ${response.succeeded}，失败 ${response.failed}。`);
  } else {
    ElMessage.success("批量审核全部成功。");
  }
  await loadActiveTab();
}

// 批量 approve 当前勾选的 Term Rule proposals，不触发发布流程。
async function bulkApproveProposals(): Promise<void> {
  const proposalIds = selectedBulkProposalIds();
  if (!proposalIds.length) {
    return;
  }
  bulkReviewing.value = true;
  error.value = null;
  bulkResult.value = null;
  try {
    const response = await termProposalsApi.bulkApprove({
      proposal_ids: proposalIds,
      review_comment: bulkReviewComment.value || null,
    });
    await handleBulkReviewResponse(response);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    bulkReviewing.value = false;
  }
}

// 批量 reject 当前勾选的 Term Rule proposals，拒绝原因沿用后端必填语义。
async function bulkRejectProposals(): Promise<void> {
  const proposalIds = selectedBulkProposalIds();
  if (!proposalIds.length) {
    return;
  }
  if (!bulkReviewComment.value.trim()) {
    ElMessage.warning("批量拒绝必须填写原因。");
    return;
  }
  bulkReviewing.value = true;
  error.value = null;
  bulkResult.value = null;
  try {
    const response = await termProposalsApi.bulkReject({
      proposal_ids: proposalIds,
      review_comment: bulkReviewComment.value,
    });
    await handleBulkReviewResponse(response);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    bulkReviewing.value = false;
  }
}

// 把 bulk 失败项压缩成一行，冲突项保留结构化冲突摘要。
function formatBulkFailureItem(item: TermRuleProposalBulkItemResponse): string {
  const detail = readRecord(item.detail);
  if (isTermRuleProposalConflictDetail(detail)) {
    return detail.conflicts.map((conflict) => formatTermRuleProposalConflictItem(conflict)).join("；");
  }
  return `建议 ${item.proposal_id}: ${formatDetailItem(item.detail)}`;
}

// 同步 Translation review tab 的批量勾选结果。
function handleTranslationBulkSelectionChange(selection: TranslationTermProposalResponse[]): void {
  translationBulkSelectedProposals.value = selection;
}

// 读取当前批量选择的 Translation proposal IDs，避免请求使用过期 table 行对象。
function selectedTranslationBulkProposalIds(): string[] {
  return translationBulkSelectedProposals.value.map((proposal) => proposal.id);
}

// 批量响应后刷新 Translation 队列，并优先定位第一条失败项供继续治理。
async function handleTranslationBulkReviewResponse(response: TranslationTermProposalBulkResponse): Promise<void> {
  translationBulkResult.value = response;
  const firstFailed = response.items.find((item) => !item.ok);
  selectedTranslationProposalId.value = firstFailed?.proposal_id || "";
  routeFocusProposalId.value = "";
  if (!firstFailed) {
    clearTranslationSelection();
    translationBulkReviewNote.value = "";
  }
  clearTranslationBulkSelection();
  if (response.failed) {
    ElMessage.warning(`批量审核完成：成功 ${response.succeeded}，失败 ${response.failed}。`);
  } else {
    ElMessage.success("批量审核全部成功。");
  }
  await loadActiveTab();
}

// 批量 approve 当前勾选的 Translation proposals，不触发发布流程。
async function bulkApproveTranslationProposals(): Promise<void> {
  const proposalIds = selectedTranslationBulkProposalIds();
  if (!proposalIds.length) {
    return;
  }
  bulkReviewing.value = true;
  error.value = null;
  translationBulkResult.value = null;
  try {
    const response = await translationTermProposalsApi.bulkApprove({
      proposal_ids: proposalIds,
      review_note: translationBulkReviewNote.value || null,
    });
    await handleTranslationBulkReviewResponse(response);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    bulkReviewing.value = false;
  }
}

// 批量 reject 当前勾选的 Translation proposals，拒绝原因沿用后端必填语义。
async function bulkRejectTranslationProposals(): Promise<void> {
  const proposalIds = selectedTranslationBulkProposalIds();
  if (!proposalIds.length) {
    return;
  }
  if (!translationBulkReviewNote.value.trim()) {
    ElMessage.warning("批量拒绝必须填写原因。");
    return;
  }
  bulkReviewing.value = true;
  error.value = null;
  translationBulkResult.value = null;
  try {
    const response = await translationTermProposalsApi.bulkReject({
      proposal_ids: proposalIds,
      review_note: translationBulkReviewNote.value,
    });
    await handleTranslationBulkReviewResponse(response);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    bulkReviewing.value = false;
  }
}

// 把 Translation bulk 失败项压缩成一行，冲突项保留 compatibility-style finding 摘要。
function formatTranslationBulkFailureItem(item: TranslationTermProposalBulkItemResponse): string {
  const detail = readRecord(item.detail);
  if (isTranslationTermProposalConflictDetail(detail)) {
    return detail.conflicts.map((conflict) => formatTranslationProposalConflictFinding(conflict, item.proposal_id)).join("；");
  }
  return `建议 ${item.proposal_id}: ${formatDetailItem(item.detail)}`;
}

// 获取 proposal 对应的治理 set；缺省值与后端默认 Term Rule Set 保持一致。
function governanceSetIdFor(proposal: TermRuleProposalResponse): string {
  return proposal.observed_term_rule_set_id || proposal.merged_term_rule_set_id || "electronics-default";
}

// 从审核详情跳转到 Term Rule Set 治理页，并携带返回 proposal 页所需的上下文。
function openGovernanceForSelectedProposal(): void {
  if (!selectedProposal.value) {
    return;
  }
  const proposal = selectedProposal.value;
  void router.push({
    name: "settings-term-rule-sets",
    query: {
      set_id: governanceSetIdFor(proposal),
      proposal_id: proposal.id,
      target_rule_id: proposal.target_rule_id || "",
      source_term: proposal.source_term,
      return_to: "term-proposals",
      return_tab: "review",
    },
  });
}

// 获取 Translation proposal 对应的治理 set；缺省值与系统内置 en2zh set 保持一致。
function translationGovernanceSetIdFor(proposal: TranslationTermProposalResponse): string {
  return proposal.observed_translation_term_set_id || proposal.published_translation_term_set_id || "translation-terms-en2zh";
}

// 从审核详情跳转到 Translation Term Set 治理页，并携带返回 proposal 页所需的上下文。
function openTranslationGovernanceForSelectedProposal(): void {
  if (!selectedTranslationProposal.value) {
    return;
  }
  const proposal = selectedTranslationProposal.value;
  void router.push({
    name: "settings-translation-term-sets",
    query: {
      set_id: translationGovernanceSetIdFor(proposal),
      proposal_id: proposal.id,
      observed_version: proposal.observed_translation_term_version || "",
      return_to: "term-proposals",
      return_tab: "translation-review",
    },
  });
}

// 选中 Translation proposal，并同步当前审核备注输入框。
function selectTranslationProposal(proposal: TranslationTermProposalResponse): void {
  routeFocusProposalId.value = "";
  selectedTranslationProposalId.value = proposal.id;
  selectedTranslationProposal.value = proposal;
  translationReviewNote.value = proposal.review_note || "";
}

// 审核通过当前 Term Rule proposal，并清理已消费的 route focus。
async function approveProposal(): Promise<void> {
  if (!selectedProposal.value) {
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    await termProposalsApi.approve(selectedProposal.value.id, reviewComment.value);
    ElMessage.success("建议已合并到术语规则集草稿。");
    routeFocusProposalId.value = "";
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

// 审核并发布当前 Term Rule proposal，但不改变既有后端语义。
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
      publish_reason: `发布已通过的术语建议：${sourceTerm}`,
    });
    ElMessage.success("建议已审核并发布为默认规则版本。");
    routeFocusProposalId.value = "";
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

// 拒绝当前 Term Rule proposal，并在刷新前清理 route focus。
async function rejectProposal(): Promise<void> {
  if (!selectedProposal.value) {
    return;
  }
  if (!reviewComment.value.trim()) {
    ElMessage.warning("拒绝必须填写原因。");
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    await termProposalsApi.reject(selectedProposal.value.id, reviewComment.value);
    ElMessage.success("建议已拒绝。");
    routeFocusProposalId.value = "";
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

// 审核通过当前 Translation proposal，并保持 queue 刷新行为可预期。
async function approveTranslationProposal(): Promise<void> {
  if (!selectedTranslationProposal.value) {
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    await translationTermProposalsApi.approve(selectedTranslationProposal.value.id, translationReviewNote.value);
    ElMessage.success("翻译术语建议已合并到草稿。");
    routeFocusProposalId.value = "";
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

// 审核并发布当前 Translation proposal，但仍保持单条语义。
async function approveAndPublishTranslationProposal(): Promise<void> {
  if (!selectedTranslationProposal.value) {
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    await translationTermProposalsApi.approveAndPublish(selectedTranslationProposal.value.id, {
      review_note: translationReviewNote.value || null,
      release_note: `发布已通过的翻译术语建议：${selectedTranslationProposal.value.id}`,
    });
    ElMessage.success("翻译术语建议已审核并发布为默认版本。");
    routeFocusProposalId.value = "";
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

// 拒绝当前 Translation proposal，并避免刷新后再次触发旧 deep-link。
async function rejectTranslationProposal(): Promise<void> {
  if (!selectedTranslationProposal.value) {
    return;
  }
  if (!translationReviewNote.value.trim()) {
    ElMessage.warning("拒绝必须填写原因。");
    return;
  }
  reviewing.value = true;
  error.value = null;
  try {
    await translationTermProposalsApi.reject(selectedTranslationProposal.value.id, translationReviewNote.value);
    ElMessage.success("翻译术语建议已拒绝。");
    routeFocusProposalId.value = "";
    await loadActiveTab();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewing.value = false;
  }
}

watch(() => route.fullPath, () => {
  routeFocusProposalId.value = queryString("proposal_id");
  applyRouteProposalContext();
  void loadActiveTab();
}, { immediate: true });
</script>

<style scoped lang="scss">
.term-proposals-page {
  display: grid;
  gap: var(--app-space-4);
}

.review-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 520px);
  gap: var(--app-space-4);
}

.review-list-panel {
  display: grid;
  align-content: start;
  gap: var(--app-space-3);
  min-width: 0;
}

.batch-review-card {
  border-left: 4px solid var(--app-color-primary);
}

.batch-review-header {
  display: flex;
  justify-content: space-between;
  gap: var(--app-space-3);
  align-items: flex-start;
  margin-bottom: var(--app-space-3);
}

.proposal-table-wrap {
  overflow-x: auto;
}

.conflict-alert,
.review-comment,
.bulk-result-alert {
  margin-bottom: var(--app-space-3);
}

.focus-notice {
  margin-bottom: var(--app-space-3);
}

.error-detail-list {
  margin: 6px 0 0;
  padding-left: 18px;
}

.alert-action {
  margin-top: 8px;
}

.governance-link-button {
  margin-top: 8px;
}

.review-panels {
  display: grid;
  gap: var(--app-space-3);
  margin-bottom: var(--app-space-3);
}

.review-panels h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.review-panels p {
  margin: 6px 0;
}

@media (max-width: 1100px) {
  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>
