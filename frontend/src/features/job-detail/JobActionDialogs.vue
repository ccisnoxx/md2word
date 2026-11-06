<template>
  <el-dialog
    v-model="retryDialogVisible"
    title="重试任务"
    width="min(640px, calc(100vw - 32px))"
    top="24px"
    class="job-action-dialog"
    append-to="body"
    :append-to-body="true"
  >
    <div class="job-action-dialog-scroll app-scrollbar-persistent">
      <el-form label-width="150px">
        <el-form-item label="任务 ID">
          <el-input :model-value="retryDialog.job?.id || ''" disabled />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="retryDialog.reason" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="配置策略">
          <el-radio-group v-model="retryDialog.strategy">
            <el-radio label="keep_original">沿用原配置</el-radio>
            <el-radio v-if="isAdmin" label="use_latest_term_assets">{{ usesTranslationResources(retryDialog.job) ? "使用最新规则与翻译术语默认值" : "使用最新符号与排版规则" }}</el-radio>
            <el-radio v-if="isAdmin" label="select_term_assets">{{ usesTranslationResources(retryDialog.job) ? "指定规则与翻译术语版本" : "指定规则版本" }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="isAdmin && retryDialog.strategy === 'select_term_assets'">
          <el-form-item label="符号与排版规则">
            <el-select
              v-model="retryDialog.termRuleVersion"
              clearable
              filterable
              :loading="configLoading"
              placeholder="沿用原符号与排版规则"
            >
              <el-option
                v-for="option in configSummary?.options.term_rule_sets || []"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="usesTranslationResources(retryDialog.job)" label="翻译术语集">
            <el-select
              v-model="retryDialog.translationTermVersion"
              clearable
              filterable
              :loading="configLoading"
              placeholder="沿用原翻译术语集"
            >
              <el-option
                v-for="option in configSummary?.options.translation_term_sets || []"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </el-form-item>
        </template>
        <el-alert
          v-if="isAdmin && retryDialog.strategy === 'use_latest_term_assets'"
          type="info"
          :closable="false"
          show-icon
          :title="usesTranslationResources(retryDialog.job) ? '重试只重绑符号与排版规则和翻译术语集默认值；模板和翻译配置沿用原任务快照。' : '重试只重绑符号与排版规则默认值；模板沿用原任务快照。'"
        />
        <ApiErrorAlert :error="configError" :diagnostic-context="jobErrorDiagnosticContext('document_jobs.config_summary')" />
      </el-form>
    </div>
    <template #footer>
      <el-button @click="retryDialogVisible = false">取消</el-button>
      <el-button type="warning" :loading="retryLoading" @click="submitRetryDialog">提交重试</el-button>
    </template>
  </el-dialog>
  <el-dialog
    v-model="cloneDialogVisible"
    title="重新发起为新任务"
    width="min(680px, calc(100vw - 32px))"
    top="24px"
    class="job-action-dialog"
    append-to="body"
    :append-to-body="true"
  >
    <div class="job-action-dialog-scroll app-scrollbar-persistent">
      <el-form label-width="150px">
        <el-form-item label="源任务 ID">
          <el-input :model-value="cloneDialog.job?.id || ''" disabled />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="cloneDialog.reason" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="配置策略">
          <el-radio-group v-model="cloneDialog.strategy">
            <el-radio label="keep_source_snapshot">沿用源任务快照</el-radio>
            <el-radio label="use_current_defaults">使用当前默认配置</el-radio>
            <el-radio v-if="isAdmin" label="select_published_versions">指定 published 版本</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="isAdmin && cloneDialog.strategy === 'select_published_versions'">
          <el-form-item label="Word 模板">
            <el-select
              v-model="cloneDialog.templateVersion"
              clearable
              filterable
              :loading="configLoading"
              placeholder="使用当前默认模板"
            >
              <el-option
                v-for="option in configSummary?.options.templates || []"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="符号与排版规则">
            <el-select
              v-model="cloneDialog.termRuleVersion"
              clearable
              filterable
              :loading="configLoading"
              placeholder="使用当前默认符号与排版规则"
            >
              <el-option
                v-for="option in configSummary?.options.term_rule_sets || []"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="usesTranslationResources(cloneDialog.job)" label="翻译术语集">
            <el-select
              v-model="cloneDialog.translationTermVersion"
              clearable
              filterable
              :loading="configLoading"
              placeholder="使用当前默认翻译术语集"
            >
              <el-option
                v-for="option in configSummary?.options.translation_term_sets || []"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="usesTranslationResources(cloneDialog.job)" label="翻译配置">
            <el-select
              v-model="cloneDialog.translationProfileVersion"
              clearable
              filterable
              :loading="configLoading"
              placeholder="使用当前默认翻译配置"
            >
              <el-option
                v-for="option in configSummary?.options.translation_profiles || []"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </el-form-item>
        </template>
        <el-alert
          v-if="cloneDialog.strategy === 'keep_source_snapshot'"
          type="info"
          :closable="false"
          show-icon
          title="重新发起会创建独立新任务；源任务状态、retry_count、归档状态都不会改变。"
        />
        <ApiErrorAlert :error="configError" :diagnostic-context="jobErrorDiagnosticContext('document_jobs.config_summary')" />
      </el-form>
    </div>
    <template #footer>
      <el-button @click="cloneDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="cloneLoading" @click="submitCloneDialog">创建新任务</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { configOptionKey } from "@/utils/configOptions";
import { usesTranslationResources } from "./jobDetailFormat";
import type { UnwrapRef } from "vue";
import type { JobDetailData } from "./useJobDetailData";
import type { JobDetailActions } from "./useJobDetailActions";
const retryDialogVisible = defineModel<UnwrapRef<JobDetailActions["retryDialogVisible"]>>("retryDialogVisible", { required: true });
const cloneDialogVisible = defineModel<UnwrapRef<JobDetailActions["cloneDialogVisible"]>>("cloneDialogVisible", { required: true });
const {
  jobErrorDiagnosticContext,
  retryLoading,
  cloneLoading,
  configError,
  configLoading,
  configSummary,
  retryDialog,
  cloneDialog,
  isAdmin,
  submitRetryDialog,
  submitCloneDialog,
} = defineProps<{
  jobErrorDiagnosticContext: UnwrapRef<JobDetailData["jobErrorDiagnosticContext"]>;
  retryLoading: UnwrapRef<JobDetailActions["retryLoading"]>;
  cloneLoading: UnwrapRef<JobDetailActions["cloneLoading"]>;
  configError: UnwrapRef<JobDetailActions["configError"]>;
  configLoading: UnwrapRef<JobDetailActions["configLoading"]>;
  configSummary: UnwrapRef<JobDetailActions["configSummary"]>;
  retryDialog: UnwrapRef<JobDetailActions["retryDialog"]>;
  cloneDialog: UnwrapRef<JobDetailActions["cloneDialog"]>;
  isAdmin: UnwrapRef<JobDetailActions["isAdmin"]>;
  submitRetryDialog: UnwrapRef<JobDetailActions["submitRetryDialog"]>;
  submitCloneDialog: UnwrapRef<JobDetailActions["submitCloneDialog"]>;
}>();
</script>

<style scoped lang="scss">

:global(.job-action-dialog) {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 48px);
  max-height: calc(100dvh - 48px);
  margin-bottom: 24px;
}

:global(.job-action-dialog .el-dialog__header),
:global(.job-action-dialog .el-dialog__footer) {
  flex: 0 0 auto;
}

:global(.job-action-dialog .el-dialog__body) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.job-action-dialog-scroll {
  max-height: min(620px, calc(100vh - 220px));
  max-height: min(620px, calc(100dvh - 220px));
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
}
</style>
