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
    return "Blocked";
  }
  if (report.summary.warning_count > 0) {
    return "Warnings";
  }
  return "Ready";
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
    { key: "added", label: "Added", value: summary?.added ?? 0 },
    { key: "updated", label: "Updated", value: summary?.updated ?? 0 },
    { key: "disabled", label: "Disabled", value: summary?.disabled ?? 0 },
    { key: "removed", label: "Removed", value: summary?.removed ?? 0 },
    { key: "unchanged", label: "Unchanged", value: summary?.unchanged ?? 0 },
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
