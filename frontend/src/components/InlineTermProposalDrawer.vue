<!-- 文件：frontend/src/components/InlineTermProposalDrawer.vue -->
<!-- 用途：在复核工作台与翻译 QA 页内就地提议翻译术语，不离开当前块或片段上下文。 -->
<template>
  <el-drawer
    v-model="visible"
    title="从此段提议翻译术语"
    direction="rtl"
    size="min(460px, 94vw)"
    :append-to-body="true"
    class="inline-term-proposal-drawer"
    @open="syncFormOnOpen"
  >
    <div class="inline-proposal-body app-scrollbar-persistent">
      <ApiErrorAlert :error="submitError" />

      <div class="proposal-context-card">
        <div class="proposal-context-tags">
          <el-tag size="small" effect="plain">语言方向：{{ resolvedLanguagePair || "未识别" }}</el-tag>
          <el-tag v-if="observedVersionLabel" size="small" type="info" effect="plain" class="mono">
            术语集：{{ observedVersionLabel }}
          </el-tag>
        </div>
        <p v-if="contextSummary" class="proposal-context-summary">{{ contextSummary }}</p>
        <div v-if="sourceExcerpt" class="proposal-excerpt">
          <span>当前片段摘录</span>
          <p>{{ sourceExcerpt }}</p>
        </div>
      </div>

      <el-form label-position="top" class="proposal-form">
        <el-form-item label="变更动作">
          <el-radio-group v-model="form.action" @change="handleActionChange">
            <el-radio-button value="add">新增术语</el-radio-button>
            <el-radio-button value="update">修改译法</el-radio-button>
            <el-radio-button value="delete">停用/删除</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="源术语" required>
          <el-input
            v-model="form.sourceTerm"
            maxlength="200"
            placeholder="输入需要统一的原文术语（如 Input Offset Voltage）"
          />
        </el-form-item>

        <el-form-item v-if="form.action !== 'delete'" label="建议目标译文" required>
          <el-input
            v-model="form.targetTerm"
            maxlength="200"
            placeholder="输入标准目标译文（如 输入失调电压）"
          />
        </el-form-item>

        <el-form-item label="大小写敏感">
          <el-switch v-model="form.caseSensitive" active-text="区分大小写" inactive-text="不区分" />
        </el-form-item>

        <el-form-item label="提议说明与上下文备注">
          <el-input
            v-model="form.note"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="说明为何建议采用此译法，便于术语审核员快速判断"
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <div class="inline-proposal-footer">
        <el-button :disabled="submitting" @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="handleSubmit">
          提交术语建议
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { translationTermProposalsApi } from "@/api/termProposals";
import type {
  DocumentJobResponse,
  TranslationTermProposalAction,
  TranslationTermProposalResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { languagePairFromJobMode } from "@/features/document-review/documentReviewFormat";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const visible = defineModel<boolean>({ required: true });

const props = defineProps<{
  job: DocumentJobResponse | null;
  observedTermSetId?: string | null;
  observedTermVersion?: string | null;
  initialSourceTerm?: string;
  initialTargetTerm?: string;
  contextSummary?: string;
  sourceExcerpt?: string;
}>();

const emit = defineEmits<{
  submitted: [proposal: TranslationTermProposalResponse];
}>();

const submitting = ref(false);
const submitError = ref<ApiClientError | null>(null);

const form = reactive<{
  action: TranslationTermProposalAction;
  sourceTerm: string;
  targetTerm: string;
  caseSensitive: boolean;
  note: string;
}>({
  action: "add",
  sourceTerm: "",
  targetTerm: "",
  caseSensitive: false,
  note: "",
});

const resolvedLanguagePair = computed(() => languagePairFromJobMode(props.job?.mode) || "");

const observedVersionLabel = computed(() => {
  if (!props.observedTermSetId && !props.observedTermVersion) {
    return "";
  }
  return `${props.observedTermSetId || "-"}@${props.observedTermVersion || "-"}`;
});

const canSubmit = computed(() => {
  if (!resolvedLanguagePair.value || !form.sourceTerm.trim()) {
    return false;
  }
  if (form.action !== "delete" && !form.targetTerm.trim()) {
    return false;
  }
  return !submitting.value;
});

function syncFormOnOpen(): void {
  submitError.value = null;
  form.action = "add";
  form.sourceTerm = (props.initialSourceTerm || "").trim();
  form.targetTerm = (props.initialTargetTerm || "").trim();
  form.caseSensitive = false;
  form.note = props.contextSummary ? `来源：${props.contextSummary}` : "";
}

function handleActionChange(): void {
  if (form.action === "delete") {
    form.targetTerm = "";
  }
}

async function handleSubmit(): Promise<void> {
  if (!canSubmit.value || !props.job) {
    return;
  }
  submitting.value = true;
  submitError.value = null;
  try {
    const response = await translationTermProposalsApi.create({
      language_pair: resolvedLanguagePair.value,
      source_job_id: props.job.id,
      source_file_id: props.job.source_file_id,
      observed_translation_term_set_id: props.observedTermSetId || null,
      observed_translation_term_version: props.observedTermVersion || null,
      changes: [
        {
          action: form.action,
          source_term: form.sourceTerm.trim(),
          target_term: form.action === "delete" ? null : form.targetTerm.trim(),
          case_sensitive: form.caseSensitive,
          note: form.note.trim() || null,
        },
      ],
    });
    ElMessage.success("翻译术语建议已提交，可继续当前审阅。");
    visible.value = false;
    emit("submitted", response);
  } catch (caught) {
    submitError.value = normalizeApiError(caught);
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped lang="scss">
.inline-proposal-body {
  display: grid;
  gap: 14px;
  max-height: calc(100vh - 150px);
  overflow-y: auto;
  padding-right: 4px;
}

.proposal-context-card {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
}

.proposal-context-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.proposal-context-summary {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.proposal-excerpt {
  display: grid;
  gap: 4px;
}

.proposal-excerpt span {
  color: var(--app-color-text-faint);
  font-size: 12px;
  font-weight: 600;
}

.proposal-excerpt p {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 120px;
  overflow-y: auto;
}

.inline-proposal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
