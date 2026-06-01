// frontend/src/api/types.ts: TypeScript contracts for the backend v1 schemas used by MVP pages.
export type AuthLoginRequest = {
  username: string;
  password: string;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: string;
  user_id: string;
  username: string;
  tenant_id: string;
  company_id: string;
};

export type CurrentUserResponse = {
  id: string;
  username: string;
  role: string;
  tenant_id: string;
  company_id: string;
  display_name: string | null;
};

export type DocumentFileResponse = {
  id: string;
  tenant_id: string;
  company_id: string;
  job_id: string | null;
  file_type: string;
  storage_provider: string;
  bucket: string;
  object_key: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  checksum_sha256: string | null;
  etag: string | null;
  status: string;
  expires_at: string | null;
  metadata: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type FileUploadUrlRequest = {
  filename: string;
  mime_type: string;
  size_bytes: number;
  file_type?: "source_pdf";
  checksum_sha256?: string | null;
  job_id?: string | null;
};

export type FileUploadUrlResponse = {
  file_id: string;
  upload_url: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_at: string;
  object_key: string;
  max_bytes: number;
  file: DocumentFileResponse;
};

export type FileUploadResponse = {
  file: DocumentFileResponse;
};

export type DocumentJobMode = "direct_pdf_to_word" | "en2zh_pdf_to_word";
export type DocumentLanguage = "auto" | "zh" | "en";
export type DocumentJobStatus = "pending" | "queued" | "running" | "succeeded" | "failed" | "canceled";
export type DocumentJobStage =
  | "uploaded"
  | "parsing"
  | "parsed"
  | "ir_converting"
  | "rendering"
  | "uploading"
  | "completed"
  | "failed"
  | "canceled";

export type DocumentJobCreateRequest = {
  source_file_id: string;
  mode: DocumentJobMode;
  document_language: DocumentLanguage;
  template_version_id?: string | null;
  term_version_id?: string | null;
  debug_full_text?: boolean;
};

export type DocumentJobResponse = {
  id: string;
  tenant_id: string;
  company_id: string;
  created_by: string;
  source_file_id: string;
  mode: DocumentJobMode;
  document_language: string;
  status: DocumentJobStatus;
  stage: DocumentJobStage;
  progress: number;
  template_version_id: string;
  term_version_id: string | null;
  result_file_id: string | null;
  mineru_raw_result_file_id: string | null;
  document_ir_file_id: string | null;
  image_asset_file_ids: string[];
  debug_full_text_enabled: boolean;
  mineru_batch_id: string | null;
  mineru_data_id: string | null;
  failed_stage: DocumentJobStage | null;
  error_code: string | null;
  error_message: string | null;
  retry_count: number;
  timeout_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  canceled_at: string | null;
  request_snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type DocumentJobCreateResponse = {
  job_id: string;
  status: DocumentJobStatus;
  stage: DocumentJobStage;
  progress: number;
  job: DocumentJobResponse;
};

export type DocumentJobListResponse = {
  items: DocumentJobResponse[];
  page: number;
  page_size: number;
  total: number;
  summary: Record<string, number>;
};

export type DocumentJobEventResponse = {
  id: string;
  job_id: string;
  tenant_id: string;
  company_id: string;
  created_by: string;
  stage: DocumentJobStage;
  level: "info" | "warning" | "error";
  event_type: string;
  message: string;
  payload: Record<string, unknown>;
  duration_ms: number | null;
  trace_id: string | null;
  created_at: string;
};

export type DocumentJobEventListResponse = {
  job_id: string;
  items: DocumentJobEventResponse[];
};

export type DocumentJobDownloadUrlResponse = {
  job_id: string;
  file_id: string;
  download_url: string;
  method: "GET";
  expires_at: string;
  file: DocumentFileResponse;
};

export type DocumentJobRetryResponse = {
  job_id: string;
  status: DocumentJobStatus;
  stage: DocumentJobStage;
  progress: number;
  retry_count: number;
  job: DocumentJobResponse;
};
