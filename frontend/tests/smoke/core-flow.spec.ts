import { expect, test, type Page } from "@playwright/test";

const actionStates = {
  download: { enabled: true, disabled_reason: null, retryable: false },
  retry: { enabled: false, disabled_reason: "只有 failed 文档任务允许重试。", retryable: false },
  cancel: { enabled: false, disabled_reason: "只有 pending、queued、running 任务允许取消。", retryable: false },
  archive: { enabled: true, disabled_reason: null, retryable: false },
  unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
  clone: { enabled: true, disabled_reason: null, retryable: false },
};

const activeActionStates = {
  download: { enabled: false, disabled_reason: "任务尚未生成可下载结果。", retryable: false },
  retry: { enabled: false, disabled_reason: "只有 failed 文档任务允许重试。", retryable: false },
  cancel: { enabled: true, disabled_reason: null, retryable: false },
  archive: { enabled: false, disabled_reason: "只有 succeeded、failed、canceled 任务允许归档。", retryable: false },
  unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
  clone: { enabled: true, disabled_reason: null, retryable: false },
};

const documentJob = {
  id: "docjob_smoke_001",
  tenant_id: "tenant_default",
  company_id: "company_default",
  created_by: "user_operator",
  source_file_id: "file_source_smoke",
  source_job_id: null,
  mode: "direct_pdf_to_word",
  document_language: "auto",
  status: "succeeded",
  stage: "completed",
  progress: 100,
  template_version_id: "template_default",
  term_version_id: null,
  result_file_id: "file_result_smoke",
  mineru_raw_result_file_id: "file_mineru_raw_smoke",
  document_ir_file_id: "file_ir_smoke",
  image_asset_file_ids: [],
  debug_full_text_enabled: false,
  mineru_batch_id: "batch_smoke",
  mineru_data_id: "docjob_smoke_001",
  failed_stage: null,
  error_code: null,
  error_message: null,
  retry_count: 0,
  timeout_at: null,
  started_at: "2026-06-11T00:00:00Z",
  completed_at: "2026-06-11T00:01:00Z",
  canceled_at: null,
  archived_at: null,
  archived_by: null,
  translation_qa_status: "unreviewed",
  translation_qa_issue_type: null,
  translation_qa_note: null,
  translation_qa_reviewed_by: null,
  translation_qa_reviewed_at: null,
  request_snapshot: {
    source_file: { original_filename: "smoke.pdf" },
  },
  available_actions: actionStates,
  created_at: "2026-06-11T00:00:00Z",
  updated_at: "2026-06-11T00:01:00Z",
};

const activeJob = {
  ...documentJob,
  id: "docjob_active_001",
  source_file_id: "file_source_active",
  status: "running",
  stage: "parsing",
  progress: 45,
  result_file_id: null,
  mineru_raw_result_file_id: null,
  document_ir_file_id: null,
  started_at: "2026-06-11T00:03:00Z",
  completed_at: null,
  translation_qa_status: "unreviewed",
  request_snapshot: {
    source_file: { original_filename: "active-smoke.pdf" },
  },
  available_actions: activeActionStates,
  created_at: "2026-06-11T00:02:00Z",
  updated_at: "2026-06-11T00:03:00Z",
};

const translationQaJob = {
  ...documentJob,
  id: "docjob_qa_001",
  source_file_id: "file_source_qa",
  mode: "en2zh_pdf_to_word",
  document_language: "en",
  result_file_id: "file_result_qa",
  document_ir_file_id: "file_ir_qa",
  debug_full_text_enabled: true,
  translation_qa_status: "unreviewed",
  request_snapshot: {
    source_file: { original_filename: "qa-smoke.pdf" },
  },
};

const translationQaAvailableResponse = {
  job_id: translationQaJob.id,
  available: true,
  availability_reason: null,
  qa: {
    status: "unreviewed",
    issue_type: null,
    note: null,
    reviewed_by: null,
    reviewed_at: null,
  },
  artifacts: {
    document_ir_file_id: "file_ir_qa",
    ai_call_log_file_ids: ["file_ai_call_qa"],
    ai_debug_archive_file_ids: ["file_ai_debug_qa"],
  },
  summary: {
    final_segment_count: 1,
    returned_segment_count: 1,
    quality_flags: [],
    ai_call_count: 1,
    ai_call_statuses: { succeeded: 1 },
    term_trace_count: 1,
    source_comparison_available: true,
    source_comparison_reason: null,
  },
  segments: [
    {
      id: "segment_qa_001",
      block_id: "block_qa_001",
      page_index: 0,
      order: 0,
      block_type: "paragraph",
      field: "text",
      index: null,
      source_text: "Hello world.",
      ai_translation_text: "你好，世界。",
      final_text: "你好，世界。",
      source_available: true,
    },
  ],
  term_traces: [
    {
      segment_id: "segment_qa_001",
      batch_id: "batch_qa",
      translation_term_set_id: "translation_term_default",
      translation_term_version: "1",
      source_term: "world",
      target_term: "世界",
      match_start: 6,
      match_end: 11,
      context: {},
      injected_to_glossary: true,
      provider_trace_id: "provider_trace_qa",
    },
  ],
  ai_calls: [
    {
      file_id: "file_ai_call_qa",
      call_id: "call_qa_001",
      status: "succeeded",
      provider: { backend: "mock", model: "smoke" },
      language_pair: "en-zh",
      source_language: "en",
      target_language: "zh",
      term_version_id: "translation_term_default@1",
      term_snapshot_hash: "hash_qa",
      term_count: 1,
      item_count: 1,
      char_count: 12,
      duration_ms: 120,
      created_at: "2026-06-11T00:01:00Z",
      error_type: null,
      error_message: null,
    },
  ],
};

const translationQaUnavailableResponse = {
  ...translationQaAvailableResponse,
  available: false,
  availability_reason: "document_ir_missing",
  artifacts: {
    document_ir_file_id: null,
    ai_call_log_file_ids: [],
    ai_debug_archive_file_ids: [],
  },
  summary: {
    final_segment_count: 0,
    returned_segment_count: 0,
    quality_flags: ["artifact_missing"],
    ai_call_count: 0,
    ai_call_statuses: {},
    term_trace_count: 0,
    source_comparison_available: false,
    source_comparison_reason: "ai_debug_archive_missing",
  },
  segments: [],
  term_traces: [],
  ai_calls: [],
};

type MockApiOptions = {
  configSummaryError?: boolean;
  downloadConflict?: boolean;
  translationQaUnavailable?: boolean;
};

type MockApiControls = {
  translationQaPatchCount: () => number;
};

type MockRole = "operator" | "admin";

const operatorPermissions = [
  "document_jobs:read",
  "document_jobs:create",
  "document_jobs:download",
  "document_jobs:retry",
  "document_jobs:cancel",
  "document_jobs:archive",
  "document_jobs:clone",
  "translation_qa:read",
  "translation_qa:write",
  "term_proposals:read",
  "term_proposals:create",
];

const adminPermissions = [
  ...operatorPermissions,
  "settings:read",
  "system:read",
  "ops:read",
  "audit:read",
  "files:retention",
];

function mockUser(role: MockRole) {
  const isAdmin = role === "admin";
  return {
    id: isAdmin ? "user_admin" : "user_operator",
    username: role,
    role,
    roles: [role],
    permissions: isAdmin ? adminPermissions : operatorPermissions,
    tenant_id: "tenant_default",
    company_id: "company_default",
    display_name: isAdmin ? "Admin" : "Operator",
  };
}

const failedJob = {
  ...documentJob,
  id: "docjob_failed_001",
  source_file_id: "file_source_failed",
  status: "failed",
  stage: "failed",
  progress: 70,
  result_file_id: null,
  failed_stage: "rendering",
  error_code: "render_failed",
  error_message: "渲染阶段失败。",
  completed_at: null,
  request_snapshot: {
    source_file: { original_filename: "failed-smoke.pdf" },
  },
  available_actions: {
    ...actionStates,
    download: { enabled: false, disabled_reason: "任务尚未生成可下载结果。", retryable: false },
    retry: { enabled: true, disabled_reason: null, retryable: false },
  },
};

const healthReady = {
  status: "ready",
  app_name: "md2word",
  jobs_dir: "/tmp/md2word-jobs",
  dependency_checks: {
    deployment_init_ready: true,
    readiness_blockers: [],
    readiness_warnings: [],
    public_deployment_mode: "smoke",
    configured_repository_backend: "sqlite",
    effective_repository_backend: "sqlite",
    worker_mode: "external",
    document_jobs_worker_backend: "external",
    document_jobs_automatic_execution_enabled: true,
    p0_document_jobs_required: true,
    p0_document_jobs_ready: true,
    artifact_storage: "local_file",
    artifact_root_writable: true,
    artifact_disk_free_bytes: 1024 * 1024 * 1024,
    stage_dispatcher: "database",
    stage_message_store: "sqlite",
    stage_spool_needs_attention: false,
    stage_spool_observation_status: "clear",
    stage_spool_oldest_running_age_seconds: 0,
    stage_spool_running_stale_messages: 0,
    stage_spool_replayable_messages: 0,
    document_job_callback_replayable_messages: 0,
    document_job_callback_failed_messages: 0,
    document_job_callback_oldest_replayable_age_seconds: 0,
    default_template_version: "template_default@1",
    default_term_rule_version: "term_rule_default@1",
    default_translation_profile_version: "translation_profile_default@1",
  },
};

const healthMetrics = {
  status: "ok",
  app_name: "md2word",
  generated_at: "2026-06-11T00:05:00Z",
  metadata_store: "sqlite",
  artifact_storage: "local_file",
  worker_mode: "external",
  stage_dispatcher: "database",
  jobs: { succeeded: 1, failed: 1, running: 1 },
  document_jobs: { succeeded: 1, failed: 1, running: 1 },
  stage_messages: { pending: 0, running: 0, failed: 0 },
  document_job_callback_messages: { pending: 0, running: 0, failed: 0 },
  resources: {
    template_versions: 1,
    term_rule_set_versions: 1,
    translation_profile_versions: 1,
  },
  audit_events: { total: 3 },
};

const activeOpsAlert = {
  code: "stage_spool_failed_messages_present",
  severity: "warning",
  source: "stage_spool",
  title: "Stage spool failed messages",
  description: "Smoke alert for controlled real-send gates.",
  count: 1,
  suggested_route: "/system-status/ops-dashboard",
  suggested_action: "preview alert delivery",
};

const opsAlerts = {
  status: "watch",
  app_name: "md2word",
  generated_at: "2026-06-11T00:05:00Z",
  summary: {
    readiness_blockers: 0,
    readiness_warnings: 0,
    stage_failed_messages: 1,
    stage_stale_running_messages: 0,
    stage_replayable_messages: 0,
    callback_failed_messages: 0,
    callback_replayable_messages: 0,
    callback_oldest_replayable_age_seconds: 0,
    failed_jobs: 1,
    running_jobs: 1,
    worker_mode: "external",
    stage_dispatcher: "database",
    stage_message_store: "sqlite",
    artifact_storage: "local_file",
  },
  alerts: [activeOpsAlert],
  safety: {
    read_only: true,
    writes_performed: false,
    recovery_actions_executed: false,
    provider_calls_executed: false,
    notification_delivery_executed: false,
    audit_events_written: false,
  },
};

const integrationCapabilitySafety = {
  read_only: true,
  provider_calls_executed: false,
  external_delivery_executed: false,
  s3_delete_executed: false,
  cleanup_scheduler_executed: false,
  quota_enforcement_executed: false,
  cleanup_executed: false,
  delete_executed: false,
  conversion_workflow_executed: false,
  audit_events_written: false,
  secret_values_exposed: false,
};

const integrationCapabilities = {
  generated_at: "2026-06-11T00:05:00Z",
  action_mode: "read_only",
  overall_status: "partial",
  capabilities: [
    {
      capability_id: "alert_delivery",
      label: "Alert Delivery",
      category: "notification",
      status: "ready",
      real_execution_enabled: true,
      dry_run_only: false,
      kill_switch_active: false,
      configured: true,
      ready: true,
      blocking_reasons: [],
      required_gates: ["pilot_alert_active", "preview_without_missing_gates", "confirmation_phrase"],
      safe_config: { destination_id: "ops-slack-primary", dry_run: false },
    },
  ],
  safety: integrationCapabilitySafety,
};

const alertDeliverySafety = {
  external_delivery_executed: false,
  provider_calls_executed: false,
  cleanup_executed: false,
  delete_executed: false,
  conversion_workflow_executed: false,
  audit_events_written: false,
  secret_values_exposed: false,
};

const alertDeliveryContract = {
  generated_at: "2026-06-11T00:05:00Z",
  action_mode: "adapter_contract",
  contract_version: "smoke-v1",
  fake_adapter_id: "fake-alert-smoke",
  fake_adapter_mode: "fake",
  real_channels: ["slack"],
  required_request_fields: ["alert_codes"],
  required_result_fields: ["outcome", "missing_gates"],
  required_audit_fields: ["action_mode"],
  required_safety_fields: ["external_delivery_executed"],
  parity_checks: { shape: true },
  destination_count: 1,
  destination_channels: ["slack"],
  blocking_reasons: [],
  safety: {
    read_only: true,
    provider_calls_executed: false,
    external_delivery_executed: false,
    audit_events_written: false,
    cleanup_executed: false,
    delete_executed: false,
    conversion_workflow_executed: false,
    secret_values_exposed: false,
  },
};

const realSendPreview = {
  generated_at: "2026-06-11T00:05:01Z",
  action_mode: "real_send_preview",
  channel: "slack",
  confirmation_phrase: "SEND REAL OPS ALERTS",
  dedupe_window_minutes: 60,
  requested_alert_codes: [activeOpsAlert.code],
  requested_destination_ids: ["ops-slack-primary"],
  delivery_id: "delivery_smoke_preview",
  totals: { requested: 1, deliverable: 1, blocked: 0 },
  gate_snapshot: { pilot_alert_active: true, capability_ready: true },
  rollback: { dry_run: true },
  items: [
    {
      alert_code: activeOpsAlert.code,
      destination_id: "ops-slack-primary",
      target_label: "#ops-alerts-phase7-pilot",
      severity: "warning",
      source: "stage_spool",
      title: activeOpsAlert.title,
      outcome: "deliverable",
      dedupe_key: "smoke-dedupe",
      idempotency_key: "smoke-idempotency",
      missing_gates: [],
      reason: "preview only",
      audit_event_written: false,
      adapter_result: null,
    },
  ],
  safety: alertDeliverySafety,
};

const s3DeleteContract = {
  generated_at: "2026-06-11T00:05:00Z",
  action_mode: "adapter_contract",
  contract_version: "smoke-v1",
  fake_adapter_id: "fake-s3-smoke",
  fake_adapter_mode: "fake",
  fake_file_retention_contract_version: "smoke-v1",
  localstack_profile: {
    harness: "localstack",
    endpoint_required: true,
    versioned_bucket_required: true,
    exact_bucket_key_required: true,
    version_id_supported: true,
    etag_precondition_supported: true,
    runtime_executed: false,
    provider_payload_persisted: false,
    secrets_required_for_contract_report: false,
  },
  storage_config_summary: { provider: "local_file", bucket_configured: false },
  required_request_fields: ["file_ids"],
  required_result_fields: ["outcome"],
  required_audit_fields: ["action_mode"],
  required_safety_fields: ["real_s3_delete_executed"],
  parity_checks: { shape: true },
  blocking_reasons: [],
  safety: {
    read_only: true,
    provider_calls_executed: false,
    real_s3_delete_executed: false,
    localstack_calls_executed: false,
    cleanup_executed: false,
    scheduler_loop_executed: false,
    delete_executed: false,
    metadata_mutated: false,
    audit_events_written: false,
    conversion_workflow_executed: false,
    secret_values_exposed: false,
  },
};

const providerCancellationSemantics = {
  generated_at: "2026-06-11T00:05:00Z",
  action_mode: "semantics_verification",
  provider: "mineru",
  verification_status: "verified",
  checked_on: "2026-06-11",
  decision: "fake_only",
  public_docs_support_real_cancel: false,
  real_provider_cancel_allowed: false,
  supported_provider_operations: ["query"],
  documented_task_statuses: ["processing", "completed"],
  unsupported_operations: ["real_cancel"],
  blocking_reasons: [],
  recommended_next_steps: ["继续使用 fake cancellation audit"],
  sources: [
    {
      label: "Smoke source",
      url: "https://example.invalid/mineru-cancellation",
      source_type: "primary_docs",
      finding: "No documented real cancellation endpoint in smoke fixture.",
    },
  ],
  safety: {
    read_only: true,
    real_provider_cancel_executed: false,
    provider_calls_executed: false,
    local_job_mutated: false,
    queue_mutated: false,
    cleanup_executed: false,
    delete_executed: false,
    conversion_workflow_executed: false,
    audit_events_written: false,
    secret_values_exposed: false,
  },
};

const recoveryActions = {
  generated_at: "2026-06-11T00:05:00Z",
  actions: [
    {
      action_id: "document_job.replay_execution",
      label: "Replay execution",
      category: "recovery",
      target_type: "document_job",
      available: true,
      requires_admin: true,
      requires_reason: true,
      requires_confirmation: false,
      dry_run_supported: true,
      mutates_metadata: true,
      mutates_queue: true,
      calls_provider: false,
      sends_notification: false,
      deletes_data: false,
      audit_action: "ops.document_job_replay",
      known_gaps: [],
      suggested_route: "/system-status/ops-dashboard",
      description: "Replay failed execution from existing metadata.",
    },
  ],
  safety: {
    read_only: true,
    execution_performed: false,
    metadata_mutated: false,
    queue_mutated: false,
    provider_calls_executed: false,
    notification_delivery_executed: false,
    cleanup_executed: false,
    delete_executed: false,
    audit_events_written: false,
  },
};

const storageUsage = {
  generated_at: "2026-06-11T00:05:00Z",
  artifact_storage: "local_file",
  artifact_root_writable: true,
  artifact_disk_free_bytes: 1024 * 1024 * 1024,
  totals: {
    file_count: 1,
    size_bytes: 1024,
    expired_count: 0,
    expired_size_bytes: 0,
    estimated_reclaimable_count: 0,
    estimated_reclaimable_size_bytes: 0,
  },
  reclaim: { estimated_reclaimable_size_bytes: 0 },
  quota: { status: "ready", usage_ratio: 0.01, warning_threshold_ratio: 0.8, block_threshold_ratio: 0.95 },
  by_storage_provider: [],
  by_file_type: [],
  by_status: [],
};

const retentionPlan = {
  generated_at: "2026-06-11T00:05:00Z",
  retention_days: 30,
  deletion_supported: true,
  action_mode: "dry_run",
  totals: { candidate_files: 0, candidate_size_bytes: 0 },
  candidates: [],
  marked_file_ids: [],
};

const retentionPolicies = {
  generated_at: "2026-06-11T00:05:00Z",
  fallback_retention_days: 30,
  effective: [
    {
      retention_days: 30,
      source: "settings_fallback",
      policy_id: null,
      scope_type: null,
      file_type: null,
      reason: "settings fallback",
    },
  ],
  items: [],
};

const quotaOpsSummary = {
  generated_at: "2026-06-11T00:05:00Z",
  action_mode: "quota_policy_ops_summary",
  policy: {
    enabled: true,
    dry_run: true,
    configured: true,
    quota_bytes: 104857600,
    status: "ready",
    warning_threshold_ratio: 0.8,
    block_threshold_ratio: 0.95,
    warning_threshold_bytes: 83886080,
    block_threshold_bytes: 99614720,
    upload_max_bytes: 10485760,
    config_errors: [],
  },
  usage: {
    current_used_size_bytes: 1024,
    proposed_upload_size_bytes: 0,
    projected_used_size_bytes: 1024,
    current_usage_ratio: 0.01,
    projected_usage_ratio: 0.01,
  },
  enforcement_ready: true,
  current_usage_would_warn: false,
  current_usage_would_block: false,
  kill_switch_enabled: false,
  reasons: [],
  rollback_options: [],
  audit_replay: [],
  audit_replay_total: 0,
  audit_replay_limit: 20,
  audit_replay_truncated: false,
  safety: {
    read_only: true,
    upload_authorization_created: false,
    upload_content_written: false,
    upload_blocking_executed: false,
    metadata_mutated: false,
    quota_enforcement_executed: false,
    cleanup_executed: false,
    delete_executed: false,
    scheduler_loop_executed: false,
    provider_calls_executed: false,
    conversion_workflow_executed: false,
    audit_events_written: false,
  },
};

const cleanupRunHistory = {
  page: 1,
  page_size: 25,
  total: 0,
  items: [],
};

const fileLibrarySearch = {
  generated_at: "2026-06-11T00:05:00Z",
  page: 1,
  page_size: 20,
  total: 1,
  sort: "created_at_desc",
  filters: {},
  items: [
    {
      file_id: "file_source_smoke",
      job_id: "docjob_smoke_001",
      file_type: "source_pdf",
      storage_provider: "local_file",
      original_filename: "smoke.pdf",
      mime_type: "application/pdf",
      size_bytes: 1024,
      status: "uploaded",
      expires_at: "2026-07-11T00:00:00Z",
      created_by: "user_operator",
      created_at: "2026-06-11T00:00:00Z",
      updated_at: "2026-06-11T00:00:00Z",
      expired: false,
      physical_delete_candidate: false,
    },
  ],
};

async function mockApi(page: Page, options: MockApiOptions = {}): Promise<MockApiControls> {
  let currentRole: MockRole = "operator";
  let translationQaPatchCount = 0;

  await page.route("**/api/v1/auth/login", async (route) => {
    const payload = route.request().postDataJSON() as { username?: string } | null;
    currentRole = payload?.username === "admin" ? "admin" : "operator";
    const user = mockUser(currentRole);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "smoke-token",
        token_type: "bearer",
        expires_in: 3600,
        user_id: user.id,
        username: user.username,
        role: user.role,
        roles: user.roles,
        permissions: user.permissions,
        tenant_id: user.tenant_id,
        company_id: user.company_id,
      }),
    });
  });
  await page.route("**/api/v1/auth/me", async (route) => {
    const user = mockUser(currentRole);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(user),
    });
  });
  await page.route("**/api/v1/health/ready", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(healthReady) });
  });
  await page.route("**/api/v1/health/metrics", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(healthMetrics) });
  });
  await page.route("**/api/v1/health/ops-alerts", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(opsAlerts) });
  });
  await page.route("**/api/v1/ops/integration-capabilities", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(integrationCapabilities) });
  });
  await page.route("**/api/v1/ops/recovery-actions", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(recoveryActions) });
  });
  await page.route("**/api/v1/ops/alert-deliveries/adapter-contract", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(alertDeliveryContract) });
  });
  await page.route("**/api/v1/ops/alert-deliveries/real-send/preview", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(realSendPreview) });
  });
  await page.route("**/api/v1/ops/s3-deletions/adapter-contract", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(s3DeleteContract) });
  });
  await page.route("**/api/v1/ops/provider-cancellations/semantics-verification", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(providerCancellationSemantics) });
  });
  await page.route("**/api/v1/files/library/search**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fileLibrarySearch) });
  });
  await page.route("**/api/v1/files/storage/usage", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(storageUsage) });
  });
  await page.route("**/api/v1/files/retention/plan", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(retentionPlan) });
  });
  await page.route("**/api/v1/files/retention/policies", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(retentionPolicies) });
  });
  await page.route("**/api/v1/files/quota-policy/ops-summary**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quotaOpsSummary) });
  });
  await page.route("**/api/v1/files/retention/cleanup-runs/history**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(cleanupRunHistory) });
  });
  await page.route("**/api/v1/document-jobs/docjob_smoke_001/events", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: documentJob.id,
        items: [
          {
            id: "event_smoke_completed",
            job_id: documentJob.id,
            tenant_id: "tenant_default",
            company_id: "company_default",
            created_by: "worker",
            stage: "completed",
            level: "info",
            event_type: "stage_completed",
            message: "任务已完成。",
            payload: {},
            duration_ms: 1000,
            trace_id: "trace_smoke",
            created_at: "2026-06-11T00:01:00Z",
          },
        ],
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_smoke_001/files", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: documentJob.id,
        files: [
          {
            id: "file_result_smoke",
            tenant_id: "tenant_default",
            company_id: "company_default",
            job_id: documentJob.id,
            file_type: "generated_word",
            storage_provider: "local_file",
            bucket: "local",
            object_key: "document-jobs/tenant_default/docjob_smoke_001/smoke.docx",
            original_filename: "smoke.docx",
            mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes: 1024,
            checksum_sha256: null,
            etag: null,
            status: "uploaded",
            expires_at: null,
            metadata: {},
            created_by: "worker",
            created_at: "2026-06-11T00:01:00Z",
            updated_at: "2026-06-11T00:01:00Z",
          },
        ],
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_smoke_001/callback-messages/summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: documentJob.id,
        status_counts: { processed: 1 },
        replayable_count: 0,
        oldest_replayable_age_seconds: 0,
        recent_problem_messages: [],
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_smoke_001/download-url", async (route) => {
    if (options.downloadConflict) {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          error_code: "document_job_not_downloadable",
          detail: "任务状态已变化，请刷新后重试。",
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: documentJob.id,
        file_id: "file_result_smoke",
        download_url: "/api/v1/files/file_result_smoke/content",
        method: "GET",
        expires_at: "2026-06-11T00:11:00Z",
        file: {
          id: "file_result_smoke",
          tenant_id: "tenant_default",
          company_id: "company_default",
          job_id: documentJob.id,
          file_type: "generated_word",
          storage_provider: "local_file",
          bucket: "local",
          object_key: "document-jobs/tenant_default/docjob_smoke_001/smoke.docx",
          original_filename: "smoke.docx",
          mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          size_bytes: 1024,
          checksum_sha256: null,
          etag: null,
          status: "uploaded",
          expires_at: null,
          metadata: {},
          created_by: "worker",
          created_at: "2026-06-11T00:01:00Z",
          updated_at: "2026-06-11T00:01:00Z",
        },
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/config-summary", async (route) => {
    if (options.configSummaryError) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error_code: "config_summary_unavailable",
          detail: "任务配置摘要暂不可用。",
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        resource_mode: "repository",
        defaults: {
          template: { label: "template-default", resource_id: "template_default", version: "1" },
          term_rule_set: { label: "term-rule-default", resource_id: "term_rule_default", version: "1" },
          translation_term_set: { label: "translation-term-default", resource_id: "translation_term_default", version: "1" },
          translation_profile: { label: "translation-profile-default", resource_id: "translation_profile_default", version: "1" },
        },
        options: {
          templates: [],
          term_rule_sets: [],
          translation_term_sets: [],
          translation_profiles: [],
        },
        readiness: {
          p0_document_jobs_required: true,
          p0_document_jobs_ready: true,
          blockers: [],
          warnings: [],
        },
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_smoke_001", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(documentJob),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_qa_001/translation-qa**", async (route) => {
    if (route.request().method() === "PATCH") {
      translationQaPatchCount += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: translationQaJob.id,
          qa: {
            status: "approved",
            issue_type: null,
            note: "smoke",
            reviewed_by: "user_operator",
            reviewed_at: "2026-06-11T00:06:00Z",
          },
          job: { ...translationQaJob, translation_qa_status: "approved" },
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(options.translationQaUnavailable ? translationQaUnavailableResponse : translationQaAvailableResponse),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_qa_001", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(translationQaJob),
    });
  });
  await page.route("**/api/v1/document-jobs**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname !== "/api/v1/document-jobs") {
      await route.fallback();
      return;
    }
    const statusGroup = url.searchParams.get("status_group");
    const status = url.searchParams.get("status");
    const qaStatus = url.searchParams.get("translation_qa_status");
    const isTranslationQaQueue = qaStatus !== null;
    let items = [documentJob];
    let filteredSummary: Record<string, number> = { succeeded: 1 };
    if (statusGroup === "active") {
      items = [activeJob];
      filteredSummary = { running: 1 };
    } else if (status === "failed") {
      items = [failedJob];
      filteredSummary = { failed: 1 };
    } else if (status === "running") {
      items = [activeJob];
      filteredSummary = { running: 1 };
    } else if (isTranslationQaQueue) {
      items = qaStatus === "approved" ? [] : [translationQaJob];
      filteredSummary = qaStatus === "approved" ? {} : { succeeded: 1 };
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items,
        page: 1,
        page_size: 20,
        total: items.length,
        summary: { succeeded: 1, running: 1, failed: 1 },
        filtered_summary: filteredSummary,
        translation_qa_summary: isTranslationQaQueue
          ? { unreviewed: 1, approved: 0, needs_fix: 0, blocked: 0 }
          : { unreviewed: 0, approved: 0, needs_fix: 0, blocked: 0 },
      }),
    });
  });

  return {
    translationQaPatchCount: () => translationQaPatchCount,
  };
}

test("operator can log in and inspect the document job workbench", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();

  await expect(page).toHaveURL(/\/jobs(\?|$)/);
  await expect(page.getByRole("heading", { name: "任务列表" })).toBeVisible();
  await expect(page.getByText("smoke.pdf")).toBeVisible();
  await page.getByRole("button", { name: "处理中" }).click();
  await expect(page).toHaveURL(/status_group=active/);
  await expect(page.getByText("active-smoke.pdf")).toBeVisible();
  await expect(page.getByRole("link", { name: "smoke.pdf", exact: true })).toHaveCount(0);

  await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=1");
  await page.getByRole("link", { name: "docjob_smoke_001" }).click();
  await expect(page).toHaveURL(/\/jobs\/docjob_smoke_001$/);
  await expect(page.getByRole("heading", { name: "任务详情" })).toBeVisible();
  await expect(page.getByText("结果文件 ID")).toBeVisible();
  await expect(page.getByRole("button", { name: "下载" })).toBeEnabled();
  await page.getByRole("button", { name: "下载" }).click();
  await expect(page.getByText("下载链接已生成")).toBeVisible();
});

test("operator sees list action conflicts after the refresh completes", async ({ page }) => {
  await mockApi(page, { downloadConflict: true });

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/jobs(\?|$)/);

  await page.getByRole("button", { name: "下载" }).click();
  await expect(page.getByText("任务状态已变化，请刷新后重试。")).toBeVisible();
  await expect(page.getByText("状态码 409")).toBeVisible();
  await expect(page.getByText("smoke.pdf")).toBeVisible();
});

test("operator cannot create a job when config summary is unavailable", async ({ page }) => {
  await mockApi(page, { configSummaryError: true });

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/jobs(\?|$)/);

  await page.goto("/jobs/new");
  await expect(page.getByRole("heading", { name: "创建转换任务" })).toBeVisible();
  await expect(page.getByText("任务配置摘要暂不可用。")).toBeVisible();
  await page.locator("input[type='file']").setInputFiles({
    name: "smoke.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n%%EOF\n"),
  });
  await expect(page.getByText("已选择 smoke.pdf。")).toBeVisible();
  await expect(page.getByRole("button", { name: "创建任务" })).toBeDisabled();
});

test("operator sees an explicit forbidden state for admin-only routes", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/jobs(\?|$)/);

  await page.goto("/settings");
  await expect(page).toHaveURL(/\/forbidden/);
  await expect(page.getByRole("heading", { name: "当前账号没有访问权限" })).toBeVisible();
  await expect(page.getByText("settings:read")).toBeVisible();
});

test("operator can inspect the translation QA queue with backend all-status summary", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/jobs(\?|$)/);

  await page.goto("/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=1");
  await expect(page.getByRole("heading", { name: "翻译 QA 队列" })).toBeVisible();
  await expect(page.getByText("qa-smoke.pdf")).toBeVisible();
  await expect(page.getByText("未复核").first()).toBeVisible();
  await expect(page.getByText("除 QA 状态外的当前筛选").first()).toBeVisible();
});

test("operator sees unavailable translation QA as readonly and cannot submit review", async ({ page }) => {
  const controls = await mockApi(page, { translationQaUnavailable: true });

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/jobs(\?|$)/);

  await page.goto("/jobs/docjob_qa_001/translation-qa");
  await expect(page.getByRole("heading", { name: "翻译 QA", level: 1 })).toBeVisible();
  await expect(page.getByText("任务缺少 DocumentIR 证据文件，无法展示最终文本片段。")).toBeVisible();
  await expect(page.getByRole("button", { name: "保存复核" })).toBeDisabled();
  expect(controls.translationQaPatchCount()).toBe(0);
});

test("admin can inspect status, ops gates, and file retention workspaces", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("admin");
  await page.getByPlaceholder("请输入密码").fill("admin-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/jobs(\?|$)/);

  await page.goto("/system-status");
  await expect(page.getByRole("heading", { name: "系统状态", level: 1 })).toBeVisible();
  await expect(page.getByText("md2word").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "运维看板" })).toBeVisible();

  await page.goto("/system-status/ops-dashboard");
  await expect(page.getByRole("heading", { name: "运维看板", level: 1 })).toBeVisible();
  await expect(page.getByText("必须先完成一次无 missing gates 的 real-send preview").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Real-send", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Preview real-send gates" }).click();
  await expect(page.getByText("real_send_preview").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Real-send", exact: true })).toBeEnabled();

  await page.goto("/system-status/file-retention");
  await expect(page.getByRole("heading", { name: "文件管理与清理", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "文件库搜索" })).toBeVisible();
  await expect(page.getByText("smoke.pdf")).toBeVisible();
  await page.getByRole("button", { name: /清理执行/ }).click();
  await expect(page.getByRole("heading", { name: "过期候选" })).toBeVisible();
  await expect(page.getByRole("button", { name: "执行物理删除" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "执行 cleanup run" })).toBeDisabled();
});
