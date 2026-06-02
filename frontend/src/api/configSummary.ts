// frontend/src/api/configSummary.ts: Aggregate configuration-release todo counts for settings home.
import { apiRequest } from "@/api/client";

export type ConfigTodoSummaryResponse = {
  pendingReviewProposals: number | null;
  approvedProposals: number | null;
  templateDraftVersions: number;
  unverifiedTemplateDraftVersions: number;
  translationDraftProfiles: number | null;
  translationProfilesUnavailable: boolean;
};

type TemplateListResponse = {
  items: Array<{ id: string }>;
};

type TemplateVersionListResponse = {
  items: Array<{
    status: string;
    verification_job_id: string | null;
    verification_note: string | null;
  }>;
};

type ProposalListResponse = {
  total: number;
};

type TranslationProfileListResponse = {
  items: Array<{ id: string }>;
};

type TranslationProfileDraftResponse = {
  snapshot_hash: string | null;
};

type Role = "admin" | "operator" | string | undefined;

async function countTemplateDrafts(): Promise<Pick<ConfigTodoSummaryResponse, "templateDraftVersions" | "unverifiedTemplateDraftVersions">> {
  const templates = await apiRequest<TemplateListResponse>({
    url: "/api/v1/templates",
    method: "GET",
  });
  const versionLists = await Promise.all(
    templates.items.map((template) =>
      apiRequest<TemplateVersionListResponse>({
        url: `/api/v1/templates/${template.id}/versions`,
        method: "GET",
      }),
    ),
  );
  const drafts = versionLists.flatMap((versionList) => versionList.items).filter((version) => version.status === "draft");
  return {
    templateDraftVersions: drafts.length,
    unverifiedTemplateDraftVersions: drafts.filter(
      (version) => !version.verification_job_id || !version.verification_note,
    ).length,
  };
}

async function countAdminProposals(): Promise<Pick<ConfigTodoSummaryResponse, "pendingReviewProposals" | "approvedProposals">> {
  const [pending, approved] = await Promise.all([
    apiRequest<ProposalListResponse>({
      url: "/api/v1/term-rule-proposals",
      method: "GET",
      params: { scope: "pending_review" },
    }),
    apiRequest<ProposalListResponse>({
      url: "/api/v1/term-rule-proposals",
      method: "GET",
      params: { scope: "all", status: "approved" },
    }),
  ]);
  return {
    pendingReviewProposals: pending.total,
    approvedProposals: approved.total,
  };
}

async function countTranslationDrafts(): Promise<Pick<ConfigTodoSummaryResponse, "translationDraftProfiles" | "translationProfilesUnavailable">> {
  try {
    const profiles = await apiRequest<TranslationProfileListResponse>({
      url: "/api/v1/translation-profiles",
      method: "GET",
    });
    const drafts = await Promise.all(
      profiles.items.map((profile) =>
        apiRequest<TranslationProfileDraftResponse>({
          url: `/api/v1/translation-profiles/${profile.id}/draft`,
          method: "GET",
        }),
      ),
    );
    return {
      translationDraftProfiles: drafts.filter((draft) => Boolean(draft.snapshot_hash)).length,
      translationProfilesUnavailable: false,
    };
  } catch (caught) {
    if (typeof caught === "object" && caught !== null && "status" in caught && caught.status === 503) {
      return {
        translationDraftProfiles: null,
        translationProfilesUnavailable: true,
      };
    }
    throw caught;
  }
}

export const configSummaryApi = {
  async get(role: Role): Promise<ConfigTodoSummaryResponse> {
    const [templates, translation, proposals] = await Promise.all([
      countTemplateDrafts(),
      countTranslationDrafts(),
      role === "admin"
        ? countAdminProposals()
        : Promise.resolve({ pendingReviewProposals: null, approvedProposals: null }),
    ]);
    return {
      ...templates,
      ...translation,
      ...proposals,
    };
  },
};
