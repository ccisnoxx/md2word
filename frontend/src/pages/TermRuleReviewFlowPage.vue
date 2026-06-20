<!-- File: frontend/src/pages/TermRuleReviewFlowPage.vue -->
<!-- Purpose: MVP UI for scoped term rule review batches, item approval, and version history. -->
<template>
  <main class="term-rule-review-flow-page app-page" aria-labelledby="term-rule-review-flow-title">
    <section class="page-heading app-page-header app-page-shell app-page-shell--wide">
      <div>
        <p class="page-kicker">Term Rule Review</p>
        <h1 id="term-rule-review-flow-title" class="page-title">术语规则审核流</h1>
        <p class="page-description">规则变更先进入待审批次；单条通过后立即发布到当前生效规则。</p>
      </div>
      <div class="page-actions app-action-row">
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </section>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <section class="review-layout app-page-shell app-page-shell--wide">
      <section class="app-panel-card review-panel">
        <div class="section-header">
          <div>
            <h2 class="section-title">提交变更</h2>
            <p class="section-subtitle">普通用户提交本部门规则；管理员可选择 global 或部门 scope。</p>
          </div>
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
          <el-form-item label="动作" prop="action">
            <el-segmented v-model="form.action" :options="actionOptions" @change="handleActionChange" />
          </el-form-item>
          <el-form-item v-if="form.action !== 'create'" label="目标规则" prop="target_rule_id">
            <el-select v-model="form.target_rule_id" filterable placeholder="选择当前生效规则" @change="applyTargetRule">
              <el-option
                v-for="rule in effectiveRules"
                :key="rule.id"
                :label="`${rule.source_term} / ${scopeLabel(rule)} / v${rule.current_version}`"
                :value="rule.id"
              />
            </el-select>
          </el-form-item>
          <template v-if="form.action !== 'delete'">
            <el-form-item label="原文术语" prop="source_term">
              <el-input v-model="form.source_term" placeholder="例如 VIN" />
            </el-form-item>
            <el-form-item label="分类" prop="category_id">
              <el-select v-model="form.category_id" filterable placeholder="选择分类">
                <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="展示分段" prop="segments">
              <TermSegmentEditor v-model="form.segments" />
            </el-form-item>
          </template>
          <template v-if="isAdmin">
            <el-form-item label="规则域">
              <el-segmented v-model="form.scope_type" :options="scopeOptions" />
            </el-form-item>
            <el-form-item v-if="form.scope_type === 'department'" label="部门 ID" prop="scope_id">
              <el-input v-model="form.scope_id" placeholder="例如 default_department" />
            </el-form-item>
          </template>
          <el-form-item label="原因说明" prop="reason">
            <el-input v-model="form.reason" type="textarea" :rows="3" placeholder="说明来源、问题和期望效果。" />
          </el-form-item>
          <el-table :data="queuedItems" empty-text="当前批次暂无变更" size="small">
            <el-table-column prop="action" label="动作" width="86" />
            <el-table-column label="术语" min-width="140">
              <template #default="{ row }">
                {{ row.source_term || row.target_rule_id || "-" }}
              </template>
            </el-table-column>
            <el-table-column label="规则域" width="130">
              <template #default="{ row }">
                {{ queuedScopeLabel(row) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ $index }">
                <el-button link type="danger" :icon="Delete" @click="removeQueuedItem($index)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="form-actions">
            <el-button :icon="Plus" @click="addItemToBatch">加入批次</el-button>
            <el-button type="primary" :loading="submitting" @click="submitBatch">
              提交批次 {{ queuedItems.length ? `(${queuedItems.length})` : "" }}
            </el-button>
          </div>
        </el-form>
      </section>

      <section class="app-panel-card review-panel">
        <div class="section-header">
          <div>
            <h2 class="section-title">我的批次</h2>
            <p class="section-subtitle">批次状态由其审核项自动推导。</p>
          </div>
          <el-tag effect="plain">共 {{ batchTotal }} 批</el-tag>
        </div>

        <el-table :data="batches" :loading="loading" empty-text="暂无批次" size="small">
          <el-table-column prop="id" label="批次" min-width="150" show-overflow-tooltip />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="batchTagType(row.status)" effect="plain">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="进度" width="150">
            <template #default="{ row }">
              {{ row.summary.approved }}/{{ row.summary.total }} 通过
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="提交时间" min-width="170" />
          <el-table-column label="详情" width="80" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openBatch(row.id)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-pagination">
          <el-pagination
            v-model:current-page="batchPage.page"
            v-model:page-size="batchPage.pageSize"
            background
            layout="total, prev, pager, next"
            :total="batchTotal"
            @current-change="loadBatches"
          />
        </div>
      </section>
    </section>

    <section v-if="isAdmin" class="admin-grid app-page-shell app-page-shell--wide">
      <section class="app-panel-card review-panel">
        <div class="section-header">
          <div>
            <h2 class="section-title">待审项</h2>
            <p class="section-subtitle">每条独立审核；冲突项会标记 conflict，不阻塞同批其他项。</p>
          </div>
        </div>
        <el-table :data="pendingItems" :loading="loading" empty-text="暂无待审项" size="small">
          <el-table-column prop="batch_id" label="批次" min-width="140" show-overflow-tooltip />
          <el-table-column prop="action" label="动作" width="88" />
          <el-table-column label="术语" min-width="150">
            <template #default="{ row }">
              {{ snapshotTerm(row) }}
            </template>
          </el-table-column>
          <el-table-column label="规则域" width="150">
            <template #default="{ row }">
              {{ row.scope_type === "global" ? "全局" : `部门 ${row.scope_id || "-"}` }}
            </template>
          </el-table-column>
          <el-table-column label="审核原因" min-width="180">
            <template #default="{ row }">
              <el-input v-model="reviewReasons[row.id]" size="small" placeholder="通过可选；拒绝必填" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="success" :icon="Check" :loading="reviewingId === row.id" @click="approve(row.id)">
                通过
              </el-button>
              <el-button link type="danger" :icon="Close" :loading="reviewingId === row.id" @click="reject(row.id)">
                拒绝
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="app-panel-card review-panel">
        <div class="section-header">
          <div>
            <h2 class="section-title">版本历史</h2>
            <p class="section-subtitle">通过审核或管理员正式修改都会生成历史记录。</p>
          </div>
        </div>
        <el-select v-model="historyRuleId" clearable filterable placeholder="按规则筛选" class="history-filter" @change="loadHistory">
          <el-option
            v-for="rule in effectiveRules"
            :key="rule.id"
            :label="`${rule.source_term} / ${scopeLabel(rule)}`"
            :value="rule.id"
          />
        </el-select>
        <el-table :data="history" :loading="loading" empty-text="暂无历史" size="small">
          <el-table-column prop="rule_id" label="规则 ID" min-width="150" show-overflow-tooltip />
          <el-table-column prop="version" label="版本" width="76" />
          <el-table-column prop="action" label="动作" width="90" />
          <el-table-column label="规则域" width="140">
            <template #default="{ row }">
              {{ row.scope_type === "global" ? "全局" : `部门 ${row.scope_id || "-"}` }}
            </template>
          </el-table-column>
          <el-table-column prop="created_by" label="操作人" min-width="120" />
          <el-table-column prop="created_at" label="时间" min-width="170" />
        </el-table>
      </section>
    </section>

    <el-drawer v-model="batchDrawer.visible" title="批次详情" size="680px">
      <el-skeleton v-if="batchDrawer.loading" :rows="6" animated />
      <div v-else-if="batchDrawer.batch" class="batch-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="批次">{{ batchDrawer.batch.id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ batchDrawer.batch.status }}</el-descriptions-item>
          <el-descriptions-item label="提交部门">{{ batchDrawer.batch.submitter_department_id }}</el-descriptions-item>
          <el-descriptions-item label="原因">{{ batchDrawer.batch.reason || "-" }}</el-descriptions-item>
        </el-descriptions>
        <el-table :data="batchDrawer.batch.items" size="small">
          <el-table-column prop="action" label="动作" width="86" />
          <el-table-column prop="status" label="状态" width="106" />
          <el-table-column label="术语" min-width="150">
            <template #default="{ row }">{{ snapshotTerm(row) }}</template>
          </el-table-column>
          <el-table-column prop="conflict_reason" label="冲突" min-width="180" show-overflow-tooltip />
          <el-table-column prop="rejection_reason" label="拒绝原因" min-width="180" show-overflow-tooltip />
        </el-table>
      </div>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { Check, Close, Delete, Plus, Refresh } from "@element-plus/icons-vue";

import { termRuleReviewsApi } from "@/api/termRuleReviews";
import { termRulesApi } from "@/api/termRules";
import type {
  TermRuleCategoryListItemResponse,
  TermRuleResponse,
  TermRuleReviewAction,
  TermRuleReviewBatchResponse,
  TermRuleReviewItemResponse,
  TermRuleReviewItemWriteRequest,
  TermRuleSegmentWriteRequest,
  TermRuleVersionResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import TermSegmentEditor from "@/components/TermSegmentEditor.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const auth = useAuthStore();
const isAdmin = computed(() => auth.user?.role === "admin");
const loading = ref(false);
const submitting = ref(false);
const reviewingId = ref("");
const error = ref<ApiClientError | null>(null);
const categories = ref<TermRuleCategoryListItemResponse[]>([]);
const effectiveRules = ref<TermRuleResponse[]>([]);
const batches = ref<TermRuleReviewBatchResponse[]>([]);
const pendingItems = ref<TermRuleReviewItemResponse[]>([]);
const history = ref<TermRuleVersionResponse[]>([]);
const queuedItems = ref<TermRuleReviewItemWriteRequest[]>([]);
const batchTotal = ref(0);
const historyRuleId = ref("");
const formRef = ref<FormInstance>();
const reviewReasons = reactive<Record<string, string>>({});
const batchPage = reactive({ page: 1, pageSize: 20 });
const batchDrawer = reactive<{ visible: boolean; loading: boolean; batch: TermRuleReviewBatchResponse | null }>({
  visible: false,
  loading: false,
  batch: null,
});

const form = reactive({
  action: "create" as TermRuleReviewAction,
  target_rule_id: "",
  base_version: null as number | null,
  source_term: "",
  category_id: "",
  segments: [
    { segment_text: "V", render_type: "plain" },
    { segment_text: "IN", render_type: "subscript" },
  ] as TermRuleSegmentWriteRequest[],
  reason: "",
  scope_type: "global" as "global" | "department",
  scope_id: auth.user?.department_id || "default_department",
});

const actionOptions = computed(() => [
  { label: "新增", value: "create" },
  { label: "编辑", value: "update" },
  ...(isAdmin.value ? [{ label: "删除", value: "delete" }] : []),
]);
const scopeOptions = [
  { label: "全局", value: "global" },
  { label: "部门", value: "department" },
];

const rules: FormRules = {
  target_rule_id: [
    {
      validator: (_rule, value, callback) => {
        if (form.action !== "create" && !String(value || "").trim()) {
          callback(new Error("请选择目标规则。"));
          return;
        }
        callback();
      },
      trigger: "change",
    },
  ],
  source_term: [
    {
      validator: (_rule, value, callback) => {
        if (form.action !== "delete" && !String(value || "").trim()) {
          callback(new Error("请填写原文术语。"));
          return;
        }
        callback();
      },
      trigger: "blur",
    },
  ],
  category_id: [
    {
      validator: (_rule, value, callback) => {
        if (form.action !== "delete" && !String(value || "").trim()) {
          callback(new Error("请选择分类。"));
          return;
        }
        callback();
      },
      trigger: "change",
    },
  ],
  reason: [{ required: true, message: "请填写原因说明", trigger: "blur" }],
  scope_id: [
    {
      validator: (_rule, value, callback) => {
        if (isAdmin.value && form.scope_type === "department" && !String(value || "").trim()) {
          callback(new Error("部门规则必须填写部门 ID。"));
          return;
        }
        callback();
      },
      trigger: "blur",
    },
  ],
};

function scopeLabel(rule: TermRuleResponse): string {
  return rule.scope_type === "global" ? "全局" : `部门 ${rule.scope_id || "-"}`;
}

function snapshotTerm(item: TermRuleReviewItemResponse): string {
  const snapshot = item.submitted_snapshot as { source_term?: unknown };
  return String(snapshot.source_term || item.normalized_term || "-");
}

function queuedScopeLabel(item: TermRuleReviewItemWriteRequest): string {
  if (!isAdmin.value || !item.scope_type) {
    return "本部门";
  }
  return item.scope_type === "global" ? "全局" : `部门 ${item.scope_id || "-"}`;
}

function batchTagType(status: string): "success" | "warning" | "danger" | "info" {
  if (status === "approved") {
    return "success";
  }
  if (status === "pending") {
    return "warning";
  }
  if (status === "conflict" || status === "partial_approved") {
    return "danger";
  }
  return "info";
}

async function loadReferenceData(): Promise<void> {
  const [categoryResponse, ruleResponse] = await Promise.all([
    termRulesApi.listCategories(),
    termRulesApi.listRules({ page: 1, page_size: 100 }),
  ]);
  categories.value = categoryResponse.items;
  effectiveRules.value = ruleResponse.items;
}

async function loadBatches(): Promise<void> {
  const response = await termRuleReviewsApi.listBatches({
    page: batchPage.page,
    page_size: batchPage.pageSize,
    mine: !isAdmin.value,
  });
  batches.value = response.items;
  batchTotal.value = response.total;
}

async function loadPendingItems(): Promise<void> {
  if (!isAdmin.value) {
    pendingItems.value = [];
    return;
  }
  pendingItems.value = await termRuleReviewsApi.listItems({ status: "pending" });
}

async function loadHistory(): Promise<void> {
  if (!isAdmin.value) {
    history.value = [];
    return;
  }
  history.value = await termRuleReviewsApi.listHistory(historyRuleId.value || undefined);
}

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    await Promise.all([loadReferenceData(), loadBatches(), loadPendingItems(), loadHistory()]);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

function handleActionChange(): void {
  form.target_rule_id = "";
  form.base_version = null;
  if (form.action === "create") {
    form.source_term = "";
    form.category_id = "";
  }
}

function applyTargetRule(): void {
  const rule = effectiveRules.value.find((item) => item.id === form.target_rule_id);
  if (!rule) {
    return;
  }
  form.base_version = rule.current_version;
  form.source_term = rule.source_term;
  form.category_id = rule.category_id;
  form.segments = rule.segments.map((segment) => ({
    segment_text: segment.segment_text,
    render_type: segment.render_type,
  }));
  form.scope_type = rule.scope_type;
  form.scope_id = rule.scope_id || auth.user?.department_id || "default_department";
}

function buildDraftItem(): TermRuleReviewItemWriteRequest {
  return {
    action: form.action,
    target_rule_id: form.action === "create" ? null : form.target_rule_id,
    base_version: form.action === "create" ? null : form.base_version,
    source_term: form.action === "delete" ? null : form.source_term,
    category_id: form.action === "delete" ? null : form.category_id,
    segments: form.action === "delete" ? null : form.segments,
    scope_type: isAdmin.value ? form.scope_type : null,
    scope_id: isAdmin.value && form.scope_type === "department" ? form.scope_id : null,
  };
}

async function addItemToBatch(showMessage = true): Promise<void> {
  await formRef.value?.validate();
  queuedItems.value = [...queuedItems.value, buildDraftItem()];
  if (showMessage) {
    ElMessage.success("已加入当前批次。");
  }
}

function removeQueuedItem(index: number): void {
  queuedItems.value = queuedItems.value.filter((_item, itemIndex) => itemIndex !== index);
}

async function submitBatch(): Promise<void> {
  if (queuedItems.value.length === 0) {
    await addItemToBatch(false);
  }
  if (!String(form.reason || "").trim()) {
    ElMessage.warning("请填写原因说明。");
    return;
  }
  submitting.value = true;
  error.value = null;
  try {
    await termRuleReviewsApi.createBatch({
      reason: form.reason,
      items: queuedItems.value,
    });
    ElMessage.success("已提交审核。");
    queuedItems.value = [];
    form.reason = "";
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    submitting.value = false;
  }
}

async function approve(itemId: string): Promise<void> {
  reviewingId.value = itemId;
  error.value = null;
  try {
    const item = await termRuleReviewsApi.approveItem(itemId, reviewReasons[itemId] || null);
    if (item.status === "conflict") {
      ElMessage.warning(item.conflict_reason || "审核项存在冲突。");
    } else {
      ElMessage.success("审核项已通过并生效。");
    }
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewingId.value = "";
  }
}

async function reject(itemId: string): Promise<void> {
  const reason = String(reviewReasons[itemId] || "").trim();
  if (!reason) {
    ElMessage.warning("拒绝必须填写原因。");
    return;
  }
  reviewingId.value = itemId;
  error.value = null;
  try {
    await termRuleReviewsApi.rejectItem(itemId, reason);
    ElMessage.success("审核项已拒绝。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    reviewingId.value = "";
  }
}

async function openBatch(batchId: string): Promise<void> {
  batchDrawer.visible = true;
  batchDrawer.loading = true;
  batchDrawer.batch = null;
  error.value = null;
  try {
    batchDrawer.batch = await termRuleReviewsApi.getBatch(batchId);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    batchDrawer.loading = false;
  }
}

onMounted(() => {
  void loadAll();
});
</script>

<style scoped lang="scss">
.term-rule-review-flow-page {
  display: grid;
  gap: var(--app-space-4);
}

.review-layout,
.admin-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  gap: var(--app-space-4);
}

.review-panel {
  display: grid;
  gap: var(--app-space-3);
  padding: var(--app-space-4);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
}

.form-actions,
.table-pagination {
  display: flex;
  justify-content: flex-end;
}

.history-filter {
  width: min(360px, 100%);
}

.batch-detail {
  display: grid;
  gap: var(--app-space-4);
}

@media (max-width: 980px) {
  .review-layout,
  .admin-grid {
    grid-template-columns: 1fr;
  }
}
</style>
