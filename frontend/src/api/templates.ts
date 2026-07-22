// frontend/src/api/templates.ts: 模板文件、样式配置和版本治理 API 封装。
import { apiRequest } from "@/api/client";
import type {
  TemplateDetailResponse,
  TemplateLayoutConfigDraftRequest,
  TemplateLayoutConfigResponse,
  TemplateListResponse,
  TemplateVersionDefaultRequest,
  TemplateVersionListResponse,
  TemplateVersionPublishRequest,
  TemplateVersionResponse,
} from "@/api/types";

export type TemplateVersionUploadPayload = {
  template: File;
  layout_config_path?: string | null;
  render_policy_json?: string;
};

function buildVersionFormData(payload: TemplateVersionUploadPayload): FormData {
  const formData = new FormData();
  formData.append("template", payload.template);
  if (payload.layout_config_path?.trim()) {
    formData.append("layout_config_path", payload.layout_config_path.trim());
  }
  formData.append("render_policy_json", payload.render_policy_json?.trim() || "{}");
  return formData;
}

export const templatesApi = {
  list(): Promise<TemplateListResponse> {
    return apiRequest<TemplateListResponse>({
      url: "/api/v1/templates",
      method: "GET",
    });
  },

  get(templateId: string): Promise<TemplateDetailResponse> {
    return apiRequest<TemplateDetailResponse>({
      url: `/api/v1/templates/${templateId}`,
      method: "GET",
    });
  },

  listVersions(templateId: string): Promise<TemplateVersionListResponse> {
    return apiRequest<TemplateVersionListResponse>({
      url: `/api/v1/templates/${templateId}/versions`,
      method: "GET",
    });
  },

  getLayoutConfig(templateId: string, version?: number): Promise<TemplateLayoutConfigResponse> {
    return apiRequest<TemplateLayoutConfigResponse>({
      url: `/api/v1/templates/${templateId}/layout-config`,
      method: "GET",
      params: version ? { version } : undefined,
    });
  },

  createLayoutConfigVersion(
    templateId: string,
    payload: TemplateLayoutConfigDraftRequest,
  ): Promise<TemplateVersionResponse> {
    return apiRequest<TemplateVersionResponse>({
      url: `/api/v1/templates/${templateId}/layout-config/versions`,
      method: "POST",
      data: payload,
    });
  },

  createVersion(templateId: string, payload: TemplateVersionUploadPayload): Promise<TemplateVersionResponse> {
    return apiRequest<TemplateVersionResponse>({
      url: `/api/v1/templates/${templateId}/versions`,
      method: "POST",
      data: buildVersionFormData(payload),
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  download(templateId: string): Promise<Blob> {
    return apiRequest<Blob>({
      url: `/api/v1/templates/${templateId}/download`,
      method: "GET",
      responseType: "blob",
    });
  },

  publishVersion(
    templateId: string,
    version: number,
    payload: TemplateVersionPublishRequest,
  ): Promise<TemplateVersionResponse> {
    return apiRequest<TemplateVersionResponse>({
      url: `/api/v1/templates/${templateId}/versions/${version}/publish`,
      method: "POST",
      data: payload,
    });
  },

  setDefaultVersion(
    templateId: string,
    version: number,
    payload: TemplateVersionDefaultRequest,
  ): Promise<TemplateVersionResponse> {
    return apiRequest<TemplateVersionResponse>({
      url: `/api/v1/templates/${templateId}/versions/${version}/set-default`,
      method: "POST",
      data: payload,
    });
  },

  disableVersion(templateId: string, version: number): Promise<TemplateVersionResponse> {
    return apiRequest<TemplateVersionResponse>({
      url: `/api/v1/templates/${templateId}/versions/${version}/disable`,
      method: "POST",
    });
  },
};
