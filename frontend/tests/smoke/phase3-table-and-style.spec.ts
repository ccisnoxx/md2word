// 文件：frontend/tests/smoke/phase3-table-and-style.spec.ts
// 用途：Phase 3 浏览器烟雾验证，覆盖表格值列可视化核定新代提交与 503 对账，以及重构后的页面样式编辑器与 A4 组合画布 4 视口/深色主题回归。
import { expect, test, type Page, type Route } from "@playwright/test";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";
const THEME_STORAGE_KEY = "md2word.frontend.theme_mode";
const HEX_1 = "1".repeat(64);
const HEX_2 = "2".repeat(64);
const HEX_3 = "3".repeat(64);
const HEX_4 = "4".repeat(64);
const SNAPSHOT_ID = "d".repeat(64);
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

function fulfillJson(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function seedAdminAuth(page: Page) {
  await page.addInitScript(
    ({ tokenKey }) => {
      window.localStorage.setItem(tokenKey, "smoke_phase3_token");
    },
    { tokenKey: TOKEN_STORAGE_KEY },
  );
  await page.route("**/api/v1/auth/me", (route) =>
    fulfillJson(route, {
      id: "user_admin",
      username: "admin",
      display_name: "管理员",
      role: "admin",
      roles: ["admin"],
      permissions: [
        "document_jobs:read",
        "document_jobs:create",
        "translation_qa:read",
        "translation_qa:write",
        "term_proposals:read",
        "term_proposals:create",
        "term_proposals:review",
        "settings:read",
        "settings:write",
      ],
      tenant_id: "tenant_default",
      company_id: "company_default",
    }),
  );
}

test.describe("Phase 3 专家级表格核定与样式工坊升级", () => {
  test("Admin 可视化表格值列核定：拒绝 pdf_binding、导入指纹、候选列指派与 503 幂等对账", async ({ page }) => {
    test.setTimeout(60_000);
    await seedAdminAuth(page);

    const baseSource = {
      generation: 1,
      ir_file_id: "file_ir_p3",
      result_file_id: "file_docx_p3",
      result_sha256: `sha256:${HEX_1}`,
      file_review_source_revision: 2,
      receipt_sha256: `sha256:${HEX_2}`,
    };
    const actions = {
      download: { enabled: true, disabled_reason: null, retryable: false },
      retry: { enabled: false, disabled_reason: null, retryable: false },
      cancel: { enabled: false, disabled_reason: null, retryable: false },
      archive: { enabled: true, disabled_reason: null, retryable: false },
      unarchive: { enabled: false, disabled_reason: null, retryable: false },
      clone: { enabled: true, disabled_reason: null, retryable: false },
      delete: { enabled: false, disabled_reason: null, retryable: false },
      publish: { enabled: false, disabled_reason: "待复核", retryable: false },
      new_generation: { enabled: true, disabled_reason: null, retryable: false },
    };

    let submittedPayload: Record<string, unknown> | null = null;

    await page.route("**/api/v1/document-jobs/docjob_review_p3", (route) =>
      fulfillJson(route, {
        id: "docjob_review_p3",
        tenant_id: "tenant_default",
        company_id: "company_default",
        created_by: "user_admin",
        source_file_id: "file_pdf_p3",
        mode: "direct_pdf_to_word",
        document_language: "en",
        status: "succeeded",
        stage: "completed",
        progress: 100,
        retry_count: 1,
        result_file_id: "file_docx_p3",
        document_ir_file_id: "file_ir_p3",
        source_document_ir_file_id: "file_ir_p3",
        quality_status: "warning",
        review_status: "unreviewed",
        delivery_status: "internal_draft",
        request_snapshot: { source_file: { original_filename: "LM358_TableReview.pdf" } },
        available_actions: actions,
        created_at: "2026-11-27T10:00:00Z",
        updated_at: "2026-11-27T10:02:00Z",
      }),
    );
    await page.route("**/api/v1/files/file_pdf_p3", (route) =>
      fulfillJson(route, { id: "file_pdf_p3", checksum_sha256: `sha256:${HEX_1}` }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_p3/quality", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_p3",
        source: baseSource,
        states: { execution_status: "succeeded", quality_status: "warning", review_status: "unreviewed", delivery_status: "internal_draft" },
        summary: { quality_flags: [], layout_quality_flags: [], blocking_quality_flags: [], unknown_flag_count: 0 },
        producers: { items: [], unknown_producer_count: 0 },
        review: { status: "unreviewed", current_record_id: null, sequence: 0, issue_type: null, note: null, reviewed_by: null, reviewed_at: null, binding: null, validity_reason: "table_semantics_confirmation_required", quality: null },
        available_actions: actions,
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_p3/quality/tables**", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_p3",
        source: baseSource,
        availability: "available",
        reason_code: null,
        report: { schema_version: "table-evidence/v1", report_file_id: "r1", report_sha256: HEX_3, coverage: "complete", status: "warning", counts: {} },
        items: [
          {
            table_id: "tbl_p3",
            logical_group_id: "lg_p3",
            member_block_ids: ["blk_p3"],
            anchor_block_id: "blk_p3",
            source_spans: [],
            source_grid: { rows: 5, columns: 4, header_rows: [0], rowspan_count: 0, colspan_count: 1 },
            references: [],
            outputs: [],
            placeholders: [],
            render_state: "native",
            flags: [],
            unknown_flag_count: 0,
            status: "warning",
            value_column_findings: [
              {
                finding_id: "find_p3",
                code: "table_semantics:value_column_span_ambiguous",
                fragment_id: "frag_p3",
                cell_id: "cell_p3",
                source_page_index: 2,
                source_row_index: 3,
                column: 1,
                end_column: 3,
                columns: [
                  { column: 1, label: "MIN", group_start_column: 1 },
                  { column: 2, label: "TYP", group_start_column: 1 },
                ],
                value: "75",
                unit: "uV",
                manual_review_required: true,
              },
            ],
            unresolved_value_columns: [
              {
                finding_id: "find_p3",
                fragment_id: "frag_p3",
                source_page_index: 2,
                bbox: null,
                source_row_index: 3,
                source_cell_index: 1,
                reason_code: "row_ambiguous",
                manual_review_required: true,
              },
            ],
          },
        ],
        next_cursor: null,
      }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_p3/quality/pages**", (route) =>
      fulfillJson(route, { job_id: "docjob_review_p3", source: baseSource, availability: "disabled", reason_code: "preview_disabled", report: null, items: [], next_cursor: null }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_p3/preview**", (route) =>
      fulfillJson(route, { job_id: "docjob_review_p3", source: baseSource, status: "disabled", availability: "disabled", reason_code: "preview_disabled", run: null, pdf_file_id: null, page_count: null, items: [], next_cursor: null }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_p3/table-references/asset_p3/content**", (route) =>
      route.fulfill({ status: 200, contentType: "image/png", body: TINY_PNG }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_p3/table-references", (route) =>
      fulfillJson(route, {
        job_id: "docjob_review_p3",
        generation: 1,
        ir_file_id: "file_ir_p3",
        evidence_status: "registered",
        items: [
          {
            block_id: "blk_p3",
            fragment_id: "frag_p3",
            logical_group_id: "lg_p3",
            page_index: 2,
            bbox: null,
            asset_id: "asset_p3",
            file_id: "file_ref_p3",
            source_status: "valid",
            availability: "available",
            mime_type: "image/png",
            checksum_sha256: `sha256:${HEX_1}`,
            size_bytes: 256,
            warning_codes: [],
            display_supported: true,
            content_path: "/api/v1/document-jobs/docjob_review_p3/table-references/asset_p3/content?generation=1&ir_file_id=file_ir_p3",
          },
        ],
      }),
    );
    const snapshot = {
      snapshot_id: SNAPSHOT_ID,
      source_pdf_file_id: "file_pdf_p3",
      source_ir_file_id: "file_ir_p3",
      final_ir_file_id: null,
      preview_run_id: null,
      preview_revision: null,
      preview_attempt: null,
      basis: "final",
      source_content: { availability: "available", reason_code: null },
      target_content: { availability: "available", reason_code: null },
      translation: { availability: "not_applicable", reason_code: null },
      preview: { availability: "disabled", reason_code: "preview_disabled" },
      mapping: { availability: "unavailable", reason_code: "preview_disabled" },
      tables: { availability: "available", reason_code: null },
    };
    const blk = {
      block_id: "blk_p3",
      order: 1,
      block_type: "table",
      source_type: "table",
      excerpt: "Electrical Characteristics",
      source_spans: [{ source_page_index: 2, bbox: null, page_width: null, page_height: null, coordinate_unit: "mineru", coordinate_verified: false, reason_code: null, fragment_id: "frag_p3" }],
      location: { kind: "unavailable", preview_page_index: null, confidence: "none", reason_code: "preview_disabled", bookmark_label: null, disposition: "rendered", representative_block_id: null, fallback_page_index: null, fallback_block_id: null, provenance_status: "unavailable" },
      flags: [],
      table_ids: ["tbl_p3"],
    };
    await page.route("**/api/v1/document-jobs/docjob_review_p3/review/blocks/blk_p3**", (route) =>
      fulfillJson(route, { job_id: "docjob_review_p3", source: baseSource, content_snapshot: snapshot, block: blk, items: [], next_cursor: null }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_p3/review/blocks**", (route) =>
      fulfillJson(route, { job_id: "docjob_review_p3", source: baseSource, content_snapshot: snapshot, availability: "available", reason_code: null, total: 1, items: [blk], next_cursor: null }),
    );
    await page.route("**/api/v1/document-jobs/docjob_review_p3/new-generation", async (route) => {
      submittedPayload = JSON.parse(route.request().postData() || "{}") as Record<string, unknown>;
      return fulfillJson(
        route,
        {
          error: {
            code: "service_unavailable",
            message: "投递队列暂不可用，请对账。",
            status_code: 503,
            generation_request_id: String(submittedPayload.request_id || ""),
            accepted: true,
            accepted_generation: 2,
          },
        },
        503,
      );
    });
    await page.route("**/api/v1/document-jobs/docjob_review_p3/generation-requests/**", (route) =>
      fulfillJson(route, {
        accepted: true,
        request_id: String(submittedPayload?.request_id || ""),
        job_id: "docjob_review_p3",
        accepted_generation: 2,
        accepted_at: "2026-11-27T15:40:00Z",
        source: baseSource,
        audit_id: "audit_replay_p3",
        replayed: true,
        current_generation: 2,
        current_job: { id: "docjob_review_p3", status: "queued", stage: "uploaded", progress: 0, retry_count: 2, result_file_id: null, quality_status: "pending", review_status: "unreviewed", delivery_status: "internal_draft" },
      }),
    );

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/jobs/docjob_review_p3/review");
    await page.getByRole("button", { name: /表格值列核定模式/ }).click();

    const drawer = page.locator(".table-value-review-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByRole("img", { name: "核定参考图 frag_p3" })).toBeVisible();

    // 缩放参考图
    await drawer.getByRole("button", { name: "+", exact: true }).click();
    await expect(drawer.getByText("125%")).toBeVisible();

    // 导入包含 pdf_binding 的 JSON -> 被明确拒绝
    const jsonTextarea = drawer.getByPlaceholder(/粘贴 table-value-column-review\/v1 JSON/);
    await jsonTextarea.fill(JSON.stringify({
      content_list_sha256: HEX_2,
      raw_html_sha256: HEX_3,
      json_pointer: "/2/0",
      corrections: [{ source_row_index: 3, source_cell_index: 1, content_sha256: HEX_4, pdf_binding: null }],
    }));
    await drawer.getByRole("button", { name: "导入并回填指纹" }).click();
    await expect(drawer.getByText("人工核定不能提交自动出处（pdf_binding）")).toBeVisible();

    // 导入合法指纹 JSON 并选择候选列 TYP
    await jsonTextarea.fill(JSON.stringify({
      source_pdf_sha256: HEX_1,
      content_list_sha256: HEX_2,
      raw_html_sha256: HEX_3,
      json_pointer: "/2/0",
      page_index: 2,
      corrections: [{ source_row_index: 3, source_cell_index: 1, content_sha256: HEX_4, original_column_range: [1, 3] }],
    }));
    await drawer.getByRole("button", { name: "导入并回填指纹" }).click();
    await drawer.getByRole("button", { name: "列 3 (TYP)" }).click();

    await drawer.getByPlaceholder(/对照原表截图核定/).fill("对照原表截图核定 75 uV 归属 TYP 列");
    const submitBtn = drawer.getByRole("button", { name: "提交核定并重算新一代" });
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // 校验严格请求载荷：不含 pdf_binding
    await expect.poll(() => submittedPayload?.action).toBe("replay_table_value_columns");
    const reviews = submittedPayload?.table_value_column_reviews as Array<Record<string, unknown>>;
    expect(reviews).toHaveLength(1);
    const corr = (reviews[0].corrections as Array<Record<string, unknown>>)[0];
    expect(corr).toEqual({
      source_row_index: 3,
      source_cell_index: 1,
      content_sha256: HEX_4,
      original_column_range: [1, 3],
      target_column: 2,
      target_header: "TYP",
    });
    expect("pdf_binding" in corr).toBe(false);

    // 503 后走同 UUID 对账成功
    await expect(drawer.getByText("禁止自动换 key 重试")).toBeVisible();
    await drawer.getByRole("button", { name: "对账核定请求" }).click();
    await expect(drawer.getByText(/核定新代已受理：第 3 代/)).toBeVisible();
  });

  test("页面样式编辑器重构：版本元信息 Popover、A4 组合画布双向联动、完整差异抽屉与 4 视口深色主题无溢出", async ({ page }) => {
    test.setTimeout(60_000);
    await seedAdminAuth(page);

    const layoutConfig = {
      template_id: "default",
      template_version_id: "default@1",
      version: 1,
      status: "published",
      is_default: true,
      active_template_version_id: "default@1",
      source_path: "templates/default/layout.yaml",
      config_sha256: `sha256:${HEX_1}`,
      meta: { template_name: "默认数据手册模板" },
      preview_samples: {
        part_number: "OPA228",
        category: "精密运算放大器",
        heading1_text: "1 关键电气特性",
        normal_text: "适用于高精度信号调理与工业测量系统。",
      },
      config: {
        page_setup: { page_width_cm: 21, page_height_cm: 29.7, top_margin: 2.54, right_margin: 2.54, bottom_margin: 2.54, left_margin: 2.54 },
        header: { enabled: true, title_text: "OPA228 Datasheet", logo_path: "/internal/logo.png" },
        footer: { enabled: true, left_text: "内部技术资料", right_text: "Rev A", show_page_number: true },
        heading1: { font_size: 14, bold: true, color: "#1E3A8A", font_name: "SimHei" },
        table_style: { header_fill: "#DBEAFE", border_color: "#94A3B8" },
        table_content: { font_size: 9, color: "#0F172A", font_name: "SimSun" },
      },
      field_schema: {
        meta: { template_name: { label: "模板名称" } },
        categories: [
          { key: "page", label: "页面", groups: ["page_setup"] },
          { key: "hf", label: "页眉页脚", groups: ["header", "footer"] },
          { key: "headings", label: "标题", groups: ["heading1"] },
          { key: "tables", label: "表格", groups: ["table_style", "table_content"] },
        ],
        group_meta: {
          page_setup: { label: "页面设置", description: "纸张尺寸与页边距" },
          header: { label: "页眉", description: "页眉标题" },
          footer: { label: "页脚", description: "页脚文字与页码" },
          heading1: { label: "一级标题", description: "主章节标题" },
          table_style: { label: "表格样式", description: "表头底色与边框" },
          table_content: { label: "表格正文", description: "单元格字体字号" },
        },
        groups: {
          page_setup: { page_width_cm: { label: "页宽", type: "number", min: 10, max: 50, unit: "cm" } },
          header: {
            enabled: { label: "启用页眉", type: "boolean" },
            title_text: { label: "页眉文字", type: "text" },
            logo_path: { label: "Logo 路径", type: "text" },
          },
          footer: {
            enabled: { label: "启用页脚", type: "boolean" },
            left_text: { label: "页脚左侧文字", type: "text" },
            right_text: { label: "页脚右侧文字", type: "text" },
            show_page_number: { label: "显示页码", type: "boolean" },
          },
          heading1: {
            font_size: { label: "字号", type: "number", min: 6, max: 48, unit: "pt" },
            color: { label: "颜色", type: "color" },
          },
          table_style: {
            header_fill: { label: "表头底色", type: "color" },
            border_color: { label: "边框色", type: "color" },
          },
          table_content: {
            font_size: { label: "表格字号", type: "number", min: 6, max: 24, unit: "pt" },
          },
        },
      },
    };

    await page.route("**/api/v1/templates", (route) =>
      fulfillJson(route, { items: [{ id: "default", name: "默认数据手册模板", is_default: true }] }),
    );
    await page.route("**/api/v1/templates/default", (route) =>
      fulfillJson(route, { id: "default", name: "默认数据手册模板", is_default: true }),
    );
    await page.route("**/api/v1/templates/default/versions", (route) =>
      fulfillJson(route, { items: [{ template_version_id: "default@1", version: 1, status: "published", is_default: true }] }),
    );
    await page.route("**/api/v1/templates/default/layout-config**", (route) => fulfillJson(route, layoutConfig));

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/settings/word-page-styles/default");

    // 路径与 SHA256 默认收纳在「版本元信息」Popover，首屏不堆叠
    await expect(page.getByText("templates/default/layout.yaml")).not.toBeVisible();
    await page.getByRole("button", { name: "版本元信息" }).click();
    await expect(page.getByText("templates/default/layout.yaml")).toBeVisible();
    await page.keyboard.press("Escape");

    // A4 组合预览画布同时渲染页眉、型号、标题、参数表与页脚
    const canvas = page.getByLabel("A4 组合近似预览画布");
    await expect(canvas).toBeVisible();
    await expect(canvas.getByText("OPA228 Datasheet")).toBeVisible();
    await expect(canvas.getByText("1 关键电气特性", { exact: true })).toBeVisible();
    await expect(canvas.getByText("MIN", { exact: true })).toBeVisible();
    await expect(canvas.getByText("内部技术资料")).toBeVisible();

    // 点击 A4 画布上的参数表区块 -> 编辑器自动切到表格样式并高亮画布 table 区
    await canvas.getByText("失调电压").click();
    await expect(canvas).toHaveAttribute("data-active-zone", "table");
    await expect(page.getByRole("tab", { name: /表格样式/ })).toHaveAttribute("aria-selected", "true");

    // 切到一级标题修改字号 -> 打开「完整差异」抽屉可见改动前后对比
    await canvas.getByText("1 关键电气特性", { exact: true }).click();
    await expect(canvas).toHaveAttribute("data-active-zone", "heading1");
    const fontSizeInput = page.locator(".layout-section .el-form-item", { hasText: "字号" }).locator("input").first();
    await fontSizeInput.fill("16");
    await page.getByRole("button", { name: "完整差异" }).click();
    await expect(page.getByLabel("全部未保存样式改动")).toContainText("14");
    await expect(page.getByLabel("全部未保存样式改动")).toContainText("16");
    await page.keyboard.press("Escape");

    // 深色主题 + 4 视口无横向溢出
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
});
