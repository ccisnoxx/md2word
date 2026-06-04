// frontend/src/api/files.ts: File metadata, upload-authorization, and retention API wrappers.
import { apiRequest } from "@/api/client";
import type {
  DocumentFileResponse,
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
};
