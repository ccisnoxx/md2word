<!-- frontend/src/pages/SettingsHomePage.vue: Configuration workbench landing page and release gate. -->
<template>
  <main class="settings-page" aria-labelledby="settings-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Config Workbench</p>
        <h1 id="settings-title">配置工作台</h1>
        <p>统一查看生产运行门禁、默认配置版本、draft 和待处理治理事项。</p>
      </div>
      <RoleGate>
        <el-tag type="warning" effect="plain">admin 操作已启用</el-tag>
      </RoleGate>
    </section>

    <ConfigTodoSummary :summary="summary" :loading="loading" :error="error" @refresh="loadSummary" />

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
          <el-tag :type="statusTagType(group.status)" effect="plain">
            {{ statusLabel(group.status) }}
          </el-tag>
        </header>

        <div class="group-metrics">
          <dl>
            <div>
              <dt>默认版本</dt>
              <dd>{{ group.default_label || "-" }}</dd>
            </div>
            <div>
              <dt>Draft</dt>
              <dd>{{ group.draft_count ?? "-" }}</dd>
            </div>
            <div>
              <dt>Pending</dt>
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
              {{ finding.severity }}
            </el-tag>
            <span>{{ finding.message }}</span>
          </router-link>
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
import { onMounted, ref } from "vue";
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
  type ConfigWorkbenchSeverity,
  type ConfigWorkbenchStatus,
  type ConfigWorkbenchSummaryResponse,
} from "@/api/configSummary";
import ConfigTodoSummary from "@/components/ConfigTodoSummary.vue";
import RoleGate from "@/components/RoleGate.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const summary = ref<ConfigWorkbenchSummaryResponse | null>(null);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);

const iconMap = {
  runtime_readiness: Cpu,
  templates: Files,
  term_rule_sets: Collection,
  translation_profiles: DocumentChecked,
  translation_term_sets: Tickets,
} satisfies Record<ConfigWorkbenchGroupId, unknown>;

async function loadSummary(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    summary.value = await configSummaryApi.get();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
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

function statusLabel(status: ConfigWorkbenchStatus): string {
  const labels: Record<ConfigWorkbenchStatus, string> = {
    ready: "Ready",
    warning: "Warning",
    blocked: "Blocked",
    unavailable: "Unavailable",
  };
  return labels[status];
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

function severityTagType(severity: ConfigWorkbenchSeverity): "success" | "warning" | "danger" | "info" {
  if (severity === "critical") {
    return "danger";
  }
  if (severity === "warning") {
    return "warning";
  }
  return "info";
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
.finding-empty {
  color: #667085;
  font-size: 13px;
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
  .settings-group-header {
    align-items: flex-start;
  }

  .page-heading {
    flex-direction: column;
  }

  .settings-group-header {
    grid-template-columns: 42px minmax(0, 1fr);
  }

  .settings-group-header .el-tag {
    grid-column: 1 / -1;
    justify-self: start;
  }

  .group-metrics dl {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .group-metrics dl {
    grid-template-columns: 1fr;
  }
}
</style>
