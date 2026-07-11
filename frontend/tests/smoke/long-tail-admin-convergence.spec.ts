// File: frontend/tests/smoke/long-tail-admin-convergence.spec.ts
// Purpose: Browser smoke coverage for the first convergence wave of low-frequency admin/config pages.
import { expect, test, type Page, type Route } from "@playwright/test";

import { expectNoPageHorizontalOverflow } from "./support/accessibility";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";

const aiProviderConfig = {
  backend: "openai_compatible",
  base_url: "https://api.example.com/v1",
  model: "deepseek-v4-flash",
  api_key_mask: "sk-****",
  api_key_configured: true,
  timeout_seconds: 120,
  max_output_tokens: 12000,
  updated_at: "2026-06-11T00:00:00Z",
  updated_by: "user_admin",
  source: "runtime_config",
};

const auditEvent = {
  audit_id: "audit_smoke_long_tail",
  actor_id: "user_admin",
  actor_role: "admin",
  action: "template.publish",
  target_type: "template",
  target_id: "default",
  reason: "publish default template",
  details: {
    template_id: "default",
    version: 1,
    action_scope: "publish",
  },
  trace_id: "trace_long_tail",
  created_at: "2026-06-11T00:05:00Z",
};

const userRow = {
  id: "user_operator",
  username: "operator",
  display_name: "Smoke Operator",
  role: "operator",
  status: "active",
  tenant_id: "tenant_default",
  company_id: "company_default",
  updated_at: "2026-06-11T00:00:00Z",
};

const templateListItem = {
  id: "default",
  name: "Datasheet Default",
  description: "默认模板",
  version: 1,
  is_default: true,
  downloadable: true,
  template: {
    file_name: "datasheet_template.docx",
  },
  layout_config: {
    file_name: "datasheet_template.yaml",
  },
};

const templateDetail = {
  id: "default",
  name: "Datasheet Default",
  is_default: true,
  downloadable: true,
  version: 1,
  template: {
    file_name: "datasheet_template.docx",
    size_bytes: 1024,
  },
};

const templateVersions = [
  {
    version: 1,
    status: "published",
    is_default: true,
    template: { file_name: "datasheet_template.docx" },
    layout_config: { file_name: "datasheet_template.yaml" },
    verification_job_id: "docjob_template_verify",
    verification_note: "smoke verification",
    published_at: "2026-06-11T00:00:00Z",
    publish_reason: "initial publish",
  },
];

const translationProfilesList = {
  items: [
    {
      id: "default",
      default_version: "2",
      target_language: "zh",
      domain: "electronics",
    },
  ],
};

const translationProfileDetail = {
  id: "default",
  default_version: "2",
  versions: [
    {
      version: "2",
      is_default: true,
      target_language: "zh",
      domain: "electronics",
      prompt_version: "v2",
      model: "deepseek-v4-flash",
      published_at: "2026-06-11T00:00:00Z",
    },
  ],
};

const translationProfileDraft = {
  snapshot_hash: "sha256:draft",
  target_language: "zh",
  domain: "electronics",
  prompt_version: "v2",
  model: "deepseek-v4-flash",
  max_pages_per_batch: 20,
  max_chars_per_batch: 60000,
};

const terminologyReleases = {
  items: [
    {
      id: "term-release-default",
      version: "3",
      status: "active",
      published_at: "2026-06-11T00:00:00Z",
      release_note: "current release",
      scope: { project: "electronics", language_pair: "en2zh", content_type: "datasheet" },
      translation_term_set: { resource_id: "electronics-default", version: "1" },
      term_rule_set: { resource_id: "electronics-default", version: "3" },
      validation_report: {
        blocking: false,
        summary: {
          error_count: 0,
          conflict_count: 0,
          warning_count: 1,
          publishable_term_count: 12,
        },
        errors: [],
        conflicts: [],
        warnings: [{ severity: "warning", code: "scope_overlap", message: "scope overlap warning" }],
      },
    },
  ],
};

const translationTermSetList = {
  items: [{ set_id: "electronics-default", language_pair: "en-zh", default_version: "1", version_count: 2 }],
};

const translationTermSetDetail = {
  set_id: "electronics-default",
  default_version: "1",
  versions: [{ version: "1", is_default: true, term_count: 12 }],
};

const termRuleSetList = {
  items: [{ id: "electronics-default", default_version: "3", version_count: 3 }],
};

const termRuleSetDetail = {
  id: "electronics-default",
  default_version: "3",
  versions: [{ version: "3", is_default: true, rule_count: 12 }],
};

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function setupLongTailAdminApi(page: Page): Promise<void> {
  await page.addInitScript((tokenKey) => {
    window.localStorage.setItem(tokenKey, "smoke-token");
  }, TOKEN_STORAGE_KEY);

  await page.route("**/api/v1/auth/me", async (route) => {
    await fulfillJson(route, {
      id: "user_admin",
      username: "admin",
      role: "admin",
      roles: ["admin"],
      permissions: ["settings:read", "settings:write", "audit:read", "users:manage"],
      tenant_id: "tenant_default",
      company_id: "company_default",
      display_name: "Admin",
    });
  });

  await page.route("**/api/v1/ai-provider-config", async (route) => {
    await fulfillJson(route, aiProviderConfig);
  });

  await page.route(/\/api\/v1\/audit-events(?:\?.*)?$/, async (route) => {
    await fulfillJson(route, {
      items: [auditEvent],
      page: 1,
      page_size: 25,
      total: 1,
    });
  });

  await page.route("**/api/v1/users", async (route) => {
    await fulfillJson(route, {
      items: [userRow],
      total: 1,
    });
  });

  await page.route("**/api/v1/templates", async (route) => {
    await fulfillJson(route, { items: [templateListItem] });
  });
  await page.route("**/api/v1/templates/default/layout-config", async (route) => {
    await fulfillJson(route, {
      template_id: "default",
      template_version_id: "default@1",
      version: 1,
      status: "published",
      is_default: true,
      active_template_version_id: "default@1",
      source_path: "resources/template_configs/datasheet_template.yaml",
      config_sha256: "sha256:layout",
      snapshot_hash: "sha256:published",
      meta: {
        schema_version: "template-config/v1",
        template_name: "数据手册模板",
        output_filename: "datasheet_template.docx",
      },
      config: {
        heading1: { font_size: 13 },
      },
      preview_samples: { heading1_text: "产品特性" },
      field_schema: {
        schema_version: "template-layout-editor/v1",
        meta: {},
        categories: [{ key: "heading", label: "标题", order: 0, groups: ["heading1"] }],
        group_meta: {
          heading1: { label: "一级标题", category: "标题", description: "维护一级标题样式。", order: 0 },
        },
        groups: {
          heading1: { font_size: { type: "number", label: "字号", unit: "pt" } },
        },
      },
    });
  });
  await page.route("**/api/v1/templates/default/versions", async (route) => {
    await fulfillJson(route, { items: templateVersions });
  });
  await page.route("**/api/v1/templates/default", async (route) => {
    await fulfillJson(route, { ...templateDetail, versions: templateVersions });
  });

  await page.route("**/api/v1/translation-profiles", async (route) => {
    await fulfillJson(route, translationProfilesList);
  });
  await page.route("**/api/v1/translation-profiles/default/draft", async (route) => {
    await fulfillJson(route, translationProfileDraft);
  });
  await page.route("**/api/v1/translation-profiles/default", async (route) => {
    await fulfillJson(route, translationProfileDetail);
  });

  await page.route("**/api/v1/terminology-releases", async (route) => {
    await fulfillJson(route, terminologyReleases);
  });
  await page.route("**/api/v1/translation-term-sets", async (route) => {
    await fulfillJson(route, translationTermSetList);
  });
  await page.route("**/api/v1/translation-term-sets/electronics-default", async (route) => {
    await fulfillJson(route, translationTermSetDetail);
  });
  await page.route("**/api/v1/term-rule-sets", async (route) => {
    await fulfillJson(route, termRuleSetList);
  });
  await page.route("**/api/v1/term-rule-sets/electronics-default", async (route) => {
    await fulfillJson(route, termRuleSetDetail);
  });
}

test("long-tail admin pages keep first-screen hierarchy aligned across desktop, tablet, and mobile", async ({ page }) => {
  await setupLongTailAdminApi(page);

  const routes = [
    { path: "/settings/ai-provider", heading: "AI 配置", text: "当前状态" },
    { path: "/system-status/audit-events", heading: "审计日志", text: "事件列表" },
    { path: "/system-status/users", heading: "用户管理", text: "内部用户" },
    { path: "/settings/templates", heading: "Word 模板文档", text: "模板列表" },
    { path: "/settings/templates/default", heading: "Word 模板文档", text: "职责边界" },
    { path: "/settings/translation-profiles", heading: "翻译配置", text: "草稿基础字段" },
    { path: "/settings/terminology-releases", heading: "术语发布", text: "新增发布向导" },
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

test("long-tail admin drawers and dialogs keep key actions reachable", async ({ page }) => {
  await setupLongTailAdminApi(page);
  await page.setViewportSize({ width: 375, height: 900 });

  await page.goto("/system-status/audit-events");
  await page.getByRole("button", { name: /查看 3/ }).click();
  await expect(page.getByRole("heading", { name: "结构化审计详情" })).toBeVisible();
  await expect(page.getByText("Top-level fields")).toBeVisible();
  await expectNoPageHorizontalOverflow(page);

  await page.goto("/system-status/users");
  await page.getByRole("button", { name: "编辑" }).click();
  await expect(page.getByRole("heading", { name: "编辑用户" })).toBeVisible();
  await expect(page.getByRole("button", { name: "保存" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "编辑用户" })).toBeHidden();
});
