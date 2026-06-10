<!-- frontend/src/components/ApiErrorAlert.vue: Render normalized API errors consistently. -->
<template>
  <el-alert v-if="error" class="api-error" type="error" :closable="false" show-icon>
    <template #title>{{ error.message }}</template>
    <div v-if="error.code || error.status || error.traceId" class="api-error-meta">
      <span v-if="error.status">状态码 {{ error.status }}</span>
      <span v-if="error.code">错误码 {{ error.code }}</span>
      <span v-if="error.traceId">追踪 ID {{ error.traceId }}</span>
    </div>
    <div v-if="operatorHint" class="api-error-hint">{{ operatorHint }}</div>
  </el-alert>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type { ApiClientError } from "@/utils/errors";

const props = defineProps<{
  error: ApiClientError | null;
}>();

const operatorHint = computed(() => {
  const error = props.error;
  if (!error) {
    return "";
  }
  if (error.status === 401 || error.code === "token_expired" || error.code === "invalid_token") {
    return "登录状态已失效，请重新登录后再继续操作。";
  }
  if (error.status === 403) {
    return "当前账号没有权限执行该操作，请切换账号或联系管理员确认角色。";
  }
  if (error.status === 409) {
    return "当前任务或资源状态不允许该操作，请刷新后按后端返回原因处理。";
  }
  if (error.status === 503) {
    return "后端服务或依赖暂不可用，请稍后重试；若持续发生，请带追踪 ID 联系技术运营。";
  }
  if (error.code === "timeout") {
    return "请求超时，任务可能仍在后端继续处理，请刷新列表或详情页确认最新状态。";
  }
  return "";
});
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

.api-error-hint {
  margin-top: 6px;
  color: #7a271a;
  font-size: 13px;
  line-height: 1.5;
}
</style>
