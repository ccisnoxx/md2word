<!-- 文件：frontend/src/features/document-review/NewGenerationDialog.vue -->
<!-- 用途：Admin 标准同任务新代弹窗，严格保留客户端 UUID 幂等键并支持 503/500/网络未知结果对账。 -->
<template>
  <el-dialog
    v-model="action.visible.value"
    title="开始同任务新代"
    width="min(600px, calc(100vw - 32px))"
    top="24px"
    class="new-generation-dialog"
    :append-to-body="true"
  >
    <div class="new-gen-scroll app-scrollbar-persistent">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="同任务新代会沿用原任务模式与绑定快照发起新一代转换，不修改原配置；客户端已锁定本次幂等请求 ID。"
      />

      <ApiErrorAlert :error="action.error.value" />

      <el-alert
        v-if="action.form.needsReconcile"
        type="warning"
        :closable="false"
        show-icon
        title="上次提交结果未确认，已保留同一请求 ID，禁止自动更换幂等键重复提交"
      >
        <div class="reconcile-box">
          <p>
            保留的请求 ID：<strong class="mono">{{ action.form.requestId }}</strong>
          </p>
          <p v-if="action.error.value?.acceptedGeneration !== undefined">
            后端提示已受理代次：第 {{ action.error.value.acceptedGeneration + 1 }} 代（请点击下方对账确认最新任务状态）。
          </p>
          <p v-if="action.form.notFoundOnReconcile">
            对账返回 404：后端未查到该请求 ID 的受理记录。确认无需继续等待后，可点击「重置请求 ID」重新发起。
          </p>
          <div class="reconcile-actions">
            <el-button type="warning" :loading="action.reconciling.value" @click="action.reconcile()">
              对账请求结果
            </el-button>
            <el-button
              v-if="action.form.notFoundOnReconcile"
              text
              type="primary"
              @click="action.resetAfterNotFound(latestExpectedSource)"
            >
              重置请求 ID
            </el-button>
          </div>
        </div>
      </el-alert>

      <el-alert
        v-if="action.lastResult.value"
        type="success"
        :closable="false"
        show-icon
        :title="`新代请求已受理：第 ${action.lastResult.value.accepted_generation + 1} 代`"
      >
        <div class="reconcile-result">
          <span>当前代次：第 {{ action.lastResult.value.current_generation + 1 }} 代</span>
          <span>任务状态：{{ jobStatusText[action.lastResult.value.current_job.status] || action.lastResult.value.current_job.status }}</span>
          <span>当前阶段：{{ jobStageText[action.lastResult.value.current_job.stage] || action.lastResult.value.current_job.stage }}</span>
          <span class="mono">审计 ID：{{ action.lastResult.value.audit_id }}</span>
        </div>
      </el-alert>

      <el-descriptions v-if="action.form.expectedSource" :column="2" border size="small" class="source-meta">
        <el-descriptions-item label="任务 ID">
          <span class="mono">{{ jobId }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="锁定来源代次">
          第 {{ action.form.expectedSource.generation + 1 }} 代
        </el-descriptions-item>
        <el-descriptions-item label="幂等请求 ID" :span="2">
          <span class="mono">{{ action.form.requestId }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="当前主件摘要" :span="2">
          <span class="mono">{{ shortHash(action.form.expectedSource.result_sha256, 20) }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-form label-position="top">
        <el-form-item label="新代原因说明（1–1000 字）" required>
          <el-input
            v-model="action.form.note"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
            :disabled="action.form.needsReconcile || Boolean(action.lastResult.value)"
            placeholder="例如：复核发现表格渲染异常，使用同源输入发起新一轮生成"
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="action.close()">关闭</el-button>
      <el-button
        v-if="!action.lastResult.value"
        type="primary"
        :loading="action.submitting.value"
        :disabled="!action.canSubmit.value"
        @click="action.submit()"
      >
        确认发起同任务新代
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import type { ReviewExpectedSourceRequest } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { jobStageText, jobStatusText } from "@/utils/format";
import { shortHash } from "./documentReviewFormat";
import type { NewGenerationAction } from "./useNewGenerationAction";

defineProps<{
  jobId: string;
  action: NewGenerationAction;
  latestExpectedSource?: ReviewExpectedSourceRequest | null;
}>();
</script>

<style scoped lang="scss">
.new-gen-scroll {
  display: grid;
  gap: 12px;
  max-height: min(560px, calc(100vh - 220px));
  overflow-y: auto;
  padding-right: 4px;
}

.reconcile-box {
  display: grid;
  gap: 8px;
  font-size: 13px;
}

.reconcile-box p {
  margin: 0;
}

.reconcile-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.reconcile-result {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13px;
}

.source-meta {
  width: 100%;
}
</style>
