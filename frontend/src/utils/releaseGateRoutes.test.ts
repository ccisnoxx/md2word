import { describe, expect, it } from "vitest";

import { releaseGateRouteForCode, releaseGateRouteLabel } from "@/utils/releaseGateRoutes";

describe("release gate route mapping", () => {
  it("routes translation term blockers before generic term blockers", () => {
    expect(releaseGateRouteForCode("translation_term_set_default_missing")).toBe("/settings/translation-term-sets");
    expect(releaseGateRouteForCode("translation_term_set_default_missing:ru2zh")).toBe("/settings/translation-term-sets");
    expect(releaseGateRouteLabel("/settings/translation-term-sets")).toBe("翻译术语");
  });

  it("routes term rule and translation profile findings to their own workbenches", () => {
    expect(releaseGateRouteForCode("term_rule_set_default_missing")).toBe("/settings/term-rule-sets");
    expect(releaseGateRouteForCode("translation_profile_default_missing")).toBe("/settings/translation-profiles");
    expect(releaseGateRouteForCode("translation_profile_default_missing:ru2zh")).toBe("/settings/translation-profiles");
  });

  it("routes document job readiness blockers to the ops dashboard", () => {
    expect(releaseGateRouteForCode("p0_document_jobs_not_ready")).toBe("/system-status/ops-dashboard");
  });

  it("routes AI provider configuration findings to the AI config page", () => {
    expect(releaseGateRouteForCode("ai_provider_config_invalid")).toBe("/settings/ai-provider");
    expect(releaseGateRouteLabel("/settings/ai-provider")).toBe("AI 配置");
  });
});
