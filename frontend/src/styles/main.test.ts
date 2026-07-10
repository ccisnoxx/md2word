// 守护全局滚动条分级合同，避免页面重新使用浏览器默认粗滚动条。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

function readSource(relativePath: string): string {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8");
}

const styleSource = readSource("./main.scss");
const sidebarSource = readSource("../components/AppSidebar.vue");
const savedViewSource = readSource("../components/SavedViewStrip.vue");
const jobTableSource = readSource("../components/JobTable.vue");
const qaPanelSource = readSource("../components/TranslationQaReviewPanel.vue");
const acceptanceSource = readSource("../pages/AcceptanceCenterPage.vue");

describe("全局滚动条分级合同", () => {
  it("为浅色和深色主题提供同一组滚动条令牌", () => {
    expect(styleSource).toContain("--app-scrollbar-size: 6px;");
    expect(styleSource.match(/--app-scrollbar-thumb:/g)).toHaveLength(2);
    expect(styleSource.match(/--app-scrollbar-thumb-hover:/g)).toHaveLength(2);
    expect(styleSource.match(/--app-scrollbar-thumb-active:/g)).toHaveLength(2);
  });

  it("只通过显式 transient 和 persistent 工具类控制滚动条", () => {
    expect(styleSource).toContain(".app-scrollbar-transient:hover");
    expect(styleSource).toContain(".app-scrollbar-transient:focus-within");
    expect(styleSource).toContain(".app-scrollbar-persistent::-webkit-scrollbar-thumb");
    expect(styleSource).not.toContain("*::-webkit-scrollbar");
  });

  it("把导航和短操作条设为 transient，把长内容设为 persistent", () => {
    expect(sidebarSource).toContain('class="sidebar-nav app-scrollbar-transient"');
    expect(savedViewSource).toContain('class="saved-view-strip app-scrollbar-transient"');
    expect(jobTableSource).toContain('class="job-table app-scrollbar-persistent"');
    expect(qaPanelSource).toContain('root-class="translation-qa-review-panel app-scrollbar-persistent"');
  });
});

describe("静态卡片反馈合同", () => {
  it("只让真实可交互卡片获得抬升反馈", () => {
    expect(styleSource).toContain("button.app-metric-card:not(:disabled):hover");
    expect(styleSource).not.toContain("\n.app-metric-card:hover,");
    expect(styleSource).not.toContain("\n.app-filter-panel:hover");
  });

  it("禁用验收卡片保持正文可读", () => {
    expect(acceptanceSource).toMatch(/\.tier-card:disabled \{[^}]*cursor: default;[^}]*transform: none;/);
    expect(acceptanceSource).not.toMatch(/\.tier-card:disabled \{[^}]*opacity:/);
  });
});
