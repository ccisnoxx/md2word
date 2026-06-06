// File: frontend/src/api/auditEvents.ts
// Purpose: Wrap Admin audit event list and governed export APIs.
import { apiRequest } from "@/api/client";
import type { AuditEventExportQuery, AuditEventExportResponse, AuditEventListQuery, AuditEventListResponse } from "@/api/types";

export const auditEventsApi = {
  // 读取 Admin 审计事件分页列表。
  list(params: AuditEventListQuery): Promise<AuditEventListResponse> {
    return apiRequest<AuditEventListResponse>({
      url: "/api/v1/audit-events",
      method: "GET",
      params,
    });
  },

  // 导出当前筛选条件下的审计事件 CSV，后端负责上限和审计记录。
  exportCsv(params: AuditEventExportQuery): Promise<AuditEventExportResponse> {
    return apiRequest<AuditEventExportResponse>({
      url: "/api/v1/audit-events/export",
      method: "GET",
      params,
    });
  },
};
