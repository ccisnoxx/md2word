// 文件：frontend/tests/smoke/document-review-publish.spec.ts
// 用途：Phase 2 浏览器烟雾验证，覆盖 direct/翻译三栏复核工作台、预览降级、发布前清单与幂等发布/新代对账、就地提议术语抽屉及多视口深浅主题。
import { expect, test, type Page, type Route } from "@playwright/test";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";
const THEME_STORAGE_KEY = "md2word.frontend.theme_mode";
const SHA_A = "a".repeat(64);
const SHA_B = "b".repeat(64);
const SHA_C = "c".repeat(64);
const SNAPSHOT_ID = "d".repeat(64);

// 1x1 透明 PNG 二进制用于模拟预览页与表格参考图。
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

const baseSource = {
  generation: 1,
  ir_file_id: "file_ir_1",
  result_file_id: "file_docx_1",
  result_sha256: `sha256:${SHA_A}`,
  file_review_source_revision: 2,
  receipt_sha256: `sha256:${SHA_B}`,
};

function makeActions(overrides: Record<string, unknown> = {}) {
  return {
    download: { enabled: true, disabled_reason: null, retryable: false, classification: "internal_only" },
    retry: { enabled: false, disabled_reason: "当前状态不允许重试。", retryable: false },
    cancel: { enabled: false, disabled_reason: "终态不可取消。", retryable: false },
    archive: { enabled: true, disabled_reason: null, retryable: false },
    unarchive: { enabled: false, disabled_reason: null, retryable: false },
    clone: { enabled: true, disabled_reason: null, retryable: false },
    delete: { enabled: false, disabled_reason: null, retryable: false },
    publish: {
      enabled: false,
      eligible: false,
      disabled_reason: "文档尚未复核。",
      disabled_reason_code: "review_status_unreviewed",
      disabled_reasons: [{ code: "review_status_unreviewed", message: "文档尚未复核。" }],
    },
    new_generation: { enabled: true, disabled_reason: null, retryable: false },
    ...overrides,
  };
}

function makeJob(overrides: Record<string, unknown> = {}) {
  return {
    id: "docjob_review_direct",
    tenant_id: "tenant_default",
    company_id: "company_default",
    created_by: "user_admin",
    source_file_id: "file_pdf_1",
    source_job_id: null,
    mode: "direct_pdf_to_word",
    document_language: "en",
    status: "succeeded",
    stage: "completed",
    progress: 100,
    template_version_id: "tpl_default@v1",
    term_version_id: "tset_en2zh@v1",
    result_file_id: "file_docx_1",
    mineru_raw_result_file_id: null,
    document_ir_file_id: "file_ir_1",
    source_document_ir_file_id: "file_ir_1",
    image_asset_file_ids: [],
    debug_full_text_enabled: false,
    mineru_batch_id: null,
    mineru_data_id: null,
    failed_stage: null,
    error_code: null,
    error_message: null,
    retry_count: 1,
    quality_status: "warning",
    review_status: "unreviewed",
    delivery_status: "internal_draft",
    timeout_at: null,
    started_at: "2026-11-27T10:00:00Z",
    completed_at: "2026-11-27T10:02:00Z",
    canceled_at: null,
    archived_at: null,
    archived_by: null,
    deleted_at: null,
    deleted_by: null,
    delete_reason: null,
    translation_qa_status: "unreviewed",
    translation_qa_issue_type: null,
    translation_qa_note: null,
    translation_qa_reviewed_by: null,
    translation_qa_reviewed_at: null,
    request_snapshot: {
      source_file: { original_filename: "OPA228_Datasheet.pdf" },
      resources: {
        template: { resource_id: "tpl_default", version: "v1" },
        term_rule_set: { resource_id: "sym_default", version: "v1" },
        translation_term_set: { set_id: "tset_en2zh", version: "v1" },
      },
    },
    available_actions: makeActions(),
    created_at: "2026-11-27T10:00:00Z",
    updated_at: "2026-11-27T10:02:00Z",
    ...overrides,
  };
}

function fulfillJson(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function seedAuth(page: Page, role: "admin" | "operator" = "admin") {
  await page.addInitScript(
    ({ tokenKey }) => {
      window.localStorage.setItem(tokenKey, "smoke_phase2_token");
    },
    { tokenKey: TOKEN_STORAGE_KEY },
  );
  await page.route("**/api/v1/auth/me", (route) =>
    fulfillJson(route, {
      id: `user_${role}`,
      username: role,
      display_name: role === "admin" ? "管理员" : "操作员",
      role,
      roles: [role],
      permissions: [
        "document_jobs:read",
        "document_jobs:create",
        "translation_qa:read",
        "translation_qa:write",
        "term_proposals:read",
        "term_proposals:create",
        ...(role === "admin" ? ["settings:read", "settings:write", "term_proposals:review"] : []),
      ],
      tenant_id: "tenant_default",
      company_id: "company_default",
    }),
  );
}

test.describe("Phase 2 统一文档复核、发布闭环与就地术语提议", () => {
  test("direct 模式三栏复核：语义表确认勾选、表格参考图灯箱、复核提交与多视口深色主题无溢出", async ({ page }) => {
    test.setTimeout(60_000);
    await seedAuth(page, "admin");

    const job = makeJob({ id: "docjob_review_direct", mode: "direct_pdf_to_word" });
    let submittedReviewBody: Record<string, unknown> | null = null;
    let currentReviewStatus = "unreviewed";

    await page.route("**/api/v1/document-jobs/docjob_review_direct", (route) =>
      fulfillJson(route, { ...job, review_status: currentReviewStatus }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/events", (route) =>
      fulfillJson(route, { items: [] }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/files", (route) =>
      fulfillJson(route, { files: [] }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/callback-messages/summary", (route) =>
      fulfillJson(route, { total: 0, problem_count: 0, statuses: {} }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/quality", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_direct",
        source: baseSource,
        states: {
          execution_status: "succeeded",
          quality_status: "warning",
          review_status: currentReviewStatus,
          delivery_status: "internal_draft",
        },
        summary: { quality_flags: [], layout_quality_flags: [], blocking_quality_flags: [], unknown_flag_count: 0 },
        producers: { items: [], unknown_producer_count: 0 },
        review: {
          status: currentReviewStatus,
          current_record_id: currentReviewStatus === "approved" ? "rev_1" : null,
          sequence: currentReviewStatus === "approved" ? 1 : 0,
          issue_type: null,
          note: null,
          reviewed_by: null,
          reviewed_at: null,
          binding: null,
          validity_reason: currentReviewStatus === "approved" ? null : "table_semantics_confirmation_required",
          quality: null,
        },
        available_actions: makeActions(),
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/quality/tables**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_direct",
        source: baseSource,
        availability: "available",
        reason_code: null,
        report: {
          schema_version: "table-evidence/v1",
          report_file_id: "file_tbl_report",
          report_sha256: SHA_C,
          coverage: "complete",
          status: "warning",
          counts: {},
        },
        items: [
          {
            table_id: "tbl_04",
            logical_group_id: "lg_04",
            member_block_ids: ["blk_04"],
            anchor_block_id: "blk_04",
            source_spans: [],
            source_grid: { rows: 14, columns: 6, header_rows: [0], rowspan_count: 1, colspan_count: 2 },
            references: [],
            outputs: [],
            placeholders: [],
            render_state: "native",
            flags: [],
            unknown_flag_count: 0,
            status: "warning",
            value_column_findings: [
              {
                finding_id: "find_1",
                code: "table_semantics:value_column_span_ambiguous",
                fragment_id: "frag_1",
                cell_id: "cell_1",
                source_page_index: 2,
                source_row_index: 3,
                column: 2,
                end_column: 4,
                columns: [
                  { column: 2, label: "MIN", group_start_column: 2 },
                  { column: 3, label: "TYP", group_start_column: 2 },
                ],
                value: "75",
                unit: "uV",
                manual_review_required: true,
              },
            ],
            unresolved_value_columns: [],
          },
        ],
        next_cursor: null,
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/quality/pages**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_direct",
        source: baseSource,
        availability: "available",
        reason_code: null,
        report: {
          schema_version: "page-quality/v1",
          analyzer_version: "analyzer/v1",
          id: "pq_1",
          run_sha256: SHA_A,
          generation: 1,
          preview_run_id: "prev_1",
          revision: 1,
          attempt: 1,
          manifest_file_id: "file_m",
          profile_id: "default",
          profile_sha256: `sha256:${SHA_A}`,
          page_count: 4,
          evaluation_state: "complete",
          quality_status: "passed",
          reason_code: null,
          manual_checks: [],
          coverage: { clipping: { checked: 4, not_checked: 0 } },
          counts: {},
        },
        items: [
          {
            preview_page_index: 3,
            rules: { clipping: { rule_version: "v1", checked: true, reason_code: null, metrics: {}, units: {} } },
            flags: [],
            unknown_flag_count: 0,
            manual_checks: [],
            block_candidates: [],
          },
        ],
        next_cursor: null,
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/preview**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_direct",
        source: baseSource,
        status: "succeeded",
        availability: "available",
        reason_code: null,
        run: null,
        pdf_file_id: "file_preview_pdf",
        page_count: 4,
        items: [
          { file_id: "prev_p0", page_index: 0, width: 800, height: 1130 },
          { file_id: "prev_p3", page_index: 3, width: 800, height: 1130 },
        ],
        next_cursor: null,
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/download-url**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_direct",
        file_id: "prev_p3",
        download_url: "/mock-assets/preview-page.png",
        expires_at: "2026-12-01T00:00:00Z",
        file: { id: "prev_p3", original_filename: "preview-page.png", file_type: "image_asset", status: "uploaded" },
        classification: "internal_only",
      }),
    );
    await page.route("**/mock-assets/preview-page.png", (route) =>
      route.fulfill({ status: 200, contentType: "image/png", body: TINY_PNG }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/table-references/asset_1/content**", (route) =>
      route.fulfill({ status: 200, contentType: "image/png", body: TINY_PNG }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/table-references", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_direct",
        generation: 1,
        ir_file_id: "file_ir_1",
        evidence_status: "registered",
        items: [
          {
            block_id: "blk_04",
            fragment_id: "frag_1",
            logical_group_id: "lg_04",
            page_index: 2,
            bbox: null,
            asset_id: "asset_1",
            file_id: "file_ref_1",
            source_status: "valid",
            availability: "available",
            mime_type: "image/png",
            checksum_sha256: `sha256:${SHA_A}`,
            size_bytes: 512,
            warning_codes: [],
            display_supported: true,
            content_path: "/api/v1/document-jobs/docjob_review_direct/table-references/asset_1/content?generation=1&ir_file_id=file_ir_1",
          },
        ],
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/review/blocks/blk_04**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_direct",
        source: baseSource,
        content_snapshot: {
          snapshot_id: SNAPSHOT_ID,
          source_pdf_file_id: "file_pdf_1",
          source_ir_file_id: "file_ir_1",
          final_ir_file_id: null,
          preview_run_id: "prev_1",
          preview_revision: 1,
          preview_attempt: 1,
          basis: "final",
          source_content: { availability: "available", reason_code: null },
          target_content: { availability: "available", reason_code: null },
          translation: { availability: "not_applicable", reason_code: null },
          preview: { availability: "available", reason_code: null },
          mapping: { availability: "available", reason_code: null },
          tables: { availability: "available", reason_code: null },
        },
        block: {
          block_id: "blk_04",
          order: 4,
          block_type: "table",
          source_type: "table",
          excerpt: "Electrical Characteristics",
          source_spans: [{ source_page_index: 2, bbox: null, page_width: null, page_height: null, coordinate_unit: "mineru", coordinate_verified: false, reason_code: null, fragment_id: "frag_1" }],
          location: { kind: "single_page", preview_page_index: 3, confidence: "high", reason_code: null, bookmark_label: null, disposition: "rendered", representative_block_id: null, fallback_page_index: null, fallback_block_id: null, provenance_status: "verified_ir205" },
          flags: [{ code: "table_continuation_uncertain", severity: "warning", table_id: "tbl_04" }],
          table_ids: ["tbl_04"],
        },
        items: [
          { kind: "text", side: "target", field: "caption", offset: 0, text: "Table 1. Electrical Characteristics", truncated: false },
        ],
        next_cursor: null,
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/review/blocks**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_direct",
        source: baseSource,
        content_snapshot: {
          snapshot_id: SNAPSHOT_ID,
          source_pdf_file_id: "file_pdf_1",
          source_ir_file_id: "file_ir_1",
          final_ir_file_id: null,
          preview_run_id: "prev_1",
          preview_revision: 1,
          preview_attempt: 1,
          basis: "final",
          source_content: { availability: "available", reason_code: null },
          target_content: { availability: "available", reason_code: null },
          translation: { availability: "not_applicable", reason_code: null },
          preview: { availability: "available", reason_code: null },
          mapping: { availability: "available", reason_code: null },
          tables: { availability: "available", reason_code: null },
        },
        availability: "available",
        reason_code: null,
        total: 1,
        items: [
          {
            block_id: "blk_04",
            order: 4,
            block_type: "table",
            source_type: "table",
            excerpt: "Electrical Characteristics",
            source_spans: [{ source_page_index: 2, bbox: null, page_width: null, page_height: null, coordinate_unit: "mineru", coordinate_verified: false, reason_code: null, fragment_id: "frag_1" }],
            location: { kind: "single_page", preview_page_index: 3, confidence: "high", reason_code: null, bookmark_label: null, disposition: "rendered", representative_block_id: null, fallback_page_index: null, fallback_block_id: null, provenance_status: "verified_ir205" },
            flags: [{ code: "table_continuation_uncertain", severity: "warning", table_id: "tbl_04" }],
            table_ids: ["tbl_04"],
          },
        ],
        next_cursor: null,
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_direct/review", async (route) => {
      if (route.request().method() === "PATCH") {
        submittedReviewBody = JSON.parse(route.request().postData() || "{}") as Record<string, unknown>;
        currentReviewStatus = String(submittedReviewBody.status || "approved");
        return fulfillJson(route, {
          job_id: "docjob_review_direct",
          accepted_record_id: "rev_1",
          accepted_sequence: 1,
          source: baseSource,
          review: {
            status: currentReviewStatus,
            current_record_id: "rev_1",
            sequence: 1,
            issue_type: submittedReviewBody.issue_type ?? null,
            note: submittedReviewBody.note ?? null,
            reviewed_by: "admin",
            reviewed_at: "2026-11-27T11:00:00Z",
            binding: {
              ...baseSource,
              binding_state: "verified",
              acknowledged_table_semantics_report_sha256: submittedReviewBody.acknowledged_table_semantics_report_sha256,
            },
            validity_reason: null,
            quality: null,
          },
          available_actions: makeActions({ publish: { enabled: true, eligible: true, disabled_reason: null } }),
        });
      }
      return route.continue();
    });

    // 从详情页点击「进入三栏复核」跳转至独立复核工作台
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/jobs/docjob_review_direct");
    await expect(page.getByRole("heading", { name: "OPA228_Datasheet.pdf" })).toBeVisible();
    await page.locator(".detail-header").getByRole("button", { name: "进入三栏复核" }).click();
    await expect(page).toHaveURL(/\/jobs\/docjob_review_direct\/review/);

    // direct 模式翻译隔离：不出现「从此段提议术语」按钮，展示表格参考图与数值列发现
    await expect(page.getByText("Table 1. Electrical Characteristics")).toBeVisible();
    await expect(page.getByRole("button", { name: "从此段提议术语" })).toHaveCount(0);
    await expect(page.getByText("疑似数值跨列归属发现（1 处，批准前需人工确认）")).toBeVisible();
    await expect(page.getByRole("img", { name: "Word 预览第 4 页" })).toBeVisible();

    // 点击表格参考图缩略图打开灯箱
    await page.getByRole("button", { name: "放大查看表格参考图 frag_1" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");

    // 切换状态为已批准：未勾选语义表确认框前按钮禁用；勾选后提交附带 report_sha256
    const statusSelect = page.locator(".signoff-panel .el-select").first();
    await statusSelect.click();
    await page.locator(".el-select-dropdown__item", { hasText: "已批准" }).click();
    const submitBtn = page.getByRole("button", { name: "提交复核" });
    await expect(submitBtn).toBeDisabled();

    await page.locator(".semantics-ack-box .el-checkbox").click();
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    await expect.poll(() => submittedReviewBody?.acknowledged_table_semantics_report_sha256).toBe(SHA_C);
    await expect(page.getByRole("button", { name: "前往发布与交付" })).toBeVisible();

    // 校验 4 视口无横向溢出 + 深色主题
    await page.evaluate((themeKey) => {
      window.localStorage.setItem(themeKey, "dark");
      document.documentElement.dataset.theme = "dark";
    }, THEME_STORAGE_KEY);

    for (const width of [1440, 1024, 768, 375]) {
      await page.setViewportSize({ width, height: 860 });
      await page.waitForTimeout(100);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `viewport ${width}px should not horizontally overflow`).toBeLessThanOrEqual(2);
    }
  });

  test("翻译模式复核预览降级与就地提议术语抽屉（工作台 + 传统 QA 页均不离页）", async ({ page }) => {
    test.setTimeout(60_000);
    await seedAuth(page, "operator");

    const transJob = makeJob({ id: "docjob_review_trans", mode: "en2zh_pdf_to_word", document_language: "en" });
    const submittedProposals: Array<Record<string, unknown>> = [];

    await page.route("**/api/v1/document-jobs/docjob_review_trans", (route) => fulfillJson(route, transJob));
    await page.route("**/api/v1/document-jobs/docjob_review_trans/quality", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_trans",
        source: baseSource,
        states: { execution_status: "succeeded", quality_status: "passed", review_status: "unreviewed", delivery_status: "internal_draft" },
        summary: { quality_flags: [], layout_quality_flags: [], blocking_quality_flags: [], unknown_flag_count: 0 },
        producers: { items: [], unknown_producer_count: 0 },
        review: { status: "unreviewed", current_record_id: null, sequence: 0, issue_type: null, note: null, reviewed_by: null, reviewed_at: null, binding: null, validity_reason: null, quality: null },
        available_actions: makeActions(),
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_trans/quality/tables**", (route) =>
      fulfillJson(route, { job_id: "docjob_review_trans", source: baseSource, availability: "available", reason_code: null, report: null, items: [], next_cursor: null }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_trans/quality/pages**", (route) =>
      fulfillJson(route, { job_id: "docjob_review_trans", source: baseSource, availability: "disabled", reason_code: "preview_disabled", report: null, items: [], next_cursor: null }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_trans/preview**", (route) =>
      fulfillJson(route, { job_id: "docjob_review_trans", source: baseSource, status: "disabled", availability: "disabled", reason_code: "preview_disabled", run: null, pdf_file_id: null, page_count: null, items: [], next_cursor: null }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_trans/table-references", (route) =>
      fulfillJson(route, { job_id: "docjob_review_trans", generation: 1, ir_file_id: "file_ir_1", evidence_status: "registered", items: [] }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_trans/review/blocks/blk_t1**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_trans",
        source: baseSource,
        content_snapshot: {
          snapshot_id: SNAPSHOT_ID,
          source_pdf_file_id: "file_pdf_1",
          source_ir_file_id: "file_ir_src",
          final_ir_file_id: "file_ir_1",
          preview_run_id: null,
          preview_revision: null,
          preview_attempt: null,
          basis: "final",
          source_content: { availability: "available", reason_code: null },
          target_content: { availability: "available", reason_code: null },
          translation: { availability: "available", reason_code: null },
          preview: { availability: "disabled", reason_code: "preview_disabled" },
          mapping: { availability: "unavailable", reason_code: "preview_disabled" },
          tables: { availability: "available", reason_code: null },
        },
        block: {
          block_id: "blk_t1",
          order: 1,
          block_type: "paragraph",
          source_type: "text",
          excerpt: "Input Offset Voltage is 75 uV max.",
          source_spans: [{ source_page_index: 0, bbox: null, page_width: null, page_height: null, coordinate_unit: "mineru", coordinate_verified: false, reason_code: null, fragment_id: null }],
          location: { kind: "unavailable", preview_page_index: null, confidence: "none", reason_code: "preview_disabled", bookmark_label: null, disposition: "rendered", representative_block_id: null, fallback_page_index: null, fallback_block_id: null, provenance_status: "unavailable" },
          flags: [],
          table_ids: [],
        },
        items: [
          { kind: "text", side: "source", field: "text", offset: 0, text: "Input Offset Voltage is 75 uV max.", truncated: false },
          { kind: "text", side: "target", field: "text", offset: 0, text: "输入失调电压最大值为 75 uV。", truncated: false },
          { kind: "term", side: "shared", field: "term", offset: 0, truncated: false, term: { unit_id: "u1", batch_id: "b1", source_term: "Input Offset Voltage", target_term: "输入失调电压", version: "v1" } },
          { kind: "batch", side: "shared", field: "batch", offset: 0, truncated: false, batch: { scope: "batch", batch_id: "b1", attempt: 1, status: "succeeded", provider_model: "gpt-4o", integrity_status: "passed", expected_item_count: 1, checked_item_count: 1, expected_token_counts: { formula: 0, literal_placeholder: 0, address: 0, bit_field: 0, model: 1, standard: 0, version: 0, signal: 0, quantity: 1, unit: 1, url: 0, email: 0, number: 1, symbol: 0, technical_literal: 0 }, actual_token_counts: { formula: 0, literal_placeholder: 0, address: 0, bit_field: 0, model: 1, standard: 0, version: 0, signal: 0, quantity: 1, unit: 1, number: 1, symbol: 0, technical_literal: 0 } } },
        ],
        next_cursor: null,
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_trans/review/blocks**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_trans",
        source: baseSource,
        content_snapshot: {
          snapshot_id: SNAPSHOT_ID,
          source_pdf_file_id: "file_pdf_1",
          source_ir_file_id: "file_ir_src",
          final_ir_file_id: "file_ir_1",
          preview_run_id: null,
          preview_revision: null,
          preview_attempt: null,
          basis: "final",
          source_content: { availability: "available", reason_code: null },
          target_content: { availability: "available", reason_code: null },
          translation: { availability: "available", reason_code: null },
          preview: { availability: "disabled", reason_code: "preview_disabled" },
          mapping: { availability: "unavailable", reason_code: "preview_disabled" },
          tables: { availability: "available", reason_code: null },
        },
        availability: "available",
        reason_code: null,
        total: 1,
        items: [
          {
            block_id: "blk_t1",
            order: 1,
            block_type: "paragraph",
            source_type: "text",
            excerpt: "Input Offset Voltage is 75 uV max.",
            source_spans: [{ source_page_index: 0, bbox: null, page_width: null, page_height: null, coordinate_unit: "mineru", coordinate_verified: false, reason_code: null, fragment_id: null }],
            location: { kind: "unavailable", preview_page_index: null, confidence: "none", reason_code: "preview_disabled", bookmark_label: null, disposition: "rendered", representative_block_id: null, fallback_page_index: null, fallback_block_id: null, provenance_status: "unavailable" },
            flags: [],
            table_ids: [],
          },
        ],
        next_cursor: null,
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_trans/translation-qa**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_trans",
        available: true,
        availability_reason: null,
        qa: { status: "unreviewed", issue_type: null, note: null, reviewed_by: null, reviewed_at: null },
        artifacts: { document_ir_file_id: "file_ir_1", ai_call_log_file_ids: [], ai_debug_archive_file_ids: [] },
        summary: { final_segment_count: 1, returned_segment_count: 1, quality_flags: [], ai_call_count: 1, ai_call_statuses: { succeeded: 1 }, term_trace_count: 0, debug_full_text_enabled: false, source_comparison_available: true, source_comparison_reason: null },
        segments: [
          { id: "seg_1", block_id: "blk_t1", page_index: 0, order: 1, block_type: "paragraph", field: "text", index: 0, source_text: "Input Offset Voltage is 75 uV max.", ai_translation_text: "输入失调电压最大值为 75 uV。", final_text: "输入失调电压最大值为 75 uV。", source_available: true },
        ],
        term_traces: [],
        ai_calls: [],
      }),
    );
    await page.route("**/api/v1/translation-term-proposals", async (route) => {
      const payload = JSON.parse(route.request().postData() || "{}") as Record<string, unknown>;
      submittedProposals.push(payload);
      return fulfillJson(route, { id: `prop_${submittedProposals.length}`, status: "pending", changes: payload.changes }, 201);
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/jobs/docjob_review_trans/review");

    // 预览未启用降级提示与源/译对照展示
    await expect(page.getByText("当前环境未开启 Word 页级预览生成功能。")).toBeVisible();
    await expect(page.getByText("输入失调电压最大值为 75 uV。")).toBeVisible();
    await expect(page.getByText("器件型号：1/1")).toBeVisible();

    // 在三栏复核台就地提议术语并留在当前路由
    await page.getByRole("button", { name: "从此段提议术语" }).click();
    const drawer = page.locator(".inline-term-proposal-drawer");
    await expect(drawer).toBeVisible();
    await drawer.getByPlaceholder(/输入需要统一的原文术语/).fill("Slew Rate");
    await drawer.getByPlaceholder(/输入标准目标译文/).fill("压摆率");
    await drawer.getByRole("button", { name: "提交术语建议" }).click();
    await expect.poll(() => submittedProposals.length).toBe(1);
    expect(submittedProposals[0].language_pair).toBe("en2zh");
    await expect(page).toHaveURL(/\/jobs\/docjob_review_trans\/review/);

    // 传统翻译 QA 页同样支持就地提议术语抽屉
    await page.goto("/jobs/docjob_review_trans/translation-qa");
    await page.getByRole("button", { name: "从此段提议术语" }).click();
    await expect(drawer).toBeVisible();
    await drawer.getByPlaceholder(/输入需要统一的原文术语/).fill("Common-Mode Rejection Ratio");
    await drawer.getByPlaceholder(/输入标准目标译文/).fill("共模抑制比");
    await drawer.getByRole("button", { name: "提交术语建议" }).click();
    await expect.poll(() => submittedProposals.length).toBe(2);
    await expect(page).toHaveURL(/\/jobs\/docjob_review_trans\/translation-qa/);
  });

  test("详情页发布与交付闭环：preflight_checks 阻断->开放、503 幂等重放发布、最终件下载与 Admin 新代对账", async ({ page }) => {
    test.setTimeout(60_000);
    await seedAuth(page, "admin");

    const job = makeJob({ id: "docjob_pub_admin", review_status: "approved", quality_status: "passed" });
    let publishEnabled = false;
    let publishAttempts = 0;
    const publishRequestIds: string[] = [];
    let publishedRecords: Array<Record<string, unknown>> = [];
    let newGenAttempts = 0;
    let newGenUuid = "";

    const pubExpectedSource = {
      ...baseSource,
      review_record_id: "rev_1",
      review_sequence: 1,
      preview_run_id: "prev_1",
      preview_revision: 1,
      quality_summary_sha256: `sha256:${SHA_C}`,
    };

    await page.route("**/api/v1/document-jobs/docjob_pub_admin", (route) =>
      fulfillJson(route, {
        ...job,
        delivery_status: publishedRecords.length ? "published" : publishEnabled ? "ready_to_publish" : "internal_draft",
        available_actions: makeActions({
          publish: publishEnabled
            ? { enabled: true, eligible: true, disabled_reason: null }
            : { enabled: false, eligible: false, disabled_reason: "文档发布写入当前已停用。", disabled_reason_code: "publication_disabled", disabled_reasons: [{ code: "publication_disabled", message: "文档发布写入当前已停用。" }] },
        }),
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_pub_admin/events", (route) => fulfillJson(route, { items: [] }));
    await page.route("**/api/v1/document-jobs/docjob_pub_admin/files", (route) => fulfillJson(route, { files: [] }));
    await page.route("**/api/v1/document-jobs/docjob_pub_admin/callback-messages/summary", (route) =>
      fulfillJson(route, { total: 0, problem_count: 0, statuses: {} }),
    );
    await page.route("**/api/v1/document-jobs/docjob_pub_admin/review/blocks**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_pub_admin",
        source: baseSource,
        content_snapshot: {
          snapshot_id: SNAPSHOT_ID,
          source_pdf_file_id: "file_pdf_1",
          source_ir_file_id: "file_ir_1",
          final_ir_file_id: null,
          preview_run_id: "prev_1",
          preview_revision: 1,
          preview_attempt: 1,
          basis: "final",
          source_content: { availability: "available", reason_code: null },
          target_content: { availability: "available", reason_code: null },
          translation: { availability: "not_applicable", reason_code: null },
          preview: { availability: "available", reason_code: null },
          mapping: { availability: "available", reason_code: null },
          tables: { availability: "available", reason_code: null },
        },
        availability: "available",
        reason_code: null,
        total: 0,
        items: [],
        next_cursor: null,
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_pub_admin/publications", (route) =>
      fulfillJson(route, {
        job_id: "docjob_pub_admin",
        expected_source: pubExpectedSource,
        preflight_checks: [
          { code: "review", status: "passed", reason_code: null, message: "检查通过。" },
          publishEnabled
            ? { code: "publication_write", status: "passed", reason_code: null, message: "检查通过。" }
            : { code: "publication_write", status: "blocked", reason_code: "publication_disabled", message: "文档发布写入当前已停用。" },
        ],
        items: publishedRecords,
        download_actions: Object.fromEntries(publishedRecords.map((item) => [String(item.publication_id), { enabled: true }])),
        available_actions: makeActions({
          publish: publishEnabled && !publishedRecords.length
            ? { enabled: true, eligible: true, disabled_reason: null }
            : { enabled: false, eligible: false, disabled_reason: publishedRecords.length ? "该结果已发布，不能重复发布。" : "文档发布写入当前已停用。", disabled_reason_code: publishedRecords.length ? "already_published" : "publication_disabled", disabled_reasons: [{ code: publishedRecords.length ? "already_published" : "publication_disabled", message: publishedRecords.length ? "该结果已发布，不能重复发布。" : "文档发布写入当前已停用。" }] },
          new_generation: { enabled: true, disabled_reason: null },
        }),
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_pub_admin/publish", async (route) => {
      publishAttempts += 1;
      const body = JSON.parse(route.request().postData() || "{}") as Record<string, unknown>;
      publishRequestIds.push(String(body.request_id || ""));
      if (publishAttempts === 1) {
        return fulfillJson(route, { error: { code: "service_unavailable", message: "发布存储暂不可用", status_code: 503 } }, 503);
      }
      const record = {
        publication_id: "pub_final_001",
        job_id: "docjob_pub_admin",
        generation: 1,
        source_file_id: "file_pdf_1",
        source_sha256: `sha256:${SHA_A}`,
        result_file_id: "file_docx_1",
        result_sha256: `sha256:${SHA_A}`,
        review_record_id: "rev_1",
        review_sequence: 1,
        preview_run_id: "prev_1",
        published_by: "admin",
        published_at: "2026-11-27T12:00:00Z",
        note: String(body.note || ""),
        versions: {
          template: { resource_id: "tpl_default", version: "v1", snapshot_hash: "h_tpl" },
          symbol_rules: { resource_id: "sym_default", version: "v1", snapshot_hash: "h_sym" },
          renderer_implementation_sha256: "h_ren",
          translation_status: "not_applicable",
          models: [],
        },
      };
      publishedRecords = [record];
      return fulfillJson(route, { publication: record, available_actions: makeActions({ publish: { enabled: false, eligible: false } }) }, 201);
    });
    await page.route("**/api/v1/document-jobs/docjob_pub_admin/publications/pub_final_001/download-url", (route) =>
      fulfillJson(route, {
        publication_id: "pub_final_001",
        job_id: "docjob_pub_admin",
        result_file_id: "file_docx_1",
        result_sha256: `sha256:${SHA_A}`,
        size_bytes: 20480,
        download_url: "https://example.test/final-delivery.docx",
        expires_at: "2026-12-01T00:00:00Z",
        method: "GET",
        classification: "final_delivery",
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_pub_admin/new-generation", async (route) => {
      newGenAttempts += 1;
      const body = JSON.parse(route.request().postData() || "{}") as Record<string, unknown>;
      newGenUuid = String(body.request_id || "");
      return fulfillJson(
        route,
        { error: { code: "service_unavailable", message: "投递队列暂不可用，请保留原请求 ID 对账。", status_code: 503, generation_request_id: newGenUuid, accepted: true, accepted_generation: 2 } },
        503,
      );
    });
    await page.route("**/api/v1/document-jobs/docjob_pub_admin/generation-requests/**", (route) =>
      fulfillJson(route, {
        accepted: true,
        request_id: newGenUuid,
        job_id: "docjob_pub_admin",
        accepted_generation: 2,
        accepted_at: "2026-11-27T12:10:00Z",
        source: baseSource,
        audit_id: "audit_ng_1",
        replayed: true,
        current_generation: 2,
        current_job: { id: "docjob_pub_admin", status: "queued", stage: "uploaded", progress: 0, retry_count: 2, result_file_id: null, quality_status: "pending", review_status: "unreviewed", delivery_status: "internal_draft" },
      }),
    );

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/jobs/docjob_pub_admin?tab=publication");

    // 初始阻断态：preflight_checks 与 #publication-disabled-reasons 可见，发布按钮禁用
    await expect(page.getByText("发布前检查清单")).toBeVisible();
    await expect(page.locator("#publication-disabled-reasons")).toContainText("文档发布写入当前已停用。");
    await expect(page.getByRole("button", { name: "正式发布为最终交付件" })).toBeDisabled();

    // 后端开放发布后刷新
    publishEnabled = true;
    await page.getByRole("button", { name: "刷新发布状态" }).click();
    await expect(page.getByRole("button", { name: "正式发布为最终交付件" })).toBeEnabled();

    // 首次提交遇 503 -> 保留同一幂等键再次重放成功
    await page.getByRole("button", { name: "正式发布为最终交付件" }).click();
    const publishDialog = page.getByRole("dialog", { name: "正式发布为最终交付件" });
    await publishDialog.getByPlaceholder(/准予交付客户/).fill("审核通过，准予交付");
    await publishDialog.getByRole("button", { name: "确认正式发布" }).click();
    await expect(publishDialog.getByText("已保留同一幂等键")).toBeVisible();

    await publishDialog.getByRole("button", { name: "使用同一幂等键重试发布" }).click();
    await expect(page.getByText("pub_final_001")).toBeVisible();
    expect(publishRequestIds).toHaveLength(2);
    expect(publishRequestIds[0]).toBe(publishRequestIds[1]);

    // 下载最终交付件（阻断 window.open 弹窗后直接在页面断言 final_delivery 提示条）
    await page.evaluate(() => { window.open = () => null; });
    await page.getByRole("button", { name: "下载最终交付件" }).click();
    await expect(page.getByText("classification: final_delivery")).toBeVisible();

    // Admin 同任务新代遇 503 -> 保留同一 UUID -> 点击对账结果成功
    await page.getByRole("button", { name: "开始同任务新代" }).click();
    const newGenDialog = page.getByRole("dialog", { name: "开始同任务新代" });
    await newGenDialog.getByPlaceholder(/发起新一轮生成/).fill("表格样式需按最新验证重跑");
    await newGenDialog.getByRole("button", { name: "确认发起同任务新代" }).click();
    await expect(newGenDialog.getByText("禁止自动更换幂等键重复提交")).toBeVisible();
    expect(newGenAttempts).toBe(1);

    await newGenDialog.getByRole("button", { name: "对账请求结果" }).click();
    await expect(newGenDialog.getByText("新代请求已受理：第 3 代")).toBeVisible();
  });
});
