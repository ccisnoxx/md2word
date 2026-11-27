// 文件：frontend/src/api/types.ts
// 用途：定义后端 v1 schema 和运维请求对应的 TypeScript 合同。
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

// 前端仅使用五个规范模式；direct 保持原文且不调用 AI。
export type TranslationMode = "direct" | "en2zh" | "ru2zh" | "zh2en" | "zh2ru";
export type TranslationLanguagePair = Exclude<TranslationMode, "direct">;
export type DocumentJobMode =
  | "direct_pdf_to_word"
  | "en2zh_pdf_to_word"
  | "ru2zh_pdf_to_word"
  | "zh2en_pdf_to_word"
  | "zh2ru_pdf_to_word";
export type DocumentLanguage = "auto" | "zh" | "en" | "ru";
export type DocumentJobStatus = "pending" | "queued" | "running" | "succeeded" | "failed" | "canceled";
export type DocumentJobStatusGroup = "active";
export type DocumentJobListSort = "created_at_desc" | "created_at_asc" | "updated_at_desc" | "updated_at_asc";
export type DocumentJobStage =
  | "uploaded"
  | "parsing"
  | "parsed"
  | "ir_converting"
  | "translating"
  | "translation_validating"
  | "rendering"
  | "quality_checking"
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
  // 旧翻译术语版本仅用于翻译任务；direct 不得显式绑定。
  term_version_id?: string | null;
  // 符号与排版规则适用于 direct 和四个翻译方向。
  term_rule_set_id?: string | null;
  term_rule_set_version?: string | null;
  // 以下术语集和 Profile 字段仅用于翻译任务，direct 不得显式绑定。
  translation_term_set_id?: string | null;
  translation_term_version?: string | null;
  translation_profile_id?: string | null;
  translation_profile_version?: string | null;
  // 全文调试仅供有权限的管理员用于翻译任务。
  debug_full_text?: boolean;
};

export type DocumentJobActionId = "download" | "retry" | "cancel" | "archive" | "unarchive" | "clone" | "delete" | "publish" | "new_generation";

export type DocumentJobDisabledReason = { code: string; message: string };

export type DocumentJobDownloadAvailability = {
  classification?: "internal_only" | null;
  warning_code?: string | null;
  warning_message?: string | null;
};

export type DocumentJobAvailableAction = DocumentJobDownloadAvailability & {
  enabled: boolean;
  disabled_reason: string | null;
  retryable: boolean;
  eligible?: boolean | null;
  disabled_reason_code?: string | null;
  disabled_reasons?: DocumentJobDisabledReason[] | null;
};

export type DocumentJobRetryRequest = {
  reason?: string | null;
  use_latest_term_assets?: boolean;
  // direct 重试可重选符号与排版规则。
  term_rule_set_id?: string | null;
  term_rule_set_version?: string | null;
  // 翻译术语重选仅用于翻译任务。
  translation_term_set_id?: string | null;
  translation_term_version?: string | null;
};

export type DocumentJobCloneRequest = {
  reason?: string | null;
  config_strategy?: "keep_source_snapshot" | "use_current_defaults" | "select_published_versions";
  document_language?: DocumentLanguage | null;
  template_version_id?: string | null;
  // 旧翻译术语版本仅用于翻译任务；direct 不得显式绑定。
  term_version_id?: string | null;
  // 符号与排版规则适用于所有任务模式。
  term_rule_set_id?: string | null;
  term_rule_set_version?: string | null;
  // 以下术语集和 Profile 字段仅用于翻译任务，direct 不得显式绑定。
  translation_term_set_id?: string | null;
  translation_term_version?: string | null;
  translation_profile_id?: string | null;
  translation_profile_version?: string | null;
  // direct 克隆不得启用 AI 全文调试。
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
  translation_prompt_id?: string | null;
  translation_prompt_content_hash?: string | null;
  mineru?: Record<string, unknown>;
  artifact_ids?: Record<string, string>;
};

/** 当前代 MinerU 验证、渲染或表格占位失败定位；页码 1 起始，文档级问题 page_number 为 null。 */
export type DocumentJobFailureDiagnostic = {
  source: "mineru_validation" | "render_operation" | "table_placeholder";
  stage: string;
  scope: "page" | "document";
  page_number: number | null;
  source_type: string | null;
  json_pointer: string | null;
  reason_code: string;
  reason: string | null;
  affected_page_numbers: number[];
  fatal_count: number;
  warning_count: number;
  details_truncated: boolean;
  /** 失败操作涉及的块 ID 与操作类型；旧响应可能缺失。 */
  block_ids?: string[];
  operation_kind?: string | null;
  /** 源 PDF 总页数；旧响应可能缺失。content_blocks 依据下只能当下限。 */
  source_page_count?: number | null;
  page_count_basis?: "mineru_layout" | "content_blocks" | null;
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
  // 滚动部署期间旧响应可缺省；动作资格仍以 available_actions 为准。
  quality_status?: DocumentJobQualityStatus;
  review_status?: DocumentJobReviewStatus;
  delivery_status?: DocumentJobDeliveryStatus;
  quality_summary?: Record<string, unknown>;
  stage: DocumentJobStage;
  progress: number;
  template_version_id: string;
  term_version_id: string | null;
  result_file_id: string | null;
  mineru_raw_result_file_id: string | null;
  // 旧详情可缺省；缺字段时不能确认复核内容来源。
  source_document_ir_file_id?: string | null;
  document_ir_file_id: string | null;
  image_asset_file_ids: string[];
  debug_full_text_enabled: boolean;
  mineru_batch_id: string | null;
  mineru_data_id: string | null;
  failed_stage: DocumentJobStage | null;
  error_code: string | null;
  error_message: string | null;
  /** 仅任务详情接口填充；列表等接口为 null。 */
  failure_diagnostic?: DocumentJobFailureDiagnostic | null;
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
  // 七种既有动作仍必需；旧后端可暂不提供发布和发起新代动作。
  available_actions: Record<Exclude<DocumentJobActionId, "publish" | "new_generation">, DocumentJobAvailableAction> & {
    publish?: DocumentJobAvailableAction;
    new_generation?: DocumentJobAvailableAction;
  };
  created_at: string;
  updated_at: string;
};

export type DocumentJobQualityStatus = "pending" | "passed" | "warning" | "blocked";
export type DocumentJobReviewStatus = "unreviewed" | "approved" | "needs_fix" | "blocked";
export type DocumentJobDeliveryStatus = "internal_draft" | "ready_to_publish" | "published";

export type DocumentQualitySourceResponse = {
  generation: number;
  ir_file_id: string | null;
  result_file_id: string | null;
  result_sha256: string | null;
  file_review_source_revision: number | null;
  receipt_sha256: string | null;
};

export type DocumentReviewComponentResponse = {
  availability: "available" | "unavailable" | "not_ready" | "disabled" | "not_applicable";
  reason_code: string | null;
};

export type DocumentReviewContentSnapshotResponse = {
  snapshot_id: string;
  source_pdf_file_id: string;
  source_ir_file_id: string | null;
  final_ir_file_id: string | null;
  preview_run_id: string | null;
  preview_revision: number | null;
  preview_attempt: number | null;
  basis: "source" | "final" | "none";
  source_content: DocumentReviewComponentResponse;
  target_content: DocumentReviewComponentResponse;
  translation: DocumentReviewComponentResponse;
  preview: DocumentReviewComponentResponse;
  mapping: DocumentReviewComponentResponse;
  tables: DocumentReviewComponentResponse;
};

export type DocumentReviewSourceSpanResponse = {
  source_page_index: number | null;
  bbox: [number, number, number, number] | null;
  page_width: number | null;
  page_height: number | null;
  coordinate_unit: "mineru";
  coordinate_verified: boolean;
  reason_code: "coordinate_space_unverified" | null;
  fragment_id: string | null;
};

export type DocumentReviewLocationResponse = {
  kind: "single_page" | "estimated_start" | "unavailable";
  preview_page_index: number | null;
  confidence: "high" | "low" | "none";
  reason_code: string | null;
  bookmark_label: string | null;
  disposition: "rendered" | "coalesced" | "suppressed" | "superseded" | "not_emitted" | null;
  representative_block_id: string | null;
  fallback_page_index: number | null;
  fallback_block_id: string | null;
  provenance_status: "verified_ir205" | "legacy_layout" | "unavailable";
};

export type DocumentReviewBlockFlagResponse = {
  code: string;
  severity: "blocker" | "warning" | "info";
  table_id: string | null;
};

export type DocumentReviewBlockItemResponse = {
  block_id: string;
  order: number;
  block_type: "heading" | "paragraph" | "table" | "image" | "list" | "formula";
  source_type: string | null;
  excerpt: string;
  source_spans: DocumentReviewSourceSpanResponse[];
  location: DocumentReviewLocationResponse;
  flags: DocumentReviewBlockFlagResponse[];
  table_ids: string[];
};

export type DocumentReviewBlocksResponse = {
  job_id: string;
  source: DocumentQualitySourceResponse;
  content_snapshot: DocumentReviewContentSnapshotResponse;
  availability: "available" | "not_ready" | "unavailable";
  reason_code: string | null;
  total: number;
  items: DocumentReviewBlockItemResponse[];
  next_cursor: string | null;
};

export type QualityAvailability = "available" | "legacy_unavailable" | "not_ready" | "disabled" | "unavailable";
export type QualityRule = "clipping" | "overflow" | "blank" | "overlap" | "density";
export type QualityIssue =
  | "conversion"
  | "translation"
  | "terminology"
  | "table_structure"
  | "layout"
  | "source_quality"
  | "artifact_missing"
  | "other";
export type TableSemanticsReviewConflict =
  | "table_semantics_confirmation_required"
  | "table_semantics_confirmation_stale"
  | "table_semantics_evidence_invalid";
export type DocumentReviewValidityReason =
  | "legacy_unbound"
  | "source_changed"
  | "artifact_missing"
  | "artifact_unavailable"
  | "integrity_conflict"
  | "quality_blocked"
  | TableSemanticsReviewConflict;
export type ValueColumnLabel = "MIN" | "TYP" | "MAX" | "LOW" | "NOM" | "HIGH" | "最小" | "典型" | "最大";

export type ReviewExpectedSourceRequest = {
  generation: number;
  result_file_id: string | null;
  result_sha256: string | null;
  file_review_source_revision: number | null;
  receipt_sha256: string | null;
};

export type DocumentQualityCountsResponse = {
  formula_count?: number | null;
  omml_count?: number | null;
  semantic_count?: number | null;
  fallback_count?: number | null;
  table_count?: number | null;
  fragment_count?: number | null;
  native_count?: number | null;
  placeholder_count?: number | null;
  blocker_count?: number | null;
  warning_count?: number | null;
  page_count?: number | null;
  complete_page_count?: number | null;
  flag_count?: number | null;
  count?: number | null;
  pages?: number | null;
  observed_pages?: number | null;
  flags?: number | null;
  manual_checks?: number | null;
  checked_rules?: number | null;
  not_checked_rules?: number | null;
};

export type TableStructureReviewSummaryResponse = {
  source_pointer: string;
  page_number: number | null;
  reason: string;
  preserved_as: "native" | "reference_image" | "pdf_crop" | "pdf_page";
  severity: "warning";
  manual_review_required: true;
};

export type DocumentQualityProducerResponse = {
  producer:
    | "formula"
    | "table_evidence"
    | "table_placeholder"
    | "word_preview"
    | "word_page_quality"
    | "document_base"
    | "unattributed";
  schema_version?: string | null;
  quality_status?: DocumentJobQualityStatus | null;
  evaluation_state?: "complete" | "incomplete" | null;
  availability?: QualityAvailability | null;
  coverage?: "complete" | "unavailable" | null;
  report_sha256?: string | null;
  reason_code?: string | null;
  counts: DocumentQualityCountsResponse;
  flags: string[];
  unknown_flag_count: number;
  table_structure_reviews?: TableStructureReviewSummaryResponse[];
};

export type DocumentQualityProducersResponse = {
  items: DocumentQualityProducerResponse[];
  unknown_producer_count: number;
};

export type DocumentQualitySummaryResponse = {
  quality_flags: string[];
  layout_quality_flags: string[];
  blocking_quality_flags: string[];
  unknown_flag_count: number;
};

export type DocumentReviewBindingResponse = {
  generation: number;
  result_file_id: string | null;
  binding_state: "verified" | "no_result" | "unverified_result" | "legacy_unbound";
  result_sha256: string | null;
  file_review_source_revision: number | null;
  receipt_sha256: string | null;
  acknowledged_table_semantics_report_sha256?: string | null;
};

export type DocumentReviewQualityResponse = {
  quality_status: DocumentJobQualityStatus;
  summary_sha256: string;
  summary: DocumentQualitySummaryResponse;
  producers: DocumentQualityProducersResponse;
};

export type DocumentReviewResponse = {
  status: DocumentJobReviewStatus;
  current_record_id: string | null;
  sequence: number | null;
  issue_type: QualityIssue | null;
  note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  binding: DocumentReviewBindingResponse | null;
  validity_reason: DocumentReviewValidityReason | null;
  quality: DocumentReviewQualityResponse | null;
};

export type DocumentReviewHistoryItemResponse = {
  id: string;
  sequence: number;
  record_status: DocumentJobReviewStatus;
  issue_type: QualityIssue | null;
  note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  origin: "live" | "legacy_import";
  legacy_observed_status: DocumentJobReviewStatus | null;
  binding: DocumentReviewBindingResponse;
  quality: DocumentReviewQualityResponse;
};

export type DocumentReviewHistoryResponse = {
  job_id: string;
  through_sequence: number;
  items: DocumentReviewHistoryItemResponse[];
  next_cursor: string | null;
};

export type DocumentQualityStatesResponse = {
  execution_status: DocumentJobStatus;
  quality_status: DocumentJobQualityStatus;
  review_status: DocumentJobReviewStatus;
  delivery_status: DocumentJobDeliveryStatus;
};

export type DocumentQualityResponse = {
  job_id: string;
  source: DocumentQualitySourceResponse;
  states: DocumentQualityStatesResponse;
  summary: DocumentQualitySummaryResponse;
  producers: DocumentQualityProducersResponse;
  review: DocumentReviewResponse;
  available_actions: Record<DocumentJobActionId, DocumentJobAvailableAction>;
};

export type DocumentCurrentReviewResponse = {
  job_id: string;
  source: DocumentQualitySourceResponse;
  review: DocumentReviewResponse;
  available_actions: Record<DocumentJobActionId, DocumentJobAvailableAction>;
};

export type DocumentReviewUpdateRequest = {
  status: DocumentJobReviewStatus;
  issue_type?: QualityIssue | null;
  note?: string | null;
  expected_source: ReviewExpectedSourceRequest;
  acknowledged_table_semantics_report_sha256?: string | null;
};

export type DocumentReviewUpdateResponse = {
  job_id: string;
  accepted_record_id: string;
  accepted_sequence: number;
  source: DocumentQualitySourceResponse;
  review: DocumentReviewResponse;
  available_actions: Record<DocumentJobActionId, DocumentJobAvailableAction>;
};

export type DocumentQualitySourceSpanResponse = {
  fragment_id?: string | null;
  source_page_index: number | null;
  bbox: [number, number, number, number] | null;
  html_state?: "missing" | "empty" | "present" | null;
  row_start?: number | null;
  row_count?: number | null;
  columns?: number | null;
};

export type DocumentQualityGridResponse = {
  rows: number;
  columns: number;
  header_rows: number[];
  rowspan_count: number;
  colspan_count: number;
};

export type DocumentQualityTableReferenceResponse = {
  fragment_id: string;
  source_status: "valid" | "missing" | "invalid" | "unavailable";
  asset_id: string | null;
  file_id: string | null;
  mime_type: string | null;
  registered: boolean;
};

export type DocumentQualityCellShapeResponse = {
  grid_span: number;
  vertical_merge: "restart" | "continue" | null;
};

export type DocumentQualityRowShapeResponse = {
  cells: DocumentQualityCellShapeResponse[];
  header: boolean;
  cant_split: boolean;
};

export type DocumentQualityFragmentResponse = {
  fragment_id: string;
  block_id: string | null;
  render_owner_block_id: string;
  source_rows: number[];
  retained_source_rows: number[];
  output_rows: number[];
  removed_header_rows: number[] | null;
  shared_header_rows: number[] | null;
  status: "rendered" | "header_only" | "empty" | "missing";
};

export type DocumentQualityNativeTableResponse = {
  output_table_key: string;
  anchor_block_id: string;
  table_index: number;
  grid_columns: number;
  rows: DocumentQualityRowShapeResponse[];
  fragments: DocumentQualityFragmentResponse[];
};

export type DocumentQualityPlaceholderResponse = {
  placeholder_id: string;
  fragment_id: string;
  owner_block_id: string;
  asset_ref: string;
  source_kind: "mineru_reference" | "source_pdf_crop";
  issue_code: "table_noneditable_placeholder";
};

export type DocumentQualityTableFlagResponse = {
  producer: "table_validator" | "table_rendering" | "table_reference" | "table_placeholder";
  code: string;
  severity: "blocker" | "warning";
  fragment_id: string | null;
};

export type DocumentQualityValueColumnResponse = {
  column: number;
  label: ValueColumnLabel;
  group_start_column: number;
};

export type DocumentQualityTableValueFindingResponse = {
  finding_id: string;
  code: "table_semantics:value_column_span_ambiguous";
  fragment_id: string;
  cell_id: string;
  source_page_index: number | null;
  source_row_index: number;
  column: number;
  end_column: number;
  columns: DocumentQualityValueColumnResponse[];
  value: string;
  unit: string | null;
  manual_review_required: true;
};

export type DocumentQualityUnresolvedValueColumnResponse = {
  finding_id: string;
  fragment_id: string;
  source_page_index: number | null;
  bbox: [number, number, number, number] | null;
  source_row_index: number;
  source_cell_index: number;
  reason_code: string;
  manual_review_required: true;
};

export type DocumentQualityTableItemResponse = {
  table_id: string;
  logical_group_id: string;
  member_block_ids: string[];
  anchor_block_id: string;
  source_spans: DocumentQualitySourceSpanResponse[];
  source_grid: DocumentQualityGridResponse;
  references: DocumentQualityTableReferenceResponse[];
  outputs: DocumentQualityNativeTableResponse[];
  placeholders: DocumentQualityPlaceholderResponse[];
  render_state: "native" | "placeholder" | "mixed" | "excluded_margin_artifact";
  flags: DocumentQualityTableFlagResponse[];
  unknown_flag_count: number;
  status: DocumentJobQualityStatus;
  value_column_findings?: DocumentQualityTableValueFindingResponse[] | null;
  unresolved_value_columns?: DocumentQualityUnresolvedValueColumnResponse[] | null;
};

export type DocumentQualityTableReportResponse = {
  schema_version: string;
  report_file_id: string;
  report_sha256: string;
  coverage: "complete" | "unavailable" | null;
  status: DocumentJobQualityStatus | null;
  counts: DocumentQualityCountsResponse;
};

export type DocumentQualityTablesResponse = {
  job_id: string;
  source: DocumentQualitySourceResponse;
  availability: QualityAvailability;
  reason_code: string | null;
  report: DocumentQualityTableReportResponse | null;
  items: DocumentQualityTableItemResponse[];
  next_cursor: string | null;
};

export type DocumentQualityPageRuleResponse = {
  rule_version: "v1";
  checked: boolean;
  reason_code: string | null;
  metrics: Record<string, number | null>;
  units: Record<string, "pt" | "pt2" | "ratio" | "count" | "char/pt2">;
};

export type DocumentQualityPageFlagResponse = {
  code:
    | "page_clip_risk"
    | "page_overflow_risk"
    | "unexpected_blank_page_suspected"
    | "page_overlap_suspected"
    | "page_density_low"
    | "page_density_high";
  severity: "warning" | "info";
  rule_version: "v1";
  preview_page_index: number;
  metric_refs: string[];
  evidence_kind: "native_and_raster";
  manual_check_required: true;
};

export type DocumentQualityBlockCandidateResponse = {
  block_id: string;
  association: "single_page" | "estimated_start" | "navigation_fallback";
  confidence: "high" | "low";
  source_page_indices: number[];
  source_spans: DocumentQualitySourceSpanResponse[];
};

export type DocumentQualityPageItemResponse = {
  preview_page_index: number;
  rules: Partial<Record<QualityRule, DocumentQualityPageRuleResponse>>;
  flags: DocumentQualityPageFlagResponse[];
  unknown_flag_count: number;
  manual_checks: string[];
  block_candidates: DocumentQualityBlockCandidateResponse[];
};

export type DocumentQualityCoverageResponse = {
  checked: number;
  not_checked: number;
};

export type DocumentQualityPageReportResponse = {
  schema_version: string;
  analyzer_version: string;
  id: string;
  run_sha256: string;
  generation: number;
  preview_run_id: string;
  revision: number;
  attempt: number;
  manifest_file_id: string;
  profile_id: string;
  profile_sha256: string;
  page_count: number;
  evaluation_state: "complete" | "incomplete";
  quality_status: "pending" | "passed" | "warning";
  reason_code: string | null;
  manual_checks: string[];
  coverage: Partial<Record<QualityRule, DocumentQualityCoverageResponse>>;
  counts: DocumentQualityCountsResponse;
};

export type DocumentQualityPagesResponse = {
  job_id: string;
  source: DocumentQualitySourceResponse;
  availability: QualityAvailability;
  reason_code: string | null;
  report: DocumentQualityPageReportResponse | null;
  items: DocumentQualityPageItemResponse[];
  next_cursor: string | null;
};

export type DocumentPreviewPageResponse = {
  file_id: string;
  page_index: number;
  width: number;
  height: number;
};

export type DocumentPreviewRunResponse = {
  run_id: string;
  revision: number;
  attempt: number;
  status: "pending" | "running" | "succeeded" | "failed" | "unavailable";
  profile_id: string;
  profile_sha256: string;
  started_at: string;
  completed_at: string | null;
  error_code: string | null;
};

export type DocumentPreviewResponse = {
  job_id: string;
  source: DocumentQualitySourceResponse;
  status: "not_ready" | "disabled" | "pending" | "running" | "succeeded" | "failed" | "unavailable";
  availability: QualityAvailability;
  reason_code: string | null;
  run: DocumentPreviewRunResponse | null;
  pdf_file_id: string | null;
  page_count: number | null;
  items: DocumentPreviewPageResponse[];
  next_cursor: string | null;
};

export type DocumentJobTableReferenceResponse = {
  block_id: string;
  fragment_id: string;
  logical_group_id: string;
  page_index: number | null;
  bbox: [number, number, number, number] | null;
  asset_id: string | null;
  file_id: string | null;
  source_status: "valid" | "missing" | "invalid";
  availability: "available" | "source_missing" | "source_invalid" | "missing" | "expired" | "deleted" | "not_uploaded";
  mime_type: string | null;
  checksum_sha256: string | null;
  size_bytes: number | null;
  warning_codes: string[];
  display_supported: boolean;
  content_path: string | null;
};

export type DocumentJobTableReferenceListResponse = {
  job_id: string;
  generation: number;
  ir_file_id: string | null;
  evidence_status: "not_ready" | "legacy_unavailable" | "registered";
  items: DocumentJobTableReferenceResponse[];
};

export type DocumentReviewTermResponse = {
  unit_id: string;
  batch_id: string;
  source_term: string;
  target_term: string;
  version: string | null;
};

export type DocumentReviewTokenCountsResponse = {
  formula: number;
  literal_placeholder: number;
  address: number;
  bit_field: number;
  model: number;
  standard: number;
  version: number;
  signal: number;
  quantity: number;
  unit: number;
  url: number;
  email: number;
  number: number;
  symbol: number;
  technical_literal: number;
};

export type DocumentReviewBatchResponse = {
  scope: "batch";
  batch_id: string;
  attempt: number;
  status: "succeeded" | "failed";
  provider_backend?: "fake" | "openai_compatible" | null;
  provider_model?: string | null;
  schema_version?: string | null;
  validator_version?: string | null;
  codec_version?: "MD2W_PT_v1" | null;
  instruction_version?: string | null;
  instruction_sha256?: string | null;
  integrity_status?: "passed" | "failed" | "pending" | null;
  error_code?: string | null;
  expected_item_count?: number | null;
  actual_item_count?: number | null;
  checked_item_count?: number | null;
  failed_item_count?: number | null;
  expected_token_counts?: DocumentReviewTokenCountsResponse | null;
  actual_token_counts?: DocumentReviewTokenCountsResponse | null;
  source_sha256?: string | null;
  restored_sha256?: string | null;
};

export type DocumentReviewContentPartResponse = {
  kind:
    | "text"
    | "list_item"
    | "caption"
    | "footnote"
    | "latex"
    | "table_text"
    | "html_summary"
    | "term"
    | "batch"
    | "table"
    | "reference";
  side: "source" | "target" | "shared";
  field: string;
  index?: number | null;
  unit_id?: string | null;
  fragment_id?: string | null;
  offset: number;
  text?: string | null;
  total_chars?: number | null;
  truncated: boolean;
  html_state?: "missing" | "empty" | "present" | null;
  sha256?: string | null;
  term?: DocumentReviewTermResponse | null;
  batch?: DocumentReviewBatchResponse | null;
  table?: DocumentQualityTableItemResponse | null;
  reference?: DocumentJobTableReferenceResponse | null;
};

export type DocumentReviewBlockDetailResponse = {
  job_id: string;
  source: DocumentQualitySourceResponse;
  content_snapshot: DocumentReviewContentSnapshotResponse;
  block: DocumentReviewBlockItemResponse;
  items: DocumentReviewContentPartResponse[];
  next_cursor: string | null;
};

export type PublicationExpectedSource = ReviewExpectedSourceRequest & {
  review_record_id: string | null;
  review_sequence: number;
  preview_run_id: string | null;
  preview_revision: number | null;
  quality_summary_sha256: string;
};

export type DocumentPublishRequest = {
  request_id: string;
  note: string;
  expected_source: PublicationExpectedSource;
};

export type DocumentPublicationResourceVersionResponse = {
  resource_id: string;
  version: string;
  snapshot_hash: string;
};

export type DocumentPublicationVersionsResponse = {
  template: DocumentPublicationResourceVersionResponse;
  symbol_rules: DocumentPublicationResourceVersionResponse;
  renderer_implementation_sha256: string;
  translation_status: "complete" | "not_applicable";
  models: string[];
};

export type DocumentPublicationRecordResponse = {
  publication_id: string;
  job_id: string;
  generation: number;
  source_file_id: string;
  source_sha256: string;
  result_file_id: string;
  result_sha256: string;
  review_record_id: string;
  review_sequence: number;
  preview_run_id: string;
  published_by: string;
  published_at: string;
  note: string;
  versions: DocumentPublicationVersionsResponse;
};

export type DocumentPublishResponse = {
  publication: DocumentPublicationRecordResponse;
  available_actions: Record<DocumentJobActionId, DocumentJobAvailableAction>;
};

export type DocumentPublicationPreflightCheckResponse = {
  code: string;
  status: "passed" | "blocked" | "not_checked";
  reason_code: string | null;
  message: string;
};

export type DocumentPublicationDownloadUrlResponse = {
  publication_id: string;
  job_id: string;
  result_file_id: string;
  result_sha256: string;
  size_bytes: number;
  download_url: string;
  expires_at: string;
  method: "GET";
  classification: "final_delivery";
};

export type DocumentPublicationsResponse = {
  preflight_checks: DocumentPublicationPreflightCheckResponse[];
  download_actions: Record<string, DocumentJobAvailableAction>;
  job_id: string;
  expected_source: PublicationExpectedSource;
  items: DocumentPublicationRecordResponse[];
  available_actions: Record<DocumentJobActionId, DocumentJobAvailableAction>;
};

export type TableValueColumnTargetHeader = "MIN" | "TYP" | "MAX" | "NOM" | "LOW" | "HIGH";

export type ManualTableValueColumnCorrectionRequest = {
  source_row_index: number;
  source_cell_index: number;
  content_sha256: string;
  original_column_range: [number, number];
  target_column: number;
  target_header: TableValueColumnTargetHeader;
};

export type ManualTableValueColumnReviewRequest = {
  schema_version: "table-value-column-review/v1";
  source_pdf_sha256: string;
  content_list_sha256: string;
  page_index: number;
  json_pointer: string;
  raw_html_sha256: string;
  normalizer_version: "table-html/v1";
  corrections: ManualTableValueColumnCorrectionRequest[];
};

export type DocumentJobNewGenerationRequest = {
  request_id: string;
  note: string;
  expected_source: ReviewExpectedSourceRequest;
  action?: "replay_table_value_columns" | null;
  table_value_column_reviews?: ManualTableValueColumnReviewRequest[] | null;
};

export type DocumentJobGenerationCurrentResponse = {
  id: string;
  status: DocumentJobStatus;
  stage: DocumentJobStage;
  progress: number;
  retry_count: number;
  result_file_id: string | null;
  quality_status: DocumentJobQualityStatus;
  review_status: DocumentJobReviewStatus;
  delivery_status: DocumentJobDeliveryStatus;
};

export type DocumentJobNewGenerationResponse = {
  accepted: true;
  request_id: string;
  job_id: string;
  accepted_generation: number;
  accepted_at: string;
  source: ReviewExpectedSourceRequest;
  audit_id: string;
  replayed: boolean;
  current_generation: number;
  current_job: DocumentJobGenerationCurrentResponse;
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
  | "page_degraded"
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
  failure_diagnostic?: DocumentJobFailureDiagnostic | null;
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
  // 这些字段由新后端按行投影；旧部署缺失时仍保留原始批次诊断。
  is_effective_leaf?: boolean;
  failure_disposition?: DocumentJobTranslationBatchFailureDisposition;
};

export type DocumentJobTranslationBatchOutcome =
  | "not_started"
  | "running"
  | "retrying"
  | "validating"
  | "failed"
  | "completed"
  | "canceled";

export type DocumentJobTranslationBatchFailureDisposition =
  | "none"
  | "retrying"
  | "terminal"
  | "stopped"
  | "superseded";

export type DocumentJobTranslationBatchExecutionResponse = {
  outcome: DocumentJobTranslationBatchOutcome;
  leaf_count: number;
  succeeded_leaf_count: number;
  active_leaf_count: number;
  retryable_failed_leaf_count: number;
  terminal_failed_leaf_count: number;
  failure_batch_id: string | null;
  reason_code: string | null;
  reason_message: string | null;
  partial_artifacts_debug_only: boolean;
};

export type DocumentJobTranslationBatchListResponse = {
  job_id: string;
  generation: number;
  items: DocumentJobTranslationBatchSummaryResponse[];
  // additive 字段：旧 API 省略时前端不得推导终态或发布资格。
  execution?: DocumentJobTranslationBatchExecutionResponse | null;
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

export type DocumentJobDownloadUrlResponse = DocumentJobDownloadAvailability & {
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
  legacy_internal_only: boolean;
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
  legacy_internal_only: boolean;
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
  min?: number;
  max?: number;
  step?: number;
};

export type TemplateLayoutConfigCategorySchema = {
  key: string;
  label: string;
  order: number;
  groups: string[];
};

export type TemplateLayoutConfigGroupMeta = {
  label: string;
  category: string;
  description: string;
  order: number;
};

export type TemplateLayoutConfigResponse = {
  template_id: string;
  template_version_id: string | null;
  version: number;
  status: TemplateVersionStatus;
  is_default: boolean;
  active_template_version_id: string;
  source_path: string | null;
  config_sha256: string | null;
  snapshot_hash: string | null;
  meta: Record<string, unknown>;
  config: Record<string, unknown>;
  preview_samples: Record<string, unknown>;
  field_schema: {
    schema_version: string;
    meta: Record<string, TemplateLayoutConfigFieldSchema>;
    categories: TemplateLayoutConfigCategorySchema[];
    group_meta: Record<string, TemplateLayoutConfigGroupMeta>;
    groups: Record<string, Record<string, TemplateLayoutConfigFieldSchema>>;
  };
};

export type TemplateLayoutConfigDraftRequest = {
  base_template_version_id: string;
  expected_config_sha256: string;
  expected_active_template_version_id: string;
  changes: Record<string, Record<string, unknown>>;
  change_note?: string;
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
  language_pair: TranslationLanguagePair;
  default_version: string | null;
  version_count: number;
  target_language: string;
  domain: string;
  prompt_version: string;
  prompt_content_hash: string;
  model: string | null;
  max_pages_per_batch: number;
  max_chars_per_batch: number;
};

export type TranslationProfileListResponse = {
  items: TranslationProfileListItemResponse[];
};

export type TranslationProfileVersionResponse = {
  translation_profile_id: string;
  language_pair: TranslationLanguagePair;
  version: string;
  status: string;
  snapshot_hash: string | null;
  is_default: boolean;
  target_language: string;
  domain: string;
  prompt_version: string;
  prompt_content_hash: string;
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

export type TranslationProfilePromptSchemeResponse = {
  id: string;
  name: string;
  markdown: string;
  content_hash: string;
  built_in: boolean;
  is_active: boolean;
  deletable: boolean;
  delete_disabled_reason: string | null;
};

export type TranslationProfileDraftResponse = {
  translation_profile_id: string;
  language_pair: TranslationLanguagePair;
  base_version: string | null;
  target_language: string;
  domain: string;
  prompt_version: string;
  prompt_schemes: TranslationProfilePromptSchemeResponse[];
  model: string | null;
  max_pages_per_batch: number;
  max_chars_per_batch: number;
  snapshot_hash: string | null;
};

export type TranslationProfileDraftUpdateRequest = {
  language_pair?: TranslationLanguagePair | null;
  target_language: string;
  domain: string;
  model: string | null;
  max_pages_per_batch: number;
  max_chars_per_batch: number;
  expected_snapshot_hash?: string | null;
};

export type TranslationProfilePromptCreateRequest = {
  name: string;
  source_prompt_id: string;
  expected_snapshot_hash: string;
};

export type TranslationProfilePromptUpdateRequest = {
  name: string;
  markdown: string;
  expected_snapshot_hash: string;
};

export type TranslationProfilePromptMutationRequest = {
  expected_snapshot_hash: string;
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
