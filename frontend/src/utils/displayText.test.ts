import { describe, expect, it } from "vitest";

import { readinessCodeText } from "@/utils/displayText";

describe("readiness display text", () => {
  it("labels P0 production metadata-store blockers", () => {
    expect(readinessCodeText("document_jobs_metadata_store_not_mysql")).toContain("MySQL");
    expect(readinessCodeText("document_jobs_worker_backend_eager_in_production")).toContain("eager");
  });

  it("labels translation readiness codes with language-pair suffixes", () => {
    expect(readinessCodeText("translation_profile_default_missing:ru2zh")).toBe("默认翻译配置未发布（俄译中）");
    expect(readinessCodeText("translation_term_set_default_missing:ru2zh")).toBe("默认翻译术语集未发布（俄译中）");
  });
});
