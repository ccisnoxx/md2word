<template>
  <el-card class="page-section card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">任务上下文建议</h2>
        <p class="section-subtitle">从当前任务带入来源文件和绑定配置版本。</p>
      </div>
      <div class="toolbar">
        <el-button type="primary" :icon="EditPen" @click="openTermRuleProposal">提交符号与排版规则建议</el-button>
        <el-button
          v-if="supportsJobTranslationQa(job)"
          :icon="EditPen"
          @click="openTranslationTermProposal"
        >
          提交翻译术语建议
        </el-button>
      </div>
    </div>
    <el-descriptions :column="2" border>
      <el-descriptions-item label="来源任务">{{ job.id }}</el-descriptions-item>
      <el-descriptions-item label="来源文件">{{ job.source_file_id }}</el-descriptions-item>
      <el-descriptions-item label="当前符号与排版规则">{{ termRuleProposalVersionLabel }}</el-descriptions-item>
      <el-descriptions-item v-if="supportsJobTranslationQa(job)" label="当前翻译术语集">
        {{ translationTermProposalVersionLabel }}
      </el-descriptions-item>
    </el-descriptions>
  </el-card>
  <el-card class="page-section card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">请求快照</h2>
        <p class="section-subtitle">次级排障信息；主流程通常只需查看状态、失败信息和事件流。</p>
      </div>
    </div>
    <details class="snapshot-details">
      <summary>查看后端记录的非正文任务参数摘要</summary>
      <pre class="snapshot app-scrollbar-persistent">{{ requestSnapshotPreview }}</pre>
    </details>
  </el-card>
</template>

<script setup lang="ts">
import { EditPen } from "@element-plus/icons-vue";
import { supportsJobTranslationQa } from "./jobDetailFormat";
import type { UnwrapRef } from "vue";

import type { JobDetailResources } from "./useJobDetailResources";
import type { JobDetailActions } from "./useJobDetailActions";
import type { DocumentJobResponse } from "@/api/types";
const {
  job,
  requestSnapshotPreview,
  termRuleProposalVersionLabel,
  translationTermProposalVersionLabel,
  openTermRuleProposal,
  openTranslationTermProposal,
} = defineProps<{
  job: DocumentJobResponse;
  requestSnapshotPreview: UnwrapRef<JobDetailResources["requestSnapshotPreview"]>;
  termRuleProposalVersionLabel: UnwrapRef<JobDetailResources["termRuleProposalVersionLabel"]>;
  translationTermProposalVersionLabel: UnwrapRef<JobDetailResources["translationTermProposalVersionLabel"]>;
  openTermRuleProposal: UnwrapRef<JobDetailActions["openTermRuleProposal"]>;
  openTranslationTermProposal: UnwrapRef<JobDetailActions["openTranslationTermProposal"]>;
}>();
</script>

<style scoped lang="scss">
.snapshot-details {
  color: var(--app-color-text-muted);
}

.snapshot-details summary {
  margin-bottom: 10px;
  cursor: pointer;
  font-weight: 600;
}

.snapshot {
  max-height: 260px;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}
</style>
