import { describe, expect, it } from "vitest";

import type { DocumentJobIncidentQueueItemResponse, DocumentJobResponse, SavedViewResponse } from "@/api/types";
import {
  buildOperationsPreviewRows,
  buildOperationsPriorityItems,
  buildSavedViewLauncherEntries,
  cockpitSourceAccess,
  countStaleActiveJobs,
} from "@/utils/operationsCockpit";

const actionStates = {
  download: { enabled: false, disabled_reason: null, retryable: false },
  retry: { enabled: false, disabled_reason: null, retryable: false },
  cancel: { enabled: false, disabled_reason: null, retryable: false },
  archive: { enabled: false, disabled_reason: null, retryable: false },
  unarchive: { enabled: false, disabled_reason: null, retryable: false },
  clone: { enabled: false, disabled_reason: null, retryable: false },
  delete: { enabled: false, disabled_reason: null, retryable: false },
};

function buildJob(overrides: Partial<DocumentJobResponse> = {}): DocumentJobResponse {
  return {
    id: "docjob_1",
    tenant_id: "tenant_default",
    company_id: "company_default",
    created_by: "user_operator",
    source_file_id: "file_source",
    source_job_id: null,
    mode: "en2zh_pdf_to_word",
    document_language: "en",
    status: "succeeded",
    stage: "completed",
    progress: 100,
    template_version_id: "template_default",
    term_version_id: null,
    result_file_id: "file_result",
    mineru_raw_result_file_id: null,
    document_ir_file_id: "file_ir",
    image_asset_file_ids: [],
    debug_full_text_enabled: false,
    mineru_batch_id: null,
    mineru_data_id: null,
    failed_stage: null,
    error_code: null,
    error_message: null,
    retry_count: 0,
    timeout_at: null,
    started_at: "2026-06-20T00:00:00Z",
    completed_at: "2026-06-20T00:01:00Z",
    canceled_at: null,
    archived_at: null,
    archived_by: null,
    deleted_at: null,
    deleted_by: null,
    delete_reason: null,
    translation_qa_status: "unreviewed",
    translation_qa_issue_type: null,
    translation_qa_note: null,
    translation_qa_reviewed_by: null,
    translation_qa_reviewed_at: null,
    request_snapshot: { source_file: { original_filename: "source.pdf" } },
    available_actions: actionStates,
    created_at: "2026-06-20T00:00:00Z",
    updated_at: "2026-06-20T00:01:00Z",
    ...overrides,
  };
}

function buildSavedView(overrides: Partial<SavedViewResponse> = {}): SavedViewResponse {
  return {
    view_id: "savedview_jobs_failed",
    tenant_id: "tenant_default",
    company_id: "company_default",
    owner_user_id: "user_operator",
    page_key: "jobs",
    name: "My failed jobs",
    filters: { status: "failed" },
    sort: "updated_at_desc",
    is_default: true,
    position: 0,
    created_at: "2026-06-20T00:00:00Z",
    updated_at: "2026-06-20T00:00:00Z",
    ...overrides,
  };
}

function buildIncident(job = buildJob({ id: "docjob_incident", status: "failed", stage: "failed" })): DocumentJobIncidentQueueItemResponse {
  return {
    job,
    failure_type: "worker_or_dispatch_failed",
    priority: 1,
    is_incident: true,
    retryable: true,
    retry_disabled_reason: null,
    stalled: false,
    stalled_minutes: null,
    blocked: false,
    suggested_action: "可直接重试",
    evidence_summary: ["worker failed"],
  };
}

describe("operations cockpit helpers", () => {
  it("derives source visibility from existing page permissions", () => {
    expect(cockpitSourceAccess({ role: "operator", roles: ["operator"], permissions: ["document_jobs:read"] })).toEqual({
      jobs: true,
      incidents: true,
      translation_qa: false,
    });
    expect(cockpitSourceAccess({ role: "operator", roles: ["operator"], permissions: ["translation_qa:read"] })).toEqual({
      jobs: false,
      incidents: false,
      translation_qa: true,
    });
  });

  it("prefers personal defaults and falls back to system saved views", () => {
    const personalEntries = buildSavedViewLauncherEntries("jobs", [buildSavedView()]);
    expect(personalEntries).toHaveLength(1);
    expect(personalEntries[0]).toMatchObject({
      fallback: false,
      pageLabel: "任务列表",
      to: { name: "jobs", query: { status: "failed", sort: "updated_at_desc", include_archived: "false", page: "1" } },
    });

    const fallbackEntries = buildSavedViewLauncherEntries("translation_qa", []);
    expect(fallbackEntries.length).toBeGreaterThan(1);
    expect(fallbackEntries.every((entry) => entry.fallback)).toBe(true);
    expect(fallbackEntries[0].to).toMatchObject({
      name: "translation-qa",
      query: { translation_qa_status: "unreviewed", page: "1" },
    });
  });

  it("builds priority items with existing saved-view query semantics", () => {
    const items = buildOperationsPriorityItems({
      access: { jobs: true, incidents: true, translation_qa: true },
      jobSummary: { failed: 2, pending: 1, queued: 1, running: 1 },
      qaSummary: { blocked: 3, needs_fix: 4, unreviewed: 5 },
      incidentSummary: {
        total: 6,
        failed: 2,
        blocked: 1,
        stalled: 2,
        retryable: 3,
        non_retryable: 1,
        by_status: {},
        by_failure_type: {
          conversion_failed: 0,
          translation_failed: 0,
          qa_unavailable: 0,
          artifact_missing: 0,
          timeout_or_stalled: 0,
          worker_or_dispatch_failed: 0,
          unknown: 0,
        },
      },
      staleActiveCount: 2,
    });

    expect(items.map((item) => item.id)).toEqual([
      "incidents-retryable",
      "incidents-stalled",
      "qa-blocked",
      "qa-needs-fix",
      "qa-unreviewed",
      "jobs-failed",
      "jobs-active",
    ]);
    expect(items.find((item) => item.id === "incidents-retryable")?.to).toMatchObject({
      name: "incidents",
      query: { retryable: "true", sort: "priority", page: "1" },
    });
    expect(items.find((item) => item.id === "jobs-active")).toMatchObject({
      label: "停滞任务",
      count: 2,
    });
  });

  it("deduplicates preview rows and deep-links QA and incident drawers", () => {
    const sharedJob = buildJob({
      id: "docjob_shared",
      status: "failed",
      stage: "failed",
      translation_qa_status: "blocked",
      updated_at: "2026-06-20T00:05:00Z",
    });
    const rows = buildOperationsPreviewRows({
      incidentItems: [buildIncident(sharedJob)],
      qaJobs: [sharedJob],
      jobItems: [sharedJob, buildJob({ id: "docjob_active", status: "running", updated_at: "2026-06-20T00:00:00Z" })],
      nowMs: new Date("2026-06-20T00:20:00Z").getTime(),
    });

    expect(rows.map((row) => row.id)).toEqual(["incident:docjob_shared", "job:docjob_active"]);
    expect(rows[0].to).toMatchObject({
      name: "incidents",
      query: { incident_job_id: "docjob_shared" },
    });
    expect(rows[1].to).toMatchObject({
      name: "jobs",
      query: { status_group: "active", sort: "updated_at_asc" },
    });
  });

  it("counts stale active jobs from the same stalled window used by saved views", () => {
    const nowMs = new Date("2026-06-20T01:00:00Z").getTime();
    expect(
      countStaleActiveJobs([
        buildJob({ id: "fresh", status: "running", updated_at: "2026-06-20T00:55:00Z" }),
        buildJob({ id: "stale", status: "queued", updated_at: "2026-06-20T00:40:00Z" }),
        buildJob({ id: "done", status: "succeeded", updated_at: "2026-06-20T00:20:00Z" }),
      ], nowMs),
    ).toBe(1);
  });
});
