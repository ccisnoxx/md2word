// frontend/src/api/files.ts: File metadata and upload-authorization API wrappers.
import { apiRequest } from "@/api/client";
import type { DocumentFileResponse, FileUploadUrlRequest, FileUploadUrlResponse } from "@/api/types";

export const filesApi = {
  createUploadUrl(payload: FileUploadUrlRequest): Promise<FileUploadUrlResponse> {
    return apiRequest<FileUploadUrlResponse>({
      url: "/api/v1/files/upload-url",
      method: "POST",
      data: payload,
    });
  },

  get(fileId: string): Promise<DocumentFileResponse> {
    return apiRequest<DocumentFileResponse>({
      url: `/api/v1/files/${fileId}`,
      method: "GET",
    });
  },
};
