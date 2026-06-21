// frontend/src/pages/SettingsHomePage.test.ts: Guard configuration workbench data-source boundaries.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const source = readFileSync(fileURLToPath(new URL("./SettingsHomePage.vue", import.meta.url)), "utf8");

describe("SettingsHomePage data-source boundary", () => {
  it("trusts backend overall status instead of deriving a second frontend fact source", () => {
    expect(source).not.toContain("deriveOverallStatus");
    expect(source).not.toContain("withDerivedOverallStatus");
    expect(source).toContain("summary.value = response;");
  });

  it("does not keep a module-level summary cache across visits or users", () => {
    expect(source).not.toContain("summaryCache");
    expect(source).not.toContain("CACHE_TTL_MS");
  });

  it("guards deferred group details from stale overview requests and pins grid rows", () => {
    expect(source).toContain("let summaryRequestSeq = 0;");
    expect(source).toContain("loadDeferredGroupDetails(response.groups, requestSeq)");
    expect(source).toMatch(/if \(requestSeq !== summaryRequestSeq \|\| !summary\.value\)/);
    expect(source).toMatch(/\.settings-page \{[\s\S]*align-content: start;[\s\S]*grid-auto-rows: max-content;/);
  });
});
