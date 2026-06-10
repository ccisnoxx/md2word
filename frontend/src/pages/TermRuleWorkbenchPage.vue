<!-- frontend/src/pages/TermRuleWorkbenchPage.vue: Admin read-only term rule inspection and simulation page. -->
<template>
  <main class="term-rule-workbench-page" aria-labelledby="term-rule-workbench-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Term Rule Workbench</p>
        <h1 id="term-rule-workbench-title">术语规则检查</h1>
        <p>只读查看当前 live runtime store，并用模拟接口检查文本渲染结果。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </section>

    <TerminologyWorkbenchNav active="live-rules" />

    <ApiErrorAlert :error="error" />

    <section class="summary-grid" aria-label="术语规则统计">
      <el-card class="card-flat summary-card" shadow="never">
        <span>分类数</span>
        <strong>{{ categories.length }}</strong>
      </el-card>
      <el-card class="card-flat summary-card" shadow="never">
        <span>规则总数</span>
        <strong>{{ totalRuleCount }}</strong>
      </el-card>
      <el-card class="card-flat summary-card" shadow="never">
        <span>启用规则</span>
        <strong>{{ enabledRuleCount }}</strong>
      </el-card>
    </section>

    <section class="content-grid">
      <el-card class="card-flat categories-card" shadow="never">
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

      <el-card class="card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">规则列表</h2>
            <p class="section-subtitle">仅支持查看、筛选和模拟，不提供编辑入口。</p>
          </div>
          <span class="muted">共 {{ ruleTotal }} 条</span>
        </div>

        <div class="toolbar filters" role="search">
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
            @keyup.enter="loadRules"
          />
          <el-button type="primary" :icon="Search" :loading="loading" @click="loadRules">搜索</el-button>
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
      </el-card>
    </section>

    <el-card class="card-flat" shadow="never">
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
          <pre>{{ simulationResult.original }}</pre>
        </section>
        <section>
          <h3>Markdown preview</h3>
          <pre>{{ simulationResult.markdown_preview }}</pre>
        </section>
        <section>
          <h3>HTML preview</h3>
          <pre>{{ simulationResult.html_preview }}</pre>
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
          <pre>{{ detailDrawer.rule.custom_markdown || "-" }}</pre>
        </section>
        <section class="detail-section">
          <h3>Custom HTML</h3>
          <pre>{{ detailDrawer.rule.custom_html || "-" }}</pre>
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
import { Refresh, Search } from "@element-plus/icons-vue";

import { termRulesApi } from "@/api/termRules";
import type {
  RuleSimulationResponse,
  TermRuleCategoryListItemResponse,
  TermRuleResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import TermPreview from "@/components/TermPreview.vue";
import TerminologyWorkbenchNav from "@/components/TerminologyWorkbenchNav.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

type EnabledFilter = "all" | "enabled" | "disabled";

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
      page: 1,
      page_size: 200,
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
  void loadRules();
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
  gap: 16px;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0 2px;
}

.page-kicker {
  margin: 0 0 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
  line-height: 1.2;
}

.page-heading p:last-child {
  margin: 8px 0 0;
  color: #667085;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  display: grid;
  gap: 6px;
}

.summary-card span {
  color: #667085;
  font-size: 13px;
}

.summary-card strong {
  color: #111827;
  font-size: 28px;
  line-height: 1;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 16px;
}

.categories-card {
  min-width: 0;
}

.filters {
  margin-bottom: 12px;
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

.simulation-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.simulation-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.simulation-grid h3,
.detail-section h3 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 650;
}

pre {
  overflow: auto;
  min-height: 44px;
  margin: 0;
  padding: 10px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #f8fafc;
  color: #111827;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.rule-detail {
  display: grid;
  gap: 16px;
}

.detail-section {
  display: grid;
  gap: 8px;
}

.detail-section p {
  margin: 0;
  color: #344054;
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
