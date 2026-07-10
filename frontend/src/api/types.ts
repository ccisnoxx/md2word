// File: frontend/src/api/types.ts
// Purpose: 定义后端 v1 schema 和运维请求对应的 TypeScript 合同。
export type AuthLoginRequest = {
  username: string;
  password: string;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: string;
  roles?: string[];
  permissions?: string[];
  user_id: string;
  username: string;
  tenant_id: string;
  company_id: string;
  department_id?: string;
};

export type CurrentUserResponse = {
  id: string;
  username: string;
  role: string;
  roles: string[];
  permissions: string[];
  tenant_id: string;
  company_id: string;
  department_id?: string;
  display_name: string | null;
};

export type AuthChangePasswordRequest = {
  current_password: string;
  new_password: string;
};

export type InternalUserRole = "admin" | "operator";
export type InternalUserStatus = "active" | "disabled";

export type InternalUserResponse = {
  id: string;
  username: string;
  normalized_username: string;
  role: InternalUserRole;
  tenant_id: string;
  company_id: string;
  department_id: string;
  status: InternalUserStatus;
  display_name: string | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  updated_by: string | null;
};

export type InternalUserListResponse = {
  items: InternalUserResponse[];
  total: number;
};

export type InternalUserCreateRequest = {
  username: string;
  display_name?: string | null;
  department_id?: string;
  role: InternalUserRole;
  status: InternalUserStatus;
  initial_password: string;
};

export type InternalUserUpdateRequest = {
  display_name?: string | null;
  department_id?: string | null;
  role?: InternalUserRole | null;
  status?: InternalUserStatus | null;
};

export type InternalUserResetPasswordRequest = {
  new_password: string;
};

export type InternalUserListQuery = {
  role?: InternalUserRole;
  status?: InternalUserStatus;
  keyword?: string;
};

export type HealthReadyResponse = {
  status: string;
  app_name: string;
  deployment: HealthDeploymentInfo;
  jobs_dir: string;
  dependency_checks: Record<string, unknown>;
};

export type HealthDeploymentInfo = {
  environment: string;
  public_deployment_mode: string;
  version: string;
  deployment_id: string | null;
  started_at: string;
};

export type HealthMetricsResponse = {
  status: string;
  app_name: string;
  generated_at: string;
  deployment: HealthDeploymentInfo;
  metadata_store: string;
  artifact_storage: string;
  worker_mode: string;
  stage_dispatcher: string;
  jobs: Record<string, number>;
  document_jobs: Record<string, number>;
  stage_messages: Record<string, number>;
  document_job_callback_messages: Record<string, number>;
  resources: Record<string, number | string | null>;
  audit_events: Record<string, number>;
};

export type AiProviderBackend = "disabled" | "openai_compatible";

export type AiProviderConfigResponse = {
  backend: AiProviderBackend;
  base_url: string | null;
  model: string;
  timeout_seconds: number;
  max_output_tokens: number;
  api_key_configured: boolean;
  api_key_mask: string | null;
  source: "settings" | "runtime_config";
  updated_at: string | null;
  updated_by: string | null;
};

export type AiProviderConfigUpdateRequest = {
  backend: AiProviderBackend;
  base_url?: string | null;
  model?: string | null;
  timeout_seconds?: number | null;
  max_output_tokens?: number | null;
  api_key?: string | null;
  clear_api_key?: boolean;
};

export type MinerUConfigResponse = {
  api_token_configured: boolean;
  uid_configured: boolean;
  source: "settings" | "runtime_config";
  updated_at: string | null;
  updated_by: string | null;
};

export type MinerUConfigUpdateRequest = {
  api_token: string;
  uid: string;
};

export type AcceptanceRunTier = "P0" | "P1" | "P2" | (string & {});
export type AcceptanceRunStatus = "passed" | "failed" | "unknown" | (string & {});
export type AcceptanceReviewDecision = "approved" | "rejected" | "needs_changes";
export type AcceptanceLatestOverallStatus = "accepted" | "blocked" | "incomplete" | "needs_attention";
export type AcceptanceRunRiskLevel = "success" | "warning" | "danger" | "unknown";

export type AcceptanceRunResponse = {
  id: string;
  title: string;
  tier: AcceptanceRunTier;
  status: AcceptanceRunStatus;
  environment: string;
  source: string;
  report_path_or_url: string | null;
  started_at: string | null;
  finished_at: string | null;
  summary: string | null;
  blockers: string[];
  warnings: string[];
  reviewer: string | null;
  decision: AcceptanceReviewDecision | null;
  reviewed_at: string | null;
  review_note: string | null;
  updated_at: string;
};

export type AcceptanceRunListResponse = {
  items: AcceptanceRunResponse[];
  total: number;
};

export type AcceptanceRunUpsertRequest = {
  id: string;
  title: string;
  tier: AcceptanceRunTier;
  status: AcceptanceRunStatus;
  environment: string;
  source: string;
  report_path_or_url?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  summary?: string | null;
  blockers: string[];
  warnings: string[];
};

export type AcceptanceLatestTierSummaryResponse = {
  tier: AcceptanceRunTier;
  run: AcceptanceRunResponse | null;
  missing: boolean;
  risk_level: AcceptanceRunRiskLevel;
  blockers: string[];
  warnings: string[];
};

export type AcceptanceLatestSummaryResponse = {
  overall_status: AcceptanceLatestOverallStatus;
  missing_tiers: AcceptanceRunTier[];
  blocker_count: number;
  warning_count: number;
  latest_reviewed_run: AcceptanceRunResponse | null;
  tiers: AcceptanceLatestTierSummaryResponse[];
  generated_at: string;
};

export type AcceptanceReviewRequest = {
  decision: AcceptanceReviewDecision;
  note?: string | null;
};

export type HealthOpsStatus = "ok" | "watch" | "needs_attention";
export type HealthOpsAlertSeverity = "info" | "warning" | "critical";
export type HealthOpsAlertSource = "readiness" | "stage_spool" | "jobs" | "document_job_callbacks";

export type HealthOpsAlertSummary = {
  readiness_blockers: number;
  readiness_warnings: number;
  stage_failed_messages: number;
  stage_stale_running_messages: number;
  stage_replayable_messages: number;
  callback_failed_messages: number;
  callback_replayable_messages: number;
  callback_oldest_replayable_age_seconds: number;
  failed_jobs: number;
  running_jobs: number;
  worker_mode: string;
  stage_dispatcher: string;
  stage_message_store: string;
  artifact_storage: string;
};

export type HealthOpsAlertItem = {
  code: string;
  severity: HealthOpsAlertSeverity;
  source: HealthOpsAlertSource;
  title: string;
  description: string;
  count: number;
  suggested_route: string | null;
  suggested_action: string;
};

export type HealthOpsAlertSafety = {
  read_only: boolean;
  writes_performed: boolean;
  recovery_actions_executed: boolean;
  provider_calls_executed: boolean;
  notification_delivery_executed: boolean;
  audit_events_written: boolean;
};

export type HealthOpsAlertsResponse = {
  status: HealthOpsStatus;
  app_name: string;
  generated_at: string;
  summary: HealthOpsAlertSummary;
  alerts: HealthOpsAlertItem[];
  safety: HealthOpsAlertSafety;
};

export type OpsAlertDeliveryChannel = "local_outbox" | "slack";
export type OpsAlertDeliveryMode = "dry_run" | "fake_send" | "real_send_preview" | "real_send";
export type OpsAlertDeliveryOutcome =
  | "deliverable"
  | "fake_delivered"
  | "sent"
  | "deduped"
  | "blocked"
  | "rate_limited"
  | "skipped_not_active"
  | "skipped_rate_limited"
  | "failed"
  | "timed_out";

export type OpsAlertDeliveryPreviewRequest = {
  alert_codes: string[];
  channel?: OpsAlertDeliveryChannel;
  dedupe_window_minutes?: number;
};

export type OpsAlertDeliveryFakeSendRequest = OpsAlertDeliveryPreviewRequest & {
  reason: string;
  confirmation: string;
};

export type OpsAlertDeliveryRealPreviewRequest = {
  alert_codes: string[];
  destination_ids: string[];
  dedupe_window_minutes?: number;
};

export type OpsAlertDeliveryRealSendRequest = OpsAlertDeliveryRealPreviewRequest & {
  reason: string;
  confirmation: string;
};

export type OpsAlertDeliverySafetyResponse = {
  external_delivery_executed: boolean;
  provider_calls_executed: boolean;
  cleanup_executed: boolean;
  delete_executed: boolean;
  conversion_workflow_executed: boolean;
  audit_events_written: boolean;
  secret_values_exposed: boolean;
};

export type OpsAlertDeliveryAdapterResultResponse = {
  contract_version: string;
  adapter_id: string;
  adapter_mode: "fake" | "real";
  channel: OpsAlertDeliveryChannel;
  alert_code: string;
  operation_id: string;
  idempotency_key: string;
  dedupe_key: string;
  timeout_seconds: number;
  outcome: OpsAlertDeliveryOutcome;
  provider_request_id: string | null;
  error_code: string | null;
  retryable: boolean;
  provider_calls_executed: boolean;
  external_delivery_executed: boolean;
  payload_persisted: boolean;
  secret_values_exposed: boolean;
};

export type OpsAlertDeliveryAdapterContractSafetyResponse = {
  read_only: boolean;
  provider_calls_executed: boolean;
  external_delivery_executed: boolean;
  audit_events_written: boolean;
  cleanup_executed: boolean;
  delete_executed: boolean;
  conversion_workflow_executed: boolean;
  secret_values_exposed: boolean;
};

export type OpsAlertDeliveryAdapterContractResponse = {
  generated_at: string;
  action_mode: "adapter_contract";
  contract_version: string;
  fake_adapter_id: string;
  fake_adapter_mode: "fake";
  real_channels: OpsAlertDestinationChannel[];
  required_request_fields: string[];
  required_result_fields: string[];
  required_audit_fields: string[];
  required_safety_fields: string[];
  parity_checks: Record<string, boolean>;
  destination_count: number;
  destination_channels: OpsAlertDestinationChannel[];
  blocking_reasons: string[];
  safety: OpsAlertDeliveryAdapterContractSafetyResponse;
};

export type OpsS3DeleteLocalStackProfileResponse = {
  harness: "localstack";
  endpoint_required: boolean;
  versioned_bucket_required: boolean;
  exact_bucket_key_required: boolean;
  version_id_supported: boolean;
  etag_precondition_supported: boolean;
  runtime_executed: boolean;
  provider_payload_persisted: boolean;
  secrets_required_for_contract_report: boolean;
};

export type OpsS3DeleteAdapterContractSafetyResponse = {
  read_only: boolean;
  provider_calls_executed: boolean;
  real_s3_delete_executed: boolean;
  localstack_calls_executed: boolean;
  cleanup_executed: boolean;
  scheduler_loop_executed: boolean;
  delete_executed: boolean;
  metadata_mutated: boolean;
  audit_events_written: boolean;
  conversion_workflow_executed: boolean;
  secret_values_exposed: boolean;
};

export type OpsS3DeleteAdapterContractResponse = {
  generated_at: string;
  action_mode: "adapter_contract";
  contract_version: string;
  fake_adapter_id: string;
  fake_adapter_mode: "fake";
  fake_file_retention_contract_version: string;
  localstack_profile: OpsS3DeleteLocalStackProfileResponse;
  storage_config_summary: Record<string, string | boolean>;
  required_request_fields: string[];
  required_result_fields: string[];
  required_audit_fields: string[];
  required_safety_fields: string[];
  parity_checks: Record<string, boolean>;
  blocking_reasons: string[];
  safety: OpsS3DeleteAdapterContractSafetyResponse;
};

export type OpsAlertDeliveryItemResponse = {
  alert_code: string;
  destination_id: string | null;
  target_label: string | null;
  severity: string | null;
  source: string | null;
  title: string | null;
  outcome: OpsAlertDeliveryOutcome;
  dedupe_key: string | null;
  idempotency_key: string | null;
  missing_gates: string[];
  reason: string;
  audit_event_written: boolean;
  adapter_result: OpsAlertDeliveryAdapterResultResponse | null;
};

export type OpsAlertDeliveryResponse = {
  generated_at: string;
  action_mode: OpsAlertDeliveryMode;
  channel: OpsAlertDeliveryChannel;
  confirmation_phrase: string;
  dedupe_window_minutes: number;
  requested_alert_codes: string[];
  requested_destination_ids: string[];
  delivery_id: string;
  totals: Record<string, number>;
  gate_snapshot: Record<string, string | number | boolean | string[] | null>;
  rollback: Record<string, string | number | boolean | null>;
  items: OpsAlertDeliveryItemResponse[];
  safety: OpsAlertDeliverySafetyResponse;
};

export type OpsAlertDestinationChannel = "slack" | "email" | "webhook";
export type OpsAlertDestinationMode = "config_dry_run";
export type OpsAlertDestinationStatus = "config_valid" | "dry_run_passed" | "disabled" | "missing_config" | "blocked";

export type OpsAlertDestinationDryRunRequest = {
  alert_codes?: string[];
  destination_ids?: string[];
};

export type OpsAlertDestinationSafetyResponse = {
  read_only: boolean;
  external_delivery_executed: boolean;
  provider_calls_executed: boolean;
  cleanup_executed: boolean;
  delete_executed: boolean;
  conversion_workflow_executed: boolean;
  audit_events_written: boolean;
  secret_values_exposed: boolean;
};

export type OpsAlertDestinationItemResponse = {
  destination_id: string;
  channel: OpsAlertDestinationChannel;
  enabled: boolean;
  secret_ref: string;
  secret_ref_present: boolean;
  target_label: string;
  allowlist: string[];
  rate_limit_per_hour: number;
  dedupe_window_minutes: number;
  status: OpsAlertDestinationStatus;
  missing_gates: string[];
  matched_alert_codes: string[];
  blocked_alert_codes: string[];
};

export type OpsAlertDestinationDryRunResponse = {
  generated_at: string;
  action_mode: OpsAlertDestinationMode;
  requested_alert_codes: string[];
  requested_destination_ids: string[];
  configured_count: number;
  selected_count: number;
  config_errors: string[];
  destinations: OpsAlertDestinationItemResponse[];
  safety: OpsAlertDestinationSafetyResponse;
};

export type OpsProviderCancellationProvider = "mineru";
export type OpsProviderCancellationTargetType = "document_job";
export type OpsProviderCancellationMode = "dry_run" | "fake_cancel";
export type OpsProviderCancellationOutcome = "cancelable" | "fake_canceled" | "deduped" | "ineligible" | "failed";

export type OpsProviderCancellationPreviewRequest = {
  target_type: OpsProviderCancellationTargetType;
  target_id: string;
  provider?: OpsProviderCancellationProvider;
  dedupe_window_minutes?: number;
};

export type OpsProviderCancellationFakeRequest = OpsProviderCancellationPreviewRequest & {
  reason: string;
  confirmation: string;
};

export type OpsProviderCancellationSemanticsSourceResponse = {
  label: string;
  url: string;
  source_type: "primary_docs";
  finding: string;
};

export type OpsProviderCancellationSemanticsSafetyResponse = {
  read_only: boolean;
  real_provider_cancel_executed: boolean;
  provider_calls_executed: boolean;
  local_job_mutated: boolean;
  queue_mutated: boolean;
  cleanup_executed: boolean;
  delete_executed: boolean;
  conversion_workflow_executed: boolean;
  audit_events_written: boolean;
  secret_values_exposed: boolean;
};

export type OpsProviderCancellationSemanticsResponse = {
  generated_at: string;
  action_mode: "semantics_verification";
  provider: OpsProviderCancellationProvider;
  verification_status: string;
  checked_on: string;
  decision: string;
  public_docs_support_real_cancel: boolean;
  real_provider_cancel_allowed: boolean;
  supported_provider_operations: string[];
  documented_task_statuses: string[];
  unsupported_operations: string[];
  blocking_reasons: string[];
  recommended_next_steps: string[];
  sources: OpsProviderCancellationSemanticsSourceResponse[];
  safety: OpsProviderCancellationSemanticsSafetyResponse;
};

export type OpsProviderCancellationTargetResponse = {
  target_type: OpsProviderCancellationTargetType;
  target_id: string;
  exists: boolean;
  status: string | null;
  stage: string | null;
  summary: Record<string, string | number | boolean | null>;
};

export type OpsProviderOperationResponse = {
  provider: OpsProviderCancellationProvider;
  operation_id: string | null;
  data_id: string | null;
  operation_type: string;
};

export type OpsProviderCancellationSafetyResponse = {
  real_provider_cancel_executed: boolean;
  provider_calls_executed: boolean;
  local_job_mutated: boolean;
  queue_mutated: boolean;
  cleanup_executed: boolean;
  delete_executed: boolean;
  conversion_workflow_executed: boolean;
  audit_events_written: boolean;
};

export type OpsProviderCancellationResponse = {
  generated_at: string;
  action_mode: OpsProviderCancellationMode;
  provider: OpsProviderCancellationProvider;
  confirmation_phrase: string;
  dedupe_window_minutes: number;
  target: OpsProviderCancellationTargetResponse;
  provider_operation: OpsProviderOperationResponse;
  eligible: boolean;
  missing_gates: string[];
  outcome: OpsProviderCancellationOutcome;
  dedupe_key: string | null;
  audit_event_written: boolean;
  safety: OpsProviderCancellationSafetyResponse;
};

export type OpsRecoveryActionCategory =
  | "recovery"
  | "cancellation"
  | "archive"
  | "cleanup"
  | "provider"
  | "notification"
  | "automation";
export type OpsRecoveryActionTargetType =
  | "document_job"
  | "provider_operation"
  | "alert"
  | "cleanup_run";

export type OpsRecoveryActionRiskFlagsResponse = {
  mutates_metadata: boolean;
  mutates_queue: boolean;
  calls_provider: boolean;
  sends_notification: boolean;
  deletes_data: boolean;
};

export type OpsIntegrationCapabilityId =
  | "alert_delivery"
  | "provider_cancellation"
  | "s3_deletion"
  | "cleanup_scheduler_execute"
  | "quota_enforcement";
export type OpsIntegrationCapabilityStatus = "blocked" | "dry_run_only" | "ready";
export type OpsIntegrationOverallStatus = "blocked" | "partial" | "ready";

export type OpsIntegrationCapabilityResponse = {
  capability_id: OpsIntegrationCapabilityId;
  label: string;
  category: string;
  status: OpsIntegrationCapabilityStatus;
  real_execution_enabled: boolean;
  dry_run_only: boolean;
  kill_switch_active: boolean;
  configured: boolean;
  ready: boolean;
  blocking_reasons: string[];
  required_gates: string[];
  safe_config: Record<string, string | number | boolean | null>;
};

export type OpsIntegrationControlPlaneSafetyResponse = {
  read_only: boolean;
  provider_calls_executed: boolean;
  external_delivery_executed: boolean;
  s3_delete_executed: boolean;
  cleanup_scheduler_executed: boolean;
  quota_enforcement_executed: boolean;
  cleanup_executed: boolean;
  delete_executed: boolean;
  conversion_workflow_executed: boolean;
  audit_events_written: boolean;
  secret_values_exposed: boolean;
};

export type OpsIntegrationControlPlaneResponse = {
  generated_at: string;
  action_mode: "read_only";
  overall_status: OpsIntegrationOverallStatus;
  capabilities: OpsIntegrationCapabilityResponse[];
  safety: OpsIntegrationControlPlaneSafetyResponse;
};

export type OpsRecoveryActionResponse = {
  action_id: string;
  label: string;
  category: OpsRecoveryActionCategory;
  target_type: OpsRecoveryActionTargetType;
  available: boolean;
  requires_admin: boolean;
  requires_reason: boolean;
  requires_confirmation: boolean;
  dry_run_supported: boolean;
  mutates_metadata: boolean;
  mutates_queue: boolean;
  calls_provider: boolean;
  sends_notification: boolean;
  deletes_data: boolean;
  audit_action: string | null;
  known_gaps: string[];
  suggested_route: string | null;
};

export type OpsRecoveryActionSafetyResponse = {
  read_only: boolean;
  execution_performed: boolean;
  metadata_mutated: boolean;
  queue_mutated: boolean;
  provider_calls_executed: boolean;
  notification_delivery_executed: boolean;
  cleanup_executed: boolean;
  delete_executed: boolean;
  audit_events_written: boolean;
};

export type OpsRecoveryActionRegistryResponse = {
  generated_at: string;
  actions: OpsRecoveryActionResponse[];
  safety: OpsRecoveryActionSafetyResponse;
};

export type OpsRecoveryActionPreviewRequest = {
  action_id: string;
  target_type: OpsRecoveryActionTargetType;
  target_id: string;
};

export type OpsRecoveryActionExecuteRequest = OpsRecoveryActionPreviewRequest & {
  reason: string;
};

export type OpsRecoveryActionTargetPreviewResponse = {
  target_type: OpsRecoveryActionTargetType;
  target_id: string;
  exists: boolean;
  status: string | null;
  stage: string | null;
  summary: Record<string, string | number | boolean | null>;
};

export type OpsRecoveryActionPreviewResponse = {
  generated_at: string;
  action: OpsRecoveryActionResponse;
  target: OpsRecoveryActionTargetPreviewResponse;
  eligible: boolean;
  missing_gates: string[];
  warnings: string[];
  risk_flags: OpsRecoveryActionRiskFlagsResponse;
  audit_action: string | null;
  safety: OpsRecoveryActionSafetyResponse;
};

export type OpsRecoveryActionExecuteResponse = {
  generated_at: string;
  action: OpsRecoveryActionResponse;
  target: OpsRecoveryActionTargetPreviewResponse;
  eligible: boolean;
  missing_gates: string[];
  warnings: string[];
  executed: boolean;
  queued_task_id: string | null;
  replayable_callback_messages: number;
  ignored_callback_messages: number;
  recovery_events_written: number;
  audit_events_written: number;
  risk_flags: OpsRecoveryActionRiskFlagsResponse;
  audit_action: string | null;
  safety: OpsRecoveryActionSafetyResponse;
};

export type AuditActorRole = "admin" | "operator" | "jobs" | "anonymous";
export type AuditEventSort = "created_at_desc" | "created_at_asc";
export type AuditDetailsValue =
  | string
  | number
  | boolean
  | null
  | AuditDetailsValue[]
  | { [key: string]: AuditDetailsValue };
export type AuditDetails = Record<string, AuditDetailsValue>;

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
  details: AuditDetails | null;
  trace_id: string;
  created_at: string;
};

export type AuditEventListResponse = {
  items: AuditEventResponse[];
  page: number;
  page_size: number;
  total: number;
};

export type AuditEventExportQuery = Omit<AuditEventListQuery, "page" | "page_size"> & {
  max_rows?: number;
};

export type AuditEventExportManifest = {
  exported_at: string;
  requested_by: string | null;
  actor_role: AuditActorRole;
  sort: AuditEventSort;
  filters: Record<string, string>;
  matched_count: number;
  exported_count: number;
  max_rows: number;
  truncated: boolean;
  columns: string[];
  audit_id: string;
};

export type AuditEventExportResponse = {
  manifest: AuditEventExportManifest;
  csv_text: string;
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

export type DocumentFileSummaryResponse = {
  id: string;
  tenant_id: string;
  company_id: string;
  job_id: string | null;
  file_type: string;
  storage_provider: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: string;
  expires_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  quality_evidence: Record<string, unknown>;
};

export type FileLibrarySort =
  | "created_at_desc"
  | "created_at_asc"
  | "updated_at_desc"
  | "updated_at_asc"
  | "expires_at_desc"
  | "expires_at_asc"
  | "size_bytes_desc"
  | "size_bytes_asc";

export type FileLibrarySearchQuery = {
  page: number;
  page_size: number;
  sort?: FileLibrarySort;
  q?: string;
  file_type?: string;
  status?: string;
  storage_provider?: string;
  job_id?: string;
  created_by?: string;
  expires_from?: string;
  expires_to?: string;
  created_from?: string;
  created_to?: string;
};

export type FileLibrarySearchItemResponse = {
  file_id: string;
  job_id: string | null;
  file_type: string;
  storage_provider: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: string;
  expires_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  expired: boolean;
  physical_delete_candidate: boolean;
};

export type FileLibrarySearchResponse = {
  generated_at: string;
  page: number;
  page_size: number;
  total: number;
  sort: FileLibrarySort;
  filters: Record<string, string>;
  items: FileLibrarySearchItemResponse[];
};

export type FileUploadUrlRequest = {
  filename: string;
  mime_type: string;
  size_bytes: number;
  file_type?: "source_pdf";
  checksum_sha256?: string | null;
  job_id?: string | null;
  quota_override_reason?: string | null;
  quota_override_confirmation?: string | null;
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

export type FileRetentionS3DeleteContractResponse = {
  contract_version: "s3-delete-fake-v1";
  adapter_mode: "fake";
  bucket: string;
  object_key: string;
  version_id: string | null;
  target_exact: boolean;
  missing_target_fields: string[];
  expected_outcome: "fake_skipped";
  safety: Record<string, boolean>;
};

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
  s3_delete_contract: FileRetentionS3DeleteContractResponse | null;
};

export type FileRetentionDeleteResponse = {
  generated_at: string;
  action_mode: "delete_preview" | "delete_execute";
  requested_file_ids: string[];
  confirmation_phrase: string;
  totals: Record<string, number>;
  items: FileRetentionDeleteItemResponse[];
};

export type FileRetentionCleanupRunPreviewRequest = {
  file_ids: string[];
  max_files?: number;
};

export type FileRetentionCleanupRunExecuteRequest = FileRetentionCleanupRunPreviewRequest & {
  run_id?: string | null;
  preview_hash: string;
  plan_id?: string | null;
  plan_signature?: string | null;
  reason: string;
  confirmation: string;
};

export type FileRetentionCleanupSchedulerDryRunRequest = {
  owner_id?: string | null;
  lock_ttl_seconds?: number;
};

export type FileRetentionSignedCleanupPlanResponse = {
  plan_id: string;
  run_id: string;
  preview_hash: string;
  requested_file_ids: string[];
  max_files: number;
  created_at: string;
  expires_at: string;
  signature: string;
  signature_algorithm: "hmac-sha256";
  safety: Record<string, boolean>;
};

export type FileRetentionCleanupRunSafetyResponse = {
  scheduler_loop_executed: boolean;
  provider_calls_executed: boolean;
  s3_delete_executed: boolean;
  physical_delete_executed: boolean;
  physical_delete_contract_reused: boolean;
  audit_events_written: boolean;
  history_recorded: boolean;
  signed_plan_created: boolean;
  signed_plan_verified: boolean;
};

export type FileRetentionCleanupRunResponse = {
  run_id: string;
  generated_at: string;
  action_mode: "cleanup_preview" | "cleanup_execute";
  confirmation_phrase: string;
  preview_hash: string;
  requested_file_ids: string[];
  max_files: number;
  physical_delete: FileRetentionDeleteResponse;
  cleanup_plan: FileRetentionSignedCleanupPlanResponse | null;
  safety: FileRetentionCleanupRunSafetyResponse;
};

export type FileRetentionCleanupLockSummaryResponse = {
  lock_name: string;
  owner_id: string;
  fencing_token: number;
  status: string;
  acquired_at: string;
  expires_at: string;
  released_at: string | null;
  released: boolean;
};

export type FileRetentionCleanupSchedulerDryRunResponse = {
  run_id: string;
  generated_at: string;
  action_mode: "scheduler_dry_run";
  readonly_report: Record<string, unknown>;
  lock: FileRetentionCleanupLockSummaryResponse;
  safety: Record<string, boolean>;
};

export type FileRetentionCleanupRunHistoryStatus = "previewed" | "executed" | "failed" | "dry_run";

export type FileRetentionCleanupRunHistoryResponse = {
  run_id: string;
  status: FileRetentionCleanupRunHistoryStatus;
  action_mode: "cleanup_preview" | "cleanup_execute" | "scheduler_dry_run";
  preview_hash: string;
  requested_file_ids: string[];
  max_files: number;
  reason: string | null;
  totals: Record<string, number>;
  safety: Record<string, boolean>;
  cleanup_plan: FileRetentionSignedCleanupPlanResponse | null;
  readonly_report: Record<string, unknown>;
  lock: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  executed_at: string | null;
};

export type FileRetentionCleanupRunHistoryListResponse = {
  page: number;
  page_size: number;
  total: number;
  items: FileRetentionCleanupRunHistoryResponse[];
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

export type FileQuotaPolicyStatus = "disabled" | "not_configured" | "invalid" | "dry_run" | "ready";

export type FileQuotaPolicyDryRunRequest = {
  size_bytes: number;
  file_type?: string;
  filename?: string | null;
};

export type FileQuotaPolicyConfigResponse = {
  enabled: boolean;
  dry_run: boolean;
  configured: boolean;
  quota_bytes: number | null;
  warning_threshold_ratio: number | null;
  block_threshold_ratio: number | null;
  warning_threshold_bytes: number | null;
  block_threshold_bytes: number | null;
  upload_max_bytes: number;
  status: FileQuotaPolicyStatus;
  config_errors: string[];
};

export type FileQuotaPolicyUsageResponse = {
  current_used_size_bytes: number;
  proposed_upload_size_bytes: number;
  projected_used_size_bytes: number;
  current_usage_ratio: number | null;
  projected_usage_ratio: number | null;
};

export type FileQuotaPolicySafetyResponse = {
  read_only: boolean;
  upload_authorization_created: boolean;
  upload_content_written: boolean;
  upload_blocking_executed: boolean;
  metadata_mutated: boolean;
  audit_events_written: boolean;
  provider_calls_executed: boolean;
  delete_executed: boolean;
  conversion_workflow_executed: boolean;
};

export type FileQuotaPolicyDryRunResponse = {
  generated_at: string;
  action_mode: "quota_policy_dry_run";
  file_type: string;
  filename: string | null;
  policy: FileQuotaPolicyConfigResponse;
  usage: FileQuotaPolicyUsageResponse;
  would_warn: boolean;
  would_block: boolean;
  reasons: string[];
  safety: FileQuotaPolicySafetyResponse;
};

export type FileQuotaPolicyOpsSafetyResponse = {
  read_only: boolean;
  upload_authorization_created: boolean;
  upload_content_written: boolean;
  upload_blocking_executed: boolean;
  metadata_mutated: boolean;
  audit_events_written: boolean;
  provider_calls_executed: boolean;
  delete_executed: boolean;
  cleanup_executed: boolean;
  scheduler_loop_executed: boolean;
  conversion_workflow_executed: boolean;
};

export type FileQuotaPolicyRollbackOptionResponse = {
  option_id: string;
  label: string;
  env_var: string;
  target_value: string;
  current_value: string;
  currently_effective: boolean;
  effect: string;
  requires_restart: boolean;
};

export type FileQuotaPolicyAuditReplayItemResponse = {
  audit_id: string;
  action: "file.quota_policy_block" | "file.quota_policy_override";
  target_type: string;
  target_id: string;
  actor_role: string;
  actor_id: string | null;
  reason: string | null;
  trace_id: string;
  created_at: string;
  outcome: string | null;
  file_type: string | null;
  filename: string | null;
  would_block: boolean | null;
  override_applied: boolean | null;
  current_used_size_bytes: number | null;
  proposed_upload_size_bytes: number | null;
  projected_used_size_bytes: number | null;
  quota_bytes: number | null;
  policy_status: string | null;
  reasons: string[];
  details: Record<string, unknown> | null;
};

export type FileQuotaPolicyOpsSummaryResponse = {
  generated_at: string;
  action_mode: "quota_policy_ops_summary";
  policy: FileQuotaPolicyConfigResponse;
  usage: FileQuotaPolicyUsageResponse;
  enforcement_ready: boolean;
  current_usage_would_warn: boolean;
  current_usage_would_block: boolean;
  kill_switch_enabled: boolean;
  reasons: string[];
  rollback_options: FileQuotaPolicyRollbackOptionResponse[];
  audit_replay: FileQuotaPolicyAuditReplayItemResponse[];
  audit_replay_total: number;
  audit_replay_limit: number;
  audit_replay_truncated: boolean;
  safety: FileQuotaPolicyOpsSafetyResponse;
};

export type TranslationMode = "direct" | "en2zh" | "ru2zh";
export type DocumentJobMode = "direct_pdf_to_word" | "en2zh_pdf_to_word" | "ru2zh_pdf_to_word";
export type DocumentLanguage = "auto" | "zh" | "en" | "ru";
export type DocumentJobStatus = "pending" | "queued" | "running" | "succeeded" | "failed" | "canceled";
export type DocumentJobStatusGroup = "active";
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
  mode?: DocumentJobMode | null;
  translation_mode?: TranslationMode | null;
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

export type DocumentJobActionId = "download" | "retry" | "cancel" | "archive" | "unarchive" | "clone" | "delete";

export type DocumentJobAvailableAction = {
  enabled: boolean;
  disabled_reason: string | null;
  retryable: boolean;
};

export type DocumentJobRetryRequest = {
  reason?: string | null;
  use_latest_term_assets?: boolean;
  term_rule_set_id?: string | null;
  term_rule_set_version?: string | null;
  translation_term_set_id?: string | null;
  translation_term_version?: string | null;
};

export type DocumentJobCloneRequest = {
  reason?: string | null;
  config_strategy?: "keep_source_snapshot" | "use_current_defaults" | "select_published_versions";
  document_language?: DocumentLanguage | null;
  template_version_id?: string | null;
  term_version_id?: string | null;
  term_rule_set_id?: string | null;
  term_rule_set_version?: string | null;
  translation_term_set_id?: string | null;
  translation_term_version?: string | null;
  translation_profile_id?: string | null;
  translation_profile_version?: string | null;
  debug_full_text?: boolean | null;
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
  source_job_id: string | null;
  mode: DocumentJobMode;
  translation_mode: TranslationMode;
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
  deleted_at: string | null;
  deleted_by: string | null;
  delete_reason: string | null;
  translation_qa_status: TranslationQaStatus;
  translation_qa_issue_type: TranslationQaIssueType | null;
  translation_qa_note: string | null;
  translation_qa_reviewed_by: string | null;
  translation_qa_reviewed_at: string | null;
  request_snapshot: Record<string, unknown>;
  available_actions: Record<DocumentJobActionId, DocumentJobAvailableAction>;
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
  filtered_summary?: Record<string, number>;
  translation_qa_summary?: Partial<Record<TranslationQaStatus, number>>;
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

export type DocumentJobIncidentFailureType =
  | "conversion_failed"
  | "translation_failed"
  | "qa_unavailable"
  | "artifact_missing"
  | "timeout_or_stalled"
  | "worker_or_dispatch_failed"
  | "unknown";

export type DocumentJobIncidentSort =
  | "priority"
  | "updated_at_desc"
  | "updated_at_asc"
  | "retry_count_desc"
  | "retry_count_asc";

export type DocumentJobIncidentRetryCountBucket = "0" | "1_2" | "3_plus";

export type DocumentJobIncidentQueueItemResponse = {
  job: DocumentJobResponse;
  failure_type: DocumentJobIncidentFailureType;
  priority: number;
  is_incident: boolean;
  retryable: boolean;
  retry_disabled_reason: string | null;
  stalled: boolean;
  stalled_minutes: number | null;
  blocked: boolean;
  suggested_action: string;
  evidence_summary: string[];
};

export type DocumentJobIncidentSummaryResponse = {
  total: number;
  failed: number;
  blocked: number;
  stalled: number;
  retryable: number;
  non_retryable: number;
  by_status: Record<string, number>;
  by_failure_type: Record<DocumentJobIncidentFailureType, number>;
};

export type DocumentJobIncidentListResponse = {
  items: DocumentJobIncidentQueueItemResponse[];
  page: number;
  page_size: number;
  total: number;
  summary: DocumentJobIncidentSummaryResponse;
};

export type DocumentJobIncidentEvidenceLinkResponse = {
  kind: "detail" | "events" | "files" | "translation_qa";
  title: string;
  target: string;
  available: boolean;
  helper: string | null;
};

export type DocumentJobIncidentEventSummaryResponse = {
  id: string;
  stage: string;
  level: string;
  event_type: string;
  message: string;
  duration_ms: number | null;
  trace_id: string | null;
  created_at: string;
};

export type DocumentJobIncidentFileSummaryResponse = {
  file_id: string;
  file_type: string | null;
  original_filename: string | null;
  storage_provider: string | null;
  status: string | null;
  size_bytes: number | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentJobIncidentDiagnosticResponse = {
  item: DocumentJobIncidentQueueItemResponse;
  evidence_links: DocumentJobIncidentEvidenceLinkResponse[];
  recent_events: DocumentJobIncidentEventSummaryResponse[];
  files: DocumentJobIncidentFileSummaryResponse[];
};

export type DocumentJobIncidentBulkRequest = {
  job_ids: string[];
  reason?: string | null;
};

export type DocumentJobIncidentBulkAction = "retry" | "refresh";

export type DocumentJobIncidentBulkItemResponse = {
  job_id: string;
  ok: boolean;
  skipped: boolean;
  status_code: number;
  error_code: string | null;
  detail: string | null;
  item: DocumentJobIncidentQueueItemResponse | null;
};

export type DocumentJobIncidentBulkResponse = {
  action: DocumentJobIncidentBulkAction;
  total: number;
  succeeded: number;
  failed: number;
  skipped: number;
  items: DocumentJobIncidentBulkItemResponse[];
};

export type SavedViewPageKey = "jobs" | "translation_qa" | "incidents";

export type SavedViewFilterValue = string | number | boolean;

export type SavedViewFilters = Record<string, SavedViewFilterValue>;

export type SavedViewResponse = {
  view_id: string;
  tenant_id: string;
  company_id: string;
  owner_user_id: string;
  page_key: SavedViewPageKey;
  name: string;
  filters: SavedViewFilters;
  sort: string;
  is_default: boolean;
  position: number;
  created_at: string;
  updated_at: string;
};

export type SavedViewListResponse = {
  items: SavedViewResponse[];
};

export type SavedViewCreateRequest = {
  page_key: SavedViewPageKey;
  name: string;
  filters: SavedViewFilters;
  sort: string;
  is_default?: boolean;
  position?: number | null;
};

export type SavedViewUpdateRequest = {
  name?: string | null;
  filters?: SavedViewFilters | null;
  sort?: string | null;
  is_default?: boolean | null;
  position?: number | null;
};

export type SavedViewReorderRequest = {
  page_key: SavedViewPageKey;
  view_ids: string[];
};

export type DocumentJobDeleteExecuteRequest = {
  preview_hash: string;
  reason?: string | null;
  confirmation?: string | null;
};

export type DocumentJobDeleteFileResponse = {
  file_id: string;
  file_type: string | null;
  storage_provider: string | null;
  status_before: string | null;
  status_after: string | null;
  size_bytes: number | null;
  action: "delete" | "keep";
  outcome: string;
  reason: string;
  deleted: boolean;
  metadata_updated: boolean;
  s3_delete_contract: Record<string, unknown> | null;
};

export type DocumentJobDeleteSafetyResponse = {
  physical_delete_executed: boolean;
  metadata_mutated: boolean;
  audit_events_written: boolean;
  s3_delete_executed: boolean;
  deleted_job_metadata_retained: boolean;
};

export type DocumentJobDeletePreviewResponse = {
  job_id: string;
  action_mode: "delete_preview";
  confirmation_phrase: string;
  preview_hash: string;
  totals: Record<string, number>;
  files: DocumentJobDeleteFileResponse[];
  safety: DocumentJobDeleteSafetyResponse;
};

export type DocumentJobDeleteExecuteResponse = {
  job_id: string;
  action_mode: "delete_execute";
  confirmation_phrase: string;
  preview_hash: string;
  totals: Record<string, number>;
  files: DocumentJobDeleteFileResponse[];
  safety: DocumentJobDeleteSafetyResponse;
  job: DocumentJobResponse;
};

export type DocumentJobArchiveResponse = {
  job_id: string;
  archived_at: string;
  job: DocumentJobResponse;
};

export type DocumentJobUnarchiveResponse = {
  job_id: string;
  restored_at: string;
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
  files: DocumentFileSummaryResponse[];
};

export type DocumentJobCallbackProblemSummaryResponse = {
  message_id: string;
  status: string;
  error_code: string | null;
  error_message: string | null;
  attempts: number;
  updated_at: string;
};

export type DocumentJobCallbackMessageSummaryResponse = {
  job_id: string;
  status_counts: Record<string, number>;
  replayable_count: number;
  oldest_replayable_age_seconds: number;
  recent_problem_messages: DocumentJobCallbackProblemSummaryResponse[];
};

export type DocumentJobTranslationBatchSummaryResponse = {
  batch_id: string;
  job_id: string;
  generation: number;
  root_batch_id: string;
  parent_batch_id: string | null;
  status: string;
  page_start: number | null;
  page_end: number | null;
  item_count: number;
  char_count: number;
  split_level: number;
  attempt_count: number;
  max_attempts: number;
  deterministic_batch_count: number;
  provider_call_budget: number;
  source_document_ir_file_id: string | null;
  result_file_id: string | null;
  ai_call_log_file_ids: string[];
  debug_archive_file_ids: string[];
  finish_reason: string | null;
  usage: Record<string, unknown>;
  response_id: string | null;
  error_code: string | null;
  error_message: string | null;
  retryable: boolean;
  truncation_retry: boolean;
  lease_expires_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentJobTranslationBatchListResponse = {
  job_id: string;
  generation: number;
  items: DocumentJobTranslationBatchSummaryResponse[];
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
  ai_debug_archive_expires_at: string | null;
  ai_debug_archive_expired: boolean;
  ai_debug_archive_contains_full_text: boolean;
};

export type DocumentJobTranslationQaSummaryResponse = {
  final_segment_count: number;
  returned_segment_count: number;
  quality_flags: string[];
  ai_call_count: number;
  ai_call_statuses: Record<string, number>;
  term_trace_count: number;
  debug_full_text_enabled: boolean;
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

export type DocumentJobTranslationResourceDefaults = {
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
  translation_defaults: Record<string, DocumentJobTranslationResourceDefaults>;
  options: DocumentJobConfigOptions;
  readiness: {
    en2zh_available: boolean;
    ru2zh_available: boolean;
    translation_modes: Record<string, boolean>;
    p0_document_jobs_required: boolean;
    p0_document_jobs_ready: boolean;
    document_jobs_worker_backend: string;
    document_jobs_automatic_execution_enabled: boolean;
    blockers: string[];
    warnings: string[];
  };
};

export type DocumentJobDownloadUrlResponse = {
  job_id: string;
  file_id: string;
  download_url: string;
  method: "GET";
  expires_at: string;
  file: DocumentFileSummaryResponse;
};

export type DocumentJobRetryResponse = {
  job_id: string;
  status: DocumentJobStatus;
  stage: DocumentJobStage;
  progress: number;
  retry_count: number;
  job: DocumentJobResponse;
};

export type DocumentJobCloneResponse = {
  source_job_id: string;
  job_id: string;
  status: DocumentJobStatus;
  stage: DocumentJobStage;
  progress: number;
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

export type TemplateLayoutConfigFieldType = "text" | "number" | "boolean" | "alignment" | "color";

export type TemplateLayoutConfigFieldSchema = {
  type: TemplateLayoutConfigFieldType;
  label: string;
  unit?: string;
  readonly?: boolean;
  options?: string[];
};

export type TemplateLayoutConfigResponse = {
  template_id: string;
  template_version_id: string | null;
  version: number;
  source_path: string | null;
  config_sha256: string | null;
  meta: Record<string, unknown>;
  config: Record<string, unknown>;
  field_schema: {
    meta: Record<string, TemplateLayoutConfigFieldSchema>;
    groups: Record<string, Record<string, TemplateLayoutConfigFieldSchema>>;
  };
};

export type TemplateLayoutConfigDraftRequest = {
  config: Record<string, unknown>;
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
  normalized_term: string;
  scope_type: "global" | "department";
  scope_id: string | null;
  current_version: number;
  active: boolean;
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
  expected_snapshot_hash?: string | null;
  category_id: string;
  source_term: string;
  scope_type?: "global" | "department";
  scope_id?: string | null;
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
  expected_snapshot_hash?: string | null;
  category_id?: string | null;
  source_term?: string | null;
  scope_type?: "global" | "department" | null;
  scope_id?: string | null;
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

export type TermRuleReviewAction = "create" | "update" | "delete";
export type TermRuleReviewItemStatus = "pending" | "approved" | "rejected" | "conflict";

export type TermRuleReviewItemWriteRequest = {
  action: TermRuleReviewAction;
  target_rule_id?: string | null;
  base_version?: number | null;
  source_term?: string | null;
  category_id?: string | null;
  apply_scope?: string;
  case_sensitive?: boolean;
  enabled?: boolean;
  priority?: number;
  segments?: TermRuleSegmentWriteRequest[] | null;
  custom_html?: string | null;
  custom_markdown?: string | null;
  notes?: string;
  scope_type?: "global" | "department" | null;
  scope_id?: string | null;
};

export type TermRuleReviewBatchCreateRequest = {
  source_job_id?: string | null;
  source_file_id?: string | null;
  reason?: string;
  items: TermRuleReviewItemWriteRequest[];
};

export type TermRuleReviewBatchSummaryResponse = {
  pending: number;
  approved: number;
  rejected: number;
  conflict: number;
  total: number;
};

export type TermRuleReviewItemResponse = {
  id: string;
  batch_id: string;
  seq: number;
  action: TermRuleReviewAction;
  status: TermRuleReviewItemStatus;
  scope_type: "global" | "department";
  scope_id: string | null;
  normalized_term: string;
  target_rule_id: string | null;
  base_version: number | null;
  submitted_snapshot: Record<string, unknown>;
  rejection_reason: string | null;
  conflict_reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TermRuleReviewBatchResponse = {
  id: string;
  submitted_by: string;
  submitter_department_id: string;
  source_job_id: string | null;
  source_file_id: string | null;
  reason: string;
  status: string;
  summary: TermRuleReviewBatchSummaryResponse;
  items: TermRuleReviewItemResponse[];
  created_at: string;
  updated_at: string;
};

export type TermRuleReviewBatchListResponse = {
  items: TermRuleReviewBatchResponse[];
  page: number;
  page_size: number;
  total: number;
};

export type TermRuleReviewBulkRequest = {
  item_ids: string[];
  reason?: string | null;
};

export type TermRuleReviewBulkItemResponse = {
  item_id: string;
  ok: boolean;
  status_code: number;
  error_code: string | null;
  detail: string | Record<string, unknown> | null;
  item: TermRuleReviewItemResponse | null;
};

export type TermRuleReviewBulkResponse = {
  action: "approve" | "reject";
  total: number;
  succeeded: number;
  failed: number;
  items: TermRuleReviewBulkItemResponse[];
};

export type TermRuleVersionResponse = {
  id: string;
  rule_id: string;
  version: number;
  action: TermRuleReviewAction;
  scope_type: "global" | "department";
  scope_id: string | null;
  normalized_term: string;
  review_item_id: string | null;
  before_snapshot: Record<string, unknown> | null;
  after_snapshot: Record<string, unknown> | null;
  created_by: string;
  created_at: string;
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
  expected_snapshot_hash?: string | null;
  yaml_text: string;
};

export type TermRuleSetRollbackRequest = {
  version: string;
};

export type TerminologyReleaseStatus = "active" | "rolled_back";

export type TerminologyReleaseScopeRequest = {
  project: string;
  language_pair: string;
  content_type: string;
};

export type TerminologyReleaseScopeResponse = TerminologyReleaseScopeRequest;

export type TerminologyReleaseCreateRequest = {
  translation_term_set_id: string;
  translation_term_version: string;
  term_rule_set_id: string;
  term_rule_set_version: string;
  scope: TerminologyReleaseScopeRequest;
  release_note?: string | null;
  source_release_id?: string | null;
  source_release_version?: string | null;
};

export type TerminologyReleaseFindingResponse = {
  severity: "error" | "warning" | "conflict";
  code: string;
  message: string;
  path: string | null;
  metadata: Record<string, unknown>;
};

export type TerminologyReleaseValidationSummaryResponse = {
  error_count: number;
  warning_count: number;
  conflict_count: number;
  publishable_term_count: number;
  overlapping_release_count: number;
};

export type TerminologyReleaseValidationReportResponse = {
  valid: boolean;
  blocking: boolean;
  summary: TerminologyReleaseValidationSummaryResponse;
  errors: TerminologyReleaseFindingResponse[];
  warnings: TerminologyReleaseFindingResponse[];
  conflicts: TerminologyReleaseFindingResponse[];
};

export type TerminologyReleaseAssetResponse = {
  resource_id: string;
  version: string;
  snapshot_hash: string | null;
  item_count: number | null;
};

export type TerminologyReleaseResponse = {
  id: string;
  version: string;
  status: TerminologyReleaseStatus;
  scope: TerminologyReleaseScopeResponse;
  translation_term_set: TerminologyReleaseAssetResponse;
  term_rule_set: TerminologyReleaseAssetResponse;
  validation_report: TerminologyReleaseValidationReportResponse;
  release_note: string | null;
  source_release_id: string | null;
  source_release_version: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  published_at: string;
  rolled_back_by: string | null;
  rolled_back_at: string | null;
};

export type TerminologyReleaseListResponse = {
  items: TerminologyReleaseResponse[];
  total: number;
};

export type TerminologyReleaseListQuery = {
  status?: TerminologyReleaseStatus;
  project?: string;
  language_pair?: string;
  content_type?: string;
};

export type TerminologyReleaseCopyResponse = {
  source: TerminologyReleaseResponse;
  draft: TerminologyReleaseCreateRequest;
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
  recommended_translations: string[];
  forbidden_translations: string[];
  synonyms: string[];
  version: string;
  set_id: string;
  case_sensitive: boolean;
  status: string;
  priority: number;
  project: string | null;
  content_type: string | null;
  tags: string[];
  maintainer: string | null;
  domain: string | null;
  category: string | null;
  note: string;
  created_at: string;
  updated_at: string;
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

export type TranslationTermSetDraftChangeRequest = {
  action: string;
  source_term: string;
  target_term?: string | null;
  recommended_translations?: string[] | null;
  forbidden_translations?: string[] | null;
  synonyms?: string[] | null;
  case_sensitive?: boolean | null;
  status?: string | null;
  priority?: number | null;
  project?: string | null;
  content_type?: string | null;
  tags?: string[] | null;
  maintainer?: string | null;
  domain?: string | null;
  category?: string | null;
  note?: string | null;
};

export type TranslationTermSetDraftChangesApplyRequest = {
  expected_snapshot_hash: string;
  reason?: string | null;
  changes: TranslationTermSetDraftChangeRequest[];
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
