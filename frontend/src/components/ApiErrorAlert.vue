<!-- frontend/src/components/ApiErrorAlert.vue: Render normalized API errors consistently. -->
<template>
  <el-alert v-if="error" class="api-error" type="error" :closable="false" show-icon>
    <template #title>{{ error.message }}</template>
    <div v-if="error.code || error.status || error.traceId" class="api-error-meta">
      <span v-if="error.status">HTTP {{ error.status }}</span>
      <span v-if="error.code">error_code={{ error.code }}</span>
      <span v-if="error.traceId">trace_id={{ error.traceId }}</span>
    </div>
  </el-alert>
</template>

<script setup lang="ts">
import type { ApiClientError } from "@/utils/errors";

defineProps<{
  error: ApiClientError | null;
}>();
</script>

<style scoped lang="scss">
.api-error {
  margin-bottom: 12px;
}

.api-error-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 4px;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}
</style>
