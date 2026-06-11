import { describe, expect, it } from "vitest";

import { formatApiErrorDiagnostic, normalizeApiErrorBody } from "@/utils/errors";

describe("API error normalization", () => {
  it("prefers structured nested error fields over legacy fields", () => {
    const error = normalizeApiErrorBody(
      503,
      {
        detail: "legacy detail",
        error_code: "service_unavailable",
        trace_id: "trace_legacy",
        error: {
          code: "document_jobs_not_ready",
          message: "P0 文档任务执行链路未就绪。",
          status_code: 503,
          trace_id: "trace_nested",
        },
      },
      "trace_header",
    );

    expect(error.status).toBe(503);
    expect(error.code).toBe("document_jobs_not_ready");
    expect(error.message).toBe("P0 文档任务执行链路未就绪。");
    expect(error.traceId).toBe("trace_nested");
  });

  it("falls back to legacy detail and error_code fields", () => {
    const error = normalizeApiErrorBody(403, {
      detail: "当前角色无权限执行该操作。",
      error_code: "role_forbidden",
      request_id: "req_frontend_001",
    });

    expect(error.status).toBe(403);
    expect(error.code).toBe("role_forbidden");
    expect(error.message).toBe("当前角色无权限执行该操作。");
    expect(error.traceId).toBe("req_frontend_001");
  });

  it("formats copyable diagnostic payloads", () => {
    const diagnostic = formatApiErrorDiagnostic({
      status: 409,
      code: "conflict",
      message: "当前状态不允许重试。",
      traceId: "trace_123",
      raw: {},
    });

    expect(diagnostic).toBe([
      "route=-",
      "operation=-",
      "job_id=-",
      "job_status=-",
      "updated_at=-",
      "http_status=409",
      "code=conflict",
      "message=当前状态不允许重试。",
      "trace_id=trace_123",
    ].join("\n"));
  });

  it("formats route and task context in diagnostic payloads", () => {
    const diagnostic = formatApiErrorDiagnostic(
      {
        status: 503,
        code: "document_jobs_not_ready",
        message: "P0 文档任务执行链路未就绪。",
        traceId: "trace_503",
        raw: {},
      },
      {
        route: "/jobs/docjob_001",
        operation: "document_jobs.detail",
        jobId: "docjob_001",
        jobStatus: "running",
        updatedAt: "2026-06-11T12:00:00Z",
      },
    );

    expect(diagnostic).toContain("route=/jobs/docjob_001");
    expect(diagnostic).toContain("operation=document_jobs.detail");
    expect(diagnostic).toContain("job_id=docjob_001");
    expect(diagnostic).toContain("job_status=running");
    expect(diagnostic).toContain("updated_at=2026-06-11T12:00:00Z");
  });
});
