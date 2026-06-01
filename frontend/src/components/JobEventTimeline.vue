<!-- frontend/src/components/JobEventTimeline.vue: Timeline display for document job events. -->
<template>
  <el-empty v-if="events.length === 0" description="暂无事件" />
  <el-timeline v-else class="event-timeline">
    <el-timeline-item
      v-for="event in events"
      :key="event.id"
      :timestamp="formatDateTime(event.created_at)"
      :type="timelineType(event.level)"
      placement="top"
    >
      <div class="event-row">
        <div class="event-heading">
          <el-tag size="small" :type="levelTagType(event.level)">{{ event.level }}</el-tag>
          <span class="mono">{{ event.event_type }}</span>
          <span class="muted">{{ stageText(event.stage) }}</span>
        </div>
        <div class="event-message">{{ event.message }}</div>
        <div v-if="event.duration_ms !== null || event.trace_id" class="event-meta">
          <span v-if="event.duration_ms !== null">{{ event.duration_ms }} ms</span>
          <span v-if="event.trace_id">trace_id={{ event.trace_id }}</span>
        </div>
      </div>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup lang="ts">
import type { DocumentJobEventResponse, DocumentJobStage } from "@/api/types";
import { formatDateTime, jobStageText } from "@/utils/format";

defineProps<{
  events: DocumentJobEventResponse[];
}>();

function stageText(stage: DocumentJobStage): string {
  return jobStageText[stage] || stage;
}

function timelineType(level: string): "primary" | "success" | "warning" | "danger" | "info" {
  if (level === "error") {
    return "danger";
  }
  if (level === "warning") {
    return "warning";
  }
  return "primary";
}

function levelTagType(level: string): "primary" | "success" | "warning" | "danger" | "info" {
  if (level === "error") {
    return "danger";
  }
  if (level === "warning") {
    return "warning";
  }
  return "info";
}
</script>

<style scoped lang="scss">
.event-timeline {
  padding-left: 4px;
}

.event-row {
  padding-bottom: 4px;
}

.event-heading,
.event-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.event-message {
  margin: 6px 0;
  color: #1f2937;
}

.event-meta {
  color: #667085;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}
</style>
