// 文件：frontend/src/features/word-page-styles/useWordPageStyleEditor.test.ts
// 用途：验证页面样式编辑器 Composable 脏检查、校验、草稿保存与 A4 组合预览样式计算。
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRenderer, ref } from "vue";
import type { Router } from "vue-router";

import { templatesApi } from "@/api/templates";
import type { TemplateLayoutConfigResponse } from "@/api/types";
import { useWordPageStyleEditor } from "./useWordPageStyleEditor";
import {
  buildCompositePaperStyle,
  buildCompositeTableStyles,
  preferredGroupForZone,
  resolveActivePreviewZone,
} from "./wordPageStylePreview";

vi.mock("@/api/templates", () => ({
  templatesApi: {
    list: vi.fn(),
    get: vi.fn(),
    listVersions: vi.fn(),
    getLayoutConfig: vi.fn(),
    createLayoutConfigVersion: vi.fn(),
  },
}));
vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
}));

const renderer = createRenderer<object, object>({
  patchProp: () => {},
  insert: () => {},
  remove: () => {},
  createElement: () => ({}),
  createText: () => ({}),
  createComment: () => ({}),
  setText: () => {},
  setElementText: () => {},
  parentNode: () => null,
  nextSibling: () => null,
});

const layoutResponse: TemplateLayoutConfigResponse = {
  template_id: "default",
  template_version_id: "default@1",
  version: 1,
  status: "published",
  is_default: true,
  active_template_version_id: "default@1",
  source_path: "templates/default/layout.yaml",
  config_sha256: "sha256:" + "a".repeat(64),
  meta: { template_name: "默认模板" },
  preview_samples: { heading1_text: "1 电气特性", normal_text: "示例正文文本" },
  config: {
    page_setup: { page_width_cm: 21, page_height_cm: 29.7, top_margin: 2.54, right_margin: 2.54, bottom_margin: 2.54, left_margin: 2.54 },
    heading1: { font_size: 14, bold: true, color: "2563EB", font_name: "SimHei" },
    table_style: { header_fill: "EEF3F8", border_color: "C7CDD4" },
    table_content: { font_size: 9, color: "#111827", font_name: "SimSun" },
  },
  field_schema: {
    meta: { template_name: { label: "模板名称" } },
    categories: [
      { key: "page", label: "页面", groups: ["page_setup"] },
      { key: "headings", label: "标题", groups: ["heading1"] },
      { key: "tables", label: "表格", groups: ["table_style", "table_content"] },
    ],
    group_meta: {
      page_setup: { label: "页面设置", description: "纸张与边距" },
      heading1: { label: "一级标题", description: "一级标题样式" },
      table_style: { label: "表格样式", description: "边框与底色" },
      table_content: { label: "表格正文", description: "单元格字体" },
    },
    groups: {
      page_setup: {
        page_width_cm: { label: "页宽", type: "number", min: 10, max: 50 },
        top_margin: { label: "上边距", type: "number", min: 0.5, max: 10 },
      },
      heading1: {
        font_size: { label: "字号", type: "number", min: 6, max: 48 },
        bold: { label: "加粗", type: "boolean" },
        color: { label: "颜色", type: "color" },
        font_name: { label: "字体", type: "text" },
      },
      table_style: {
        header_fill: { label: "表头底色", type: "color" },
        border_color: { label: "边框色", type: "color" },
      },
      table_content: {
        font_size: { label: "字号", type: "number", min: 6, max: 24 },
        color: { label: "文字色", type: "color" },
        font_name: { label: "字体", type: "text" },
      },
    },
  },
} as unknown as TemplateLayoutConfigResponse;

const disposers: Array<() => void> = [];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(templatesApi.list).mockResolvedValue({ items: [{ id: "default", name: "默认模板", is_default: true }] } as never);
  vi.mocked(templatesApi.get).mockResolvedValue({ id: "default", name: "默认模板", is_default: true } as never);
  vi.mocked(templatesApi.listVersions).mockResolvedValue({ items: [{ template_version_id: "default@1", version: 1, status: "published", is_default: true }] } as never);
  vi.mocked(templatesApi.getLayoutConfig).mockResolvedValue(layoutResponse);
});

afterEach(() => {
  disposers.splice(0).forEach((dispose) => dispose());
  vi.unstubAllGlobals();
});

describe("wordPageStylePreview A4 组合预览计算", () => {
  it("按真实纸张比例计算边距与表格样式，并支持双向区块映射", () => {
    const paper = buildCompositePaperStyle(layoutResponse.config);
    expect(paper.aspectRatio).toBe("21 / 29.7");
    expect(String(paper.padding)).toContain("%");

    const tableStyles = buildCompositeTableStyles({
      table_style: { header_fill: "#DBEAFE", border_color: "#94A3B8" },
      table_content: { font_size: 10, color: "#0F172A", font_name: "SimSun" },
    });
    expect(tableStyles.header.backgroundColor).toBe("#DBEAFE");
    expect(tableStyles.borderColor).toBe("#94A3B8");

    expect(resolveActivePreviewZone("table_content")).toBe("table");
    expect(resolveActivePreviewZone("toc_level1")).toBe("toc");
    expect(preferredGroupForZone("table", ["page_setup", "table_style", "table_content"])).toBe("table_style");
  });
});

describe("useWordPageStyleEditor 脏检查与保存", () => {
  it("归一化颜色值、追踪脏差异、联动 A4 预览点击并仅提交修改字段", async () => {
    vi.stubGlobal("window", Object.assign(new EventTarget(), { confirm: vi.fn(() => true) }));
    const router = { push: vi.fn() } as unknown as Router;

    let editor!: ReturnType<typeof useWordPageStyleEditor>;
    const app = renderer.createApp({
      setup() {
        editor = useWordPageStyleEditor(ref("default"), router, { registerRouteGuard: false });
        return () => null;
      },
    });
    app.mount({});
    disposers.push(() => app.unmount());

    await vi.waitFor(() => expect(editor.layoutConfig.value).not.toBeNull());
    // 6 位裸色值自动补全 # 前缀
    expect(editor.layoutConfigForm.value.heading1.color).toBe("#2563EB");
    expect(editor.isLayoutDirty.value).toBe(false);

    // 点击 A4 画布的表格区 -> 自动切换到 table_style 分组
    editor.selectPreviewZone("table");
    expect(editor.activeLayoutGroup.value).toBe("table_style");
    expect(editor.activePreviewZone.value).toBe("table");

    // 修改一级标题字号并校验脏摘要
    editor.layoutConfigForm.value.heading1.font_size = 16;
    expect(editor.isLayoutDirty.value).toBe(true);
    expect(editor.dirtyFieldCount.value).toBe(1);
    expect(editor.buildLayoutChanges()).toEqual({ heading1: { font_size: 16 } });

    vi.mocked(templatesApi.createLayoutConfigVersion).mockResolvedValueOnce({
      template_version_id: "default@2",
      version: 2,
      status: "draft",
      is_default: false,
    } as never);
    await editor.saveLayoutConfigVersion();
    expect(templatesApi.createLayoutConfigVersion).toHaveBeenCalledWith("default", {
      base_template_version_id: "default@1",
      expected_config_sha256: "sha256:" + "a".repeat(64),
      expected_active_template_version_id: "default@1",
      changes: { heading1: { font_size: 16 } },
    });
  });
});
