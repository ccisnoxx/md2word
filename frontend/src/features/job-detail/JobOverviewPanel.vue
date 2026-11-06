<template>
  <el-card class="page-section card-flat" shadow="never">
    <div class="detail-overview">
      <JobStatusBadge :status="job.status" />
      <JobProgress :status="job.status" :stage="job.stage" :progress="job.progress" />
    </div>
    <el-descriptions :column="2" border>
      <el-descriptions-item label="模式">{{ jobModeText[job.mode] || job.mode }}</el-descriptions-item>
      <el-descriptions-item v-if="!usesTranslationResources(job)" label="转换说明">保持原文语言和语义，不调用 AI。</el-descriptions-item>
      <el-descriptions-item v-if="supportsJobTranslationQa(job)" label="翻译 QA">
        <span class="qa-summary">
          <el-tag :type="translationQaStatusTagType(job.translation_qa_status)" effect="plain">
            {{ translationQaStatusText[job.translation_qa_status] }}
          </el-tag>
          <span>{{ translationQaReviewText }}</span>
        </span>
      </el-descriptions-item>
      <el-descriptions-item label="文档语言">{{ job.document_language }}</el-descriptions-item>
      <el-descriptions-item label="源 PDF">{{ sourceFilename }}</el-descriptions-item>
      <el-descriptions-item label="源文件 ID">{{ job.source_file_id }}</el-descriptions-item>
      <el-descriptions-item label="来源任务 ID">{{ job.source_job_id || "-" }}</el-descriptions-item>
      <el-descriptions-item label="结果文件 ID">{{ job.result_file_id || "-" }}</el-descriptions-item>
      <el-descriptions-item label="Word 模板">{{ boundTemplateLabel }}</el-descriptions-item>
      <el-descriptions-item label="符号与排版规则">{{ boundTermRuleSetLabel }}</el-descriptions-item>
      <el-descriptions-item v-if="usesTranslationResources(job)" label="翻译术语集">{{ boundTranslationTermSetLabel }}</el-descriptions-item>
      <el-descriptions-item v-if="usesTranslationResources(job)" label="翻译配置">{{ boundTranslationProfileLabel }}</el-descriptions-item>
      <el-descriptions-item v-if="usesTranslationResources(job)" label="旧术语版本 ID">{{ job.term_version_id || "-" }}</el-descriptions-item>
      <el-descriptions-item label="创建时间">{{ formatDateTime(job.created_at) }}</el-descriptions-item>
      <el-descriptions-item label="更新时间">{{ formatDateTime(job.updated_at) }}</el-descriptions-item>
      <el-descriptions-item label="重试次数">{{ job.retry_count }}</el-descriptions-item>
      <el-descriptions-item label="完成时间">{{ formatDateTime(job.completed_at) }}</el-descriptions-item>
      <el-descriptions-item label="取消时间">{{ formatDateTime(job.canceled_at) }}</el-descriptions-item>
      <el-descriptions-item label="归档时间">{{ formatDateTime(job.archived_at) }}</el-descriptions-item>
      <el-descriptions-item label="归档人">{{ job.archived_by || "-" }}</el-descriptions-item>
      <el-descriptions-item v-if="supportsJobTranslationQa(job) && job.translation_qa_note" label="QA 备注">
        {{ job.translation_qa_note }}
      </el-descriptions-item>
    </el-descriptions>
    <el-alert
      v-if="runningNotice"
      class="state-alert"
      :type="runningNoticeType"
      :closable="false"
      show-icon
      :title="runningNotice"
    />
    <el-alert
      v-if="downloadHint"
      class="state-alert"
      :type="isDocumentJobActionEnabled(job, 'download') ? 'info' : 'warning'"
      :closable="false"
      show-icon
      :title="downloadHint"
    />
  </el-card>
</template>

<script setup lang="ts">
import JobProgress from "@/components/JobProgress.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import {
  formatDateTime,
  isDocumentJobActionEnabled,
  jobModeText,
  translationQaStatusTagType,
  translationQaStatusText,
} from "@/utils/format";
import { supportsJobTranslationQa, usesTranslationResources } from "./jobDetailFormat";
import type { UnwrapRef } from "vue";

import type { JobDetailResources } from "./useJobDetailResources";
import type { JobDetailDiagnostics } from "./useJobDetailDiagnostics";
import type { DocumentJobResponse } from "@/api/types";
const {
  job,
  sourceFilename,
  translationQaReviewText,
  boundTemplateLabel,
  boundTermRuleSetLabel,
  boundTranslationTermSetLabel,
  boundTranslationProfileLabel,
  runningNotice,
  runningNoticeType,
  downloadHint,
} = defineProps<{
  job: DocumentJobResponse;
  sourceFilename: UnwrapRef<JobDetailResources["sourceFilename"]>;
  translationQaReviewText: UnwrapRef<JobDetailResources["translationQaReviewText"]>;
  boundTemplateLabel: UnwrapRef<JobDetailResources["boundTemplateLabel"]>;
  boundTermRuleSetLabel: UnwrapRef<JobDetailResources["boundTermRuleSetLabel"]>;
  boundTranslationTermSetLabel: UnwrapRef<JobDetailResources["boundTranslationTermSetLabel"]>;
  boundTranslationProfileLabel: UnwrapRef<JobDetailResources["boundTranslationProfileLabel"]>;
  runningNotice: UnwrapRef<JobDetailDiagnostics["runningNotice"]>;
  runningNoticeType: UnwrapRef<JobDetailDiagnostics["runningNoticeType"]>;
  downloadHint: UnwrapRef<JobDetailDiagnostics["downloadHint"]>;
}>();
</script>

<style scoped lang="scss">
.detail-overview {
  display: grid;
  grid-template-columns: auto minmax(220px, 420px);
  gap: 18px;
  align-items: center;
  margin-bottom: 18px;
}

.state-alert {
  margin-top: 14px;
}

.qa-summary {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

@media (max-width: 760px) {
  .detail-overview {
    grid-template-columns: 1fr;
  }
}
</style>
