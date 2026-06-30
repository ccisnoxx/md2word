// File: frontend/tests/smoke/governance-workbench.spec.ts
// Purpose: Browser smoke coverage for governance/configuration workbench templates.
import { expect, test, type Page, type Route } from "@playwright/test";

import { expectNoPageHorizontalOverflow } from "./support/accessibility";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";

const templateDetail = {
  id: "default",
  name: "Datasheet Default",
  is_default: true,
  latest_version: 1,
  versions: [],
  template_file: {
    label: "Word 模板",
    exists: true,
    file_name: "datasheet_template.docx",
    size_bytes: 1024,
    updated_at: "2026-06-11T00:00:00Z",
    sha256: "sha256:docx",
    download_url: "/api/v1/templates/default/download",
  },
  layout_config: {
    label: "页面布局 YAML",
    exists: true,
    file_name: "datasheet_template.yaml",
    size_bytes: 2048,
    updated_at: "2026-06-11T00:00:00Z",
    sha256: "sha256:layout",
    download_url: null,
  },
  subscript_config: {
    label: "术语上下标 YAML",
    exists: true,
    file_name: "subscripts_dictionary.yaml",
    size_bytes: 512,
    updated_at: "2026-06-11T00:00:00Z",
    sha256: "sha256:subscript",
    download_url: null,
  },
};

const templateLayoutConfig = {
  template_id: "default",
  template_version_id: "default@1",
  version: 1,
  source_path: "resources/template_configs/datasheet_template.yaml",
  config_sha256: "sha256:layout",
  meta: {
    schema_version: "template-config/v1",
    template_name: "数据手册模板",
    output_filename: "datasheet_template.docx",
  },
  config: {
    page_setup: { top_margin: 2.3 },
    heading1: { font_name: "宋体", font_size: 13, bold: true, color: "#0c69b2", alignment: "left" },
    heading2: { font_size: 11 },
    heading3: { font_size: 10 },
    normal: { font_size: 10.5, color: "#000000", alignment: "justify" },
    table_content: { font_size: 9 },
    table_style: { style_name: "Table Grid", header_fill: "#EEF3F8", border_color: "#C7CDD4" },
    table_note: { font_size: 8, italic: false },
    caption: { font_size: 9 },
    long_table_caption: { font_size: 10.5 },
    header: { enabled: false, logo_path: "assets/company_logo.png", title_text: "数据手册" },
    footer: { enabled: false, show_page_number: true, alignment: "center" },
  },
  field_schema: {
    meta: {
      schema_version: { type: "text", label: "schema_version", readonly: true },
      template_name: { type: "text", label: "配置名称", readonly: true },
      output_filename: { type: "text", label: "输出文件名", readonly: true },
    },
    groups: {
      page_setup: { top_margin: { type: "number", label: "上边距", unit: "cm" } },
      heading1: {
        font_name: { type: "text", label: "字体" },
        font_size: { type: "number", label: "字号", unit: "pt" },
        bold: { type: "boolean", label: "加粗" },
        color: { type: "color", label: "颜色" },
        alignment: { type: "alignment", label: "对齐方式" },
      },
      heading2: { font_size: { type: "number", label: "字号", unit: "pt" } },
      heading3: { font_size: { type: "number", label: "字号", unit: "pt" } },
      normal: {
        font_size: { type: "number", label: "字号", unit: "pt" },
        color: { type: "color", label: "颜色" },
        alignment: { type: "alignment", label: "对齐方式" },
      },
      table_content: { font_size: { type: "number", label: "字号", unit: "pt" } },
      table_style: {
        style_name: { type: "text", label: "表格样式" },
        header_fill: { type: "color", label: "表头底色" },
        border_color: { type: "color", label: "边框颜色" },
      },
      table_note: {
        font_size: { type: "number", label: "字号", unit: "pt" },
        italic: { type: "boolean", label: "斜体" },
      },
      caption: { font_size: { type: "number", label: "字号", unit: "pt" } },
      long_table_caption: { font_size: { type: "number", label: "字号", unit: "pt" } },
      header: {
        enabled: { type: "boolean", label: "启用页眉覆盖" },
        logo_path: { type: "text", label: "Logo 路径", readonly: true },
        title_text: { type: "text", label: "页眉标题" },
      },
      footer: {
        enabled: { type: "boolean", label: "启用页脚覆盖" },
        show_page_number: { type: "boolean", label: "显示页码" },
        alignment: { type: "alignment", label: "页脚对齐" },
      },
    },
  },
};

const configSummary = {
  generated_at: "2026-06-30T00:00:00Z",
  overall_status: "warning",
  release_gate: {
    p0_document_jobs_required: true,
    p0_document_jobs_ready: false,
    blockers: ["p0_document_jobs_not_ready"],
    warnings: ["translation_defaults_missing"],
    blocker_findings: [
      {
        code: "p0_document_jobs_not_ready",
        severity: "critical",
        message: "P0 document_jobs 发布门禁未满足。",
        route: "/system-status/ops-dashboard",
        target_id: null,
      },
    ],
    warning_findings: [],
  },
  groups: [
    {
      id: "runtime_readiness",
      label: "运行门禁",
      status: "blocked",
      detail_status: "complete",
      route: "/system-status",
      default_label: "hostdzire",
      draft_count: null,
      pending_count: 1,
      warning_count: 1,
      blocker_count: 1,
      findings: [
        {
          code: "p0_document_jobs_not_ready",
          severity: "critical",
          message: "P0 document_jobs 发布门禁未满足。",
          route: "/system-status/ops-dashboard",
          target_id: null,
        },
      ],
    },
    {
      id: "templates",
      label: "Word 模板",
      status: "warning",
      detail_status: "complete",
      route: "/settings/templates",
      default_label: "default@1",
      draft_count: 1,
      pending_count: 1,
      warning_count: 1,
      blocker_count: 0,
      findings: [
        {
          code: "template_draft_pending",
          severity: "warning",
          message: "当前模板存在未发布草稿。",
          route: "/settings/templates/default",
          target_id: "default",
        },
      ],
    },
    {
      id: "term_rule_sets",
      label: "术语规则",
      status: "ready",
      detail_status: "complete",
      route: "/settings/term-rule-sets",
      default_label: "electronics-default@3",
      draft_count: 0,
      pending_count: 0,
      warning_count: 0,
      blocker_count: 0,
      findings: [],
    },
    {
      id: "translation_profiles",
      label: "翻译配置",
      status: "warning",
      detail_status: "complete",
      route: "/settings/translation-profiles",
      default_label: "default@2",
      draft_count: 1,
      pending_count: 0,
      warning_count: 1,
      blocker_count: 0,
      findings: [],
    },
    {
      id: "translation_term_sets",
      label: "翻译术语集",
      status: "warning",
      detail_status: "complete",
      route: "/settings/translation-term-sets",
      default_label: "electronics-default@1",
      draft_count: 1,
      pending_count: 2,
      warning_count: 1,
      blocker_count: 0,
      findings: [
        {
          code: "translation_term_proposal_conflict",
          severity: "warning",
          message: "待审核翻译术语建议存在版本冲突。",
          route: "/settings/translation-term-sets",
          target_id: "electronics-default",
        },
      ],
    },
  ],
};

const termRuleCategories = {
  items: [{ id: "electronics", name: "电子元件" }],
};

const draftRules = {
  items: [
    {
      id: "rule_voltage",
      source_term: "VIN",
      category_id: "electronics",
      category_name: "电子元件",
      segments: [
        { segment_text: "V", render_type: "plain" },
        { segment_text: "IN", render_type: "subscript" },
      ],
      enabled: true,
    },
  ],
};

const termProposal = {
  id: "proposal_term_001",
  proposal_id: "proposal_term_001",
  status: "pending_review",
  intent: "update",
  source_term: "VIN",
  category_id: "electronics",
  segments: [
    { segment_text: "V", render_type: "plain" },
    { segment_text: "IN", render_type: "subscript" },
  ],
  reason: "需要统一大小写和上下标表现。",
  source_job_id: "docjob_gate_term",
  source_file_id: "file_term_source",
  observed_term_rule_set_id: "electronics-default",
  observed_term_rule_version: "3",
  target_rule_id: "rule_voltage",
  target_rule_snapshot: {
    id: "rule_voltage",
    source_term: "VIN",
    category_id: "electronics",
    segments: [
      { segment_text: "V", render_type: "plain" },
      { segment_text: "IN", render_type: "subscript" },
    ],
  },
  review_note: null,
};

const translationProposal = {
  id: "proposal_translation_001",
  proposal_id: "proposal_translation_001",
  status: "pending",
  source_job_id: "docjob_gate_translation",
  source_file_id: "file_translation_source",
  observed_translation_term_set_id: "electronics-default",
  observed_translation_term_version: "1",
  changes: [
    {
      action: "update",
      source_term: "VIN",
      target_term: "输入电压",
      note: "统一推荐译法。",
    },
  ],
  published_translation_term_set_id: null,
  published_translation_term_version: null,
  review_note: null,
};

const translationTermSetDetail = {
  set_id: "electronics-default",
  language_pair: "en-zh",
  default_version: "1",
  version_count: 2,
  versions: [
    {
      version: "1",
      is_default: true,
      term_count: 12,
      snapshot_hash: "sha256:published",
      published_at: "2026-06-11T00:00:00Z",
      published_by: "admin",
      release_note: "initial release",
    },
  ],
};

const translationTermSetDraft = {
  base_version: "1",
  snapshot_hash: "sha256:draft",
  term_count: 13,
  validation: {
    valid: false,
    errors: [
      { code: "duplicate_source_term", message: "存在重复规范化术语。", normalized_source_term: "vin" },
    ],
    warnings: [
      { code: "deprecated_term", message: "存在建议废弃条目。", normalized_source_term: "vout" },
    ],
  },
  entries: [
    {
      source_term: "VIN",
      target_term: "输入电压",
      recommended_translations: ["输入电压"],
      forbidden_translations: [],
      synonyms: [],
      language_pair: "en-zh",
      project: "default",
      content_type: "datasheet",
      tags: ["power"],
      status: "publishable",
      updated_at: "2026-06-11T00:00:00Z",
      maintainer: "admin",
      case_sensitive: false,
      priority: 1,
      domain: "power",
      category: "voltage",
      note: "draft note",
    },
  ],
};

const translationTermSetDiff = {
  base_version: "1",
  target_version: "draft",
  summary: { added: 1, removed: 0, changed: 2, unchanged: 9 },
  items: [
    {
      kind: "changed",
      source_term: "VIN",
      normalized_source_term: "vin",
      changed_fields: ["target_term"],
      before: { target_term: "输入端电压" },
      after: { target_term: "输入电压" },
    },
  ],
};

const translationTermSetPreflight = {
  publish_blocked: true,
  blocking_reasons: ["存在重复规范化术语。"],
};

const translationProposalCompatibility = {
  summary: {
    total: 1,
    compatible: 0,
    warning: 0,
    conflict: 1,
  },
  items: [
    {
      proposal_id: "proposal_translation_001",
      compatibility: "conflict",
      observed_version: "1",
      change_count: 1,
      conflicts: [{ code: "snapshot_hash_conflict" }],
      warnings: [],
    },
  ],
};

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function setupGovernanceApi(page: Page): Promise<void> {
  await page.addInitScript((tokenKey) => {
    window.localStorage.setItem(tokenKey, "smoke-token");
  }, TOKEN_STORAGE_KEY);

  await page.route("**/api/v1/auth/me", async (route) => {
    await fulfillJson(route, {
      id: "user_admin",
      username: "admin",
      role: "admin",
      roles: ["admin"],
      permissions: ["settings:read", "settings:write", "term_proposals:read", "system:read", "ops:read", "audit:read", "users:manage"],
      tenant_id: "tenant_default",
      company_id: "company_default",
      display_name: "Admin",
    });
  });

  await page.route(/\/api\/v1\/config-workbench\/summary\?mode=overview$/, async (route) => {
    await fulfillJson(route, configSummary);
  });

  await page.route(/\/api\/v1\/term-rule-categories$/, async (route) => {
    await fulfillJson(route, termRuleCategories);
  });

  await page.route(/\/api\/v1\/term-rule-sets\/electronics-default\/draft\/rules\?.*$/, async (route) => {
    await fulfillJson(route, draftRules);
  });

  await page.route(/\/api\/v1\/term-rule-proposals\?.*$/, async (route) => {
    await fulfillJson(route, { items: [termProposal] });
  });

  await page.route(/\/api\/v1\/term-rules\/rule_voltage$/, async (route) => {
    await fulfillJson(route, draftRules.items[0]);
  });

  await page.route(/\/api\/v1\/translation-term-proposals\?.*$/, async (route) => {
    await fulfillJson(route, { items: [translationProposal] });
  });

  await page.route(/\/api\/v1\/translation-term-sets$/, async (route) => {
    await fulfillJson(route, { items: [{ set_id: "electronics-default", language_pair: "en-zh", default_version: "1", version_count: 2 }] });
  });

  await page.route(/\/api\/v1\/translation-term-sets\/electronics-default$/, async (route) => {
    await fulfillJson(route, translationTermSetDetail);
  });
  await page.route(/\/api\/v1\/translation-term-sets\/electronics-default\/draft$/, async (route) => {
    await fulfillJson(route, translationTermSetDraft);
  });
  await page.route(/\/api\/v1\/translation-term-sets\/electronics-default\/diff$/, async (route) => {
    await fulfillJson(route, translationTermSetDiff);
  });
  await page.route(/\/api\/v1\/translation-term-sets\/electronics-default\/preflight$/, async (route) => {
    await fulfillJson(route, translationTermSetPreflight);
  });
  await page.route(/\/api\/v1\/translation-term-sets\/electronics-default\/proposal-compatibility\?.*$/, async (route) => {
    await fulfillJson(route, translationProposalCompatibility);
  });

  await page.route(/\/api\/v1\/templates$/, async (route) => {
    await fulfillJson(route, { items: [{ id: "default", name: "Datasheet Default", is_default: true }] });
  });
  await page.route(/\/api\/v1\/templates\/default$/, async (route) => {
    await fulfillJson(route, templateDetail);
  });
  await page.route(/\/api\/v1\/templates\/default\/layout-config$/, async (route) => {
    await fulfillJson(route, templateLayoutConfig);
  });
}

test("governance workbench first screens stay readable across desktop, tablet, and mobile", async ({ page }) => {
  await setupGovernanceApi(page);

  const routes = [
    { path: "/settings", heading: "配置工作台", text: "发布门禁处理队列" },
    { path: "/settings/translation-term-sets", heading: "翻译术语集", text: "草稿摘要" },
    { path: "/settings/word-page-styles/default", heading: "Word 页面样式配置", text: "变更摘要" },
  ] as const;

  for (const viewport of [
    { width: 1440, height: 920 },
    { width: 768, height: 1024 },
    { width: 375, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    for (const route of routes) {
      await page.goto(route.path);
      await expect(page.getByRole("heading", { name: route.heading })).toBeVisible();
      await expect(page.getByText(route.text)).toBeVisible();
      await expectNoPageHorizontalOverflow(page);
    }
  }
});

test("governance review, diff, and editor panels expose the shared template hierarchy", async ({ page }) => {
  await setupGovernanceApi(page);

  await page.setViewportSize({ width: 1440, height: 920 });

  await page.goto("/term-proposals?tab=review");
  await expect(page.getByRole("heading", { name: "术语建议" })).toBeVisible();
  await expect(page.getByText("批量审核").first()).toBeVisible();
  await page.getByRole("row", { name: /proposal_term_001/ }).getByRole("button", { name: "查看" }).click();
  await expect(page.getByText("审核详情")).toBeVisible();
  await expect(page.getByRole("heading", { name: "提议变更" })).toBeVisible();
  await expectNoPageHorizontalOverflow(page);

  await page.goto("/settings/translation-term-sets");
  await expect(page.getByRole("heading", { name: "翻译术语集" })).toBeVisible();
  await expect(page.getByText("差异 / 发布前检查")).toBeVisible();
  await expect(page.getByText("待审核建议兼容性")).toBeVisible();
  await expect(page.getByRole("heading", { name: "草稿词条" })).toBeVisible();
  await expectNoPageHorizontalOverflow(page);

  await page.goto("/settings/word-page-styles/default");
  await expect(page.getByRole("heading", { name: "Word 页面样式配置" })).toBeVisible();
  await expect(page.getByLabel("样式大类").getByRole("button", { name: /^标题/ })).toBeVisible();
  await expect(page.getByLabel("配置变更摘要")).toBeVisible();
  await expectNoPageHorizontalOverflow(page);
});
