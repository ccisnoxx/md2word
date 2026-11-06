<template>
  <el-card class="page-section card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">事件流</h2>
        <p class="section-subtitle">阶段事件和排障 trace 信息。</p>
      </div>
      <div class="toolbar">
        <el-select v-model="eventLevelFilter" clearable placeholder="全部级别" style="width: 132px">
          <el-option label="info" value="info" />
          <el-option label="warning" value="warning" />
          <el-option label="error" value="error" />
        </el-select>
        <el-select v-model="eventStageFilter" clearable placeholder="全部阶段" style="width: 156px">
          <el-option
            v-for="stage in documentJobStages"
            :key="stage"
            :label="jobStageText[stage]"
            :value="stage"
          />
        </el-select>
        <el-button :icon="Refresh" :loading="eventsLoading" @click="loadEvents()">刷新事件</el-button>
      </div>
    </div>
    <ApiErrorAlert :error="eventsError" :diagnostic-context="jobErrorDiagnosticContext('document_jobs.events')" />
    <JobEventTimeline :events="filteredEvents" />
  </el-card>
</template>

<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobEventTimeline from "@/components/JobEventTimeline.vue";
import { documentJobStages, jobStageText } from "@/utils/format";
import type { UnwrapRef } from "vue";
import type { JobDetailData } from "./useJobDetailData";
import type { JobDetailDiagnostics } from "./useJobDetailDiagnostics";
const eventLevelFilter = defineModel<UnwrapRef<JobDetailData["eventLevelFilter"]>>("eventLevelFilter", { required: true });
const eventStageFilter = defineModel<UnwrapRef<JobDetailData["eventStageFilter"]>>("eventStageFilter", { required: true });
const {
  eventsLoading,
  eventsError,
  loadEvents,
  jobErrorDiagnosticContext,
  filteredEvents,
} = defineProps<{
  eventsLoading: UnwrapRef<JobDetailData["eventsLoading"]>;
  eventsError: UnwrapRef<JobDetailData["eventsError"]>;
  loadEvents: UnwrapRef<JobDetailData["loadEvents"]>;
  jobErrorDiagnosticContext: UnwrapRef<JobDetailData["jobErrorDiagnosticContext"]>;
  filteredEvents: UnwrapRef<JobDetailDiagnostics["filteredEvents"]>;
}>();
</script>

<style scoped lang="scss">

</style>
