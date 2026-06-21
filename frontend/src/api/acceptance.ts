// File: frontend/src/api/acceptance.ts
// Purpose: Wrap Admin Acceptance Center run and review APIs.
import { apiRequest } from "@/api/client";
import type {
  AcceptanceLatestSummaryResponse,
  AcceptanceReviewRequest,
  AcceptanceRunListResponse,
  AcceptanceRunResponse,
} from "@/api/types";

type AcceptanceReviewApiPayload = {
  decision: AcceptanceReviewRequest["decision"];
  review_note?: string;
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

  review(runId: string, payload: AcceptanceReviewRequest): Promise<AcceptanceRunResponse> {
    return apiRequest<AcceptanceRunResponse>({
      url: `/api/v1/acceptance/runs/${runId}/review`,
      method: "POST",
      data: buildAcceptanceReviewPayload(payload),
    });
  },
};

function buildAcceptanceReviewPayload(payload: AcceptanceReviewRequest): AcceptanceReviewApiPayload {
  const note = payload.note?.trim();
  return {
    decision: payload.decision,
    ...(note ? { review_note: note } : {}),
  };
}
