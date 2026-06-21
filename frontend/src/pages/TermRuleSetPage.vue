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
      <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Draft 规则</h2>
            <p class="section-subtitle">新增、编辑、启停和移除都只作用于 draft。</p>
          </div>
          <div class="rule-actions">
            <el-button type="primary" :icon="Plus" :disabled="!selectedSetId" @click="openCreateRuleDialog()">
              新增规则
            </el-button>
            <el-button :icon="EditPen" :disabled="!selectedSetId" @click="openCreateRuleDialog('advanced')">
              新增高级规则
            </el-button>
          </div>
        </div>

        <div class="toolbar filters app-filter-panel" role="search">
          <el-select v-model="draftRuleFilters.categoryId" clearable placeholder="全部分类" class="filter-select">
            <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
          </el-select>
          <el-select v-model="draftRuleFilters.enabled" placeholder="全部状态" class="filter-select">
            <el-option label="全部状态" value="all" />
            <el-option label="仅启用" value="enabled" />
            <el-option label="仅停用" value="disabled" />
          </el-select>
          <el-input
            v-model="draftRuleFilters.keyword"
            clearable
            class="keyword-input"
            placeholder="搜索 source term"
            @keyup.enter="searchDraftRules"
          />
          <el-button type="primary" :icon="Search" :loading="draftRulesLoading" @click="searchDraftRules">
            搜索
          </el-button>
          <el-button @click="resetDraftRuleFilters">清除</el-button>
        </div>

        <el-table :data="draftRules" :loading="draftRulesLoading" empty-text="暂无 draft rule" class="rule-table">
          <el-table-column prop="source_term" label="Source term" min-width="150" show-overflow-tooltip />
          <el-table-column label="预览" min-width="150">
            <template #default="{ row }">
              <TermPreview :segments="row.segments" />
            </template>
          </el-table-column>
          <el-table-column prop="category_name" label="分类" min-width="130" show-overflow-tooltip />
          <el-table-column prop="apply_scope" label="Scope" width="116" />
          <el-table-column prop="priority" label="Priority" width="94" />
          <el-table-column label="状态" width="92">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">
                {{ row.enabled ? "启用" : "停用" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="EditPen" @click="openEditRuleDialog(row)">编辑</el-button>
              <el-button
                link
                type="warning"
                :icon="Switch"
                :loading="togglingRuleId === row.id"
                @click="toggleRule(row)"
              >
                {{ row.enabled ? "停用" : "启用" }}
              </el-button>
              <el-button
                link
                type="danger"
                :icon="Delete"
                :loading="deletingRuleId === row.id"
                @click="deleteRule(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-if="draftRuleTotal > draftRuleFilters.pageSize"
          v-model:current-page="draftRuleFilters.page"
          v-model:page-size="draftRuleFilters.pageSize"
          class="table-pagination"
          layout="total, prev, pager, next"
          :total="draftRuleTotal"
          :page-sizes="[20, 50, 100]"
          @current-change="loadDraftRules"
          @size-change="searchDraftRules"
        />
      </el-card>
    </RoleGate>

    <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Draft diff</h2>
          <p class="section-subtitle">默认比较当前 default published version 与 draft。</p>
        </div>
        <el-button :loading="diffLoading" @click="loadGovernanceReports">刷新 diff</el-button>
      </div>
      <div class="diff-summary app-governance-grid">
        <div v-for="item in diffCounters" :key="item.key" class="diff-counter app-governance-metric">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
      <el-table :data="diffReport?.items || []" :loading="diffLoading" empty-text="暂无 draft diff">
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag :type="changeTypeTagType(row.change_type)" effect="plain">
              {{ changeTypeLabel(row.change_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_term" label="Source term" min-width="150" show-overflow-tooltip />
        <el-table-column label="Changed fields" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.changed_fields.join(", ") || "-" }}</template>
        </el-table-column>
        <el-table-column label="Before" min-width="170">
          <template #default="{ row }">
            <TermPreview v-if="row.before" :segments="row.before.segments" />
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="After" min-width="170">
          <template #default="{ row }">
            <TermPreview v-if="row.after" :segments="row.after.segments" />
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">发布前校验</h2>
          <p class="section-subtitle">Errors 和 conflicts 会阻止发布；warnings 仅提示。</p>
        </div>
        <el-tag :type="preflightStatusType" effect="plain">
          {{ preflightStatusLabel }}
        </el-tag>
      </div>
      <el-table :data="preflightFindings" :loading="preflightLoading" empty-text="暂无 preflight finding">
        <el-table-column label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="findingTagType(row.severity)" effect="plain">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="Code" width="210" show-overflow-tooltip />
        <el-table-column prop="message" label="说明" min-width="260" show-overflow-tooltip />
        <el-table-column prop="source_term" label="Source term" width="150" show-overflow-tooltip />
        <el-table-column prop="path" label="Path" width="180" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Published versions</h2>
          <p class="section-subtitle">set-default 和 rollback 只允许使用已发布版本。</p>
        </div>
      </div>
      <el-table :data="detail?.versions || []" :loading="loading" empty-text="暂无 published version">
        <el-table-column prop="version" label="版本" width="120" />
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
        <el-table-column prop="rule_count" label="规则数" width="100" />
        <el-table-column prop="enabled_rule_count" label="启用规则" width="110" />
        <el-table-column prop="snapshot_hash" label="snapshot" min-width="180" show-overflow-tooltip />
        <el-table-column label="发布时间" width="190">
          <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column prop="publish_reason" label="发布说明" min-width="180" show-overflow-tooltip />
        <el-table-column v-if="isAdmin" label="admin 操作" width="210" fixed="right">
          <template #default="{ row }">
            <RoleGate>
              <el-button link type="warning" :disabled="row.is_default" @click="setDefault(row.version)">设默认</el-button>
              <el-button link type="danger" @click="rollback(row.version)">Rollback</el-button>
            </RoleGate>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <RoleGate>
      <el-card v-if="!unavailable" class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">已 approve 待核对 proposals</h2>
            <p class="section-subtitle">发布前核对本次已审核合并的来源建议。</p>
          </div>
        </div>
        <TermProposalTable
          :items="approvedProposals"
          :categories="categoryMap"
          :loading="loading"
          @select="openApprovedProposal"
        />
      </el-card>
    </RoleGate>

    <RoleGate>
      <el-card v-if="!unavailable" class="app-panel-card app-page-shell app-page-shell--wide" shadow="never">
        <el-collapse>
          <el-collapse-item title="YAML 高级编辑兜底" name="yaml">
            <el-alert
              class="yaml-warning"
              type="warning"
              title="这是高级兜底入口。主流程应优先使用结构化 draft rule 编辑，保存前会由后端校验 YAML。"
              :closable="false"
              show-icon
            />
            <el-input v-model="yamlText" type="textarea" :rows="14" class="mono" />
            <el-button class="yaml-save" type="warning" :loading="savingYaml" @click="saveYamlDraft">
              保存 YAML draft
            </el-button>
          </el-collapse-item>
        </el-collapse>
      </el-card>
    </RoleGate>

    <el-dialog
      v-model="ruleDialog.visible"
      :title="ruleDialogTitle"
      width="min(760px, calc(100vw - 32px))"
      top="24px"
      class="rule-dialog"
      append-to="body"
      :append-to-body="true"
    >
      <div class="rule-dialog-scroll">
        <el-form ref="ruleFormRef" :model="ruleForm" :rules="ruleRules" label-width="130px">
          <el-form-item label="Source term" prop="source_term">
            <el-input v-model="ruleForm.source_term" placeholder="例如 VIN" />
          </el-form-item>
          <el-form-item label="分类" prop="category_id">
            <el-select v-model="ruleForm.category_id" filterable placeholder="选择分类">
              <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="Segments" prop="segments">
            <TermSegmentEditor v-model="ruleForm.segments" />
          </el-form-item>
          <el-form-item label="预览">
            <TermPreview :segments="ruleForm.segments" />
          </el-form-item>
          <div class="rule-form-grid">
            <el-form-item label="Scope" prop="apply_scope">
              <el-select v-model="ruleForm.apply_scope">
                <el-option label="Both" value="both" />
                <el-option label="Markdown" value="markdown" />
                <el-option label="Table" value="table" />
              </el-select>
            </el-form-item>
            <el-form-item label="Priority" prop="priority">
              <el-input-number v-model="ruleForm.priority" :min="0" :max="10000" />
            </el-form-item>
            <el-form-item label="Case sensitive">
              <el-switch v-model="ruleForm.case_sensitive" />
            </el-form-item>
            <el-form-item label="启用">
              <el-switch v-model="ruleForm.enabled" />
            </el-form-item>
          </div>
          <el-form-item label="Custom markdown">
            <el-input v-model="ruleForm.custom_markdown" clearable />
          </el-form-item>
          <el-form-item label="Custom HTML">
            <el-input v-model="ruleForm.custom_html" clearable />
          </el-form-item>
          <el-form-item label="Notes">
            <el-input v-model="ruleForm.notes" type="textarea" :rows="3" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="ruleDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="savingRule" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="publishDialog.visible" title="发布 Term Rule Set draft" width="640px">
      <el-alert
        v-if="preflightReport?.blocking"
        class="dialog-alert"
        type="error"
        title="当前 draft 存在 blocking preflight finding，不能发布。"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="preflightReport && preflightReport.summary.warning_count > 0"
        class="dialog-alert"
        type="warning"
        title="当前 draft 存在 warning，发布前请确认影响。"
        :closable="false"
        show-icon
      />
      <el-table
        v-if="preflightFindings.length"
        :data="preflightFindings"
        size="small"
        class="dialog-findings"
        max-height="220"
      >
        <el-table-column prop="severity" label="级别" width="90" />
        <el-table-column prop="code" label="Code" width="190" show-overflow-tooltip />
        <el-table-column prop="message" label="说明" min-width="220" show-overflow-tooltip />
      </el-table>
      <el-form ref="publishFormRef" :model="publishDialog.form" :rules="publishRules" label-width="100px">
        <el-form-item label="发布说明" prop="publish_reason">
          <el-input v-model="publishDialog.form.publish_reason" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="publishDialog.visible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="Boolean(preflightReport?.blocking)"
          :loading="publishing"
          @click="publishDraft"
        >
          发布并设默认
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { Delete, EditPen, Plus, Refresh, Search, Switch } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { termProposalsApi } from "@/api/termProposals";
import { termRulesApi } from "@/api/termRules";
import { termRuleSetsApi } from "@/api/termRuleSets";
import type {
  TermRuleCategoryListItemResponse,
  TermRuleGovernanceFindingResponse,
  TermRuleProposalResponse,
  TermRuleResponse,
  TermRuleSegmentWriteRequest,
  TermRuleSetDetailResponse,
  TermRuleSetDiffResponse,
  TermRuleSetDraftResponse,
  TermRuleSetListItemResponse,
  TermRuleSetPreflightResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import TermPreview from "@/components/TermPreview.vue";
import TermProposalTable from "@/components/TermProposalTable.vue";
import TermSegmentEditor from "@/components/TermSegmentEditor.vue";
import TerminologyWorkbenchNav from "@/components/TerminologyWorkbenchNav.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

type EnabledFilter = "all" | "enabled" | "disabled";
type RuleDialogMode = "create" | "edit";
type RuleDialogVariant = "basic" | "advanced";

type RuleFormState = {
  source_term: string;
  category_id: string;
  apply_scope: string;
  case_sensitive: boolean;
  enabled: boolean;
  priority: number;
  segments: TermRuleSegmentWriteRequest[];
  custom_html: string;
  custom_markdown: string;
  notes: string;
};

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
const publishFormRef = ref<FormInstance>();
const ruleFormRef = ref<FormInstance>();

const draftRuleFilters = reactive({
  page: 1,
  pageSize: 20,
  categoryId: "",
  enabled: "all" as EnabledFilter,
  keyword: "",
});

const ruleDialog = reactive({
  visible: false,
  mode: "create" as RuleDialogMode,
  variant: "basic" as RuleDialogVariant,
  ruleId: "",
});

const ruleForm = reactive<RuleFormState>(createEmptyRuleForm());

const publishDialog = reactive({
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
  if (!preflightReport.value) {
    return "未加载";
  }
  if (preflightReport.value.blocking) {
    return "Blocked";
  }
  if (preflightReport.value.summary.warning_count > 0) {
    return "Warnings";
  }
  return "Ready";
});

const preflightStatusType = computed(() => {
  if (!preflightReport.value) {
    return "info";
  }
  if (preflightReport.value.blocking) {
    return "danger";
  }
  if (preflightReport.value.summary.warning_count > 0) {
    return "warning";
  }
  return "success";
});

const preflightFindings = computed<TermRuleGovernanceFindingResponse[]>(() => {
  const report = preflightReport.value;
  if (!report) {
    return [];
  }
  return [...report.errors, ...report.warnings, ...report.conflicts];
});

const diffCounters = computed(() => {
  const summary = diffReport.value?.summary;
  return [
    { key: "added", label: "Added", value: summary?.added ?? 0 },
    { key: "updated", label: "Updated", value: summary?.updated ?? 0 },
    { key: "disabled", label: "Disabled", value: summary?.disabled ?? 0 },
    { key: "removed", label: "Removed", value: summary?.removed ?? 0 },
    { key: "unchanged", label: "Unchanged", value: summary?.unchanged ?? 0 },
  ];
});

// 创建新规则表单默认值。
function createEmptyRuleForm(variant: RuleDialogVariant = "basic"): RuleFormState {
  const segments: TermRuleSegmentWriteRequest[] =
    variant === "advanced"
      ? [
          { segment_text: "", render_type: "plain" },
          { segment_text: "", render_type: "subscript" },
          { segment_text: "", render_type: "superscript" },
        ]
      : [{ segment_text: "", render_type: "plain" }];
  return {
    source_term: "",
    category_id: "",
    apply_scope: "both",
    case_sensitive: true,
    enabled: true,
    priority: 100,
    segments,
    custom_html: "",
    custom_markdown: "",
    notes: "",
  };
}

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
  ruleDialog.variant = rule.segments.length > 2 || Boolean(rule.custom_html || rule.custom_markdown) ? "advanced" : "basic";
  ruleDialog.ruleId = rule.id;
  ruleDialog.visible = true;
}

// 校验 segment 内容，避免空片段提交到后端。
function validateSegments(): boolean {
  if (!ruleForm.segments.length || ruleForm.segments.some((segment) => !segment.segment_text.trim())) {
    ElMessage.error("请填写完整 segments。");
    return false;
  }
  return true;
}

// 组装 draft rule 写入 payload。
function buildRulePayload() {
  return {
    category_id: ruleForm.category_id,
    source_term: ruleForm.source_term.trim(),
    apply_scope: ruleForm.apply_scope,
    case_sensitive: ruleForm.case_sensitive,
    enabled: ruleForm.enabled,
    priority: ruleForm.priority,
    segments: ruleForm.segments.map((segment) => ({
      segment_text: segment.segment_text,
      render_type: segment.render_type,
    })),
    custom_html: ruleForm.custom_html.trim() || null,
    custom_markdown: ruleForm.custom_markdown.trim() || null,
    notes: ruleForm.notes,
  };
}

// 保存新增或编辑后的 draft rule。
async function saveRule(): Promise<void> {
  if (!selectedSetId.value || !validateSegments()) {
    return;
  }
  const valid = await ruleFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  savingRule.value = true;
  error.value = null;
  try {
    const response =
      ruleDialog.mode === "create"
        ? await termRuleSetsApi.createDraftRule(selectedSetId.value, buildRulePayload())
        : await termRuleSetsApi.updateDraftRule(selectedSetId.value, ruleDialog.ruleId, buildRulePayload());
    ElMessage.success(ruleDialog.mode === "create" ? "Draft rule 已新增。" : "Draft rule 已保存。");
    ruleDialog.visible = false;
    await refreshAfterDraftMutation(response.draft);
  } catch (caught) {
    error.value = normalizeApiError(caught);
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
      enabled: !rule.enabled,
    });
    ElMessage.success(rule.enabled ? "Draft rule 已停用。" : "Draft rule 已启用。");
    await refreshAfterDraftMutation(response.draft);
  } catch (caught) {
    error.value = normalizeApiError(caught);
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
    const response = await termRuleSetsApi.deleteDraftRule(selectedSetId.value, rule.id);
    ElMessage.success("Draft rule 已删除。");
    await refreshAfterDraftMutation(response.draft);
  } catch (caught) {
    error.value = normalizeApiError(caught);
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
  const valid = await publishFormRef.value?.validate().catch(() => false);
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
    const response = await termRuleSetsApi.updateDraft(selectedSetId.value, { yaml_text: yamlText.value });
    ElMessage.success("YAML draft 已保存。");
    await refreshAfterDraftMutation(response);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    savingYaml.value = false;
  }
}

// 返回 diff change type 的中文标签。
function changeTypeLabel(changeType: string): string {
  const labels: Record<string, string> = {
    added: "新增",
    updated: "更新",
    disabled: "停用",
    removed: "移除",
    unchanged: "未变",
  };
  return labels[changeType] || changeType;
}

// 返回 diff change type 对应的 Element Plus tag 类型。
function changeTypeTagType(changeType: string): "success" | "warning" | "danger" | "info" | "primary" {
  if (changeType === "added") {
    return "success";
  }
  if (changeType === "updated") {
    return "primary";
  }
  if (changeType === "disabled") {
    return "warning";
  }
  if (changeType === "removed") {
    return "danger";
  }
  return "info";
}

// 返回 preflight finding 对应的 Element Plus tag 类型。
function findingTagType(severity: string): "success" | "warning" | "danger" | "info" | "primary" {
  if (severity === "error" || severity === "conflict") {
    return "danger";
  }
  if (severity === "warning") {
    return "warning";
  }
  return "info";
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

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  margin-bottom: var(--app-space-3);
}

.rule-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  justify-content: flex-end;
}

.filter-select {
  width: 180px;
}

.keyword-input {
  width: min(320px, 100%);
}

.rule-table {
  width: 100%;
}

.table-pagination {
  justify-content: flex-end;
  margin-top: 12px;
}

.diff-counter {
  min-height: 62px;
}

.diff-counter span {
  display: block;
}

.diff-counter strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
}

.rule-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: var(--app-space-4);
}

:global(.rule-dialog) {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 48px);
  max-height: calc(100dvh - 48px);
  margin-bottom: 24px;
}

:global(.rule-dialog .el-dialog__header),
:global(.rule-dialog .el-dialog__footer) {
  flex: 0 0 auto;
}

:global(.rule-dialog .el-dialog__body) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.rule-dialog-scroll {
  max-height: min(640px, calc(100vh - 220px));
  max-height: min(640px, calc(100dvh - 220px));
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
}

.dialog-alert,
.dialog-findings,
.yaml-warning,
.yaml-save {
  margin-top: 12px;
}

.yaml-warning {
  margin-bottom: 12px;
}

@media (max-width: 1120px) {
  .rule-set-grid,
  .diff-summary {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .filters,
  .rule-form-grid {
    grid-template-columns: 1fr;
  }

  .filter-select,
  .keyword-input {
    width: 100%;
  }
}
</style>
