// File: frontend/src/api/files.ts
// Purpose: Provide file metadata, upload-authorization, file-library search, and retention API wrappers.
import { apiRequest } from "@/api/client";
import type {
  DocumentFileResponse,
  FileLibrarySearchQuery,
  FileLibrarySearchResponse,
  FileQuotaPolicyDryRunRequest,
  FileQuotaPolicyDryRunResponse,
  FileRetentionCleanupRunExecuteRequest,
  FileRetentionCleanupRunHistoryListResponse,
  FileRetentionCleanupRunHistoryResponse,
  FileRetentionCleanupRunPreviewRequest,
  FileRetentionCleanupRunResponse,
  FileRetentionCleanupSchedulerDryRunRequest,
  FileRetentionCleanupSchedulerDryRunResponse,
  FileRetentionDeleteExecuteRequest,
  FileRetentionDeletePreviewRequest,
  FileRetentionDeleteResponse,
  FileRetentionMarkExpiredResponse,
  FileRetentionPolicyCreateRequest,
  FileRetentionPolicyImpactPreviewRequest,
  FileRetentionPolicyImpactResponse,
  FileRetentionPolicyListResponse,
  FileRetentionPolicyReasonRequest,
  FileRetentionPolicyResponse,
  FileRetentionPolicyUpdateRequest,
  FileRetentionPlanResponse,
  FileStorageUsageResponse,
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

  // 搜索 Admin-only document_files 安全摘要，不返回 object_key/bucket/raw metadata。
  searchLibrary(params: FileLibrarySearchQuery): Promise<FileLibrarySearchResponse> {
    return apiRequest<FileLibrarySearchResponse>({
      url: "/api/v1/files/library/search",
      method: "GET",
      params,
    });
  },

  // 读取 Admin-only retention dry-run 计划。
  getRetentionPlan(): Promise<FileRetentionPlanResponse> {
    return apiRequest<FileRetentionPlanResponse>({
      url: "/api/v1/files/retention/plan",
      method: "GET",
    });
  },

  // 读取 Admin-only document_files storage usage 只读汇总。
  getStorageUsage(): Promise<FileStorageUsageResponse> {
    return apiRequest<FileStorageUsageResponse>({
      url: "/api/v1/files/storage/usage",
      method: "GET",
    });
  },

  // 预演 staged quota policy 对拟上传文件的 warning/block 结果，不创建上传授权。
  dryRunQuotaPolicy(payload: FileQuotaPolicyDryRunRequest): Promise<FileQuotaPolicyDryRunResponse> {
    return apiRequest<FileQuotaPolicyDryRunResponse>({
      url: "/api/v1/files/quota-policy/dry-run",
      method: "POST",
      data: payload,
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

  // 预览一次 manual cleanup run，不修改 metadata、不删除文件、不写审计。
  previewRetentionCleanupRun(payload: FileRetentionCleanupRunPreviewRequest): Promise<FileRetentionCleanupRunResponse> {
    return apiRequest<FileRetentionCleanupRunResponse>({
      url: "/api/v1/files/retention/cleanup-runs/preview",
      method: "POST",
      data: payload,
    });
  },

  // 执行带 preview_hash 的 manual cleanup run，后端复用 selected-file physical-delete 安全合同。
  executeRetentionCleanupRun(payload: FileRetentionCleanupRunExecuteRequest): Promise<FileRetentionCleanupRunResponse> {
    return apiRequest<FileRetentionCleanupRunResponse>({
      url: "/api/v1/files/retention/cleanup-runs/execute",
      method: "POST",
      data: payload,
    });
  },

  // 手动运行 scheduler dry-run，只生成 readonly report、lock evidence 和 history。
  runRetentionCleanupSchedulerDryRun(
    payload: FileRetentionCleanupSchedulerDryRunRequest,
  ): Promise<FileRetentionCleanupSchedulerDryRunResponse> {
    return apiRequest<FileRetentionCleanupSchedulerDryRunResponse>({
      url: "/api/v1/files/retention/cleanup-runs/scheduler-dry-run",
      method: "POST",
      data: payload,
    });
  },

  // 读取 cleanup run durable history 分页列表，不触发清理。
  listRetentionCleanupRunHistory(params: { page: number; page_size: number }): Promise<FileRetentionCleanupRunHistoryListResponse> {
    return apiRequest<FileRetentionCleanupRunHistoryListResponse>({
      url: "/api/v1/files/retention/cleanup-runs/history",
      method: "GET",
      params,
    });
  },

  // 读取单条 cleanup run durable history，不返回对象路径或文件内容。
  getRetentionCleanupRunHistory(runId: string): Promise<FileRetentionCleanupRunHistoryResponse> {
    return apiRequest<FileRetentionCleanupRunHistoryResponse>({
      url: `/api/v1/files/retention/cleanup-runs/history/${runId}`,
      method: "GET",
    });
  },

  // 列出 Admin-only retention policy governance 状态。
  listRetentionPolicies(): Promise<FileRetentionPolicyListResponse> {
    return apiRequest<FileRetentionPolicyListResponse>({
      url: "/api/v1/files/retention/policies",
      method: "GET",
    });
  },

  // 创建 draft retention policy；发布前不影响新文件。
  createRetentionPolicy(payload: FileRetentionPolicyCreateRequest): Promise<FileRetentionPolicyResponse> {
    return apiRequest<FileRetentionPolicyResponse>({
      url: "/api/v1/files/retention/policies",
      method: "POST",
      data: payload,
    });
  },

  // 更新 draft retention policy。
  updateRetentionPolicy(policyId: string, payload: FileRetentionPolicyUpdateRequest): Promise<FileRetentionPolicyResponse> {
    return apiRequest<FileRetentionPolicyResponse>({
      url: `/api/v1/files/retention/policies/${policyId}`,
      method: "PATCH",
      data: payload,
    });
  },

  // 预览 retention policy 对历史文件的影响，不回填 expires_at。
  previewRetentionPolicyImpact(policyId: string, payload: FileRetentionPolicyImpactPreviewRequest): Promise<FileRetentionPolicyImpactResponse> {
    return apiRequest<FileRetentionPolicyImpactResponse>({
      url: `/api/v1/files/retention/policies/${policyId}/impact-preview`,
      method: "POST",
      data: payload,
    });
  },

  // 发布 draft retention policy，使其影响后续新文件。
  publishRetentionPolicy(policyId: string, payload: FileRetentionPolicyReasonRequest): Promise<FileRetentionPolicyResponse> {
    return apiRequest<FileRetentionPolicyResponse>({
      url: `/api/v1/files/retention/policies/${policyId}/publish`,
      method: "POST",
      data: payload,
    });
  },

  // 把 published retention policy 设为同 scope 默认策略。
  setDefaultRetentionPolicy(policyId: string, payload: FileRetentionPolicyReasonRequest): Promise<FileRetentionPolicyResponse> {
    return apiRequest<FileRetentionPolicyResponse>({
      url: `/api/v1/files/retention/policies/${policyId}/set-default`,
      method: "POST",
      data: payload,
    });
  },

  // 禁用 draft 或 published retention policy。
  disableRetentionPolicy(policyId: string, payload: FileRetentionPolicyReasonRequest): Promise<FileRetentionPolicyResponse> {
    return apiRequest<FileRetentionPolicyResponse>({
      url: `/api/v1/files/retention/policies/${policyId}/disable`,
      method: "POST",
      data: payload,
    });
  },
};
