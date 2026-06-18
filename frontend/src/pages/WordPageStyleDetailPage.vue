<!-- frontend/src/pages/WordPageStyleDetailPage.vue: Visual editor for Word page style YAML groups. -->
<template>
  <main class="word-style-page" aria-labelledby="word-style-title">
    <section class="style-hero">
      <div>
        <p class="page-kicker">Word 页面样式配置</p>
        <h1 id="word-style-title">Word 页面样式配置</h1>
        <p>{{ template?.name || templateId }}：维护后续 Word 生成时应用的页面排版样式。</p>
      </div>
      <div class="style-actions">
        <el-select
          v-model="selectedTemplateId"
          class="template-switcher"
          filterable
          aria-label="选择模板"
          @change="changeTemplate"
        >
          <el-option
            v-for="item in templates"
            :key="item.id"
            :label="`${item.name}${item.is_default ? '（默认）' : ''}`"
            :value="item.id"
          />
        </el-select>
        <el-button :icon="Document" @click="$router.push(`/settings/templates/${templateId}`)">模板文档</el-button>
        <el-button :icon="Refresh" :loading="loading || layoutConfigLoading" @click="confirmReloadAll">刷新</el-button>
        <el-button :disabled="!isLayoutDirty || layoutConfigSaving" @click="resetLayoutConfigForm">撤销</el-button>
        <el-button type="primary" :loading="layoutConfigSaving" :disabled="!layoutConfig || !isLayoutDirty" @click="saveLayoutConfigVersion">
          保存为草稿版本
        </el-button>
      </div>
    </section>

    <ApiErrorAlert :error="error" />

    <section class="style-status-grid" aria-label="样式配置状态">
      <article>
        <span>模板</span>
        <strong>{{ template?.name || templateId }}</strong>
        <small>{{ template?.is_default ? "当前默认模板" : "非默认模板" }}</small>
      </article>
      <article>
        <span>配置分组</span>
        <strong>{{ layoutGroupEntries.length || "-" }}</strong>
        <small>按 datasheet_template.yaml 一级分类渲染</small>
      </article>
      <article>
        <span>未保存</span>
        <strong>{{ dirtyFieldCount }}</strong>
        <small>{{ isLayoutDirty ? "保存后生成 draft version" : "当前无未保存改动" }}</small>
      </article>
    </section>

    <el-alert
      title="公司 Logo、默认页眉内容和 DOCX 文件由 Word 模板文档维护；这里保留页眉/页脚文字样式、对齐和开关等排版设置。"
      type="info"
      show-icon
      :closable="false"
    />

    <el-alert
      v-if="!layoutConfig && !layoutConfigLoading"
      title="未加载到模板页面样式配置"
      type="warning"
      show-icon
      :closable="false"
    />

    <template v-if="layoutConfig">
      <section class="config-meta-strip" aria-label="当前配置元信息">
        <dl>
          <div v-for="[fieldName, value] in layoutMetaEntries" :key="fieldName">
            <dt>{{ layoutMetaLabel(fieldName) }}</dt>
            <dd>{{ String(value ?? "-") }}</dd>
          </div>
          <div><dt>来源</dt><dd class="mono">{{ layoutConfig.source_path || "-" }}</dd></div>
          <div><dt>SHA256</dt><dd class="mono">{{ layoutConfig.config_sha256 || "-" }}</dd></div>
        </dl>
      </section>

      <section class="style-workbench" aria-label="Word 页面样式编辑器">
        <aside class="category-rail" aria-label="样式大类">
          <button
            v-for="category in availableCategories"
            :key="category.id"
            type="button"
            :class="{ active: activeCategoryId === category.id }"
            @click="setActiveCategory(category.id)"
          >
            <span>{{ category.title }}</span>
            <small>{{ category.description }}</small>
            <el-tag v-if="categoryDirtyCount(category.id) > 0" size="small" type="warning" effect="plain">
              {{ categoryDirtyCount(category.id) }}
            </el-tag>
          </button>
        </aside>

        <section class="style-editor-panel">
          <header class="style-panel-header">
            <div>
              <h2>{{ activeCategory?.title || "样式分组" }}</h2>
              <p>{{ activeCategory?.description || "选择一个分组开始编辑。" }}</p>
            </div>
            <el-tag v-if="activeCategoryDirtyCount > 0" type="warning" effect="plain">
              {{ activeCategoryDirtyCount }} 项未保存
            </el-tag>
          </header>

          <div class="group-tabs" role="tablist" aria-label="样式分组">
            <button
              v-for="groupName in activeCategoryGroups"
              :key="groupName"
              type="button"
              role="tab"
              :aria-selected="activeLayoutGroup === groupName"
              :class="{ active: activeLayoutGroup === groupName }"
              @click="setActiveGroup(groupName)"
            >
              <span>{{ layoutGroupTitle(groupName) }}</span>
              <el-tag v-if="groupDirtyCount(groupName) > 0" size="small" type="warning" effect="plain">
                {{ groupDirtyCount(groupName) }}
              </el-tag>
              <el-tag v-if="groupHasErrors(groupName)" size="small" type="danger" effect="plain">校验</el-tag>
            </button>
          </div>

          <el-form label-position="top" class="layout-form">
            <section
              v-for="[groupName, groupSchema] in visibleLayoutGroupEntries"
              :key="groupName"
              class="layout-section"
            >
              <header class="layout-section-heading">
                <div>
                  <h3>{{ layoutGroupTitle(groupName) }}</h3>
                  <p>{{ layoutGroupDescription(groupName) }}</p>
                </div>
              </header>

              <div class="layout-fields">
                <el-form-item
                  v-for="[fieldName, fieldSchema] in displayedFieldEntries(groupName, groupSchema)"
                  :key="`${groupName}.${fieldName}`"
                  :label="fieldLabel(fieldName, fieldSchema)"
                  :error="fieldError(groupName, fieldName)"
                >
                  <el-switch
                    v-if="fieldSchema.type === 'boolean'"
                    v-model="layoutConfigForm[groupName][fieldName]"
                    :disabled="Boolean(fieldSchema.readonly)"
                    @change="validateField(groupName, fieldName)"
                  />
                  <el-input-number
                    v-else-if="fieldSchema.type === 'number'"
                    v-model="layoutConfigForm[groupName][fieldName]"
                    :min="numberMin(fieldName)"
                    :step="numberStep(fieldName, fieldSchema.unit)"
                    :disabled="Boolean(fieldSchema.readonly)"
                    controls-position="right"
                    @change="validateField(groupName, fieldName)"
                  />
                  <el-segmented
                    v-else-if="fieldSchema.type === 'alignment'"
                    v-model="layoutConfigForm[groupName][fieldName]"
                    :options="alignmentOptions"
                    :disabled="Boolean(fieldSchema.readonly)"
                    @change="validateField(groupName, fieldName)"
                  />
                  <div v-else-if="fieldSchema.type === 'color'" class="color-field">
                    <el-color-picker
                      v-model="layoutConfigForm[groupName][fieldName]"
                      :predefine="colorPredefines"
                      :disabled="Boolean(fieldSchema.readonly)"
                      @change="validateField(groupName, fieldName)"
                    />
                    <el-input
                      v-model="layoutConfigForm[groupName][fieldName]"
                      :disabled="Boolean(fieldSchema.readonly)"
                      placeholder="#000000"
                      @blur="validateField(groupName, fieldName)"
                    />
                  </div>
                  <el-input
                    v-else
                    v-model="layoutConfigForm[groupName][fieldName]"
                    :disabled="Boolean(fieldSchema.readonly)"
                    @blur="validateField(groupName, fieldName)"
                  />
                </el-form-item>
              </div>
            </section>
          </el-form>
        </section>

        <aside class="change-panel" aria-label="配置变更摘要">
          <div class="change-panel-heading">
            <h2>变更摘要</h2>
            <el-tag v-if="isLayoutDirty" type="warning" effect="plain">{{ dirtyFieldCount }}</el-tag>
          </div>
          <p v-if="!isLayoutDirty">当前没有未保存改动。</p>
          <ul v-else>
            <li v-for="item in visibleDirtySummaries" :key="item.path">
              <strong>{{ item.label }}</strong>
              <span>{{ item.before }} -> {{ item.after }}</span>
            </li>
          </ul>
          <p v-if="dirtySummaries.length > visibleDirtySummaries.length" class="muted">
            还有 {{ dirtySummaries.length - visibleDirtySummaries.length }} 项改动。
          </p>
          <div class="change-note">
            保存只创建 draft version；完成验证、发布并设为默认后，后续 Word 生成才会使用。
          </div>
        </aside>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Document, Refresh } from "@element-plus/icons-vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";

import { templatesApi } from "@/api/templates";
import type {
  TemplateDetailResponse,
  TemplateLayoutConfigFieldSchema,
  TemplateLayoutConfigResponse,
  TemplateListItemResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

type LayoutCategory = {
  id: string;
  title: string;
  description: string;
  groups: string[];
};

const props = defineProps<{
  templateId: string;
}>();

const router = useRouter();
const templates = ref<TemplateListItemResponse[]>([]);
const selectedTemplateId = ref(props.templateId);
const template = ref<TemplateDetailResponse | null>(null);
const layoutConfig = ref<TemplateLayoutConfigResponse | null>(null);
const layoutConfigForm = ref<Record<string, any>>({});
const sourceLayoutConfig = ref<Record<string, any>>({});
const activeCategoryId = ref("");
const activeLayoutGroup = ref("");
const layoutValidationErrors = ref<Record<string, string>>({});
const loading = ref(false);
const layoutConfigLoading = ref(false);
const layoutConfigSaving = ref(false);
const error = ref<ApiClientError | null>(null);

const layoutCategories: LayoutCategory[] = [
  { id: "page", title: "页面", description: "纸张边距、页眉页脚距离。", groups: ["page_setup"] },
  { id: "cover", title: "首页", description: "首页型号行和品类行。", groups: ["part_number", "category"] },
  { id: "headings", title: "标题", description: "一级、二级、三级标题层级。", groups: ["heading1", "heading2", "heading3"] },
  { id: "toc", title: "目录", description: "目录标题和各级目录项。", groups: ["toc_title", "toc_level1", "toc_level2", "toc_level3"] },
  { id: "body", title: "正文", description: "正文段落和表格注释。", groups: ["normal", "table_note", "caption", "long_table_caption"] },
  { id: "table", title: "表格", description: "表格正文、表头底色和边框。", groups: ["table_content", "table_style"] },
  { id: "header_footer", title: "页眉页脚", description: "页眉/页脚文字样式与开关。", groups: ["header", "footer"] },
];

const layoutMetaEntries = computed(() => Object.entries(layoutConfig.value?.meta ?? {}));
const layoutGroupEntries = computed(() => Object.entries(layoutConfig.value?.field_schema.groups ?? {}));
const availableCategories = computed(() => {
  const groups = layoutConfig.value?.field_schema.groups ?? {};
  return layoutCategories.filter((category) => category.groups.some((groupName) => groupName in groups));
});
const activeCategory = computed(() => availableCategories.value.find((category) => category.id === activeCategoryId.value) || null);
const activeCategoryGroups = computed(() => {
  const groups = layoutConfig.value?.field_schema.groups ?? {};
  return (activeCategory.value?.groups ?? []).filter((groupName) => groupName in groups);
});
const visibleLayoutGroupEntries = computed(() =>
  layoutGroupEntries.value.filter(([groupName]) => groupName === activeLayoutGroup.value),
);
const isLayoutDirty = computed(() => stableStringify(sourceLayoutConfig.value) !== stableStringify(layoutConfigForm.value));
const dirtySummaries = computed(() => buildDirtySummaries());
const visibleDirtySummaries = computed(() => dirtySummaries.value.slice(0, 10));
const dirtyFieldCount = computed(() => dirtySummaries.value.length);
const activeCategoryDirtyCount = computed(() => (activeCategory.value ? categoryDirtyCount(activeCategory.value.id) : 0));
const alignmentOptions = [
  { value: "left", label: "左对齐" },
  { value: "center", label: "居中" },
  { value: "right", label: "右对齐" },
  { value: "justify", label: "两端对齐" },
];
const colorPredefines = ["#000000", "#475569", "#2563EB", "#10B981", "#F97316", "#EEF3F8", "#C7CDD4"];
const colorValueRe = /^#[0-9a-fA-F]{6}$/;

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  selectedTemplateId.value = props.templateId;
  try {
    const [templateList, templateResponse] = await Promise.all([
      templatesApi.list(),
      templatesApi.get(props.templateId),
    ]);
    templates.value = templateList.items;
    template.value = templateResponse;
    await loadLayoutConfig();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function loadLayoutConfig(): Promise<void> {
  layoutConfigLoading.value = true;
  error.value = null;
  try {
    const response = await templatesApi.getLayoutConfig(props.templateId);
    layoutConfig.value = response;
    const form = cloneLayoutConfig(response.config);
    normalizeColorValues(form, response.field_schema.groups);
    layoutConfigForm.value = form;
    sourceLayoutConfig.value = cloneLayoutConfig(form);
    layoutValidationErrors.value = {};
    activateFirstAvailableGroup(response.field_schema.groups);
  } catch (caught) {
    layoutConfig.value = null;
    layoutConfigForm.value = {};
    sourceLayoutConfig.value = {};
    activeCategoryId.value = "";
    activeLayoutGroup.value = "";
    error.value = normalizeApiError(caught);
  } finally {
    layoutConfigLoading.value = false;
  }
}

function activateFirstAvailableGroup(groups: TemplateLayoutConfigResponse["field_schema"]["groups"]): void {
  const category = layoutCategories.find((item) => item.groups.some((groupName) => groupName in groups));
  activeCategoryId.value = category?.id || "";
  activeLayoutGroup.value = category?.groups.find((groupName) => groupName in groups) || Object.keys(groups)[0] || "";
}

async function confirmReloadAll(): Promise<void> {
  if (!(await confirmDiscardDirty("刷新会丢弃当前未保存改动。"))) {
    return;
  }
  await loadAll();
}

async function changeTemplate(nextTemplateId: string | number | boolean | Record<string, unknown>): Promise<void> {
  const nextId = String(nextTemplateId);
  if (nextId === props.templateId) {
    return;
  }
  if (!(await confirmDiscardDirty("切换模板会丢弃当前未保存改动。"))) {
    selectedTemplateId.value = props.templateId;
    return;
  }
  await router.push(`/settings/word-page-styles/${nextId}`);
}

async function confirmDiscardDirty(message: string): Promise<boolean> {
  if (!isLayoutDirty.value) {
    return true;
  }
  try {
    await ElMessageBox.confirm(message, "未保存改动", {
      confirmButtonText: "丢弃",
      cancelButtonText: "取消",
      type: "warning",
    });
    return true;
  } catch {
    return false;
  }
}

function cloneLayoutConfig(config: Record<string, unknown>): Record<string, any> {
  return JSON.parse(JSON.stringify(config));
}

async function saveLayoutConfigVersion(): Promise<void> {
  if (!layoutConfig.value) {
    return;
  }
  if (!validateLayoutConfigForm()) {
    ElMessage.error("页面样式配置存在无效字段，请先修正标红项。");
    return;
  }
  layoutConfigSaving.value = true;
  error.value = null;
  try {
    const version = await templatesApi.createLayoutConfigVersion(props.templateId, {
      config: layoutConfigForm.value,
    });
    ElMessage.success(`已生成页面样式 draft version ${version.version}。完成验证、发布并设为默认后才会影响后续 Word 生成。`);
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    layoutConfigSaving.value = false;
  }
}

function layoutMetaLabel(fieldName: string): string {
  return layoutConfig.value?.field_schema.meta?.[fieldName]?.label || fieldName;
}

function fieldLabel(fieldName: string, fieldSchema: TemplateLayoutConfigFieldSchema): string {
  return fieldSchema.unit ? `${fieldSchema.label} (${fieldSchema.unit})` : fieldSchema.label || fieldName;
}

function layoutGroupTitle(groupName: string): string {
  const titles: Record<string, string> = {
    page_setup: "页面设置",
    part_number: "首页型号行",
    category: "首页品类行",
    heading1: "一级标题",
    heading2: "二级标题",
    heading3: "三级标题",
    toc_title: "目录标题",
    toc_level1: "目录一级项",
    toc_level2: "目录二级项",
    toc_level3: "目录三级项",
    normal: "正文",
    table_content: "表格正文",
    table_style: "表格样式",
    table_note: "表格注释",
    caption: "图注 / 表题",
    long_table_caption: "续表标题",
    header: "页眉",
    footer: "页脚",
  };
  return titles[groupName] || groupName;
}

function layoutGroupDescription(groupName: string): string {
  const descriptions: Record<string, string> = {
    page_setup: "控制整份 Word 的页边距、页眉页脚距离。",
    part_number: "控制首页型号行的字体、字号、颜色和段落间距。",
    category: "控制首页品类行的字体、字号、颜色和段落间距。",
    heading1: "控制一级标题的层级样式和段前段后间距。",
    heading2: "控制二级标题的层级样式和段前段后间距。",
    heading3: "控制三级标题的层级样式和段前段后间距。",
    toc_title: "控制目录标题样式。",
    toc_level1: "控制目录一级项样式。",
    toc_level2: "控制目录二级项样式。",
    toc_level3: "控制目录三级项样式。",
    normal: "控制普通正文段落样式。",
    table_content: "控制表格正文单元格文字样式。",
    table_style: "控制可编辑表格的基础样式、表头底色和边框色。",
    table_note: "控制表格注释文字样式。",
    caption: "控制图注和表题样式。",
    long_table_caption: "控制续表标题样式。",
    header: "控制渲染器写入的页眉文字样式；公司 Logo 和默认页眉内容请在 Word 模板文档中维护。",
    footer: "控制渲染器写入的页脚文字样式和页码设置；默认页脚内容请在 Word 模板文档中维护。",
  };
  return descriptions[groupName] || "维护该 Word 输出区域的字体、段落和颜色样式。";
}

function displayedFieldEntries(
  groupName: string,
  groupSchema: Record<string, TemplateLayoutConfigFieldSchema>,
): Array<[string, TemplateLayoutConfigFieldSchema]> {
  return Object.entries(groupSchema).filter(([fieldName]) => !(groupName === "header" && fieldName === "logo_path"));
}

function numberStep(fieldName: string, unit?: string): number {
  if (fieldName === "line_spacing") {
    return 0.05;
  }
  return unit === "cm" ? 0.1 : 0.5;
}

function numberMin(fieldName: string): number {
  return fieldName.endsWith("_indent_pt") ? -100 : 0;
}

function fieldError(groupName: string, fieldName: string): string {
  return layoutValidationErrors.value[`${groupName}.${fieldName}`] || "";
}

function groupHasErrors(groupName: string): boolean {
  return Object.keys(layoutValidationErrors.value).some((path) => path.startsWith(`${groupName}.`));
}

function groupDirtyCount(groupName: string): number {
  return dirtySummaries.value.filter((item) => item.groupName === groupName).length;
}

function categoryDirtyCount(categoryId: string): number {
  const category = layoutCategories.find((item) => item.id === categoryId);
  if (!category) {
    return 0;
  }
  return dirtySummaries.value.filter((item) => category.groups.includes(item.groupName)).length;
}

function setActiveCategory(categoryId: string): void {
  const category = availableCategories.value.find((item) => item.id === categoryId);
  if (!category) {
    return;
  }
  activeCategoryId.value = category.id;
  activeLayoutGroup.value = category.groups.find((groupName) => layoutConfig.value?.field_schema.groups[groupName]) || "";
}

function setActiveGroup(groupName: string): void {
  activeLayoutGroup.value = groupName;
}

function resetLayoutConfigForm(): void {
  layoutConfigForm.value = cloneLayoutConfig(sourceLayoutConfig.value);
  layoutValidationErrors.value = {};
}

function validateField(groupName: string, fieldName: string): void {
  const groups = layoutConfig.value?.field_schema.groups ?? {};
  const fieldSchema = groups[groupName]?.[fieldName];
  if (!fieldSchema) {
    return;
  }
  const path = `${groupName}.${fieldName}`;
  const errorMessage = validateFieldValue(path, layoutConfigForm.value[groupName]?.[fieldName], fieldSchema);
  const nextErrors = { ...layoutValidationErrors.value };
  if (errorMessage) {
    nextErrors[path] = errorMessage;
  } else {
    delete nextErrors[path];
  }
  layoutValidationErrors.value = nextErrors;
}

function validateLayoutConfigForm(): boolean {
  const errors: Record<string, string> = {};
  const groups = layoutConfig.value?.field_schema.groups ?? {};
  for (const [groupName, groupSchema] of Object.entries(groups)) {
    const groupValue = layoutConfigForm.value[groupName];
    if (!groupValue || typeof groupValue !== "object") {
      errors[groupName] = "分组缺失。";
      continue;
    }
    for (const [fieldName, fieldSchema] of Object.entries(groupSchema)) {
      const path = `${groupName}.${fieldName}`;
      const errorMessage = validateFieldValue(path, groupValue[fieldName], fieldSchema);
      if (errorMessage) {
        errors[path] = errorMessage;
      }
    }
  }
  layoutValidationErrors.value = errors;
  if (Object.keys(errors).length > 0) {
    const firstErrorGroup = Object.keys(errors)[0].split(".")[0];
    const firstCategory = layoutCategories.find((category) => category.groups.includes(firstErrorGroup));
    activeCategoryId.value = firstCategory?.id || activeCategoryId.value;
    activeLayoutGroup.value = firstErrorGroup;
  }
  return Object.keys(errors).length === 0;
}

function validateFieldValue(
  path: string,
  value: unknown,
  fieldSchema: TemplateLayoutConfigFieldSchema,
): string {
  if (fieldSchema.type === "number" && (typeof value !== "number" || Number.isNaN(value))) {
    return "请输入数字。";
  }
  if (fieldSchema.type === "boolean" && typeof value !== "boolean") {
    return "请选择开关状态。";
  }
  if (fieldSchema.type === "alignment" && !alignmentOptions.some((option) => option.value === value)) {
    return "请选择有效对齐方式。";
  }
  if (fieldSchema.type === "color" && (typeof value !== "string" || !colorValueRe.test(value))) {
    return "请输入 6 位 RGB 颜色。";
  }
  if (fieldSchema.type === "text" && typeof value !== "string") {
    return "请输入文本。";
  }
  if (path === "header.logo_path") {
    return "";
  }
  return "";
}

function normalizeColorValues(config: Record<string, any>, groups: TemplateLayoutConfigResponse["field_schema"]["groups"]): void {
  for (const [groupName, groupSchema] of Object.entries(groups)) {
    const groupValue = config[groupName];
    if (!groupValue || typeof groupValue !== "object") {
      continue;
    }
    for (const [fieldName, fieldSchema] of Object.entries(groupSchema)) {
      if (fieldSchema.type !== "color") {
        continue;
      }
      const value = groupValue[fieldName];
      if (typeof value === "string" && /^[0-9a-fA-F]{6}$/.test(value)) {
        groupValue[fieldName] = `#${value}`;
      }
    }
  }
}

function buildDirtySummaries(): Array<{ groupName: string; path: string; label: string; before: string; after: string }> {
  const groups = layoutConfig.value?.field_schema.groups ?? {};
  const summaries: Array<{ groupName: string; path: string; label: string; before: string; after: string }> = [];
  for (const [groupName, groupSchema] of Object.entries(groups)) {
    for (const [fieldName, fieldSchema] of Object.entries(groupSchema)) {
      const before = sourceLayoutConfig.value[groupName]?.[fieldName];
      const after = layoutConfigForm.value[groupName]?.[fieldName];
      if (stableStringify(before) === stableStringify(after)) {
        continue;
      }
      summaries.push({
        groupName,
        path: `${groupName}.${fieldName}`,
        label: `${layoutGroupTitle(groupName)} / ${fieldSchema.label || fieldName}`,
        before: displayLayoutValue(before),
        after: displayLayoutValue(after),
      });
    }
  }
  return summaries;
}

function displayLayoutValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function stableStringify(value: unknown): string {
  return JSON.stringify(value);
}

function handleBeforeUnload(event: BeforeUnloadEvent): void {
  if (!isLayoutDirty.value) {
    return;
  }
  event.preventDefault();
  event.returnValue = "";
}

onBeforeRouteLeave(() => {
  if (!isLayoutDirty.value) {
    return true;
  }
  return window.confirm("当前 Word 页面样式配置有未保存改动，确定离开吗？");
});

watch(
  () => props.templateId,
  () => {
    void loadAll();
  },
);

onMounted(() => {
  window.addEventListener("beforeunload", handleBeforeUnload);
  void loadAll();
});

onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", handleBeforeUnload);
});
</script>

<style scoped lang="scss">
.word-style-page {
  display: grid;
  gap: 16px;
}

.style-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.style-hero h1 {
  margin: 4px 0;
  color: #0f172a;
  font-size: 26px;
  line-height: 1.2;
}

.style-hero p:last-child {
  max-width: 760px;
  margin: 0;
  color: #475569;
}

.style-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.template-switcher {
  width: 240px;
}

.style-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.style-status-grid article {
  display: grid;
  gap: 4px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.style-status-grid span,
.style-status-grid small,
.config-meta-strip dt,
.change-panel p,
.change-panel li span,
.change-note {
  color: #475569;
}

.style-status-grid strong {
  color: #0f172a;
  font-size: 20px;
}

.config-meta-strip {
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.config-meta-strip dl {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px 16px;
  margin: 0;
}

.config-meta-strip div {
  min-width: 0;
}

.config-meta-strip dt {
  font-size: 12px;
}

.config-meta-strip dd {
  margin: 3px 0 0;
  overflow-wrap: anywhere;
}

.style-workbench {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr) 300px;
  gap: 16px;
  align-items: start;
}

.category-rail,
.change-panel {
  position: sticky;
  top: 86px;
}

.category-rail {
  display: grid;
  gap: 8px;
}

.category-rail button {
  position: relative;
  display: grid;
  gap: 4px;
  min-height: 72px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
  color: #1e293b;
  text-align: left;
  cursor: pointer;
  transition: border-color 180ms ease, background-color 180ms ease, box-shadow 180ms ease;
}

.category-rail button:hover,
.category-rail button:focus-visible {
  border-color: #93c5fd;
  box-shadow: 0 8px 22px rgb(15 23 42 / 8%);
  outline: none;
}

.category-rail button.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.category-rail button span {
  font-weight: 650;
}

.category-rail button small {
  color: #475569;
  line-height: 1.4;
}

.category-rail button :deep(.el-tag) {
  position: absolute;
  top: 10px;
  right: 10px;
}

.style-editor-panel,
.change-panel {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.style-editor-panel {
  min-width: 0;
  padding: 16px;
}

.style-panel-header,
.layout-section-heading,
.change-panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.style-panel-header {
  margin-bottom: 14px;
}

.style-panel-header h2,
.change-panel h2,
.layout-section h3 {
  margin: 0;
  color: #0f172a;
  font-size: 16px;
  font-weight: 650;
}

.style-panel-header p,
.layout-section-heading p {
  margin: 4px 0 0;
  color: #475569;
  font-size: 13px;
}

.group-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.group-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  cursor: pointer;
  transition: border-color 180ms ease, background-color 180ms ease;
}

.group-tabs button:hover,
.group-tabs button:focus-visible {
  border-color: #2563eb;
  outline: none;
}

.group-tabs button.active {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
}

.layout-form {
  display: grid;
  gap: 12px;
}

.layout-section-heading {
  margin-bottom: 14px;
}

.layout-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 10px 14px;
}

.layout-fields :deep(.el-form-item) {
  margin-bottom: 8px;
}

.layout-fields :deep(.el-input-number),
.layout-fields :deep(.el-select),
.layout-fields :deep(.el-segmented) {
  width: 100%;
}

.color-field {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}

.change-panel {
  display: grid;
  gap: 12px;
  padding: 14px;
}

.change-panel p {
  margin: 0;
}

.change-panel ul {
  display: grid;
  gap: 10px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.change-panel li {
  display: grid;
  gap: 3px;
  padding-bottom: 10px;
  border-bottom: 1px solid #eef2f7;
}

.change-panel li strong {
  color: #0f172a;
  font-size: 13px;
}

.change-panel li span {
  overflow-wrap: anywhere;
  font-size: 12px;
}

.change-note {
  padding: 10px;
  border-radius: 8px;
  background: #f8fafc;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 1180px) {
  .style-workbench {
    grid-template-columns: 210px minmax(0, 1fr);
  }

  .change-panel {
    position: static;
    grid-column: 1 / -1;
  }
}

@media (max-width: 820px) {
  .style-hero,
  .style-panel-header,
  .layout-section-heading {
    flex-direction: column;
  }

  .style-actions,
  .template-switcher {
    width: 100%;
  }

  .style-status-grid,
  .style-workbench {
    grid-template-columns: 1fr;
  }

  .category-rail {
    position: static;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  }
}
</style>
