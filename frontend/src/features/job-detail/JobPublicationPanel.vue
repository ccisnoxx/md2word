<!-- 文件：frontend/src/features/job-detail/JobPublicationPanel.vue -->
<!-- 用途：在「发布与交付」标签页完整呈现 preflight_checks、幂等正式发布、不可变发布记录与最终交付件下载，以及 Admin 同任务新代入口。 -->
<template>
  <div class="publication-tab-stack">
    <el-card class="page-section publication-availability card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">发布与交付状态</h2>
          <p class="section-subtitle">
            {{ effectivePublishAction?.eligible === true ? "核心资格通过" : effectivePublishAction?.eligible === false ? "核心资格未通过" : "核心资格未提供" }}
            ·
            {{ effectivePublishAction?.enabled === true ? "后端已开放发布" : "当前不可发布" }}
          </p>
        </div>
        <div class="publication-header-actions">
          <el-tag
            v-if="job.delivery_status"
            :type="jobDeliveryStatusTagType(job.delivery_status)"
            effect="plain"
          >
            交付状态：{{ jobDeliveryStatusText[job.delivery_status] || job.delivery_status }}
          </el-tag>
          <el-button size="small" :icon="Refresh" :loading="publication.loading.value" @click="publication.load()">
            刷新发布状态
          </el-button>
          <el-tooltip
            v-if="isAdmin && effectiveNewGenerationAction"
            :disabled="effectiveNewGenerationAction.enabled || !effectiveNewGenerationAction.disabled_reason"
            :content="effectiveNewGenerationAction.disabled_reason || ''"
            placement="top"
          >
            <span>
              <el-button
                size="small"
                type="warning"
                plain
                :disabled="!effectiveNewGenerationAction.enabled"
                @click="$emit('open-new-generation')"
              >
                开始同任务新代
              </el-button>
            </span>
          </el-tooltip>
          <el-button
            size="small"
            type="primary"
            :disabled="!publication.publishEnabled.value"
            @click="publication.openPublishDialog()"
          >
            正式发布为最终交付件
          </el-button>
        </div>
      </div>

      <ApiErrorAlert :error="publication.error.value" />

      <el-alert
        v-if="publication.lastFinalDeliveryDownload.value"
        class="final-delivery-alert"
        type="success"
        :closable="true"
        show-icon
        title="已签发正式最终交付件下载链接（classification: final_delivery）"
        @close="publication.lastFinalDeliveryDownload.value = null"
      >
        <div class="final-delivery-meta">
          <span>发布记录：<strong class="mono">{{ publication.lastFinalDeliveryDownload.value.publication_id }}</strong></span>
          <span>体积：{{ formatBytes(publication.lastFinalDeliveryDownload.value.size_bytes) }}</span>
          <span>有效期至 {{ formatDateTime(publication.lastFinalDeliveryDownload.value.expires_at) }}</span>
          <a :href="publication.lastFinalDeliveryDownload.value.download_url" target="_blank" rel="noopener">
            打开最终交付件下载链接
          </a>
          <el-button
            text
            size="small"
            @click="publication.copySha256(publication.lastFinalDeliveryDownload.value.result_sha256)"
          >
            复制 SHA256
          </el-button>
        </div>
      </el-alert>

      <div v-if="preflightChecks.length" class="preflight-section">
        <h3>发布前检查清单</h3>
        <ul class="preflight-list" aria-label="发布前检查清单">
          <li v-for="check in preflightChecks" :key="check.code" class="preflight-item">
            <div class="preflight-item-head">
              <el-tag
                size="small"
                :type="check.status === 'passed' ? 'success' : check.status === 'blocked' ? 'danger' : 'info'"
                effect="plain"
              >
                {{ check.status === "passed" ? "通过" : check.status === "blocked" ? "阻断" : "未核验" }}
              </el-tag>
              <strong>{{ publicationPreflightTitle(check.code) }}</strong>
              <small v-if="check.reason_code" class="mono preflight-code">{{ check.reason_code }}</small>
            </div>
            <p class="preflight-message">{{ check.message }}</p>
          </li>
        </ul>
      </div>

      <div v-if="!publication.publishEnabled.value && disabledReasons.length" class="publication-reasons-block">
        <h3>发布限制说明</h3>
        <ul id="publication-disabled-reasons" class="publication-reasons" tabindex="0" aria-label="发布禁用原因">
          <li v-for="(reason, index) in disabledReasons" :key="`${reason.code}-${index}`">
            <span>{{ reason.message }}</span>
            <small v-if="reason.code" class="mono">{{ reason.code }}</small>
          </li>
        </ul>
      </div>
      <p v-else-if="publication.publishEnabled.value" class="publication-ready-note">
        后端全部发布前门禁已满足，可点击上方「正式发布为最终交付件」固化当前代次产物。
      </p>
    </el-card>

    <!-- 不可变发布历史记录表 -->
    <el-card class="page-section card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">不可变发布记录</h2>
          <p class="section-subtitle">每条正式发布记录永久绑定代次、复核序号、预览运行与主件 SHA256，与内部草稿下载严格隔离。</p>
        </div>
      </div>

      <el-table
        v-loading="publication.loading.value"
        :data="publicationItems"
        empty-text="当前任务尚未生成正式发布记录。"
        class="publication-table"
      >
        <el-table-column label="发布记录 / 代次" min-width="190">
          <template #default="{ row }">
            <div class="pub-id-cell">
              <strong class="mono">{{ row.publication_id }}</strong>
              <span class="pub-sub">第 {{ row.generation + 1 }} 代 · 复核 #{{ row.review_sequence }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="发布人 / 时间" min-width="170">
          <template #default="{ row }">
            <div class="pub-id-cell">
              <span>{{ row.published_by }}</span>
              <span class="pub-sub">{{ formatDateTime(row.published_at) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="发布备注" min-width="180">
          <template #default="{ row }">
            <span class="pub-note">{{ row.note }}</span>
          </template>
        </el-table-column>
        <el-table-column label="绑定资源快照与校验" min-width="230">
          <template #default="{ row }">
            <div class="pub-versions-cell">
              <span class="mono">模板：{{ row.versions.template.resource_id }}@{{ row.versions.template.version }}</span>
              <span class="mono">规则：{{ row.versions.symbol_rules.resource_id }}@{{ row.versions.symbol_rules.version }}</span>
              <span class="mono">
                SHA256：{{ shortHash(row.result_sha256, 16) }}
                <el-button link size="small" type="primary" @click="publication.copySha256(row.result_sha256)">
                  复制
                </el-button>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最终件交付" width="168" align="right">
          <template #default="{ row }">
            <el-tooltip
              :disabled="isRecordDownloadEnabled(row.publication_id) || !recordDownloadDisabledReason(row.publication_id)"
              :content="recordDownloadDisabledReason(row.publication_id)"
              placement="top"
            >
              <span>
                <el-button
                  size="small"
                  type="success"
                  :icon="Download"
                  :loading="publication.downloadingPublicationId.value === row.publication_id"
                  :disabled="!isRecordDownloadEnabled(row.publication_id)"
                  @click="publication.downloadFinalDelivery(row)"
                >
                  下载最终交付件
                </el-button>
              </span>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 幂等正式发布确认弹窗 -->
    <el-dialog
      v-model="publication.publishDialogVisible.value"
      title="正式发布为最终交付件"
      width="min(600px, calc(100vw - 32px))"
      top="24px"
      :append-to-body="true"
    >
      <div class="publish-dialog-scroll app-scrollbar-persistent">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="正式发布将把当前代次产物登记为不可变最终交付件（final_delivery），锁定本次观测的主件与复核来源。"
        />

        <el-alert
          v-if="publication.publishForm.ambiguousFailure"
          type="warning"
          :closable="false"
          show-icon
          title="上次发布提交遇到 5xx 或网络异常，已保留同一幂等键，请直接使用同一请求 ID 重放确认"
        >
          <div class="publish-reconcile-box">
            <span>保留的幂等请求 ID：<strong class="mono">{{ publication.publishForm.requestId }}</strong></span>
            <el-button size="small" link type="primary" @click="publication.load()">先刷新发布记录确认</el-button>
            <el-button size="small" link @click="publication.resetPublishKey()">确认未提交后重置请求 ID</el-button>
          </div>
        </el-alert>

        <ApiErrorAlert :error="publication.publishError.value" />

        <el-descriptions v-if="publication.publishForm.expectedSource" :column="2" border size="small">
          <el-descriptions-item label="锁定代次">
            第 {{ publication.publishForm.expectedSource.generation + 1 }} 代
          </el-descriptions-item>
          <el-descriptions-item label="复核序号">
            #{{ publication.publishForm.expectedSource.review_sequence }}
          </el-descriptions-item>
          <el-descriptions-item label="幂等请求 ID" :span="2">
            <span class="mono">{{ publication.publishForm.requestId }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="主件 SHA256" :span="2">
            <span class="mono">{{ shortHash(publication.publishForm.expectedSource.result_sha256, 20) }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-form label-position="top">
          <el-form-item label="发布备注（1–1000 字）" required>
            <el-input
              v-model="publication.publishForm.note"
              type="textarea"
              :rows="3"
              maxlength="1000"
              show-word-limit
              placeholder="例如：已完成第 1–14 页参数表与术语人工复核，准予交付客户"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button :disabled="publication.publishing.value" @click="publication.publishDialogVisible.value = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="publication.publishing.value"
          :disabled="!publication.canSubmitPublish.value"
          @click="publication.submitPublish()"
        >
          {{ publication.publishForm.ambiguousFailure ? "使用同一幂等键重试发布" : "确认正式发布" }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Download, Refresh } from "@element-plus/icons-vue";

import type { DocumentJobResponse } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { publicationPreflightTitle, shortHash } from "@/features/document-review/documentReviewFormat";
import {
  documentJobActionDisabledReasons,
  formatBytes,
  formatDateTime,
  jobDeliveryStatusTagType,
  jobDeliveryStatusText,
} from "@/utils/format";
import type { JobPublicationState } from "./useJobPublication";

const props = defineProps<{
  job: DocumentJobResponse;
  publication: JobPublicationState;
  isAdmin: boolean;
}>();

defineEmits<{
  "open-new-generation": [];
}>();

const effectivePublishAction = computed(() => props.publication.publishAction.value);
const effectiveNewGenerationAction = computed(() => props.publication.newGenerationActionState.value);
const preflightChecks = computed(() => props.publication.publications.value?.preflight_checks ?? []);
const publicationItems = computed(() => props.publication.publications.value?.items ?? []);

const disabledReasons = computed(() => {
  const fromPub = props.publication.publications.value?.available_actions.publish;
  if (fromPub) {
    if (fromPub.disabled_reasons?.length) {
      return fromPub.disabled_reasons;
    }
    return fromPub.disabled_reason
      ? [{ code: fromPub.disabled_reason_code || "", message: fromPub.disabled_reason }]
      : [];
  }
  return documentJobActionDisabledReasons(props.job, "publish");
});

function isRecordDownloadEnabled(publicationId: string): boolean {
  const action = props.publication.publications.value?.download_actions[publicationId];
  return action ? action.enabled === true : true;
}

function recordDownloadDisabledReason(publicationId: string): string {
  return props.publication.publications.value?.download_actions[publicationId]?.disabled_reason || "";
}
</script>

<style scoped lang="scss">
.publication-tab-stack {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.publication-tab-stack > * {
  min-width: 0;
}

.publication-header-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.final-delivery-alert {
  margin-bottom: 14px;
}

.final-delivery-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.preflight-section {
  margin-bottom: 14px;
}

.preflight-section h3,
.publication-reasons-block h3 {
  margin: 0 0 8px;
  color: var(--app-color-text);
  font-size: 14px;
}

.preflight-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.preflight-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
}

.preflight-item-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.preflight-code {
  margin-left: auto;
  color: var(--app-color-text-faint);
}

.preflight-message {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.publication-reasons {
  margin: 0;
  padding-left: 20px;
  color: var(--app-color-text);
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.publication-reasons small {
  display: block;
  color: var(--app-color-text-muted);
}

.publication-reasons:focus-visible {
  outline: 2px solid var(--app-color-primary);
  outline-offset: 4px;
}

.publication-empty-reasons,
.publication-ready-note {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.publication-ready-note {
  color: var(--app-color-success, #15803d);
}

.pub-id-cell,
.pub-versions-cell {
  display: grid;
  gap: 3px;
  font-size: 12px;
}

.pub-sub {
  color: var(--app-color-text-muted);
}

.pub-note {
  font-size: 13px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.publish-dialog-scroll {
  display: grid;
  gap: 12px;
  max-height: min(540px, calc(100vh - 220px));
  overflow-y: auto;
  padding-right: 4px;
}

.publish-reconcile-box {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
</style>
