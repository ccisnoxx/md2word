<template>
  <el-dialog v-model="deleteDialog.visible" title="执行物理删除" width="640px">
    <el-alert class="delete-warning" type="error" title="不可逆操作" :closable="false" show-icon>
      该操作会删除 selected expired local/local_object 文件内容；metadata 行、任务记录、事件和 object_key 会保留。
    </el-alert>
    <el-form label-position="top">
      <el-form-item label="Selected file IDs">
        <el-input :model-value="selectedFileIds.join('\n')" type="textarea" :rows="4" readonly class="mono" />
      </el-form-item>
      <el-form-item label="Reason">
        <el-input v-model="deleteDialog.reason" type="textarea" :rows="2" placeholder="说明为什么执行本次物理删除" />
      </el-form-item>
      <el-form-item label="Confirmation phrase">
        <el-input v-model="deleteDialog.confirmation" :placeholder="deleteReport?.confirmation_phrase || 'DELETE EXPIRED FILES'" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="deleteDialog.visible = false">取消</el-button>
      <el-button type="danger" :disabled="!canSubmitPhysicalDelete" :loading="deleting" @click="executePhysicalDelete">
        确认物理删除
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="cleanupRunDialog.visible" title="执行 manual cleanup run" width="720px">
    <el-alert class="delete-warning" type="error" title="受控删除合同" :closable="false" show-icon>
      cleanup run 会复用 selected-file physical-delete 合同：不会启动 scheduler，不会调用 provider，不会执行 S3 delete；execute 必须携带本次 preview_hash、signed plan、reason 和确认短语。
    </el-alert>
    <el-form label-position="top">
      <el-form-item label="Selected file IDs">
        <el-input :model-value="cleanupRunReport?.requested_file_ids.join('\n') || ''" type="textarea" :rows="4" readonly class="mono" />
      </el-form-item>
      <el-form-item label="Preview Hash">
        <el-input :model-value="cleanupRunReport?.preview_hash || ''" readonly class="mono" />
      </el-form-item>
      <el-form-item label="Signed Plan">
        <el-input :model-value="cleanupRunReport?.cleanup_plan?.plan_id || ''" readonly class="mono" />
      </el-form-item>
      <el-form-item label="Reason">
        <el-input v-model="cleanupRunDialog.reason" type="textarea" :rows="2" placeholder="说明为什么执行本次 cleanup run" />
      </el-form-item>
      <el-form-item label="Confirmation phrase">
        <el-input v-model="cleanupRunDialog.confirmation" :placeholder="cleanupRunReport?.confirmation_phrase || 'EXECUTE AUTOMATED RETENTION CLEANUP'" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="cleanupRunDialog.visible = false">取消</el-button>
      <el-button type="danger" :disabled="!canSubmitCleanupRun" :loading="cleanupExecuting" @click="executeCleanupRun">
        确认 cleanup run
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="policyDialog.visible" :title="policyDialog.policyId ? '编辑保留策略' : '新增保留策略 draft'" width="640px">
    <el-alert class="delete-warning" type="info" title="不会回填历史文件" :closable="false" show-icon>
      创建或编辑 draft 不影响新文件；发布后只影响后续新文件 expires_at，历史文件需要单独 dry-run backfill 任务。
    </el-alert>
    <el-form label-position="top">
      <el-form-item label="Name">
        <el-input v-model="policyDialog.form.name" placeholder="例如 Generated Word 30 days" />
      </el-form-item>
      <el-form-item label="Scope">
        <el-select v-model="policyDialog.form.scope_type">
          <el-option label="global" value="global" />
          <el-option label="file_type" value="file_type" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="policyDialog.form.scope_type === 'file_type'" label="File Type">
        <el-select v-model="policyDialog.form.file_type" filterable>
          <el-option v-for="fileType in fileTypeOptions" :key="fileType" :label="fileType" :value="fileType" />
        </el-select>
      </el-form-item>
      <el-form-item label="Retention Days">
        <el-input-number v-model="policyDialog.form.retention_days" :min="1" :max="3650" />
      </el-form-item>
      <el-form-item label="Description">
        <el-input v-model="policyDialog.form.description" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="policyDialog.visible = false">取消</el-button>
      <el-button type="primary" :loading="policySaving" @click="savePolicy">保存 draft</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
// 物理删除、cleanup run 执行与策略 draft 编辑三个确认对话框。
import type { UnwrapRef } from "vue";
import { fileTypeOptions } from "./retentionFormat";
import type { RetentionCleanup } from "./useRetentionCleanup";
import type { RetentionPolicy } from "./useRetentionPolicy";

const {
  deleteDialog,
  selectedFileIds,
  deleteReport,
  canSubmitPhysicalDelete,
  deleting,
  executePhysicalDelete,
  cleanupRunDialog,
  cleanupRunReport,
  canSubmitCleanupRun,
  cleanupExecuting,
  executeCleanupRun,
  policyDialog,
  policySaving,
  savePolicy,
} = defineProps<{
  deleteDialog: UnwrapRef<RetentionCleanup["deleteDialog"]>;
  selectedFileIds: UnwrapRef<RetentionCleanup["selectedFileIds"]>;
  deleteReport: UnwrapRef<RetentionCleanup["deleteReport"]>;
  canSubmitPhysicalDelete: UnwrapRef<RetentionCleanup["canSubmitPhysicalDelete"]>;
  deleting: UnwrapRef<RetentionCleanup["deleting"]>;
  executePhysicalDelete: UnwrapRef<RetentionCleanup["executePhysicalDelete"]>;
  cleanupRunDialog: UnwrapRef<RetentionCleanup["cleanupRunDialog"]>;
  cleanupRunReport: UnwrapRef<RetentionCleanup["cleanupRunReport"]>;
  canSubmitCleanupRun: UnwrapRef<RetentionCleanup["canSubmitCleanupRun"]>;
  cleanupExecuting: UnwrapRef<RetentionCleanup["cleanupExecuting"]>;
  executeCleanupRun: UnwrapRef<RetentionCleanup["executeCleanupRun"]>;
  policyDialog: UnwrapRef<RetentionPolicy["policyDialog"]>;
  policySaving: UnwrapRef<RetentionPolicy["policySaving"]>;
  savePolicy: UnwrapRef<RetentionPolicy["savePolicy"]>;
}>();
</script>

<style scoped lang="scss">
.mono {
  font-family: var(--app-font-mono);
  font-size: 12px;
}

.delete-warning {
  margin-bottom: var(--app-space-4);
}
</style>
