<!-- 文件：frontend/src/pages/AcceptanceCenterPage.vue -->
<!-- 用途：展示管理员验收中心的 P0/P1/P2 交付证据与复核决策。 -->
<template>
  <main class="acceptance-center-page app-page" aria-labelledby="acceptance-center-title">
    <WorkbenchPageHeader
      title-id="acceptance-center-title"
      kicker="Acceptance"
      title="验收中心"
      description="查看 P0/P1/P2 交付证据、阻断风险、报告路径和最近复核结论。"
      wide
      section-class="page-heading app-page-header"
    >
      <template #actions>
        <el-tag :type="overallStatus.tagType" effect="plain">{{ overallStatus.label }}</el-tag>
        <el-button type="primary" :icon="Plus" @click="openRunDialog">登记运行</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadRuns">刷新</el-button>
      </template>
    </WorkbenchPageHeader>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <WorkbenchMetricStrip
      v-loading="loading"
      label="验收概览"
      :items="overviewItems"
      wide
      section-class="overview-grid"
    />

    <section class="tier-strip app-page-shell app-page-shell--wide" aria-label="P0 P1 P2 验收证据">
      <button
        v-for="card in tierCards"
        :key="card.tier"
        class="tier-card app-metric-card app-status-card"
        :class="`is-${card.status.key}`"
        type="button"
        :disabled="!card.run"
        @click="card.run && openRun(card.run)"
      >
        <span class="status-dot app-status-dot" aria-hidden="true"></span>
        <span class="tier-card-copy">
          <span>{{ card.label }}</span>
          <strong>{{ card.status.label }}</strong>
          <small>{{ card.description }}</small>
        </span>
      </button>
    </section>

    <section class="app-page-shell app-page-shell--wide" aria-label="验收运行列表">
      <WorkbenchPanelCard
        title="验收运行"
        subtitle="选择一条运行查看详情并提交复核。"
        card-class="run-list-panel app-filter-panel app-table-card"
      >
        <el-empty v-if="showEmptyState" description="暂无验收运行；后端返回 P0/P1/P2 证据后会显示在这里。" :image-size="96" />
        <div v-else class="table-wrap app-scrollbar-persistent">
        <el-table
          v-loading="loading"
          :data="orderedRuns"
          empty-text="暂无验收运行"
          table-layout="fixed"
          class="run-table"
          highlight-current-row
          :row-class-name="runRowClassName"
          @row-click="openRun"
        >
          <el-table-column label="验收运行" min-width="240">
            <template #default="{ row }">
              <div class="identity-cell">
                <strong>{{ row.title || row.id }}</strong>
                <span class="mono muted">{{ row.id }}</span>
                <span class="muted">{{ row.source || "未标注来源" }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="层级" width="120">
            <template #default="{ row }">
              <el-tag effect="plain">{{ tierLabel(row.tier) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="150">
            <template #default="{ row }">
              <el-tag :type="statusMeta(row.status).tagType" effect="plain">{{ statusMeta(row.status).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="风险" min-width="220">
            <template #default="{ row }">
              <div class="risk-cell">
                <el-tag :type="riskMeta(row).tagType" effect="plain">{{ riskMeta(row).label }}</el-tag>
                <small>{{ riskMeta(row).description }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="报告" min-width="220">
            <template #default="{ row }">
              <a v-if="isHttpUrl(row.report_path_or_url)" :href="row.report_path_or_url" target="_blank" rel="noreferrer">打开报告</a>
              <span v-else class="mono report-path">{{ row.report_path_or_url || "未提供" }}</span>
            </template>
          </el-table-column>
          <el-table-column label="最近复核" min-width="210">
            <template #default="{ row }">
              <div class="review-cell">
                <el-tag :type="decisionMeta(row.decision).tagType" effect="plain">{{ decisionMeta(row.decision).label }}</el-tag>
                <small>{{ row.reviewer || "未记录 reviewer" }} · {{ formatDateTime(row.reviewed_at) }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" min-width="180">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" width="110">
            <template #default="{ row }">
              <el-button size="small" :icon="View" @click.stop="openRun(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
        </div>
      </WorkbenchPanelCard>
    </section>

    <el-drawer
      v-model="drawerVisible"
      class="acceptance-detail-drawer"
      title="验收详情"
      direction="rtl"
      size="min(720px, 100vw)"
      append-to-body
      @close="clearSelectedRun"
    >
      <div class="acceptance-drawer-scroll app-scrollbar-persistent">
        <ApiErrorAlert :error="detailError" />
        <ApiErrorAlert :error="operationError" />

        <el-skeleton v-if="detailLoading && !selectedRun" :rows="8" animated />

        <template v-else-if="selectedRun">
          <section class="drawer-title-block">
            <div>
              <p class="page-kicker">{{ tierLabel(selectedRun.tier) }}</p>
              <h2>{{ selectedRun.title || selectedRun.id }}</h2>
              <p class="mono muted">{{ selectedRun.id }}</p>
            </div>
            <el-tag :type="statusMeta(selectedRun.status).tagType" effect="plain">{{ statusMeta(selectedRun.status).label }}</el-tag>
          </section>

          <section v-if="safeList(selectedRun.blockers).length || safeList(selectedRun.warnings).length" class="drawer-alerts app-alert-stack">
            <el-alert v-if="safeList(selectedRun.blockers).length" type="error" title="验收阻断" :closable="false" show-icon>
              <ul class="evidence-list">
                <li v-for="blocker in safeList(selectedRun.blockers)" :key="blocker">{{ evidenceItemText(blocker) }}</li>
              </ul>
            </el-alert>
            <el-alert v-if="safeList(selectedRun.warnings).length" type="warning" title="验收告警" :closable="false" show-icon>
              <ul class="evidence-list">
                <li v-for="warning in safeList(selectedRun.warnings)" :key="warning">{{ evidenceItemText(warning) }}</li>
              </ul>
            </el-alert>
          </section>

          <section class="drawer-section">
            <div class="section-header compact">
              <div>
                <h3 class="section-title">运行摘要</h3>
                <p class="section-subtitle">{{ selectedRun.summary || "后端未返回摘要。" }}</p>
              </div>
            </div>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="环境">{{ selectedRun.environment || "-" }}</el-descriptions-item>
              <el-descriptions-item label="来源">{{ selectedRun.source || "-" }}</el-descriptions-item>
              <el-descriptions-item label="报告">
                <a v-if="selectedRunReportHref" :href="selectedRunReportHref" target="_blank" rel="noreferrer">打开报告</a>
                <span v-else class="mono">{{ selectedRun.report_path_or_url || "未提供" }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="开始时间">{{ formatDateTime(selectedRun.started_at) }}</el-descriptions-item>
              <el-descriptions-item label="结束时间">{{ formatDateTime(selectedRun.finished_at) }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ formatDateTime(selectedRun.updated_at) }}</el-descriptions-item>
            </el-descriptions>
          </section>

          <section class="drawer-section review-panel">
            <div class="section-header compact">
              <div>
                <h3 class="section-title">复核结论</h3>
                <p class="section-subtitle">
                  当前结论：{{ decisionMeta(selectedRun.decision).label }} · {{ selectedRun.reviewer || "未记录 reviewer" }} ·
                  {{ formatDateTime(selectedRun.reviewed_at) }}
                </p>
              </div>
            </div>
            <el-form label-position="top">
              <el-form-item label="决策">
                <el-segmented v-model="reviewForm.decision" :options="decisionOptions" />
              </el-form-item>
              <el-form-item label="备注">
                <el-input
                  v-model="reviewForm.note"
                  type="textarea"
                  :rows="4"
                  maxlength="1000"
                  show-word-limit
                  placeholder="记录通过依据、阻断原因或需补充证据。"
                />
              </el-form-item>
            </el-form>
            <div class="review-actions">
              <el-button @click="clearSelectedRun">关闭</el-button>
              <el-button type="primary" :loading="reviewSaving" @click="submitReview">提交复核</el-button>
            </div>
          </section>
        </template>

        <el-empty v-else description="请选择一条验收运行" :image-size="96" />
      </div>
    </el-drawer>

    <el-dialog
      v-model="runDialogVisible"
      class="acceptance-run-dialog"
      title="登记验收运行"
      width="760px"
      destroy-on-close
      append-to-body
      @closed="resetRunForm"
    >
      <ApiErrorAlert :error="runError" />
      <el-form label-position="top" class="acceptance-run-form">
        <div class="run-form-grid">
          <el-form-item label="运行 ID" required>
            <el-input v-model="runForm.id" maxlength="160" placeholder="acceptance_p1_translation_current" />
          </el-form-item>
          <el-form-item label="标题" required>
            <el-input v-model="runForm.title" maxlength="240" placeholder="P1 Translation Formal Run" />
          </el-form-item>
          <el-form-item label="层级" required>
            <el-select v-model="runForm.tier" class="form-control" placeholder="选择层级">
              <el-option v-for="option in tierOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态" required>
            <el-select v-model="runForm.status" class="form-control" placeholder="选择状态">
              <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="环境" required>
            <el-input v-model="runForm.environment" maxlength="120" placeholder="hostdzire" />
          </el-form-item>
          <el-form-item label="来源" required>
            <el-input v-model="runForm.source" maxlength="160" placeholder="manual_import:p1_translation" />
          </el-form-item>
          <el-form-item label="开始时间">
            <el-date-picker v-model="runForm.started_at" class="form-control" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" placeholder="选择开始时间" />
          </el-form-item>
          <el-form-item label="结束时间">
            <el-date-picker v-model="runForm.finished_at" class="form-control" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" placeholder="选择结束时间" />
          </el-form-item>
        </div>
        <el-form-item label="报告路径或 URL">
          <el-input v-model="runForm.report_path_or_url" maxlength="1000" placeholder="tests/tmp/p1_translation_runs/run-1/report.md" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="runForm.summary" type="textarea" :rows="4" maxlength="4000" show-word-limit placeholder="记录本次运行结论、样本范围和签字状态。" />
        </el-form-item>
        <div class="run-form-grid">
          <el-form-item label="阻断项">
            <el-input v-model="runForm.blockersText" type="textarea" :rows="4" placeholder="每行一条 blocker" />
          </el-form-item>
          <el-form-item label="告警项">
            <el-input v-model="runForm.warningsText" type="textarea" :rows="4" placeholder="每行一条 warning" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <div class="dialog-actions">
          <el-button @click="runDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="runSaving" @click="submitRunUpsert">保存运行</el-button>
        </div>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Refresh, View } from "@element-plus/icons-vue";

import { acceptanceApi } from "@/api/acceptance";
import WorkbenchMetricStrip, { type WorkbenchMetricItem } from "@/components/WorkbenchMetricStrip.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import type {
  AcceptanceLatestSummaryResponse,
  AcceptanceReviewDecision,
  AcceptanceRunResponse,
  AcceptanceRunStatus,
  AcceptanceRunTier,
  AcceptanceRunUpsertRequest,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

type StatusView = {
  key: "success" | "warning" | "danger" | "running" | "unknown";
  label: string;
  tagType: "success" | "warning" | "danger" | "info";
  description: string;
};

type TierCard = {
  tier: "P0" | "P1" | "P2";
  label: string;
  run: AcceptanceRunResponse | null;
  status: StatusView;
  description: string;
};

type ReviewForm = {
  decision: AcceptanceReviewDecision | "";
  note: string;
};

type RunForm = {
  id: string;
  title: string;
  tier: "P0" | "P1" | "P2";
  status: "passed" | "failed" | "unknown";
  environment: string;
  source: string;
  report_path_or_url: string;
  started_at: string | null;
  finished_at: string | null;
  summary: string;
  blockersText: string;
  warningsText: string;
};

const route = useRoute();
const router = useRouter();

const tierOrder = ["P0", "P1", "P2"] as const;
const tierOptions: Array<{ label: string; value: RunForm["tier"] }> = [
  { label: "P0 Golden Sample", value: "P0" },
  { label: "P1 翻译验收", value: "P1" },
  { label: "P2 在线门禁", value: "P2" },
];
const statusOptions: Array<{ label: string; value: RunForm["status"] }> = [
  { label: "已通过", value: "passed" },
  { label: "失败", value: "failed" },
  { label: "未知，需确认", value: "unknown" },
];
const decisionOptions = [
  { label: "复核通过", value: "approved" },
  { label: "复核拒绝", value: "rejected" },
  { label: "需修改", value: "needs_changes" },
];
const evidenceMessageLabels: Record<string, string> = {
  starter_summary_historical_p0_signoff: "这是历史 P0 签字摘要，不代表下一次发布的最新运行证据。",
  starter_summary_replace_with_latest_run_report_before_release: "发布前需要用最新脚本报告或人工导入摘要替换这条 starter summary。",
  p1_formal_regression_not_recorded: "尚未记录正式 P1 翻译回归报告。",
  p1_manual_signoff_pending: "P1 人工签字仍待完成。",
  p2_online_gate_not_recorded: "尚未记录 P2 在线门禁报告。",
};

const runs = ref<AcceptanceRunResponse[]>([]);
const latestSummary = ref<AcceptanceLatestSummaryResponse | null>(null);
const total = ref(0);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);
const detailLoading = ref(false);
const detailError = ref<ApiClientError | null>(null);
const operationError = ref<ApiClientError | null>(null);
const runError = ref<ApiClientError | null>(null);
const drawerVisible = ref(false);
const runDialogVisible = ref(false);
const selectedRunId = ref("");
const selectedRun = ref<AcceptanceRunResponse | null>(null);
const reviewSaving = ref(false);
const runSaving = ref(false);
const reviewForm = reactive<ReviewForm>({
  decision: "",
  note: "",
});
const runForm = reactive<RunForm>(buildDefaultRunForm());

const orderedRuns = computed(() => [...runs.value].sort(compareRuns));
const showEmptyState = computed(() => !loading.value && !error.value && runs.value.length === 0);
const blockerCount = computed(() => latestSummary.value?.blocker_count ?? runs.value.reduce((count, run) => count + safeList(run.blockers).length, 0));
const warningCount = computed(() => latestSummary.value?.warning_count ?? runs.value.reduce((count, run) => count + safeList(run.warnings).length, 0));
const latestReviewedRun = computed(() =>
  latestSummary.value?.latest_reviewed_run ??
  runs.value
    .filter((run) => run.reviewed_at)
    .sort((left, right) => timestamp(right.reviewed_at) - timestamp(left.reviewed_at))[0] ?? null,
);
const latestReviewLabel = computed(() => {
  const run = latestReviewedRun.value;
  return run ? decisionMeta(run.decision).label : "未复核";
});
const latestReviewMeta = computed(() => {
  const run = latestReviewedRun.value;
  if (!run) {
    return "暂无 reviewer 和 reviewed_at";
  }
  return `${run.reviewer || "未记录 reviewer"} · ${formatDateTime(run.reviewed_at)}`;
});
const selectedRunReportHref = computed(() => reportHref(selectedRun.value?.report_path_or_url));
const overviewItems = computed<WorkbenchMetricItem[]>(() => [
  {
    id: "overall_status",
    label: "整体状态",
    value: overallStatus.value.label,
    helper: overallStatus.value.description,
    statusKey: overallStatus.value.key === "warning" ? "warning" : overallStatus.value.key === "danger" ? "danger" : overallStatus.value.key,
  },
  {
    id: "runs_total",
    label: "验收运行",
    value: total.value,
    helper: "当前列表返回的证据总数",
  },
  {
    id: "risk_counts",
    label: "阻断 / 告警",
    value: `${blockerCount.value} / ${warningCount.value}`,
    helper: "unknown 状态不会按通过处理",
  },
  {
    id: "latest_review",
    label: "最近复核",
    value: latestReviewLabel.value,
    helper: latestReviewMeta.value,
  },
]);

const overallStatus = computed<StatusView>(() => {
  if (latestSummary.value) {
    return latestSummaryStatusMeta(latestSummary.value);
  }
  if (!runs.value.length) {
    return {
      key: "unknown",
      label: "暂无证据",
      tagType: "info",
      description: "等待后端返回验收运行。",
    };
  }
  const missingTiers = tierOrder.filter((tier) => !latestRunForTier(tier));
  if (runs.value.some((run) => riskMeta(run).key === "danger")) {
    return {
      key: "danger",
      label: "存在阻断",
      tagType: "danger",
      description: "至少一条验收运行存在 blocker、failed 或 blocked 状态。",
    };
  }
  if (missingTiers.length) {
    return {
      key: "warning",
      label: "证据不完整",
      tagType: "warning",
      description: `缺少 ${missingTiers.join(" / ")} 验收运行，不能视为完整通过。`,
    };
  }
  if (runs.value.some((run) => riskMeta(run).key === "warning")) {
    return {
      key: "warning",
      label: "需要关注",
      tagType: "warning",
      description: "存在 warning、running 或 unknown 状态。",
    };
  }
  return {
    key: "success",
    label: "可接受",
    tagType: "success",
    description: "当前返回的验收运行未报告阻断或告警。",
  };
});

const tierCards = computed<TierCard[]>(() =>
  tierOrder.map((tier) => {
    const summary = latestSummary.value?.tiers.find((item) => normalizeTier(item.tier) === tier);
    const run = summary?.run ?? latestRunForTier(tier);
    const status = summary ? riskLevelMeta(summary.risk_level, summary.missing) : run ? riskMeta(run) : statusMeta("unknown");
    return {
      tier,
      label: tierLabel(tier),
      run,
      status,
      description: run
        ? `${run.environment || "未标注环境"} · ${formatDateTime(run.finished_at || run.updated_at)}`
        : "暂无该层级验收证据。",
    };
  }),
);

async function loadRuns(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [response, summary] = await Promise.all([acceptanceApi.list(), acceptanceApi.latestSummary()]);
    runs.value = response.items;
    total.value = response.total;
    latestSummary.value = summary;
    if (selectedRunId.value) {
      selectedRun.value = runs.value.find((run) => run.id === selectedRunId.value) ?? selectedRun.value;
    }
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function loadRunDetail(runId: string): Promise<void> {
  detailLoading.value = true;
  detailError.value = null;
  operationError.value = null;
  try {
    const response = await acceptanceApi.get(runId);
    selectedRun.value = response;
    hydrateReviewForm(response);
  } catch (caught) {
    detailError.value = normalizeApiError(caught);
  } finally {
    detailLoading.value = false;
  }
}

function openRun(run: AcceptanceRunResponse): void {
  selectedRunId.value = run.id;
  selectedRun.value = run;
  hydrateReviewForm(run);
  drawerVisible.value = true;
  void replaceAcceptanceQuery(run.id);
  void loadRunDetail(run.id);
}

function clearSelectedRun(): void {
  if (!drawerVisible.value && !selectedRunId.value) {
    return;
  }
  drawerVisible.value = false;
  selectedRunId.value = "";
  selectedRun.value = null;
  detailError.value = null;
  operationError.value = null;
  reviewForm.decision = "";
  reviewForm.note = "";
  void replaceAcceptanceQuery("");
}

async function submitReview(): Promise<void> {
  if (!selectedRunId.value) {
    return;
  }
  operationError.value = null;
  if (!reviewForm.decision) {
    ElMessage.error("请选择复核决策。");
    return;
  }
  if (reviewRequiresNote(reviewForm.decision) && !reviewForm.note.trim()) {
    ElMessage.error("拒绝或需修改时必须填写复核备注。");
    return;
  }
  if (reviewForm.decision === "approved" && selectedRun.value && riskMeta(selectedRun.value).key !== "success") {
    const confirmed = await confirmRiskyApproval(selectedRun.value);
    if (!confirmed) {
      return;
    }
  }
  reviewSaving.value = true;
  try {
    const response = await acceptanceApi.review(selectedRunId.value, {
      decision: reviewForm.decision,
      note: reviewForm.note,
    });
    selectedRun.value = response;
    updateRunInList(response);
    hydrateReviewForm(response);
    ElMessage.success("验收复核已提交。");
    await loadRuns();
  } catch (caught) {
    operationError.value = normalizeApiError(caught);
    ElMessage.error(operationError.value.message);
  } finally {
    reviewSaving.value = false;
  }
}

function openRunDialog(): void {
  Object.assign(runForm, buildDefaultRunForm());
  runError.value = null;
  runDialogVisible.value = true;
}

async function submitRunUpsert(): Promise<void> {
  runError.value = null;
  if (!validateRunForm()) {
    return;
  }
  runSaving.value = true;
  try {
    const response = await acceptanceApi.upsert(buildRunPayload());
    updateRunInList(response);
    if (selectedRunId.value === response.id) {
      selectedRun.value = response;
      hydrateReviewForm(response);
    }
    ElMessage.success("验收运行已保存。");
    runDialogVisible.value = false;
    await loadRuns();
  } catch (caught) {
    runError.value = normalizeApiError(caught);
    ElMessage.error(runError.value.message);
  } finally {
    runSaving.value = false;
  }
}

function resetRunForm(): void {
  Object.assign(runForm, buildDefaultRunForm());
  runError.value = null;
}

function buildRunPayload(): AcceptanceRunUpsertRequest {
  return {
    id: runForm.id,
    title: runForm.title,
    tier: runForm.tier,
    status: runForm.status,
    environment: runForm.environment,
    source: runForm.source,
    report_path_or_url: runForm.report_path_or_url,
    started_at: runForm.started_at,
    finished_at: runForm.finished_at,
    summary: runForm.summary,
    blockers: textLines(runForm.blockersText),
    warnings: textLines(runForm.warningsText),
  };
}

function validateRunForm(): boolean {
  const requiredFields: Array<[string, string]> = [
    [runForm.id, "运行 ID"],
    [runForm.title, "标题"],
    [runForm.environment, "环境"],
    [runForm.source, "来源"],
  ];
  const missing = requiredFields.find(([value]) => !value.trim());
  if (missing) {
    ElMessage.error(`${missing[1]}不能为空。`);
    return false;
  }
  const startedAt = timestamp(runForm.started_at);
  const finishedAt = timestamp(runForm.finished_at);
  if (startedAt && finishedAt && finishedAt < startedAt) {
    ElMessage.error("结束时间不能早于开始时间。");
    return false;
  }
  return true;
}

function hydrateReviewForm(run: AcceptanceRunResponse): void {
  reviewForm.decision = run.decision ?? "";
  reviewForm.note = run.review_note ?? "";
}

function updateRunInList(run: AcceptanceRunResponse): void {
  const index = runs.value.findIndex((candidate) => candidate.id === run.id);
  if (index >= 0) {
    runs.value.splice(index, 1, run);
    return;
  }
  runs.value.unshift(run);
  total.value += 1;
}

function reviewRequiresNote(decision: AcceptanceReviewDecision): boolean {
  return decision === "rejected" || decision === "needs_changes";
}

function buildDefaultRunForm(): RunForm {
  return {
    id: defaultRunId(),
    title: "",
    tier: "P0",
    status: "unknown",
    environment: "hostdzire",
    source: "manual_import",
    report_path_or_url: "",
    started_at: null,
    finished_at: null,
    summary: "",
    blockersText: "",
    warningsText: "",
  };
}

function defaultRunId(): string {
  const stamp = new Date().toISOString().replace(/\D/g, "").slice(0, 14);
  return `acceptance_manual_${stamp}`;
}

async function confirmRiskyApproval(run: AcceptanceRunResponse): Promise<boolean> {
  return ElMessageBox.confirm(
    `${run.title || run.id} 仍存在 unknown、warning 或 blocker。复核通过只代表人工确认该条摘要，不会把原始验收状态改为 passed。`,
    "确认复核通过",
    {
      confirmButtonText: "确认提交",
      cancelButtonText: "返回检查",
      type: "warning",
    },
  ).then(() => true).catch(() => false);
}

function latestRunForTier(tier: "P0" | "P1" | "P2"): AcceptanceRunResponse | null {
  return runs.value
    .filter((run) => normalizeTier(run.tier) === tier)
    .sort((left, right) => timestamp(right.updated_at || right.finished_at || right.started_at) - timestamp(left.updated_at || left.finished_at || left.started_at))[0] ?? null;
}

function compareRuns(left: AcceptanceRunResponse, right: AcceptanceRunResponse): number {
  const tierDelta = tierRank(left.tier) - tierRank(right.tier);
  if (tierDelta !== 0) {
    return tierDelta;
  }
  return timestamp(right.updated_at || right.finished_at || right.started_at) - timestamp(left.updated_at || left.finished_at || left.started_at);
}

function tierRank(tier: AcceptanceRunTier): number {
  const index = tierOrder.indexOf(normalizeTier(tier) as (typeof tierOrder)[number]);
  return index >= 0 ? index : tierOrder.length;
}

function normalizeTier(tier: AcceptanceRunTier): string {
  return String(tier || "").toUpperCase();
}

function tierLabel(tier: AcceptanceRunTier): string {
  const normalized = normalizeTier(tier);
  if (normalized === "P0") {
    return "P0 Golden Sample";
  }
  if (normalized === "P1") {
    return "P1 翻译验收";
  }
  if (normalized === "P2") {
    return "P2 在线门禁";
  }
  return normalized || "未分层";
}

function statusMeta(status: AcceptanceRunStatus): StatusView {
  const normalized = String(status || "unknown").toLowerCase();
  if (normalized === "passed") {
    return {
      key: "success",
      label: "已通过",
      tagType: "success",
      description: "后端验收状态为 passed。",
    };
  }
  if (normalized === "blocked") {
    return {
      key: "danger",
      label: "已阻断",
      tagType: "danger",
      description: "后端验收状态为 blocked。",
    };
  }
  if (normalized === "failed") {
    return {
      key: "danger",
      label: "失败",
      tagType: "danger",
      description: "验收运行失败。",
    };
  }
  if (normalized === "running") {
    return {
      key: "running",
      label: "运行中",
      tagType: "warning",
      description: "验收仍在执行，不能作为通过结论。",
    };
  }
  if (!normalized || normalized === "unknown") {
    return {
      key: "unknown",
      label: "未知，需确认",
      tagType: "info",
      description: "状态未知，不按通过处理。",
    };
  }
  return {
    key: "unknown",
    label: `未识别: ${status}`,
    tagType: "info",
    description: "状态未被前端识别，不按通过处理。",
  };
}

function latestSummaryStatusMeta(summary: AcceptanceLatestSummaryResponse): StatusView {
  if (summary.overall_status === "accepted") {
    return {
      key: "success",
      label: "可接受",
      tagType: "success",
      description: "P0/P1/P2 最新证据均未报告阻断或告警。",
    };
  }
  if (summary.overall_status === "blocked") {
    return {
      key: "danger",
      label: "存在阻断",
      tagType: "danger",
      description: `最新证据包含 ${summary.blocker_count} 个阻断项，不能作为发布通过结论。`,
    };
  }
  if (summary.overall_status === "incomplete") {
    return {
      key: "warning",
      label: "证据不完整",
      tagType: "warning",
      description: `缺少 ${summary.missing_tiers.join(" / ")} 验收证据，不能视为完整通过。`,
    };
  }
  return {
    key: "warning",
    label: "需要关注",
    tagType: "warning",
    description: `最新证据包含 ${summary.warning_count} 个告警或未知状态。`,
  };
}

function riskLevelMeta(riskLevel: string, missing: boolean): StatusView {
  if (missing) {
    return {
      key: "unknown",
      label: "缺少证据",
      tagType: "info",
      description: "该层级暂无最新验收运行。",
    };
  }
  if (riskLevel === "danger") {
    return {
      key: "danger",
      label: "存在阻断",
      tagType: "danger",
      description: "该层级最新证据包含失败状态或 blocker。",
    };
  }
  if (riskLevel === "warning" || riskLevel === "unknown") {
    return {
      key: "warning",
      label: "需要关注",
      tagType: "warning",
      description: "该层级最新证据包含告警或未知状态。",
    };
  }
  return {
    key: "success",
    label: "无明显风险",
    tagType: "success",
    description: "该层级最新证据未返回 blocker 或 warning。",
  };
}

function riskMeta(run: AcceptanceRunResponse): StatusView {
  const status = statusMeta(run.status);
  const blockers = safeList(run.blockers);
  const warnings = safeList(run.warnings);
  if (blockers.length || status.key === "danger") {
    return {
      key: "danger",
      label: "存在阻断",
      tagType: "danger",
      description: blockers.length ? `${blockers.length} 个 blocker` : status.description,
    };
  }
  if (warnings.length || status.key === "running" || status.key === "unknown") {
    return {
      key: "warning",
      label: "需要关注",
      tagType: "warning",
      description: warnings.length ? `${warnings.length} 个 warning` : status.description,
    };
  }
  return {
    key: "success",
    label: "无明显风险",
    tagType: "success",
    description: "未返回 blocker 或 warning。",
  };
}

function decisionMeta(decision: AcceptanceReviewDecision | null): { label: string; tagType: "success" | "warning" | "danger" | "info" } {
  if (decision === "approved") {
    return { label: "已通过", tagType: "success" };
  }
  if (decision === "rejected") {
    return { label: "已拒绝", tagType: "danger" };
  }
  if (decision === "needs_changes") {
    return { label: "需修改", tagType: "warning" };
  }
  return { label: "未复核", tagType: "info" };
}

function safeList(value: string[] | null | undefined): string[] {
  return Array.isArray(value) ? value.filter((item) => typeof item === "string" && item.trim()) : [];
}

function textLines(value: string): string[] {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function evidenceItemText(value: string): string {
  return evidenceMessageLabels[value] ?? value;
}

function timestamp(value?: string | null): number {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function isHttpUrl(value?: string | null): boolean {
  return typeof value === "string" && /^https?:\/\//i.test(value);
}

function reportHref(value?: string | null): string | undefined {
  return typeof value === "string" && isHttpUrl(value) ? value : undefined;
}

function firstQueryValue(value: unknown): string {
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

async function replaceAcceptanceQuery(runId: string): Promise<void> {
  const query = { ...route.query };
  if (runId) {
    query.acceptance_run_id = runId;
  } else {
    delete query.acceptance_run_id;
  }
  await router.replace({ name: "system-status-acceptance", query });
}

function syncRunFromRoute(): void {
  const routeRunId = firstQueryValue(route.query.acceptance_run_id);
  if (!routeRunId) {
    if (drawerVisible.value) {
      drawerVisible.value = false;
    }
    selectedRunId.value = "";
    selectedRun.value = null;
    detailError.value = null;
    operationError.value = null;
    return;
  }
  if (routeRunId === selectedRunId.value && drawerVisible.value) {
    return;
  }
  selectedRunId.value = routeRunId;
  selectedRun.value = runs.value.find((run) => run.id === routeRunId) ?? null;
  if (selectedRun.value) {
    hydrateReviewForm(selectedRun.value);
  }
  drawerVisible.value = true;
  void loadRunDetail(routeRunId);
}

function runRowClassName({ row }: { row: AcceptanceRunResponse }): string {
  return row.id === selectedRunId.value ? "is-selected-run" : "";
}

watch(
  () => route.query.acceptance_run_id,
  () => syncRunFromRoute(),
);

onMounted(async () => {
  await loadRuns();
  syncRunFromRoute();
});
</script>

<style scoped lang="scss">
.acceptance-center-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
  overflow-x: hidden;
}

.page-heading,
.section-header,
.heading-actions,
.review-actions,
.dialog-actions {
  display: flex;
  align-items: center;
}

.page-heading,
.section-header {
  justify-content: space-between;
  gap: var(--app-space-4);
}

.heading-actions,
.review-actions,
.dialog-actions {
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.tier-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.tier-card {
  width: 100%;
  border-color: var(--app-color-border);
  color: var(--app-color-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.tier-card:disabled {
  cursor: default;
  transform: none;
}

.tier-card-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.table-wrap {
  overflow-x: auto;
}

.run-table {
  min-width: 1120px;
}

.identity-cell,
.review-cell,
.risk-cell {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.review-cell small,
.risk-cell small {
  color: var(--app-color-text-muted);
}

.mono {
  font-family: var(--app-font-mono);
}

.muted {
  color: var(--app-color-text-muted);
}

.report-path {
  overflow-wrap: anywhere;
}

:deep(.is-selected-run > td.el-table__cell) {
  background: var(--app-color-primary-soft);
}

:global(.acceptance-detail-drawer.el-drawer) {
  max-width: 100vw;
}

:global(.acceptance-detail-drawer .el-drawer__body) {
  min-height: 0;
  padding: 0;
  overflow: hidden;
}

.acceptance-drawer-scroll {
  display: grid;
  align-content: start;
  gap: var(--app-space-4);
  height: 100%;
  min-width: 0;
  padding: 0 var(--app-space-5) var(--app-space-5);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.drawer-title-block {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-3);
  padding-top: var(--app-space-2);
}

.drawer-title-block h2 {
  margin: 0;
  overflow-wrap: anywhere;
  font-size: 22px;
}

.drawer-section {
  display: grid;
  gap: var(--app-space-3);
  min-width: 0;
  padding: var(--app-space-4);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
}

.section-header.compact {
  align-items: flex-start;
}

.evidence-list {
  margin: var(--app-space-2) 0 0;
  padding-left: var(--app-space-5);
}

.review-panel {
  margin-bottom: var(--app-space-2);
}

.acceptance-run-form {
  display: grid;
  gap: var(--app-space-3);
}

.run-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.form-control {
  width: 100%;
}

@media (max-width: 860px) {
  .page-heading,
  .section-header,
  .drawer-title-block {
    align-items: flex-start;
    flex-direction: column;
  }

  .heading-actions,
  .review-actions,
  .dialog-actions {
    justify-content: flex-start;
    width: 100%;
  }

  .tier-strip {
    grid-template-columns: 1fr;
  }

  .run-form-grid {
    grid-template-columns: 1fr;
  }

  .acceptance-drawer-scroll {
    padding: 0 var(--app-space-4) var(--app-space-4);
  }
}
</style>
