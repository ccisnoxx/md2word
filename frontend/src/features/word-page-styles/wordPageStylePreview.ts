// 文件：frontend/src/features/word-page-styles/wordPageStylePreview.ts
// 用途：计算微缩 A4 Datasheet 组合预览画布的纸张边距比例、各区块近似排版样式与当前编辑分组高亮映射。
import type { CSSProperties } from "vue";

export type CompositePreviewZone =
  | "page_setup"
  | "header"
  | "identity"
  | "toc"
  | "heading1"
  | "heading2"
  | "heading3"
  | "normal"
  | "caption"
  | "table"
  | "table_note"
  | "footer";

export function resolveActivePreviewZone(groupName: string): CompositePreviewZone {
  if (groupName === "page_setup") {
    return "page_setup";
  }
  if (groupName === "header") {
    return "header";
  }
  if (groupName === "footer") {
    return "footer";
  }
  if (groupName === "part_number" || groupName === "category") {
    return "identity";
  }
  if (groupName.startsWith("toc_")) {
    return "toc";
  }
  if (groupName === "heading1") {
    return "heading1";
  }
  if (groupName === "heading2") {
    return "heading2";
  }
  if (groupName === "heading3") {
    return "heading3";
  }
  if (groupName === "caption" || groupName === "long_table_caption") {
    return "caption";
  }
  if (groupName === "table_style" || groupName === "table_content") {
    return "table";
  }
  if (groupName === "table_note") {
    return "table_note";
  }
  return "normal";
}

// 点击 A4 画布中的区块时，按可用分组优先映射回对应的配置分组名。
export function preferredGroupForZone(zone: CompositePreviewZone, availableGroups: string[]): string | null {
  const candidates: Record<CompositePreviewZone, string[]> = {
    page_setup: ["page_setup"],
    header: ["header"],
    identity: ["part_number", "category"],
    toc: ["toc_title", "toc_entry", "toc_level1"],
    heading1: ["heading1"],
    heading2: ["heading2"],
    heading3: ["heading3"],
    normal: ["normal"],
    caption: ["caption", "long_table_caption"],
    table: ["table_style", "table_content"],
    table_note: ["table_note"],
    footer: ["footer"],
  };
  for (const name of candidates[zone]) {
    if (availableGroups.includes(name)) {
      return name;
    }
  }
  if (zone === "toc") {
    return availableGroups.find((name) => name.startsWith("toc_")) || null;
  }
  return null;
}

function readNum(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clampMarginPercent(cm: number, axisCm: number): number {
  if (axisCm <= 0) {
    return 8;
  }
  return Number(Math.min(Math.max((cm / axisCm) * 100, 3), 24).toFixed(2));
}

export function buildCompositePaperStyle(config: Record<string, any>): CSSProperties {
  const setup = config.page_setup ?? {};
  const width = Math.max(readNum(setup.page_width_cm, 21), 10);
  const height = Math.max(readNum(setup.page_height_cm, 29.7), 10);
  const top = clampMarginPercent(readNum(setup.top_margin, 2.54), height);
  const right = clampMarginPercent(readNum(setup.right_margin, 2.54), width);
  const bottom = clampMarginPercent(readNum(setup.bottom_margin, 2.54), height);
  const left = clampMarginPercent(readNum(setup.left_margin, 2.54), width);
  return {
    aspectRatio: `${width} / ${height}`,
    padding: `${top}% ${right}% ${bottom}% ${left}%`,
  };
}

function resolveFontFamily(style: Record<string, any> | undefined): string {
  if (!style) {
    return "sans-serif";
  }
  const names = [style.font_name_en, style.font_name, style.font_name_zh, style.font_name_complex]
    .filter((item): item is string => typeof item === "string" && item.trim().length > 0);
  return names.length ? `${names.join(", ")}, sans-serif` : "sans-serif";
}

export function buildCompositeTextBlockStyle(
  style: Record<string, any> | undefined,
  fallbackFontPt = 10,
  scale = 0.72,
): CSSProperties {
  const fontPt = Math.max(readNum(style?.font_size, fallbackFontPt), 6);
  const alignment = String(style?.alignment || "left");
  return {
    fontFamily: resolveFontFamily(style),
    fontSize: `${Math.max(Number((fontPt * scale).toFixed(1)), 7)}px`,
    fontWeight: style?.bold ? 700 : 400,
    fontStyle: style?.italic ? "italic" : "normal",
    color: typeof style?.color === "string" && style.color.trim() ? style.color : "#111827",
    textAlign: (["left", "center", "right", "justify"].includes(alignment) ? alignment : "left") as CSSProperties["textAlign"],
    lineHeight: String(Math.max(readNum(style?.line_spacing, 1.25), 1)),
    marginTop: `${Math.min(readNum(style?.space_before, 0) * 0.35, 14)}px`,
    marginBottom: `${Math.min(readNum(style?.space_after, 0) * 0.35, 14)}px`,
    textIndent: `${Math.min(readNum(style?.first_line_indent_pt, 0) * 0.35, 24)}px`,
  };
}

export function buildCompositeTableStyles(config: Record<string, any>): {
  header: CSSProperties;
  cell: CSSProperties;
  borderColor: string;
} {
  const tableStyle = config.table_style ?? {};
  const tableContent = config.table_content ?? {};
  const borderColor = typeof tableStyle.border_color === "string" && tableStyle.border_color.trim()
    ? tableStyle.border_color
    : "#C7CDD4";
  const headerFill = typeof tableStyle.header_fill === "string" && tableStyle.header_fill.trim()
    ? tableStyle.header_fill
    : "#EEF3F8";
  const fontPt = Math.max(readNum(tableContent.font_size, 9), 6);
  const cellFontPx = Math.max(Number((fontPt * 0.7).toFixed(1)), 7);
  return {
    borderColor,
    header: {
      backgroundColor: headerFill,
      borderColor,
      fontFamily: resolveFontFamily(tableContent),
      fontSize: `${cellFontPx}px`,
      fontWeight: 700,
      color: typeof tableContent.color === "string" && tableContent.color.trim() ? tableContent.color : "#0F172A",
    },
    cell: {
      borderColor,
      fontFamily: resolveFontFamily(tableContent),
      fontSize: `${cellFontPx}px`,
      color: typeof tableContent.color === "string" && tableContent.color.trim() ? tableContent.color : "#111827",
    },
  };
}
