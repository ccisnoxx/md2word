<!-- File: frontend/src/components/TermRuleYamlFallbackPanel.vue -->
<!-- Purpose: Render the advanced YAML fallback editor for Term Rule Set draft text. -->
<template>
  <el-card class="app-panel-card app-page-shell app-page-shell--wide" shadow="never">
    <el-collapse>
      <el-collapse-item title="YAML 高级编辑兜底" name="yaml">
        <el-alert
          class="yaml-warning"
          type="warning"
          title="这是高级兜底入口。主流程应优先使用结构化 draft rule 编辑，保存前会由后端校验 YAML。"
          :closable="false"
          show-icon
        />
        <el-input v-model="yamlText" type="textarea" :rows="14" class="mono" />
        <el-button class="yaml-save" type="warning" :loading="saving" @click="emit('save')">
          保存 YAML draft
        </el-button>
      </el-collapse-item>
    </el-collapse>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  saving: boolean;
}>();

const yamlText = defineModel<string>("yamlText", { required: true });
const emit = defineEmits<{
  save: [];
}>();
</script>

<style scoped lang="scss">
.yaml-warning,
.yaml-save {
  margin-top: 12px;
}

.yaml-warning {
  margin-bottom: 12px;
}
</style>
