// frontend/src/utils/errors.ts: Normalize backend and network failures for UI display.
import axios from "axios";

export type ApiClientError = {
  status?: number;
  code?: string;
  message: string;
  traceId?: string;
  raw: unknown;
};

export type ApiErrorDiagnosticContext = {
  route?: string;
  operation?: string;
  jobId?: string;
  jobStatus?: string;
  updatedAt?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function detailToMessage(detail: unknown): string | undefined {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return "请求参数校验失败。";
  }
  if (isRecord(detail)) {
    return readString(detail.message) || readString(detail.detail);
  }
  return undefined;
}

export function normalizeApiErrorBody(
  status: number | undefined,
  data: unknown,
  traceId?: string | null,
): ApiClientError {
  const body = isRecord(data) ? data : {};
  const nestedError = isRecord(body.error) ? body.error : {};
  const code = readString(nestedError.code) || readString(body.error_code);
  const message =
    readString(nestedError.message) ||
    detailToMessage(body.detail) ||
    readString(body.error) ||
    "请求失败，请稍后重试。";
  const responseTraceId =
    readString(nestedError.request_id) ||
    readString(nestedError.trace_id) ||
    readString(body.request_id) ||
    readString(body.trace_id);

  return {
    status,
    code,
    message,
    traceId: responseTraceId || traceId || undefined,
    raw: data,
  };
}

export function normalizeApiError(error: unknown): ApiClientError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const traceId = error.response?.headers?.["x-trace-id"];
    if (error.response) {
      return normalizeApiErrorBody(
        status,
        error.response.data,
        Array.isArray(traceId) ? traceId[0] : traceId,
      );
    }
    if (error.code === "ECONNABORTED") {
      return { message: "请求超时。", code: "timeout", raw: error };
    }
    return { message: error.message || "网络连接失败。", raw: error };
  }

  if (isApiClientError(error)) {
    return error;
  }

  if (error instanceof Error) {
    return { message: error.message, raw: error };
  }

  return { message: "请求失败，请稍后重试。", raw: error };
}

export function isApiClientError(error: unknown): error is ApiClientError {
  return isRecord(error) && typeof error.message === "string" && "raw" in error;
}

export function formatApiErrorDiagnostic(error: ApiClientError, context: ApiErrorDiagnosticContext = {}): string {
  return [
    `route=${context.route ?? "-"}`,
    `operation=${context.operation ?? "-"}`,
    `job_id=${context.jobId ?? "-"}`,
    `job_status=${context.jobStatus ?? "-"}`,
    `updated_at=${context.updatedAt ?? "-"}`,
    `http_status=${error.status ?? "-"}`,
    `code=${error.code ?? "-"}`,
    `message=${error.message}`,
    `trace_id=${error.traceId ?? "-"}`,
  ].join("\n");
}
