<!-- File: frontend/src/pages/OpsDashboardPage.vue -->
<!-- Purpose: Render Admin-only operations status, fake controls, and dry-run safety panels. -->
<template>
  <main class="ops-dashboard-page" aria-labelledby="ops-dashboard-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Operations</p>
        <h1 id="ops-dashboard-title">运维看板</h1>
        <p>只读汇总 worker、队列、readiness、存储和任务风险；恢复动作仍需在既有任务页面或外部流程中处理。</p>
      </div>
      <div class="heading-actions">
        <el-tag :type="opsStatus.tagType" effect="plain">{{ opsStatus.label }}</el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="loadDashboard">刷新看板</el-button>
      </div>
    </section>

    <ApiErrorAlert :error="error" />

    <el-alert type="info" title="read-only" :closable="false" show-icon>
      此页面只调用 health、document-jobs 和 recovery action registry 读取接口，不提供重试、取消、归档、恢复 MinerU 结果、cleanup 或真实删除操作。
    </el-alert>

    <section v-loading="loading" class="summary-grid" aria-label="运维摘要">
      <article class="summary-card status-card" :class="`is-${opsStatus.key}`">
        <span class="status-dot" aria-hidden="true"></span>
        <div>
          <span>整体状态</span>
          <strong>{{ opsStatus.label }}</strong>
          <small>{{ opsStatus.description }}</small>
        </div>
      </article>

      <article class="summary-card">
        <span>Worker</span>
        <strong>{{ workerMode }}</strong>
        <small>dispatcher: {{ stageDispatcher }}</small>
      </article>

      <article class="summary-card">
        <span>Stage queue</span>
        <strong>{{ queuePressureLabel }}</strong>
        <small>failed {{ stageFailedCount }} · stale {{ staleRunningCount }} · replayable {{ replayableCount }}</small>
      </article>

      <article class="summary-card">
        <span>Document jobs</span>
        <strong>{{ failedJobsTotal }} / {{ runningJobsTotal }}</strong>
        <small>失败 / 运行中样例来自 document-jobs 只读列表</small>
      </article>
    </section>

    <section v-if="alertItems.length" class="alert-grid" aria-label="运维告警和建议">
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

    <section class="alert-delivery-panel" aria-label="告警 fake outbox 投递">
      <el-card class="card-flat dashboard-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Alert Delivery Fake Outbox</h2>
            <p class="section-subtitle">只记录 local outbox fake delivery audit，不发送 Slack、email 或 webhook。</p>
          </div>
          <div class="toolbar">
            <el-tag effect="plain">active={{ activeOpsAlerts.length }}</el-tag>
            <el-tag effect="plain" type="info">selected={{ selectedActiveAlertCodes.length }}</el-tag>
          </div>
        </div>

        <el-alert class="delivery-warning" type="warning" title="fake delivery only" :closable="false" show-icon>
          Fake-send 会写入 <span class="mono">ops.alert_delivery_fake</span> audit；后端 safety metadata 会保持 external delivery 为 false。
        </el-alert>

        <div class="alert-delivery-layout">
          <div class="alert-delivery-list">
            <div class="delivery-selection-bar">
              <el-checkbox
                :model-value="allActiveAlertsSelected"
                :indeterminate="someActiveAlertsSelected"
                :disabled="activeOpsAlerts.length === 0"
                @change="toggleAllAlertDeliverySelection(Boolean($event))"
              >
                选择全部当前告警
              </el-checkbox>
              <span>{{ selectedActiveAlertCodes.length }} / {{ activeOpsAlerts.length }}</span>
            </div>

            <el-table :data="activeOpsAlerts" empty-text="暂无 active ops alerts" table-layout="fixed" class="delivery-alert-table">
              <el-table-column label="" width="54">
                <template #default="{ row }">
                  <el-checkbox
                    :model-value="isAlertDeliverySelected(row.code)"
                    :aria-label="`select ${row.code}`"
                    @change="toggleAlertDeliverySelection(row.code, Boolean($event))"
                  />
                </template>
              </el-table-column>
              <el-table-column label="Alert" min-width="240">
                <template #default="{ row }">
                  <div class="action-title">
                    <span class="mono">{{ row.code }}</span>
                    <small>{{ row.title }}</small>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="Severity" width="110">
                <template #default="{ row }">
                  <el-tag size="small" :type="opsAlertSeverityTagType(row.severity)" effect="plain">{{ row.severity }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="source" label="Source" min-width="120" />
              <el-table-column prop="count" label="Count" width="90" />
              <el-table-column prop="suggested_action" label="Suggested Action" min-width="260" show-overflow-tooltip />
            </el-table>
          </div>

          <aside class="alert-delivery-controls">
            <el-form label-position="top">
              <el-form-item label="Channel">
                <el-input model-value="local_outbox" readonly />
              </el-form-item>
              <el-form-item label="Dedupe Window">
                <el-input-number
                  v-model="alertDeliveryDedupeWindow"
                  :min="1"
                  :max="1440"
                  :step="15"
                  controls-position="right"
                />
                <span class="field-hint">minutes</span>
              </el-form-item>
            </el-form>

            <div class="delivery-actions">
              <el-button
                :icon="View"
                :disabled="!canPreviewAlertDelivery"
                :loading="alertDeliveryLoading"
                @click="previewAlertDelivery"
              >
                预览 fake outbox
              </el-button>
              <el-button
                type="warning"
                :icon="Bell"
                :disabled="!canOpenAlertDeliveryDialog"
                :loading="alertDeliveryLoading"
                @click="openAlertDeliveryDialog"
              >
                Fake-send
              </el-button>
            </div>
          </aside>
        </div>

        <section v-if="alertDeliveryReport" class="alert-delivery-result" aria-label="告警 fake outbox 结果">
          <div class="section-header">
            <div>
              <h3 class="section-title">Delivery Result</h3>
              <p class="section-subtitle">
                {{ alertDeliveryReport.action_mode }} · {{ alertDeliveryReport.delivery_id }} ·
                generated {{ formatDateTime(alertDeliveryReport.generated_at) }}
              </p>
            </div>
            <div class="toolbar">
              <el-tag effect="plain">requested={{ alertDeliveryTotal("requested") }}</el-tag>
              <el-tag effect="plain" type="success">fake={{ alertDeliveryTotal("fake_delivered") }}</el-tag>
              <el-tag effect="plain" type="warning">deduped={{ alertDeliveryTotal("deduped") }}</el-tag>
              <el-tag effect="plain" type="danger">failed={{ alertDeliveryTotal("failed") }}</el-tag>
            </div>
          </div>

          <el-descriptions class="delivery-safety" :column="3" border size="small">
            <el-descriptions-item v-for="item in alertDeliverySafetyItems" :key="item.label" :label="item.label">
              <span class="mono">{{ item.value }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <el-table :data="alertDeliveryReport.items" empty-text="暂无 fake delivery 结果" table-layout="fixed" class="delivery-result-table">
            <el-table-column prop="alert_code" label="Alert Code" min-width="230">
              <template #default="{ row }"><span class="mono">{{ row.alert_code }}</span></template>
            </el-table-column>
            <el-table-column prop="outcome" label="Outcome" min-width="150">
              <template #default="{ row }">
                <el-tag size="small" :type="alertDeliveryOutcomeTag(row.outcome)" effect="plain">{{ row.outcome }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="audit_event_written" label="Audit" width="110">
              <template #default="{ row }">{{ row.audit_event_written ? "written" : "no" }}</template>
            </el-table-column>
            <el-table-column prop="dedupe_key" label="Dedupe Key" min-width="240">
              <template #default="{ row }"><span class="mono">{{ row.dedupe_key || "-" }}</span></template>
            </el-table-column>
            <el-table-column prop="reason" label="Reason" min-width="280" show-overflow-tooltip />
          </el-table>
        </section>
      </el-card>
    </section>

    <section class="alert-destination-panel" aria-label="告警 destination 配置 dry-run">
      <el-card class="card-flat dashboard-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Alert Destination Config Dry Run</h2>
            <p class="section-subtitle">只校验 staged Slack/email/webhook destination 配置，不发送外部通知、不读取 secret value。</p>
          </div>
          <div class="toolbar">
            <el-tag effect="plain">configured={{ alertDestinationReport?.configured_count ?? "-" }}</el-tag>
            <el-tag effect="plain" type="info">selected={{ alertDestinationReport?.selected_count ?? "-" }}</el-tag>
          </div>
        </div>

        <el-alert class="delivery-warning" type="info" title="config dry-run only" :closable="false" show-icon>
          Dry-run 可用当前已选择的 active alert codes 校验 allowlist；即使 destination enabled=true，真实 Slack/email/webhook delivery 仍未实现。
        </el-alert>

        <div class="alert-destination-layout">
          <el-form class="alert-destination-form" label-position="top">
            <el-form-item label="Alert codes">
              <el-input
                :model-value="selectedActiveAlertCodes.join('\n')"
                type="textarea"
                :rows="3"
                readonly
                class="mono"
                placeholder="未选择时仅检查 destination config"
              />
            </el-form-item>
            <el-form-item label="Destination IDs">
              <el-input
                v-model="alertDestinationIdsInput"
                type="textarea"
                :rows="3"
                class="mono"
                placeholder="可选；逗号或换行分隔。留空表示全部 configured destinations。"
              />
            </el-form-item>
          </el-form>

          <aside class="alert-destination-controls">
            <div class="metric-row">
              <span>request alerts</span>
              <strong>{{ selectedActiveAlertCodes.length }}</strong>
            </div>
            <div class="metric-row">
              <span>destination ids</span>
              <strong>{{ parsedAlertDestinationIds.length || "all" }}</strong>
            </div>
            <div class="delivery-actions">
              <el-button
                :icon="View"
                :loading="alertDestinationLoading"
                @click="dryRunAlertDestinations"
              >
                Dry-run destinations
              </el-button>
            </div>
          </aside>
        </div>

        <section v-if="alertDestinationReport" class="alert-destination-result" aria-label="Alert destination dry-run 结果">
          <div class="section-header">
            <div>
              <h3 class="section-title">Destination Dry Run Result</h3>
              <p class="section-subtitle">
                {{ alertDestinationReport.action_mode }} · generated {{ formatDateTime(alertDestinationReport.generated_at) }}
              </p>
            </div>
            <div class="toolbar">
              <el-tag effect="plain">requested_alerts={{ alertDestinationReport.requested_alert_codes.length }}</el-tag>
              <el-tag effect="plain" type="warning">errors={{ alertDestinationReport.config_errors.length }}</el-tag>
            </div>
          </div>

          <el-alert
            v-if="alertDestinationReport.config_errors.length"
            class="delivery-warning"
            type="warning"
            title="config errors"
            :closable="false"
            show-icon
          >
            <ul class="compact-list">
              <li v-for="configError in alertDestinationReport.config_errors" :key="configError">{{ configError }}</li>
            </ul>
          </el-alert>

          <el-descriptions class="delivery-safety" :column="4" border size="small">
            <el-descriptions-item v-for="item in alertDestinationSafetyItems" :key="item.label" :label="item.label">
              <span class="mono">{{ item.value }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <el-table :data="alertDestinationReport.destinations" empty-text="暂无 destination dry-run 结果" table-layout="fixed" class="delivery-result-table">
            <el-table-column prop="destination_id" label="Destination" min-width="200">
              <template #default="{ row }"><span class="mono">{{ row.destination_id }}</span></template>
            </el-table-column>
            <el-table-column prop="channel" label="Channel" width="110" />
            <el-table-column prop="status" label="Status" min-width="140">
              <template #default="{ row }">
                <el-tag size="small" :type="alertDestinationStatusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="enabled" label="Enabled" width="100">
              <template #default="{ row }">{{ booleanLabel(row.enabled) }}</template>
            </el-table-column>
            <el-table-column prop="secret_ref" label="Secret Ref" min-width="190">
              <template #default="{ row }"><span class="mono">{{ row.secret_ref || "-" }}</span></template>
            </el-table-column>
            <el-table-column prop="target_label" label="Target" min-width="160" show-overflow-tooltip />
            <el-table-column label="Allowlist Match" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                match={{ row.matched_alert_codes.length }} / blocked={{ row.blocked_alert_codes.length }}
              </template>
            </el-table-column>
            <el-table-column label="Gates" min-width="300" show-overflow-tooltip>
              <template #default="{ row }">{{ row.missing_gates.join(" / ") || "none" }}</template>
            </el-table-column>
          </el-table>
        </section>
      </el-card>
    </section>

    <section class="provider-cancellation-panel" aria-label="Provider cancellation fake control">
      <el-card class="card-flat dashboard-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Provider Cancellation Fake Control</h2>
            <p class="section-subtitle">只预览或记录 MinerU fake cancellation audit，不调用真实 provider，也不改变本地任务状态。</p>
          </div>
          <div class="toolbar">
            <el-tag effect="plain">{{ providerCancellationForm.targetType }}</el-tag>
            <el-tag effect="plain" type="info">provider={{ providerCancellationForm.provider }}</el-tag>
          </div>
        </div>

        <el-alert class="delivery-warning" type="warning" title="fake cancellation only" :closable="false" show-icon>
          Fake-cancel 只会在目标 eligible 且未 dedupe 时写入
          <span class="mono">ops.provider_cancellation_fake</span> audit；不会取消 MinerU 任务、不会修改 document job 或 queue。
        </el-alert>

        <div class="provider-cancellation-layout">
          <el-form class="provider-cancellation-form" label-position="top">
            <el-form-item label="Target Type">
              <el-select v-model="providerCancellationForm.targetType">
                <el-option label="document_job" value="document_job" />
                <el-option label="legacy_job" value="legacy_job" />
              </el-select>
            </el-form-item>
            <el-form-item label="Target ID">
              <el-input
                v-model.trim="providerCancellationForm.targetId"
                placeholder="输入精确 document job 或 legacy job ID"
                clearable
                class="mono"
              />
            </el-form-item>
            <el-form-item label="Provider">
              <el-input :model-value="providerCancellationForm.provider" readonly />
            </el-form-item>
            <el-form-item label="Dedupe Window">
              <el-input-number
                v-model="providerCancellationForm.dedupeWindowMinutes"
                :min="1"
                :max="1440"
                :step="15"
                controls-position="right"
              />
              <span class="field-hint">minutes</span>
            </el-form-item>
          </el-form>

          <aside class="provider-cancellation-controls">
            <div class="metric-row">
              <span>preview</span>
              <strong>{{ providerCancellationReport ? providerCancellationReport.outcome : "not run" }}</strong>
            </div>
            <div class="metric-row">
              <span>eligible</span>
              <strong>{{ providerCancellationReport ? booleanLabel(providerCancellationReport.eligible) : "not reported" }}</strong>
            </div>
            <div class="delivery-actions">
              <el-button
                :icon="View"
                :disabled="!canPreviewProviderCancellation"
                :loading="providerCancellationLoading"
                @click="previewProviderCancellation"
              >
                预览 fake cancellation
              </el-button>
              <el-button
                type="warning"
                :icon="CircleClose"
                :disabled="!canOpenProviderCancellationDialog"
                :loading="providerCancellationLoading"
                @click="openProviderCancellationDialog"
              >
                Fake-cancel
              </el-button>
            </div>
          </aside>
        </div>

        <section
          v-if="providerCancellationReport"
          class="provider-cancellation-result"
          aria-label="Provider cancellation fake 结果"
        >
          <div class="section-header">
            <div>
              <h3 class="section-title">Provider Cancellation Result</h3>
              <p class="section-subtitle">
                {{ providerCancellationReport.action_mode }} · {{ providerCancellationReport.provider }} ·
                generated {{ formatDateTime(providerCancellationReport.generated_at) }}
              </p>
            </div>
            <div class="toolbar">
              <el-tag :type="providerCancellationOutcomeTag(providerCancellationReport.outcome)" effect="plain">
                {{ providerCancellationReport.outcome }}
              </el-tag>
              <el-tag :type="providerCancellationReport.eligible ? 'success' : 'warning'" effect="plain">
                eligible={{ booleanLabel(providerCancellationReport.eligible) }}
              </el-tag>
              <el-tag :type="providerCancellationReport.audit_event_written ? 'success' : 'info'" effect="plain">
                audit={{ providerCancellationReport.audit_event_written ? "written" : "no" }}
              </el-tag>
            </div>
          </div>

          <el-alert
            v-if="!providerCancellationReportMatchesForm"
            class="delivery-warning"
            type="warning"
            title="preview target changed"
            :closable="false"
            show-icon
          >
            当前输入已不同于最近一次 preview；请重新预览后再 fake-cancel。
          </el-alert>

          <div class="provider-result-grid">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item v-for="item in providerCancellationTargetItems" :key="item.label" :label="item.label">
                <span class="mono">{{ item.value }}</span>
              </el-descriptions-item>
            </el-descriptions>

            <el-descriptions :column="1" border size="small">
              <el-descriptions-item v-for="item in providerCancellationOperationItems" :key="item.label" :label="item.label">
                <span class="mono">{{ item.value }}</span>
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <el-descriptions v-if="providerCancellationTargetSummaryItems.length" :column="2" border size="small">
            <el-descriptions-item
              v-for="item in providerCancellationTargetSummaryItems"
              :key="item.label"
              :label="item.label"
            >
              <span class="mono">{{ item.value }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <div class="provider-gates">
            <span>Missing gates</span>
            <template v-if="providerCancellationReport.missing_gates.length">
              <el-tag
                v-for="gate in providerCancellationReport.missing_gates"
                :key="gate"
                type="warning"
                effect="plain"
              >
                {{ gate }}
              </el-tag>
            </template>
            <el-tag v-else type="success" effect="plain">none</el-tag>
          </div>

          <el-descriptions class="delivery-safety" :column="4" border size="small">
            <el-descriptions-item v-for="item in providerCancellationSafetyItems" :key="item.label" :label="item.label">
              <span class="mono">{{ item.value }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="dedupe_key">
              <span class="mono">{{ providerCancellationReport.dedupe_key || "-" }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="confirmation_phrase">
              <span class="mono">{{ providerCancellationReport.confirmation_phrase }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </section>
      </el-card>
    </section>

    <section class="action-safety-panel" aria-label="恢复动作安全注册表">
      <el-card class="card-flat dashboard-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Recovery Action Safety Registry</h2>
            <p class="section-subtitle">Admin-only 只读动作目录；这里只展示 gate、risk 和 gap，不提供执行控件。</p>
          </div>
          <el-tag type="info" effect="plain">{{ recoveryActionSummary }}</el-tag>
        </div>
        <el-table :data="recoveryActions" empty-text="暂无 recovery action registry" table-layout="fixed" class="action-table">
          <el-table-column label="Action" min-width="230">
            <template #default="{ row }">
              <div class="action-title">
                <span class="mono">{{ row.action_id }}</span>
                <small>{{ row.label }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="Target" min-width="130">
            <template #default="{ row }">{{ row.target_type }}</template>
          </el-table-column>
          <el-table-column label="Gates" min-width="220">
            <template #default="{ row }">{{ recoveryActionGateSummary(row) }}</template>
          </el-table-column>
          <el-table-column label="Risk" min-width="240" show-overflow-tooltip>
            <template #default="{ row }">{{ recoveryActionRiskSummary(row) }}</template>
          </el-table-column>
          <el-table-column label="Status" width="150">
            <template #default="{ row }">
              <el-tag :type="recoveryActionAvailabilityTag(row).type" effect="plain">
                {{ recoveryActionAvailabilityTag(row).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="Gap / Route" min-width="280" show-overflow-tooltip>
            <template #default="{ row }">
              <router-link v-if="row.suggested_route" :to="row.suggested_route">{{ recoveryActionGapSummary(row) }}</router-link>
              <span v-else>{{ recoveryActionGapSummary(row) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>

    <section class="dashboard-panels" aria-label="worker 和系统详情">
      <el-card class="card-flat dashboard-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Worker / Queue</h2>
            <p class="section-subtitle">来自 health readiness 和 metrics 的 stage message 观察值。</p>
          </div>
          <router-link to="/system-status">系统状态</router-link>
        </div>
        <div class="metric-table">
          <div v-for="item in queueMetricItems" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </el-card>

      <el-card class="card-flat dashboard-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Runtime</h2>
            <p class="section-subtitle">metadata、artifact storage 和 readiness 关键字段。</p>
          </div>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item v-for="item in runtimeItems" :key="item.label" :label="item.label">
            <span class="mono">{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="card-flat dashboard-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Resources</h2>
            <p class="section-subtitle">默认资源版本和版本数量。</p>
          </div>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item v-for="item in resourceItems" :key="item.label" :label="item.label">
            <span class="mono">{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </section>

    <section class="job-panels" aria-label="任务样例">
      <el-card class="card-flat job-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">失败任务样例</h2>
            <p class="section-subtitle">最多展示 5 条最近更新的失败任务。</p>
          </div>
          <router-link :to="failedJobsRoute">查看全部失败任务</router-link>
        </div>
        <el-table :data="failedJobs" empty-text="暂无失败任务" table-layout="fixed" class="job-table">
          <el-table-column label="Job" min-width="190">
            <template #default="{ row }">
              <router-link :to="`/jobs/${row.id}`" class="mono">{{ row.id }}</router-link>
            </template>
          </el-table-column>
          <el-table-column label="Stage" min-width="130">
            <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
          </el-table-column>
          <el-table-column label="Updated" min-width="170">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="Error" min-width="280" show-overflow-tooltip>
            <template #default="{ row }">{{ jobErrorSummary(row) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="card-flat job-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">运行中任务样例</h2>
            <p class="section-subtitle">最多展示 5 条最近更新的运行中任务。</p>
          </div>
          <router-link :to="runningJobsRoute">查看全部运行中任务</router-link>
        </div>
        <el-table :data="runningJobs" empty-text="暂无运行中任务" table-layout="fixed" class="job-table">
          <el-table-column label="Job" min-width="190">
            <template #default="{ row }">
              <router-link :to="`/jobs/${row.id}`" class="mono">{{ row.id }}</router-link>
            </template>
          </el-table-column>
          <el-table-column label="Stage" min-width="130">
            <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
          </el-table-column>
          <el-table-column label="Progress" width="120">
            <template #default="{ row }">{{ row.progress }}%</template>
          </el-table-column>
          <el-table-column label="Updated" min-width="170">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>

    <section class="reference-grid" aria-label="运维相关入口">
      <router-link to="/system-status">系统状态</router-link>
      <router-link to="/system-status/audit-events">审计日志</router-link>
      <router-link to="/system-status/file-retention">文件保留计划</router-link>
      <router-link :to="failedJobsRoute">失败任务筛选</router-link>
      <router-link :to="runningJobsRoute">运行中任务筛选</router-link>
    </section>

    <el-dialog v-model="alertDeliveryDialog.visible" title="Fake-send ops alerts" width="680px">
      <el-alert class="delivery-warning" type="warning" title="local outbox only" :closable="false" show-icon>
        该操作只会调用 fake-send 合同并写入 audit，不会发送外部通知。
      </el-alert>
      <el-form label-position="top">
        <el-form-item label="Selected alert codes">
          <el-input :model-value="selectedActiveAlertCodes.join('\n')" type="textarea" :rows="4" readonly class="mono" />
        </el-form-item>
        <el-form-item label="Reason">
          <el-input v-model="alertDeliveryDialog.reason" type="textarea" :rows="2" placeholder="说明为什么记录本次 fake delivery" />
        </el-form-item>
        <el-form-item label="Confirmation phrase">
          <el-input v-model="alertDeliveryDialog.confirmation" :placeholder="alertDeliveryConfirmationPhrase" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="alertDeliveryDialog.visible = false">取消</el-button>
        <el-button
          type="warning"
          :icon="Bell"
          :disabled="!canFakeSendAlertDelivery"
          :loading="alertDeliveryLoading"
          @click="fakeSendAlertDelivery"
        >
          确认 fake-send
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="providerCancellationDialog.visible" title="Fake-cancel provider operation" width="720px">
      <el-alert class="delivery-warning" type="warning" title="fake provider cancellation only" :closable="false" show-icon>
        该操作只会调用 fake-cancel 合同并写入 audit；不会调用 MinerU cancellation，也不会修改本地任务或队列。
      </el-alert>
      <el-form label-position="top">
        <el-form-item label="Target">
          <el-input :model-value="providerCancellationDialogTarget" readonly class="mono" />
        </el-form-item>
        <el-form-item label="Provider Operation">
          <el-input :model-value="providerCancellationDialogOperation" readonly class="mono" />
        </el-form-item>
        <el-form-item label="Reason">
          <el-input
            v-model="providerCancellationDialog.reason"
            type="textarea"
            :rows="2"
            placeholder="说明为什么记录本次 provider fake cancellation"
          />
        </el-form-item>
        <el-form-item label="Confirmation phrase">
          <el-input v-model="providerCancellationDialog.confirmation" :placeholder="providerCancellationConfirmationPhrase" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="providerCancellationDialog.visible = false">取消</el-button>
        <el-button
          type="warning"
          :icon="CircleClose"
          :disabled="!canFakeCancelProviderCancellation"
          :loading="providerCancellationLoading"
          @click="fakeCancelProviderCancellation"
        >
          确认 fake-cancel
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Bell, CircleClose, Refresh, View } from "@element-plus/icons-vue";

import { documentJobsApi } from "@/api/documentJobs";
import { healthApi } from "@/api/health";
import { opsAlertDestinationsApi } from "@/api/opsAlertDestinations";
import { opsAlertDeliveriesApi } from "@/api/opsAlertDeliveries";
import { opsProviderCancellationsApi } from "@/api/opsProviderCancellations";
import { opsRecoveryActionsApi } from "@/api/opsRecoveryActions";
import type {
  DocumentJobResponse,
  DocumentJobStage,
  HealthMetricsResponse,
  HealthOpsAlertItem,
  HealthOpsAlertsResponse,
  HealthOpsStatus,
  HealthReadyResponse,
  OpsAlertDestinationDryRunResponse,
  OpsAlertDestinationStatus,
  OpsAlertDeliveryOutcome,
  OpsAlertDeliveryResponse,
  OpsProviderCancellationOutcome,
  OpsProviderCancellationPreviewRequest,
  OpsProviderCancellationProvider,
  OpsProviderCancellationResponse,
  OpsProviderCancellationTargetType,
  OpsRecoveryActionResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatBytes, formatDateTime, jobStageText } from "@/utils/format";

type AlertType = "success" | "warning" | "info" | "error";
type TagType = "success" | "warning" | "danger" | "info";

type DetailItem = {
  label: string;
  value: string;
};

type MetricItem = {
  label: string;
  value: number | string;
};

type OpsStatusView = {
  key: "ok" | "watch" | "needs-attention" | "unknown";
  label: string;
  description: string;
  tagType: TagType;
};

type OpsAlert = {
  key: string;
  title: string;
  description: string;
  alertType: AlertType;
  to?: string | { path: string; query: Record<string, string> };
  linkText?: string;
};

const ready = ref<HealthReadyResponse | null>(null);
const metrics = ref<HealthMetricsResponse | null>(null);
const opsAlerts = ref<HealthOpsAlertsResponse | null>(null);
const recoveryActions = ref<OpsRecoveryActionResponse[]>([]);
const recoveryActionsGeneratedAt = ref<string | null>(null);
const recoveryActionsReadOnly = ref<boolean | null>(null);
const failedJobs = ref<DocumentJobResponse[]>([]);
const runningJobs = ref<DocumentJobResponse[]>([]);
const failedJobsTotal = ref(0);
const runningJobsTotal = ref(0);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);
const refreshedAt = ref<string | null>(null);
const selectedAlertDeliveryCodes = ref<string[]>([]);
const alertDeliveryDedupeWindow = ref(60);
const alertDeliveryLoading = ref(false);
const alertDeliveryReport = ref<OpsAlertDeliveryResponse | null>(null);
const alertDeliveryDialog = ref({
  visible: false,
  reason: "",
  confirmation: "",
});
const alertDestinationIdsInput = ref("");
const alertDestinationLoading = ref(false);
const alertDestinationReport = ref<OpsAlertDestinationDryRunResponse | null>(null);
const providerCancellationForm = ref<{
  targetType: OpsProviderCancellationTargetType;
  targetId: string;
  provider: OpsProviderCancellationProvider;
  dedupeWindowMinutes: number;
}>({
  targetType: "document_job",
  targetId: "",
  provider: "mineru",
  dedupeWindowMinutes: 60,
});
const providerCancellationLoading = ref(false);
const providerCancellationReport = ref<OpsProviderCancellationResponse | null>(null);
const providerCancellationDialog = ref({
  visible: false,
  reason: "",
  confirmation: "",
});

const failedJobsRoute = { path: "/jobs", query: { status: "failed", sort: "updated_at_desc" } };
const runningJobsRoute = { path: "/jobs", query: { status: "running", sort: "updated_at_desc" } };

const checks = computed<Record<string, unknown>>(() => ready.value?.dependency_checks ?? {});
const blockers = computed(() => stringListCheck("readiness_blockers"));
const warnings = computed(() => stringListCheck("readiness_warnings"));
const workerMode = computed(() => metrics.value?.worker_mode || stringCheck("worker_mode"));
const stageDispatcher = computed(() => metrics.value?.stage_dispatcher || stringCheck("stage_dispatcher"));
const stageFailedCount = computed(() => stageCount("failed"));
const stageRunningCount = computed(() => stageCount("running"));
const stagePendingCount = computed(() => stageCount("pending"));
const staleRunningCount = computed(() => numberCheck("stage_spool_running_stale_messages") ?? 0);
const replayableCount = computed(() => numberCheck("stage_spool_replayable_messages") ?? 0);
const activeOpsAlerts = computed(() => opsAlerts.value?.alerts ?? []);
const activeOpsAlertCodes = computed(() => activeOpsAlerts.value.map((alert) => alert.code));
const selectedActiveAlertCodes = computed(() => {
  const activeCodes = new Set(activeOpsAlertCodes.value);
  return selectedAlertDeliveryCodes.value.filter((code) => activeCodes.has(code));
});
const allActiveAlertsSelected = computed(() => (
  activeOpsAlerts.value.length > 0 && selectedActiveAlertCodes.value.length === activeOpsAlerts.value.length
));
const someActiveAlertsSelected = computed(() => (
  selectedActiveAlertCodes.value.length > 0 && selectedActiveAlertCodes.value.length < activeOpsAlerts.value.length
));
const alertDeliveryConfirmationPhrase = computed(() => alertDeliveryReport.value?.confirmation_phrase || "SEND FAKE OPS ALERTS");
const canPreviewAlertDelivery = computed(() => (
  selectedActiveAlertCodes.value.length > 0 && !alertDeliveryLoading.value
));
const canOpenAlertDeliveryDialog = computed(() => (
  selectedActiveAlertCodes.value.length > 0 && !alertDeliveryLoading.value
));
const canFakeSendAlertDelivery = computed(() => (
  canOpenAlertDeliveryDialog.value
  && alertDeliveryDialog.value.reason.trim().length > 0
  && alertDeliveryDialog.value.confirmation === alertDeliveryConfirmationPhrase.value
));
const alertDeliverySafetyItems = computed<DetailItem[]>(() => {
  const safety = alertDeliveryReport.value?.safety;
  return [
    { label: "external_delivery", value: booleanLabel(safety?.external_delivery_executed ?? null) },
    { label: "provider_calls", value: booleanLabel(safety?.provider_calls_executed ?? null) },
    { label: "cleanup", value: booleanLabel(safety?.cleanup_executed ?? null) },
    { label: "delete", value: booleanLabel(safety?.delete_executed ?? null) },
    { label: "conversion_workflow", value: booleanLabel(safety?.conversion_workflow_executed ?? null) },
    { label: "audit_events", value: booleanLabel(safety?.audit_events_written ?? null) },
  ];
});
const parsedAlertDestinationIds = computed(() => parseAlertDestinationIds(alertDestinationIdsInput.value));
const alertDestinationSafetyItems = computed<DetailItem[]>(() => {
  const safety = alertDestinationReport.value?.safety;
  return [
    { label: "read_only", value: booleanLabel(safety?.read_only ?? null) },
    { label: "external_delivery", value: booleanLabel(safety?.external_delivery_executed ?? null) },
    { label: "provider_calls", value: booleanLabel(safety?.provider_calls_executed ?? null) },
    { label: "cleanup", value: booleanLabel(safety?.cleanup_executed ?? null) },
    { label: "delete", value: booleanLabel(safety?.delete_executed ?? null) },
    { label: "conversion_workflow", value: booleanLabel(safety?.conversion_workflow_executed ?? null) },
    { label: "audit_events", value: booleanLabel(safety?.audit_events_written ?? null) },
    { label: "secret_values_exposed", value: booleanLabel(safety?.secret_values_exposed ?? null) },
  ];
});
const providerCancellationTargetId = computed(() => providerCancellationForm.value.targetId.trim());
const providerCancellationConfirmationPhrase = computed(() => (
  providerCancellationReport.value?.confirmation_phrase || "FAKE CANCEL PROVIDER OPERATION"
));
const providerCancellationReportMatchesForm = computed(() => {
  const report = providerCancellationReport.value;
  if (!report) {
    return false;
  }
  return report.target.target_type === providerCancellationForm.value.targetType
    && report.target.target_id === providerCancellationTargetId.value
    && report.provider === providerCancellationForm.value.provider
    && report.dedupe_window_minutes === providerCancellationForm.value.dedupeWindowMinutes;
});
const canPreviewProviderCancellation = computed(() => (
  providerCancellationTargetId.value.length > 0 && !providerCancellationLoading.value
));
const canOpenProviderCancellationDialog = computed(() => (
  Boolean(providerCancellationReport.value?.eligible)
  && providerCancellationReportMatchesForm.value
  && !providerCancellationLoading.value
));
const canFakeCancelProviderCancellation = computed(() => (
  canOpenProviderCancellationDialog.value
  && providerCancellationDialog.value.reason.trim().length > 0
  && providerCancellationDialog.value.confirmation === providerCancellationConfirmationPhrase.value
));
const providerCancellationTargetItems = computed<DetailItem[]>(() => {
  const target = providerCancellationReport.value?.target;
  return [
    { label: "target_type", value: target?.target_type || "not reported" },
    { label: "target_id", value: target?.target_id || "not reported" },
    { label: "exists", value: booleanLabel(target?.exists ?? null) },
    { label: "status", value: target?.status || "not reported" },
    { label: "stage", value: target?.stage || "not reported" },
  ];
});
const providerCancellationOperationItems = computed<DetailItem[]>(() => {
  const operation = providerCancellationReport.value?.provider_operation;
  return [
    { label: "provider", value: operation?.provider || "not reported" },
    { label: "operation_id", value: operation?.operation_id || "not reported" },
    { label: "data_id", value: operation?.data_id || "not reported" },
    { label: "operation_type", value: operation?.operation_type || "not reported" },
  ];
});
const providerCancellationTargetSummaryItems = computed<DetailItem[]>(() => (
  recordDetailItems(providerCancellationReport.value?.target.summary ?? {})
));
const providerCancellationSafetyItems = computed<DetailItem[]>(() => {
  const safety = providerCancellationReport.value?.safety;
  return [
    { label: "real_provider_cancel", value: booleanLabel(safety?.real_provider_cancel_executed ?? null) },
    { label: "provider_calls", value: booleanLabel(safety?.provider_calls_executed ?? null) },
    { label: "local_job_mutated", value: booleanLabel(safety?.local_job_mutated ?? null) },
    { label: "queue_mutated", value: booleanLabel(safety?.queue_mutated ?? null) },
    { label: "cleanup", value: booleanLabel(safety?.cleanup_executed ?? null) },
    { label: "delete", value: booleanLabel(safety?.delete_executed ?? null) },
    { label: "conversion_workflow", value: booleanLabel(safety?.conversion_workflow_executed ?? null) },
    { label: "audit_events", value: booleanLabel(safety?.audit_events_written ?? null) },
  ];
});
const providerCancellationDialogTarget = computed(() => {
  const target = providerCancellationReport.value?.target;
  if (!target) {
    return "-";
  }
  return `${target.target_type}:${target.target_id}`;
});
const providerCancellationDialogOperation = computed(() => {
  const operation = providerCancellationReport.value?.provider_operation;
  if (!operation) {
    return "-";
  }
  return `${operation.provider}:${operation.operation_id || "missing"}:${operation.data_id || "missing"}`;
});

const queuePressureLabel = computed(() => {
  const total = stagePendingCount.value + stageRunningCount.value + stageFailedCount.value;
  if (total === 0 && staleRunningCount.value === 0 && replayableCount.value === 0) {
    return "clear";
  }
  return `${total} messages`;
});

const recoveryActionSummary = computed(() => {
  const available = recoveryActions.value.filter((item) => item.available).length;
  const unavailable = recoveryActions.value.length - available;
  return `${available} available · ${unavailable} candidate`;
});

const opsStatus = computed<OpsStatusView>(() => {
  if (opsAlerts.value) {
    return opsStatusFromBackend(opsAlerts.value.status);
  }
  if (!ready.value && !metrics.value) {
    return {
      key: "unknown",
      label: "unknown",
      description: "尚未取得运维状态。",
      tagType: "info",
    };
  }
  if (blockers.value.length > 0 || stageFailedCount.value > 0 || staleRunningCount.value > 0) {
    return {
      key: "needs-attention",
      label: "needs attention",
      description: "存在阻断项、失败 stage message 或 stale running message。",
      tagType: "danger",
    };
  }
  if (warnings.value.length > 0 || replayableCount.value > 0 || failedJobsTotal.value > 0 || runningJobsTotal.value > 0) {
    return {
      key: "watch",
      label: "watch",
      description: "核心链路未阻断，但存在需要持续观察的运行信号。",
      tagType: "warning",
    };
  }
  return {
    key: "ok",
    label: "ok",
    description: "当前未发现 readiness 或队列风险信号。",
    tagType: "success",
  };
});

const staleRunningGuidance = computed(() => {
  if (workerMode.value === "external") {
    return "external worker 模式下，应先确认独立 worker 进程是否存活，再结合任务事件判断是否需要后续处理。";
  }
  return "in_process 模式下，stale running 可能来自进程退出残留；先查看任务详情和系统状态，必要时按现有部署流程处理。";
});

const alertItems = computed<OpsAlert[]>(() => {
  if (opsAlerts.value) {
    return opsAlerts.value.alerts.map(buildBackendOpsAlert);
  }
  const items: OpsAlert[] = [];
  if (blockers.value.length > 0) {
    items.push({
      key: "readiness-blockers",
      title: `Readiness blockers: ${blockers.value.length}`,
      description: blockers.value.join("、"),
      alertType: "error",
      to: "/system-status",
      linkText: "查看系统状态",
    });
  }
  if (warnings.value.length > 0) {
    items.push({
      key: "readiness-warnings",
      title: `Readiness warnings: ${warnings.value.length}`,
      description: warnings.value.join("、"),
      alertType: "warning",
      to: "/system-status",
      linkText: "查看 readiness 详情",
    });
  }
  if (stageFailedCount.value > 0) {
    items.push({
      key: "stage-failed",
      title: `Failed stage messages: ${stageFailedCount.value}`,
      description: "failed stage message 不会自动 replay，需结合任务详情事件和既有 retry 流程判断下一步。",
      alertType: "error",
      to: failedJobsRoute,
      linkText: "查看失败任务",
    });
  }
  if (staleRunningCount.value > 0) {
    items.push({
      key: "stale-running",
      title: `Stale running messages: ${staleRunningCount.value}`,
      description: staleRunningGuidance.value,
      alertType: "error",
      to: runningJobsRoute,
      linkText: "查看运行中任务",
    });
  }
  if (replayableCount.value > 0) {
    items.push({
      key: "replayable",
      title: `Replayable messages: ${replayableCount.value}`,
      description: "pending/running stage message 属于可恢复观察项；外部 worker 或服务重启可能继续处理，仍需结合任务事件确认进展。",
      alertType: "warning",
      to: runningJobsRoute,
      linkText: "查看运行中任务",
    });
  }
  if (failedJobsTotal.value > 0) {
    items.push({
      key: "failed-jobs",
      title: `Failed document jobs: ${failedJobsTotal.value}`,
      description: "失败任务应从任务详情查看错误阶段、事件流和文件区，再决定是否按既有任务流程重试。",
      alertType: "warning",
      to: failedJobsRoute,
      linkText: "查看失败任务",
    });
  }
  if (runningJobsTotal.value > 0) {
    items.push({
      key: "running-jobs",
      title: `Running document jobs: ${runningJobsTotal.value}`,
      description: "运行中任务样例只用于观察，不代表需要人工干预。",
      alertType: "info",
      to: runningJobsRoute,
      linkText: "查看运行中任务",
    });
  }
  return items;
});

const queueMetricItems = computed<MetricItem[]>(() => [
  { label: "stage pending", value: stagePendingCount.value },
  { label: "stage running", value: stageRunningCount.value },
  { label: "stage failed", value: stageFailedCount.value },
  { label: "stale running", value: staleRunningCount.value },
  { label: "replayable", value: replayableCount.value },
  { label: "oldest running age", value: secondsLabel(numberCheck("stage_spool_oldest_running_age_seconds")) },
  { label: "observation", value: stringCheck("stage_spool_observation_status") },
]);

const runtimeItems = computed<DetailItem[]>(() => [
  { label: "app_name", value: ready.value?.app_name || metrics.value?.app_name || "not reported" },
  { label: "metadata_store", value: metrics.value?.metadata_store || stringCheck("effective_repository_backend") },
  { label: "configured_repository", value: stringCheck("configured_repository_backend") },
  { label: "artifact_storage", value: metrics.value?.artifact_storage || stringCheck("artifact_storage") },
  { label: "artifact_root_writable", value: booleanLabel(booleanCheck("artifact_root_writable")) },
  { label: "artifact_disk_free", value: formatOptionalBytes(numberCheck("artifact_disk_free_bytes")) },
  { label: "stage_message_store", value: stringCheck("stage_message_store") },
  { label: "ops_alerts_generated_at", value: formatDateTime(opsAlerts.value?.generated_at) },
  { label: "ops_alerts_read_only", value: booleanLabel(opsAlerts.value?.safety.read_only ?? null) },
  { label: "recovery_actions_generated_at", value: formatDateTime(recoveryActionsGeneratedAt.value) },
  { label: "recovery_actions_read_only", value: booleanLabel(recoveryActionsReadOnly.value) },
  { label: "last_refreshed", value: formatDateTime(refreshedAt.value) },
]);

const resourceItems = computed<DetailItem[]>(() => [
  { label: "default_template_version", value: resourceValue("default_template_version") },
  { label: "default_term_rule_version", value: resourceValue("default_term_rule_version") },
  { label: "default_translation_profile_version", value: resourceValue("default_translation_profile_version") },
  { label: "template_versions", value: resourceValue("template_versions") },
  { label: "term_rule_set_versions", value: resourceValue("term_rule_set_versions") },
  { label: "translation_profile_versions", value: resourceValue("translation_profile_versions") },
]);

// 读取看板需要的所有只读数据。
async function loadDashboard(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [
      readyResponse,
      metricsResponse,
      opsAlertsResponse,
      recoveryActionsResponse,
      failedResponse,
      runningResponse,
    ] = await Promise.all([
      healthApi.getReady(),
      healthApi.getMetrics(),
      healthApi.getOpsAlerts(),
      opsRecoveryActionsApi.list(),
      documentJobsApi.list({
        page: 1,
        page_size: 5,
        status: "failed",
        sort: "updated_at_desc",
        include_archived: false,
      }),
      documentJobsApi.list({
        page: 1,
        page_size: 5,
        status: "running",
        sort: "updated_at_desc",
        include_archived: false,
      }),
    ]);
    ready.value = readyResponse;
    metrics.value = metricsResponse;
    opsAlerts.value = opsAlertsResponse;
    pruneAlertDeliverySelection(opsAlertsResponse.alerts.map((alert) => alert.code));
    recoveryActions.value = recoveryActionsResponse.actions;
    recoveryActionsGeneratedAt.value = recoveryActionsResponse.generated_at;
    recoveryActionsReadOnly.value = recoveryActionsResponse.safety.read_only;
    failedJobs.value = failedResponse.items;
    failedJobsTotal.value = failedResponse.total;
    runningJobs.value = runningResponse.items;
    runningJobsTotal.value = runningResponse.total;
    refreshedAt.value = new Date().toISOString();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

// 判断某个 active alert 是否已被选中进入 fake delivery 请求。
function isAlertDeliverySelected(alertCode: string): boolean {
  return selectedActiveAlertCodes.value.includes(alertCode);
}

// 更新单个 alert code 的选择状态，保持 exact-target 列表不重复。
function toggleAlertDeliverySelection(alertCode: string, checked: boolean): void {
  const current = new Set(selectedActiveAlertCodes.value);
  if (checked) {
    current.add(alertCode);
  } else {
    current.delete(alertCode);
  }
  selectedAlertDeliveryCodes.value = Array.from(current);
}

// 在当前 active alerts 范围内全选或清空 fake delivery 目标。
function toggleAllAlertDeliverySelection(checked: boolean): void {
  selectedAlertDeliveryCodes.value = checked ? [...activeOpsAlertCodes.value] : [];
}

// 刷新后移除已经不再 active 的 alert code，避免向后端发送 stale target。
function pruneAlertDeliverySelection(activeCodes: string[]): void {
  const activeCodeSet = new Set(activeCodes);
  selectedAlertDeliveryCodes.value = selectedAlertDeliveryCodes.value.filter((code) => activeCodeSet.has(code));
}

// 构建 alert delivery 请求 payload，统一固定 local_outbox channel。
function buildAlertDeliveryPayload(): { alert_codes: string[]; channel: "local_outbox"; dedupe_window_minutes: number } {
  return {
    alert_codes: [...selectedActiveAlertCodes.value],
    channel: "local_outbox",
    dedupe_window_minutes: alertDeliveryDedupeWindow.value,
  };
}

// 调用后端 dry-run preview，不写审计、不发送外部通知。
async function previewAlertDelivery(): Promise<void> {
  alertDeliveryLoading.value = true;
  error.value = null;
  try {
    alertDeliveryReport.value = await opsAlertDeliveriesApi.preview(buildAlertDeliveryPayload());
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    alertDeliveryLoading.value = false;
  }
}

// 打开 fake-send 确认对话框，并清空上一次输入。
function openAlertDeliveryDialog(): void {
  alertDeliveryDialog.value = {
    visible: true,
    reason: "",
    confirmation: "",
  };
}

// 调用 fake-send 合同，只记录 local outbox audit，不触发真实通知。
async function fakeSendAlertDelivery(): Promise<void> {
  if (!canFakeSendAlertDelivery.value) {
    return;
  }
  alertDeliveryLoading.value = true;
  error.value = null;
  try {
    alertDeliveryReport.value = await opsAlertDeliveriesApi.fakeSend({
      ...buildAlertDeliveryPayload(),
      reason: alertDeliveryDialog.value.reason,
      confirmation: alertDeliveryDialog.value.confirmation,
    });
    alertDeliveryDialog.value.visible = false;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    alertDeliveryLoading.value = false;
  }
}

// 读取 alert delivery totals，缺失字段按 0 展示。
function alertDeliveryTotal(key: string): number {
  return alertDeliveryReport.value?.totals[key] ?? 0;
}

// 将 fake delivery outcome 映射为 Element Plus 标签样式。
function alertDeliveryOutcomeTag(outcome: OpsAlertDeliveryOutcome): TagType {
  if (outcome === "fake_delivered" || outcome === "deliverable") {
    return "success";
  }
  if (outcome === "deduped" || outcome.startsWith("skipped_")) {
    return "warning";
  }
  if (outcome === "failed") {
    return "danger";
  }
  return "info";
}

// 解析可选 destination IDs，支持逗号和换行分隔并去重。
function parseAlertDestinationIds(rawValue: string): string[] {
  const values = rawValue
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return Array.from(new Set(values));
}

// 调用 alert destination config dry-run，不发送外部通知或写审计。
async function dryRunAlertDestinations(): Promise<void> {
  alertDestinationLoading.value = true;
  error.value = null;
  try {
    alertDestinationReport.value = await opsAlertDestinationsApi.dryRun({
      alert_codes: [...selectedActiveAlertCodes.value],
      destination_ids: parsedAlertDestinationIds.value,
    });
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    alertDestinationLoading.value = false;
  }
}

// 将 alert destination dry-run status 映射为 Element Plus 标签样式。
function alertDestinationStatusTag(status: OpsAlertDestinationStatus): TagType {
  if (status === "dry_run_passed" || status === "config_valid") {
    return "success";
  }
  if (status === "disabled" || status === "blocked") {
    return "warning";
  }
  if (status === "missing_config") {
    return "danger";
  }
  return "info";
}

// 构建 provider cancellation 请求 payload，统一固定 mineru provider 和 exact target。
function buildProviderCancellationPayload(): OpsProviderCancellationPreviewRequest {
  return {
    target_type: providerCancellationForm.value.targetType,
    target_id: providerCancellationTargetId.value,
    provider: providerCancellationForm.value.provider,
    dedupe_window_minutes: providerCancellationForm.value.dedupeWindowMinutes,
  };
}

// 调用 provider cancellation dry-run preview，不写审计、不调用真实 provider。
async function previewProviderCancellation(): Promise<void> {
  if (!canPreviewProviderCancellation.value) {
    return;
  }
  providerCancellationLoading.value = true;
  error.value = null;
  try {
    providerCancellationReport.value = await opsProviderCancellationsApi.preview(buildProviderCancellationPayload());
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    providerCancellationLoading.value = false;
  }
}

// 打开 provider fake-cancel 确认对话框，并清空上一次输入。
function openProviderCancellationDialog(): void {
  providerCancellationDialog.value = {
    visible: true,
    reason: "",
    confirmation: "",
  };
}

// 调用 provider fake-cancel 合同，只写审计，不调用真实 provider 或修改任务状态。
async function fakeCancelProviderCancellation(): Promise<void> {
  if (!canFakeCancelProviderCancellation.value) {
    return;
  }
  providerCancellationLoading.value = true;
  error.value = null;
  try {
    providerCancellationReport.value = await opsProviderCancellationsApi.fakeCancel({
      ...buildProviderCancellationPayload(),
      reason: providerCancellationDialog.value.reason,
      confirmation: providerCancellationDialog.value.confirmation,
    });
    providerCancellationDialog.value.visible = false;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    providerCancellationLoading.value = false;
  }
}

// 将 provider cancellation outcome 映射为 Element Plus 标签样式。
function providerCancellationOutcomeTag(outcome: OpsProviderCancellationOutcome): TagType {
  if (outcome === "cancelable" || outcome === "fake_canceled") {
    return "success";
  }
  if (outcome === "deduped" || outcome === "ineligible") {
    return "warning";
  }
  if (outcome === "failed") {
    return "danger";
  }
  return "info";
}

// 从 readiness dependency_checks 中读取原始字段。
function checkValue(key: string): unknown {
  return checks.value[key];
}

// 将可选字段统一转成界面可读字符串。
function stringCheck(key: string): string {
  return displayValue(checkValue(key));
}

// 读取 readiness 中的字符串列表字段。
function stringListCheck(key: string): string[] {
  const value = checkValue(key);
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
  }
  if (typeof value === "string" && value.trim()) {
    return [value];
  }
  return [];
}

// 读取 readiness 中的布尔字段。
function booleanCheck(key: string): boolean | null {
  const value = checkValue(key);
  return typeof value === "boolean" ? value : null;
}

// 读取 readiness 中的数字字段。
function numberCheck(key: string): number | null {
  const value = checkValue(key);
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

// 将布尔值转成运维界面短标签。
function booleanLabel(value: boolean | null): string {
  if (value === null) {
    return "not reported";
  }
  return value ? "yes" : "no";
}

// 汇总 action 执行 gate，供只读 registry 表格展示。
function recoveryActionGateSummary(action: OpsRecoveryActionResponse): string {
  const gates = [
    action.requires_admin ? "admin" : null,
    action.requires_reason ? "reason" : null,
    action.requires_confirmation ? "confirmation" : null,
    action.dry_run_supported ? "dry-run" : null,
  ].filter((item): item is string => item !== null);
  return gates.length > 0 ? gates.join(" / ") : "none";
}

// 汇总 action 风险 flags，不代表本页面实际执行这些副作用。
function recoveryActionRiskSummary(action: OpsRecoveryActionResponse): string {
  const risks = [
    action.mutates_metadata ? "metadata" : null,
    action.mutates_queue ? "queue" : null,
    action.calls_provider ? "provider" : null,
    action.sends_notification ? "notification" : null,
    action.deletes_data ? "delete" : null,
  ].filter((item): item is string => item !== null);
  return risks.length > 0 ? risks.join(" / ") : "none";
}

// 返回 action 可用性标签，候选执行动作必须显示为 unavailable。
function recoveryActionAvailabilityTag(action: OpsRecoveryActionResponse): { label: string; type: TagType } {
  if (action.available) {
    return { label: "available", type: "success" };
  }
  return { label: "candidate", type: "warning" };
}

// 展示第一条 gap 或建议路由，避免在表格中展开长列表。
function recoveryActionGapSummary(action: OpsRecoveryActionResponse): string {
  if (action.known_gaps.length > 0) {
    return action.known_gaps[0];
  }
  return action.suggested_route || "no known gap";
}

// 将后端 ops-alerts 状态映射为页面摘要状态。
function opsStatusFromBackend(status: HealthOpsStatus): OpsStatusView {
  if (status === "needs_attention") {
    return {
      key: "needs-attention",
      label: "needs attention",
      description: "后端只读告警合同发现需要人工关注的阻断或队列风险。",
      tagType: "danger",
    };
  }
  if (status === "watch") {
    return {
      key: "watch",
      label: "watch",
      description: "后端只读告警合同发现需要持续观察的运行信号。",
      tagType: "warning",
    };
  }
  return {
    key: "ok",
    label: "ok",
    description: "后端只读告警合同未发现当前运维风险信号。",
    tagType: "success",
  };
}

// 将后端告警项映射为 Element Plus 可渲染的告警卡片。
function buildBackendOpsAlert(alert: HealthOpsAlertItem): OpsAlert {
  const route = alert.suggested_route || undefined;
  return {
    key: alert.code,
    title: `${alert.title}: ${alert.count}`,
    description: `${alert.description} 建议：${alert.suggested_action}`,
    alertType: opsAlertType(alert.severity),
    to: route,
    linkText: route ? "查看建议位置" : undefined,
  };
}

// 将后端严重级别映射为前端 alert 类型。
function opsAlertType(severity: HealthOpsAlertItem["severity"]): AlertType {
  if (severity === "critical") {
    return "error";
  }
  if (severity === "warning") {
    return "warning";
  }
  return "info";
}

// 将后端严重级别映射为 Element Plus 标签类型。
function opsAlertSeverityTagType(severity: HealthOpsAlertItem["severity"]): TagType {
  if (severity === "critical") {
    return "danger";
  }
  if (severity === "warning") {
    return "warning";
  }
  return "info";
}

// 将未知类型的 health 字段转成稳定展示文本。
function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "not reported";
  }
  if (typeof value === "boolean") {
    return booleanLabel(value);
  }
  if (typeof value === "number") {
    return String(value);
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

// 将安全摘要对象转换为稳定 descriptions 展示项。
function recordDetailItems(record: Record<string, string | number | boolean | null>): DetailItem[] {
  return Object.entries(record).map(([label, value]) => ({
    label,
    value: displayValue(value),
  }));
}

// 格式化可选字节数，缺失时保持 not reported。
function formatOptionalBytes(value: number | null): string {
  if (value === null) {
    return "not reported";
  }
  return formatBytes(value);
}

// 格式化秒数，避免缺失字段显示为 0。
function secondsLabel(value: number | null): string {
  if (value === null) {
    return "not reported";
  }
  return `${value}s`;
}

// 从 metrics 读取 stage message 状态计数。
function stageCount(status: string): number {
  return metrics.value?.stage_messages[status] ?? 0;
}

// 读取资源字段，优先使用 metrics.resources，缺失再回退到 readiness。
function resourceValue(key: string): string {
  const metricValue = metrics.value?.resources[key];
  if (metricValue !== undefined) {
    return displayValue(metricValue);
  }
  return displayValue(checkValue(key));
}

// 将任务阶段转成中文标签。
function stageLabel(stage: DocumentJobStage): string {
  return jobStageText[stage] || stage;
}

// 汇总失败任务的错误码和错误信息。
function jobErrorSummary(job: DocumentJobResponse): string {
  if (job.error_code && job.error_message) {
    return `${job.error_code}: ${job.error_message}`;
  }
  return job.error_message || job.error_code || "-";
}

onMounted(() => {
  void loadDashboard();
});
</script>

<style scoped lang="scss">
.ops-dashboard-page {
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

.heading-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.summary-grid,
.alert-delivery-panel,
.alert-destination-panel,
.provider-cancellation-panel,
.action-safety-panel,
.dashboard-panels,
.job-panels {
  display: grid;
  gap: 14px;
}

.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dashboard-panels {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.job-panels {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.summary-card {
  display: grid;
  gap: 6px;
  min-height: 118px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.summary-card span,
.summary-card strong,
.summary-card small {
  display: block;
}

.summary-card span {
  color: #667085;
  font-size: 13px;
}

.summary-card strong {
  color: #111827;
  font-size: 22px;
  line-height: 1.2;
}

.summary-card small {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.status-card {
  grid-template-columns: 12px minmax(0, 1fr);
  align-items: start;
}

.status-card strong {
  font-size: 24px;
}

.status-dot {
  width: 10px;
  height: 10px;
  margin-top: 8px;
  border-radius: 999px;
  background: #94a3b8;
}

.status-card.is-ok .status-dot {
  background: #16a34a;
}

.status-card.is-watch .status-dot {
  background: #d97706;
}

.status-card.is-needs-attention .status-dot {
  background: #dc2626;
}

.alert-grid {
  display: grid;
  gap: 12px;
}

.alert-description {
  margin: 0 0 6px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.delivery-warning {
  margin-bottom: 14px;
}

.alert-delivery-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 14px;
  align-items: start;
}

.alert-delivery-list,
.alert-delivery-controls,
.alert-delivery-result {
  min-width: 0;
}

.delivery-selection-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 38px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  color: #475467;
  font-size: 13px;
}

.alert-delivery-controls {
  display: grid;
  gap: 12px;
  padding: 12px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fbfdff;
}

.field-hint {
  margin-left: 8px;
  color: #667085;
  font-size: 12px;
}

.delivery-actions {
  display: grid;
  gap: 8px;
}

.delivery-actions .el-button {
  width: 100%;
  margin-left: 0;
}

.alert-delivery-result {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #d9e2ec;
}

.alert-destination-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 14px;
  align-items: start;
}

.alert-destination-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.alert-destination-controls {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fbfdff;
}

.alert-destination-result {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #d9e2ec;
}

.compact-list {
  margin: 0;
  padding-left: 18px;
}

.delivery-safety {
  margin-bottom: 12px;
}

.delivery-alert-table,
.delivery-result-table {
  width: 100%;
}

.provider-cancellation-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 14px;
  align-items: start;
}

.provider-cancellation-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.provider-cancellation-controls {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fbfdff;
}

.provider-cancellation-result {
  display: grid;
  gap: 12px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #d9e2ec;
}

.provider-result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.provider-gates {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
}

.provider-gates > span {
  color: #475467;
  font-size: 13px;
  font-weight: 600;
}

.dashboard-panel,
.job-panel {
  border: 1px solid #d9e2ec;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.section-title {
  margin: 0;
  color: #111827;
  font-size: 18px;
}

.section-subtitle {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
}

.metric-table {
  display: grid;
  gap: 8px;
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 34px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
}

.metric-row span {
  color: #475467;
  font-size: 13px;
}

.metric-row strong {
  color: #111827;
  font-size: 15px;
}

.mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}

.job-table {
  width: 100%;
}

.action-table {
  width: 100%;
}

.action-title {
  display: grid;
  gap: 3px;
}

.action-title small {
  color: #667085;
}

.reference-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

@media (max-width: 1100px) {
  .summary-grid,
  .dashboard-panels,
  .job-panels {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading,
  .heading-actions,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar,
  .delivery-selection-bar {
    justify-content: flex-start;
  }

  .summary-grid,
  .alert-delivery-layout,
  .alert-destination-layout,
  .alert-destination-form,
  .provider-cancellation-layout,
  .provider-cancellation-form,
  .provider-result-grid,
  .dashboard-panels,
  .job-panels {
    grid-template-columns: 1fr;
  }
}
</style>
