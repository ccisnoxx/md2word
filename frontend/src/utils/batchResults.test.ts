import { describe, expect, it } from "vitest";

import { normalizeIncidentBatchResult, normalizeJobsBatchResult } from "@/utils/batchResults";

describe("batch result normalization", () => {
  it("normalizes Jobs bulk responses without inventing skipped counts", () => {
    const result = normalizeJobsBatchResult("批量重试", {
      action: "retry",
      total: 2,
      succeeded: 1,
      failed: 1,
      items: [
        { job_id: "ok", ok: true, status_code: 200, error_code: null, detail: null, job: null },
        { job_id: "failed", ok: false, status_code: 409, error_code: "not_retryable", detail: "不可重试", job: null },
      ],
    });

    expect(result).toMatchObject({
      title: "批量重试完成",
      succeeded: 1,
      failed: 1,
      skipped: null,
      total: 2,
    });
    expect(result.details).toEqual([
      { id: "failed", state: "failed", statusCode: 409, code: "not_retryable", detail: "不可重试" },
    ]);
  });

  it("keeps Incident skipped rows visible with failed rows", () => {
    const result = normalizeIncidentBatchResult("批量重试", {
      action: "retry",
      total: 3,
      succeeded: 1,
      failed: 1,
      skipped: 1,
      items: [
        { job_id: "ok", ok: true, skipped: false, status_code: 200, error_code: null, detail: null, item: null },
        { job_id: "failed", ok: false, skipped: false, status_code: 500, error_code: "retry_failed", detail: null, item: null },
        { job_id: "skipped", ok: false, skipped: true, status_code: 409, error_code: "not_retryable", detail: "不可重试", item: null },
      ],
    });

    expect(result.skipped).toBe(1);
    expect(result.details.map((detail) => [detail.id, detail.state])).toEqual([
      ["failed", "failed"],
      ["skipped", "skipped"],
    ]);
  });
});

