<!-- 文件：frontend/src/pages/OpsDashboardPage.vue -->
<!-- 用途：admin 运维状态、fake 控制与 dry-run 安全面板；数据与动作由 features/ops-dashboard 的 composable 持有。 -->
<template>
  <main class="ops-dashboard-page app-page" aria-labelledby="ops-dashboard-title">
    <WorkbenchPageHeader
      title-id="ops-dashboard-title"
      kicker="Operations"
      title="运维看板"
      description="汇总 worker、队列、readiness、存储和任务风险；任务恢复先做 registry preview，再复用既有任务动作处理。"
      wide
      section-class="page-heading app-page-header"
    >
      <template #actions>
        <el-tag :type="opsStatus.tagType" effect="plain">{{ opsStatus.label }}</el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="loadDashboard">刷新看板</el-button>
      </template>
    </WorkbenchPageHeader>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <el-alert class="app-page-shell app-page-shell--wide" type="info" title="safe operations" :closable="false" show-icon>
      此页面不会同步恢复 MinerU 结果、cleanup、真实 provider cancellation 或真实删除；文档任务 replay 只投递 Worker 或清理终态 callback。
    </el-alert>

    <WorkbenchMetricStrip
      v-loading="loading"
      label="运维摘要"
      :items="overviewItems"
      wide
      section-class="summary-grid"
    />

    <section v-if="alertItems.length" class="alert-grid app-alert-stack app-page-shell app-page-shell--wide" aria-label="运维告警和建议">
      <el-alert
        v-for="item in alertItems"
        :key="item.key"
        :type="item.alertType"
        :title="item.title"
        :closable="false"
        show-icon
      >
        <div class="alert-description">{{ item.description }}</div>
        <router-link v-if="item.to" :to="item.to">{{ item.linkText }}</router-link>
      </el-alert>
    </section>

    <OpsIntegrationControlPanel
      v-bind="{
        integrationOverallStatusTag, integrationCapabilities, readyIntegrationCapabilityCount,
        blockedIntegrationCapabilityCount, integrationCapabilityRows, integrationSafetyItems,
      }"
    />

    <OpsAlertDeliveryPanel
      v-model:alert-delivery-dedupe-window="alertDeliveryDedupeWindow"
      v-bind="{
        activeOpsAlerts, selectedActiveAlertCodes, alertDeliveryContract,
        alertDeliveryContractSafetyItems, alertDeliveryContractParityItems, allActiveAlertsSelected,
        someActiveAlertsSelected, toggleAllAlertDeliverySelection, isAlertDeliverySelected,
        toggleAlertDeliverySelection, canPreviewAlertDelivery, alertDeliveryLoading,
        previewAlertDelivery, canOpenAlertDeliveryDialog, openAlertDeliveryDialog,
      }"
    >
      <template #pilot>
        <OpsSlackPilotSection
          v-bind="{
            realAlertDeliveryPilotActive, alertDeliveryCapability, realAlertDeliveryGateText,
            realAlertDeliveryPilotItems, realAlertDeliveryRollbackItems, canPreviewRealAlertDelivery,
            alertDeliveryLoading, previewRealAlertDelivery, canOpenRealAlertDeliveryDialog,
            openRealAlertDeliveryDialog,
          }"
        />
      </template>
      <template #result>
        <OpsAlertDeliveryResult
          v-bind="{
            alertDeliveryReport, alertDeliveryTotal, alertDeliverySafetyItems,
          }"
        />
      </template>
    </OpsAlertDeliveryPanel>

    <OpsS3DeleteContractPanel
      v-bind="{
        s3DeleteContract, s3DeleteContractSafetyItems, s3DeleteLocalStackItems, s3DeleteStorageItems,
        s3DeleteContractParityItems,
      }"
    />

    <OpsAlertDestinationPanel
      v-model:alert-destination-ids-input="alertDestinationIdsInput"
      v-bind="{
        alertDestinationReport, selectedActiveAlertCodes, parsedAlertDestinationIds,
        alertDestinationLoading, dryRunAlertDestinations, alertDestinationSafetyItems,
      }"
    />

    <OpsProviderCancellationPanel
      v-bind="{
        providerCancellationForm, providerCancellationSemantics, providerCancellationReport,
        canPreviewProviderCancellation, providerCancellationLoading, previewProviderCancellation,
        canOpenProviderCancellationDialog, openProviderCancellationDialog,
      }"
    >
      <template #semantics>
        <OpsProviderSemanticsSection
          v-bind="{
            providerCancellationSemantics, providerCancellationSemanticsSafetyItems,
          }"
        />
      </template>
      <template #result>
        <OpsProviderCancellationResult
          v-bind="{
            providerCancellationReport, providerCancellationReportMatchesForm,
            providerCancellationTargetItems, providerCancellationOperationItems,
            providerCancellationTargetSummaryItems, providerCancellationSafetyItems,
          }"
        />
      </template>
    </OpsProviderCancellationPanel>

    <OpsActionSafetyPanel
      v-bind="{
        recoveryActionSummary, recoveryActions,
      }"
    />

    <OpsWorkerSystemPanels
      v-bind="{
        queueMetricItems, runtimeItems, resourceItems,
      }"
    />

    <OpsJobSamplesPanel
      v-bind="{
        failedJobs, isPreviewingJobAction, isExecutingJobAction, previewJobRecoveryAction, runningJobs,
      }"
    />

    <OpsJobRecoveryPreview
      v-bind="{
        jobRecoveryPreview, jobRecoveryTargetSummaryItems, jobRecoveryRiskItems,
        selectedJobRecoveryAction, canExecutePreviewedJobRecovery, jobRecoveryExecuting,
        executePreviewedJobRecovery,
      }"
    />

    <section class="reference-grid app-filter-panel app-page-shell app-page-shell--wide" aria-label="运维相关入口">
      <router-link to="/system-status">系统状态</router-link>
      <router-link to="/system-status/audit-events">审计日志</router-link>
      <router-link to="/system-status/file-retention">文件管理与清理</router-link>
      <router-link :to="failedJobsRoute">失败任务筛选</router-link>
      <router-link :to="runningJobsRoute">运行中任务筛选</router-link>
    </section>

    <OpsDialogs
      v-bind="{
        alertDeliveryDialog, selectedActiveAlertCodes, alertDeliveryConfirmationPhrase,
        canFakeSendAlertDelivery, alertDeliveryLoading, fakeSendAlertDelivery, realAlertDeliveryDialog,
        canRealSendAlertDelivery, realSendAlertDelivery, providerCancellationDialog,
        providerCancellationDialogTarget, providerCancellationDialogOperation,
        providerCancellationConfirmationPhrase, canFakeCancelProviderCancellation,
        providerCancellationLoading, fakeCancelProviderCancellation,
      }"
    />
  </main>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { Refresh } from "@element-plus/icons-vue";

import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import WorkbenchMetricStrip from "@/components/WorkbenchMetricStrip.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import OpsActionSafetyPanel from "@/features/ops-dashboard/OpsActionSafetyPanel.vue";
import OpsAlertDeliveryPanel from "@/features/ops-dashboard/OpsAlertDeliveryPanel.vue";
import OpsAlertDeliveryResult from "@/features/ops-dashboard/OpsAlertDeliveryResult.vue";
import OpsAlertDestinationPanel from "@/features/ops-dashboard/OpsAlertDestinationPanel.vue";
import OpsDialogs from "@/features/ops-dashboard/OpsDialogs.vue";
import OpsIntegrationControlPanel from "@/features/ops-dashboard/OpsIntegrationControlPanel.vue";
import OpsJobRecoveryPreview from "@/features/ops-dashboard/OpsJobRecoveryPreview.vue";
import OpsJobSamplesPanel from "@/features/ops-dashboard/OpsJobSamplesPanel.vue";
import OpsProviderCancellationPanel from "@/features/ops-dashboard/OpsProviderCancellationPanel.vue";
import OpsProviderCancellationResult from "@/features/ops-dashboard/OpsProviderCancellationResult.vue";
import OpsProviderSemanticsSection from "@/features/ops-dashboard/OpsProviderSemanticsSection.vue";
import OpsS3DeleteContractPanel from "@/features/ops-dashboard/OpsS3DeleteContractPanel.vue";
import OpsSlackPilotSection from "@/features/ops-dashboard/OpsSlackPilotSection.vue";
import OpsWorkerSystemPanels from "@/features/ops-dashboard/OpsWorkerSystemPanels.vue";
import { failedJobsRoute, runningJobsRoute } from "@/features/ops-dashboard/opsDashboardFormat";
import { useOpsAlertDelivery } from "@/features/ops-dashboard/useOpsAlertDelivery";
import { useOpsAlertDestination } from "@/features/ops-dashboard/useOpsAlertDestination";
import { useOpsDashboardData } from "@/features/ops-dashboard/useOpsDashboardData";
import { useOpsHealthView } from "@/features/ops-dashboard/useOpsHealthView";
import { useOpsJobRecovery } from "@/features/ops-dashboard/useOpsJobRecovery";
import { useProviderCancellation } from "@/features/ops-dashboard/useProviderCancellation";

const data = useOpsDashboardData({
  onActiveAlertCodesLoaded: (codes) => alertDelivery.pruneAlertDeliverySelection(codes),
});
const healthView = useOpsHealthView(data);
const alertDelivery = useOpsAlertDelivery(data);
const alertDestination = useOpsAlertDestination(data, alertDelivery);
const providerCancellation = useProviderCancellation(data);
const jobRecovery = useOpsJobRecovery(data);
const {
  integrationCapabilities, recoveryActions, failedJobs, runningJobs, loading, error, alertDeliveryContract,
  s3DeleteContract, providerCancellationSemantics, activeOpsAlerts, integrationCapabilityRows,
  readyIntegrationCapabilityCount, blockedIntegrationCapabilityCount, integrationOverallStatusTag,
  integrationSafetyItems, recoveryActionSummary, loadDashboard,
} = data;
const {
  overviewItems, opsStatus, alertItems, queueMetricItems, runtimeItems, resourceItems,
  s3DeleteContractSafetyItems, s3DeleteLocalStackItems, s3DeleteStorageItems, s3DeleteContractParityItems,
} = healthView;
const {
  alertDeliveryDedupeWindow, alertDeliveryLoading, alertDeliveryReport, alertDeliveryDialog,
  realAlertDeliveryDialog, selectedActiveAlertCodes, alertDeliveryCapability, realAlertDeliveryPilotActive,
  realAlertDeliveryGateText, allActiveAlertsSelected, someActiveAlertsSelected,
  alertDeliveryConfirmationPhrase, canPreviewAlertDelivery, canOpenAlertDeliveryDialog,
  canFakeSendAlertDelivery, canPreviewRealAlertDelivery, canOpenRealAlertDeliveryDialog,
  canRealSendAlertDelivery, alertDeliverySafetyItems, realAlertDeliveryPilotItems,
  realAlertDeliveryRollbackItems, alertDeliveryContractSafetyItems, alertDeliveryContractParityItems,
  isAlertDeliverySelected, toggleAlertDeliverySelection, toggleAllAlertDeliverySelection,
  previewAlertDelivery, openAlertDeliveryDialog, fakeSendAlertDelivery, previewRealAlertDelivery,
  openRealAlertDeliveryDialog, realSendAlertDelivery, alertDeliveryTotal,
} = alertDelivery;
const {
  alertDestinationIdsInput, alertDestinationLoading, alertDestinationReport, parsedAlertDestinationIds,
  alertDestinationSafetyItems, dryRunAlertDestinations,
} = alertDestination;
const {
  providerCancellationForm, providerCancellationLoading, providerCancellationReport,
  providerCancellationDialog, providerCancellationSemanticsSafetyItems,
  providerCancellationConfirmationPhrase, providerCancellationReportMatchesForm,
  canPreviewProviderCancellation, canOpenProviderCancellationDialog, canFakeCancelProviderCancellation,
  providerCancellationTargetItems, providerCancellationOperationItems,
  providerCancellationTargetSummaryItems, providerCancellationSafetyItems, providerCancellationDialogTarget,
  providerCancellationDialogOperation, previewProviderCancellation, openProviderCancellationDialog,
  fakeCancelProviderCancellation,
} = providerCancellation;
const {
  jobRecoveryPreview, selectedJobRecoveryAction, jobRecoveryExecuting, jobRecoveryRiskItems,
  jobRecoveryTargetSummaryItems, canExecutePreviewedJobRecovery, isPreviewingJobAction, isExecutingJobAction,
  previewJobRecoveryAction, executePreviewedJobRecovery,
} = jobRecovery;

onMounted(() => {
  void loadDashboard();
});
</script>

<style scoped lang="scss">
.ops-dashboard-page {
  display: grid;
  gap: var(--app-space-4);
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.heading-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.summary-grid {
  display: grid;
  gap: var(--app-space-4);
}

.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.summary-card {
  min-height: 118px;
}

.summary-card strong {
  font-size: 22px;
}

.status-card strong {
  font-size: 24px;
}

.alert-description {
  margin: 0 0 var(--app-space-2);
}

.reference-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-3);
}

@media (max-width: 1100px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading,
  .heading-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
