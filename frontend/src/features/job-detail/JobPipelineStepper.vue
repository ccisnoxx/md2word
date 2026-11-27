<!-- 文件：frontend/src/features/job-detail/JobPipelineStepper.vue；用途：展示任务各执行阶段的水平进度与失败定位摘要。 -->
<template>
  <section class="pipeline-stepper-shell app-page-shell" aria-label="任务执行阶段进度">
    <div class="pipeline-stepper-header">
      <div class="pipeline-stepper-title">
        <strong>执行流水线</strong>
        <span class="pipeline-stage-current">
          当前阶段：{{ currentStageLabel }} · {{ job.progress }}%
        </span>
      </div>
      <div v-if="job.status === 'failed'" class="pipeline-failure-facts">
        <span class="task-disposition-fact is-danger">
          <span>失败阶段</span>
          <strong>{{ failedStageLabel }}</strong>
        </span>
        <span v-if="job.error_code" class="task-disposition-fact is-danger">
          <span>错误码</span>
          <strong class="mono">{{ job.error_code }}</strong>
        </span>
        <span v-if="failedPageNumber" class="task-disposition-fact is-danger">
          <span>失败定位</span>
          <strong>源 PDF 第 {{ failedPageNumber }} 页</strong>
        </span>
      </div>
    </div>

    <ol class="pipeline-track app-scrollbar-transient">
      <li
        v-for="(node, index) in pipelineNodes"
        :key="node.key"
        class="pipeline-node"
        :class="`is-${node.state}`"
      >
        <span class="pipeline-node-marker" aria-hidden="true">
          <el-icon v-if="node.state === 'done'"><Check /></el-icon>
          <el-icon v-else-if="node.state === 'failed'"><Close /></el-icon>
          <el-icon v-else-if="node.state === 'canceled'"><Remove /></el-icon>
          <span v-else-if="node.state === 'active'" class="pipeline-active-dot"></span>
          <span v-else class="pipeline-step-index">{{ index + 1 }}</span>
        </span>
        <span class="pipeline-node-copy">
          <strong>{{ node.label }}</strong>
          <small>{{ stateCaption(node.state) }}</small>
        </span>
        <span v-if="index < pipelineNodes.length - 1" class="pipeline-connector" aria-hidden="true"></span>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Check, Close, Remove } from "@element-plus/icons-vue";

import type { DocumentJobResponse, DocumentJobStage } from "@/api/types";
import { jobStageText } from "@/utils/format";
import { usesTranslationResources } from "./jobDetailFormat";

type PipelineStepState = "done" | "active" | "failed" | "canceled" | "pending";

type PipelineNode = {
  key: DocumentJobStage;
  label: string;
  state: PipelineStepState;
};

const { job } = defineProps<{
  job: DocumentJobResponse;
}>();

const DIRECT_STAGES: DocumentJobStage[] = [
  "uploaded",
  "parsing",
  "ir_converting",
  "rendering",
  "quality_checking",
  "uploading",
];

const TRANSLATION_STAGES: DocumentJobStage[] = [
  "uploaded",
  "parsing",
  "ir_converting",
  "translating",
  "translation_validating",
  "rendering",
  "quality_checking",
  "uploading",
];

const stageOrder = computed(() => (usesTranslationResources(job) ? TRANSLATION_STAGES : DIRECT_STAGES));

function stagePosition(stage: string | null | undefined, order: DocumentJobStage[]): number {
  if (!stage) {
    return -1;
  }
  if (stage === "parsed") {
    const parsingIndex = order.indexOf("parsing");
    return parsingIndex >= 0 ? parsingIndex + 0.5 : -1;
  }
  if (stage === "completed") {
    return order.length;
  }
  return order.indexOf(stage as DocumentJobStage);
}

const pipelineNodes = computed<PipelineNode[]>(() => {
  const order = stageOrder.value;
  if (job.status === "succeeded" || job.stage === "completed") {
    return order.map((key) => ({ key, label: jobStageText[key], state: "done" }));
  }

  if (job.status === "failed") {
    const anchorStage = job.failed_stage || job.stage;
    const pos = stagePosition(anchorStage, order);
    return order.map((key, index) => {
      if (pos < 0) {
        return { key, label: jobStageText[key], state: "pending" };
      }
      if (index < Math.floor(pos) || (pos % 1 !== 0 && index <= Math.floor(pos))) {
        return { key, label: jobStageText[key], state: "done" };
      }
      if (index === Math.ceil(pos)) {
        return { key, label: jobStageText[key], state: "failed" };
      }
      return { key, label: jobStageText[key], state: "pending" };
    });
  }

  if (job.status === "canceled") {
    const pos = stagePosition(job.stage, order);
    return order.map((key, index) => {
      if (pos < 0) {
        return { key, label: jobStageText[key], state: "pending" };
      }
      if (index < Math.floor(pos)) {
        return { key, label: jobStageText[key], state: "done" };
      }
      if (index === Math.floor(pos)) {
        return { key, label: jobStageText[key], state: "canceled" };
      }
      return { key, label: jobStageText[key], state: "pending" };
    });
  }

  const pos = stagePosition(job.stage, order);
  return order.map((key, index) => {
    if (pos < 0) {
      return { key, label: jobStageText[key], state: index === 0 ? "active" : "pending" };
    }
    if (pos % 1 !== 0) {
      if (index <= Math.floor(pos)) {
        return { key, label: jobStageText[key], state: "done" };
      }
      if (index === Math.ceil(pos)) {
        return { key, label: jobStageText[key], state: "active" };
      }
      return { key, label: jobStageText[key], state: "pending" };
    }
    if (index < pos) {
      return { key, label: jobStageText[key], state: "done" };
    }
    if (index === pos) {
      return { key, label: jobStageText[key], state: "active" };
    }
    return { key, label: jobStageText[key], state: "pending" };
  });
});

const currentStageLabel = computed(() => jobStageText[job.stage as DocumentJobStage] || job.stage || "-");
const failedStageLabel = computed(() => {
  const stage = job.failed_stage || job.stage;
  return stage ? (jobStageText[stage as DocumentJobStage] || stage) : "-";
});
const failedPageNumber = computed(() => {
  const page = job.failure_diagnostic?.page_number;
  return typeof page === "number" && Number.isInteger(page) && page >= 1 ? page : null;
});

function stateCaption(state: PipelineStepState): string {
  if (state === "done") {
    return "已完成";
  }
  if (state === "active") {
    return "进行中";
  }
  if (state === "failed") {
    return "失败";
  }
  if (state === "canceled") {
    return "已取消";
  }
  return "待执行";
}
</script>

<style scoped lang="scss">
.pipeline-stepper-shell {
  display: grid;
  gap: 10px;
  padding: 12px 16px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
}

.pipeline-stepper-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.pipeline-stepper-title {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
}

.pipeline-stepper-title strong {
  color: var(--app-color-text);
  font-size: 13px;
}

.pipeline-stage-current {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.pipeline-failure-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.task-disposition-fact {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border: 1px solid var(--app-color-danger-border);
  border-radius: var(--app-radius-pill);
  background: var(--app-color-danger-soft);
  font-size: 12px;
  line-height: 1.4;
}

.task-disposition-fact span {
  color: var(--app-color-text-muted);
}

.task-disposition-fact strong {
  color: var(--app-color-danger);
  font-weight: 600;
}

.pipeline-track {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0;
  padding: 4px 0 6px;
  list-style: none;
  overflow-x: auto;
}

.pipeline-node {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 0 auto;
  min-width: 112px;
}

.pipeline-node:last-child {
  flex: 0 0 auto;
}

.pipeline-node-marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  border: 1.5px solid var(--app-color-border);
  border-radius: var(--app-radius-pill);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.pipeline-node.is-done .pipeline-node-marker {
  border-color: var(--app-color-success);
  background: var(--app-color-success-soft);
  color: var(--app-color-success);
}

.pipeline-node.is-active .pipeline-node-marker {
  border-color: var(--app-color-primary);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary);
}

.pipeline-node.is-failed .pipeline-node-marker {
  border-color: var(--app-color-danger);
  background: var(--app-color-danger-soft);
  color: var(--app-color-danger);
}

.pipeline-node.is-canceled .pipeline-node-marker {
  border-color: var(--app-color-warning);
  background: var(--app-color-warning-soft);
  color: var(--app-color-warning);
}

.pipeline-active-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--app-radius-pill);
  background: var(--app-color-primary);
  animation: pipeline-pulse 1.6s ease-in-out infinite;
}

@keyframes pipeline-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.35);
    opacity: 0.55;
  }
}

@media (prefers-reduced-motion: reduce) {
  .pipeline-active-dot {
    animation: none;
  }
}

.pipeline-node-copy {
  display: grid;
  gap: 1px;
  min-width: 0;
}

.pipeline-node-copy strong {
  color: var(--app-color-text);
  font-size: 12px;
  line-height: 1.3;
  white-space: nowrap;
}

.pipeline-node.is-pending .pipeline-node-copy strong {
  color: var(--app-color-text-muted);
  font-weight: 500;
}

.pipeline-node.is-failed .pipeline-node-copy strong {
  color: var(--app-color-danger);
}

.pipeline-node-copy small {
  color: var(--app-color-text-faint);
  font-size: 11px;
  line-height: 1.2;
}

.pipeline-connector {
  flex: 1 1 16px;
  min-width: 14px;
  height: 2px;
  margin-right: 4px;
  border-radius: 1px;
  background: var(--app-color-border-soft);
}

.pipeline-node.is-done .pipeline-connector {
  background: var(--app-color-success-border);
}

.pipeline-node.is-failed .pipeline-connector {
  background: var(--app-color-danger-border);
}
</style>
