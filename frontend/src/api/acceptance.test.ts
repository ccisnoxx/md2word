import { beforeEach, describe, expect, it, vi } from "vitest";

import { acceptanceApi } from "@/api/acceptance";
import { apiRequest } from "@/api/client";
import type { AcceptanceLatestSummaryResponse, AcceptanceRunListResponse, AcceptanceRunResponse } from "@/api/types";

vi.mock("@/api/client", () => ({
  apiRequest: vi.fn(),
}));

const acceptanceRun: AcceptanceRunResponse = {
  id: "run_p0_1",
  title: "P0 Golden Sample",
  tier: "P0",
  status: "passed",
  environment: "hostdzire",
  source: "golden_sample",
  report_path_or_url: "tests/tmp/golden_sample_runs/run_p0_1/report.md",
  started_at: "2026-06-21T01:00:00Z",
  finished_at: "2026-06-21T01:12:00Z",
  summary: "4/4 succeeded",
  blockers: [],
  warnings: [],
  reviewer: null,
  decision: null,
  reviewed_at: null,
  review_note: null,
  updated_at: "2026-06-21T01:12:00Z",
};

const listResponse: AcceptanceRunListResponse = {
  items: [acceptanceRun],
  total: 1,
};

const latestSummaryResponse: AcceptanceLatestSummaryResponse = {
  overall_status: "accepted",
  missing_tiers: [],
  blocker_count: 0,
  warning_count: 0,
  latest_reviewed_run: null,
  tiers: [
    {
      tier: "P0",
      run: acceptanceRun,
      missing: false,
      risk_level: "success",
      blockers: [],
      warnings: [],
    },
  ],
  generated_at: "2026-06-21T01:13:00Z",
};

describe("acceptance API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiRequest).mockResolvedValue(listResponse);
  });

  it("requests the acceptance run list endpoint", async () => {
    await acceptanceApi.list();

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/acceptance/runs",
      method: "GET",
    });
  });

  it("requests one acceptance run by id", async () => {
    vi.mocked(apiRequest).mockResolvedValue(acceptanceRun);

    await acceptanceApi.get("run_p0_1");

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/acceptance/runs/run_p0_1",
      method: "GET",
    });
  });

  it("requests the latest acceptance summary endpoint", async () => {
    vi.mocked(apiRequest).mockResolvedValue(latestSummaryResponse);

    await acceptanceApi.latestSummary();

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/acceptance/runs/latest-summary",
      method: "GET",
    });
  });

  it("posts a review decision with a trimmed note", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ ...acceptanceRun, decision: "needs_changes" });

    await acceptanceApi.review("run_p0_1", {
      decision: "needs_changes",
      note: "  补充 P1 签字  ",
    });

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/acceptance/runs/run_p0_1/review",
      method: "POST",
      data: {
        decision: "needs_changes",
        review_note: "补充 P1 签字",
      },
    });
  });

  it("omits a blank optional review note", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ ...acceptanceRun, decision: "approved" });

    await acceptanceApi.review("run_p0_1", {
      decision: "approved",
      note: "   ",
    });

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/acceptance/runs/run_p0_1/review",
      method: "POST",
      data: {
        decision: "approved",
      },
    });
  });
});
