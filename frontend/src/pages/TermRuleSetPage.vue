<!-- frontend/src/pages/TermRuleSetPage.vue: Term Rule Set draft summary, publish, defaults and rollback. -->
<template>
  <main class="term-rule-set-page" aria-labelledby="term-rule-set-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Term Rule Set</p>
        <h1 id="term-rule-set-title">术语规则集</h1>
        <p>查看默认版本、published versions、draft 摘要和已审核待发布 proposal。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </section>

    <ApiErrorAlert :error="error" />

    <el-alert
      v-if="unavailable"
      type="warning"
      title="当前部署未启用 MySQL resource service，Term Rule Set 版本管理不可用。"
      :closable="false"
      show-icon
    />

    <section v-else class="rule-set-grid">
      <el-card class="card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">规则集选择</h2>
            <p class="section-subtitle">V2.1 按现有规则集管理，不新建规则集。</p>
          </div>
        </div>
        <el-select v-model="selectedSetId" :disabled="loading" placeholder="选择规则集" @change="loadSelectedSet">
          <el-option v-for="item in sets" :key="item.id" :label="item.id" :value="item.id" />
        </el-select>
      </el-card>

      <el-card class="card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Draft 摘要</h2>
            <p class="section-subtitle">V2.1 不做完整 draft-vs-default diff。</p>
          </div>
          <el-tag v-if="draft?.snapshot_hash" effect="plain" class="mono">{{ draft.snapshot_hash }}</el-tag>
        </div>
        <dl class="summary-list">
          <div><dt>base version</dt><dd>{{ draft?.base_version || "-" }}</dd></div>
          <div><dt>rule_count</dt><dd>{{ draft?.rule_count ?? "-" }}</dd></div>
          <div><dt>enabled_rule_count</dt><dd>{{ draft?.enabled_rule_count ?? "-" }}</dd></div>
        </dl>
        <RoleGate>
          <el-button type="primary" :disabled="!selectedSetId" @click="openPublishDialog">发布 draft</el-button>
        </RoleGate>
      </el-card>
    </section>

    <el-card v-if="!unavailable" class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Published versions</h2>
          <p class="section-subtitle">set-default 和 rollback 只允许使用已发布版本。</p>
        </div>
      </div>
      <el-table :data="detail?.versions || []" :loading="loading" empty-text="暂无 published version">
        <el-table-column prop="version" label="版本" width="120" />
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
        <el-table-column prop="rule_count" label="规则数" width="100" />
        <el-table-column prop="enabled_rule_count" label="启用规则" width="110" />
        <el-table-column prop="snapshot_hash" label="snapshot" min-width="180" show-overflow-tooltip />
        <el-table-column label="发布时间" width="190">
          <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column prop="publish_reason" label="发布说明" min-width="180" show-overflow-tooltip />
        <el-table-column v-if="isAdmin" label="admin 操作" width="210" fixed="right">
          <template #default="{ row }">
            <RoleGate>
              <el-button link type="warning" :disabled="row.is_default" @click="setDefault(row.version)">设默认</el-button>
              <el-button link type="danger" @click="rollback(row.version)">Rollback</el-button>
            </RoleGate>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <RoleGate>
      <el-card v-if="!unavailable" class="card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">已 approve 待核对 proposals</h2>
            <p class="section-subtitle">发布前核对本次已审核合并的来源建议。</p>
          </div>
        </div>
        <TermProposalTable :items="approvedProposals" :categories="categoryMap" :loading="loading" @select="noop" />
      </el-card>
    </RoleGate>

    <RoleGate>
      <el-card v-if="!unavailable" class="card-flat" shadow="never">
        <el-collapse>
          <el-collapse-item title="YAML 高级编辑兜底" name="yaml">
            <el-alert
              class="yaml-warning"
              type="warning"
              title="这是高级兜底入口。主流程应通过 proposal 审核合并 draft，保存前会由后端校验 YAML。"
              :closable="false"
              show-icon
            />
            <el-input v-model="yamlText" type="textarea" :rows="14" class="mono" />
            <el-button class="yaml-save" type="warning" :loading="savingYaml" @click="saveYamlDraft">
              保存 YAML draft
            </el-button>
          </el-collapse-item>
        </el-collapse>
      </el-card>
    </RoleGate>

    <el-dialog v-model="publishDialog.visible" title="发布 Term Rule Set draft" width="540px">
      <el-form ref="publishFormRef" :model="publishDialog.form" :rules="publishRules" label-width="100px">
        <el-form-item label="发布说明" prop="publish_reason">
          <el-input v-model="publishDialog.form.publish_reason" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="publishDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="publishing" @click="publishDraft">发布并设默认</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";

import { termProposalsApi } from "@/api/termProposals";
import { termRulesApi } from "@/api/termRules";
import { termRuleSetsApi } from "@/api/termRuleSets";
import type {
  TermRuleCategoryListItemResponse,
  TermRuleProposalResponse,
  TermRuleSetDetailResponse,
  TermRuleSetDraftResponse,
  TermRuleSetListItemResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import TermProposalTable from "@/components/TermProposalTable.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

const auth = useAuthStore();
const isAdmin = computed(() => auth.user?.role === "admin");
const sets = ref<TermRuleSetListItemResponse[]>([]);
const selectedSetId = ref("");
const detail = ref<TermRuleSetDetailResponse | null>(null);
const draft = ref<TermRuleSetDraftResponse | null>(null);
const yamlText = ref("");
const approvedProposals = ref<TermRuleProposalResponse[]>([]);
const categories = ref<TermRuleCategoryListItemResponse[]>([]);
const loading = ref(false);
const publishing = ref(false);
const savingYaml = ref(false);
const unavailable = ref(false);
const error = ref<ApiClientError | null>(null);
const publishFormRef = ref<FormInstance>();

const publishDialog = reactive({
  visible: false,
  form: {
    publish_reason: "",
  },
});

const publishRules: FormRules = {
  publish_reason: [{ required: true, message: "请填写发布说明", trigger: "blur" }],
};

const categoryMap = computed(() =>
  Object.fromEntries(categories.value.map((category) => [category.id, category.name])),
);

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  unavailable.value = false;
  try {
    const [setResponse, categoryResponse] = await Promise.all([
      termRuleSetsApi.list(),
      termRulesApi.listCategories(),
    ]);
    sets.value = setResponse.items;
    categories.value = categoryResponse.items;
    selectedSetId.value ||= sets.value[0]?.id || "";
    if (selectedSetId.value) {
      await loadSelectedSet();
    }
    if (auth.user?.role === "admin") {
      approvedProposals.value = (await termProposalsApi.list({ scope: "all", status: "approved" })).items;
    }
  } catch (caught) {
    const normalized = normalizeApiError(caught);
    if (normalized.status === 503) {
      unavailable.value = true;
    }
    error.value = normalized;
  } finally {
    loading.value = false;
  }
}

async function loadSelectedSet(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const [detailResponse, draftResponse] = await Promise.all([
    termRuleSetsApi.get(selectedSetId.value),
    termRuleSetsApi.getDraft(selectedSetId.value),
  ]);
  detail.value = detailResponse;
  draft.value = draftResponse;
  yamlText.value = draftResponse.yaml_text;
}

function openPublishDialog(): void {
  publishDialog.form.publish_reason = "";
  publishDialog.visible = true;
}

async function publishDraft(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const valid = await publishFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  publishing.value = true;
  error.value = null;
  try {
    await termRuleSetsApi.publish(selectedSetId.value, {
      make_default: true,
      publish_reason: publishDialog.form.publish_reason,
    });
    ElMessage.success("Term Rule Set draft 已发布。");
    publishDialog.visible = false;
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    publishing.value = false;
  }
}

async function setDefault(version: string): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm("将该 published version 切换为默认术语规则集版本。", `设默认 ${version}`, {
      confirmButtonText: "设默认",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  error.value = null;
  try {
    await termRuleSetsApi.setDefault(selectedSetId.value, version);
    ElMessage.success("默认术语规则集已切换。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function rollback(version: string): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm("Rollback 会基于该版本恢复规则集，请确认这是已发布版本。", `Rollback ${version}`, {
      confirmButtonText: "Rollback",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  error.value = null;
  try {
    await termRuleSetsApi.rollback(selectedSetId.value, { version });
    ElMessage.success("已完成 rollback。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function saveYamlDraft(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  savingYaml.value = true;
  error.value = null;
  try {
    const response = await termRuleSetsApi.updateDraft(selectedSetId.value, { yaml_text: yamlText.value });
    draft.value = response;
    yamlText.value = response.yaml_text;
    ElMessage.success("YAML draft 已保存。");
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    savingYaml.value = false;
  }
}

function noop(): void {
  return;
}

onMounted(() => {
  void loadAll();
});
</script>

<style scoped lang="scss">
.term-rule-set-page {
  display: grid;
  gap: 16px;
}

.rule-set-grid {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 16px;
}

.summary-list {
  display: grid;
  gap: 10px;
  margin: 0 0 16px;
}

.summary-list div {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 10px;
}

.summary-list dt {
  color: #667085;
}

.summary-list dd {
  margin: 0;
  font-weight: 650;
}

.yaml-warning,
.yaml-save {
  margin-top: 12px;
}

.yaml-warning {
  margin-bottom: 12px;
}

@media (max-width: 880px) {
  .rule-set-grid {
    grid-template-columns: 1fr;
  }
}
</style>
