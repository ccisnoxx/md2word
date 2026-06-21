// File: frontend/src/composables/useTermRuleGovernanceDisplay.ts
// Purpose: Centralize Term Rule Set diff and preflight display mapping.
import type {
  TermRuleGovernanceFindingResponse,
  TermRuleSetDiffResponse,
  TermRuleSetPreflightResponse,
} from "@/api/types";

type ElementTagType = "success" | "warning" | "danger" | "info" | "primary";

export type TermRuleDiffCounter = {
  key: string;
  label: string;
  value: number;
};

export function termRulePreflightStatusLabel(report: TermRuleSetPreflightResponse | null): string {
  if (!report) {
    return "未加载";
  }
  if (report.blocking) {
    return "已阻断";
  }
  if (report.summary.warning_count > 0) {
    return "有告警";
  }
  return "可发布";
}

export function termRulePreflightStatusType(report: TermRuleSetPreflightResponse | null): ElementTagType {
  if (!report) {
    return "info";
  }
  if (report.blocking) {
    return "danger";
  }
  if (report.summary.warning_count > 0) {
    return "warning";
  }
  return "success";
}

export function termRulePreflightFindings(
  report: TermRuleSetPreflightResponse | null,
): TermRuleGovernanceFindingResponse[] {
  if (!report) {
    return [];
  }
  return [...report.errors, ...report.warnings, ...report.conflicts];
}

export function termRuleDiffCounters(report: TermRuleSetDiffResponse | null): TermRuleDiffCounter[] {
  const summary = report?.summary;
  return [
    { key: "added", label: "新增", value: summary?.added ?? 0 },
    { key: "updated", label: "更新", value: summary?.updated ?? 0 },
    { key: "disabled", label: "停用", value: summary?.disabled ?? 0 },
    { key: "removed", label: "移除", value: summary?.removed ?? 0 },
    { key: "unchanged", label: "未变", value: summary?.unchanged ?? 0 },
  ];
}

export function termRuleChangeTypeLabel(changeType: string): string {
  const labels: Record<string, string> = {
    added: "新增",
    updated: "更新",
    disabled: "停用",
    removed: "移除",
    unchanged: "未变",
  };
  return labels[changeType] || changeType;
}

export function termRuleChangeTypeTagType(changeType: string): ElementTagType {
  if (changeType === "added") {
    return "success";
  }
  if (changeType === "updated") {
    return "primary";
  }
  if (changeType === "disabled") {
    return "warning";
  }
  if (changeType === "removed") {
    return "danger";
  }
  return "info";
}

export function termRuleFindingTagType(severity: string): ElementTagType {
  if (severity === "error" || severity === "conflict") {
    return "danger";
  }
  if (severity === "warning") {
    return "warning";
  }
  return "info";
}

export function termRuleFindingSeverityLabel(severity: string): string {
  const labels: Record<string, string> = {
    error: "错误",
    warning: "告警",
    conflict: "冲突",
  };
  return labels[severity] || severity;
}

export function termRuleFieldLabel(field: string): string {
  const labels: Record<string, string> = {
    id: "规则 ID",
    category_id: "分类",
    category_name: "分类",
    source_term: "源术语",
    normalized_term: "规范化术语",
    scope_type: "规则域类型",
    scope_id: "规则域 ID",
    scope_key: "规则域键",
    current_version: "当前版本",
    active: "生效状态",
    rule_mode: "规则模式",
    apply_scope: "适用范围",
    case_sensitive: "区分大小写",
    enabled: "启用状态",
    priority: "优先级",
    custom_html: "自定义 HTML",
    custom_markdown: "自定义 Markdown",
    notes: "备注",
    segments: "片段",
  };
  return labels[field] || field;
}

export function termRuleChangedFieldsLabel(fields: string[]): string {
  if (!fields.length) {
    return "-";
  }
  return fields.map(termRuleFieldLabel).join("、");
}
