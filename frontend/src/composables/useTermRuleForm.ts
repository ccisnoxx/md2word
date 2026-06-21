// File: frontend/src/composables/useTermRuleForm.ts
// Purpose: Keep draft term-rule form defaults, validation, and API payload mapping in one place.
import type {
  TermRuleCreateRequest,
  TermRuleResponse,
  TermRuleSegmentWriteRequest,
} from "@/api/types";

export type RuleDialogVariant = "basic" | "advanced";

export type RuleFormState = {
  source_term: string;
  category_id: string;
  apply_scope: string;
  case_sensitive: boolean;
  enabled: boolean;
  priority: number;
  segments: TermRuleSegmentWriteRequest[];
  custom_html: string;
  custom_markdown: string;
  notes: string;
};

export function createEmptyRuleForm(variant: RuleDialogVariant = "basic"): RuleFormState {
  const segments: TermRuleSegmentWriteRequest[] =
    variant === "advanced"
      ? [
          { segment_text: "", render_type: "plain" },
          { segment_text: "", render_type: "subscript" },
          { segment_text: "", render_type: "superscript" },
        ]
      : [{ segment_text: "", render_type: "plain" }];
  return {
    source_term: "",
    category_id: "",
    apply_scope: "both",
    case_sensitive: true,
    enabled: true,
    priority: 100,
    segments,
    custom_html: "",
    custom_markdown: "",
    notes: "",
  };
}

export function isAdvancedRule(rule: TermRuleResponse): boolean {
  return rule.segments.length > 2 || Boolean(rule.custom_html || rule.custom_markdown);
}

export function validateTermRuleSegments(segments: TermRuleSegmentWriteRequest[]): string | null {
  if (!segments.length || segments.some((segment) => !segment.segment_text.trim())) {
    return "请填写完整 segments。";
  }
  return null;
}

export function buildTermRuleMutationPayload(
  form: RuleFormState,
  expectedSnapshotHash: string | null,
): TermRuleCreateRequest {
  return {
    expected_snapshot_hash: expectedSnapshotHash,
    category_id: form.category_id,
    source_term: form.source_term.trim(),
    apply_scope: form.apply_scope,
    case_sensitive: form.case_sensitive,
    enabled: form.enabled,
    priority: form.priority,
    segments: form.segments.map((segment) => ({
      segment_text: segment.segment_text,
      render_type: segment.render_type,
    })),
    custom_html: form.custom_html.trim() || null,
    custom_markdown: form.custom_markdown.trim() || null,
    notes: form.notes,
  };
}
