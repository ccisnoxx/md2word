// 文件：frontend/tests/smoke/core-flow.spec.ts
// 用途：覆盖内部工作台核心操作流程的浏览器 smoke。
import { expect, test, type Page } from "@playwright/test";
import { activateSkipLink, expectNoPageHorizontalOverflow, WORKBENCH_VIEWPORTS } from "./support/accessibility";

const adminOnlyDeleteReason = "只有 admin 可以删除文档任务。";

const actionStates = {
  download: { enabled: true, disabled_reason: null, retryable: false },
  retry: { enabled: false, disabled_reason: "只有 failed 文档任务允许重试。", retryable: false },
  cancel: { enabled: false, disabled_reason: "只有 pending、queued、running 任务允许取消。", retryable: false },
  archive: { enabled: true, disabled_reason: null, retryable: false },
  unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
  clone: { enabled: true, disabled_reason: null, retryable: false },
  delete: { enabled: false, disabled_reason: adminOnlyDeleteReason, retryable: false },
};

const activeActionStates = {
  download: { enabled: false, disabled_reason: "任务尚未生成可下载结果。", retryable: false },
  retry: { enabled: false, disabled_reason: "只有 failed 文档任务允许重试。", retryable: false },
  cancel: { enabled: true, disabled_reason: null, retryable: false },
  archive: { enabled: false, disabled_reason: "只有 succeeded、failed、canceled 任务允许归档。", retryable: false },
  unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
  clone: { enabled: true, disabled_reason: null, retryable: false },
  delete: { enabled: false, disabled_reason: "只有终态任务允许删除；处理中任务请先取消。", retryable: false },
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
  deleted_at: null,
  deleted_by: null,
  delete_reason: null,
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

const translationQaBlockedJob = {
  ...translationQaJob,
  id: "docjob_qa_002",
  source_file_id: "file_source_qa_blocked",
  result_file_id: "file_result_qa_blocked",
  document_ir_file_id: "file_ir_qa_blocked",
  translation_qa_status: "blocked",
  translation_qa_issue_type: "artifact_missing",
  translation_qa_note: "debug archive missing",
  request_snapshot: {
    source_file: { original_filename: "qa-blocked-smoke.pdf" },
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
    ai_debug_archive_expires_at: "2026-06-18T00:00:00Z",
    ai_debug_archive_expired: false,
    ai_debug_archive_contains_full_text: true,
  },
  summary: {
    final_segment_count: 2,
    returned_segment_count: 2,
    quality_flags: [],
    ai_call_count: 1,
    ai_call_statuses: { succeeded: 1 },
    term_trace_count: 1,
    debug_full_text_enabled: true,
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
    {
      id: "segment_qa_002",
      block_id: "block_qa_002",
      page_index: 0,
      order: 1,
      block_type: "paragraph",
      field: "text",
      index: null,
      source_text: "Second segment.",
      ai_translation_text: "第二段。",
      final_text: "第二段。",
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

const translationQaBlockedResponse = {
  ...translationQaAvailableResponse,
  job_id: translationQaBlockedJob.id,
  qa: {
    status: "blocked",
    issue_type: "artifact_missing",
    note: "debug archive missing",
    reviewed_by: "user_operator",
    reviewed_at: "2026-06-11T00:04:00Z",
  },
  segments: [
    {
      id: "segment_qa_blocked_001",
      block_id: "block_qa_blocked_001",
      page_index: 0,
      order: 0,
      block_type: "paragraph",
      field: "text",
      index: null,
      source_text: "Blocked evidence.",
      ai_translation_text: "阻塞证据。",
      final_text: "阻塞证据。",
      source_available: true,
    },
  ],
  term_traces: [],
};

const translationQaUnavailableResponse = {
  ...translationQaAvailableResponse,
  available: false,
  availability_reason: "document_ir_missing",
  artifacts: {
    document_ir_file_id: null,
    ai_call_log_file_ids: [],
    ai_debug_archive_file_ids: [],
    ai_debug_archive_expires_at: null,
    ai_debug_archive_expired: false,
    ai_debug_archive_contains_full_text: false,
  },
  summary: {
    final_segment_count: 0,
    returned_segment_count: 0,
    quality_flags: ["artifact_missing"],
    ai_call_count: 0,
    ai_call_statuses: {},
    term_trace_count: 0,
    debug_full_text_enabled: false,
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
  en2zhAvailable?: boolean;
  translationQaUnavailable?: boolean;
};

type DocumentJobCreatePayload = {
  source_file_id?: string;
  mode?: string;
  translation_mode?: string;
  document_language?: string;
};

type MockApiControls = {
  createdDocumentJobPayloads: () => DocumentJobCreatePayload[];
  translationQaPatchCount: () => number;
  layoutConfigDraftPayloads: () => Array<{
    base_template_version_id: string;
    expected_config_sha256: string;
    expected_active_template_version_id: string;
    changes: Record<string, unknown>;
  }>;
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

const templateDetail = {
  id: "default",
  name: "数据手册模板",
  description: "当前默认 DOCX 模板与绑定页面布局配置。",
  version: 1,
  is_default: true,
  downloadable: true,
  download_url: "/api/v1/templates/default/download",
  template: {
    label: "Word 模板",
    exists: true,
    file_name: "datasheet_template.docx",
    size_bytes: 1024,
    updated_at: "2026-06-11T00:00:00Z",
    sha256: "sha256:docx",
    download_url: "/api/v1/templates/default/download",
  },
  layout_config: {
    label: "页面布局 YAML",
    exists: true,
    file_name: "datasheet_template.yaml",
    size_bytes: 2048,
    updated_at: "2026-06-11T00:00:00Z",
    sha256: "sha256:layout",
    download_url: null,
  },
  subscript_config: {
    label: "术语上下标 YAML",
    exists: true,
    file_name: "subscripts_dictionary.yaml",
    size_bytes: 512,
    updated_at: "2026-06-11T00:00:00Z",
    sha256: "sha256:subscript",
    download_url: null,
  },
};

const templateLayoutConfig = {
  template_id: "default",
  template_version_id: "default@1",
  version: 1,
  status: "published",
  is_default: true,
  active_template_version_id: "default@1",
  source_path: "resources/template_configs/datasheet_template.yaml",
  config_sha256: "sha256:layout",
  snapshot_hash: "sha256:published",
  meta: {
    schema_version: "template-config/v1",
    template_name: "数据手册模板",
    output_filename: "datasheet_template.docx",
  },
  config: {
    page_setup: { top_margin: 2.3 },
    part_number: { font_size: 22 },
    category: { font_size: 12 },
    heading1: {
      font_name: "宋体",
      western_font_name: "Arial",
      complex_script_font_name: "Times New Roman",
      font_size: 13,
      bold: true,
      color: "#0c69b2",
      alignment: "left",
    },
    heading2: { font_size: 11 },
    heading3: { font_size: 10 },
    toc_title: { font_size: 13 },
    toc_level1: { font_size: 11 },
    toc_level2: { font_size: 10.5 },
    toc_level3: { font_size: 10 },
    normal: { font_size: 10.5, color: "#000000", alignment: "justify" },
    table_content: { font_size: 9 },
    table_style: { style_name: "Table Grid", header_fill: "#EEF3F8", border_color: "#C7CDD4" },
    table_note: { font_size: 8, italic: false },
    caption: { font_size: 9 },
    long_table_caption: { font_size: 10.5 },
    header: {
      enabled: false,
      logo_path: "assets/company_logo.png",
      title_text: "数据手册",
      title_font_name: "微软雅黑",
      title_western_font_name: "Arial",
      title_complex_script_font_name: "Times New Roman",
    },
    footer: {
      enabled: false,
      left_text: "",
      right_text: "",
      show_page_number: true,
      font_name: "宋体",
      western_font_name: "Arial",
      complex_script_font_name: "Times New Roman",
      alignment: "center",
    },
  },
  preview_samples: { heading1_text: "产品特性", normal_text: "正文效果示意文本。" },
  field_schema: {
    schema_version: "template-layout-editor/v1",
    meta: {
      schema_version: { type: "text", label: "schema_version", readonly: true },
      template_name: { type: "text", label: "配置名称", readonly: true },
      output_filename: { type: "text", label: "输出文件名", readonly: true },
    },
    categories: [
      { key: "page", label: "页面", order: 0, groups: ["page_setup"] },
      { key: "cover", label: "首页", order: 1, groups: ["part_number", "category"] },
      { key: "heading", label: "标题", order: 2, groups: ["heading1", "heading2", "heading3"] },
      { key: "toc", label: "目录", order: 3, groups: ["toc_title", "toc_level1", "toc_level2", "toc_level3"] },
      { key: "body", label: "正文", order: 4, groups: ["normal"] },
      { key: "table", label: "表格与图注", order: 5, groups: ["table_content", "table_style", "table_note", "caption", "long_table_caption"] },
      { key: "header_footer", label: "页眉页脚", order: 6, groups: ["header", "footer"] },
    ],
    group_meta: Object.fromEntries(
      [
        ["page_setup", "页面设置"], ["part_number", "首页型号行"], ["category", "首页品类行"],
        ["heading1", "一级标题"], ["heading2", "二级标题"], ["heading3", "三级标题"],
        ["toc_title", "目录标题"], ["toc_level1", "目录一级项"], ["toc_level2", "目录二级项"], ["toc_level3", "目录三级项"],
        ["normal", "正文"], ["table_content", "表格正文"], ["table_style", "表格样式"],
        ["table_note", "表格注释"], ["caption", "图注 / 表题"], ["long_table_caption", "续表标题"],
        ["header", "页眉"], ["footer", "页脚"],
      ].map(([key, label], order) => [key, { label, category: "", description: `维护${label}样式。`, order }]),
    ),
    groups: {
      page_setup: { top_margin: { type: "number", label: "上边距", unit: "cm" } },
      part_number: { font_size: { type: "number", label: "字号", unit: "pt" } },
      category: { font_size: { type: "number", label: "字号", unit: "pt" } },
      heading1: {
        font_name: { type: "text", label: "中文字体" },
        western_font_name: { type: "text", label: "西文字体" },
        complex_script_font_name: { type: "text", label: "复杂文种字体" },
        font_size: { type: "number", label: "字号", unit: "pt" },
        bold: { type: "boolean", label: "加粗" },
        color: { type: "color", label: "颜色" },
        alignment: { type: "alignment", label: "对齐方式" },
      },
      heading2: { font_size: { type: "number", label: "字号", unit: "pt" } },
      heading3: { font_size: { type: "number", label: "字号", unit: "pt" } },
      toc_title: { font_size: { type: "number", label: "字号", unit: "pt" } },
      toc_level1: { font_size: { type: "number", label: "字号", unit: "pt" } },
      toc_level2: { font_size: { type: "number", label: "字号", unit: "pt" } },
      toc_level3: { font_size: { type: "number", label: "字号", unit: "pt" } },
      normal: {
        font_size: { type: "number", label: "字号", unit: "pt" },
        color: { type: "color", label: "颜色" },
        alignment: { type: "alignment", label: "对齐方式" },
      },
      table_content: {
        font_size: { type: "number", label: "字号", unit: "pt" },
        min_font_size: { type: "number", label: "最小字号", unit: "pt", optional: true, min: 1, max: 200, step: 0.5 },
      },
      table_style: {
        style_name: { type: "text", label: "表格样式" },
        header_fill: { type: "color", label: "表头底色" },
        border_color: { type: "color", label: "边框颜色" },
      },
      table_note: {
        font_size: { type: "number", label: "字号", unit: "pt" },
        italic: { type: "boolean", label: "斜体" },
      },
      caption: { font_size: { type: "number", label: "字号", unit: "pt" } },
      long_table_caption: { font_size: { type: "number", label: "字号", unit: "pt" } },
      header: {
        enabled: { type: "boolean", label: "启用页眉覆盖" },
        logo_path: { type: "text", label: "Logo 路径", readonly: true },
        title_text: { type: "text", label: "页眉标题" },
        title_font_name: { type: "text", label: "页眉中文字体" },
        title_western_font_name: { type: "text", label: "页眉西文字体" },
        title_complex_script_font_name: { type: "text", label: "页眉复杂文种字体" },
      },
      footer: {
        enabled: { type: "boolean", label: "启用页脚覆盖" },
        left_text: { type: "text", label: "页脚左侧文字" },
        right_text: { type: "text", label: "页脚右侧文字" },
        show_page_number: { type: "boolean", label: "显示页码" },
        font_name: { type: "text", label: "页脚中文字体" },
        western_font_name: { type: "text", label: "页脚西文字体" },
        complex_script_font_name: { type: "text", label: "页脚复杂文种字体" },
        alignment: { type: "alignment", label: "页脚对齐" },
      },
    },
  },
};

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

const auditEventList = {
  items: [
    {
      audit_id: "audit_smoke_delete_denied",
      actor_id: "user_operator",
      actor_role: "operator",
      action: "document_job.delete_denied",
      target_type: "document_job",
      target_id: "docjob_smoke_001",
      reason: "只有 admin 可以删除文档任务。",
      details: { role: "operator", source: "core-flow-smoke" },
      trace_id: "trace_audit_smoke",
      created_at: "2026-06-11T00:05:00Z",
    },
  ],
  page: 1,
  page_size: 25,
  total: 1,
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
  const createdDocumentJobPayloads: DocumentJobCreatePayload[] = [];
  const layoutConfigDraftPayloads: Array<{
    base_template_version_id: string;
    expected_config_sha256: string;
    expected_active_template_version_id: string;
    changes: Record<string, unknown>;
  }> = [];
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
  await page.route(/\/api\/v1\/saved-views(?:\/.*)?(?:\?.*)?$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) });
      return;
    }
    if (route.request().method() === "DELETE") {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    if (new URL(route.request().url()).pathname.endsWith("/reorder")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) });
      return;
    }
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: route.request().method() === "POST" ? 201 : 200,
      contentType: "application/json",
      body: JSON.stringify({
        view_id: "savedview_smoke",
        tenant_id: "tenant_default",
        company_id: "company_default",
        owner_user_id: "user_operator",
        page_key: payload.page_key || "jobs",
        name: payload.name || "Smoke view",
        filters: payload.filters || {},
        sort: payload.sort || "updated_at_desc",
        is_default: Boolean(payload.is_default),
        position: 0,
        created_at: "2026-06-20T00:00:00Z",
        updated_at: "2026-06-20T00:00:00Z",
      }),
    });
  });
  await page.route(/\/api\/v1\/document-job-incidents(?:\/.*)?(?:\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() === "GET" && url.pathname === "/api/v1/document-job-incidents") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          page: 1,
          page_size: Number(url.searchParams.get("page_size") || 20),
          total: 0,
          summary: {
            total: 0,
            failed: 0,
            blocked: 0,
            stalled: 0,
            retryable: 0,
            non_retryable: 0,
            by_status: {},
            by_failure_type: {},
          },
        }),
      });
      return;
    }
    await route.fallback();
  });
  await page.route("**/api/v1/health/ready", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(healthReady) });
  });
  await page.route("**/api/v1/health/metrics", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(healthMetrics) });
  });
  await page.route("**/api/v1/audit-events**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/export")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          manifest: {
            exported_at: "2026-06-11T00:05:00Z",
            requested_by: "user_admin",
            actor_role: "admin",
            sort: "created_at_desc",
            filters: {},
            matched_count: 1,
            exported_count: 1,
            max_rows: 5000,
            truncated: false,
            columns: ["created_at", "actor_role", "actor_id", "action", "target_type", "target_id", "reason", "trace_id"],
            audit_id: "audit_export_smoke",
          },
          csv_text: "created_at,actor_role,actor_id,action,target_type,target_id,reason,trace_id\n",
        }),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(auditEventList) });
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
  await page.route("**/api/v1/files/upload-url", async (route) => {
    const file = {
      id: "file_upload_smoke",
      tenant_id: "tenant_default",
      company_id: "company_default",
      job_id: null,
      file_type: "source_pdf",
      storage_provider: "local_file",
      bucket: "local",
      object_key: "uploads/file_upload_smoke/source.pdf",
      original_filename: "smoke.pdf",
      mime_type: "application/pdf",
      size_bytes: 1024,
      checksum_sha256: null,
      etag: null,
      status: "pending",
      expires_at: "2026-06-11T00:20:00Z",
      metadata: {},
      created_by: "user_operator",
      created_at: "2026-06-11T00:00:00Z",
      updated_at: "2026-06-11T00:00:00Z",
    };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        file_id: file.id,
        upload_url: "/api/v1/files/file_upload_smoke/content",
        method: "PUT",
        headers: { "Content-Type": "application/pdf" },
        expires_at: "2026-06-11T00:20:00Z",
        object_key: file.object_key,
        max_bytes: 52_428_800,
        file,
      }),
    });
  });
  await page.route("**/api/v1/files/file_upload_smoke/content", async (route) => {
    const file = {
      id: "file_upload_smoke",
      tenant_id: "tenant_default",
      company_id: "company_default",
      job_id: null,
      file_type: "source_pdf",
      storage_provider: "local_file",
      bucket: "local",
      object_key: "uploads/file_upload_smoke/source.pdf",
      original_filename: "smoke.pdf",
      mime_type: "application/pdf",
      size_bytes: 1024,
      checksum_sha256: null,
      etag: null,
      status: "uploaded",
      expires_at: "2026-06-11T00:20:00Z",
      metadata: {},
      created_by: "user_operator",
      created_at: "2026-06-11T00:00:00Z",
      updated_at: "2026-06-11T00:00:00Z",
    };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ file }),
    });
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
        download_url: "about:blank#file_result_smoke",
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
        role: currentRole,
        resource_mode: "versioned",
        defaults: {
          template: { label: "template-default", resource_id: "template_default", version: "1" },
          term_rule_set: { label: "term-rule-default", resource_id: "term_rule_default", version: "1" },
          translation_term_set: options.en2zhAvailable === false
            ? null
            : { label: "translation-term-default", resource_id: "translation_term_default", version: "1" },
          translation_profile: options.en2zhAvailable === false
            ? null
            : { label: "translation-profile-default", resource_id: "translation_profile_default", version: "1" },
        },
        translation_defaults: {
          en2zh: {
            translation_term_set: options.en2zhAvailable === false
              ? null
              : { label: "translation-term-default", resource_id: "translation_term_default", version: "1" },
            translation_profile: options.en2zhAvailable === false
              ? null
              : { label: "translation-profile-default", resource_id: "translation_profile_default", version: "1" },
          },
          ru2zh: {
            translation_term_set: null,
            translation_profile: null,
          },
        },
        options: {
          templates: [],
          term_rule_sets: [],
          translation_term_sets: [],
          translation_profiles: [],
        },
        readiness: {
          en2zh_available: options.en2zhAvailable !== false,
          ru2zh_available: false,
          translation_modes: {
            en2zh: options.en2zhAvailable !== false,
            ru2zh: false,
          },
          p0_document_jobs_required: true,
          p0_document_jobs_ready: true,
          document_jobs_worker_backend: "external",
          document_jobs_automatic_execution_enabled: true,
          blockers: [],
          warnings: [],
        },
      }),
    });
  });
  await page.route("**/api/v1/templates/default/layout-config/versions", async (route) => {
    const payload = route.request().postDataJSON() as {
      base_template_version_id: string;
      expected_config_sha256: string;
      expected_active_template_version_id: string;
      changes: Record<string, unknown>;
    };
    layoutConfigDraftPayloads.push(payload);
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        template_id: "default",
        template_version_id: "default@2",
        version: 2,
        status: "draft",
        is_current: false,
        is_default: false,
        snapshot_hash: "sha256:draft",
        render_policy: {},
        verification_job_id: null,
        verification_note: null,
        verified_by: null,
        verified_at: null,
        publish_reason: null,
        published_by: null,
        published_at: null,
        template: templateDetail.template,
        layout_config: { ...templateDetail.layout_config, file_name: "layout_config.yaml" },
      }),
    });
  });
  await page.route(/\/api\/v1\/templates\/default\/layout-config(?:\?.*)?$/, async (route) => {
    const requestedVersion = new URL(route.request().url()).searchParams.get("version");
    const draftChanges = layoutConfigDraftPayloads.at(-1)?.changes.heading1 as { font_size?: number } | undefined;
    const tableDraftChanges = layoutConfigDraftPayloads.at(-1)?.changes.table_content as
      | { min_font_size?: number }
      | undefined;
    const response = requestedVersion === "2"
      ? {
          ...templateLayoutConfig,
          template_version_id: "default@2",
          version: 2,
          status: "draft",
          is_default: false,
          config_sha256: "sha256:draft",
          snapshot_hash: "sha256:draft",
          config: {
            ...templateLayoutConfig.config,
            heading1: { ...templateLayoutConfig.config.heading1, ...draftChanges },
            table_content: { ...templateLayoutConfig.config.table_content, ...tableDraftChanges },
          },
        }
      : templateLayoutConfig;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(response) });
  });
  await page.route("**/api/v1/templates/default/versions", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        template_id: "default",
        items: [
          {
            template_id: "default",
            template_version_id: "default@1",
            version: 1,
            status: "published",
            is_current: true,
            is_default: true,
            snapshot_hash: "sha256:published",
            render_policy: {},
            verification_job_id: "docjob_smoke_001",
            verification_note: "smoke",
            verified_by: "user_admin",
            verified_at: "2026-06-11T00:00:00Z",
            publish_reason: "baseline",
            published_by: "user_admin",
            published_at: "2026-06-11T00:00:00Z",
            template: templateDetail.template,
            layout_config: templateDetail.layout_config,
          },
        ],
      }),
    });
  });
  await page.route("**/api/v1/templates/default", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(templateDetail) });
  });
  await page.route("**/api/v1/templates", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [templateDetail] }),
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
  await page.route("**/api/v1/document-jobs/docjob_qa_002/translation-qa**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(translationQaBlockedResponse),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_qa_002", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(translationQaBlockedJob),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_created_001/events", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: "docjob_created_001",
        items: [],
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_created_001/files", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: "docjob_created_001",
        files: [],
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_created_001/callback-messages/summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: "docjob_created_001",
        status_counts: {},
        replayable_count: 0,
        oldest_replayable_age_seconds: 0,
        recent_problem_messages: [],
      }),
    });
  });
  await page.route("**/api/v1/document-jobs/docjob_created_001", async (route) => {
    const payload = createdDocumentJobPayloads[createdDocumentJobPayloads.length - 1];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...documentJob,
        id: "docjob_created_001",
        source_file_id: payload?.source_file_id || "file_upload_smoke",
        mode: payload?.mode || "direct_pdf_to_word",
        document_language: payload?.document_language || "auto",
        status: "queued",
        stage: "uploaded",
        progress: 0,
        result_file_id: null,
        started_at: null,
        completed_at: null,
        request_snapshot: {
          source_file: { original_filename: "smoke.pdf" },
        },
        available_actions: activeActionStates,
        created_at: "2026-06-11T00:08:00Z",
        updated_at: "2026-06-11T00:08:00Z",
      }),
    });
  });
  await page.route("**/api/v1/document-jobs**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname !== "/api/v1/document-jobs") {
      await route.fallback();
      return;
    }
    if (route.request().method() === "POST") {
      const payload = route.request().postDataJSON() as DocumentJobCreatePayload;
      createdDocumentJobPayloads.push(payload);
      const job = {
        ...documentJob,
        id: "docjob_created_001",
        source_file_id: payload.source_file_id || "file_upload_smoke",
        mode: payload.mode || "direct_pdf_to_word",
        document_language: payload.document_language || "auto",
        status: "queued",
        stage: "uploaded",
        progress: 0,
        result_file_id: null,
        started_at: null,
        completed_at: null,
        available_actions: activeActionStates,
        created_at: "2026-06-11T00:08:00Z",
        updated_at: "2026-06-11T00:08:00Z",
      };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: job.id,
          status: job.status,
          stage: job.stage,
          progress: job.progress,
          job,
        }),
      });
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
      if (qaStatus === "approved") {
        items = [];
      } else if (qaStatus === "blocked") {
        items = [translationQaBlockedJob];
      } else if (qaStatus === "all") {
        items = [translationQaJob, translationQaBlockedJob];
      } else {
        items = [translationQaJob];
      }
      filteredSummary = items.length ? { succeeded: items.length } : {};
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
          ? { unreviewed: 1, approved: 0, needs_fix: 0, blocked: 1 }
          : { unreviewed: 0, approved: 0, needs_fix: 0, blocked: 0 },
      }),
    });
  });

  return {
    createdDocumentJobPayloads: () => createdDocumentJobPayloads,
    translationQaPatchCount: () => translationQaPatchCount,
    layoutConfigDraftPayloads: () => layoutConfigDraftPayloads,
  };
}

async function loginAsOperator(page: Page): Promise<void> {
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);
}

async function settleWorkbenchScreenshot(page: Page): Promise<void> {
  await expect(page.locator(".el-loading-mask")).toHaveCount(0);
  await page.waitForTimeout(350);
}

async function expectLocatorInViewport(page: Page, selector: string): Promise<void> {
  const box = await page.locator(selector).boundingBox();
  const viewport = page.viewportSize();
  expect(box, `${selector} should have a rendered bounding box`).not.toBeNull();
  expect(viewport, "viewport should be available").not.toBeNull();
  if (!box || !viewport) {
    return;
  }
  expect(box.y, `${selector} should not start above the viewport`).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height, `${selector} should fit inside the viewport`).toBeLessThanOrEqual(viewport.height + 1);
}

test("operations redesign renders verified desktop, tablet, and mobile screenshots", async ({ browser }, testInfo) => {
  test.setTimeout(60_000);
  for (const viewport of WORKBENCH_VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
    });
    const page = await context.newPage();
    await mockApi(page);
    if (viewport.name === "laptop") {
      await page.addInitScript(() => {
        window.localStorage.setItem("md2word.theme.mode", "dark");
      });
    }

    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "md2word 内部工作台" })).toBeVisible();
    if (viewport.name === "laptop") {
      await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    }
    await expectNoPageHorizontalOverflow(page);
    await settleWorkbenchScreenshot(page);
    await page.screenshot({ path: testInfo.outputPath(`ops-login-${viewport.name}.png`) });

    await loginAsOperator(page);
    await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=1");
    await expect(page.getByRole("heading", { name: "任务列表" })).toBeVisible();
    await expect(page.locator(".work-queue-strip").getByRole("button", { name: /失败任务/ })).toBeVisible();
    await expect(page.getByText("smoke.pdf")).toBeVisible();
    await expectNoPageHorizontalOverflow(page);
    await activateSkipLink(page);
    await settleWorkbenchScreenshot(page);
    await page.screenshot({ path: testInfo.outputPath(`ops-jobs-${viewport.name}.png`) });

    await page.goto("/jobs/docjob_smoke_001");
    await expect(page.getByRole("heading", { name: "任务详情" })).toBeVisible();
    await page.getByRole("tab", { name: "诊断" }).click();
    await expect(page.getByRole("heading", { name: "诊断摘要" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "下一步建议" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "关键证据" }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "事件预览" })).toBeVisible();
    await expectNoPageHorizontalOverflow(page);
    await settleWorkbenchScreenshot(page);
    await page.screenshot({ path: testInfo.outputPath(`ops-job-detail-diagnostics-${viewport.name}.png`) });

    await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=1");
    await expect(page.getByRole("heading", { name: "任务列表" })).toBeVisible();

    if (viewport.width > 980) {
      await expect(page.locator(".app-sidebar-shell")).toBeVisible();
      await expect(page.locator(".app-sidebar-shell").getByText("运营工作台")).toBeVisible();
      await expect(page.locator(".app-sidebar-shell").getByRole("link", { name: "任务工作台" })).toHaveAttribute("aria-current", "page");
      await page.screenshot({ path: testInfo.outputPath(`app-shell-expanded-${viewport.name}.png`) });

      await page.getByRole("button", { name: "收起侧边栏" }).click();
      await expect.poll(() => page.evaluate(() => window.localStorage.getItem("md2word.sidebar.collapsed"))).toBe("true");
      await page.reload();
      await expect(page.getByRole("button", { name: "展开侧边栏" })).toBeVisible();
      await expect(page.locator(".app-sidebar-shell .sidebar-link-label")).toHaveCount(0);
      await expectNoPageHorizontalOverflow(page);
      await settleWorkbenchScreenshot(page);
      await page.screenshot({ path: testInfo.outputPath(`app-shell-collapsed-${viewport.name}.png`) });
    } else {
      await expect(page.locator(".app-sidebar-shell")).toBeHidden();
      await page.getByRole("button", { name: "打开导航" }).click();
      await expect(page.locator(".app-mobile-drawer")).toBeVisible();
      await expect(page.locator(".app-mobile-drawer").getByText("运营工作台")).toBeVisible();
      await expect(page.locator(".app-mobile-drawer").getByRole("link", { name: "任务工作台" })).toBeVisible();
      await expectNoPageHorizontalOverflow(page);
      await settleWorkbenchScreenshot(page);
      await page.screenshot({ path: testInfo.outputPath(`app-shell-drawer-${viewport.name}.png`) });
      await page.keyboard.press("Escape");
      await expect(page.locator(".app-mobile-drawer")).toBeHidden();
      await expect(page.getByRole("button", { name: "打开导航" })).toBeFocused();
    }

    await page.locator(".jobs-table-card .el-table__body-wrapper .el-checkbox").first().click();
    await expect(page.getByLabel("批量操作")).toBeVisible();
    await expect(page.getByText("已选 1 个任务")).toBeVisible();
    await expectNoPageHorizontalOverflow(page);
    await expectLocatorInViewport(page, ".bulk-action-bar");
    await settleWorkbenchScreenshot(page);
    await page.screenshot({ path: testInfo.outputPath(`ops-jobs-bulk-${viewport.name}.png`) });

    await page.goto("/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=1");
    await expect(page.getByRole("heading", { name: "翻译 QA 队列" })).toBeVisible();
    await expect(page.getByText("复核收件箱")).toBeVisible();
    await expect(page.getByText("处理面板")).toBeVisible();
    await expect(page.getByText("qa-smoke.pdf")).toBeVisible();
    await expectNoPageHorizontalOverflow(page);
    await settleWorkbenchScreenshot(page);
    const qaLayoutHeights = await page.evaluate(() => ({
      heading: document.querySelector(".translation-qa-queue-page .page-heading")?.getBoundingClientRect().height ?? 0,
      inboxItem: document.querySelector(".translation-qa-queue-page .qa-inbox-item")?.getBoundingClientRect().height ?? 0,
    }));
    expect(qaLayoutHeights.heading).toBeLessThanOrEqual(viewport.width < 600 ? 240 : 140);
    expect(qaLayoutHeights.inboxItem).toBeLessThanOrEqual(96);
    await page.screenshot({ path: testInfo.outputPath(`ops-qa-${viewport.name}.png`) });

    await page.goto("/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=1&qa_job_id=docjob_qa_001");
    await expect(page.locator(".translation-qa-review-drawer")).toBeVisible();
    await expect(page.getByRole("heading", { name: "docjob_qa_001" })).toBeVisible();
    const qaReviewPanel = page.getByLabel("翻译 QA 复核面板");
    await expect(qaReviewPanel.getByText("qa-smoke.pdf")).toBeVisible();
    await expect(qaReviewPanel.getByText("Hello world.")).toBeVisible();
    await expectNoPageHorizontalOverflow(page);
    const drawerBox = await page.locator(".translation-qa-review-drawer").boundingBox();
    expect(drawerBox?.width || 0).toBeLessThanOrEqual(viewport.width + 1);

    if (viewport.width < 600) {
      const qaScrollRoot = page.locator(".translation-qa-review-panel");
      const mobileScrollContract = await qaScrollRoot.evaluate((element) => {
        const body = element.querySelector<HTMLElement>(".qa-review-body");
        return {
          rootOverflowY: getComputedStyle(element).overflowY,
          bodyOverflowY: body ? getComputedStyle(body).overflowY : "",
          rootOwnsOverflow: element.scrollHeight > element.clientHeight,
        };
      });
      expect(mobileScrollContract).toEqual({
        rootOverflowY: "auto",
        bodyOverflowY: "visible",
        rootOwnsOverflow: true,
      });
      await expect(qaReviewPanel.getByLabel("快捷键提示")).toBeHidden();

      await qaScrollRoot.evaluate((element) => {
        element.scrollTop = element.scrollHeight;
      });
      const actionBar = qaReviewPanel.locator(".footer-command-row");
      const noteBox = await qaReviewPanel.getByLabel("QA 备注").boundingBox();
      const actionBarBox = await actionBar.boundingBox();
      expect(noteBox, "QA 备注应能滚动到操作栏上方").not.toBeNull();
      expect(actionBarBox, "移动端操作栏应保持可见").not.toBeNull();
      if (noteBox && actionBarBox) {
        expect(noteBox.y + noteBox.height).toBeLessThanOrEqual(actionBarBox.y + 1);
        expect(actionBarBox.y).toBeGreaterThanOrEqual(0);
        expect(actionBarBox.y + actionBarBox.height).toBeLessThanOrEqual(viewport.height + 1);
      }
      for (const actionName of ["关闭", "仅保存", "保存并下一条"]) {
        await expect(qaReviewPanel.getByRole("button", { name: actionName, exact: true })).toBeVisible();
      }
    } else {
      await expect(qaReviewPanel.getByLabel("快捷键提示")).toBeVisible();
    }

    await settleWorkbenchScreenshot(page);
    await page.screenshot({ path: testInfo.outputPath(`ops-qa-drawer-${viewport.name}.png`) });

    await context.close();
  }
});

test("operator can log in and inspect the document job workbench", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();

  await expect(page).toHaveURL(/\/cockpit(\?|$)/);
  await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=1");
  await expect(page.getByRole("heading", { name: "任务列表" })).toBeVisible();
  await expect(page.getByText("smoke.pdf")).toBeVisible();
  await page.locator(".job-table .more-action").first().click();
  await expect(page.locator(".el-dropdown-menu:visible").getByText("删除", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "处理中", exact: true }).click();
  await expect(page).toHaveURL(/status_group=active/);
  await expect(page.getByText("active-smoke.pdf")).toBeVisible();
  await expect(page.getByRole("link", { name: "smoke.pdf", exact: true })).toHaveCount(0);

  await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=1");
  await page.getByRole("link", { name: "docjob_smoke_001" }).click();
  await expect(page).toHaveURL(/\/jobs\/docjob_smoke_001$/);
  await expect(page.getByRole("heading", { name: "任务详情" })).toBeVisible();
  await expect(page.getByText("结果文件 ID")).toBeVisible();
  await expect(page.getByRole("button", { name: "下载" })).toBeEnabled();
  await expect(page.locator(".job-actions").getByRole("button", { name: "删除" })).toHaveCount(0);
  await page.getByRole("button", { name: "下载" }).click();
  await expect(page.getByText("下载链接已生成")).toBeVisible();
});

test("operator can inspect source-page review warnings and still download Word", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await mockApi(page);
  await page.route("**/api/v1/document-jobs/docjob_smoke_001/files", async (route) => {
    await route.fulfill({ json: {
      job_id: documentJob.id,
      files: [{
        id: documentJob.result_file_id, file_type: "generated_word", original_filename: "review.docx",
        status: "uploaded", size_bytes: 1024, created_at: documentJob.created_at,
        quality_evidence: { review_issues: [{
          code: "caption_subject_unresolved", source_page: 21, block_id: "block_0236",
          message: "题注归属未确定，已按源解析结果保留，请核对图表与题注位置。",
        }] },
      }],
    } });
  });
  await page.goto("/login");
  await loginAsOperator(page);
  await page.goto("/jobs/docjob_smoke_001");
  await expect(page.getByRole("heading", { name: "任务详情" })).toBeVisible();
  await expect(page.getByText("任务已完成，部分内容需人工复核")).toBeVisible();
  await page.getByRole("tab", { name: "诊断", exact: true }).click();
  const review = page.locator('[aria-label="转换复核位置"]');
  await expect(review).toContainText("源 PDF 第 21 页");
  await expect(review).toContainText("Word 重新排版后的页码可能不同");
  await expect(page.getByText("Word 已生成，1 处内容需要复核")).toBeVisible();
  for (const width of [1440, 375]) {
    await page.setViewportSize({ width, height: 960 });
    await review.scrollIntoViewIfNeeded();
    await expectNoPageHorizontalOverflow(page);
    await review.screenshot({ path: `/tmp/md2word-review-warning-${width}.png` });
  }
  await page.getByRole("button", { name: "下载", exact: true }).click();
  await expect(page.getByText("下载链接已生成")).toBeVisible();
  expect(errors).toEqual([]);
});

test("operator sees list action conflicts after the refresh completes", async ({ page }) => {
  await mockApi(page, { downloadConflict: true });

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);
  await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=1");

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
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

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

test("operator can create an English to Chinese document job from the mode selector", async ({ page }) => {
  const controls = await mockApi(page, { en2zhAvailable: true });

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

  await page.goto("/jobs/new");
  await expect(page.getByRole("heading", { name: "创建转换任务" })).toBeVisible();
  await expect(page.getByText("任务模式")).toBeVisible();
  await expect(page.getByRole("radio", { name: "英译中" })).toBeEnabled();
  await page.locator(".mode-row .el-radio-button").filter({ hasText: "英译中" }).click();
  await page.locator("input[type='file']").setInputFiles({
    name: "smoke.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n%%EOF\n"),
  });
  await page.getByRole("button", { name: "创建任务" }).click();

  await expect.poll(() => controls.createdDocumentJobPayloads().length).toBe(1);
  expect(controls.createdDocumentJobPayloads()[0]).toMatchObject({
    source_file_id: "file_upload_smoke",
    translation_mode: "en2zh",
    document_language: "en",
  });
});

test("operator sees unavailable English to Chinese mode disabled while direct mode remains creatable", async ({ page }) => {
  const controls = await mockApi(page, { en2zhAvailable: false });

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

  await page.goto("/jobs/new");
  await expect(page.getByRole("heading", { name: "创建转换任务" })).toBeVisible();
  await expect(page.getByText(/英译中\s*需要默认翻译术语集和翻译配置发布后才能选择。/)).toBeVisible();
  await expect(page.getByRole("radio", { name: "英译中" })).toBeDisabled();
  await page.locator("input[type='file']").setInputFiles({
    name: "smoke.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n%%EOF\n"),
  });
  await page.getByRole("button", { name: "创建任务" }).click();

  await expect.poll(() => controls.createdDocumentJobPayloads().length).toBe(1);
  expect(controls.createdDocumentJobPayloads()[0]).toMatchObject({
    source_file_id: "file_upload_smoke",
    translation_mode: "direct",
    document_language: "auto",
  });
});

test("operator sees an explicit forbidden state for admin-only routes", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

  await page.goto("/settings");
  await expect(page).toHaveURL(/\/forbidden/);
  await expect(page.getByRole("heading", { name: "当前账号没有访问权限" })).toBeVisible();
  await expect(page.getByText("settings:read")).toBeVisible();

  await page.goto("/settings/templates/default");
  await expect(page).toHaveURL(/\/forbidden/);
  await expect(page.getByText("admin")).toBeVisible();

  await page.goto("/settings/word-page-styles/default");
  await expect(page).toHaveURL(/\/forbidden/);
  await expect(page.getByText("admin")).toBeVisible();
});

test("admin can edit Word page styles and save a draft version", async ({ page }) => {
  const controls = await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("admin");
  await page.getByPlaceholder("请输入密码").fill("admin-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

  await page.goto("/settings/templates");
  await expect(page.getByRole("heading", { name: "Word 模板文档", level: 1 })).toBeVisible();
  await page.getByRole("link", { name: "default" }).click();
  await expect(page).toHaveURL(/\/settings\/templates\/default$/);
  await expect(page.getByRole("heading", { name: "Word 模板文档", level: 1 })).toBeVisible();
  await expect(page.getByText("模板文档负责")).toBeVisible();
  await expect(page.getByText("页面设置")).not.toBeVisible();

  await page.goto("/settings/word-page-styles");
  await expect(page.getByRole("heading", { name: "Word 页面样式配置", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "配置样式" }).click();
  await expect(page).toHaveURL(/\/settings\/word-page-styles\/default$/);
  await expect(page.getByText("公司 Logo、默认页眉内容和 DOCX 文件由 Word 模板文档维护")).toBeVisible();
  await expect(page.getByRole("combobox", { name: "选择模板版本" })).toBeVisible();
  await expect(page.getByText("当前默认", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Word 页面样式编辑器").getByText("Logo 路径")).not.toBeVisible();
  await expect(page.getByText("效果示意，最终以该 draft 的真实 Word 验证任务为准。")).toBeVisible();

  await page.getByLabel("Word 页面样式编辑器").getByRole("button", { name: /^表格与图注\s/ }).click();
  await page.getByRole("tab", { name: /表格正文/ }).click();
  const minimumTableFontSize = page.locator(".layout-section .el-form-item", { hasText: "最小字号" }).locator("input").first();
  await expect(minimumTableFontSize).toBeVisible();
  await minimumTableFontSize.fill("7");

  await page.getByLabel("Word 页面样式编辑器").getByRole("button", { name: /^页眉页脚\s/ }).click();
  await page.getByRole("tab", { name: /页脚/ }).click();
  await expect(page.getByLabel("Word 页面样式编辑器").getByText("页脚左侧文字", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Word 页面样式编辑器").getByText("页脚右侧文字", { exact: true })).toBeVisible();

  await page.getByLabel("Word 页面样式编辑器").getByRole("button", { name: /^标题\s/ }).click();
  await page.getByRole("tab", { name: /一级标题/ }).click();
  await expect(page.getByLabel("Word 页面样式编辑器").getByText("中文字体", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Word 页面样式编辑器").getByText("西文字体", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Word 页面样式编辑器").getByText("复杂文种字体", { exact: true })).toBeVisible();
  const headingFontSize = page.locator(".layout-section .el-form-item", { hasText: "字号" }).locator("input").first();
  await headingFontSize.fill("14");
  await expect(page.getByLabel("配置变更摘要").getByText("2", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "保存为草稿版本" }).click();

  await expect.poll(() => controls.layoutConfigDraftPayloads().length).toBe(1);
  expect(controls.layoutConfigDraftPayloads()[0]).toMatchObject({
    base_template_version_id: "default@1",
    expected_config_sha256: "sha256:layout",
    expected_active_template_version_id: "default@1",
  });
  expect((controls.layoutConfigDraftPayloads()[0].changes.heading1 as { font_size: number }).font_size).toBe(14);
  expect((controls.layoutConfigDraftPayloads()[0].changes.table_content as { min_font_size: number }).min_font_size).toBe(7);
  expect(controls.layoutConfigDraftPayloads()[0].changes).not.toHaveProperty("sample_content");
  expect(controls.layoutConfigDraftPayloads()[0].changes).not.toHaveProperty("template_name");
  await expect(page.getByText("已生成页面样式 draft version 2")).toBeVisible();
  await expect(page.getByRole("button", { name: "创建验证任务" })).toBeVisible();
  await page.getByRole("button", { name: "发布", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "发布模板版本" })).toBeVisible();
  await expect(page.getByText("只有状态为 succeeded 且绑定当前版本的验证任务才能发布。")).toBeVisible();
  await expect(page).toHaveURL(/\/settings\/word-page-styles\/default$/);
  await page.getByRole("dialog", { name: "发布模板版本" }).getByRole("button", { name: "取消" }).click();
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.getByLabel("模板版本 2 操作").getByRole("button", { name: "发布", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
});

test("operator can inspect the translation QA queue with backend all-status summary", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

  await page.goto("/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=1");
  await expect(page.getByRole("heading", { name: "翻译 QA 队列" })).toBeVisible();
  await expect(page.getByText("qa-smoke.pdf")).toBeVisible();
  await expect(page.getByText("未复核").first()).toBeVisible();
  await expect(page.getByText("复核收件箱")).toBeVisible();
  await expect(page.getByText("处理面板")).toBeVisible();
});

test("operator can use the translation QA drawer review flow", async ({ page }) => {
  const controls = await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

  await page.goto("/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=1&qa_job_id=docjob_qa_001");
  await expect(page.locator(".translation-qa-review-drawer")).toBeVisible();
  await expect(page.getByRole("heading", { name: "docjob_qa_001" })).toBeVisible();
  const qaReviewPanel = page.getByLabel("翻译 QA 复核面板");
  await expect(qaReviewPanel.getByText("qa-smoke.pdf")).toBeVisible();
  await expect(page.getByText("1 / 2")).toBeVisible();

  await page.getByLabel("QA 备注").fill("typing");
  await page.keyboard.press("j");
  await expect(page.getByText("1 / 2")).toBeVisible();
  await page.locator(".qa-review-header").click();
  await page.keyboard.press("j");
  await expect(page.getByText("2 / 2")).toBeVisible();
  await expect(qaReviewPanel.getByText("Esc")).toBeVisible();
  await expect(qaReviewPanel.getByText("Cmd/Ctrl")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.locator(".translation-qa-review-drawer")).toBeHidden();
  await expect(page).not.toHaveURL(/qa_job_id=/);

  await page.getByRole("button", { name: "复核", exact: true }).first().click();
  await expect(page).toHaveURL(/qa_job_id=docjob_qa_001/);
  await expect(page.getByRole("heading", { name: "docjob_qa_001" })).toBeVisible();
  await page.getByLabel("QA 备注").fill("smoke");
  await page.getByRole("button", { name: "仅保存" }).click();
  await expect.poll(() => controls.translationQaPatchCount()).toBe(1);
  await expect(page).toHaveURL(/qa_job_id=docjob_qa_001/);
  await expect(page.getByRole("heading", { name: "docjob_qa_001" })).toBeVisible();

  await qaReviewPanel.locator(".segment-review-surface").click();
  await page.keyboard.press("Control+Enter");
  await expect.poll(() => controls.translationQaPatchCount()).toBe(2);
  await expect(page).toHaveURL(/qa_job_id=docjob_qa_002/);
  await expect(page.getByRole("heading", { name: "docjob_qa_002" })).toBeVisible();
  await expect(qaReviewPanel.getByText("qa-blocked-smoke.pdf")).toBeVisible();
});

test("operator can use the shared translation QA panel on the detail page", async ({ page }) => {
  const controls = await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

  await page.goto("/jobs/docjob_qa_001/translation-qa");
  await expect(page.getByRole("heading", { name: "翻译 QA", level: 1 })).toBeVisible();
  const qaReviewPanel = page.getByLabel("翻译 QA 复核面板");
  await expect(qaReviewPanel.getByText("qa-smoke.pdf")).toBeVisible();
  await expect(qaReviewPanel.getByText("Hello world.")).toBeVisible();
  await page.getByLabel("QA 备注").fill("detail shared panel");
  await page.getByRole("button", { name: "保存复核" }).click();
  await expect.poll(() => controls.translationQaPatchCount()).toBe(1);
  await expect(page.getByText("翻译 QA 复核已保存。")).toBeVisible();
});

test("operator sees unavailable translation QA in the queue drawer as readonly", async ({ page }) => {
  const controls = await mockApi(page, { translationQaUnavailable: true });

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

  await page.goto("/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=1&qa_job_id=docjob_qa_001");
  await expect(page.locator(".translation-qa-review-drawer")).toBeVisible();
  await expect(page.locator(".qa-review-header-actions").getByText("只读诊断")).toBeVisible();
  await expect(page.getByRole("alert").getByText("任务缺少 DocumentIR 证据文件，无法展示最终文本片段。")).toBeVisible();
  await expect(page.getByRole("button", { name: "仅保存" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "保存并下一条" })).toBeDisabled();
  expect(controls.translationQaPatchCount()).toBe(0);
});

test("operator sees unavailable translation QA as readonly and cannot submit review", async ({ page }) => {
  const controls = await mockApi(page, { translationQaUnavailable: true });

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("operator");
  await page.getByPlaceholder("请输入密码").fill("operator-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

  await page.goto("/jobs/docjob_qa_001/translation-qa");
  await expect(page.getByRole("heading", { name: "翻译 QA", level: 1 })).toBeVisible();
  await expect(page.getByRole("alert").getByText("任务缺少 DocumentIR 证据文件，无法展示最终文本片段。")).toBeVisible();
  await expect(page.getByRole("button", { name: "保存复核" })).toBeDisabled();
  expect(controls.translationQaPatchCount()).toBe(0);
});

test("admin can inspect status, audit, ops gates, and file retention workspaces", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名").fill("admin");
  await page.getByPlaceholder("请输入密码").fill("admin-pass");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page).toHaveURL(/\/cockpit(\?|$)/);

  await page.goto("/system-status");
  await expect(page.getByRole("heading", { name: "系统状态", level: 1 })).toBeVisible();
  await expect(page.getByText("md2word").first()).toBeVisible();
  await expect(page.getByLabel("任务和资源状态").getByRole("link", { name: "运维看板" })).toBeVisible();

  await page.goto("/system-status/audit-events");
  await expect(page.getByRole("heading", { name: "审计日志", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "事件列表" })).toBeVisible();
  await expect(page.getByText("document_job.delete_denied")).toBeVisible();

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
