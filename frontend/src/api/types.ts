// File: frontend/src/api/types.ts
// Purpose: Define TypeScript contracts for backend v1 schemas used by MVP and Admin pages.
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

export type HealthReadyResponse = {
  status: string;
  app_name: string;
  jobs_dir: string;
  dependency_checks: Record<string, unknown>;
};

export type HealthMetricsResponse = {
  status: string;
  app_name: string;
  generated_at: string;
  metadata_store: string;
  artifact_storage: string;
  worker_mode: string;
  stage_dispatcher: string;
  jobs: Record<string, number>;
  stage_messages: Record<string, number>;
  resources: Record<string, number | string | null>;
  audit_events: Record<string, number>;
};

export type AuditActorRole = "admin" | "operator" | "jobs" | "anonymous";
export type AuditEventSort = "created_at_desc" | "created_at_asc";

export type AuditEventListQuery = {
  page: number;
  page_size: number;
  sort?: AuditEventSort;
  actor_role?: AuditActorRole;
  action?: string;
  target_type?: string;
  target_id?: string;
  actor_id?: string;
  q?: string;
  created_from?: string;
  created_to?: string;
};

export type AuditEventResponse = {
  audit_id: string;
  actor_id: string | null;
  actor_role: AuditActorRole;
  action: string;
  target_type: string;
  target_id: string;
  reason: string | null;
  trace_id: string;
  created_at: string;
};

export type AuditEventListResponse = {
  items: AuditEventResponse[];
  page: number;
  page_size: number;
  total: number;
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

export type FileRetentionCandidateResponse = {
  file_id: string;
  job_id: string | null;
  file_type: string;
  storage_provider: string;
  bucket: string;
  object_key: string;
  size_bytes: number;
  status: string;
  expires_at: string;
  reason: string;
};

export type FileRetentionPlanResponse = {
  generated_at: string;
  retention_days: number;
  deletion_supported: boolean;
  action_mode: "dry_run" | "mark_expired";
  totals: Record<string, number>;
  candidates: FileRetentionCandidateResponse[];
  marked_file_ids: string[];
};

export type FileRetentionMarkExpiredResponse = FileRetentionPlanResponse;

export type FileRetentionDeletePreviewRequest = {
  file_ids: string[];
};

export type FileRetentionDeleteExecuteRequest = {
  file_ids: string[];
  reason: string;
  confirmation: string;
};

export type FileRetentionDeleteOutcome =
  | "deletable"
  | "deleted"
  | "already_missing"
  | "skipped_not_found"
  | "skipped_not_expired_status"
  | "skipped_not_expired_time"
  | "skipped_already_deleted"
  | "skipped_unsupported_storage"
  | "skipped_missing_object_key"
  | "failed";

export type FileRetentionDeleteItemResponse = {
  file_id: string;
  job_id: string | null;
  file_type: string | null;
  storage_provider: string | null;
  status_before: string | null;
  status_after: string | null;
  object_key: string | null;
  size_bytes: number | null;
  outcome: FileRetentionDeleteOutcome;
  reason: string;
  deleted: boolean;
  metadata_updated: boolean;
};

export type FileRetentionDeleteResponse = {
  generated_at: string;
  action_mode: "delete_preview" | "delete_execute";
  requested_file_ids: string[];
  confirmation_phrase: string;
  totals: Record<string, number>;
  items: FileRetentionDeleteItemResponse[];
};

export type FileRetentionPolicyScopeType = "global" | "file_type";
export type FileRetentionPolicyStatus = "draft" | "published" | "disabled";

export type FileRetentionPolicyCreateRequest = {
  name: string;
  scope_type: FileRetentionPolicyScopeType;
  file_type?: string | null;
  retention_days: number;
  description?: string | null;
};

export type FileRetentionPolicyUpdateRequest = {
  name?: string | null;
  scope_type?: FileRetentionPolicyScopeType | null;
  file_type?: string | null;
  retention_days?: number | null;
  description?: string | null;
};

export type FileRetentionPolicyReasonRequest = {
  reason: string;
};

export type EffectiveFileRetentionPolicyResponse = {
  retention_days: number;
  source: "published_policy" | "settings_fallback";
  policy_id: string | null;
  scope_type: FileRetentionPolicyScopeType | null;
  file_type: string | null;
  reason: string;
};

export type FileRetentionPolicyResponse = {
  policy_id: string;
  name: string;
  status: FileRetentionPolicyStatus;
  scope_type: FileRetentionPolicyScopeType;
  file_type: string | null;
  retention_days: number;
  description: string | null;
  is_default: boolean;
  is_effective: boolean;
  effective_reason: string | null;
  matching_file_count: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  published_by: string | null;
  published_at: string | null;
  disabled_by: string | null;
  disabled_at: string | null;
  reason: string | null;
};

export type FileRetentionPolicyListResponse = {
  generated_at: string;
  fallback_retention_days: number;
  effective: EffectiveFileRetentionPolicyResponse[];
  items: FileRetentionPolicyResponse[];
};

export type FileRetentionPolicyImpactPreviewRequest = {
  mode: "candidate_policy";
};

export type FileRetentionPolicyImpactItemResponse = {
  file_id: string;
  job_id: string | null;
  file_type: string;
  status: string;
  storage_provider: string;
  current_expires_at: string | null;
  projected_expires_at: string;
  currently_expired: boolean;
  would_be_expired: boolean;
  would_change_expires_at: boolean;
};

export type FileRetentionPolicyImpactResponse = {
  generated_at: string;
  policy: FileRetentionPolicyResponse;
  totals: Record<string, number>;
  items: FileRetentionPolicyImpactItemResponse[];
};

export type FileStorageUsageGroupResponse = {
  key: string;
  file_count: number;
  size_bytes: number;
  expired_count: number;
  expired_size_bytes: number;
  estimated_reclaimable_count: number;
  estimated_reclaimable_size_bytes: number;
};

export type FileStorageUsageResponse = {
  generated_at: string;
  artifact_storage: string;
  artifact_root_writable: boolean | null;
  artifact_disk_free_bytes: number | null;
  totals: Record<string, number>;
  reclaim: Record<string, number | string>;
  quota: Record<string, number | string | boolean | null>;
  by_storage_provider: FileStorageUsageGroupResponse[];
  by_file_type: FileStorageUsageGroupResponse[];
  by_status: FileStorageUsageGroupResponse[];
};

export type DocumentJobMode = "direct_pdf_to_word" | "en2zh_pdf_to_word";
export type DocumentLanguage = "auto" | "zh" | "en";
export type DocumentJobStatus = "pending" | "queued" | "running" | "succeeded" | "failed" | "canceled";
export type DocumentJobListSort = "created_at_desc" | "created_at_asc" | "updated_at_desc" | "updated_at_asc";
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
  term_rule_set_id?: string | null;
  term_rule_set_version?: string | null;
  translation_term_set_id?: string | null;
  translation_term_version?: string | null;
  translation_profile_id?: string | null;
  translation_profile_version?: string | null;
  debug_full_text?: boolean;
};

export type DocumentJobRetryRequest = {
  reason?: string | null;
  use_latest_term_assets?: boolean;
  term_rule_set_id?: string | null;
  term_rule_set_version?: string | null;
  translation_term_set_id?: string | null;
  translation_term_version?: string | null;
};

export type DocumentJobBulkAction = "retry" | "archive" | "cancel";

export type DocumentJobBulkJobIdsRequest = {
  job_ids: string[];
};

export type DocumentJobBulkRetryRequest = DocumentJobBulkJobIdsRequest & DocumentJobRetryRequest;

export type BoundResourceVersion = {
  resource_type: string;
  resource_id: string;
  version: string;
  status: string;
  snapshot_hash: string;
  payload_ref?: string | null;
};

export type BoundTranslationTermVersion = {
  set_id: string;
  language_pair: string;
  version: string;
  status: string;
  snapshot_hash: string;
  term_count: number;
};

export type DocumentJobResourceSnapshot = {
  template?: BoundResourceVersion | null;
  term_rule_set?: BoundResourceVersion | null;
  translation_term_set?: BoundTranslationTermVersion | null;
  translation_profile?: BoundResourceVersion | null;
  mineru?: Record<string, unknown>;
  artifact_ids?: Record<string, string>;
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
  archived_at: string | null;
  archived_by: string | null;
  translation_qa_status: TranslationQaStatus;
  translation_qa_issue_type: TranslationQaIssueType | null;
  translation_qa_note: string | null;
  translation_qa_reviewed_by: string | null;
  translation_qa_reviewed_at: string | null;
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

export type DocumentJobBulkItemResponse = {
  job_id: string;
  ok: boolean;
  status_code: number;
  error_code: string | null;
  detail: string | null;
  job: DocumentJobResponse | null;
};

export type DocumentJobBulkResponse = {
  action: DocumentJobBulkAction;
  total: number;
  succeeded: number;
  failed: number;
  items: DocumentJobBulkItemResponse[];
};

export type DocumentJobArchiveResponse = {
  job_id: string;
  archived_at: string;
  job: DocumentJobResponse;
};

export type DocumentJobCancelResponse = {
  job_id: string;
  status: DocumentJobStatus;
  stage: DocumentJobStage;
  canceled_at: string;
  job: DocumentJobResponse;
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

export type DocumentJobFileListResponse = {
  job_id: string;
  files: DocumentFileResponse[];
};

export type TranslationQaStatus = "unreviewed" | "approved" | "needs_fix" | "blocked";
export type TranslationQaIssueType =
  | "translation"
  | "terminology"
  | "layout"
  | "source_quality"
  | "artifact_missing"
  | "other";

export type DocumentJobTranslationQaStateResponse = {
  status: TranslationQaStatus;
  issue_type: TranslationQaIssueType | null;
  note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
};

export type DocumentJobTranslationQaArtifactsResponse = {
  document_ir_file_id: string | null;
  ai_call_log_file_ids: string[];
  ai_debug_archive_file_ids: string[];
};

export type DocumentJobTranslationQaSummaryResponse = {
  final_segment_count: number;
  returned_segment_count: number;
  quality_flags: string[];
  ai_call_count: number;
  ai_call_statuses: Record<string, number>;
  term_trace_count: number;
  source_comparison_available: boolean;
  source_comparison_reason: string | null;
};

export type DocumentJobTranslationQaSegmentResponse = {
  id: string;
  block_id: string;
  page_index: number | null;
  order: number;
  block_type: string;
  field: string;
  index: number | null;
  source_text: string | null;
  ai_translation_text: string | null;
  final_text: string;
  source_available: boolean;
};

export type DocumentJobTranslationQaTermTraceResponse = {
  segment_id: string | null;
  batch_id: string | null;
  translation_term_set_id: string | null;
  translation_term_version: string | null;
  source_term: string | null;
  target_term: string | null;
  match_start: number | null;
  match_end: number | null;
  context: Record<string, unknown> | null;
  injected_to_glossary: boolean;
  provider_trace_id: string | null;
};

export type DocumentJobTranslationQaAiCallResponse = {
  file_id: string;
  call_id: string | null;
  status: string | null;
  provider: Record<string, unknown>;
  language_pair: string | null;
  source_language: string | null;
  target_language: string | null;
  term_version_id: string | null;
  term_snapshot_hash: string | null;
  term_count: number;
  item_count: number;
  char_count: number;
  duration_ms: number | null;
  created_at: string | null;
  error_type: string | null;
  error_message: string | null;
};

export type DocumentJobTranslationQaResponse = {
  job_id: string;
  available: boolean;
  availability_reason: string | null;
  qa: DocumentJobTranslationQaStateResponse;
  artifacts: DocumentJobTranslationQaArtifactsResponse;
  summary: DocumentJobTranslationQaSummaryResponse;
  segments: DocumentJobTranslationQaSegmentResponse[];
  term_traces: DocumentJobTranslationQaTermTraceResponse[];
  ai_calls: DocumentJobTranslationQaAiCallResponse[];
};

export type DocumentJobTranslationQaUpdateRequest = {
  status: TranslationQaStatus;
  issue_type?: TranslationQaIssueType | null;
  note?: string | null;
};

export type DocumentJobTranslationQaUpdateResponse = {
  job_id: string;
  qa: DocumentJobTranslationQaStateResponse;
  job: DocumentJobResponse;
};

export type DocumentJobConfigVersionOption = {
  resource_id: string;
  version: string;
  label: string;
  status: string;
  is_default: boolean;
  snapshot_hash?: string | null;
  summary: Record<string, unknown>;
};

export type DocumentJobConfigDefaults = {
  template?: DocumentJobConfigVersionOption | null;
  term_rule_set?: DocumentJobConfigVersionOption | null;
  translation_term_set?: DocumentJobConfigVersionOption | null;
  translation_profile?: DocumentJobConfigVersionOption | null;
};

export type DocumentJobConfigOptions = {
  templates: DocumentJobConfigVersionOption[];
  term_rule_sets: DocumentJobConfigVersionOption[];
  translation_term_sets: DocumentJobConfigVersionOption[];
  translation_profiles: DocumentJobConfigVersionOption[];
};

export type DocumentJobConfigSummaryResponse = {
  role: string;
  resource_mode: "legacy" | "versioned";
  defaults: DocumentJobConfigDefaults;
  options: DocumentJobConfigOptions;
  readiness: {
    en2zh_available: boolean;
    warnings: string[];
  };
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

export type TemplateAssetResponse = {
  label: string;
  exists: boolean;
  file_name: string | null;
  size_bytes: number | null;
  updated_at: string | null;
  sha256: string | null;
  download_url: string | null;
};

export type TemplateListItemResponse = {
  id: string;
  name: string;
  description: string;
  version: number;
  is_default: boolean;
  downloadable: boolean;
  download_url: string | null;
  template: TemplateAssetResponse;
  layout_config: TemplateAssetResponse;
  subscript_config: TemplateAssetResponse;
};

export type TemplateDetailResponse = TemplateListItemResponse;

export type TemplateListResponse = {
  items: TemplateListItemResponse[];
};

export type TemplateVersionStatus = "draft" | "published" | "disabled" | string;

export type TemplateVersionResponse = {
  template_id: string | null;
  template_version_id: string | null;
  version: number;
  status: TemplateVersionStatus;
  is_current: boolean;
  is_default: boolean;
  snapshot_hash: string | null;
  render_policy: Record<string, unknown>;
  verification_job_id: string | null;
  verification_note: string | null;
  verified_by: string | null;
  verified_at: string | null;
  publish_reason: string | null;
  published_by: string | null;
  published_at: string | null;
  template: TemplateAssetResponse;
  layout_config: TemplateAssetResponse | null;
};

export type TemplateVersionListResponse = {
  template_id: string;
  items: TemplateVersionResponse[];
};

export type TemplateVersionPublishRequest = {
  make_default: false;
  publish_reason: string;
  verification_job_id: string;
  verification_note: string;
};

export type TemplateVersionDefaultRequest = {
  set_default_reason: string;
};

export type TermRuleRenderType = "plain" | "subscript" | "superscript";

export type TermRuleCategoryListItemResponse = {
  id: string;
  code: string;
  name: string;
  priority: number;
  enabled: boolean;
  description: string;
  rule_count: number;
  enabled_rule_count: number;
};

export type TermRuleCategoryListResponse = {
  items: TermRuleCategoryListItemResponse[];
};

export type TermRuleSegmentResponse = {
  seq: number;
  segment_text: string;
  render_type: TermRuleRenderType;
};

export type TermRuleSegmentWriteRequest = {
  segment_text: string;
  render_type: TermRuleRenderType;
};

export type TermRuleResponse = {
  id: string;
  category_id: string;
  category_code: string;
  category_name: string;
  source_term: string;
  rule_mode: string;
  apply_scope: string;
  case_sensitive: boolean;
  enabled: boolean;
  priority: number;
  segments: TermRuleSegmentResponse[];
  custom_html: string | null;
  custom_markdown: string | null;
  notes: string;
};

export type TermRuleListResponse = {
  items: TermRuleResponse[];
  page: number;
  page_size: number;
  total: number;
};

export type TermRuleCreateRequest = {
  id?: string | null;
  category_id: string;
  source_term: string;
  apply_scope?: string;
  case_sensitive?: boolean;
  enabled?: boolean;
  priority?: number;
  segments: TermRuleSegmentWriteRequest[];
  custom_html?: string | null;
  custom_markdown?: string | null;
  notes?: string;
};

export type TermRuleUpdateRequest = {
  category_id?: string | null;
  source_term?: string | null;
  apply_scope?: string | null;
  case_sensitive?: boolean | null;
  enabled?: boolean | null;
  priority?: number | null;
  segments?: TermRuleSegmentWriteRequest[] | null;
  custom_html?: string | null;
  custom_markdown?: string | null;
  notes?: string | null;
};

export type RuleSimulationRequest = {
  text: string;
};

export type RuleSimulationResponse = {
  original: string;
  markdown_preview: string;
  html_preview: string;
};

export type TermRuleProposalIntent = "create" | "update" | "disable";
export type TermRuleProposalStatus = "pending_review" | "approved" | "rejected" | "published";

export type TermRuleProposalCreateRequest = {
  intent: TermRuleProposalIntent;
  source_term?: string | null;
  category_id?: string | null;
  segments?: TermRuleSegmentWriteRequest[] | null;
  reason: string;
  source_job_id?: string | null;
  source_file_id?: string | null;
  page_number?: number | null;
  context_before?: string | null;
  context_after?: string | null;
  observed_term_rule_set_id?: string | null;
  observed_term_rule_version?: string | null;
  target_rule_id?: string | null;
};

export type TermRuleProposalApproveAndPublishRequest = {
  review_comment?: string | null;
  publish_reason?: string | null;
};

export type TermRuleProposalBulkAction = "approve" | "reject";

export type TermRuleProposalBulkReviewRequest = {
  proposal_ids: string[];
  review_comment?: string | null;
};

export type TermRuleProposalBulkRejectRequest = {
  proposal_ids: string[];
  review_comment: string;
};

export type TermRuleProposalResponse = {
  id: string;
  intent: TermRuleProposalIntent;
  status: TermRuleProposalStatus;
  source_term: string;
  category_id: string;
  segments: TermRuleSegmentResponse[];
  reason: string;
  source_job_id: string | null;
  source_file_id: string | null;
  page_number: number | null;
  context_before: string | null;
  context_after: string | null;
  observed_term_rule_set_id: string | null;
  observed_term_rule_version: string | null;
  target_rule_id: string | null;
  target_rule_snapshot: Record<string, unknown> | null;
  created_by: string;
  created_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_comment: string | null;
  merged_term_rule_set_id: string | null;
  merged_draft_snapshot_hash: string | null;
  published_term_rule_set_id: string | null;
  published_term_rule_set_version: string | null;
  published_at: string | null;
};

// 描述 Term Rule Proposal 审核冲突的稳定分类。
export type TermRuleProposalConflictType =
  | "stale_target_rule"
  | "missing_target_rule"
  | "source_term_segments_conflict";

// 描述 Term Rule Proposal 审核时发现的一条结构化冲突。
export type TermRuleProposalConflictItemResponse = {
  type: TermRuleProposalConflictType;
  message: string;
  proposal_id: string;
  target_rule_id: string | null;
  source_term: string;
  category_id: string;
  current_rule: TermRuleResponse | null;
  target_rule_snapshot: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
};

// 返回 Term Rule Proposal 审核冲突的稳定 409 响应 payload。
export type TermRuleProposalConflictResponse = {
  code: "term_rule_proposal_conflict";
  message: string;
  conflicts: TermRuleProposalConflictItemResponse[];
};

export type TermRuleProposalListResponse = {
  items: TermRuleProposalResponse[];
  total: number;
};

export type TermRuleProposalBulkItemResponse = {
  proposal_id: string;
  ok: boolean;
  status_code: number;
  error_code: string | null;
  detail: string | TermRuleProposalConflictResponse | Record<string, unknown> | null;
  proposal: TermRuleProposalResponse | null;
};

export type TermRuleProposalBulkResponse = {
  action: TermRuleProposalBulkAction;
  total: number;
  succeeded: number;
  failed: number;
  items: TermRuleProposalBulkItemResponse[];
};

export type TermRuleSetListItemResponse = {
  id: string;
  default_version: string | null;
  version_count: number;
  rule_count: number;
  enabled_rule_count: number;
};

export type TermRuleSetListResponse = {
  items: TermRuleSetListItemResponse[];
};

export type TermRuleSetVersionResponse = {
  term_rule_set_id: string;
  version: string;
  status: string;
  rule_count: number;
  enabled_rule_count: number;
  snapshot_hash: string | null;
  is_default: boolean;
  published_by: string | null;
  publish_reason: string | null;
  published_at: string | null;
};

export type TermRuleSetDetailResponse = {
  id: string;
  default_version: string | null;
  versions: TermRuleSetVersionResponse[];
};

export type TermRuleSetDraftResponse = {
  term_rule_set_id: string;
  base_version: string | null;
  rule_count: number;
  enabled_rule_count: number;
  yaml_text: string;
  snapshot_hash: string | null;
};

export type TermRuleDraftRuleMutationResponse = {
  rule: TermRuleResponse;
  draft: TermRuleSetDraftResponse;
};

export type TermRuleDraftRuleDeleteResponse = {
  id: string;
  removed: boolean;
  draft: TermRuleSetDraftResponse;
};

export type TermRuleSetVersionRefResponse = {
  ref: string;
  version: string;
  snapshot_hash: string | null;
  rule_count: number;
  enabled_rule_count: number;
};

export type TermRuleSetDiffSummaryResponse = {
  added: number;
  updated: number;
  disabled: number;
  removed: number;
  unchanged: number;
  total: number;
};

export type TermRuleSetDiffItemResponse = {
  change_type: "added" | "updated" | "disabled" | "removed" | "unchanged";
  rule_id: string;
  source_term: string;
  category_id: string;
  changed_fields: string[];
  before: TermRuleResponse | null;
  after: TermRuleResponse | null;
};

export type TermRuleSetDiffResponse = {
  term_rule_set_id: string;
  base_ref: TermRuleSetVersionRefResponse;
  target_ref: TermRuleSetVersionRefResponse;
  summary: TermRuleSetDiffSummaryResponse;
  items: TermRuleSetDiffItemResponse[];
};

export type TermRuleGovernanceFindingResponse = {
  severity: "error" | "warning" | "conflict";
  code: string;
  message: string;
  path: string | null;
  rule_id: string | null;
  source_term: string | null;
  category_id: string | null;
  metadata: Record<string, unknown>;
};

export type TermRuleSetPreflightSummaryResponse = {
  error_count: number;
  warning_count: number;
  conflict_count: number;
  rule_count: number;
  enabled_rule_count: number;
};

export type TermRuleSetPreflightResponse = {
  term_rule_set_id: string;
  valid: boolean;
  blocking: boolean;
  base_ref: TermRuleSetVersionRefResponse;
  draft_ref: TermRuleSetVersionRefResponse;
  summary: TermRuleSetPreflightSummaryResponse;
  errors: TermRuleGovernanceFindingResponse[];
  warnings: TermRuleGovernanceFindingResponse[];
  conflicts: TermRuleGovernanceFindingResponse[];
  diff_summary: TermRuleSetDiffSummaryResponse;
};

export type TermRuleSetPublishRequest = {
  make_default: boolean;
  publish_reason: string;
};

export type TermRuleSetDraftUpdateRequest = {
  yaml_text: string;
};

export type TermRuleSetRollbackRequest = {
  version: string;
};

export type TranslationProfileListItemResponse = {
  id: string;
  default_version: string | null;
  version_count: number;
  target_language: string;
  domain: string;
  prompt_version: string;
  model: string | null;
  max_pages_per_batch: number;
  max_chars_per_batch: number;
};

export type TranslationProfileListResponse = {
  items: TranslationProfileListItemResponse[];
};

export type TranslationProfileVersionResponse = {
  translation_profile_id: string;
  version: string;
  status: string;
  snapshot_hash: string | null;
  is_default: boolean;
  target_language: string;
  domain: string;
  prompt_version: string;
  model: string | null;
  max_pages_per_batch: number;
  max_chars_per_batch: number;
  published_at: string | null;
};

export type TranslationProfileDetailResponse = {
  id: string;
  default_version: string | null;
  versions: TranslationProfileVersionResponse[];
};

export type TranslationProfileDraftResponse = {
  translation_profile_id: string;
  base_version: string | null;
  target_language: string;
  domain: string;
  prompt_version: string;
  model: string | null;
  max_pages_per_batch: number;
  max_chars_per_batch: number;
  snapshot_hash: string | null;
};

export type TranslationProfileDraftUpdateRequest = {
  target_language: string;
  domain: string;
  prompt_version: string;
  model: string | null;
  max_pages_per_batch: number;
  max_chars_per_batch: number;
};

export type TranslationProfilePublishRequest = {
  make_default: boolean;
};

export type TranslationProfileRollbackRequest = {
  version: string;
};

export type TranslationTermValidationFindingResponse = {
  code: string;
  message: string;
  normalized_source_term: string | null;
};

export type TranslationTermValidationReportResponse = {
  valid: boolean;
  errors: TranslationTermValidationFindingResponse[];
  warnings: TranslationTermValidationFindingResponse[];
};

export type TranslationTermSetImportDuplicateResponse = {
  row_number: number;
  kept_row_number: number;
  source_term: string;
  normalized_source_term: string;
};

export type TranslationTermSetImportReportResponse = {
  dedupe: string;
  total_rows: number;
  imported_rows: number;
  duplicate_rows: number;
  duplicates: TranslationTermSetImportDuplicateResponse[];
};

export type TranslationTermSetImportRequest = {
  csv_text: string;
  target?: "draft" | "seed";
  dedupe?: "reject" | "keep_first";
};

export type TranslationTermSetImportResponse = {
  target: string;
  set_id: string;
  language_pair: string;
  version: string;
  term_count: number;
  snapshot_hash: string;
  validation: TranslationTermValidationReportResponse;
  import_report: TranslationTermSetImportReportResponse;
};

export type TranslationTermSetExportManifestResponse = {
  set_id: string;
  language_pair: string;
  version: string;
  format: string;
  exported_at: string;
  exported_by: string | null;
};

export type TranslationTermSetExportResponse = {
  manifest: TranslationTermSetExportManifestResponse;
  csv_text: string;
};

export type TranslationTermEntryResponse = {
  language_pair: string;
  source_term: string;
  normalized_source_term: string;
  target_term: string;
  version: string;
  set_id: string;
  case_sensitive: boolean;
  status: string;
  priority: number;
  domain: string | null;
  category: string | null;
  note: string;
};

export type TranslationTermSetListItemResponse = {
  set_id: string;
  language_pair: string;
  default_version: string | null;
  draft_version: string | null;
  version_count: number;
  default_term_count: number;
  draft_term_count: number;
  snapshot_hash: string | null;
};

export type TranslationTermSetListResponse = {
  items: TranslationTermSetListItemResponse[];
};

export type TranslationTermSetVersionResponse = {
  set_id: string;
  language_pair: string;
  version: string;
  status: string;
  snapshot_hash: string | null;
  term_count: number;
  is_default: boolean;
  published_by: string | null;
  published_at: string | null;
  release_note: string | null;
  created_at: string;
  updated_at: string;
};

export type TranslationTermSetDetailResponse = {
  set_id: string;
  language_pair: string;
  default_version: string | null;
  draft_version: string | null;
  versions: TranslationTermSetVersionResponse[];
};

export type TranslationTermSetDraftResponse = {
  set_id: string;
  language_pair: string;
  version: string;
  base_version: string | null;
  term_count: number;
  snapshot_hash: string;
  validation: TranslationTermValidationReportResponse;
  entries: TranslationTermEntryResponse[];
};

export type TranslationTermSetDiffSummaryResponse = {
  added: number;
  removed: number;
  changed: number;
  unchanged: number;
  total_before: number;
  total_after: number;
};

export type TranslationTermSetDiffEntryPayload = Record<string, string | number | boolean | null>;

export type TranslationTermSetDiffEntryResponse = {
  kind: "added" | "removed" | "changed" | "unchanged";
  normalized_source_term: string;
  source_term: string;
  changed_fields: string[];
  before: TranslationTermSetDiffEntryPayload | null;
  after: TranslationTermSetDiffEntryPayload | null;
};

export type TranslationTermSetDiffResponse = {
  set_id: string;
  language_pair: string;
  base_version: string;
  target_version: string;
  summary: TranslationTermSetDiffSummaryResponse;
  items: TranslationTermSetDiffEntryResponse[];
};

export type TranslationTermSetPreflightResponse = {
  set_id: string;
  language_pair: string;
  base_version: string;
  target_version: string;
  publish_blocked: boolean;
  blocking_reasons: string[];
  validation: TranslationTermValidationReportResponse;
  diff_summary: TranslationTermSetDiffSummaryResponse;
};

export type TranslationTermSetPublishRequest = {
  make_default: boolean;
  release_note?: string | null;
};

export type TranslationTermSetRollbackRequest = {
  version: string;
};

export type TranslationTermProposalCompatibilityFindingResponse = {
  severity: "warning" | "conflict";
  code: string;
  message: string;
  normalized_source_term: string | null;
  action: string | null;
  current_entry: TranslationTermSetDiffEntryPayload | null;
  observed_entry: TranslationTermSetDiffEntryPayload | null;
};

export type TranslationTermProposalCompatibilityItemResponse = {
  proposal_id: string;
  compatibility: "compatible" | "warning" | "conflict";
  observed_version: string | null;
  change_count: number;
  conflicts: TranslationTermProposalCompatibilityFindingResponse[];
  warnings: TranslationTermProposalCompatibilityFindingResponse[];
};

export type TranslationTermProposalCompatibilitySummaryResponse = {
  total: number;
  compatible: number;
  warning: number;
  conflict: number;
};

export type TranslationTermProposalCompatibilityResponse = {
  set_id: string;
  language_pair: string;
  summary: TranslationTermProposalCompatibilitySummaryResponse;
  items: TranslationTermProposalCompatibilityItemResponse[];
};

export type TranslationTermProposalStatus = "pending" | "approved" | "rejected" | "published";
export type TranslationTermProposalAction = "add" | "update" | "delete";

export type TranslationTermProposalChangeRequest = {
  action: TranslationTermProposalAction;
  source_term: string;
  target_term?: string | null;
  case_sensitive?: boolean | null;
  status?: string | null;
  priority?: number | null;
  domain?: string | null;
  category?: string | null;
  note?: string | null;
};

export type TranslationTermProposalCreateRequest = {
  language_pair?: string;
  source_job_id?: string | null;
  source_file_id?: string | null;
  observed_translation_term_set_id?: string | null;
  observed_translation_term_version?: string | null;
  changes: TranslationTermProposalChangeRequest[];
};

export type TranslationTermProposalReviewRequest = {
  review_note?: string | null;
};

export type TranslationTermProposalApproveAndPublishRequest = {
  review_note?: string | null;
  release_note?: string | null;
};

export type TranslationTermProposalRejectRequest = {
  review_note: string;
};

export type TranslationTermProposalBulkAction = "approve" | "reject";

export type TranslationTermProposalBulkReviewRequest = {
  proposal_ids: string[];
  review_note?: string | null;
};

export type TranslationTermProposalBulkRejectRequest = {
  proposal_ids: string[];
  review_note: string;
};

export type TranslationTermProposalChangeResponse = {
  seq: number;
  action: TranslationTermProposalAction;
  source_term: string;
  normalized_source_term: string;
  target_term: string | null;
  case_sensitive: boolean | null;
  status: string | null;
  priority: number | null;
  domain: string | null;
  category: string | null;
  note: string | null;
};

export type TranslationTermProposalResponse = {
  id: string;
  status: TranslationTermProposalStatus;
  submitted_by: string;
  source_job_id: string | null;
  source_file_id: string | null;
  observed_translation_term_set_id: string | null;
  observed_translation_term_version: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  published_translation_term_set_id: string | null;
  published_translation_term_version: string | null;
  published_at: string | null;
  changes: TranslationTermProposalChangeResponse[];
  created_at: string;
};

export type TranslationTermProposalListResponse = {
  items: TranslationTermProposalResponse[];
  total: number;
};

export type TranslationTermProposalConflictResponse = {
  code: "translation_term_proposal_conflict";
  message: string;
  conflicts: TranslationTermProposalCompatibilityFindingResponse[];
};

export type TranslationTermProposalBulkItemResponse = {
  proposal_id: string;
  ok: boolean;
  status_code: number;
  error_code: string | null;
  detail: string | TranslationTermProposalConflictResponse | Record<string, unknown> | null;
  proposal: TranslationTermProposalResponse | null;
};

export type TranslationTermProposalBulkResponse = {
  action: TranslationTermProposalBulkAction;
  total: number;
  succeeded: number;
  failed: number;
  items: TranslationTermProposalBulkItemResponse[];
};
