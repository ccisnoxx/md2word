<template>
  <el-drawer
    :model-value="drawerVisible"
    class="incident-diagnostic-drawer"
    direction="rtl"
    :size="drawerSize"
    :with-header="false"
    :destroy-on-close="false"
    append-to-body
    @update:model-value="handleDrawerModelValue"
  >
    <WorkbenchDrawerSurface
      label="异常诊断"
      kicker="异常诊断"
      :title="diagnosticTitle"
      :subtitle="diagnostic?.item?.suggested_action || ''"
      root-class="diagnostic-panel"
    >
      <template #actions>
        <el-button text @click="closeDiagnostic">关闭</el-button>
      </template>
      <ApiErrorAlert :error="drawerError" :diagnostic-context="drawerErrorDiagnosticContext" />
      <section v-if="drawerError && !drawerLoading && !diagnostic" class="diagnostic-section diagnostic-recovery-state" aria-live="assertive">
        <h3>诊断加载失败</h3>
        <p>当前无法读取该异常的诊断详情。可刷新诊断、打开任务详情，或关闭抽屉返回列表。</p>
        <div class="drawer-actions">
          <el-button :loading="drawerLoading" @click="refreshDiagnostic">刷新诊断</el-button>
          <el-button :disabled="!selectedIncidentJobId" @click="openSelectedJobDetail">打开详情</el-button>
          <el-button text @click="closeDiagnostic">返回列表</el-button>
        </div>
      </section>
      <div v-if="drawerLoading" class="drawer-loading">诊断加载中...</div>
      <template v-else-if="diagnostic">
        <EvidenceSurfaceSection title="诊断摘要" root-class="diagnostic-section">
          <div class="diagnostic-summary">
            <div>
              <span>失败类型</span>
              <strong>{{ incidentFailureTypeText[diagnostic.item.failure_type] }}</strong>
            </div>
            <div>
              <span>重试性</span>
              <strong>{{ diagnostic.item.retryable ? "可重试" : diagnostic.item.retry_disabled_reason || "不可重试" }}</strong>
            </div>
            <div>
              <span>状态/阶段</span>
              <strong>{{ jobStatusText[diagnostic.item.job.status] }} / {{ stageLabel(diagnostic.item) }}</strong>
            </div>
            <div>
              <span>重试次数</span>
              <strong>{{ diagnostic.item.job.retry_count }}</strong>
            </div>
          </div>
        </EvidenceSurfaceSection>

        <EvidenceSurfaceSection title="下一步建议" root-class="diagnostic-section">
          <el-alert
            v-if="incidentDiagnosticGuidance"
            class="incident-guidance-alert"
            :type="incidentDiagnosticGuidance.type"
            :closable="false"
            show-icon
            :title="incidentDiagnosticGuidance.title"
          >
            <p>{{ incidentDiagnosticGuidance.description }}</p>
            <ul>
              <li v-for="bullet in incidentDiagnosticGuidance.bullets" :key="bullet">{{ bullet }}</li>
            </ul>
          </el-alert>
        </EvidenceSurfaceSection>

        <EvidenceSurfaceSection
          title="关键证据"
          description="先看任务标识、错误摘要和 trace，再看后端证据标签。"
          root-class="diagnostic-section"
        >
          <EvidenceKeyValueList class="evidence-list" :items="incidentKeyEvidenceItems" />
          <div class="evidence-chips">
            <el-tag v-for="entry in diagnostic.item.evidence_summary" :key="entry" effect="plain">{{ entry }}</el-tag>
            <el-tag v-if="!diagnostic.item.evidence_summary.length" effect="plain">暂无后端证据摘要</el-tag>
          </div>
        </EvidenceSurfaceSection>

        <EvidenceSurfaceSection
          title="事件时间线"
          description="优先查看最近 warning / error 事件，确认失败发生点和 trace。"
          root-class="diagnostic-section"
        >
          <ol class="event-list">
            <li v-for="event in diagnostic.recent_events" :key="event.id" :class="`is-${event.level}`">
              <span class="event-meta">{{ formatDateTime(event.created_at) }} · {{ event.level }} · {{ eventStageLabel(event.stage) }}</span>
              <strong>{{ event.event_type }}</strong>
              <p>{{ event.message }}</p>
              <small v-if="event.trace_id" class="mono">trace_id={{ event.trace_id }}</small>
            </li>
          </ol>
          <el-empty v-if="!diagnostic.recent_events.length" class="compact-diagnostic-empty" description="暂无最近事件；可刷新诊断或打开详情查看完整事件流" />
        </EvidenceSurfaceSection>

        <EvidenceSurfaceSection
          title="文件与入口"
          description="抽屉只给出最短诊断路径；更深层内容跳转到完整详情页。"
          root-class="diagnostic-section"
        >
          <div class="evidence-links">
            <RouterLink
              v-for="link in diagnostic.evidence_links"
              :key="link.kind"
              class="evidence-link"
              :class="{ 'is-disabled': !link.available }"
              :to="link.target"
            >
              <strong>{{ evidenceLinkTitle(link) }}</strong>
              <span>{{ link.available ? link.helper || link.target : link.helper || '当前入口不可用' }}</span>
            </RouterLink>
          </div>
          <div class="file-list">
            <div v-for="file in diagnostic.files" :key="file.file_id" class="file-row">
              <span class="mono">{{ file.file_id }}</span>
              <strong>{{ file.file_type || "-" }}</strong>
              <span>{{ file.status || "-" }}</span>
              <small>{{ file.original_filename || "-" }}</small>
            </div>
          </div>
          <el-empty v-if="!diagnostic.files.length" class="compact-diagnostic-empty" description="暂无文件摘要；可打开任务详情查看完整文件列表" />
        </EvidenceSurfaceSection>
      </template>

      <template #footer>
        <div class="drawer-footer">
        <div class="drawer-footer-copy">
          <strong>操作</strong>
          <ShortcutHintList :items="incidentDrawerShortcutHints" />
        </div>
        <div class="drawer-actions">
          <el-button @click="refreshDiagnostic">刷新诊断</el-button>
          <el-button v-if="diagnostic?.item" @click="openJobDetail(diagnostic.item)">打开详情</el-button>
          <el-button
            v-if="diagnostic?.item"
            type="warning"
            :disabled="!diagnostic.item.retryable"
            :loading="actionPending[diagnostic.item.job.id] === 'retry'"
            @click="handleSingleRetry(diagnostic.item)"
          >
            重试
          </el-button>
        </div>
        </div>
      </template>
    </WorkbenchDrawerSurface>
  </el-drawer>
</template>

<script setup lang="ts">
import type { UnwrapRef } from "vue";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import EvidenceKeyValueList from "@/components/EvidenceKeyValueList.vue";
import EvidenceSurfaceSection from "@/components/EvidenceSurfaceSection.vue";
import ShortcutHintList from "@/components/ShortcutHintList.vue";
import WorkbenchDrawerSurface from "@/components/WorkbenchDrawerSurface.vue";
import { formatDateTime, jobStatusText } from "@/utils/format";
import { incidentFailureTypeText } from "@/utils/incidents";
import { eventStageLabel, evidenceLinkTitle, stageLabel } from "./incidentQuery";
import { incidentDrawerShortcutHints } from "./useIncidentShortcuts";
import type { IncidentActions } from "./useIncidentActions";
import type { IncidentDiagnostic } from "./useIncidentDiagnostic";

const {
  drawerVisible,
  drawerSize,
  drawerLoading,
  drawerError,
  diagnostic,
  diagnosticTitle,
  selectedIncidentJobId,
  drawerErrorDiagnosticContext,
  incidentDiagnosticGuidance,
  incidentKeyEvidenceItems,
  actionPending,
  handleDrawerModelValue,
  closeDiagnostic,
  refreshDiagnostic,
  openSelectedJobDetail,
  openJobDetail,
  handleSingleRetry,
} = defineProps<{
  drawerVisible: UnwrapRef<IncidentDiagnostic["drawerVisible"]>;
  drawerSize: IncidentDiagnostic["drawerSize"];
  drawerLoading: UnwrapRef<IncidentDiagnostic["drawerLoading"]>;
  drawerError: UnwrapRef<IncidentDiagnostic["drawerError"]>;
  diagnostic: UnwrapRef<IncidentDiagnostic["diagnostic"]>;
  diagnosticTitle: UnwrapRef<IncidentDiagnostic["diagnosticTitle"]>;
  selectedIncidentJobId: UnwrapRef<IncidentDiagnostic["selectedIncidentJobId"]>;
  drawerErrorDiagnosticContext: UnwrapRef<IncidentDiagnostic["drawerErrorDiagnosticContext"]>;
  incidentDiagnosticGuidance: UnwrapRef<IncidentDiagnostic["incidentDiagnosticGuidance"]>;
  incidentKeyEvidenceItems: UnwrapRef<IncidentDiagnostic["incidentKeyEvidenceItems"]>;
  actionPending: UnwrapRef<IncidentActions["actionPending"]>;
  handleDrawerModelValue: IncidentDiagnostic["handleDrawerModelValue"];
  closeDiagnostic: IncidentDiagnostic["closeDiagnostic"];
  refreshDiagnostic: IncidentDiagnostic["refreshDiagnostic"];
  openSelectedJobDetail: IncidentDiagnostic["openSelectedJobDetail"];
  openJobDetail: IncidentDiagnostic["openJobDetail"];
  handleSingleRetry: IncidentActions["handleSingleRetry"];
}>();
</script>

<style scoped lang="scss">
.drawer-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--app-space-2);
}

.evidence-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.diagnostic-panel {
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: var(--app-space-4);
  min-height: 100%;
  padding: 20px;
}

.drawer-header,
.drawer-footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-3);
}

.drawer-header h2 {
  margin: 0;
  font-size: 22px;
}

.drawer-subtitle {
  margin: 4px 0 0;
  color: var(--app-color-text-muted);
}

.drawer-footer-copy {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.drawer-footer-copy strong {
  color: var(--app-color-text);
}

.drawer-loading {
  color: var(--app-color-text-muted);
}

.diagnostic-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-2);
}

.diagnostic-summary div,
.diagnostic-section {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
}

.diagnostic-summary span {
  display: block;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.diagnostic-summary strong {
  display: block;
  margin-top: 4px;
  overflow-wrap: anywhere;
}

.diagnostic-section {
  display: grid;
  gap: var(--app-space-2);
}

.diagnostic-section h3 {
  margin: 0;
  font-size: 15px;
}

.diagnostic-recovery-state p,
.incident-guidance-alert p,
.incident-guidance-alert ul {
  margin: 4px 0 0;
}

.incident-guidance-alert ul {
  padding-left: 18px;
}

.incident-guidance-alert li {
  margin-top: 2px;
}

.evidence-list {
  display: grid;
  gap: 8px;
  margin: 0;
}

.evidence-list div {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 10px;
}

.evidence-list dt {
  color: var(--app-color-text-muted);
}

.evidence-list dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.evidence-links {
  display: grid;
  gap: 8px;
}

.evidence-link {
  display: grid;
  gap: 2px;
  padding: 10px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  color: inherit;
  text-decoration: none;
}

.evidence-link span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.evidence-link.is-disabled {
  opacity: 0.55;
}

.event-list {
  display: grid;
  gap: 10px;
  padding-left: 18px;
  margin: 0;
}

.event-list li {
  padding: 8px;
  border: 1px solid var(--app-color-border-soft);
  border-left: 3px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
}

.event-list li.is-error {
  border-left-color: var(--el-color-danger);
}

.event-list li.is-warning {
  border-left-color: var(--el-color-warning);
}

.event-list p {
  margin: 2px 0 0;
}

.event-list small {
  display: block;
  margin-top: 3px;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.event-meta {
  display: block;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.file-list {
  display: grid;
  gap: 6px;
}

.file-row {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) 110px 92px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  padding: 8px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
}

.file-row small {
  overflow: hidden;
  color: var(--app-color-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-diagnostic-empty {
  padding: 8px 0 0;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

@media (max-width: 900px) {
  .drawer-header,
  .drawer-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .diagnostic-summary {
    grid-template-columns: 1fr 1fr;
  }

  .file-row,
  .evidence-list div {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .diagnostic-summary {
    grid-template-columns: 1fr;
  }
}
</style>
