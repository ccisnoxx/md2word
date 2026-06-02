// frontend/src/api/templates.ts: Template Profile API wrappers for V2.1 config management.
import { apiRequest } from "@/api/client";
import type {
  TemplateDetailResponse,
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
