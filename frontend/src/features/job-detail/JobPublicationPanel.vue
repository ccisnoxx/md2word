<template>
  <el-card class="page-section publication-availability card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">发布可用性</h2>
        <p class="section-subtitle">
          {{ job.available_actions.publish?.eligible === true ? "核心资格通过" : job.available_actions.publish?.eligible === false ? "核心资格未通过" : "核心资格未提供" }}
          ·
          {{ isDocumentJobActionEnabled(job, "publish") ? "后端已开放发布" : "当前不可发布" }}
        </p>
      </div>
      <el-button :disabled="!isDocumentJobActionEnabled(job, 'publish')" aria-describedby="publication-disabled-reasons">发布</el-button>
    </div>
    <ul id="publication-disabled-reasons" class="publication-reasons" tabindex="0" aria-label="发布禁用原因">
      <li v-for="(reason, index) in documentJobActionDisabledReasons(job, 'publish')" :key="`${reason.code}-${index}`">
        <span>{{ reason.message }}</span>
        <small v-if="reason.code" class="mono">{{ reason.code }}</small>
      </li>
    </ul>
  </el-card>
</template>

<script setup lang="ts">
import { documentJobActionDisabledReasons, isDocumentJobActionEnabled } from "@/utils/format";

import type { DocumentJobResponse } from "@/api/types";
const {
  job,
} = defineProps<{
  job: DocumentJobResponse;
}>();
</script>

<style scoped lang="scss">
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
</style>
