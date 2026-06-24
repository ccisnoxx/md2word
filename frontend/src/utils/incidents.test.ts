import { describe, expect, it } from "vitest";

import type { DocumentJobIncidentQueueItemResponse } from "@/api/types";
import {
  buildIncidentDiagnosticGuidance,
  countBatchRetryable,
  failedOrSkippedBatchItems,
  incidentPriorityLabel,
  isIncidentFailureType,
  isIncidentRetryCountBucket,
  isIncidentSort,
  shouldIgnoreIncidentShortcut,
} from "@/utils/incidents";

function buildIncident(id: string, retryable: boolean, stalled = false, blocked = false): DocumentJobIncidentQueueItemResponse {
  return {
    job: {
      id,
      tenant_id: "tenant_default",
      company_id: "company_default",
      created_by: "user_operator",
      source_file_id: `${id}_source`,
      source_job_id: null,
      mode: "direct_pdf_to_word",
      translation_mode: "direct",
      document_language: "auto",
      status: "failed",
      stage: "failed",
      progress: 100,
      template_version_id: "template_default",
      term_version_id: null,
      result_file_id: null,
      mineru_raw_result_file_id: null,
      document_ir_file_id: null,
      image_asset_file_ids: [],
      debug_full_text_enabled: false,
      mineru_batch_id: null,
      mineru_data_id: null,
      failed_stage: "parsing",
      error_code: "mineru_failed",
      error_message: "failed",
      retry_count: 0,
      timeout_at: null,
      started_at: null,
      completed_at: null,
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
      request_snapshot: {},
      available_actions: {
        download: { enabled: false, disabled_reason: null, retryable: false },
        retry: { enabled: retryable, disabled_reason: retryable ? null : "no", retryable },
        cancel: { enabled: false, disabled_reason: null, retryable: false },
        archive: { enabled: true, disabled_reason: null, retryable: false },
        unarchive: { enabled: false, disabled_reason: null, retryable: false },
        clone: { enabled: true, disabled_reason: null, retryable: false },
        delete: { enabled: false, disabled_reason: null, retryable: false },
      },
      created_at: "2026-06-20T00:00:00Z",
      updated_at: "2026-06-20T00:01:00Z",
    },
    failure_type: stalled ? "timeout_or_stalled" : "conversion_failed",
    priority: stalled || blocked ? 0 : retryable ? 1 : 2,
    is_incident: true,
    retryable,
    retry_disabled_reason: retryable ? null : "no",
    stalled,
    stalled_minutes: stalled ? 20 : null,
    blocked,
    suggested_action: retryable ? "可直接重试" : "查看详情",
    evidence_summary: [],
  };
}

describe("incident helpers", () => {
  it("validates known query enum values", () => {
    expect(isIncidentFailureType("artifact_missing")).toBe(true);
    expect(isIncidentFailureType("not_real")).toBe(false);
    expect(isIncidentSort("priority")).toBe(true);
    expect(isIncidentRetryCountBucket("3_plus")).toBe(true);
  });

  it("counts retryable and non-retryable selected incidents", () => {
    expect(countBatchRetryable([buildIncident("a", true), buildIncident("b", false)])).toEqual({
      retryable: 1,
      nonRetryable: 1,
    });
  });

  it("keeps skipped batch rows visible with failures", () => {
    const result = {
      action: "retry" as const,
      total: 2,
      succeeded: 1,
      failed: 0,
      skipped: 1,
      items: [
        { job_id: "ok", ok: true, skipped: false, status_code: 200, error_code: null, detail: null, item: null },
        { job_id: "skip", ok: false, skipped: true, status_code: 409, error_code: "not_retryable", detail: "no", item: null },
      ],
    };

    expect(failedOrSkippedBatchItems(result).map((item) => item.job_id)).toEqual(["skip"]);
  });

  it("labels stalled or blocked incidents ahead of retryable incidents", () => {
    expect(incidentPriorityLabel(buildIncident("stalled", false, true))).toBe("P0");
    expect(incidentPriorityLabel(buildIncident("retryable", true))).toBe("P1");
  });

  it("builds diagnostic guidance from retryability, failure type, and retry count", () => {
    const retryable = buildIncident("retryable", true);
    const artifactMissing = buildIncident("artifact", false);
    artifactMissing.failure_type = "artifact_missing";
    artifactMissing.job.retry_count = 3;

    expect(buildIncidentDiagnosticGuidance(retryable)).toMatchObject({
      type: "success",
      title: "可按现有流程重试",
    });
    expect(buildIncidentDiagnosticGuidance(artifactMissing).bullets.join(" ")).toContain("generated_word");
    expect(buildIncidentDiagnosticGuidance(artifactMissing).bullets.join(" ")).toContain("多次重试");
  });

  it("is safe when shortcut checks run without a DOM target", () => {
    expect(shouldIgnoreIncidentShortcut(null)).toBe(false);
  });
});
