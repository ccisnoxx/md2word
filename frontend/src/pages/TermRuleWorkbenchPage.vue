<!-- frontend/src/pages/TermRuleWorkbenchPage.vue: Read-only term rule inspection and proposal entry page. -->
<template>
  <main class="term-rule-workbench-page app-page" aria-labelledby="term-rule-workbench-title">
    <section class="page-heading app-page-header app-page-shell app-page-shell--wide">
      <div>
        <p class="page-kicker">Term Rule Workbench</p>
        <h1 id="term-rule-workbench-title" class="page-title">术语规则检查</h1>
        <p class="page-description">只读查看当前 live runtime store，并用模拟接口检查文本渲染结果。</p>
      </div>
      <div class="page-actions app-action-row">
        <el-tooltip
          :disabled="isAdmin"
          content="你暂无新建正式术语规则权限，可提交规则建议，由术语管理员审核后生效。"
          placement="bottom"
        >
          <span>
            <el-button type="primary" :icon="Plus" :disabled="!isAdmin" @click="openFormalRuleDraft">新建规则</el-button>
          </span>
        </el-tooltip>
        <el-button :icon="EditPen" @click="submitRuleSuggestion">提交规则建议</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </section>

    <TerminologyWorkbenchNav class="app-page-shell app-page-shell--wide" active="live-rules" />

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <section class="summary-grid app-metric-grid app-page-shell app-page-shell--wide" aria-label="术语规则统计">
      <el-card class="app-panel-card summary-card app-metric-card" shadow="never">
        <span>分类数</span>
        <strong>{{ categories.length }}</strong>
      </el-card>
      <el-card class="app-panel-card summary-card app-metric-card" shadow="never">
        <span>规则总数</span>
        <strong>{{ totalRuleCount }}</strong>
      </el-card>
      <el-card class="app-panel-card summary-card app-metric-card" shadow="never">
        <span>启用规则</span>
        <strong>{{ enabledRuleCount }}</strong>
      </el-card>
    </section>

    <section class="content-grid app-page-shell app-page-shell--wide">
      <el-card class="app-panel-card app-table-card categories-card" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">分类概览</h2>
            <p class="section-subtitle">来自当前 live term rules store。</p>
          </div>
        </div>
        <el-table :data="categories" :loading="loading" empty-text="暂无分类" size="small">
          <el-table-column prop="name" label="分类" min-width="140" show-overflow-tooltip />
          <el-table-column label="状态" width="82">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">
                {{ row.enabled ? "启用" : "停用" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="rule_count" label="规则" width="76" />
          <el-table-column prop="enabled_rule_count" label="启用" width="76" />
        </el-table>
      </el-card>

      <el-card class="app-panel-card app-table-card" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">规则列表</h2>
            <p class="section-subtitle">正式规则由术语管理员维护；普通用户通过规则建议进入审核。</p>
          </div>
          <span class="muted">共 {{ ruleTotal }} 条</span>
        </div>

        <div class="toolbar filters app-filter-panel" role="search">
          <el-select v-model="filters.categoryId" clearable placeholder="全部分类" class="filter-select">
            <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
          </el-select>
          <el-select v-model="filters.enabled" placeholder="全部状态" class="filter-select">
            <el-option label="全部状态" value="all" />
            <el-option label="仅启用" value="enabled" />
            <el-option label="仅停用" value="disabled" />
          </el-select>
          <el-input
            v-model="filters.keyword"
            clearable
            class="keyword-input"
            placeholder="搜索 source term"
            @keyup.enter="searchRules"
          />
          <el-button type="primary" :icon="Search" :loading="loading" @click="searchRules">搜索</el-button>
          <el-button @click="resetFilters">清除</el-button>
        </div>

        <el-table :data="rules" :loading="loading" empty-text="暂无规则" class="rule-table">
          <el-table-column prop="source_term" label="Source term" min-width="150" show-overflow-tooltip />
          <el-table-column label="预览" min-width="150">
            <template #default="{ row }">
              <TermPreview :segments="row.segments" />
            </template>
          </el-table-column>
          <el-table-column prop="category_name" label="分类" min-width="130" show-overflow-tooltip />
          <el-table-column label="规则域" width="140">
            <template #default="{ row }">
              <el-tag effect="plain" :type="row.scope_type === 'global' ? 'info' : 'warning'">
                {{ scopeLabel(row) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="apply_scope" label="Scope" width="116" />
          <el-table-column prop="priority" label="Priority" width="94" />
          <el-table-column label="状态" width="88">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">
                {{ row.enabled ? "启用" : "停用" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="详情" width="86" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openRuleDetail(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-pagination">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            background
            layout="total, sizes, prev, pager, next"
            :page-sizes="[20, 50, 100]"
            :total="ruleTotal"
            @current-change="loadRules"
            @size-change="handlePageSizeChange"
          />
        </div>
      </el-card>
    </section>

    <el-card class="app-panel-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">规则模拟</h2>
          <p class="section-subtitle">结果按文本展示，HTML preview 不直接渲染。</p>
        </div>
      </div>
      <ApiErrorAlert :error="simulationError" />
      <el-input v-model="simulationText" type="textarea" :rows="4" placeholder="输入需要检查的文本，例如 VIN and VOUT" />
      <div class="simulation-actions">
        <el-button type="primary" :loading="simulating" :disabled="!simulationText.trim()" @click="simulateText">
          模拟
        </el-button>
      </div>
      <div v-if="simulationResult" class="simulation-grid">
        <section>
          <h3>Original</h3>
          <pre class="app-technical-block">{{ simulationResult.original }}</pre>
        </section>
        <section>
          <h3>Markdown preview</h3>
          <pre class="app-technical-block">{{ simulationResult.markdown_preview }}</pre>
        </section>
        <section>
          <h3>HTML preview</h3>
          <pre class="app-technical-block">{{ simulationResult.html_preview }}</pre>
        </section>
      </div>
    </el-card>

    <el-drawer v-model="detailDrawer.visible" title="规则详情" size="560px">
      <el-skeleton v-if="detailLoading" :rows="6" animated />
      <div v-else-if="detailDrawer.rule" class="rule-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="ID">{{ detailDrawer.rule.id }}</el-descriptions-item>
          <el-descriptions-item label="Source term">{{ detailDrawer.rule.source_term }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ detailDrawer.rule.category_name }}</el-descriptions-item>
          <el-descriptions-item label="规则域">{{ scopeLabel(detailDrawer.rule) }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ detailDrawer.rule.current_version }}</el-descriptions-item>
          <el-descriptions-item label="Scope">{{ detailDrawer.rule.apply_scope }}</el-descriptions-item>
          <el-descriptions-item label="Case sensitive">
            {{ detailDrawer.rule.case_sensitive ? "是" : "否" }}
          </el-descriptions-item>
          <el-descriptions-item label="Priority">{{ detailDrawer.rule.priority }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detailDrawer.rule.enabled ? "启用" : "停用" }}</el-descriptions-item>
        </el-descriptions>

        <section class="detail-section">
          <h3>Segments</h3>
          <TermPreview :segments="detailDrawer.rule.segments" />
          <el-table :data="detailDrawer.rule.segments" size="small" class="segments-table">
            <el-table-column prop="seq" label="Seq" width="70" />
            <el-table-column prop="segment_text" label="Text" min-width="180" />
            <el-table-column prop="render_type" label="Render" width="120" />
          </el-table>
        </section>

        <section class="detail-section">
          <h3>Custom markdown</h3>
          <pre class="app-technical-block">{{ detailDrawer.rule.custom_markdown || "-" }}</pre>
        </section>
        <section class="detail-section">
          <h3>Custom HTML</h3>
          <pre class="app-technical-block">{{ detailDrawer.rule.custom_html || "-" }}</pre>
        </section>
        <section class="detail-section">
          <h3>Notes</h3>
          <p>{{ detailDrawer.rule.notes || "-" }}</p>
        </section>
      </div>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { EditPen, Plus, Refresh, Search } from "@element-plus/icons-vue";

import { termRulesApi } from "@/api/termRules";
import type {
  RuleSimulationResponse,
  TermRuleCategoryListItemResponse,
  TermRuleResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import TermPreview from "@/components/TermPreview.vue";
import TerminologyWorkbenchNav from "@/components/TerminologyWorkbenchNav.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

type EnabledFilter = "all" | "enabled" | "disabled";

const router = useRouter();
const auth = useAuthStore();
const categories = ref<TermRuleCategoryListItemResponse[]>([]);
const rules = ref<TermRuleResponse[]>([]);
const ruleTotal = ref(0);
const loading = ref(false);
const detailLoading = ref(false);
const simulating = ref(false);
const error = ref<ApiClientError | null>(null);
const simulationError = ref<ApiClientError | null>(null);
const simulationText = ref("");
const simulationResult = ref<RuleSimulationResponse | null>(null);

const filters = reactive({
  categoryId: "",
  enabled: "all" as EnabledFilter,
  keyword: "",
});
const pagination = reactive({
  page: 1,
  pageSize: 20,
});

const detailDrawer = reactive<{
  visible: boolean;
  rule: TermRuleResponse | null;
}>({
  visible: false,
  rule: null,
});

const totalRuleCount = computed(() => categories.value.reduce((sum, category) => sum + category.rule_count, 0));
const enabledRuleCount = computed(() =>
  categories.value.reduce((sum, category) => sum + category.enabled_rule_count, 0),
);
const isAdmin = computed(() => auth.user?.role === "admin" || auth.roles.includes("admin"));

function enabledParam(): boolean | undefined {
  if (filters.enabled === "enabled") {
    return true;
  }
  if (filters.enabled === "disabled") {
    return false;
  }
  return undefined;
}

async function loadCategories(): Promise<void> {
  categories.value = (await termRulesApi.listCategories()).items;
}

async function loadRules(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const response = await termRulesApi.listRules({
      page: pagination.page,
      page_size: pagination.pageSize,
      category_id: filters.categoryId || undefined,
      enabled: enabledParam(),
      q: filters.keyword.trim() || undefined,
    });
    rules.value = response.items;
    ruleTotal.value = response.total;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    await loadCategories();
    await loadRules();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function openRuleDetail(row: TermRuleResponse): Promise<void> {
  detailDrawer.visible = true;
  detailDrawer.rule = row;
  detailLoading.value = true;
  error.value = null;
  try {
    detailDrawer.rule = await termRulesApi.getRule(row.id);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    detailLoading.value = false;
  }
}

function resetFilters(): void {
  filters.categoryId = "";
  filters.enabled = "all";
  filters.keyword = "";
  pagination.page = 1;
  void loadRules();
}

function handlePageSizeChange(): void {
  pagination.page = 1;
  void loadRules();
}

function searchRules(): void {
  pagination.page = 1;
  void loadRules();
}

function scopeLabel(rule: TermRuleResponse): string {
  return rule.scope_type === "global" ? "全局" : `部门 ${rule.scope_id || "-"}`;
}

function openFormalRuleDraft(): void {
  if (!isAdmin.value) {
    return;
  }
  void router.push({ name: "settings-term-rule-sets" });
}

function submitRuleSuggestion(): void {
  void router.push({
    name: "term-rule-reviews",
    query: {
      action: "create",
    },
  });
}

async function simulateText(): Promise<void> {
  const text = simulationText.value.trim();
  if (!text) {
    return;
  }
  simulating.value = true;
  simulationError.value = null;
  simulationResult.value = null;
  try {
    simulationResult.value = await termRulesApi.simulate({ text });
  } catch (caught) {
    simulationError.value = normalizeApiError(caught);
  } finally {
    simulating.value = false;
  }
}

onMounted(() => {
  void loadAll();
});
</script>

<style scoped lang="scss">
.term-rule-workbench-page {
  display: grid;
  gap: var(--app-space-4);
}

.summary-grid {
  gap: var(--app-space-3);
}

.summary-card {
  display: grid;
  gap: 6px;
  border-color: var(--app-color-primary-border);
}

.summary-card span {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.summary-card strong {
  color: var(--app-color-text);
  font-size: 28px;
  line-height: 1;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: var(--app-space-4);
}

.categories-card {
  min-width: 0;
  border-color: var(--app-color-primary-border);
}

.filters {
  margin-bottom: var(--app-space-3);
  border-color: var(--app-color-accent-cyan-border);
}

.filter-select {
  width: 180px;
}

.keyword-input {
  width: min(320px, 100%);
}

.rule-table {
  width: 100%;
}

.table-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.simulation-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.simulation-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: var(--app-space-4);
}

.simulation-grid h3,
.detail-section h3 {
  margin: 0 0 8px;
  color: var(--app-color-primary-rail);
  font-size: 14px;
  font-weight: 650;
}

.rule-detail {
  display: grid;
  gap: var(--app-space-4);
}

.detail-section {
  display: grid;
  gap: 8px;
}

.detail-section p {
  margin: 0;
  color: var(--app-color-text-muted);
  line-height: 1.6;
}

.segments-table {
  margin-top: 8px;
}

@media (max-width: 980px) {
  .content-grid,
  .simulation-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 820px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .filter-select,
  .keyword-input {
    width: 100%;
  }
}
</style>
