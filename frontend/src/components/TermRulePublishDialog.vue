<!-- File: frontend/src/components/TermRulePublishDialog.vue -->
<!-- Purpose: Render the Term Rule Set publish confirmation dialog and expose form validation. -->
<template>
  <el-dialog v-model="visible" title="发布 Term Rule Set draft" width="640px">
    <el-alert
      v-if="preflightReport?.blocking"
      class="dialog-alert"
      type="error"
      title="当前 draft 存在 blocking preflight finding，不能发布。"
      :closable="false"
      show-icon
    />
    <el-alert
      v-else-if="preflightReport && preflightReport.summary.warning_count > 0"
      class="dialog-alert"
      type="warning"
      title="当前 draft 存在 warning，发布前请确认影响。"
      :closable="false"
      show-icon
    />
    <el-table
      v-if="preflightFindings.length"
      :data="preflightFindings"
      size="small"
      class="dialog-findings"
      max-height="220"
    >
      <el-table-column prop="severity" label="级别" width="90" />
      <el-table-column prop="code" label="Code" width="190" show-overflow-tooltip />
      <el-table-column prop="message" label="说明" min-width="220" show-overflow-tooltip />
    </el-table>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="发布说明" prop="publish_reason">
        <el-input v-model="form.publish_reason" type="textarea" :rows="4" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        type="primary"
        :disabled="Boolean(preflightReport?.blocking)"
        :loading="publishing"
        @click="emit('publish')"
      >
        发布并设默认
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { FormInstance, FormRules } from "element-plus";

import type { TermRuleSetPreflightResponse } from "@/api/types";
import { termRulePreflightFindings } from "@/composables/useTermRuleGovernanceDisplay";

export type TermRulePublishFormState = {
  publish_reason: string;
};

const props = defineProps<{
  form: TermRulePublishFormState;
  rules: FormRules;
  preflightReport: TermRuleSetPreflightResponse | null;
  publishing: boolean;
}>();

const visible = defineModel<boolean>("visible", { required: true });
const emit = defineEmits<{
  publish: [];
}>();

const formRef = ref<FormInstance>();
const preflightFindings = computed(() => termRulePreflightFindings(props.preflightReport));

async function validate(): Promise<boolean> {
  return (await formRef.value?.validate().catch(() => false)) || false;
}

defineExpose({ validate });
</script>

<style scoped lang="scss">
.dialog-alert,
.dialog-findings {
  margin-top: 12px;
}
</style>
