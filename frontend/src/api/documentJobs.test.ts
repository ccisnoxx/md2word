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
});
