// 文件：frontend/src/features/document-review/useDocumentReviewSession.test.ts
// 用途：验证统一文档复核工作台会话的核心契约：表格语义强确认、409 冲突保留、预览映射诚实表达与参考图 ObjectURL 释放。
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRenderer, nextTick, reactive } from "vue";
import type { Router } from "vue-router";

import { documentJobsApi } from "@/api/documentJobs";
import type {
  DocumentJobResponse,
  DocumentJobTableReferenceListResponse,
  DocumentPreviewResponse,
  DocumentQualityPagesResponse,
  DocumentQualityResponse,
  DocumentQualityTablesResponse,
  DocumentReviewBlockDetailResponse,
  DocumentReviewBlocksResponse,
} from "@/api/types";
import { useDocumentReviewSession } from "./useDocumentReviewSession";

vi.mock("@/api/documentJobs", () => ({
  documentJobsApi: {
    get: vi.fn(),
    getQuality: vi.fn(),
    listQualityTables: vi.fn(),
    listQualityPages: vi.fn(),
    getPreview: vi.fn(),
    listReviewBlocks: vi.fn(),
    getReviewBlockDetail: vi.fn(),
    listTableReferences: vi.fn(),
    getTableReferenceContentBlob: vi.fn(),
    submitReview: vi.fn(),
    listReviewHistory: vi.fn(),
    createDownloadUrl: vi.fn(),
  },
}));
vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
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

const SHA_A = "a".repeat(64);
const SHA_B = "b".repeat(64);
const SHA_C = "c".repeat(64);
const SNAPSHOT_ID = "d".repeat(64);

const baseSource = {
  generation: 1,
  ir_file_id: "file_ir_1",
  result_file_id: "file_docx_1",
  result_sha256: `sha256:${SHA_A}`,
  file_review_source_revision: 2,
  receipt_sha256: `sha256:${SHA_B}`,
};

function makeJob(mode: DocumentJobResponse["mode"] = "direct_pdf_to_word"): DocumentJobResponse {
  return {
    id: "job_review_1",
    status: "succeeded",
    stage: "completed",
    mode,
    retry_count: 1,
    source_file_id: "file_pdf_1",
    result_file_id: "file_docx_1",
    document_ir_file_id: "file_ir_1",
    source_document_ir_file_id: "file_ir_1",
    quality_status: "warning",
    review_status: "unreviewed",
    delivery_status: "internal_draft",
    request_snapshot: { source_file: { original_filename: "OPA228.pdf" } },
    available_actions: {
      download: { enabled: true },
      retry: { enabled: false },
      cancel: { enabled: false },
      archive: { enabled: true },
      unarchive: { enabled: false },
      clone: { enabled: true },
      delete: { enabled: false },
      publish: { enabled: false },
      new_generation: { enabled: true },
    },
  } as unknown as DocumentJobResponse;
}

function makeQuality(): DocumentQualityResponse {
  return {
    job_id: "job_review_1",
    source: baseSource,
    states: {
      execution_status: "succeeded",
      quality_status: "warning",
      review_status: "unreviewed",
      delivery_status: "internal_draft",
    },
    summary: { quality_flags: [], layout_quality_flags: [], blocking_quality_flags: [], unknown_flag_count: 0 },
    producers: { items: [], unknown_producer_count: 0 },
    review: {
      status: "unreviewed",
      current_record_id: null,
      sequence: 0,
      issue_type: null,
      note: null,
      reviewed_by: null,
      reviewed_at: null,
      binding: null,
      validity_reason: "table_semantics_confirmation_required",
      quality: null,
    },
    available_actions: makeJob().available_actions as DocumentQualityResponse["available_actions"],
  };
}

function makeTables(withFinding = true): DocumentQualityTablesResponse {
  return {
    job_id: "job_review_1",
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
    items: withFinding
      ? [
          {
            table_id: "tbl_04",
            logical_group_id: "lg_04",
            member_block_ids: ["blk_04"],
            anchor_block_id: "blk_04",
            source_spans: [],
            source_grid: { rows: 6, columns: 4, header_rows: [0], rowspan_count: 0, colspan_count: 1 },
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
                column: 1,
                end_column: 3,
                columns: [
                  { column: 1, label: "MIN", group_start_column: 1 },
                  { column: 2, label: "TYP", group_start_column: 1 },
                ],
                value: "1.5",
                unit: "mV",
                manual_review_required: true,
              },
            ],
            unresolved_value_columns: [],
          },
        ]
      : [],
    next_cursor: null,
  };
}

function makeBlocks(): DocumentReviewBlocksResponse {
  return {
    job_id: "job_review_1",
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
    total: 2,
    items: [
      {
        block_id: "blk_04",
        order: 4,
        block_type: "table",
        source_type: "table",
        excerpt: "Electrical Characteristics",
        source_spans: [
          {
            source_page_index: 2,
            bbox: null,
            page_width: null,
            page_height: null,
            coordinate_unit: "mineru",
            coordinate_verified: false,
            reason_code: "coordinate_space_unverified",
            fragment_id: "frag_1",
          },
        ],
        location: {
          kind: "single_page",
          preview_page_index: 3,
          confidence: "high",
          reason_code: null,
          bookmark_label: null,
          disposition: "rendered",
          representative_block_id: null,
          fallback_page_index: null,
          fallback_block_id: null,
          provenance_status: "verified_ir205",
        },
        flags: [{ code: "table_continuation_uncertain", severity: "warning", table_id: "tbl_04" }],
        table_ids: ["tbl_04"],
      },
      {
        block_id: "blk_05",
        order: 5,
        block_type: "paragraph",
        source_type: "text",
        excerpt: "Note 1",
        source_spans: [
          {
            source_page_index: 4,
            bbox: null,
            page_width: null,
            page_height: null,
            coordinate_unit: "mineru",
            coordinate_verified: false,
            reason_code: "coordinate_space_unverified",
            fragment_id: null,
          },
        ],
        location: {
          kind: "unavailable",
          preview_page_index: null,
          confidence: "none",
          reason_code: "mapping_missing",
          bookmark_label: null,
          disposition: "not_emitted",
          representative_block_id: null,
          fallback_page_index: 1,
          fallback_block_id: null,
          provenance_status: "unavailable",
        },
        flags: [],
        table_ids: [],
      },
    ],
    next_cursor: null,
  };
}

function makePreview(status: DocumentPreviewResponse["status"] = "succeeded"): DocumentPreviewResponse {
  return {
    job_id: "job_review_1",
    source: baseSource,
    status,
    availability: status === "succeeded" ? "available" : "disabled",
    reason_code: status === "succeeded" ? null : "preview_disabled",
    run: null,
    pdf_file_id: null,
    page_count: status === "succeeded" ? 4 : null,
    items: status === "succeeded"
      ? [
          { file_id: "prev_p0", page_index: 0, width: 800, height: 1130 },
          { file_id: "prev_p3", page_index: 3, width: 800, height: 1130 },
        ]
      : [],
    next_cursor: null,
  };
}

function makePages(): DocumentQualityPagesResponse {
  return {
    job_id: "job_review_1",
    source: baseSource,
    availability: "available",
    reason_code: null,
    report: null,
    items: [],
    next_cursor: null,
  };
}

function makeTableRefs(): DocumentJobTableReferenceListResponse {
  return {
    job_id: "job_review_1",
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
        size_bytes: 1024,
        warning_codes: [],
        display_supported: true,
        content_path: "/api/v1/document-jobs/job_review_1/table-references/asset_1/content?generation=1&ir_file_id=file_ir_1",
      },
    ],
  };
}

function makeBlockDetail(blockId = "blk_04"): DocumentReviewBlockDetailResponse {
  const blocks = makeBlocks();
  const block = blocks.items.find((item) => item.block_id === blockId) || blocks.items[0];
  return {
    job_id: "job_review_1",
    source: baseSource,
    content_snapshot: blocks.content_snapshot,
    block,
    items: [
      {
        kind: "text",
        side: "target",
        field: "text",
        offset: 0,
        text: "Electrical Characteristics Table",
        truncated: false,
      },
    ],
    next_cursor: null,
  };
}

const disposers: Array<() => void> = [];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(documentJobsApi.get).mockResolvedValue(makeJob());
  vi.mocked(documentJobsApi.getQuality).mockResolvedValue(makeQuality());
  vi.mocked(documentJobsApi.listQualityTables).mockResolvedValue(makeTables(true));
  vi.mocked(documentJobsApi.listQualityPages).mockResolvedValue(makePages());
  vi.mocked(documentJobsApi.getPreview).mockResolvedValue(makePreview("succeeded"));
  vi.mocked(documentJobsApi.listReviewBlocks).mockResolvedValue(makeBlocks());
  vi.mocked(documentJobsApi.listTableReferences).mockResolvedValue(makeTableRefs());
  vi.mocked(documentJobsApi.getReviewBlockDetail).mockImplementation(async (_jobId, blockId) => makeBlockDetail(blockId));
  vi.mocked(documentJobsApi.createDownloadUrl).mockResolvedValue({
    download_url: "https://example.test/preview.png",
    expires_at: "2026-12-01T00:00:00Z",
    file: { original_filename: "preview.png" },
  } as never);
  vi.mocked(documentJobsApi.getTableReferenceContentBlob).mockResolvedValue(new Blob(["png"], { type: "image/png" }));
});

afterEach(() => {
  disposers.splice(0).forEach((dispose) => dispose());
  vi.unstubAllGlobals();
});

describe("useDocumentReviewSession", () => {
  it("强制批准时勾选表格语义报告摘要，非批准自动清除，并在 409 冲突时保留用户输入", async () => {
    const createObjectURL = vi.fn(() => "blob:table-ref-1");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    vi.stubGlobal("window", Object.assign(new EventTarget(), {}));

    const route = reactive({ params: { jobId: "job_review_1" }, query: {}, fullPath: "/jobs/job_review_1/review" });
    const router = { push: vi.fn(), replace: vi.fn() } as unknown as Router;

    let session!: ReturnType<typeof useDocumentReviewSession>;
    const app = renderer.createApp({
      setup() {
        session = useDocumentReviewSession(route, router);
        return () => null;
      },
    });
    app.mount({});
    disposers.push(() => app.unmount());

    await vi.waitFor(() => expect(session.blockDetail.value).not.toBeNull());
    await vi.waitFor(() => expect(createObjectURL).toHaveBeenCalledTimes(1));

    // direct 模式翻译隔离与预览页精确同步（preview_page_index=3，而非 source_page_index=2）
    expect(session.isTranslationJob.value).toBe(false);
    expect(session.activePreviewPageIndex.value).toBe(3);

    // 切到 location.kind=unavailable 的块时，绝不把 source_page_index=4 冒充为 Word 预览页
    await session.selectBlock("blk_05");
    expect(session.activePreviewPageIndex.value).toBe(3);

    // 批准前存在表格语义发现 -> 未勾选前禁止提交
    session.reviewForm.status = "approved";
    session.reviewForm.note = "已核对全部表格";
    await nextTick();
    expect(session.mustTickTableSemanticsToApprove.value).toBe(true);
    expect(session.canSubmitReview.value).toBe(false);

    // 勾选后可提交并附带 report_sha256
    session.reviewForm.acknowledgeTableSemantics = true;
    await nextTick();
    expect(session.canSubmitReview.value).toBe(true);

    // 模拟 409 来源冲突 -> 保留用户输入，不覆盖草稿
    vi.mocked(documentJobsApi.submitReview).mockRejectedValueOnce({
      status: 409,
      code: "conflict",
      message: "复核提交条件已变化，请重新读取。",
      raw: {},
    });
    const conflictOk = await session.submitReview();
    expect(conflictOk).toBe(false);
    expect(session.reviewConflictActive.value).toBe(true);
    expect(session.reviewForm.status).toBe("approved");
    expect(session.reviewForm.note).toBe("已核对全部表格");
    expect(documentJobsApi.submitReview).toHaveBeenCalledWith("job_review_1", {
      status: "approved",
      issue_type: null,
      note: "已核对全部表格",
      expected_source: {
        generation: baseSource.generation,
        result_file_id: baseSource.result_file_id,
        result_sha256: baseSource.result_sha256,
        file_review_source_revision: baseSource.file_review_source_revision,
        receipt_sha256: baseSource.receipt_sha256,
      },
      acknowledged_table_semantics_report_sha256: SHA_C,
    });

    // 切换为 needs_fix 后自动清除 acknowledged_table_semantics_report_sha256，遵守后端非批准禁传规则
    session.reviewForm.status = "needs_fix";
    await nextTick();
    expect(session.reviewForm.acknowledgeTableSemantics).toBe(false);
    vi.mocked(documentJobsApi.submitReview).mockResolvedValueOnce({
      job_id: "job_review_1",
      accepted_record_id: "rev_2",
      accepted_sequence: 1,
      source: baseSource,
      review: { ...makeQuality().review, status: "needs_fix", sequence: 1, validity_reason: null },
      available_actions: makeQuality().available_actions,
    });
    const ok = await session.submitReview();
    expect(ok).toBe(true);
    const secondCallPayload = vi.mocked(documentJobsApi.submitReview).mock.calls[1][1];
    expect(secondCallPayload.acknowledged_table_semantics_report_sha256).toBeUndefined();

    // 卸载时自动 revokeObjectURL 释放内存
    app.unmount();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:table-ref-1");
  });

  it("预览未启用时优雅降级且不中断块详情与复核提交", async () => {
    vi.stubGlobal("window", Object.assign(new EventTarget(), {}));
    vi.mocked(documentJobsApi.getPreview).mockResolvedValueOnce(makePreview("disabled"));
    vi.mocked(documentJobsApi.listQualityTables).mockResolvedValueOnce(makeTables(false));

    const route = reactive({ params: { jobId: "job_review_1" }, query: {}, fullPath: "/jobs/job_review_1/review" });
    const router = { push: vi.fn(), replace: vi.fn() } as unknown as Router;

    let session!: ReturnType<typeof useDocumentReviewSession>;
    const app = renderer.createApp({
      setup() {
        session = useDocumentReviewSession(route, router);
        return () => null;
      },
    });
    app.mount({});
    disposers.push(() => app.unmount());

    await vi.waitFor(() => expect(session.blockDetail.value).not.toBeNull());
    expect(session.previewResponse.value?.status).toBe("disabled");
    expect(session.previewPages.value).toHaveLength(0);
    expect(session.pageError.value).toBeNull();
  });
});
