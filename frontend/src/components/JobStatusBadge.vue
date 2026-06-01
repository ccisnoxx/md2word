<!-- frontend/src/components/JobStatusBadge.vue: Text badge for document job status. -->
<template>
  <el-tag :type="tagType" effect="light" round>{{ text }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type { DocumentJobStatus } from "@/api/types";
import { jobStatusText } from "@/utils/format";

const props = defineProps<{
  status: DocumentJobStatus | string;
}>();

const text = computed(() => jobStatusText[props.status as DocumentJobStatus] || props.status);
const tagType = computed(() => {
  switch (props.status) {
    case "succeeded":
      return "success";
    case "failed":
      return "danger";
    case "running":
      return "warning";
    case "canceled":
      return "info";
    default:
      return "primary";
  }
});
</script>
