// File: frontend/src/api/terminologyReleases.ts
// Purpose: Provide Terminology Governance Package release API wrappers.
import { apiRequest } from "@/api/client";
import type {
  TerminologyReleaseCopyResponse,
  TerminologyReleaseCreateRequest,
  TerminologyReleaseListQuery,
  TerminologyReleaseListResponse,
  TerminologyReleaseResponse,
  TerminologyReleaseValidationReportResponse,
} from "@/api/types";

function buildListParams(params: TerminologyReleaseListQuery = {}): TerminologyReleaseListQuery {
  const query: TerminologyReleaseListQuery = {};
  if (params.status) {
    query.status = params.status;
  }
  const project = params.project?.trim();
  if (project) {
    query.project = project;
  }
  const languagePair = params.language_pair?.trim();
  if (languagePair) {
    query.language_pair = languagePair;
  }
  const contentType = params.content_type?.trim();
  if (contentType) {
    query.content_type = contentType;
  }
  return query;
}

export const terminologyReleasesApi = {
  list(params: TerminologyReleaseListQuery = {}): Promise<TerminologyReleaseListResponse> {
    return apiRequest<TerminologyReleaseListResponse>({
      url: "/api/v1/terminology-releases",
      method: "GET",
      params: buildListParams(params),
    });
  },

  get(releaseId: string, version?: string | null): Promise<TerminologyReleaseResponse> {
    return apiRequest<TerminologyReleaseResponse>({
      url: `/api/v1/terminology-releases/${releaseId}`,
      method: "GET",
      params: version ? { version } : undefined,
    });
  },

  preflight(payload: TerminologyReleaseCreateRequest): Promise<TerminologyReleaseValidationReportResponse> {
    return apiRequest<TerminologyReleaseValidationReportResponse>({
      url: "/api/v1/terminology-releases/preflight",
      method: "POST",
      data: payload,
    });
  },

  publish(payload: TerminologyReleaseCreateRequest): Promise<TerminologyReleaseResponse> {
    return apiRequest<TerminologyReleaseResponse>({
      url: "/api/v1/terminology-releases",
      method: "POST",
      data: payload,
    });
  },

  rollback(releaseId: string): Promise<TerminologyReleaseResponse> {
    return apiRequest<TerminologyReleaseResponse>({
      url: `/api/v1/terminology-releases/${releaseId}/rollback`,
      method: "POST",
    });
  },

  copy(releaseId: string, version?: string | null): Promise<TerminologyReleaseCopyResponse> {
    return apiRequest<TerminologyReleaseCopyResponse>({
      url: `/api/v1/terminology-releases/${releaseId}/copy`,
      method: "POST",
      params: version ? { version } : undefined,
    });
  },
};
