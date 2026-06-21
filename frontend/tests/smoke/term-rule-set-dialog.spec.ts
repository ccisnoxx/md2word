// File: frontend/tests/smoke/term-rule-set-dialog.spec.ts
// Purpose: Browser smoke coverage for the Term Rule Set draft-rule dialog viewport contract.
import { expect, test, type Page, type Route } from "@playwright/test";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";
const defaultSetId = "term_rule_default";

const category = {
  id: "cat_vehicle",
  code: "vehicle",
  name: "整车术语",
  priority: 10,
  enabled: true,
  description: "Vehicle terms",
  rule_count: 1,
  enabled_rule_count: 1,
};

const rule = {
  id: "rule_vin",
  category_id: category.id,
  category_code: category.code,
  category_name: category.name,
  source_term: "VIN",
  normalized_term: "vin",
  scope_type: "global",
  scope_id: null,
  current_version: 1,
  active: true,
  rule_mode: "segments",
  apply_scope: "both",
  case_sensitive: false,
  enabled: true,
  priority: 100,
  segments: [{ seq: 0, segment_text: "VIN", render_type: "plain" }],
  custom_html: null,
  custom_markdown: null,
  notes: "Vehicle identification number",
};

const versionRef = {
  ref: "default",
  version: "1",
  snapshot_hash: "hash_default",
  rule_count: 1,
  enabled_rule_count: 1,
};

const draftRef = {
  ref: "draft",
  version: "draft",
  snapshot_hash: "hash_draft",
  rule_count: 1,
  enabled_rule_count: 1,
};

const diffSummary = {
  added: 0,
  updated: 0,
  disabled: 0,
  removed: 0,
  unchanged: 1,
  total: 1,
};

async function setupTermRuleSetApi(page: Page): Promise<void> {
  await page.addInitScript((tokenKey) => {
    window.localStorage.setItem(tokenKey, "smoke-token");
  }, TOKEN_STORAGE_KEY);

  await page.route("**/api/v1/auth/me", async (route) => {
    await fulfillJson(route, {
      id: "user_admin",
      username: "admin",
      role: "admin",
      roles: ["admin"],
      permissions: ["settings:read", "term_proposals:read", "system:read"],
      tenant_id: "tenant_default",
      company_id: "company_default",
      display_name: "Admin",
    });
  });

  await page.route("**/api/v1/term-rule-categories", async (route) => {
    await fulfillJson(route, { items: [category] });
  });

  await page.route(/\/api\/v1\/term-rule-proposals(?:\?.*)?$/, async (route) => {
    await fulfillJson(route, { items: [], total: 0 });
  });

  await page.route(/\/api\/v1\/term-rule-sets(?:\/.*)?(?:\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();

    if (method === "GET" && path === "/api/v1/term-rule-sets") {
      await fulfillJson(route, {
        items: [
          {
            id: defaultSetId,
            default_version: "1",
            version_count: 1,
            rule_count: 1,
            enabled_rule_count: 1,
          },
        ],
      });
      return;
    }

    if (method === "GET" && path === `/api/v1/term-rule-sets/${defaultSetId}`) {
      await fulfillJson(route, {
        id: defaultSetId,
        default_version: "1",
        versions: [
          {
            term_rule_set_id: defaultSetId,
            version: "1",
            status: "published",
            rule_count: 1,
            enabled_rule_count: 1,
            snapshot_hash: "hash_default",
            is_default: true,
            published_by: "admin",
            publish_reason: "Smoke fixture",
            published_at: "2026-06-21T00:00:00Z",
          },
        ],
      });
      return;
    }

    if (method === "GET" && path === `/api/v1/term-rule-sets/${defaultSetId}/draft`) {
      await fulfillJson(route, draftResponse());
      return;
    }

    if (method === "GET" && path === `/api/v1/term-rule-sets/${defaultSetId}/draft/rules`) {
      await fulfillJson(route, { items: [rule], page: 1, page_size: 20, total: 1 });
      return;
    }

    if (method === "GET" && path === `/api/v1/term-rule-sets/${defaultSetId}/diff`) {
      await fulfillJson(route, {
        term_rule_set_id: defaultSetId,
        base_ref: versionRef,
        target_ref: draftRef,
        summary: diffSummary,
        items: [{ change_type: "unchanged", rule_id: rule.id, source_term: rule.source_term, category_id: category.id, changed_fields: [], before: rule, after: rule }],
      });
      return;
    }

    if (method === "GET" && path === `/api/v1/term-rule-sets/${defaultSetId}/preflight`) {
      await fulfillJson(route, {
        term_rule_set_id: defaultSetId,
        valid: true,
        blocking: false,
        base_ref: versionRef,
        draft_ref: draftRef,
        summary: { error_count: 0, warning_count: 0, conflict_count: 0, rule_count: 1, enabled_rule_count: 1 },
        errors: [],
        warnings: [],
        conflicts: [],
        diff_summary: diffSummary,
      });
      return;
    }

    await fulfillJson(route, { error_code: "not_found", message: "Unexpected smoke request" }, 404);
  });
}

for (const viewport of [
  { name: "desktop", width: 1440, height: 960 },
  { name: "tablet", width: 768, height: 900 },
  { name: "mobile", width: 375, height: 900 },
]) {
  test(`term rule draft dialog stays reachable at ${viewport.name}`, async ({ page }, testInfo) => {
    await setupTermRuleSetApi(page);
    await page.setViewportSize(viewport);

    await page.goto("/settings/term-rule-sets");

    await expect(page.getByRole("heading", { name: "术语规则集" })).toBeVisible();
    await page.getByRole("button", { name: "新增规则" }).click();

    const dialog = page.locator(".rule-dialog");
    await expect(dialog).toBeVisible();
    await expect(page.getByRole("button", { name: "保存" })).toBeVisible();
    await expect(page.locator(".rule-dialog-scroll")).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`term-rule-dialog-${viewport.name}.png`), fullPage: true });

    const metrics = await page.evaluate(() => {
      const dialog = document.querySelector<HTMLElement>(".rule-dialog");
      const body = document.querySelector<HTMLElement>(".rule-dialog .el-dialog__body");
      const scroll = document.querySelector<HTMLElement>(".rule-dialog-scroll");
      const footer = document.querySelector<HTMLElement>(".rule-dialog .el-dialog__footer");
      const dialogRect = dialog?.getBoundingClientRect();
      const footerRect = footer?.getBoundingClientRect();
      return {
        dialogMountedOutsideMain: Boolean(dialog && !dialog.closest("main")),
        bodyOverflow: body ? getComputedStyle(body).overflow : "",
        scrollOverflowY: scroll ? getComputedStyle(scroll).overflowY : "",
        scrollOwnsOverflow: scroll ? scroll.scrollHeight >= scroll.clientHeight : false,
        footerVisible: Boolean(
          footerRect &&
            footerRect.top >= 0 &&
            footerRect.bottom <= window.innerHeight &&
            footerRect.left >= 0 &&
            footerRect.right <= window.innerWidth,
        ),
        dialogWithinViewport: Boolean(
          dialogRect &&
            dialogRect.top >= 0 &&
            dialogRect.bottom <= window.innerHeight &&
            dialogRect.left >= 0 &&
            dialogRect.right <= window.innerWidth,
        ),
        documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        bodyOverflowX: document.body.scrollWidth - document.body.clientWidth,
      };
    });

    expect(metrics).toMatchObject({
      dialogMountedOutsideMain: true,
      bodyOverflow: "hidden",
      scrollOverflowY: "auto",
      scrollOwnsOverflow: true,
      footerVisible: true,
      dialogWithinViewport: true,
    });
    expect(metrics.documentOverflow).toBeLessThanOrEqual(1);
    expect(metrics.bodyOverflowX).toBeLessThanOrEqual(1);
  });
}

function draftResponse() {
  return {
    term_rule_set_id: defaultSetId,
    base_version: "1",
    rule_count: 1,
    enabled_rule_count: 1,
    yaml_text: "version: 2\nrules:\n  - source_term: VIN\n",
    snapshot_hash: "hash_draft",
  };
}

async function fulfillJson(route: Route, payload: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}
