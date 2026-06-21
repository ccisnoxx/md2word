<!-- File: frontend/src/components/TermRuleDraftRuleDialog.vue -->
<!-- Purpose: Render the draft term-rule edit dialog while the page owns mutation flow. -->
<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="min(760px, calc(100vw - 32px))"
    top="24px"
    class="rule-dialog"
    append-to="body"
    :append-to-body="true"
  >
    <div class="rule-dialog-scroll">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="130px">
        <el-form-item label="源术语" prop="source_term">
          <el-input v-model="form.source_term" placeholder="例如 VIN" />
        </el-form-item>
        <el-form-item label="分类" prop="category_id">
          <el-select v-model="form.category_id" filterable placeholder="选择分类">
            <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="术语片段" prop="segments">
          <TermSegmentEditor v-model="form.segments" />
        </el-form-item>
        <el-form-item label="预览">
          <TermPreview :segments="form.segments" />
        </el-form-item>
        <div class="rule-form-grid">
          <el-form-item label="适用范围" prop="apply_scope">
            <el-select v-model="form.apply_scope">
              <el-option label="正文和表格" value="both" />
              <el-option label="仅正文 Markdown" value="markdown" />
              <el-option label="仅表格" value="table" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级" prop="priority">
            <el-input-number v-model="form.priority" :min="0" :max="10000" />
          </el-form-item>
          <el-form-item label="区分大小写">
            <el-switch v-model="form.case_sensitive" />
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="form.enabled" />
          </el-form-item>
        </div>
        <el-form-item label="自定义 Markdown">
          <el-input v-model="form.custom_markdown" clearable />
        </el-form-item>
        <el-form-item label="自定义 HTML">
          <el-input v-model="form.custom_html" clearable />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="emit('save')">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from "vue";
import type { FormInstance, FormRules } from "element-plus";

import type { TermRuleCategoryListItemResponse } from "@/api/types";
import type { RuleFormState } from "@/composables/useTermRuleForm";
import TermPreview from "@/components/TermPreview.vue";
import TermSegmentEditor from "@/components/TermSegmentEditor.vue";

defineProps<{
  title: string;
  form: RuleFormState;
  rules: FormRules;
  categories: TermRuleCategoryListItemResponse[];
  saving: boolean;
}>();

const visible = defineModel<boolean>("visible", { required: true });
const emit = defineEmits<{
  save: [];
}>();

const formRef = ref<FormInstance>();

async function validate(): Promise<boolean> {
  return (await formRef.value?.validate().catch(() => false)) || false;
}

defineExpose({ validate });
</script>

<style scoped lang="scss">
.rule-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: var(--app-space-4);
}

:global(.rule-dialog) {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 48px);
  max-height: calc(100dvh - 48px);
  margin-bottom: 24px;
}

:global(.rule-dialog .el-dialog__header),
:global(.rule-dialog .el-dialog__footer) {
  flex: 0 0 auto;
}

:global(.rule-dialog .el-dialog__body) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.rule-dialog-scroll {
  max-height: min(640px, calc(100vh - 220px));
  max-height: min(640px, calc(100dvh - 220px));
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
}

@media (max-width: 760px) {
  .rule-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
