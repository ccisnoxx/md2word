// File: frontend/src/api/files.ts
// Purpose: Provide file metadata, upload-authorization, and retention API wrappers.
import { apiRequest } from "@/api/client";
import type {
  DocumentFileResponse,
  FileRetentionDeleteExecuteRequest,
  FileRetentionDeletePreviewRequest,
  FileRetentionDeleteResponse,
  FileRetentionMarkExpiredResponse,
  FileRetentionPlanResponse,
  FileUploadUrlRequest,
  FileUploadUrlResponse,
} from "@/api/types";

export const filesApi = {
  // 创建 PDF 上传授权并登记 source file metadata。
  createUploadUrl(payload: FileUploadUrlRequest): Promise<FileUploadUrlResponse> {
    return apiRequest<FileUploadUrlResponse>({
      url: "/api/v1/files/upload-url",
      method: "POST",
      data: payload,
    });
  },

  // 读取单个文件 metadata。
  get(fileId: string): Promise<DocumentFileResponse> {
    return apiRequest<DocumentFileResponse>({
      url: `/api/v1/files/${fileId}`,
      method: "GET",
    });
  },

  // 读取 Admin-only retention dry-run 计划。
  getRetentionPlan(): Promise<FileRetentionPlanResponse> {
    return apiRequest<FileRetentionPlanResponse>({
      url: "/api/v1/files/retention/plan",
      method: "GET",
    });
  },

  // 将当前过期候选标记为 expired，不执行物理删除。
  markRetentionExpired(): Promise<FileRetentionMarkExpiredResponse> {
    return apiRequest<FileRetentionMarkExpiredResponse>({
      url: "/api/v1/files/retention/mark-expired",
      method: "POST",
    });
  },

  // 预览 selected expired 文件物理删除结果，不修改 metadata 或二进制。
  previewRetentionDelete(payload: FileRetentionDeletePreviewRequest): Promise<FileRetentionDeleteResponse> {
    return apiRequest<FileRetentionDeleteResponse>({
      url: "/api/v1/files/retention/delete-preview",
      method: "POST",
      data: payload,
    });
  },

  // 执行 selected expired 文件物理删除，后端仍保留 metadata 追溯信息。
  deleteExpiredRetentionFiles(payload: FileRetentionDeleteExecuteRequest): Promise<FileRetentionDeleteResponse> {
    return apiRequest<FileRetentionDeleteResponse>({
      url: "/api/v1/files/retention/delete-expired",
      method: "POST",
      data: payload,
    });
  },
};
