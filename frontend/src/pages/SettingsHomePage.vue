<!-- frontend/src/pages/SettingsHomePage.vue: 配置工作台入口和发布门禁。 -->
<template>
  <main class="settings-page app-page" aria-labelledby="settings-title">
    <WorkbenchPageHeader
      title-id="settings-title"
      kicker="配置中心"
      title="配置工作台"
      description="统一查看生产运行门禁、默认配置版本、草稿和待处理治理事项。"
      section-class="page-heading app-page-header"
    >
      <template #actions>
        <RoleGate>
          <el-tag type="warning" effect="plain">管理员操作已启用</el-tag>
        </RoleGate>
      </template>
    </WorkbenchPageHeader>

    <ConfigTodoSummary class="app-page-shell" :summary="summary" :loading="initialLoading" :error="error" @refresh="refreshSummary" />
    <div v-if="summary && refreshing" class="refresh-note app-page-shell">正在后台更新配置总览，当前页面保留上次结果。</div>

    <section class="word-config-entry-grid app-page-shell" aria-label="配置入口">
      <RoleGate>
      <router-link class="word-config-entry app-entry-card" to="/settings/templates">
        <span class="settings-group-icon" aria-hidden="true">
          <el-icon><Document /></el-icon>
        </span>
        <span>
          <strong>Word 模板文档</strong>
          <small>管理 DOCX 模板文件、默认页眉内容、公司 Logo 和版本发布。</small>
        </span>
      </router-link>
      <router-link class="word-config-entry app-entry-card" to="/settings/word-page-styles">
        <span class="settings-group-icon" aria-hidden="true">
          <el-icon><Brush /></el-icon>
        </span>
        <span>
          <strong>Word 页面样式配置</strong>
          <small>维护页边距、标题、目录、正文、表格和页眉页脚文字样式。</small>
        </span>
      </router-link>
      <router-link class="word-config-entry app-entry-card" to="/settings/ai-provider">
        <span class="settings-group-icon" aria-hidden="true">
          <el-icon><Cpu /></el-icon>
        </span>
        <span>
          <strong>AI 配置</strong>
          <small>管理翻译 provider、Base URL、模型和运行时 API Key。</small>
        </span>
      </router-link>
      <router-link class="word-config-entry app-entry-card" to="/settings/mineru">
        <span class="settings-group-icon" aria-hidden="true">
          <el-icon><Key /></el-icon>
        </span>
        <span>
          <strong>MinerU 配置</strong>
          <small>原子轮换 PDF 解析使用的 MinerU 账号 UID 与 API 密钥，并查看配置状态。</small>
        </span>
      </router-link>
      </RoleGate>
    </section>

    <section v-if="summary" class="app-page-shell" aria-label="发布门禁处理队列">
      <WorkbenchPanelCard
        title="发布门禁处理队列"
        subtitle="把 P0 document_jobs 门禁、阻断项和告警项收敛到可处理入口。"
        card-class="release-gate-workspace app-panel"
      >
        <template #actions>
          <div class="gate-tags">
            <el-tag :type="summary.release_gate.p0_document_jobs_ready ? 'success' : 'danger'" effect="plain">
              p0={{ summary.release_gate.p0_document_jobs_ready ? "ready" : "blocked" }}
            </el-tag>
            <el-tag effect="plain">blockers={{ summary.release_gate.blockers.length }}</el-tag>
            <el-tag effect="plain">warnings={{ summary.release_gate.warnings.length }}</el-tag>
          </div>
        </template>

        <WorkbenchGovernanceMetricStrip
          label="发布门禁摘要"
          section-class="gate-status-grid"
          :items="releaseGateMetricItems"
        />

        <div v-if="releaseGateItems.length" class="gate-action-list">
        <router-link v-for="item in releaseGateItems" :key="item.key" class="gate-action-item app-subpanel" :to="item.route">
          <el-tag size="small" :type="severityTagType(item.severity)" effect="plain">
            {{ configWorkbenchSeverityText(item.severity) }}
          </el-tag>
          <span>{{ item.message }}</span>
          <small>{{ item.routeLabel }}</small>
        </router-link>
        </div>
        <div v-else class="gate-empty">当前发布门禁没有待处理项。</div>
      </WorkbenchPanelCard>
    </section>

    <section v-if="summary" class="settings-groups app-page-shell" aria-label="配置治理状态">
      <article v-for="group in summary.groups" :key="group.id" class="settings-group app-panel">
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
            class="finding-item app-subpanel"
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
  Brush,
  Collection,
  Cpu,
  Document,
  DocumentChecked,
  Files,
  Key,
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
import WorkbenchGovernanceMetricStrip, { type WorkbenchGovernanceMetricItem } from "@/components/WorkbenchGovernanceMetricStrip.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import {
  configWorkbenchDetailStatusText,
  configWorkbenchSeverityText,
  configWorkbenchStatusText,
  readinessCodeText,
} from "@/utils/displayText";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { releaseGateRouteForCode, releaseGateRouteLabel } from "@/utils/releaseGateRoutes";

type ReleaseGateItem = {
  key: string;
  severity: "critical" | "warning";
  message: string;
  route: string;
  routeLabel: string;
};

let summaryRequestSeq = 0;

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
const releaseGateMetricItems = computed<WorkbenchGovernanceMetricItem[]>(() => {
  if (!summary.value) {
    return [];
  }
  return [
    {
      id: "p0_document_jobs",
      label: "P0 document_jobs",
      value: summary.value.release_gate.p0_document_jobs_ready ? "就绪" : "阻断",
      helper: summary.value.release_gate.p0_document_jobs_required ? "当前环境强制门禁" : "当前环境观察门禁",
      tone: summary.value.release_gate.p0_document_jobs_ready ? "success" : "danger",
    },
    {
      id: "blockers",
      label: "阻断项",
      value: summary.value.release_gate.blockers.length,
      helper: "需要先处理再发布",
      tone: summary.value.release_gate.blockers.length ? "danger" : "success",
    },
    {
      id: "warnings",
      label: "告警项",
      value: summary.value.release_gate.warnings.length,
      helper: "建议发布前确认",
      tone: summary.value.release_gate.warnings.length ? "warning" : "success",
    },
  ];
});

const iconMap = {
  runtime_readiness: Cpu,
  templates: Files,
  term_rule_sets: Collection,
  translation_profiles: DocumentChecked,
  translation_term_sets: Tickets,
} satisfies Record<ConfigWorkbenchGroupId, unknown>;

async function loadSummary(): Promise<void> {
  await fetchSummary({ background: Boolean(summary.value) });
}

async function refreshSummary(): Promise<void> {
  await fetchSummary({ background: Boolean(summary.value) });
}

async function fetchSummary({ background }: { background: boolean }): Promise<void> {
  const requestSeq = ++summaryRequestSeq;
  if (background) {
    refreshing.value = true;
  } else {
    initialLoading.value = true;
  }
  error.value = null;
  try {
    const response = await configSummaryApi.get("overview");
    if (requestSeq !== summaryRequestSeq) {
      return;
    }
    resetGroupDetailState();
    summary.value = response;
    void loadDeferredGroupDetails(response.groups, requestSeq);
  } catch (caught) {
    if (requestSeq === summaryRequestSeq) {
      error.value = normalizeApiError(caught);
    }
  } finally {
    if (requestSeq === summaryRequestSeq) {
      initialLoading.value = false;
      refreshing.value = false;
    }
  }
}

function resetGroupDetailState(): void {
  for (const groupId of Object.keys(groupLoading) as ConfigWorkbenchGroupId[]) {
    groupLoading[groupId] = false;
    groupErrors[groupId] = "";
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

async function loadDeferredGroupDetails(groups: ConfigWorkbenchGroup[], requestSeq: number): Promise<void> {
  await Promise.allSettled(
    groups
      .filter((group) => group.detail_status === "deferred")
      .map((group) => loadGroupDetail(group.id, requestSeq)),
  );
}

async function loadGroupDetail(groupId: ConfigWorkbenchGroupId, requestSeq: number): Promise<void> {
  groupLoading[groupId] = true;
  groupErrors[groupId] = "";
  try {
    const group = await configSummaryApi.getGroup(groupId, "full");
    if (requestSeq !== summaryRequestSeq || !summary.value) {
      return;
    }
    summary.value = {
      ...summary.value,
      groups: summary.value.groups.map((item) => item.id === group.id ? group : item),
    };
  } catch (caught) {
    if (requestSeq === summaryRequestSeq) {
      const normalized = normalizeApiError(caught);
      groupErrors[groupId] = normalized.message || "深度检查加载失败。";
    }
  } finally {
    if (requestSeq === summaryRequestSeq) {
      groupLoading[groupId] = false;
    }
  }
}

onMounted(() => {
  void loadSummary();
});
</script>

<style scoped lang="scss">
.settings-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
}

.page-heading {
  overflow: hidden;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--app-space-4);
  min-height: 176px;
  border-color: color-mix(in srgb, var(--app-color-primary-border) 78%, transparent);
  background:
    linear-gradient(var(--app-color-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--app-color-grid-line) 1px, transparent 1px),
    var(--app-gradient-hero);
  background-size:
    32px 32px,
    32px 32px,
    auto;
  box-shadow:
    0 24px 64px color-mix(in srgb, var(--app-color-primary) 22%, transparent),
    var(--app-shadow-panel);
}

.page-heading::before {
  width: 0;
}

.page-heading::after {
  position: absolute;
  inset: 0;
  width: auto;
  content: "";
  background:
    linear-gradient(116deg, transparent 0 44%, rgba(255, 255, 255, 0.2) 44% 50%, transparent 66%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.2), transparent 44%);
  opacity: 1;
  mask-image: none;
  pointer-events: none;
}

.page-heading .page-kicker,
.page-heading .page-title,
.page-heading .page-description {
  color: #ffffff;
}

.page-heading .page-kicker::before {
  background: linear-gradient(90deg, #ffffff, var(--app-color-accent-emerald));
}

.page-heading .page-description {
  color: rgba(255, 255, 255, 0.82);
}

.settings-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.word-config-entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--app-space-4);
}

.word-config-entry {
  min-height: 130px;
  padding: var(--app-space-5);
  border-color: color-mix(in srgb, var(--app-color-primary-border) 72%, transparent);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--app-color-surface) 88%, var(--app-color-primary-soft)), var(--app-color-glass-muted)),
    var(--app-gradient-panel-depth);
  box-shadow: var(--app-shadow-panel);
}

.word-config-entry::before {
  position: absolute;
  inset: 0 0 auto;
  height: 4px;
  content: "";
  background: var(--app-gradient-accent-line);
}

.word-config-entry::after {
  width: 96px;
  opacity: 1;
}

.word-config-entry span:last-child {
  display: grid;
  gap: 4px;
}

.word-config-entry strong {
  color: inherit;
}

.word-config-entry small {
  color: var(--app-color-text-muted);
  line-height: 1.45;
}

.refresh-note {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.release-gate-workspace {
  display: grid;
  gap: var(--app-space-4);
  border-color: color-mix(in srgb, var(--app-color-accent-emerald-border) 78%, transparent);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--app-color-accent-emerald-soft) 48%, transparent), transparent 46%),
    var(--app-gradient-panel-depth);
}

.gate-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.gate-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--app-space-2);
}

.gate-status-grid article {
  position: relative;
  overflow: hidden;
  display: grid;
  gap: 5px;
  min-height: 112px;
  padding: var(--app-space-4);
  border: 1px solid color-mix(in srgb, var(--app-color-accent-emerald-border) 72%, transparent);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--app-color-accent-emerald-soft) 86%, transparent), var(--app-color-glass-strong)),
    var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
  transition:
    border-color var(--app-motion-fast) ease-out,
    box-shadow var(--app-motion-fast) ease-out,
    transform var(--app-motion-fast) var(--app-ease-out);
}

.gate-status-grid article:hover {
  border-color: var(--app-color-accent-emerald-border);
  box-shadow: var(--app-shadow-panel-hover);
  transform: translateY(-2px);
}

.gate-status-grid article::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  content: "";
  background: linear-gradient(180deg, var(--app-color-accent-emerald), var(--app-color-primary));
}

.gate-status-grid span,
.gate-status-grid strong,
.gate-status-grid small {
  display: block;
}

.gate-status-grid span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.gate-status-grid strong {
  color: var(--app-color-text);
  font-size: 20px;
  line-height: 1.2;
}

.gate-status-grid small {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.gate-action-list {
  display: grid;
  gap: 8px;
}

.gate-action-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--app-space-2);
  align-items: center;
  min-height: 44px;
  padding: var(--app-space-3);
  color: var(--app-color-text);
  transition:
    border-color 180ms ease-out,
    color 180ms ease-out,
    transform 180ms var(--app-ease-out),
    box-shadow 180ms ease-out;
}

.gate-action-item:hover {
  border-color: var(--app-color-primary-border);
  color: var(--app-color-text);
  box-shadow: var(--app-shadow-subtle);
  transform: translateY(-1px);
}

.gate-action-item span {
  overflow-wrap: anywhere;
}

.gate-action-item small,
.gate-empty {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.settings-group {
  position: relative;
  overflow: hidden;
  display: grid;
  align-content: start;
  gap: var(--app-space-4);
  min-width: 0;
  border-color: color-mix(in srgb, var(--app-color-primary-border) 70%, transparent);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--app-color-surface) 88%, var(--app-color-primary-soft)), var(--app-color-glass-muted)),
    var(--app-gradient-panel-depth);
}

.settings-group::after {
  position: absolute;
  inset: 0 0 auto;
  height: 4px;
  content: "";
  background: var(--app-gradient-accent-line);
  pointer-events: none;
}

.settings-group-header {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: var(--app-space-3);
  align-items: flex-start;
  color: var(--app-color-text);
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
  border-radius: var(--app-radius-md);
  background: var(--app-gradient-action);
  color: #ffffff;
  font-size: 20px;
  box-shadow:
    0 12px 22px color-mix(in srgb, var(--app-color-primary) 24%, transparent),
    inset 0 1px 0 rgba(255, 255, 255, 0.34);
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
  color: var(--app-color-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.group-metrics dl {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-2);
  margin: 0;
}

.group-metrics div {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--app-color-surface) 86%, var(--app-color-primary-soft)), var(--app-color-surface-muted));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.32);
}

.group-metrics dt {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.group-metrics dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
  color: var(--app-color-text);
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
  gap: var(--app-space-2);
  align-items: center;
  min-height: 42px;
  padding: 10px;
  color: var(--app-color-text);
  transition:
    border-color 180ms ease-out,
    color 180ms ease-out,
    transform 180ms var(--app-ease-out),
    box-shadow 180ms ease-out;
}

.finding-item:hover {
  border-color: var(--app-color-primary-border);
  color: var(--app-color-text);
  box-shadow: var(--app-shadow-subtle);
  transform: translateY(-1px);
}

.finding-more,
.finding-empty,
.finding-error {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.finding-error {
  color: var(--app-color-danger);
}

.settings-link {
  display: inline-flex;
  justify-content: center;
  min-height: 38px;
  padding: 9px 12px;
  border: 1px solid var(--app-color-primary);
  border-radius: var(--app-radius-md);
  background: var(--app-gradient-action);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 12px 24px color-mix(in srgb, var(--app-color-primary) 22%, transparent);
  transition:
    border-color 180ms ease-out,
    color 180ms ease-out,
    transform 180ms var(--app-ease-out),
    box-shadow 180ms ease-out;
}

.settings-link:hover {
  border-color: var(--app-color-primary);
  color: #ffffff;
  box-shadow: var(--app-shadow-panel-hover);
  transform: translateY(-2px);
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
