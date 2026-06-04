// File: frontend/src/api/auditEvents.ts
// Purpose: Wrap read-only audit event APIs for the Admin audit viewer.
import { apiRequest } from "@/api/client";
import type { AuditEventListQuery, AuditEventListResponse } from "@/api/types";

export const auditEventsApi = {
  // 读取 Admin 审计事件分页列表。
  list(params: AuditEventListQuery): Promise<AuditEventListResponse> {
    return apiRequest<AuditEventListResponse>({
      url: "/api/v1/audit-events",
      method: "GET",
      params,
    });
  },
};
