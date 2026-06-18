import { describe, expect, it } from "vitest";

import { readinessCodeText } from "@/utils/displayText";

describe("readiness display text", () => {
  it("labels P0 production metadata-store blockers", () => {
    expect(readinessCodeText("document_jobs_metadata_store_not_mysql")).toContain("MySQL");
    expect(readinessCodeText("document_jobs_worker_backend_eager_in_production")).toContain("eager");
  });
});
