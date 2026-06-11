<!-- frontend/src/pages/SettingsHomePage.vue: Configuration workbench landing page and release gate. -->
<template>
  <main class="settings-page" aria-labelledby="settings-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">配置中心</p>
        <h1 id="settings-title">配置工作台</h1>
        <p>统一查看生产运行门禁、默认配置版本、草稿和待处理治理事项。</p>
      </div>
      <RoleGate>
        <el-tag type="warning" effect="plain">管理员操作已启用</el-tag>
      </RoleGate>
    </section>

    <ConfigTodoSummary :summary="summary" :loading="initialLoading" :error="error" @refresh="refreshSummary" />
    <div v-if="summary && refreshing" class="refresh-note">正在后台更新配置总览，当前页面保留上次结果。</div>

    <section v-if="summary" class="release-gate-workspace" aria-label="发布门禁处理队列">
      <div class="section-header">
        <div>
          <h2 class="section-title">发布门禁处理队列</h2>
          <p class="section-subtitle">把 P0 document_jobs 门禁、阻断项和告警项收敛到可处理入口。</p>
        </div>
        <div class="gate-tags">
          <el-tag :type="summary.release_gate.p0_document_jobs_ready ? 'success' : 'danger'" effect="plain">
            p0={{ summary.release_gate.p0_document_jobs_ready ? "ready" : "blocked" }}
          </el-tag>
          <el-tag effect="plain">blockers={{ summary.release_gate.blockers.length }}</el-tag>
          <el-tag effect="plain">warnings={{ summary.release_gate.warnings.length }}</el-tag>
        </div>
      </div>

      <div class="gate-status-grid">
        <article>
          <span>P0 document_jobs</span>
          <strong>{{ summary.release_gate.p0_document_jobs_ready ? "就绪" : "阻断" }}</strong>
          <small>{{ summary.release_gate.p0_document_jobs_required ? "当前环境强制门禁" : "当前环境观察门禁" }}</small>
        </article>
        <article>
          <span>阻断项</span>
          <strong>{{ summary.release_gate.blockers.length }}</strong>
          <small>需要先处理再发布</small>
        </article>
        <article>
          <span>告警项</span>
          <strong>{{ summary.release_gate.warnings.length }}</strong>
          <small>建议发布前确认</small>
        </article>
      </div>

      <div v-if="releaseGateItems.length" class="gate-action-list">
        <router-link v-for="item in releaseGateItems" :key="item.key" class="gate-action-item" :to="item.route">
          <el-tag size="small" :type="severityTagType(item.severity)" effect="plain">
            {{ configWorkbenchSeverityText(item.severity) }}
          </el-tag>
          <span>{{ item.message }}</span>
          <small>{{ item.routeLabel }}</small>
        </router-link>
      </div>
      <div v-else class="gate-empty">当前发布门禁没有待处理项。</div>
    </section>

    <section v-if="summary" class="settings-groups" aria-label="配置治理状态">
      <article v-for="group in summary.groups" :key="group.id" class="settings-group">
        <header class="settings-group-header">
          <span class="settings-group-icon" aria-hidden="true">
            <el-icon><component :is="groupIcon(group.id)" /></el-icon>
          </span>
          <span class="settings-group-copy">
            <strong>{{ group.label }}</strong>
            <small>{{ groupSubtitle(group) }}</small>
          </span>
          <span class="group-tags">
            <el-tag :type="statusTagType(group.status)" effect="plain">
              {{ configWorkbenchStatusText(group.status) }}
            </el-tag>
            <el-tag v-if="group.detail_status !== 'complete'" type="info" effect="plain">
              {{ detailLabel(group) }}
            </el-tag>
          </span>
        </header>

        <div class="group-metrics">
          <dl>
            <div>
              <dt>默认版本</dt>
              <dd>{{ group.default_label || "-" }}</dd>
            </div>
            <div>
              <dt>草稿</dt>
              <dd>{{ group.draft_count ?? "-" }}</dd>
            </div>
            <div>
              <dt>待处理</dt>
              <dd>{{ group.pending_count ?? "-" }}</dd>
            </div>
            <div>
              <dt>阻断 / 告警</dt>
              <dd>{{ group.blocker_count }} / {{ group.warning_count }}</dd>
            </div>
          </dl>
        </div>

        <div class="finding-stack">
          <router-link
            v-for="finding in visibleFindings(group)"
            :key="finding.code + finding.target_id"
            class="finding-item"
            :to="finding.route || group.route"
          >
            <el-tag size="small" :type="severityTagType(finding.severity)" effect="plain">
              {{ configWorkbenchSeverityText(finding.severity) }}
            </el-tag>
            <span>{{ finding.message }}</span>
          </router-link>
          <div v-if="groupLoading[group.id]" class="finding-more">正在加载深度检查结果。</div>
          <div v-if="groupErrors[group.id]" class="finding-error">{{ groupErrors[group.id] }}</div>
          <div v-if="group.findings.length > 3" class="finding-more">
            还有 {{ group.findings.length - 3 }} 条事项，请进入详情页查看。
          </div>
          <div v-if="group.findings.length === 0" class="finding-empty">暂无阻断或告警。</div>
        </div>

        <router-link class="settings-link" :to="group.route">
          <span>进入{{ group.label }}</span>
        </router-link>
      </article>
    </section>

    <el-empty v-else-if="!loading && !error" description="暂无配置工作台数据" :image-size="90" />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  Collection,
  Cpu,
  DocumentChecked,
  Files,
  Tickets,
} from "@element-plus/icons-vue";

import {
  configSummaryApi,
  type ConfigWorkbenchFinding,
  type ConfigWorkbenchGroup,
  type ConfigWorkbenchGroupId,
  type ConfigWorkbenchStatus,
  type ConfigWorkbenchSummaryResponse,
} from "@/api/configSummary";
import ConfigTodoSummary from "@/components/ConfigTodoSummary.vue";
import RoleGate from "@/components/RoleGate.vue";
import {
  configWorkbenchDetailStatusText,
  configWorkbenchSeverityText,
  configWorkbenchStatusText,
  readinessCodeText,
} from "@/utils/displayText";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { releaseGateRouteForCode, releaseGateRouteLabel } from "@/utils/releaseGateRoutes";

const CACHE_TTL_MS = 60_000;

type ReleaseGateItem = {
  key: string;
  severity: "critical" | "warning";
  message: string;
  route: string;
  routeLabel: string;
};

let summaryCache: { value: ConfigWorkbenchSummaryResponse; loadedAt: number } | null = null;

const summary = ref<ConfigWorkbenchSummaryResponse | null>(null);
const initialLoading = ref(false);
const refreshing = ref(false);
const error = ref<ApiClientError | null>(null);
const groupLoading = reactive<Record<ConfigWorkbenchGroupId, boolean>>({
  runtime_readiness: false,
  templates: false,
  term_rule_sets: false,
  translation_profiles: false,
  translation_term_sets: false,
});
const groupErrors = reactive<Record<ConfigWorkbenchGroupId, string>>({
  runtime_readiness: "",
  templates: "",
  term_rule_sets: "",
  translation_profiles: "",
  translation_term_sets: "",
});
const loading = computed(() => initialLoading.value || refreshing.value);
const releaseGateItems = computed<ReleaseGateItem[]>(() => {
  if (!summary.value) {
    return [];
  }
  return [
    ...releaseGateFindingItems("critical", summary.value.release_gate.blockers, summary.value.release_gate.blocker_findings),
    ...releaseGateFindingItems("warning", summary.value.release_gate.warnings, summary.value.release_gate.warning_findings),
  ];
});

const iconMap = {
  runtime_readiness: Cpu,
  templates: Files,
  term_rule_sets: Collection,
  translation_profiles: DocumentChecked,
  translation_term_sets: Tickets,
} satisfies Record<ConfigWorkbenchGroupId, unknown>;

async function loadSummary(force = false): Promise<void> {
  const cached = summaryCache;
  if (!force && cached && Date.now() - cached.loadedAt < CACHE_TTL_MS) {
    summary.value = cached.value;
    void fetchSummary({ background: true });
    return;
  }
  await fetchSummary({ background: Boolean(summary.value) });
}

async function refreshSummary(): Promise<void> {
  await loadSummary(true);
}

async function fetchSummary({ background }: { background: boolean }): Promise<void> {
  if (background) {
    refreshing.value = true;
  } else {
    initialLoading.value = true;
  }
  error.value = null;
  try {
    const response = await configSummaryApi.get("overview");
    summary.value = withDerivedOverallStatus(response);
    summaryCache = { value: summary.value, loadedAt: Date.now() };
    void loadDeferredGroupDetails(response.groups);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    initialLoading.value = false;
    refreshing.value = false;
  }
}

function groupIcon(groupId: ConfigWorkbenchGroupId): unknown {
  return iconMap[groupId];
}

function visibleFindings(group: ConfigWorkbenchGroup): ConfigWorkbenchFinding[] {
  return group.findings.slice(0, 3);
}

function groupSubtitle(group: ConfigWorkbenchGroup): string {
  if (group.status === "ready") {
    return "已满足当前配置门禁。";
  }
  if (group.status === "unavailable") {
    return "当前部署未启用对应版本治理能力。";
  }
  if (group.blocker_count > 0) {
    return "存在需要先处理的阻断项。";
  }
  return "存在发布前建议处理的事项。";
}

function detailLabel(group: ConfigWorkbenchGroup): string {
  if (groupLoading[group.id]) {
    return "深度检查加载中";
  }
  return configWorkbenchDetailStatusText(group.detail_status);
}

function statusTagType(status: ConfigWorkbenchStatus): "success" | "warning" | "danger" | "info" {
  if (status === "ready") {
    return "success";
  }
  if (status === "blocked") {
    return "danger";
  }
  if (status === "warning") {
    return "warning";
  }
  return "info";
}

function severityTagType(severity: string): "success" | "warning" | "danger" | "info" {
  if (severity === "critical") {
    return "danger";
  }
  if (severity === "warning") {
    return "warning";
  }
  return "info";
}

function releaseGateFindingItems(
  severity: "critical" | "warning",
  codes: string[],
  findings: ConfigWorkbenchFinding[],
): ReleaseGateItem[] {
  if (findings.length) {
    return findings.map((finding, index) => {
      const route = finding.route || releaseGateRouteForCode(finding.code);
      return {
        key: `${severity}:${finding.code}:${finding.target_id || index}`,
        severity,
        message: finding.message,
        route,
        routeLabel: releaseGateRouteLabel(route),
      };
    });
  }
  return codes.map((code) => {
    const route = releaseGateRouteForCode(code);
    return {
      key: `${severity}:${code}`,
      severity,
      message: readinessCodeText(code),
      route,
      routeLabel: releaseGateRouteLabel(route),
    };
  });
}

async function loadDeferredGroupDetails(groups: ConfigWorkbenchGroup[]): Promise<void> {
  await Promise.allSettled(
    groups
      .filter((group) => group.detail_status === "deferred")
      .map((group) => loadGroupDetail(group.id)),
  );
}

async function loadGroupDetail(groupId: ConfigWorkbenchGroupId): Promise<void> {
  groupLoading[groupId] = true;
  groupErrors[groupId] = "";
  try {
    const group = await configSummaryApi.getGroup(groupId, "full");
    if (!summary.value) {
      return;
    }
    summary.value = withDerivedOverallStatus({
      ...summary.value,
      groups: summary.value.groups.map((item) => item.id === group.id ? group : item),
    });
    summaryCache = { value: summary.value, loadedAt: Date.now() };
  } catch (caught) {
    const normalized = normalizeApiError(caught);
    groupErrors[groupId] = normalized.message || "深度检查加载失败。";
  } finally {
    groupLoading[groupId] = false;
  }
}

function withDerivedOverallStatus(response: ConfigWorkbenchSummaryResponse): ConfigWorkbenchSummaryResponse {
  return {
    ...response,
    overall_status: deriveOverallStatus(response.groups, response.release_gate.blockers, response.release_gate.warnings),
  };
}

function deriveOverallStatus(
  groups: ConfigWorkbenchGroup[],
  blockers: string[],
  warnings: string[],
): ConfigWorkbenchStatus {
  if (blockers.length || groups.some((group) => group.status === "blocked")) {
    return "blocked";
  }
  if (warnings.length || groups.some((group) => group.status === "warning" || group.status === "unavailable")) {
    return "warning";
  }
  return "ready";
}

onMounted(() => {
  void loadSummary();
});
</script>

<style scoped lang="scss">
.settings-page {
  display: grid;
  gap: 18px;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0 2px;
}

.page-kicker {
  margin: 0 0 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
  line-height: 1.2;
}

.page-heading p:last-child {
  margin: 8px 0 0;
  color: #667085;
}

.settings-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.refresh-note {
  color: #667085;
  font-size: 13px;
}

.release-gate-workspace {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.section-title {
  margin: 0;
  color: #111827;
  font-size: 18px;
  line-height: 1.3;
}

.section-subtitle {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.gate-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.gate-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.gate-status-grid article {
  display: grid;
  gap: 5px;
  min-height: 92px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
}

.gate-status-grid span,
.gate-status-grid strong,
.gate-status-grid small {
  display: block;
}

.gate-status-grid span {
  color: #667085;
  font-size: 12px;
}

.gate-status-grid strong {
  color: #111827;
  font-size: 20px;
  line-height: 1.2;
}

.gate-status-grid small {
  color: #667085;
  font-size: 12px;
}

.gate-action-list {
  display: grid;
  gap: 8px;
}

.gate-action-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 44px;
  padding: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #111827;
}

.gate-action-item:hover {
  border-color: #93c5fd;
  color: #111827;
}

.gate-action-item span {
  overflow-wrap: anywhere;
}

.gate-action-item small,
.gate-empty {
  color: #667085;
  font-size: 13px;
}

.settings-group {
  display: grid;
  align-content: start;
  gap: 14px;
  min-width: 0;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.settings-group-header {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: flex-start;
  color: #111827;
}

.group-tags {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.settings-group-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: #eef2ff;
  color: #4f46e5;
  font-size: 20px;
}

.settings-group-copy strong,
.settings-group-copy small {
  display: block;
}

.settings-group-copy strong {
  margin-bottom: 8px;
  font-size: 16px;
}

.settings-group-copy small {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.group-metrics dl {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.group-metrics div {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
}

.group-metrics dt {
  color: #667085;
  font-size: 12px;
}

.group-metrics dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
  color: #111827;
  font-size: 13px;
  font-weight: 700;
}

.finding-stack {
  display: grid;
  gap: 8px;
}

.finding-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  min-height: 42px;
  padding: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #111827;
}

.finding-item:hover {
  border-color: #93c5fd;
  color: #111827;
}

.finding-more,
.finding-empty,
.finding-error {
  color: #667085;
  font-size: 13px;
}

.finding-error {
  color: #b42318;
}

.settings-link {
  display: inline-flex;
  justify-content: center;
  min-height: 38px;
  padding: 9px 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 14px;
  font-weight: 700;
}

.settings-link:hover {
  border-color: #60a5fa;
  color: #1d4ed8;
}

@media (max-width: 1040px) {
  .settings-groups {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .page-heading,
  .section-header,
  .settings-group-header {
    align-items: flex-start;
  }

  .page-heading,
  .section-header {
    flex-direction: column;
  }

  .gate-tags {
    justify-content: flex-start;
  }

  .settings-group-header {
    grid-template-columns: 42px minmax(0, 1fr);
  }

  .settings-group-header .group-tags {
    grid-column: 1 / -1;
    justify-self: start;
  }

  .group-metrics dl {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .gate-status-grid {
    grid-template-columns: 1fr;
  }

  .gate-action-item {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .gate-action-item small {
    grid-column: 2;
  }
}

@media (max-width: 520px) {
  .group-metrics dl {
    grid-template-columns: 1fr;
  }
}
</style>
