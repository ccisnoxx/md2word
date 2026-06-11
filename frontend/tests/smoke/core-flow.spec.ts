import { expect, test, type Page } from "@playwright/test";

const actionStates = {
  download: { enabled: true, disabled_reason: null, retryable: false },
  retry: { enabled: false, disabled_reason: "只有 failed 文档任务允许重试。", retryable: false },
  cancel: { enabled: false, disabled_reason: "只有 pending、queued、running 任务允许取消。", retryable: false },
  archive: { enabled: true, disabled_reason: null, retryable: false },
  unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
  clone: { enabled: true, disabled_reason: null, retryable: false },
};

const documentJob = {
  id: "docjob_smoke_001",
  tenant_id: "tenant_default",
  company_id: "company_default",
  created_by: "user_operator",
  source_file_id: "file_source_smoke",
  source_job_id: null,
  mode: "direct_pdf_to_word",
  document_language: "auto",
  status: "succeeded",
  stage: "completed",
  progress: 100,
  template_version_id: "template_default",
  term_version_id: null,
  result_file_id: "file_result_smoke",
  mineru_raw_result_file_id: "file_mineru_raw_smoke",
  document_ir_file_id: "file_ir_smoke",
  image_asset_file_ids: [],
  debug_full_text_enabled: false,
  mineru_batch_id: "batch_smoke",
  mineru_data_id: "docjob_smoke_001",
  failed_stage: null,
  error_code: null,
  error_message: null,
  retry_count: 0,
  timeout_at: null,
  started_at: "2026-06-11T00:00:00Z",
  completed_at: "2026-06-11T00:01:00Z",
  canceled_at: null,
  archived_at: null,
  archived_by: null,
  translation_qa_status: "unreviewed",
  translation_qa_issue_type: null,
  translation_qa_note: null,
  translation_qa_reviewed_by: null,
  translation_qa_reviewed_at: null,
  request_snapshot: {
    source_file: { original_filename: "smoke.pdf" },
  },
  available_actions: actionStates,
  created_at: "2026-06-11T00:00:00Z",
  updated_at: "2026-06-11T00:01:00Z",
};

async function mockApi(page: Page): Promise<void> {
  await page.route("**/api/v1/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "smoke-token",
        token_type: "bearer",
        expires_in: 3600,
        user_id: "user_operator",
        username: "operator",
        role: "operator",
        roles: ["operator"],
        permissions: [
          "document_jobs:read",
          "document_jobs:create",
          "document_jobs:download",
          "document_jobs:retry",
          "document_jobs:cancel",
          "document_jobs:archive",
          "document_jobs:clone",
          "translation_qa:read",
          "translation_qa:write",
          "term_proposals:read",
          "term_proposals:create",
        ],
        tenant_id: "tenant_default",
        company_id: "company_default",
      }),
    });
  });
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user_operator",
        username: "operator",
        role: "operator",
        roles: ["operator"],
        permissions: [
          "document_jobs:read",
          "document_jobs:create",
          "document_jobs:download",
          "document_jobs:retry",
          "document_jobs:cancel",
          "document_jobs:archive",
          "document_jobs:clone",
          "translation_qa:read",
          "translation_qa:write",
          "term_proposals:read",
          "term_proposals:create",
        ],
        tenant_id: "tenant_default",
        company_id: "company_default",
        display_name: "Operator",
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_smoke_001/events", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: documentJob.id,
        items: [
          {
            id: "event_smoke_completed",
            job_id: documentJob.id,
            tenant_id: "tenant_default",
            company_id: "company_default",
            created_by: "worker",
            stage: "completed",
            level: "info",
            event_type: "stage_completed",
            message: "任务已完成。",
            payload: {},
            duration_ms: 1000,
            trace_id: "trace_smoke",
            created_at: "2026-06-11T00:01:00Z",
          },
        ],
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_smoke_001/files", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: documentJob.id,
        files: [
          {
            id: "file_result_smoke",
            tenant_id: "tenant_default",
            company_id: "company_default",
            job_id: documentJob.id,
            file_type: "generated_word",
            original_filename: "smoke.docx",
            storage_backend: "local_file",
            storage_path: "document-jobs/tenant_default/docjob_smoke_001/smoke.docx",
            object_key: null,
            media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes: 1024,
            checksum_sha256: null,
            status: "uploaded",
            retention_until: null,
            metadata: {},
            created_at: "2026-06-11T00:01:00Z",
            updated_at: "2026-06-11T00:01:00Z",
          },
        ],
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_smoke_001/callback-messages/summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: documentJob.id,
        status_counts: { processed: 1 },
        replayable_count: 0,
        oldest_replayable_age_seconds: 0,
        recent_problem_messages: [],
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_smoke_001/download-url", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: documentJob.id,
        file_id: "file_result_smoke",
        download_url: "/api/v1/files/file_result_smoke/content",
        expires_in_seconds: 600,
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_smoke_001", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(documentJob),
    });
  });
  await page.route("**/api/v1/document-jobs**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname !== "/api/v1/document-jobs") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [documentJob],
        page: 1,
        page_size: 20,
        total: 1,
        summary: { succeeded: 1 },
      }),
    });
  });
}

test("operator can log in and inspect the document job workbench", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();

  await expect(page).toHaveURL(/\/jobs$/);
  await expect(page.getByRole("heading", { name: "任务列表" })).toBeVisible();
  await expect(page.getByText("smoke.pdf")).toBeVisible();

  await page.getByRole("link", { name: "docjob_smoke_001" }).click();
  await expect(page).toHaveURL(/\/jobs\/docjob_smoke_001$/);
  await expect(page.getByRole("heading", { name: "任务详情" })).toBeVisible();
  await expect(page.getByText("结果文件 ID")).toBeVisible();
  await expect(page.getByRole("button", { name: "下载" })).toBeEnabled();
});

test("operator sees an explicit forbidden state for admin-only routes", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/jobs$/);

  await page.goto("/settings");
  await expect(page).toHaveURL(/\/forbidden/);
  await expect(page.getByRole("heading", { name: "当前账号没有访问权限" })).toBeVisible();
  await expect(page.getByText("settings:read")).toBeVisible();
});
