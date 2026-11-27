import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api/client";
import { documentJobsApi } from "@/api/documentJobs";
import type { DocumentJobTranslationBatchListResponse } from "@/api/types";

vi.mock("@/api/client", () => ({
  apiRequest: vi.fn(),
}));

const translationBatchList: DocumentJobTranslationBatchListResponse = {
  job_id: "docjob_batch",
  generation: 1,
  execution: {
    outcome: "retrying",
    leaf_count: 2,
    succeeded_leaf_count: 1,
    active_leaf_count: 1,
    retryable_failed_leaf_count: 0,
    terminal_failed_leaf_count: 0,
    failure_batch_id: null,
    reason_code: null,
    reason_message: null,
    partial_artifacts_debug_only: true,
  },
  items: [],
};

describe("document jobs API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiRequest).mockResolvedValue(translationBatchList);
  });

  it("requests job-scoped translation batch diagnostics", async () => {
    const response = await documentJobsApi.listTranslationBatches("docjob_batch");

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/document-jobs/docjob_batch/translation-batches",
      method: "GET",
    });
    expect(response.execution?.outcome).toBe("retrying");
  });

  it("covers Phase 2 quality, preview, review, table-reference, publication, and new-generation endpoints", async () => {
    const expectedSource = {
      generation: 1,
      result_file_id: "file_docx_1",
      result_sha256: "sha256:" + "a".repeat(64),
      file_review_source_revision: 2,
      receipt_sha256: "sha256:" + "b".repeat(64),
    };

    await documentJobsApi.getQuality("job_1");
    expect(apiRequest).toHaveBeenLastCalledWith({ url: "/api/v1/document-jobs/job_1/quality", method: "GET" });

    await documentJobsApi.listQualityTables("job_1", { limit: 20, cursor: "c1" });
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/quality/tables",
      method: "GET",
      params: { limit: 20, cursor: "c1" },
    });

    await documentJobsApi.listQualityPages("job_1", { limit: 10 });
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/quality/pages",
      method: "GET",
      params: { limit: 10 },
    });

    await documentJobsApi.getPreview("job_1", { limit: 50 });
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/preview",
      method: "GET",
      params: { limit: 50 },
    });

    await documentJobsApi.getReview("job_1");
    expect(apiRequest).toHaveBeenLastCalledWith({ url: "/api/v1/document-jobs/job_1/review", method: "GET" });

    await documentJobsApi.listReviewHistory("job_1", { limit: 25 });
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/review/history",
      method: "GET",
      params: { limit: 25 },
    });

    await documentJobsApi.submitReview("job_1", {
      status: "approved",
      issue_type: null,
      note: "已核对",
      expected_source: expectedSource,
      acknowledged_table_semantics_report_sha256: "c".repeat(64),
    });
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/review",
      method: "PATCH",
      data: {
        status: "approved",
        issue_type: null,
        note: "已核对",
        expected_source: expectedSource,
        acknowledged_table_semantics_report_sha256: "c".repeat(64),
      },
    });

    await documentJobsApi.getReviewBlockDetail("job_1", "blk/04", { snapshot_id: "d".repeat(64), limit: 20 });
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/review/blocks/blk%2F04",
      method: "GET",
      params: { snapshot_id: "d".repeat(64), limit: 20 },
    });

    await documentJobsApi.listTableReferences("job_1", { block_id: "blk_04" });
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/table-references",
      method: "GET",
      params: { block_id: "blk_04" },
    });

    await documentJobsApi.getTableReferenceContentBlob("/api/v1/document-jobs/job_1/table-references/a1/content?generation=1&ir_file_id=ir1");
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/table-references/a1/content?generation=1&ir_file_id=ir1",
      method: "GET",
      responseType: "blob",
    });

    await documentJobsApi.requestNewGeneration("job_1", {
      request_id: "11111111-2222-4333-8444-555555555555",
      note: "重算新代",
      expected_source: expectedSource,
    });
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/new-generation",
      method: "POST",
      data: {
        request_id: "11111111-2222-4333-8444-555555555555",
        note: "重算新代",
        expected_source: expectedSource,
      },
    });

    await documentJobsApi.getGenerationRequest("job_1", "11111111-2222-4333-8444-555555555555");
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/generation-requests/11111111-2222-4333-8444-555555555555",
      method: "GET",
    });

    await documentJobsApi.listPublications("job_1");
    expect(apiRequest).toHaveBeenLastCalledWith({ url: "/api/v1/document-jobs/job_1/publications", method: "GET" });

    await documentJobsApi.publish("job_1", {
      request_id: "22222222-3333-4444-8555-666666666666",
      note: "正式交付",
      expected_source: {
        ...expectedSource,
        review_record_id: "rev_1",
        review_sequence: 1,
        preview_run_id: "prev_1",
        preview_revision: 1,
        quality_summary_sha256: "sha256:" + "e".repeat(64),
      },
    });
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/publish",
      method: "POST",
      data: expect.objectContaining({
        request_id: "22222222-3333-4444-8555-666666666666",
        note: "正式交付",
      }),
    });

    await documentJobsApi.createPublicationDownloadUrl("job_1", "pub_1");
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job_1/publications/pub_1/download-url",
      method: "GET",
    });
  });
});
