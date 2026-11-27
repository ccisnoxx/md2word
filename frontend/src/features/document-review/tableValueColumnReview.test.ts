// 文件：frontend/src/features/document-review/tableValueColumnReview.test.ts
// 用途：验证表格值列人工核定校验器、禁止 pdf_binding 守卫、JSON 指纹导入与幂等 503 对账。
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

import { documentJobsApi } from "@/api/documentJobs";
import { filesApi } from "@/api/files";
import type { DocumentQualityTableItemResponse, ReviewExpectedSourceRequest } from "@/api/types";
import {
  applyProvenanceJsonToDrafts,
  buildInitialFragmentDrafts,
  validateAndBuildTableValueReviews,
} from "./tableValueColumnReview";
import { useTableValueColumnReview } from "./useTableValueColumnReview";

vi.mock("@/api/documentJobs", () => ({
  documentJobsApi: {
    requestNewGeneration: vi.fn(),
    getGenerationRequest: vi.fn(),
  },
}));
vi.mock("@/api/files", () => ({
  filesApi: {
    get: vi.fn(),
  },
}));
vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
}));

const HEX_1 = "1".repeat(64);
const HEX_2 = "2".repeat(64);
const HEX_3 = "3".repeat(64);
const HEX_4 = "4".repeat(64);

const tableFixture: DocumentQualityTableItemResponse = {
  table_id: "tbl_01",
  logical_group_id: "lg_01",
  member_block_ids: ["blk_01"],
  anchor_block_id: "blk_01",
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
      value: "75",
      unit: "uV",
      manual_review_required: true,
    },
  ],
  unresolved_value_columns: [
    {
      finding_id: "find_1",
      fragment_id: "frag_1",
      source_page_index: 2,
      bbox: null,
      source_row_index: 3,
      source_cell_index: 1,
      reason_code: "row_ambiguous",
      manual_review_required: true,
    },
  ],
};

const expectedSource: ReviewExpectedSourceRequest = {
  generation: 1,
  result_file_id: "file_docx_1",
  result_sha256: `sha256:${HEX_1}`,
  file_review_source_revision: 2,
  receipt_sha256: `sha256:${HEX_2}`,
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("tableValueColumnReview 纯校验与载荷构建", () => {
  it("严格校验列区间与指纹，构造不含 pdf_binding 的 replay_table_value_columns 载荷", () => {
    const drafts = buildInitialFragmentDrafts([tableFixture], `sha256:${HEX_1}`);
    expect(drafts).toHaveLength(1);
    expect(drafts[0].sourcePdfSha256).toBe(HEX_1);
    expect(drafts[0].corrections[0].sourceCellIndex).toBe(1);
    expect(drafts[0].corrections[0].rangeStart).toBe(1);
    expect(drafts[0].corrections[0].rangeEnd).toBe(3);

    // 未填指纹前校验失败
    const invalidInitial = validateAndBuildTableValueReviews(drafts);
    expect(invalidInitial.valid).toBe(false);
    expect(invalidInitial.errors.some((e) => e.includes("content_list_sha256"))).toBe(true);

    // 填写合法指纹并测试 target_column 越界拦截
    drafts[0].contentListSha256 = HEX_2;
    drafts[0].rawHtmlSha256 = HEX_3;
    drafts[0].jsonPointer = "/2/0";
    drafts[0].corrections[0].contentSha256 = HEX_4;
    drafts[0].corrections[0].targetColumn = 3; // 越出 [1, 3) 右开边界
    const outOfRange = validateAndBuildTableValueReviews(drafts);
    expect(outOfRange.valid).toBe(false);
    expect(outOfRange.errors.some((e) => e.includes("[1, 3)"))).toBe(true);

    // 调整为合法 target_column=2, target_header="TYP"
    drafts[0].corrections[0].targetColumn = 2;
    drafts[0].corrections[0].targetHeader = "TYP";
    const valid = validateAndBuildTableValueReviews(drafts);
    expect(valid.valid).toBe(true);
    expect(valid.reviews).toEqual([
      {
        schema_version: "table-value-column-review/v1",
        source_pdf_sha256: HEX_1,
        content_list_sha256: HEX_2,
        page_index: 2,
        json_pointer: "/2/0",
        raw_html_sha256: HEX_3,
        normalizer_version: "table-html/v1",
        corrections: [
          {
            source_row_index: 3,
            source_cell_index: 1,
            content_sha256: HEX_4,
            original_column_range: [1, 3],
            target_column: 2,
            target_header: "TYP",
          },
        ],
      },
    ]);
    expect("pdf_binding" in valid.reviews[0].corrections[0]).toBe(false);
  });

  it("JSON 导入显式拒绝包含 pdf_binding 的非法输入，合法 JSON 正确回填字段", () => {
    const drafts = buildInitialFragmentDrafts([tableFixture]);
    const rejected = applyProvenanceJsonToDrafts(
      JSON.stringify({
        source_pdf_sha256: HEX_1,
        content_list_sha256: HEX_2,
        raw_html_sha256: HEX_3,
        json_pointer: "/2/0",
        corrections: [{ source_row_index: 3, source_cell_index: 1, content_sha256: HEX_4, pdf_binding: null }],
      }),
      drafts,
    );
    expect(rejected.ok).toBe(false);
    expect(rejected.error).toContain("pdf_binding");

    const accepted = applyProvenanceJsonToDrafts(
      JSON.stringify({
        source_pdf_sha256: `sha256:${HEX_1}`,
        content_list_sha256: HEX_2,
        raw_html_sha256: HEX_3,
        json_pointer: "/2/0",
        page_index: 2,
        corrections: [
          {
            source_row_index: 3,
            source_cell_index: 1,
            content_sha256: HEX_4,
            original_column_range: [1, 3],
            target_column: 2,
            target_header: "TYP",
          },
        ],
      }),
      drafts,
    );
    expect(accepted).toEqual({ ok: true, appliedFragments: 1, appliedCorrections: 1 });
    expect(validateAndBuildTableValueReviews(drafts).valid).toBe(true);
  });
});

describe("useTableValueColumnReview 幂等提交与对账", () => {
  it("自动读取源 PDF SHA256，提交 replay_table_value_columns，遇 503 保留 UUID 走 GET 对账", async () => {
    const store = new Map<string, string>();
    vi.stubGlobal("window", {
      sessionStorage: {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => { store.set(k, v); },
        removeItem: (k: string) => { store.delete(k); },
      },
    });
    vi.mocked(filesApi.get).mockResolvedValue({
      id: "file_pdf_1",
      checksum_sha256: `sha256:${HEX_1}`,
    } as never);

    const onAccepted = vi.fn();
    const ctrl = useTableValueColumnReview({
      jobId: ref("job_p3_1"),
      sourcePdfFileId: ref("file_pdf_1"),
      onAccepted,
    });

    ctrl.open([tableFixture], expectedSource);
    await vi.waitFor(() => expect(ctrl.fragments.value[0].sourcePdfSha256).toBe(HEX_1));

    const uuid = ctrl.form.requestId;
    ctrl.fragments.value[0].contentListSha256 = HEX_2;
    ctrl.fragments.value[0].rawHtmlSha256 = HEX_3;
    ctrl.fragments.value[0].jsonPointer = "/2/0";
    ctrl.fragments.value[0].corrections[0].contentSha256 = HEX_4;
    ctrl.fragments.value[0].corrections[0].targetColumn = 2;
    ctrl.fragments.value[0].corrections[0].targetHeader = "TYP";
    ctrl.form.note = "人工核对第 4 行数值归属 TYP 列";

    vi.mocked(documentJobsApi.requestNewGeneration).mockRejectedValueOnce({
      status: 503,
      code: "service_unavailable",
      generationRequestId: uuid,
      accepted: true,
      acceptedGeneration: 2,
      message: "队列暂不可用",
      raw: {},
    });

    expect(await ctrl.submit()).toBeNull();
    expect(documentJobsApi.requestNewGeneration).toHaveBeenCalledWith("job_p3_1", {
      request_id: uuid,
      note: "人工核对第 4 行数值归属 TYP 列",
      expected_source: expectedSource,
      action: "replay_table_value_columns",
      table_value_column_reviews: [
        expect.objectContaining({
          schema_version: "table-value-column-review/v1",
          json_pointer: "/2/0",
          normalizer_version: "table-html/v1",
        }),
      ],
    });
    expect(ctrl.form.needsReconcile).toBe(true);
    expect(ctrl.form.requestId).toBe(uuid);

    vi.mocked(documentJobsApi.getGenerationRequest).mockResolvedValueOnce({
      accepted: true,
      request_id: uuid,
      job_id: "job_p3_1",
      accepted_generation: 2,
      accepted_at: "2026-11-27T15:30:00Z",
      source: expectedSource,
      audit_id: "audit_replay_1",
      replayed: true,
      current_generation: 2,
      current_job: {
        id: "job_p3_1",
        status: "queued",
        stage: "uploaded",
        progress: 0,
        retry_count: 2,
        result_file_id: null,
        quality_status: "pending",
        review_status: "unreviewed",
        delivery_status: "internal_draft",
      },
    });

    const reconciled = await ctrl.reconcile();
    expect(documentJobsApi.getGenerationRequest).toHaveBeenCalledWith("job_p3_1", uuid);
    expect(reconciled?.accepted_generation).toBe(2);
    expect(onAccepted).toHaveBeenCalledTimes(1);
  });
});
