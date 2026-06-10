<!-- File: frontend/src/pages/TranslationTermSetPage.vue -->
<!-- Purpose: Provide the Admin Translation Term Set CSV import, export, default switching, and rollback page. -->
<template>
  <main class="translation-term-set-page" aria-labelledby="translation-term-set-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Translation Term Set</p>
        <h1 id="translation-term-set-title">翻译术语集</h1>
        <p>通过 CSV 管理 draft，查看版本并执行发布、设默认和回滚。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </section>

    <ApiErrorAlert :error="error" />
    <el-alert
      v-if="errorActionHint"
      class="context-alert"
      type="info"
      :title="errorActionHint"
      :closable="false"
      show-icon
    />
    <el-alert
      v-if="proposalGovernanceContext"
      class="context-alert governance-context-alert"
      type="info"
      :closable="false"
      show-icon
    >
      <template #title>
        <span>Proposal 治理上下文</span>
      </template>
      <div class="context-summary">
        <el-tag effect="plain">proposal: {{ proposalGovernanceContext.proposalId }}</el-tag>
        <el-tag effect="plain">set: {{ proposalGovernanceContext.setId || "-" }}</el-tag>
        <el-tag effect="plain">observed: {{ proposalGovernanceContext.observedVersion || "-" }}</el-tag>
        <el-button link type="primary" @click="returnToProposalReview">返回 proposal 审核页</el-button>
      </div>
    </el-alert>

    <el-alert
      v-if="unavailable"
      type="warning"
      title="当前部署未启用 MySQL resource service，Translation Term Set 管理不可用。"
      :closable="false"
      show-icon
    />

    <section v-else class="term-set-grid">
      <el-card class="card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">术语集</h2>
            <p class="section-subtitle">选择 set 查看 draft 和 published versions。</p>
          </div>
        </div>
        <el-table :data="sets" :loading="loading" empty-text="暂无 Translation Term Set" @row-click="selectSet">
          <el-table-column prop="set_id" label="set_id" min-width="210" show-overflow-tooltip />
          <el-table-column prop="language_pair" label="语言方向" width="110" />
          <el-table-column prop="default_version" label="默认版本" width="150" show-overflow-tooltip />
          <el-table-column prop="version_count" label="版本数" width="90" />
        </el-table>
      </el-card>

      <el-card class="card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Draft 摘要</h2>
            <p class="section-subtitle">CSV 导入是本阶段唯一 draft 修改入口。</p>
          </div>
          <el-tag v-if="draft?.snapshot_hash" class="mono" effect="plain">{{ draft.snapshot_hash }}</el-tag>
        </div>
        <el-empty v-if="!selectedSetId" description="请选择术语集" :image-size="90" />
        <template v-else>
          <dl class="summary-list">
            <div><dt>base version</dt><dd>{{ draft?.base_version || "-" }}</dd></div>
            <div><dt>term_count</dt><dd>{{ draft?.term_count ?? "-" }}</dd></div>
            <div><dt>validation</dt><dd>{{ draft?.validation.valid ? "valid" : "invalid" }}</dd></div>
          </dl>
          <RoleGate>
            <div class="action-row">
              <el-button type="primary" :disabled="!selectedSetId" @click="openImportDialog">导入 CSV</el-button>
              <el-button type="success" :disabled="!selectedSetId" @click="openPublishDialog">发布 draft</el-button>
              <el-button :disabled="!selectedSetId" @click="exportVersion(null)">导出默认 CSV</el-button>
            </div>
          </RoleGate>
        </template>
      </el-card>
    </section>

    <el-card v-if="!unavailable && lastImportReport" class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">最近一次 CSV 导入</h2>
          <p class="section-subtitle">{{ importReportSummary }}</p>
        </div>
        <el-tag effect="plain">dedupe={{ lastImportReport.dedupe }}</el-tag>
      </div>
      <el-table
        :data="lastImportReport.duplicates"
        empty-text="本次导入没有重复项"
        class="import-report-table"
      >
        <el-table-column prop="row_number" label="重复行" width="100" />
        <el-table-column prop="kept_row_number" label="保留行" width="100" />
        <el-table-column prop="source_term" label="source_term" min-width="180" show-overflow-tooltip />
        <el-table-column prop="normalized_source_term" label="normalized" min-width="180" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Draft validation</h2>
          <p class="section-subtitle">errors 会阻断发布，warnings 作为发布前提示。</p>
        </div>
      </div>
      <el-table :data="validationFindings" :loading="loading" empty-text="暂无 validation findings">
        <el-table-column prop="level" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="row.level === 'error' ? 'danger' : 'warning'" effect="plain">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="code" width="220" show-overflow-tooltip />
        <el-table-column prop="normalized_source_term" label="normalized_source_term" width="220" show-overflow-tooltip />
        <el-table-column prop="message" label="message" min-width="260" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Diff / Preflight</h2>
          <p class="section-subtitle">default-vs-draft 的只读治理预览，不会发布或修改 draft。</p>
        </div>
        <el-tag v-if="diff" effect="plain">{{ diff.base_version }} -> {{ diff.target_version }}</el-tag>
      </div>

      <div class="governance-summary-grid" aria-label="Translation Term Set diff summary">
        <article class="summary-metric">
          <span>Added</span>
          <strong>{{ diff?.summary.added ?? "-" }}</strong>
        </article>
        <article class="summary-metric">
          <span>Removed</span>
          <strong>{{ diff?.summary.removed ?? "-" }}</strong>
        </article>
        <article class="summary-metric">
          <span>Changed</span>
          <strong>{{ diff?.summary.changed ?? "-" }}</strong>
        </article>
        <article class="summary-metric">
          <span>Unchanged</span>
          <strong>{{ diff?.summary.unchanged ?? "-" }}</strong>
        </article>
      </div>

      <el-alert
        v-if="preflight?.publish_blocked"
        class="context-alert"
        type="error"
        title="Preflight 阻断发布"
        :closable="false"
        show-icon
      >
        <ul class="blocking-list">
          <li v-for="reason in preflight.blocking_reasons" :key="reason">{{ reason }}</li>
        </ul>
      </el-alert>
      <el-alert
        v-else-if="preflight"
        class="context-alert"
        type="success"
        title="Preflight 未发现阻断项"
        :closable="false"
        show-icon
      />

      <el-table :data="visibleDiffItems" :loading="loading" empty-text="暂无 draft diff 变化">
        <el-table-column label="Kind" width="110">
          <template #default="{ row }">
            <el-tag :type="diffKindTag(row.kind)" effect="plain">{{ row.kind }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_term" label="source_term" min-width="160" show-overflow-tooltip />
        <el-table-column prop="normalized_source_term" label="normalized" min-width="170" show-overflow-tooltip />
        <el-table-column label="changed_fields" min-width="220">
          <template #default="{ row }">
            <span v-if="!row.changed_fields.length" class="muted">-</span>
            <span v-else class="tag-stack">
              <el-tag v-for="field in row.changed_fields" :key="field" size="small" effect="plain">{{ field }}</el-tag>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="before" min-width="260">
          <template #default="{ row }">
            <pre class="diff-payload">{{ formatDiffPayload(row.before) }}</pre>
          </template>
        </el-table-column>
        <el-table-column label="after" min-width="260">
          <template #default="{ row }">
            <pre class="diff-payload">{{ formatDiffPayload(row.after) }}</pre>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Pending proposal compatibility</h2>
          <p class="section-subtitle">只读预览 pending proposals 与当前 draft 的兼容性。</p>
        </div>
      </div>

      <div class="governance-summary-grid" aria-label="Translation Term Proposal compatibility summary">
        <article class="summary-metric">
          <span>Total</span>
          <strong>{{ proposalCompatibility?.summary.total ?? "-" }}</strong>
        </article>
        <article class="summary-metric">
          <span>Compatible</span>
          <strong>{{ proposalCompatibility?.summary.compatible ?? "-" }}</strong>
        </article>
        <article class="summary-metric">
          <span>Warnings</span>
          <strong>{{ proposalCompatibility?.summary.warning ?? "-" }}</strong>
        </article>
        <article class="summary-metric">
          <span>Conflicts</span>
          <strong>{{ proposalCompatibility?.summary.conflict ?? "-" }}</strong>
        </article>
      </div>

      <el-alert
        v-if="proposalCompatibilityNotice"
        class="context-alert"
        type="warning"
        :title="proposalCompatibilityNotice"
        :closable="false"
        show-icon
      />
      <el-table
        :data="proposalCompatibility?.items || []"
        :loading="loading"
        empty-text="暂无 pending Translation Term Proposal"
        :row-class-name="proposalCompatibilityRowClassName"
      >
        <el-table-column prop="proposal_id" label="Proposal" min-width="160">
          <template #default="{ row }">
            <router-link :to="{ name: 'term-proposals', query: { tab: 'translation-review', proposal_id: row.proposal_id } }" class="mono">
              {{ row.proposal_id }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column label="Compatibility" width="140">
          <template #default="{ row }">
            <el-tag :type="compatibilityTag(row.compatibility)" effect="plain">{{ row.compatibility }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="observed_version" label="Observed" min-width="150" show-overflow-tooltip />
        <el-table-column prop="change_count" label="Changes" width="100" />
        <el-table-column label="Conflicts" min-width="220">
          <template #default="{ row }">{{ findingCodes(row.conflicts) }}</template>
        </el-table-column>
        <el-table-column label="Warnings" min-width="220">
          <template #default="{ row }">{{ findingCodes(row.warnings) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Published versions</h2>
          <p class="section-subtitle">rollback 只切默认指针，不生成新版本。</p>
        </div>
      </div>
      <el-table :data="detail?.versions || []" :loading="loading" empty-text="暂无 published version">
        <el-table-column prop="version" label="版本" width="170" show-overflow-tooltip />
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
        <el-table-column prop="term_count" label="术语数" width="90" />
        <el-table-column prop="snapshot_hash" label="snapshot" min-width="210" show-overflow-tooltip />
        <el-table-column label="发布时间" width="190">
          <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column prop="published_by" label="发布人" width="120" />
        <el-table-column prop="release_note" label="发布说明" min-width="180" show-overflow-tooltip />
        <el-table-column v-if="isAdmin" label="admin 操作" width="260" fixed="right">
          <template #default="{ row }">
            <RoleGate>
              <el-button link type="primary" @click="exportVersion(row.version)">导出</el-button>
              <el-button link type="warning" :disabled="row.is_default" @click="setDefault(row.version)">设默认</el-button>
              <el-button link type="danger" :disabled="row.is_default" @click="rollback(row.version)">Rollback</el-button>
            </RoleGate>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Draft entries</h2>
          <p class="section-subtitle">逐行维护当前 draft；发布后才会影响后续新任务的默认术语版本。</p>
        </div>
        <RoleGate>
          <el-button type="primary" :icon="Plus" :disabled="!selectedSetId" @click="openAddTermDialog">新增术语</el-button>
        </RoleGate>
      </div>
      <el-table :data="draft?.entries || []" :loading="loading" empty-text="暂无 draft entries">
        <el-table-column prop="source_term" label="source_term" min-width="180" show-overflow-tooltip />
        <el-table-column prop="target_term" label="target_term" min-width="180" show-overflow-tooltip />
        <el-table-column prop="normalized_source_term" label="normalized" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status" label="status" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="case_sensitive" label="case" width="90">
          <template #default="{ row }">{{ row.case_sensitive ? "sensitive" : "ignore" }}</template>
        </el-table-column>
        <el-table-column prop="priority" label="priority" width="90" />
        <el-table-column prop="domain" label="domain" width="140" show-overflow-tooltip />
        <el-table-column prop="category" label="category" width="140" show-overflow-tooltip />
        <el-table-column prop="note" label="note" min-width="160" show-overflow-tooltip />
        <el-table-column v-if="isAdmin" label="admin 操作" width="240" fixed="right">
          <template #default="{ row }">
            <RoleGate>
              <div class="table-actions">
                <el-button link type="primary" :icon="Edit" @click="openEditTermDialog(row)">编辑</el-button>
                <el-button
                  link
                  type="warning"
                  :icon="CircleClose"
                  :disabled="row.status === 'disabled'"
                  @click="disableDraftEntry(row)"
                >
                  禁用
                </el-button>
                <el-button link type="danger" :icon="Delete" @click="deleteDraftEntry(row)">删除</el-button>
              </div>
            </RoleGate>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="importDialog.visible" title="导入 Translation Term CSV" width="720px">
      <el-form ref="importFormRef" :model="importDialog.form" :rules="importRules" label-width="90px">
        <el-form-item label="dedupe" prop="dedupe">
          <el-segmented v-model="importDialog.form.dedupe" :options="dedupeOptions" />
          <p class="form-help">{{ dedupeHint }}</p>
        </el-form-item>
        <el-form-item label="CSV" prop="csv_text">
          <el-input
            v-model="importDialog.form.csv_text"
            type="textarea"
            :rows="12"
            class="mono"
            placeholder="language_pair,source_term,target_term,version"
          />
        </el-form-item>
      </el-form>
      <el-alert
        v-if="lastImportReport"
        class="dialog-alert"
        type="success"
        :title="importReportSummary"
        :closable="false"
        show-icon
      />
      <template #footer>
        <el-button @click="importDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="importCsv">导入到 draft</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="entryDialog.visible" :title="entryDialogTitle" width="720px">
      <el-form ref="entryFormRef" :model="entryDialog.form" :rules="entryRules" label-width="120px">
        <div class="entry-form-grid">
          <el-form-item label="source_term" prop="source_term">
            <el-input
              v-model="entryDialog.form.source_term"
              class="mono"
              :readonly="entryDialog.mode === 'edit'"
              :disabled="entryDialog.mode === 'edit'"
            />
          </el-form-item>
          <el-form-item label="target_term" prop="target_term">
            <el-input v-model="entryDialog.form.target_term" class="mono" />
          </el-form-item>
          <el-form-item label="case_sensitive">
            <el-switch v-model="entryDialog.form.case_sensitive" />
          </el-form-item>
          <el-form-item label="status" prop="status">
            <el-segmented v-model="entryDialog.form.status" :options="termStatusOptions" />
          </el-form-item>
          <el-form-item label="priority">
            <el-input-number v-model="entryDialog.form.priority" :min="-1000" :max="1000" controls-position="right" />
          </el-form-item>
          <el-form-item label="domain">
            <el-input v-model="entryDialog.form.domain" />
          </el-form-item>
          <el-form-item label="category">
            <el-input v-model="entryDialog.form.category" />
          </el-form-item>
          <el-form-item label="note">
            <el-input v-model="entryDialog.form.note" type="textarea" :rows="3" />
          </el-form-item>
        </div>
      </el-form>
      <el-alert
        v-if="draft?.snapshot_hash"
        class="dialog-alert"
        type="info"
        :title="`基于当前 draft snapshot: ${draft.snapshot_hash}`"
        :closable="false"
        show-icon
      />
      <template #footer>
        <el-button @click="entryDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="entrySaving" @click="submitDraftEntry">保存到 draft</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="publishDialog.visible" title="发布 Translation Term Set draft" width="540px">
      <el-form ref="publishFormRef" :model="publishDialog.form" :rules="publishRules" label-width="100px">
        <el-form-item label="发布说明" prop="release_note">
          <el-input v-model="publishDialog.form.release_note" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="publishDialog.form.make_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="publishDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="publishing" @click="publishDraft">发布</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportDialog.visible" title="导出 Translation Term CSV" width="760px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="set_id">{{ exportDialog.manifest?.set_id || "-" }}</el-descriptions-item>
        <el-descriptions-item label="version">{{ exportDialog.manifest?.version || "-" }}</el-descriptions-item>
        <el-descriptions-item label="language_pair">{{ exportDialog.manifest?.language_pair || "-" }}</el-descriptions-item>
        <el-descriptions-item label="exported_by">{{ exportDialog.manifest?.exported_by || "-" }}</el-descriptions-item>
      </el-descriptions>
      <el-input v-model="exportDialog.csv_text" type="textarea" :rows="14" class="mono export-text" readonly />
      <template #footer>
        <el-button @click="copyExport">复制 CSV</el-button>
        <el-button type="primary" @click="downloadExport">下载 CSV</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { CircleClose, Delete, Edit, Plus, Refresh } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { translationTermSetsApi } from "@/api/translationTermSets";
import type {
  TranslationTermEntryResponse,
  TranslationTermProposalCompatibilityFindingResponse,
  TranslationTermProposalCompatibilityItemResponse,
  TranslationTermProposalCompatibilityResponse,
  TranslationTermSetDraftChangeRequest,
  TranslationTermSetDetailResponse,
  TranslationTermSetDiffEntryPayload,
  TranslationTermSetDiffEntryResponse,
  TranslationTermSetDiffResponse,
  TranslationTermSetDraftResponse,
  TranslationTermSetExportManifestResponse,
  TranslationTermSetImportReportResponse,
  TranslationTermSetListItemResponse,
  TranslationTermSetPreflightResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

type FindingRow = {
  level: "error" | "warning";
  code: string;
  message: string;
  normalized_source_term: string | null;
};

type DedupeMode = "reject" | "keep_first";
type DiffKind = TranslationTermSetDiffEntryResponse["kind"];
type Compatibility = TranslationTermProposalCompatibilityItemResponse["compatibility"];
type TagType = "success" | "warning" | "info" | "danger";
type EntryDialogMode = "add" | "edit";
type TermStatus = "active" | "disabled";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const isAdmin = computed(() => auth.user?.role === "admin");
const sets = ref<TranslationTermSetListItemResponse[]>([]);
const selectedSetId = ref("");
const detail = ref<TranslationTermSetDetailResponse | null>(null);
const draft = ref<TranslationTermSetDraftResponse | null>(null);
const diff = ref<TranslationTermSetDiffResponse | null>(null);
const preflight = ref<TranslationTermSetPreflightResponse | null>(null);
const proposalCompatibility = ref<TranslationTermProposalCompatibilityResponse | null>(null);
const loading = ref(false);
const unavailable = ref(false);
const importing = ref(false);
const publishing = ref(false);
const entrySaving = ref(false);
const error = ref<ApiClientError | null>(null);
const lastImportReport = ref<TranslationTermSetImportReportResponse | null>(null);
const importFormRef = ref<FormInstance>();
const publishFormRef = ref<FormInstance>();
const entryFormRef = ref<FormInstance>();

const dedupeOptions = [
  { label: "reject", value: "reject" },
  { label: "keep_first", value: "keep_first" },
];

const termStatusOptions = [
  { label: "active", value: "active" },
  { label: "disabled", value: "disabled" },
];

const importDialog = reactive({
  visible: false,
  form: {
    csv_text: "",
    dedupe: "reject" as DedupeMode,
  },
});

const publishDialog = reactive({
  visible: false,
  form: {
    make_default: true,
    release_note: "",
  },
});

const entryDialog = reactive({
  visible: false,
  mode: "add" as EntryDialogMode,
  form: {
    source_term: "",
    target_term: "",
    case_sensitive: false,
    status: "active" as TermStatus,
    priority: 0,
    domain: "",
    category: "",
    note: "",
  },
});

const exportDialog = reactive({
  visible: false,
  manifest: null as TranslationTermSetExportManifestResponse | null,
  csv_text: "",
});

const importRules: FormRules = {
  csv_text: [{ required: true, message: "请粘贴 CSV 内容", trigger: "blur" }],
};

const publishRules: FormRules = {
  release_note: [{ required: true, message: "请填写发布说明", trigger: "blur" }],
};

const entryRules: FormRules = {
  source_term: [{ required: true, message: "请填写 source_term", trigger: "blur" }],
  target_term: [{ required: true, message: "请填写 target_term", trigger: "blur" }],
  status: [{ required: true, message: "请选择 status", trigger: "change" }],
};

const dedupeHints: Record<DedupeMode, string> = {
  reject: "默认策略。只要 CSV 存在重复 normalized_source_term，后端会拒绝导入，draft 不会保存。",
  keep_first: "治理导入策略。保留第一条重复术语，丢弃后续重复行，并在导入报告中列出被丢弃的行。",
};

const dedupeHint = computed(() => dedupeHints[importDialog.form.dedupe]);
const entryDialogTitle = computed(() => (entryDialog.mode === "add" ? "新增 draft 术语" : "编辑 draft 术语"));

const proposalGovernanceContext = computed(() => {
  const proposalId = queryString("proposal_id");
  if (!proposalId) {
    return null;
  }
  return {
    proposalId,
    setId: queryString("set_id"),
    observedVersion: queryString("observed_version"),
    returnTab: queryString("return_tab") || "translation-review",
  };
});

const importReportSummary = computed(() => {
  const report = lastImportReport.value;
  if (!report) {
    return "";
  }
  return `总行数 ${report.total_rows}，导入 ${report.imported_rows} 行，重复 ${report.duplicate_rows} 行。`;
});

const validationFindings = computed<FindingRow[]>(() => {
  const report = draft.value?.validation;
  if (!report) {
    return [];
  }
  return [
    ...report.errors.map((item) => ({ ...item, level: "error" as const })),
    ...report.warnings.map((item) => ({ ...item, level: "warning" as const })),
  ];
});

const visibleDiffItems = computed(() => (
  diff.value?.items.filter((item) => item.kind !== "unchanged") ?? []
));

const targetProposalCompatibility = computed(() => {
  const proposalId = proposalGovernanceContext.value?.proposalId;
  if (!proposalId) {
    return null;
  }
  return proposalCompatibility.value?.items.find((item) => item.proposal_id === proposalId) || null;
});

const proposalCompatibilityNotice = computed(() => {
  const proposalId = proposalGovernanceContext.value?.proposalId;
  if (!proposalId || loading.value || targetProposalCompatibility.value) {
    return "";
  }
  return `proposal ${proposalId} 当前不在 pending compatibility 列表中；可能已审核、已发布、已拒绝，或当前 set 不匹配。`;
});

// 根据 Translation Term Set 页面语境给 Admin 提供下一步处理建议。
const errorActionHint = computed(() => {
  const currentError = error.value;
  if (!currentError) {
    return "";
  }
  if (currentError.status === 503) {
    return "当前部署未启用 MySQL resource service，本页面不会保存任何 Translation Term Set 变更。";
  }
  if (currentError.status === 404) {
    return "目标 set 或 version 不存在。请刷新术语集列表后确认版本仍可用。";
  }
  if (currentError.status === 409 && currentError.code === "draft_snapshot_conflict") {
    return "draft 已被其他修改更新，本页面已刷新当前 set。请重新确认后再保存。";
  }
  if (currentError.status === 400 && /CSV|重复|dedupe|language_pair|字段/.test(currentError.message)) {
    return "CSV 未导入，draft 未保存。请按错误信息修正 CSV，或在确认可丢弃重复行后改用 keep_first。";
  }
  if (currentError.status === 400 && /draft|术语|source_term|target_term|changes|新增|目标|状态/.test(currentError.message)) {
    return "draft 行级修改未保存。请按错误信息修正表单后重试。";
  }
  if (currentError.status === 400) {
    return "操作未执行。请确认目标版本是 published 状态，且请求参数符合当前 API 合同。";
  }
  return "";
});

// 记录页面级 API 错误，并在 503 时切到不可用状态。
function setPageError(caught: unknown): void {
  const normalized = normalizeApiError(caught);
  if (normalized.status === 503) {
    unavailable.value = true;
  }
  error.value = normalized;
}

function queryString(key: string): string {
  const value = route.query[key];
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

// 加载 set 列表和当前选中 set 的详情。
async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  unavailable.value = false;
  try {
    const response = await translationTermSetsApi.list();
    sets.value = response.items;
    selectedSetId.value = queryString("set_id") || selectedSetId.value || sets.value[0]?.set_id || "";
    if (selectedSetId.value) {
      await loadSelectedSet();
    }
  } catch (caught) {
    setPageError(caught);
  } finally {
    loading.value = false;
  }
}

// 切换当前管理的 Translation Term Set，并清空旧 set 的导入报告。
async function selectSet(row: TranslationTermSetListItemResponse): Promise<void> {
  selectedSetId.value = row.set_id;
  lastImportReport.value = null;
  error.value = null;
  try {
    await loadSelectedSet();
  } catch (caught) {
    setPageError(caught);
  }
}

// 加载当前 set 的详情和 draft 预览。
async function loadSelectedSet(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const [
    detailResponse,
    draftResponse,
    diffResponse,
    preflightResponse,
    proposalCompatibilityResponse,
  ] = await Promise.all([
    translationTermSetsApi.get(selectedSetId.value),
    translationTermSetsApi.getDraft(selectedSetId.value),
    translationTermSetsApi.getDiff(selectedSetId.value),
    translationTermSetsApi.getPreflight(selectedSetId.value),
    translationTermSetsApi.getProposalCompatibility(selectedSetId.value),
  ]);
  detail.value = detailResponse;
  draft.value = draftResponse;
  diff.value = diffResponse;
  preflight.value = preflightResponse;
  proposalCompatibility.value = proposalCompatibilityResponse;
}

// 打开 CSV 导入对话框，并重置导入策略为安全的 reject。
function openImportDialog(): void {
  importDialog.form.csv_text = "";
  importDialog.form.dedupe = "reject";
  lastImportReport.value = null;
  importDialog.visible = true;
}

// 将 CSV 导入 draft；失败时保留后端错误并提示 draft 未保存。
async function importCsv(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const valid = await importFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  importing.value = true;
  error.value = null;
  try {
    const response = await translationTermSetsApi.importCsv(selectedSetId.value, {
      csv_text: importDialog.form.csv_text,
      target: "draft",
      dedupe: importDialog.form.dedupe,
    });
    lastImportReport.value = response.import_report;
    ElMessage.success("CSV 已导入 draft。");
    await loadAll();
  } catch (caught) {
    setPageError(caught);
  } finally {
    importing.value = false;
  }
}

function optionalText(value: string): string | null {
  const normalized = value.trim();
  return normalized || null;
}

function resetEntryForm(): void {
  entryDialog.form.source_term = "";
  entryDialog.form.target_term = "";
  entryDialog.form.case_sensitive = false;
  entryDialog.form.status = "active";
  entryDialog.form.priority = 0;
  entryDialog.form.domain = "";
  entryDialog.form.category = "";
  entryDialog.form.note = "";
}

function openAddTermDialog(): void {
  resetEntryForm();
  entryDialog.mode = "add";
  entryDialog.visible = true;
}

function openEditTermDialog(row: TranslationTermEntryResponse): void {
  entryDialog.mode = "edit";
  entryDialog.form.source_term = row.source_term;
  entryDialog.form.target_term = row.target_term;
  entryDialog.form.case_sensitive = row.case_sensitive;
  entryDialog.form.status = row.status === "disabled" ? "disabled" : "active";
  entryDialog.form.priority = row.priority;
  entryDialog.form.domain = row.domain || "";
  entryDialog.form.category = row.category || "";
  entryDialog.form.note = row.note || "";
  entryDialog.visible = true;
}

async function applyDraftEntryChanges(changes: TranslationTermSetDraftChangeRequest[], reason: string): Promise<void> {
  if (!selectedSetId.value || !draft.value?.snapshot_hash) {
    return;
  }
  await translationTermSetsApi.applyDraftChanges(selectedSetId.value, {
    expected_snapshot_hash: draft.value.snapshot_hash,
    reason,
    changes,
  });
  await loadSelectedSet();
}

async function handleDraftChangeError(caught: unknown): Promise<void> {
  const normalized = normalizeApiError(caught);
  if (normalized.status === 503) {
    unavailable.value = true;
  }
  error.value = normalized;
  if (normalized.status === 409 && normalized.code === "draft_snapshot_conflict") {
    ElMessage.warning("draft 已被其他修改更新，已刷新当前 set。");
    try {
      await loadSelectedSet();
    } catch (refreshError) {
      setPageError(refreshError);
    }
  }
}

async function submitDraftEntry(): Promise<void> {
  const valid = await entryFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  entrySaving.value = true;
  error.value = null;
  const change: TranslationTermSetDraftChangeRequest = {
    action: entryDialog.mode === "add" ? "add" : "update",
    source_term: entryDialog.form.source_term,
    target_term: entryDialog.form.target_term,
    case_sensitive: entryDialog.form.case_sensitive,
    status: entryDialog.form.status,
    priority: entryDialog.form.priority,
    domain: optionalText(entryDialog.form.domain),
    category: optionalText(entryDialog.form.category),
    note: entryDialog.form.note.trim(),
  };
  try {
    await applyDraftEntryChanges([change], `${change.action} ${change.source_term}`);
    ElMessage.success("draft 术语已保存。");
    entryDialog.visible = false;
  } catch (caught) {
    await handleDraftChangeError(caught);
  } finally {
    entrySaving.value = false;
  }
}

async function disableDraftEntry(row: TranslationTermEntryResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将 ${row.source_term} 标记为 disabled。术语仍保留在 draft 中，但发布后不参与匹配。`,
      "禁用 draft 术语",
      {
        confirmButtonText: "禁用",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  error.value = null;
  try {
    await applyDraftEntryChanges(
      [
        {
          action: "update",
          source_term: row.source_term,
          status: "disabled",
        },
      ],
      `disable ${row.source_term}`,
    );
    ElMessage.success("draft 术语已禁用。");
  } catch (caught) {
    await handleDraftChangeError(caught);
  }
}

async function deleteDraftEntry(row: TranslationTermEntryResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `从当前 draft 移除 ${row.source_term}。此操作不会删除任何 published history，只有发布 draft 后才会影响后续新任务。`,
      "删除 draft 术语",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  error.value = null;
  try {
    await applyDraftEntryChanges(
      [
        {
          action: "delete",
          source_term: row.source_term,
        },
      ],
      `delete ${row.source_term}`,
    );
    ElMessage.success("draft 术语已删除。");
  } catch (caught) {
    await handleDraftChangeError(caught);
  }
}

// 打开发布 draft 对话框，要求填写发布说明。
function openPublishDialog(): void {
  publishDialog.form.release_note = "";
  publishDialog.form.make_default = true;
  publishDialog.visible = true;
}

// 发布当前 draft，并按开关决定是否设为默认版本。
async function publishDraft(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const valid = await publishFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  publishing.value = true;
  error.value = null;
  try {
    await translationTermSetsApi.publish(selectedSetId.value, {
      make_default: publishDialog.form.make_default,
      release_note: publishDialog.form.release_note,
    });
    ElMessage.success("Translation Term Set draft 已发布。");
    publishDialog.visible = false;
    await loadAll();
  } catch (caught) {
    setPageError(caught);
  } finally {
    publishing.value = false;
  }
}

// 导出默认版本或指定 published version 的 CSV。
async function exportVersion(version: string | null): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  error.value = null;
  try {
    const response = await translationTermSetsApi.exportCsv(selectedSetId.value, version);
    exportDialog.manifest = response.manifest;
    exportDialog.csv_text = response.csv_text;
    exportDialog.visible = true;
  } catch (caught) {
    setPageError(caught);
  }
}

// 将导出的 CSV 正文复制到剪贴板。
async function copyExport(): Promise<void> {
  if (!exportDialog.csv_text) {
    return;
  }
  await navigator.clipboard.writeText(exportDialog.csv_text);
  ElMessage.success("CSV 已复制。");
}

// 在浏览器侧下载导出的 CSV，不触发后端文件删除或文件管理。
function downloadExport(): void {
  if (!exportDialog.csv_text || !exportDialog.manifest) {
    return;
  }
  const blob = new Blob([exportDialog.csv_text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${exportDialog.manifest.set_id}-${exportDialog.manifest.version}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

// 将 diff payload 压缩为页面内可扫描 JSON。
function formatDiffPayload(payload: TranslationTermSetDiffEntryPayload | null): string {
  return payload ? JSON.stringify(payload, null, 2) : "-";
}

// 将 diff kind 映射为表格标签样式。
function diffKindTag(kind: DiffKind): TagType {
  if (kind === "added") {
    return "success";
  }
  if (kind === "removed") {
    return "danger";
  }
  if (kind === "changed") {
    return "warning";
  }
  return "info";
}

// 将 proposal compatibility 映射为表格标签样式。
function compatibilityTag(compatibility: Compatibility): TagType {
  if (compatibility === "compatible") {
    return "success";
  }
  if (compatibility === "warning") {
    return "warning";
  }
  return "danger";
}

// 汇总 finding codes，避免在列表中渲染大段冲突 payload。
function findingCodes(findings: TranslationTermProposalCompatibilityFindingResponse[]): string {
  return findings.length ? findings.map((item) => item.code).join(", ") : "-";
}

// 高亮从 proposal 审核页跳转而来的 compatibility 行，找不到时由页面提示说明。
function proposalCompatibilityRowClassName({ row }: { row: TranslationTermProposalCompatibilityItemResponse }): string {
  return row.proposal_id === proposalGovernanceContext.value?.proposalId ? "is-selected-row" : "";
}

// 返回 Translation proposal 审核页，保持 proposal_id deep-link。
function returnToProposalReview(): void {
  const context = proposalGovernanceContext.value;
  if (!context) {
    return;
  }
  void router.push({
    name: "term-proposals",
    query: {
      tab: context.returnTab,
      proposal_id: context.proposalId,
    },
  });
}

// 切换默认指针；只影响后续默认绑定，不改已有 job 快照。
async function setDefault(version: string): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "将该 published version 切换为默认翻译术语集版本。此操作只影响后续使用默认配置的新 job；已创建 job 的 resource snapshot 不会改变。",
      `设默认 ${version}`,
      {
        confirmButtonText: "设默认",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  error.value = null;
  try {
    await translationTermSetsApi.setDefault(selectedSetId.value, version);
    ElMessage.success("默认翻译术语集已切换。");
    await loadAll();
  } catch (caught) {
    setPageError(caught);
  }
}

// Rollback 只切默认指针，不生成新版本、不删除历史版本、不改已有 job 快照。
async function rollback(version: string): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "Rollback 只会把默认版本指针切回该 published version，不会生成新版本，不会删除或修改历史版本，也不会改变已创建 job 的 resource snapshot。",
      `Rollback ${version}`,
      {
        confirmButtonText: "Rollback",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  error.value = null;
  try {
    await translationTermSetsApi.rollback(selectedSetId.value, { version });
    ElMessage.success("已完成 rollback。");
    await loadAll();
  } catch (caught) {
    setPageError(caught);
  }
}

watch(() => route.fullPath, () => {
  void loadAll();
}, { immediate: true });
</script>

<style scoped lang="scss">
.translation-term-set-page {
  display: grid;
  gap: 16px;
}

.term-set-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(340px, 0.9fr);
  gap: 16px;
}

.summary-list {
  display: grid;
  gap: 10px;
  margin: 0 0 16px;
}

.summary-list div {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  gap: 10px;
}

.summary-list dt {
  color: #667085;
}

.summary-list dd {
  min-width: 0;
  margin: 0;
  color: #111827;
  overflow-wrap: anywhere;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.context-alert {
  margin-bottom: 4px;
}

.context-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.governance-context-alert {
  border-left: 4px solid #2563eb;
}

.governance-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.summary-metric {
  min-width: 0;
  padding: 12px;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  background: #fff;
}

.summary-metric span {
  display: block;
  color: #667085;
  font-size: 12px;
}

.summary-metric strong {
  display: block;
  margin-top: 4px;
  color: #111827;
  font-size: 24px;
  line-height: 1.2;
}

.blocking-list {
  margin: 0;
  padding-left: 18px;
}

.tag-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.table-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.diff-payload {
  max-height: 140px;
  margin: 0;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.form-help {
  flex-basis: 100%;
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.import-report-table {
  width: 100%;
}

.dialog-alert {
  margin-top: 12px;
}

.export-text {
  margin-top: 14px;
}

.entry-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
}

.entry-form-grid :deep(.el-form-item:nth-child(8)) {
  grid-column: 1 / -1;
}

:deep(.el-table__row.is-selected-row td) {
  background: #ecf5ff;
}

@media (max-width: 1040px) {
  .term-set-grid {
    grid-template-columns: 1fr;
  }

  .governance-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .entry-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
