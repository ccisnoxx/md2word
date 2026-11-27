// 文件：frontend/src/features/word-page-styles/useWordPageStyleEditor.ts
// 用途：Word 页面样式编辑器的单数据源 Owner，管理模板/版本切换、字段校验、脏检查摘要与草稿保存。
import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { onBeforeRouteLeave, type Router } from "vue-router";

import { templatesApi } from "@/api/templates";
import type {
  TemplateDetailResponse,
  TemplateLayoutConfigFieldSchema,
  TemplateLayoutConfigResponse,
  TemplateListItemResponse,
  TemplateVersionResponse,
} from "@/api/types";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import {
  buildCompositePaperStyle,
  buildCompositeTableStyles,
  buildCompositeTextBlockStyle,
  preferredGroupForZone,
  resolveActivePreviewZone,
  type CompositePreviewZone,
} from "./wordPageStylePreview";

export type LayoutCategory = {
  id: string;
  title: string;
  description: string;
  groups: string[];
};

export type LayoutDirtySummaryItem = {
  groupName: string;
  path: string;
  label: string;
  before: string;
  after: string;
};

export const ALIGNMENT_OPTIONS = [
  { value: "left", label: "左对齐" },
  { value: "center", label: "居中" },
  { value: "right", label: "右对齐" },
  { value: "justify", label: "两端对齐" },
];

export const COLOR_PREDEFINES = ["#000000", "#475569", "#2563EB", "#10B981", "#F97316", "#EEF3F8", "#C7CDD4"];
const COLOR_VALUE_RE = /^#[0-9a-fA-F]{6}$/;

function stableStringify(value: unknown): string {
  return JSON.stringify(value);
}

function cloneLayoutConfig(config: Record<string, unknown>): Record<string, any> {
  return JSON.parse(JSON.stringify(config));
}

function isRecord(value: unknown): value is Record<string, any> {
  return typeof value === "object" && value !== null;
}

function displayLayoutValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function normalizeColorValues(
  config: Record<string, any>,
  groups: TemplateLayoutConfigResponse["field_schema"]["groups"],
): void {
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

export function useWordPageStyleEditor(
  templateIdRef: Ref<string>,
  router: Pick<Router, "push">,
  options: { registerRouteGuard?: boolean } = { registerRouteGuard: true },
) {
  const templates = ref<TemplateListItemResponse[]>([]);
  const selectedTemplateId = ref(templateIdRef.value);
  const templateVersions = ref<TemplateVersionResponse[]>([]);
  const selectedVersion = ref<number | null>(null);
  const template = ref<TemplateDetailResponse | null>(null);
  const layoutConfig = ref<TemplateLayoutConfigResponse | null>(null);
  const layoutConfigForm = ref<Record<string, any>>({});
  const sourceLayoutConfig = ref<Record<string, any>>({});
  const activeCategoryId = ref("");
  const activeLayoutGroup = ref("");
  const layoutValidationErrors = ref<Record<string, string>>({});
  const dirtyDrawerOpen = ref(false);
  const loading = ref(false);
  const layoutConfigLoading = ref(false);
  const layoutConfigSaving = ref(false);
  const error = ref<ApiClientError | null>(null);

  let pageLoadSequence = 0;
  let layoutLoadSequence = 0;

  const isLegacyInternalVersion = computed(
    () => templateVersions.value.find((item) => item.version === layoutConfig.value?.version)?.legacy_internal_only === true,
  );
  const layoutMetaEntries = computed(() => Object.entries(layoutConfig.value?.meta ?? {}));
  const layoutGroupEntries = computed(() => Object.entries(layoutConfig.value?.field_schema.groups ?? {}));
  const allGroupNames = computed(() => Object.keys(layoutConfig.value?.field_schema.groups ?? {}));

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
  const activeCategory = computed(
    () => availableCategories.value.find((category) => category.id === activeCategoryId.value) || null,
  );
  const activeCategoryGroups = computed(() => {
    const groups = layoutConfig.value?.field_schema.groups ?? {};
    return (activeCategory.value?.groups ?? []).filter((groupName) => groupName in groups);
  });
  const visibleLayoutGroupEntries = computed(() =>
    layoutGroupEntries.value.filter(([groupName]) => groupName === activeLayoutGroup.value),
  );

  const isLayoutDirty = computed(
    () => stableStringify(sourceLayoutConfig.value) !== stableStringify(layoutConfigForm.value),
  );
  const dirtySummaries = computed<LayoutDirtySummaryItem[]>(() => {
    const groups = layoutConfig.value?.field_schema.groups ?? {};
    const summaries: LayoutDirtySummaryItem[] = [];
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
  });
  const visibleDirtySummaries = computed(() => dirtySummaries.value.slice(0, 6));
  const dirtyFieldCount = computed(() => dirtySummaries.value.length);
  const activeCategoryDirtyCount = computed(() =>
    activeCategory.value ? categoryDirtyCount(activeCategory.value.id) : 0,
  );

  // 组合 A4 预览画布投影
  const activePreviewZone = computed(() => resolveActivePreviewZone(activeLayoutGroup.value));
  const compositePreview = computed(() => {
    const cfg = layoutConfigForm.value;
    const samples = layoutConfig.value?.preview_samples ?? {};
    const readSample = (key: string, fallback: string): string => {
      const value = samples[key];
      return typeof value === "string" && value.trim() ? value : fallback;
    };
    return {
      paperStyle: buildCompositePaperStyle(cfg),
      headerEnabled: Boolean(cfg.header?.enabled),
      headerText: String(cfg.header?.title_text || "电子元器件数据手册"),
      headerStyle: buildCompositeTextBlockStyle(cfg.header, 8, 0.8),
      partNumberText: readSample("part_number", "OPA228 / OPA2228"),
      partNumberStyle: buildCompositeTextBlockStyle(cfg.part_number, 14, 0.72),
      categoryText: readSample("category", "高精度低噪声运算放大器"),
      categoryStyle: buildCompositeTextBlockStyle(cfg.category, 10, 0.72),
      tocTitleText: "目录",
      tocTitleStyle: buildCompositeTextBlockStyle(cfg.toc_title, 10, 0.72),
      tocEntryText: "1.1 电气特性参数 .................. 1",
      tocEntryStyle: buildCompositeTextBlockStyle(cfg.toc_entry ?? cfg.toc_level1, 8.5, 0.74),
      heading1Text: readSample("heading1_text", "1 产品概述"),
      heading1Style: buildCompositeTextBlockStyle(cfg.heading1, 13, 0.74),
      heading2Text: readSample("heading2_text", "1.1 关键电气特性"),
      heading2Style: buildCompositeTextBlockStyle(cfg.heading2, 11, 0.74),
      heading3Text: readSample("heading3_text", "1.1.1 直流精度参数"),
      heading3Style: buildCompositeTextBlockStyle(cfg.heading3, 10, 0.74),
      normalText: readSample(
        "normal_text",
        "OPA228 系列精密运放提供极低失调电压与高速压摆率，适用于高精度仪器仪表与工业采集电路。",
      ),
      normalStyle: buildCompositeTextBlockStyle(cfg.normal, 9.5, 0.74),
      captionText: readSample("caption_text", "表 1 关键电气参数（TA = 25°C）"),
      captionStyle: buildCompositeTextBlockStyle(cfg.caption ?? cfg.long_table_caption, 8.5, 0.76),
      tableStyles: buildCompositeTableStyles(cfg),
      tableNoteText: readSample("table_note_text", "注：所有典型值均在 VS = ±15 V 条件下实测获得。"),
      tableNoteStyle: buildCompositeTextBlockStyle(cfg.table_note, 8, 0.76),
      footerEnabled: Boolean(cfg.footer?.enabled),
      footerLeftText: String(cfg.footer?.left_text || ""),
      footerRightText: String(cfg.footer?.right_text || ""),
      footerShowPageNumber: Boolean(cfg.footer?.show_page_number),
      footerStyle: buildCompositeTextBlockStyle(cfg.footer, 8, 0.8),
    };
  });

  function versionStatusLabel(status: string): string {
    return (
      {
        draft: "草稿",
        published: "已发布",
        disabled: "已禁用",
        superseded: "已替代",
      }[status] || status
    );
  }

  function layoutMetaLabel(fieldName: string): string {
    return layoutConfig.value?.field_schema.meta?.[fieldName]?.label || fieldName;
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
    const allowed = fieldSchema.options ?? ALIGNMENT_OPTIONS.map((option) => option.value);
    return ALIGNMENT_OPTIONS.filter((option) => allowed.includes(option.value));
  }

  function fieldError(groupName: string, fieldName: string): string {
    return layoutValidationErrors.value[`${groupName}.${fieldName}`] || "";
  }

  function groupHasErrors(groupName: string): boolean {
    return Object.keys(layoutValidationErrors.value).some(
      (path) => path === groupName || path.startsWith(`${groupName}.`),
    );
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

  function activateFirstAvailableGroup(groups: TemplateLayoutConfigResponse["field_schema"]["groups"]): void {
    const category = layoutCategories.value.find((item) => item.groups.some((groupName) => groupName in groups));
    activeCategoryId.value = category?.id || "";
    activeLayoutGroup.value = category?.groups.find((groupName) => groupName in groups) || Object.keys(groups)[0] || "";
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
    if (!layoutConfig.value?.field_schema.groups[groupName]) {
      return;
    }
    const owningCategory = availableCategories.value.find((category) => category.groups.includes(groupName));
    if (owningCategory) {
      activeCategoryId.value = owningCategory.id;
    }
    activeLayoutGroup.value = groupName;
  }

  function selectPreviewZone(zone: CompositePreviewZone): void {
    const targetGroup = preferredGroupForZone(zone, allGroupNames.value);
    if (targetGroup) {
      setActiveGroup(targetGroup);
    }
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
    if (fieldSchema.type === "color" && value !== null && value !== "" && (typeof value !== "string" || !COLOR_VALUE_RE.test(value))) {
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
      setActiveGroup(firstErrorGroup);
    }
    return Object.keys(errors).length === 0;
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

  async function loadLayoutConfig(version?: number, templateId = templateIdRef.value): Promise<void> {
    const requestSequence = ++layoutLoadSequence;
    layoutConfigLoading.value = true;
    error.value = null;
    try {
      const response = await templatesApi.getLayoutConfig(templateId, version);
      if (requestSequence !== layoutLoadSequence || templateId !== templateIdRef.value) {
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
      if (requestSequence !== layoutLoadSequence || templateId !== templateIdRef.value) {
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

  async function loadAll(): Promise<void> {
    const requestSequence = ++pageLoadSequence;
    const templateId = templateIdRef.value;
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

  async function confirmReloadAll(): Promise<void> {
    if (!(await confirmDiscardDirty("刷新会丢弃当前未保存改动。"))) {
      return;
    }
    await loadAll();
  }

  async function changeTemplate(nextTemplateId: string | number | boolean | Record<string, unknown>): Promise<void> {
    const nextId = String(nextTemplateId);
    if (nextId === templateIdRef.value) {
      return;
    }
    if (!(await confirmDiscardDirty("切换模板会丢弃当前未保存改动。"))) {
      selectedTemplateId.value = templateIdRef.value;
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

  function openTemplateDocument(): void {
    void router.push(`/settings/templates/${templateIdRef.value}`);
  }

  function openValidationFlow(): void {
    if (!layoutConfig.value) {
      return;
    }
    void router.push({
      path: `/settings/templates/${templateIdRef.value}`,
      query: { validate_version: String(layoutConfig.value.version) },
    });
  }

  function resetLayoutConfigForm(): void {
    layoutConfigForm.value = cloneLayoutConfig(sourceLayoutConfig.value);
    layoutValidationErrors.value = {};
    dirtyDrawerOpen.value = false;
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
      const version = await templatesApi.createLayoutConfigVersion(templateIdRef.value, {
        base_template_version_id: layoutConfig.value.template_version_id || `${templateIdRef.value}@${layoutConfig.value.version}`,
        expected_config_sha256: layoutConfig.value.config_sha256 || "",
        expected_active_template_version_id: layoutConfig.value.active_template_version_id,
        changes,
      });
      templateVersions.value = [version, ...templateVersions.value.filter((item) => item.version !== version.version)];
      ElMessage.success(`已生成页面样式 draft version ${version.version}。完成验证、发布并设为默认后才会影响后续 Word 生成。`);
      dirtyDrawerOpen.value = false;
      await loadLayoutConfig(version.version);
    } catch (caught) {
      error.value = normalizeApiError(caught);
      applyServerFieldErrors(error.value.raw);
    } finally {
      layoutConfigSaving.value = false;
    }
  }

  function handleBeforeUnload(event: BeforeUnloadEvent): void {
    if (!isLayoutDirty.value) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
  }

  if (options.registerRouteGuard !== false) {
    onBeforeRouteLeave(() => {
      if (!isLayoutDirty.value) {
        return true;
      }
      return window.confirm("当前 Word 页面样式配置有未保存改动，确定离开吗？");
    });
  }

  watch(templateIdRef, () => {
    void loadAll();
  });

  onMounted(() => {
    if (typeof window !== "undefined") {
      window.addEventListener("beforeunload", handleBeforeUnload);
    }
    void loadAll();
  });

  onBeforeUnmount(() => {
    pageLoadSequence += 1;
    layoutLoadSequence += 1;
    if (typeof window !== "undefined") {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    }
  });

  return {
    templates,
    selectedTemplateId,
    templateVersions,
    selectedVersion,
    template,
    layoutConfig,
    isLegacyInternalVersion,
    layoutConfigForm,
    activeCategoryId,
    activeLayoutGroup,
    layoutMetaEntries,
    layoutGroupEntries,
    availableCategories,
    activeCategory,
    activeCategoryGroups,
    visibleLayoutGroupEntries,
    isLayoutDirty,
    dirtySummaries,
    visibleDirtySummaries,
    dirtyFieldCount,
    activeCategoryDirtyCount,
    dirtyDrawerOpen,
    activePreviewZone,
    compositePreview,
    loading,
    layoutConfigLoading,
    layoutConfigSaving,
    error,
    loadAll,
    loadLayoutConfig,
    confirmReloadAll,
    changeTemplate,
    changeVersion,
    openTemplateDocument,
    openValidationFlow,
    resetLayoutConfigForm,
    saveLayoutConfigVersion,
    setActiveCategory,
    setActiveGroup,
    selectPreviewZone,
    validateField,
    validateLayoutConfigForm,
    buildLayoutChanges,
    versionStatusLabel,
    layoutMetaLabel,
    fieldLabel,
    layoutGroupTitle,
    layoutGroupDescription,
    displayedFieldEntries,
    alignmentOptionsFor,
    fieldError,
    groupHasErrors,
    groupDirtyCount,
    categoryDirtyCount,
  };
}

export type WordPageStyleEditor = ReturnType<typeof useWordPageStyleEditor>;
