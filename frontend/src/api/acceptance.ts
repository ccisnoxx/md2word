// File: frontend/src/api/acceptance.ts
// Purpose: Wrap Admin Acceptance Center run and review APIs.
import { apiRequest } from "@/api/client";
import type {
  AcceptanceLatestSummaryResponse,
  AcceptanceReviewRequest,
  AcceptanceRunListResponse,
  AcceptanceRunResponse,
  AcceptanceRunUpsertRequest,
} from "@/api/types";

type AcceptanceReviewApiPayload = {
  decision: AcceptanceReviewRequest["decision"];
  review_note?: string;
};

type AcceptanceRunUpsertApiPayload = Omit<AcceptanceRunUpsertRequest, "blockers" | "warnings"> & {
  blockers?: string[];
  warnings?: string[];
};

export const acceptanceApi = {
  list(): Promise<AcceptanceRunListResponse> {
    return apiRequest<AcceptanceRunListResponse>({
      url: "/api/v1/acceptance/runs",
      method: "GET",
    });
  },

  latestSummary(): Promise<AcceptanceLatestSummaryResponse> {
    return apiRequest<AcceptanceLatestSummaryResponse>({
      url: "/api/v1/acceptance/runs/latest-summary",
      method: "GET",
    });
  },

  get(runId: string): Promise<AcceptanceRunResponse> {
    return apiRequest<AcceptanceRunResponse>({
      url: `/api/v1/acceptance/runs/${runId}`,
      method: "GET",
    });
  },

  upsert(payload: AcceptanceRunUpsertRequest): Promise<AcceptanceRunResponse> {
    return apiRequest<AcceptanceRunResponse>({
      url: "/api/v1/acceptance/runs",
      method: "POST",
      data: buildAcceptanceRunUpsertPayload(payload),
    });
  },

  review(runId: string, payload: AcceptanceReviewRequest): Promise<AcceptanceRunResponse> {
    return apiRequest<AcceptanceRunResponse>({
      url: `/api/v1/acceptance/runs/${runId}/review`,
      method: "POST",
      data: buildAcceptanceReviewPayload(payload),
    });
  },
};

function buildAcceptanceRunUpsertPayload(payload: AcceptanceRunUpsertRequest): AcceptanceRunUpsertApiPayload {
  const reportPathOrUrl = normalizeOptionalText(payload.report_path_or_url);
  const startedAt = normalizeOptionalText(payload.started_at);
  const finishedAt = normalizeOptionalText(payload.finished_at);
  const summary = normalizeOptionalText(payload.summary);
  return {
    id: payload.id.trim(),
    title: payload.title.trim(),
    tier: payload.tier,
    status: payload.status,
    environment: payload.environment.trim(),
    source: payload.source.trim(),
    ...(reportPathOrUrl ? { report_path_or_url: reportPathOrUrl } : {}),
    ...(startedAt ? { started_at: startedAt } : {}),
    ...(finishedAt ? { finished_at: finishedAt } : {}),
    ...(summary ? { summary } : {}),
    blockers: normalizeStringList(payload.blockers),
    warnings: normalizeStringList(payload.warnings),
  };
}

function buildAcceptanceReviewPayload(payload: AcceptanceReviewRequest): AcceptanceReviewApiPayload {
  const note = payload.note?.trim();
  return {
    decision: payload.decision,
    ...(note ? { review_note: note } : {}),
  };
}

function normalizeOptionalText(value?: string | null): string | undefined {
  const normalized = value?.trim();
  return normalized || undefined;
}

function normalizeStringList(values: string[]): string[] {
  return values.map((value) => value.trim()).filter(Boolean);
}
