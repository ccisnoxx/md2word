// File: frontend/src/utils/displayText.ts
// Purpose: Centralize Chinese display text for backend enums, codes, and diagnostic fields.

export function unknownText(value: string | null | undefined, noun = "值"): string {
  const raw = String(value || "").trim();
  return raw ? `未知${noun}（${raw}）` : `未知${noun}`;
}

export function missingText(): string {
  return "未上报";
}

export function booleanText(value: boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return missingText();
  }
  return value ? "是" : "否";
}

export function configWorkbenchStatusText(status: string): string {
  const labels: Record<string, string> = {
    ready: "就绪",
    warning: "有告警",
    blocked: "已阻断",
    unavailable: "未启用",
  };
  return labels[status] || unknownText(status, "配置状态");
}

export function configWorkbenchSeverityText(severity: string): string {
  const labels: Record<string, string> = {
    info: "提示",
    warning: "告警",
    critical: "阻断",
  };
  return labels[severity] || unknownText(severity, "严重级别");
}

export function configWorkbenchDetailStatusText(status: string): string {
  const labels: Record<string, string> = {
    complete: "已完成检查",
    deferred: "深度检查待加载",
    failed: "检查失败",
  };
  return labels[status] || unknownText(status, "检查状态");
}

export function proposalIntentText(intent: string): string {
  const labels: Record<string, string> = {
    create: "新增",
    update: "编辑",
    disable: "禁用",
  };
  return labels[intent] || unknownText(intent, "建议类型");
}

export function proposalStatusText(status: string): string {
  const labels: Record<string, string> = {
    pending_review: "待审核",
    pending: "待审核",
    approved: "已通过",
    rejected: "已拒绝",
    published: "已发布",
  };
  return labels[status] || unknownText(status, "审核状态");
}

export function translationProposalActionText(action: string | null | undefined): string {
  const raw = String(action || "").trim();
  const labels: Record<string, string> = {
    add: "新增",
    update: "编辑",
    delete: "删除",
  };
  return labels[raw] || unknownText(raw, "动作");
}

function readinessCodeParts(code: string): { baseCode: string; languagePair: string | null } {
  const [baseCode, languagePair] = String(code || "").trim().split(":", 2);
  return { baseCode, languagePair: languagePair || null };
}

function languagePairText(languagePair: string): string {
  const labels: Record<string, string> = {
    en2zh: "英译中",
    ru2zh: "俄译中",
  };
  return labels[languagePair] || languagePair;
}

export function readinessCodeText(code: string): string {
  const { baseCode, languagePair } = readinessCodeParts(code);
  const labels: Record<string, string> = {
    ai_provider_config_invalid: "AI provider 配置文件不可读取",
    auth_internal_users_source_missing: "内部账号来源未配置",
    auth_jwt_secret_key_missing: "认证签名密钥未配置",
    data_dir_not_writable: "数据目录不可写",
    default_template_missing: "默认模板文件缺失",
    default_translation_unavailable: "默认翻译模式依赖不可用",
    document_jobs_celery_broker_url_missing: "文档任务 Celery broker 未配置",
    document_jobs_celery_queue_missing: "文档任务 Celery 队列未配置",
    document_job_callback_failed_messages_present: "存在失败的文档任务 callback message",
    document_job_callback_oldest_replayable_stale: "存在长时间未处理的文档任务 callback message",
    document_job_callback_replayable_messages_present: "存在可重放的文档任务 callback message",
    document_jobs_metadata_store_not_mysql: "生产门禁下文档任务元数据存储必须使用 MySQL",
    document_jobs_stale_running_present: "存在长时间未更新的文档任务",
    document_jobs_timed_out_present: "存在已超时的文档任务",
    document_jobs_worker_backend_disabled: "文档任务执行器被禁用",
    document_jobs_worker_backend_eager_in_production: "生产门禁下仍使用 eager 文档任务执行器",
    health_service_unavailable: "健康检查服务不可用",
    layout_config_missing: "版式配置文件缺失",
    mineru_api_token_missing: "MinerU API token 未配置",
    mineru_callback_url_missing: "MinerU callback URL 未配置",
    mineru_uid_missing: "MinerU UID 未配置",
    p0_document_jobs_not_ready: "P0 文档任务执行链路未就绪",
    stage_spool_dir_missing: "阶段消息目录缺失",
    stage_spool_failed_messages_present: "存在失败的阶段消息",
    stage_spool_replayable_messages_present: "存在可继续处理的阶段消息",
    stage_spool_stale_running_messages_present: "存在过期运行中的阶段消息",
    subscript_config_missing: "下标配置文件缺失",
    tmp_dir_missing: "临时目录缺失",
    translation_profile_default_missing: "默认翻译配置未发布",
    translation_profile_default_unavailable: "默认翻译配置不可用",
    translation_term_set_default_missing: "默认翻译术语集未发布",
    translation_term_set_default_unavailable: "默认翻译术语集不可用",
    translation_unavailable: "翻译能力不可用",
  };
  const label = labels[baseCode];
  if (label) {
    return languagePair ? `${label}（${languagePairText(languagePair)}）` : label;
  }
  return `未识别的就绪检查项（${code}）`;
}

export function healthLabelText(key: string): string {
  const labels: Record<string, string> = {
    app_name: "应用名称",
    artifact_disk_free: "artifact 剩余空间",
    artifact_root_writable: "artifact 根目录可写",
    artifact_storage: "artifact 存储",
    configured_repository: "配置的元数据存储",
    configured_repository_backend: "配置的元数据存储",
    default_template_version: "默认模板版本",
    default_term_rule_version: "默认术语规则版本",
    default_translation_profile_version: "默认翻译配置版本",
    default_translation_term_version: "默认翻译术语版本",
    deployment_id: "部署 ID",
    deployment_started_at: "进程启动时间",
    document_jobs_auto_execution: "文档任务自动执行",
    document_job_callback_failed_messages: "callback message 失败",
    document_job_callback_ignored_messages: "callback message 已忽略",
    document_job_callback_oldest_replayable_age_seconds: "callback message 最长待处理",
    document_job_callback_pending_messages: "callback message 待处理",
    document_job_callback_processed_messages: "callback message 已处理",
    document_job_callback_replayable_messages: "可重放 callback message",
    document_job_callback_running_messages: "callback message 运行中",
    document_jobs_celery_queue: "文档任务 Celery 队列",
    document_jobs_oldest_age: "文档任务最长运行时间",
    document_jobs_running_oldest_age_seconds: "文档任务最长运行时间",
    document_jobs_running_stale_count: "长时间未更新文档任务",
    document_jobs_stale: "长时间未更新文档任务",
    document_jobs_timed_out: "已超时文档任务",
    document_jobs_timed_out_count: "已超时文档任务",
    document_jobs_worker_backend: "文档任务执行器",
    effective_repository_backend: "实际元数据存储",
    jobs_dir: "任务目录",
    jobs_dir_writable: "任务目录可写",
    metadata_store: "元数据存储",
    app_version: "应用版本",
    app_env: "运行环境",
    p0_document_jobs_ready: "P0 文档任务就绪",
    p0_document_jobs_required: "P0 文档任务门禁",
    public_deployment_mode: "公开部署模式",
    stage_dispatcher: "阶段调度器",
    stage_failed: "阶段消息失败",
    stage_message_store: "阶段消息存储",
    stage_pending: "阶段消息待处理",
    stage_replayable: "可继续处理阶段消息",
    stage_running: "阶段消息运行中",
    stage_spool_available: "阶段消息存储可用",
    stage_spool_needs_attention: "阶段消息需要关注",
    stage_spool_observation: "阶段消息观察状态",
    stage_spool_oldest_running_age_seconds: "阶段消息最长运行时间",
    stage_spool_replayable_messages: "可继续处理阶段消息",
    stage_spool_running_stale_messages: "过期运行中阶段消息",
    stale_running: "过期运行中阶段消息",
    template_versions: "模板版本数",
    term_rule_set_versions: "术语规则集版本数",
    tmp_dir_exists: "临时目录存在",
    translation_profile_versions: "翻译配置版本数",
    worker_mode: "任务工作模式",
  };
  return labels[key] || key;
}

export function commonValueText(value: string): string {
  const labels: Record<string, string> = {
    background_tasks: "后台任务",
    blocked: "已阻断",
    database: "数据库",
    degraded: "有告警",
    disabled: "已禁用",
    eager: "同步执行",
    external: "外部工作进程",
    external_worker: "外部工作进程",
    file: "文件存储",
    local_file: "本地文件",
    local_object: "本地对象存储",
    mysql: "MySQL",
    needs_attention: "需要关注",
    ok: "正常",
    ready: "就绪",
    replayable: "可继续处理",
    s3: "S3",
    single_tenant_public: "单租户公开部署",
    unknown: "未知",
    watch: "需观察",
  };
  return labels[value] || value;
}
