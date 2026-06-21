// frontend/src/composables/useTermRuleForm.test.ts: Guard draft term-rule form defaults and payload mapping.
import { describe, expect, it } from "vitest";

import type { TermRuleResponse } from "@/api/types";
import {
  buildTermRuleMutationPayload,
  createEmptyRuleForm,
  isAdvancedRule,
  validateTermRuleSegments,
} from "@/composables/useTermRuleForm";

describe("useTermRuleForm", () => {
  it("creates advanced defaults with subscript and superscript segment presets", () => {
    expect(createEmptyRuleForm("advanced").segments).toEqual([
      { segment_text: "", render_type: "plain" },
      { segment_text: "", render_type: "subscript" },
      { segment_text: "", render_type: "superscript" },
    ]);
  });

  it("keeps custom render fields nullable and preserves explicit segment text", () => {
    const form = createEmptyRuleForm();
    Object.assign(form, {
      category_id: "cat",
      source_term: "  VIN  ",
      segments: [{ segment_text: "CO2", render_type: "plain" }],
      custom_html: "  ",
      custom_markdown: " **VIN** ",
      notes: "keep note spacing ",
    });

    expect(buildTermRuleMutationPayload(form, "snap-1")).toMatchObject({
      expected_snapshot_hash: "snap-1",
      category_id: "cat",
      source_term: "VIN",
      segments: [{ segment_text: "CO2", render_type: "plain" }],
      custom_html: null,
      custom_markdown: "**VIN**",
      notes: "keep note spacing ",
    });
  });

  it("reports incomplete segment rows before the backend mutation", () => {
    expect(validateTermRuleSegments([])).toBe("请填写完整 segments。");
    expect(validateTermRuleSegments([{ segment_text: "  ", render_type: "plain" }])).toBe("请填写完整 segments。");
    expect(validateTermRuleSegments([{ segment_text: "H2O", render_type: "plain" }])).toBeNull();
  });

  it("detects advanced existing rules from segment count or custom render fields", () => {
    const baseRule = {
      segments: [
        { seq: 1, segment_text: "CO", render_type: "plain" },
        { seq: 2, segment_text: "2", render_type: "subscript" },
      ],
      custom_html: null,
      custom_markdown: null,
    } as TermRuleResponse;

    expect(isAdvancedRule(baseRule)).toBe(false);
    expect(isAdvancedRule({ ...baseRule, segments: [...baseRule.segments, { seq: 3, segment_text: "e", render_type: "superscript" }] })).toBe(true);
    expect(isAdvancedRule({ ...baseRule, custom_html: "<strong>CO2</strong>" })).toBe(true);
  });
});
