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
  items: [],
};

describe("document jobs API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiRequest).mockResolvedValue(translationBatchList);
  });

  it("requests job-scoped translation batch diagnostics", async () => {
    await documentJobsApi.listTranslationBatches("docjob_batch");

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/document-jobs/docjob_batch/translation-batches",
      method: "GET",
    });
  });
});
