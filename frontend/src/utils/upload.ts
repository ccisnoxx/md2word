// frontend/src/utils/upload.ts: PDF file validation and authorized content upload helpers.
import type { FileUploadResponse, FileUploadUrlResponse } from "@/api/types";
import { normalizeApiErrorBody, type ApiClientError } from "@/utils/errors";

const DEFAULT_MAX_UPLOAD_BYTES = 52_428_800;

export function getMaxUploadBytes(): number {
  const configured = Number(import.meta.env.VITE_MAX_UPLOAD_BYTES || DEFAULT_MAX_UPLOAD_BYTES);
  return Number.isFinite(configured) && configured > 0 ? configured : DEFAULT_MAX_UPLOAD_BYTES;
}

export function validatePdfFile(file: File): string | null {
  const hasPdfName = file.name.toLowerCase().endsWith(".pdf");
  const hasPdfType = file.type === "application/pdf" || file.type === "";

  if (!hasPdfName || !hasPdfType) {
    return "请选择 PDF 文件。";
  }
  if (file.size > getMaxUploadBytes()) {
    return `文件大小超过限制，当前上限为 ${Math.round(getMaxUploadBytes() / 1024 / 1024)} MB。`;
  }
  return null;
}

export async function uploadFileContent(
  authorization: FileUploadUrlResponse,
  file: File,
  token: string | null,
): Promise<FileUploadResponse> {
  const headers = new Headers(authorization.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", file.type || "application/pdf");
  }
  if (token && shouldAttachBearerForApiUpload(authorization.upload_url) && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(authorization.upload_url, {
    method: authorization.method,
    headers,
    body: file,
  });

  if (!response.ok) {
    throw await buildFetchApiError(response);
  }

  return await parseUploadSuccess(response, authorization);
}

function shouldAttachBearerForApiUpload(uploadUrl: string): boolean {
  try {
    const parsed = new URL(uploadUrl, window.location.origin);
    return parsed.pathname.startsWith("/api/v1/files/") && parsed.pathname.endsWith("/content");
  } catch {
    return false;
  }
}

async function buildFetchApiError(response: Response): Promise<ApiClientError> {
  const traceId = response.headers.get("x-trace-id");
  const text = await response.text();
  if (!text) {
    return {
      status: response.status,
      message: response.statusText || "上传失败。",
      traceId: traceId || undefined,
      raw: null,
    };
  }

  try {
    return normalizeApiErrorBody(response.status, JSON.parse(text), traceId);
  } catch {
    return {
      status: response.status,
      message: text,
      traceId: traceId || undefined,
      raw: text,
    };
  }
}

async function parseUploadSuccess(
  response: Response,
  authorization: FileUploadUrlResponse,
): Promise<FileUploadResponse> {
  const text = await response.text();
  if (!text.trim()) {
    if (shouldAttachBearerForApiUpload(authorization.upload_url)) {
      throw {
        status: response.status,
        code: "invalid_upload_response",
        message: "文件上传接口没有返回文件登记结果。",
        raw: null,
      } satisfies ApiClientError;
    }
    return { file: authorization.file };
  }

  try {
    return JSON.parse(text) as FileUploadResponse;
  } catch (caught) {
    if (!shouldAttachBearerForApiUpload(authorization.upload_url)) {
      return { file: authorization.file };
    }
    throw {
      status: response.status,
      code: "invalid_upload_response",
      message: "文件上传接口返回了不可解析的响应。",
      raw: caught,
    } satisfies ApiClientError;
  }
}
