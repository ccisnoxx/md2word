// File: frontend/tests/smoke/acceptance-center.spec.ts
// Purpose: Browser smoke coverage for the admin Acceptance Center page.
import { expect, test, type Page, type Route } from "@playwright/test";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";

const acceptanceRuns = [
  {
    id: "acceptance_p0_golden_sample_current",
    title: "P0 Golden Sample canonical suite",
    tier: "P0",
    status: "passed",
    environment: "hostdzire",
    source: "manual_summary:golden_sample_acceptance_report",
    report_path_or_url: "docs/testing/pdf-to-word-golden-sample-acceptance-report.md",
    started_at: null,
    finished_at: null,
    summary:
      "Historical starter summary: the Golden Sample report records the 2026-06-17 hostdzire admin signoff. Replace this starter summary with the latest run report before using Acceptance Center as release evidence.",
    blockers: [],
    warnings: [
      "starter_summary_historical_p0_signoff",
      "starter_summary_replace_with_latest_run_report_before_release",
    ],
    reviewer: null,
    decision: null,
    reviewed_at: null,
    review_note: null,
    updated_at: "2026-06-21T00:00:00Z",
  },
  {
    id: "acceptance_p1_translation_current",
    title: "P1 en2zh translation beta gate",
    tier: "P1",
    status: "unknown",
    environment: "hostdzire",
    source: "manual_summary:p1_translation_samples",
    report_path_or_url: "tests/fixtures/p1_translation_samples/README.md",
    started_at: null,
    finished_at: null,
    summary: "No formal P1 translation beta run is recorded yet.",
    blockers: ["p1_formal_regression_not_recorded"],
    warnings: ["requires_P1_TRANSLATION_FORMAL=1"],
    reviewer: null,
    decision: null,
    reviewed_at: null,
    review_note: null,
    updated_at: "2026-06-21T00:01:00Z",
  },
  {
    id: "acceptance_p2_online_gate_current",
    title: "P2 internal online gate",
    tier: "P2",
    status: "unknown",
    environment: "hostdzire",
    source: "manual_summary:online_first_validation_workflow",
    report_path_or_url: "docs/deploy/online-first-validation-workflow.md",
    started_at: null,
    finished_at: null,
    summary: "No P2 online gate report is recorded yet.",
    blockers: ["p2_online_gate_not_recorded"],
    warnings: ["aggregates_release_check_p0_p1_preflights"],
    reviewer: null,
    decision: null,
    reviewed_at: null,
    review_note: null,
    updated_at: "2026-06-21T00:02:00Z",
  },
];

async function setupAcceptanceApi(page: Page): Promise<{ reviewPayloads: unknown[]; upsertPayloads: unknown[] }> {
  const mockRuns = acceptanceRuns.map((run) => ({ ...run, blockers: [...run.blockers], warnings: [...run.warnings] }));
  const reviewPayloads: unknown[] = [];
  const upsertPayloads: unknown[] = [];

  await page.addInitScript((tokenKey) => {
    window.localStorage.setItem(tokenKey, "smoke-token");
  }, TOKEN_STORAGE_KEY);

  await page.route("**/api/v1/auth/me", async (route) => {
    await fulfillJson(route, {
      id: "user_admin",
      username: "admin",
      role: "admin",
      roles: ["admin"],
      permissions: ["system:read", "ops:read", "audit:read", "users:manage"],
      tenant_id: "tenant_default",
      company_id: "company_default",
      display_name: "Admin",
    });
  });

  await page.route("**/api/v1/acceptance/runs", async (route) => {
    if (route.request().method() === "POST") {
      const payload = route.request().postDataJSON();
      upsertPayloads.push(payload);
      const existingIndex = mockRuns.findIndex((candidate) => candidate.id === payload.id);
      const savedRun = {
        id: payload.id,
        title: payload.title,
        tier: payload.tier,
        status: payload.status,
        environment: payload.environment,
        source: payload.source,
        report_path_or_url: payload.report_path_or_url ?? null,
        started_at: payload.started_at ?? null,
        finished_at: payload.finished_at ?? null,
        summary: payload.summary ?? null,
        blockers: payload.blockers ?? [],
        warnings: payload.warnings ?? [],
        reviewer: null,
        decision: null,
        reviewed_at: null,
        review_note: null,
        updated_at: "2026-06-21T00:20:00Z",
      };
      if (existingIndex >= 0) {
        mockRuns.splice(existingIndex, 1, savedRun);
      } else {
        mockRuns.unshift(savedRun);
      }
      await fulfillJson(route, savedRun, existingIndex >= 0 ? 200 : 201);
      return;
    }
    await fulfillJson(route, { items: mockRuns, total: mockRuns.length });
  });

  await page.route("**/api/v1/acceptance/runs/latest-summary", async (route) => {
    await fulfillJson(route, {
      overall_status: "blocked",
      missing_tiers: [],
      blocker_count: 2,
      warning_count: 3,
      latest_reviewed_run: null,
      tiers: mockRuns.map((run) => ({
        tier: run.tier,
        run,
        missing: false,
        risk_level: run.blockers.length || run.status === "failed" ? "danger" : run.warnings.length || run.status === "unknown" ? "warning" : "success",
        blockers: run.blockers,
        warnings: run.warnings,
      })),
      generated_at: "2026-06-21T00:03:00Z",
    });
  });

  await page.route(/\/api\/v1\/acceptance\/runs\/(?!latest-summary$)([^/]+)$/, async (route) => {
    const runId = route.request().url().split("/").pop() || "";
    const run = mockRuns.find((candidate) => candidate.id === runId);
    await fulfillJson(route, run ?? { error_code: "not_found", message: "missing" }, run ? 200 : 404);
  });

  await page.route(/\/api\/v1\/acceptance\/runs\/([^/]+)\/review$/, async (route) => {
    const payload = route.request().postDataJSON();
    reviewPayloads.push(payload);
    const runId = route.request().url().split("/").at(-2) || "";
    const run = mockRuns.find((candidate) => candidate.id === runId) ?? mockRuns[0];
    await fulfillJson(route, {
      ...run,
      reviewer: "user_admin",
      decision: payload.decision,
      reviewed_at: "2026-06-21T00:10:00Z",
      review_note: payload.review_note ?? null,
      updated_at: "2026-06-21T00:10:00Z",
    });
  });

  return { reviewPayloads, upsertPayloads };
}

test("admin reviews an acceptance run", async ({ page }) => {
  const controls = await setupAcceptanceApi(page);

  await page.goto("/system-status/acceptance");

  await expect(page.getByRole("heading", { name: "验收中心" })).toBeVisible();
  await expect(page.getByText("P0 Golden Sample canonical suite")).toBeVisible();
  await expect(page.getByText("P1 en2zh translation beta gate")).toBeVisible();
  await expect(page.getByText("P2 internal online gate")).toBeVisible();

  await page.getByText("P0 Golden Sample canonical suite").click();
  await expect(page.getByText("这是历史 P0 签字摘要，不代表下一次发布的最新运行证据。")).toBeVisible();
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.getByRole("heading", { name: "P0 Golden Sample canonical suite" })).toBeHidden();

  await page.getByText("P1 en2zh translation beta gate").click();
  await expect(page.getByRole("heading", { name: "P1 en2zh translation beta gate" })).toBeVisible();
  await page.locator(".el-segmented__item").filter({ hasText: "需修改" }).click();
  await page.getByPlaceholder("记录通过依据、阻断原因或需补充证据。").fill("补齐 P1 formal run 后再验收。");
  await page.getByRole("button", { name: "提交复核" }).click();

  await expect.poll(() => controls.reviewPayloads.length).toBe(1);
  expect(controls.reviewPayloads[0]).toEqual({
    decision: "needs_changes",
    review_note: "补齐 P1 formal run 后再验收。",
  });
});

test("admin registers an acceptance run summary", async ({ page }) => {
  const controls = await setupAcceptanceApi(page);

  await page.goto("/system-status/acceptance");

  await page.getByRole("button", { name: "登记运行" }).click();
  await expect(page.getByRole("dialog", { name: "登记验收运行" })).toBeVisible();
  await page.getByLabel("运行 ID").fill("acceptance_p0_manual_smoke");
  await page.getByLabel("标题").fill("P0 Manual Smoke");
  await page.getByLabel("来源").fill("manual_import:smoke");
  await page.getByPlaceholder("tests/tmp/p1_translation_runs/run-1/report.md").fill("tests/tmp/smoke/report.md");
  await page.getByPlaceholder("记录本次运行结论、样本范围和签字状态。").fill("smoke run summary");
  await page.getByPlaceholder("每行一条 blocker").fill("manual_review_pending");
  await page.getByRole("button", { name: "保存运行" }).click();

  await expect.poll(() => controls.upsertPayloads.length).toBe(1);
  expect(controls.upsertPayloads[0]).toEqual({
    id: "acceptance_p0_manual_smoke",
    title: "P0 Manual Smoke",
    tier: "P0",
    status: "unknown",
    environment: "hostdzire",
    source: "manual_import:smoke",
    report_path_or_url: "tests/tmp/smoke/report.md",
    summary: "smoke run summary",
    blockers: ["manual_review_pending"],
    warnings: [],
  });
  await expect(page.getByText("P0 Manual Smoke")).toBeVisible();
});

for (const viewport of [
  { name: "desktop", width: 1440, height: 960 },
  { name: "tablet", width: 768, height: 900 },
  { name: "mobile", width: 375, height: 900 },
]) {
  test(`acceptance center renders without page overflow at ${viewport.name}`, async ({ page }, testInfo) => {
    await setupAcceptanceApi(page);
    await page.setViewportSize(viewport);

    await page.goto("/system-status/acceptance");

    await expect(page.getByRole("heading", { name: "验收中心" })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`acceptance-center-${viewport.name}.png`), fullPage: true });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1),
      )
      .toBe(true);
  });
}

async function fulfillJson(route: Route, payload: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}
