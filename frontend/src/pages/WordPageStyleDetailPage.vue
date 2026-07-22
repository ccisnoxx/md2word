<!-- frontend/src/pages/WordPageStyleDetailPage.vue: 按后端白名单 schema 渲染 Word 页面样式配置。 -->
<template>
  <main class="word-style-page app-page" aria-labelledby="word-style-title">
    <WorkbenchPageHeader
      title-id="word-style-title"
      kicker="Word 页面样式配置"
      title="Word 页面样式配置"
      :description="`${template?.name || props.templateId}：维护后续 Word 生成时应用的页面排版样式。`"
      wide
      section-class="style-hero app-page-header"
      actions-class="style-actions app-action-row"
    >
      <template #actions>
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
        <el-select
          v-model="selectedVersion"
          class="version-switcher"
          aria-label="选择模板版本"
          @change="changeVersion"
        >
          <el-option
            v-for="item in templateVersions"
            :key="item.template_version_id"
            :label="`v${item.version} · ${versionStatusLabel(item.status)}${item.is_default ? '（默认）' : ''}`"
            :value="item.version"
          />
        </el-select>
        <el-button :icon="Document" @click="$router.push(`/settings/templates/${props.templateId}`)">模板文档</el-button>
        <el-button v-if="layoutConfig?.status === 'draft'" @click="openValidationFlow">创建验证任务</el-button>
        <el-button :icon="Refresh" :loading="loading || layoutConfigLoading" @click="confirmReloadAll">刷新</el-button>
        <el-button :disabled="!isLayoutDirty || layoutConfigSaving" @click="resetLayoutConfigForm">撤销</el-button>
        <el-button type="primary" :loading="layoutConfigSaving" :disabled="!layoutConfig || !isLayoutDirty" @click="saveLayoutConfigVersion">
          保存为草稿版本
        </el-button>
      </template>
    </WorkbenchPageHeader>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <WorkbenchMetricStrip
      label="样式配置状态"
      :items="overviewItems"
      wide
      section-class="style-status-grid"
    />

    <el-alert
      class="app-page-shell app-page-shell--wide"
      title="公司 Logo、默认页眉内容和 DOCX 文件由 Word 模板文档维护；这里保留页眉/页脚文字样式、对齐和开关等排版设置。"
      type="info"
      show-icon
      :closable="false"
    />

    <el-alert
      class="app-page-shell app-page-shell--wide"
      v-if="!layoutConfig && !layoutConfigLoading"
      title="未加载到模板页面样式配置"
      type="warning"
      show-icon
      :closable="false"
    />

    <template v-if="layoutConfig">
      <section class="config-meta-strip app-evidence-panel app-page-shell app-page-shell--wide" aria-label="当前配置元信息">
        <dl>
          <div v-for="[fieldName, value] in layoutMetaEntries" :key="fieldName">
            <dt>{{ layoutMetaLabel(fieldName) }}</dt>
            <dd>{{ String(value ?? "-") }}</dd>
          </div>
          <div><dt>来源</dt><dd class="mono">{{ layoutConfig.source_path || "-" }}</dd></div>
          <div><dt>SHA256</dt><dd class="mono">{{ layoutConfig.config_sha256 || "-" }}</dd></div>
        </dl>
      </section>

      <section class="style-workbench app-page-shell app-page-shell--wide" aria-label="Word 页面样式编辑器">
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

        <WorkbenchPanelCard
          :title="activeCategory?.title || '样式分组'"
          :subtitle="activeCategory?.description || '选择一个分组开始编辑。'"
          card-class="style-editor-panel"
          body-class="style-editor-panel-body"
        >
          <template #actions>
            <el-tag v-if="activeCategoryDirtyCount > 0" type="warning" effect="plain">
              {{ activeCategoryDirtyCount }} 项未保存
            </el-tag>
          </template>

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
                    :min="fieldSchema.min"
                    :max="fieldSchema.max"
                    :step="fieldSchema.step ?? 1"
                    :disabled="Boolean(fieldSchema.readonly)"
                    controls-position="right"
                    @change="validateField(groupName, fieldName)"
                  />
                  <el-segmented
                    v-else-if="fieldSchema.type === 'alignment'"
                    v-model="layoutConfigForm[groupName][fieldName]"
                    :options="alignmentOptionsFor(fieldSchema)"
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
                    v-else-if="fieldSchema.type === 'text'"
                    v-model="layoutConfigForm[groupName][fieldName]"
                    :disabled="Boolean(fieldSchema.readonly)"
                    @blur="validateField(groupName, fieldName)"
                  />
                  <el-alert v-else title="后端返回了当前页面不支持的字段类型，已阻止保存。" type="error" :closable="false" />
                </el-form-item>
              </div>
            </section>
          </el-form>
        </WorkbenchPanelCard>

        <aside aria-label="配置变更摘要">
          <WorkbenchPanelCard
            title="变更摘要"
            card-class="change-panel"
            body-class="change-panel-body"
          >
            <template #actions>
              <el-tag v-if="isLayoutDirty" type="warning" effect="plain">{{ dirtyFieldCount }}</el-tag>
            </template>
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
          </WorkbenchPanelCard>

          <WorkbenchPanelCard
            title="效果示意"
            subtitle="浏览器近似展示不代表 Word 最终分页和字体替换结果。"
            card-class="preview-panel"
          >
            <div class="preview-paper" :style="previewPageStyle">
              <div v-if="previewHeaderEnabled" class="preview-header">{{ previewHeaderText }}</div>
              <div v-if="activeLayoutGroup === 'table_style' || activeLayoutGroup === 'table_content'" class="preview-table">
                <div :style="previewTableHeaderStyle">参数</div><div :style="previewTableHeaderStyle">典型值</div>
                <div :style="previewTableCellStyle">输入电压</div><div :style="previewTableCellStyle">5 V</div>
              </div>
              <p v-else :style="previewTextStyle">{{ previewText }}</p>
              <div v-if="previewFooterEnabled" class="preview-footer">1</div>
            </div>
            <p class="preview-disclaimer">效果示意，最终以该 draft 的真实 Word 验证任务为准。</p>
          </WorkbenchPanelCard>
        </aside>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, type CSSProperties } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Document, Refresh } from "@element-plus/icons-vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";

import { templatesApi } from "@/api/templates";
import type {
  TemplateDetailResponse,
  TemplateLayoutConfigFieldSchema,
  TemplateLayoutConfigResponse,
  TemplateListItemResponse,
  TemplateVersionResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import WorkbenchMetricStrip, { type WorkbenchMetricItem } from "@/components/WorkbenchMetricStrip.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
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
const templateVersions = ref<TemplateVersionResponse[]>([]);
const selectedVersion = ref<number | null>(null);
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
let pageLoadSequence = 0;
let layoutLoadSequence = 0;

const layoutMetaEntries = computed(() => Object.entries(layoutConfig.value?.meta ?? {}));
const layoutGroupEntries = computed(() => Object.entries(layoutConfig.value?.field_schema.groups ?? {}));
const layoutCategories = computed<LayoutCategory[]>(() =>
  (layoutConfig.value?.field_schema.categories ?? []).map((category) => ({
    id: category.key,
    title: category.label,
    description: `管理${category.label}相关样式。`,
    groups: category.groups,
  })),
);
const availableCategories = computed(() => {
  const groups = layoutConfig.value?.field_schema.groups ?? {};
  return layoutCategories.value.filter((category) => category.groups.some((groupName) => groupName in groups));
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
const overviewItems = computed<WorkbenchMetricItem[]>(() => [
  {
    id: "template",
    label: "模板",
    value: template.value?.name || props.templateId,
    helper: template.value?.is_default ? "当前默认模板" : "非默认模板",
  },
  {
    id: "version",
    label: "当前版本",
    value: layoutConfig.value?.template_version_id || "-",
    helper: layoutConfig.value?.status === "draft" ? "草稿，尚未影响生产生成" : "已发布版本",
    tone: layoutConfig.value?.status === "draft" ? "warning" : "success",
  },
  {
    id: "group_count",
    label: "配置分组",
    value: layoutGroupEntries.value.length || "-",
    helper: "按版式配置一级分类渲染",
  },
  {
    id: "dirty_count",
    label: "未保存",
    value: dirtyFieldCount.value,
    helper: isLayoutDirty.value ? "保存后生成 draft version" : "当前无未保存改动",
    tone: isLayoutDirty.value ? "warning" : "success",
  },
]);
const alignmentOptions = [
  { value: "left", label: "左对齐" },
  { value: "center", label: "居中" },
  { value: "right", label: "右对齐" },
  { value: "justify", label: "两端对齐" },
];
const colorPredefines = ["#000000", "#475569", "#2563EB", "#10B981", "#F97316", "#EEF3F8", "#C7CDD4"];
const colorValueRe = /^#[0-9a-fA-F]{6}$/;
const previewPageStyle = computed(() => {
  const setup = layoutConfigForm.value.page_setup ?? {};
  const width = Number(setup.page_width_cm || 21);
  const height = Number(setup.page_height_cm || 29.7);
  return {
    aspectRatio: `${width} / ${height}`,
    padding: `${Math.min(Number(setup.top_margin || 0) / height * 100, 30)}% ${Math.min(Number(setup.right_margin || 0) / width * 100, 30)}% ${Math.min(Number(setup.bottom_margin || 0) / height * 100, 30)}% ${Math.min(Number(setup.left_margin || 0) / width * 100, 30)}%`,
  };
});
const previewTextStyle = computed<CSSProperties>(() => {
  const style = layoutConfigForm.value[activeLayoutGroup.value] ?? layoutConfigForm.value.normal ?? {};
  return {
    fontFamily: String(style.font_name || "serif"),
    fontSize: `${Math.max(Number(style.font_size || 10), 6) * 0.9}px`,
    fontWeight: style.bold ? 700 : 400,
    fontStyle: style.italic ? "italic" : "normal",
    color: String(style.color || "#000000"),
    textAlign: (style.alignment === "justify" ? "justify" : String(style.alignment || "left")) as CSSProperties["textAlign"],
    lineHeight: String(style.line_spacing || 1.2),
    marginTop: `${Number(style.space_before || 0) * 0.5}px`,
    marginBottom: `${Number(style.space_after || 0) * 0.5}px`,
    textIndent: `${Number(style.first_line_indent_pt || 0) * 0.4}px`,
  };
});
const previewText = computed(() => previewTextForGroup(activeLayoutGroup.value));
const previewHeaderEnabled = computed(() => Boolean(layoutConfigForm.value.header?.enabled));
const previewFooterEnabled = computed(() => Boolean(layoutConfigForm.value.footer?.enabled));
const previewHeaderText = computed(() => String(layoutConfigForm.value.header?.title_text || "数据手册"));
const previewTableHeaderStyle = computed(() => ({
  backgroundColor: String(layoutConfigForm.value.table_style?.header_fill || "#EEF3F8"),
  borderColor: String(layoutConfigForm.value.table_style?.border_color || "#C7CDD4"),
  fontWeight: 700,
}));
const previewTableCellStyle = computed(() => ({
  borderColor: String(layoutConfigForm.value.table_style?.border_color || "#C7CDD4"),
  fontFamily: String(layoutConfigForm.value.table_content?.font_name || "serif"),
  fontSize: `${Math.max(Number(layoutConfigForm.value.table_content?.font_size || 9), 6) * 0.9}px`,
  color: String(layoutConfigForm.value.table_content?.color || "#000000"),
}));

async function loadAll(): Promise<void> {
  const requestSequence = ++pageLoadSequence;
  const templateId = props.templateId;
  loading.value = true;
  error.value = null;
  selectedTemplateId.value = templateId;
  try {
    const [templateList, templateResponse, versionResponse] = await Promise.all([
      templatesApi.list(),
      templatesApi.get(templateId),
      templatesApi.listVersions(templateId),
    ]);
    if (requestSequence !== pageLoadSequence) {
      return;
    }
    templates.value = templateList.items;
    template.value = templateResponse;
    templateVersions.value = versionResponse.items;
    await loadLayoutConfig(undefined, templateId);
  } catch (caught) {
    if (requestSequence === pageLoadSequence) {
      error.value = normalizeApiError(caught);
    }
  } finally {
    if (requestSequence === pageLoadSequence) {
      loading.value = false;
    }
  }
}

async function loadLayoutConfig(version?: number, templateId = props.templateId): Promise<void> {
  const requestSequence = ++layoutLoadSequence;
  layoutConfigLoading.value = true;
  error.value = null;
  try {
    const response = await templatesApi.getLayoutConfig(templateId, version);
    if (requestSequence !== layoutLoadSequence || templateId !== props.templateId) {
      return;
    }
    layoutConfig.value = response;
    selectedVersion.value = response.version;
    const form = cloneLayoutConfig(response.config);
    normalizeColorValues(form, response.field_schema.groups);
    layoutConfigForm.value = form;
    sourceLayoutConfig.value = cloneLayoutConfig(form);
    layoutValidationErrors.value = {};
    activateFirstAvailableGroup(response.field_schema.groups);
  } catch (caught) {
    if (requestSequence !== layoutLoadSequence || templateId !== props.templateId) {
      return;
    }
    layoutConfig.value = null;
    layoutConfigForm.value = {};
    sourceLayoutConfig.value = {};
    activeCategoryId.value = "";
    activeLayoutGroup.value = "";
    error.value = normalizeApiError(caught);
  } finally {
    if (requestSequence === layoutLoadSequence) {
      layoutConfigLoading.value = false;
    }
  }
}

function activateFirstAvailableGroup(groups: TemplateLayoutConfigResponse["field_schema"]["groups"]): void {
  const category = layoutCategories.value.find((item) => item.groups.some((groupName) => groupName in groups));
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

async function changeVersion(nextVersion: string | number | boolean | Record<string, unknown>): Promise<void> {
  const version = Number(nextVersion);
  if (!Number.isInteger(version) || version < 1 || version === layoutConfig.value?.version) {
    return;
  }
  if (!(await confirmDiscardDirty("切换版本会丢弃当前未保存改动。"))) {
    selectedVersion.value = layoutConfig.value?.version ?? null;
    return;
  }
  await loadLayoutConfig(version);
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

function buildLayoutChanges(): Record<string, Record<string, unknown>> {
  const changes: Record<string, Record<string, unknown>> = {};
  const groups = layoutConfig.value?.field_schema.groups ?? {};
  for (const [groupName, groupSchema] of Object.entries(groups)) {
    for (const [fieldName, fieldSchema] of Object.entries(groupSchema)) {
      if (fieldSchema.readonly) {
        continue;
      }
      const before = sourceLayoutConfig.value[groupName]?.[fieldName];
      const after = layoutConfigForm.value[groupName]?.[fieldName];
      if (stableStringify(before) === stableStringify(after)) {
        continue;
      }
      changes[groupName] ??= {};
      changes[groupName][fieldName] = after;
    }
  }
  return changes;
}

function openValidationFlow(): void {
  if (!layoutConfig.value) {
    return;
  }
  void router.push({
    path: `/settings/templates/${props.templateId}`,
    query: { validate_version: String(layoutConfig.value.version) },
  });
}

function previewTextForGroup(groupName: string): string {
  const samples = layoutConfig.value?.preview_samples ?? {};
  const sampleKeys: Record<string, string> = {
    part_number: "part_number",
    category: "category",
    heading1: "heading1_text",
    heading2: "heading2_text",
    heading3: "heading3_text",
    normal: "normal_text",
    table_note: "table_note_text",
    caption: "caption_text",
    long_table_caption: "caption_text",
  };
  if (groupName === "page_setup") {
    return "A4 页面正文区域示意";
  }
  if (groupName.startsWith("toc_")) {
    return groupName === "toc_title" ? "目录" : "1.1 产品概述 ........................ 3";
  }
  if (groupName === "header") {
    return previewHeaderText.value;
  }
  if (groupName === "footer") {
    return "页码示意";
  }
  const value = samples[sampleKeys[groupName] || "normal_text"];
  return typeof value === "string" && value ? value : "模板样式效果示意文本";
}

function applyServerFieldErrors(raw: unknown): void {
  if (!isRecord(raw) || !isRecord(raw.detail) || !Array.isArray(raw.detail.field_errors)) {
    return;
  }
  const errors: Record<string, string> = {};
  for (const item of raw.detail.field_errors) {
    if (!isRecord(item) || typeof item.path !== "string" || typeof item.message !== "string") {
      continue;
    }
    errors[item.path] = item.message;
  }
  if (Object.keys(errors).length > 0) {
    layoutValidationErrors.value = errors;
  }
}

function isRecord(value: unknown): value is Record<string, any> {
  return typeof value === "object" && value !== null;
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
    const changes = buildLayoutChanges();
    const version = await templatesApi.createLayoutConfigVersion(props.templateId, {
      base_template_version_id: layoutConfig.value.template_version_id || `${props.templateId}@${layoutConfig.value.version}`,
      expected_config_sha256: layoutConfig.value.config_sha256 || "",
      expected_active_template_version_id: layoutConfig.value.active_template_version_id,
      changes,
    });
    templateVersions.value = [version, ...templateVersions.value.filter((item) => item.version !== version.version)];
    ElMessage.success(`已生成页面样式 draft version ${version.version}。完成验证、发布并设为默认后才会影响后续 Word 生成。`);
    await loadLayoutConfig(version.version);
  } catch (caught) {
    error.value = normalizeApiError(caught);
    applyServerFieldErrors(error.value.raw);
  } finally {
    layoutConfigSaving.value = false;
  }
}

function layoutMetaLabel(fieldName: string): string {
  return layoutConfig.value?.field_schema.meta?.[fieldName]?.label || fieldName;
}

function versionStatusLabel(status: string): string {
  return {
    draft: "草稿",
    published: "已发布",
    disabled: "已禁用",
    superseded: "已替代",
  }[status] || status;
}

function fieldLabel(fieldName: string, fieldSchema: TemplateLayoutConfigFieldSchema): string {
  return fieldSchema.unit ? `${fieldSchema.label} (${fieldSchema.unit})` : fieldSchema.label || fieldName;
}

function layoutGroupTitle(groupName: string): string {
  return layoutConfig.value?.field_schema.group_meta[groupName]?.label || groupName;
}

function layoutGroupDescription(groupName: string): string {
  return layoutConfig.value?.field_schema.group_meta[groupName]?.description || "维护该 Word 输出区域的样式。";
}

function displayedFieldEntries(
  groupName: string,
  groupSchema: Record<string, TemplateLayoutConfigFieldSchema>,
): Array<[string, TemplateLayoutConfigFieldSchema]> {
  return Object.entries(groupSchema).filter(([fieldName]) => !(groupName === "header" && fieldName === "logo_path"));
}

function alignmentOptionsFor(fieldSchema: TemplateLayoutConfigFieldSchema): Array<{ value: string; label: string }> {
  const allowed = fieldSchema.options ?? alignmentOptions.map((option) => option.value);
  return alignmentOptions.filter((option) => allowed.includes(option.value));
}

function fieldError(groupName: string, fieldName: string): string {
  return layoutValidationErrors.value[`${groupName}.${fieldName}`] || "";
}

function groupHasErrors(groupName: string): boolean {
  return Object.keys(layoutValidationErrors.value).some((path) => path === groupName || path.startsWith(`${groupName}.`));
}

function groupDirtyCount(groupName: string): number {
  return dirtySummaries.value.filter((item) => item.groupName === groupName).length;
}

function categoryDirtyCount(categoryId: string): number {
  const category = layoutCategories.value.find((item) => item.id === categoryId);
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
      if (fieldSchema.readonly) {
        continue;
      }
      const path = `${groupName}.${fieldName}`;
      const supportedType = ["number", "boolean", "alignment", "color", "text"].includes(fieldSchema.type);
      if (!supportedType) {
        errors[path] = `不支持字段类型 ${fieldSchema.type}。`;
        continue;
      }
      if (stableStringify(sourceLayoutConfig.value[groupName]?.[fieldName]) === stableStringify(groupValue[fieldName])) {
        continue;
      }
      const errorMessage = validateFieldValue(path, groupValue[fieldName], fieldSchema);
      if (errorMessage) {
        errors[path] = errorMessage;
      }
    }
  }
  layoutValidationErrors.value = errors;
  if (Object.keys(errors).length > 0) {
    const firstErrorGroup = Object.keys(errors)[0].split(".")[0];
    const firstCategory = layoutCategories.value.find((category) => category.groups.includes(firstErrorGroup));
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
  if (!["number", "boolean", "alignment", "color", "text"].includes(fieldSchema.type)) {
    return `不支持字段类型 ${fieldSchema.type}。`;
  }
  if (fieldSchema.type === "number" && (typeof value !== "number" || !Number.isFinite(value))) {
    return "请输入数字。";
  }
  if (fieldSchema.type === "number" && typeof value === "number" && fieldSchema.min !== undefined && value < fieldSchema.min) {
    return `不能小于 ${fieldSchema.min}。`;
  }
  if (fieldSchema.type === "number" && typeof value === "number" && fieldSchema.max !== undefined && value > fieldSchema.max) {
    return `不能大于 ${fieldSchema.max}。`;
  }
  if (fieldSchema.type === "boolean" && typeof value !== "boolean") {
    return "请选择开关状态。";
  }
  if (fieldSchema.type === "alignment" && !alignmentOptionsFor(fieldSchema).some((option) => option.value === value)) {
    return "请选择有效对齐方式。";
  }
  if (fieldSchema.type === "color" && value !== null && value !== "" && (typeof value !== "string" || !colorValueRe.test(value))) {
    return "请输入 6 位 RGB 颜色。";
  }
  if (fieldSchema.type === "text" && typeof value !== "string") {
    return "请输入文本。";
  }
  if (
    fieldSchema.type === "text"
    && typeof value === "string"
    && (path.endsWith("font_name") || path === "table_style.style_name")
    && !value.trim()
  ) {
    return "该字段不能为空。";
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
  pageLoadSequence += 1;
  layoutLoadSequence += 1;
  window.removeEventListener("beforeunload", handleBeforeUnload);
});
</script>

<style scoped lang="scss">
.word-style-page {
  display: grid;
  gap: var(--app-space-4);
}

.style-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.style-hero h1 {
  margin: 0;
}

.style-hero p:last-child {
  margin: var(--app-space-1) 0 0;
}

.style-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.template-switcher {
  width: 240px;
}

.version-switcher {
  width: 180px;
}

.style-status-grid span,
.style-status-grid small,
.config-meta-strip dt,
.change-panel p,
.change-panel li span,
.change-note {
  color: var(--app-color-text-muted);
}

.style-status-grid strong {
  color: var(--app-color-text);
}

.config-meta-strip {
  padding: var(--app-space-3) var(--app-space-4);
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
  gap: var(--app-space-4);
  align-items: start;
}

.category-rail,
.style-workbench > aside {
  position: sticky;
  top: 86px;
}

.style-workbench > aside {
  display: grid;
  gap: var(--app-space-4);
}

.category-rail {
  display: grid;
  gap: var(--app-space-2);
}

.category-rail button {
  position: relative;
  display: grid;
  gap: 4px;
  min-height: 72px;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  text-align: left;
  cursor: pointer;
  transition: border-color 180ms ease, background-color 180ms ease, box-shadow 180ms ease;
}

.category-rail button:hover,
.category-rail button:focus-visible {
  border-color: var(--app-color-primary-border);
  box-shadow: var(--app-shadow-panel);
  outline: none;
}

.category-rail button.active {
  border-color: var(--app-color-primary-border);
  background: var(--app-color-primary-soft);
}

.category-rail button span {
  font-weight: 650;
}

.category-rail button small {
  color: var(--app-color-text-muted);
  line-height: 1.4;
}

.category-rail button :deep(.el-tag) {
  position: absolute;
  top: 10px;
  right: 10px;
}

.style-editor-panel {
  min-width: 0;
  padding: var(--app-space-4);
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
  color: var(--app-color-text);
  font-size: 16px;
  font-weight: 650;
}

.style-panel-header p,
.layout-section-heading p {
  margin: 4px 0 0;
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.group-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  margin-bottom: var(--app-space-4);
  padding-bottom: var(--app-space-3);
  border-bottom: 1px solid var(--app-color-border);
}

.group-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  cursor: pointer;
  transition: border-color 180ms ease, background-color 180ms ease;
}

.group-tabs button:hover,
.group-tabs button:focus-visible {
  border-color: var(--app-color-primary);
  outline: none;
}

.group-tabs button.active {
  border-color: var(--app-color-primary);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
}

.layout-form {
  display: grid;
  gap: var(--app-space-3);
}

.layout-section-heading {
  margin-bottom: 14px;
}

.layout-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: var(--app-space-3) var(--app-space-4);
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
  gap: var(--app-space-3);
  padding: var(--app-space-4);
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
  border-bottom: 1px solid var(--app-color-border-soft);
}

.change-panel li strong {
  color: var(--app-color-text);
  font-size: 13px;
}

.change-panel li span {
  overflow-wrap: anywhere;
  font-size: 12px;
}

.change-note {
  padding: var(--app-space-3);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
  font-size: 12px;
  line-height: 1.5;
}

.preview-paper {
  position: relative;
  display: grid;
  align-content: center;
  min-height: 260px;
  overflow: hidden;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  background: #fff;
  color: #111827;
  box-shadow: var(--app-shadow-subtle);
}

.preview-header,
.preview-footer {
  position: absolute;
  right: 10%;
  left: 10%;
  color: #64748b;
  font-size: 9px;
  text-align: center;
}

.preview-header {
  top: 4%;
}

.preview-footer {
  bottom: 4%;
}

.preview-table {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.preview-table > div {
  padding: 6px;
  border: 1px solid;
}

.preview-disclaimer {
  margin: var(--app-space-2) 0 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 1180px) {
  .style-workbench {
    grid-template-columns: 210px minmax(0, 1fr);
  }

  .style-workbench > aside {
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
  .template-switcher,
  .version-switcher {
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
