// frontend/src/api/configSummary.ts: Config workbench aggregate API wrapper.
import { apiRequest } from "@/api/client";

export type ConfigWorkbenchStatus = "ready" | "warning" | "blocked" | "unavailable";
export type ConfigWorkbenchSeverity = "info" | "warning" | "critical";
export type ConfigWorkbenchGroupId =
  | "runtime_readiness"
  | "templates"
  | "term_rule_sets"
  | "translation_profiles"
  | "translation_term_sets";

export type ConfigWorkbenchFinding = {
  code: string;
  severity: ConfigWorkbenchSeverity;
  message: string;
  route: string | null;
  target_id: string | null;
};

export type ConfigWorkbenchGroup = {
  id: ConfigWorkbenchGroupId;
  label: string;
  status: ConfigWorkbenchStatus;
  route: string;
  default_label: string | null;
  draft_count: number | null;
  pending_count: number | null;
  warning_count: number;
  blocker_count: number;
  findings: ConfigWorkbenchFinding[];
};

export type ConfigWorkbenchReleaseGate = {
  p0_document_jobs_required: boolean;
  p0_document_jobs_ready: boolean;
  blockers: string[];
  warnings: string[];
};

export type ConfigWorkbenchSummaryResponse = {
  generated_at: string;
  overall_status: ConfigWorkbenchStatus;
  release_gate: ConfigWorkbenchReleaseGate;
  groups: ConfigWorkbenchGroup[];
};

export type ConfigTodoSummaryResponse = ConfigWorkbenchSummaryResponse;

export const configSummaryApi = {
  get(): Promise<ConfigWorkbenchSummaryResponse> {
    return apiRequest<ConfigWorkbenchSummaryResponse>({
      url: "/api/v1/config-workbench/summary",
      method: "GET",
    });
  },
};

