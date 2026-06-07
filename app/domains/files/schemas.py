# File: app/domains/files/schemas.py
# Purpose: 定义文件元数据、上传授权、文件库搜索、保留期管理、quota enforcement 和清理 API 模型。

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FileUploadUrlRequest(BaseModel):
    """创建 source_pdf 上传授权的请求，可携带 Admin-only quota override。"""

    filename: str
    mime_type: str = "application/pdf"
    size_bytes: int
    file_type: Literal["source_pdf"] = "source_pdf"
    checksum_sha256: str | None = None
    job_id: str | None = None
    quota_override_reason: str | None = None
    quota_override_confirmation: str | None = None


class DocumentFileResponse(BaseModel):
    """返回单个 document_file 的元数据，不包含文件内容。"""

    id: str
    tenant_id: str
    company_id: str
    job_id: str | None = None
    file_type: str
    storage_provider: str
    bucket: str
    object_key: str
    original_filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str | None = None
    etag: str | None = None
    status: str
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class FileLibrarySearchItemResponse(BaseModel):
    """返回文件库搜索中的安全文件摘要，不包含对象定位或 raw metadata。"""

    file_id: str
    job_id: str | None = None
    file_type: str
    storage_provider: str
    original_filename: str
    mime_type: str
    size_bytes: int
    status: str
    expires_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    expired: bool
    physical_delete_candidate: bool


class FileLibrarySearchResponse(BaseModel):
    """返回 Admin-only 文件库搜索分页结果。"""

    generated_at: datetime
    page: int
    page_size: int
    total: int
    sort: Literal[
        "created_at_desc",
        "created_at_asc",
        "updated_at_desc",
        "updated_at_asc",
        "expires_at_desc",
        "expires_at_asc",
        "size_bytes_desc",
        "size_bytes_asc",
    ]
    filters: dict[str, str] = Field(default_factory=dict)
    items: list[FileLibrarySearchItemResponse] = Field(default_factory=list)


class FileUploadUrlResponse(BaseModel):
    """返回上传授权和已登记文件元数据。"""

    file_id: str
    upload_url: str
    method: Literal["PUT"]
    headers: dict[str, str]
    expires_at: datetime
    object_key: str
    max_bytes: int
    file: DocumentFileResponse


class FileUploadResponse(BaseModel):
    """返回代理上传完成后的文件元数据。"""

    file: DocumentFileResponse


class FileRetentionCandidateResponse(BaseModel):
    """返回一条过期 document_file 候选；仅用于计划展示，不代表会被物理删除。"""

    file_id: str
    job_id: str | None = None
    file_type: str
    storage_provider: str
    bucket: str
    object_key: str
    size_bytes: int
    status: str
    expires_at: datetime
    reason: str


class FileRetentionPlanResponse(BaseModel):
    """返回 document_files 保留期 dry-run 或 metadata 标记结果。"""

    generated_at: datetime
    retention_days: int
    deletion_supported: bool = False
    action_mode: Literal["dry_run", "mark_expired"]
    totals: dict[str, int] = Field(default_factory=dict)
    candidates: list[FileRetentionCandidateResponse] = Field(default_factory=list)
    marked_file_ids: list[str] = Field(default_factory=list)


class FileRetentionDeletePreviewRequest(BaseModel):
    """请求预览 selected expired document_files 的物理删除结果。"""

    file_ids: list[str] = Field(default_factory=list)


class FileRetentionDeleteExecuteRequest(BaseModel):
    """请求执行 selected expired document_files 的物理删除。"""

    file_ids: list[str] = Field(default_factory=list)
    reason: str
    confirmation: str


class FileRetentionS3DeleteContractResponse(BaseModel):
    """返回 S3 fake deletion safety contract，不代表真实删除授权。"""

    contract_version: Literal["s3-delete-fake-v1"]
    adapter_mode: Literal["fake"]
    bucket: str
    object_key: str
    version_id: str | None = None
    target_exact: bool
    missing_target_fields: list[str] = Field(default_factory=list)
    expected_outcome: Literal["fake_skipped"]
    safety: dict[str, bool] = Field(default_factory=dict)


class FileRetentionDeleteItemResponse(BaseModel):
    """返回单个文件的物理删除预览或执行结果。"""

    file_id: str
    job_id: str | None = None
    file_type: str | None = None
    storage_provider: str | None = None
    status_before: str | None = None
    status_after: str | None = None
    object_key: str | None = None
    size_bytes: int | None = None
    outcome: Literal[
        "deletable",
        "deleted",
        "already_missing",
        "skipped_not_found",
        "skipped_not_expired_status",
        "skipped_not_expired_time",
        "skipped_already_deleted",
        "skipped_unsupported_storage",
        "skipped_missing_object_key",
        "failed",
    ]
    reason: str
    deleted: bool = False
    metadata_updated: bool = False
    s3_delete_contract: FileRetentionS3DeleteContractResponse | None = None


class FileRetentionDeleteResponse(BaseModel):
    """返回 selected expired document_files 物理删除预览或执行汇总。"""

    generated_at: datetime
    action_mode: Literal["delete_preview", "delete_execute"]
    requested_file_ids: list[str] = Field(default_factory=list)
    confirmation_phrase: str
    totals: dict[str, int] = Field(default_factory=dict)
    items: list[FileRetentionDeleteItemResponse] = Field(default_factory=list)


class FileRetentionCleanupRunPreviewRequest(BaseModel):
    """请求预览一次精确 file_ids 的 cleanup run。"""

    file_ids: list[str] = Field(default_factory=list)
    max_files: int = Field(default=50, ge=1, le=50)


class FileRetentionCleanupRunExecuteRequest(FileRetentionCleanupRunPreviewRequest):
    """请求执行一次已 preview 的 cleanup run。"""

    run_id: str | None = None
    preview_hash: str
    plan_id: str | None = None
    plan_signature: str | None = None
    reason: str
    confirmation: str


class FileRetentionCleanupSchedulerDryRunRequest(BaseModel):
    """请求手动运行 scheduler dry-run；只生成计划和 lock/history 证据。"""

    owner_id: str | None = None
    lock_ttl_seconds: int = Field(default=60, ge=1, le=900)


class FileRetentionSignedCleanupPlanResponse(BaseModel):
    """返回 cleanup run signed plan 摘要，不包含对象路径或 secret。"""

    plan_id: str
    run_id: str
    preview_hash: str
    requested_file_ids: list[str] = Field(default_factory=list)
    max_files: int
    created_at: datetime
    expires_at: datetime
    signature: str
    signature_algorithm: Literal["hmac-sha256"]
    safety: dict[str, bool] = Field(default_factory=dict)


class FileRetentionCleanupRunSafetyResponse(BaseModel):
    """声明 cleanup run 执行边界和外部副作用状态。"""

    scheduler_loop_executed: bool = False
    provider_calls_executed: bool = False
    s3_delete_executed: bool = False
    physical_delete_executed: bool = False
    physical_delete_contract_reused: bool = True
    audit_events_written: bool = False
    history_recorded: bool = False
    signed_plan_created: bool = False
    signed_plan_verified: bool = False


class FileRetentionCleanupRunResponse(BaseModel):
    """返回 cleanup run preview 或 execute 结果。"""

    run_id: str
    generated_at: datetime
    action_mode: Literal["cleanup_preview", "cleanup_execute"]
    confirmation_phrase: str
    preview_hash: str
    requested_file_ids: list[str] = Field(default_factory=list)
    max_files: int
    physical_delete: FileRetentionDeleteResponse
    cleanup_plan: FileRetentionSignedCleanupPlanResponse | None = None
    safety: FileRetentionCleanupRunSafetyResponse


class FileRetentionCleanupLockSummaryResponse(BaseModel):
    """返回手动 scheduler dry-run 持有过的 cleanup lock 摘要。"""

    lock_name: str
    owner_id: str
    fencing_token: int
    status: str
    acquired_at: datetime
    expires_at: datetime
    released_at: datetime | None = None
    released: bool


class FileRetentionCleanupSchedulerDryRunResponse(BaseModel):
    """返回手动 scheduler dry-run 的只读报告、lock 和 safety evidence。"""

    run_id: str
    generated_at: datetime
    action_mode: Literal["scheduler_dry_run"]
    readonly_report: dict[str, Any] = Field(default_factory=dict)
    lock: FileRetentionCleanupLockSummaryResponse
    safety: dict[str, bool] = Field(default_factory=dict)


class FileRetentionCleanupRunHistoryResponse(BaseModel):
    """返回 cleanup run durable history 摘要。"""

    run_id: str
    status: Literal["previewed", "executed", "failed", "dry_run"]
    action_mode: Literal["cleanup_preview", "cleanup_execute", "scheduler_dry_run"]
    preview_hash: str
    requested_file_ids: list[str] = Field(default_factory=list)
    max_files: int
    reason: str | None = None
    totals: dict[str, int] = Field(default_factory=dict)
    safety: dict[str, bool] = Field(default_factory=dict)
    cleanup_plan: FileRetentionSignedCleanupPlanResponse | None = None
    readonly_report: dict[str, Any] = Field(default_factory=dict)
    lock: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    executed_at: datetime | None = None


class FileRetentionCleanupRunHistoryListResponse(BaseModel):
    """返回 cleanup run history 分页列表。"""

    page: int
    page_size: int
    total: int
    items: list[FileRetentionCleanupRunHistoryResponse] = Field(default_factory=list)


class FileRetentionPolicyCreateRequest(BaseModel):
    """创建 draft document_files retention policy 的请求。"""

    name: str
    scope_type: Literal["global", "file_type"]
    file_type: str | None = None
    retention_days: int = Field(ge=1, le=3650)
    description: str | None = None


class FileRetentionPolicyUpdateRequest(BaseModel):
    """更新 draft document_files retention policy 的请求。"""

    name: str | None = None
    scope_type: Literal["global", "file_type"] | None = None
    file_type: str | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    description: str | None = None


class FileRetentionPolicyReasonRequest(BaseModel):
    """发布、设为默认或禁用 retention policy 的请求。"""

    reason: str


class FileRetentionPolicyImpactPreviewRequest(BaseModel):
    """请求预览 retention policy 对现有 document_files 的影响。"""

    mode: Literal["candidate_policy"] = "candidate_policy"


class EffectiveFileRetentionPolicyResponse(BaseModel):
    """返回某个 file_type 的有效 retention policy 摘要。"""

    retention_days: int
    source: Literal["published_policy", "settings_fallback"]
    policy_id: str | None = None
    scope_type: Literal["global", "file_type"] | None = None
    file_type: str | None = None
    reason: str


class FileRetentionPolicyResponse(BaseModel):
    """返回单个 document_files retention policy。"""

    policy_id: str
    name: str
    status: Literal["draft", "published", "disabled"]
    scope_type: Literal["global", "file_type"]
    file_type: str | None = None
    retention_days: int
    description: str | None = None
    is_default: bool = False
    is_effective: bool = False
    effective_reason: str | None = None
    matching_file_count: int = 0
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    published_by: str | None = None
    published_at: datetime | None = None
    disabled_by: str | None = None
    disabled_at: datetime | None = None
    reason: str | None = None


class FileRetentionPolicyListResponse(BaseModel):
    """返回 retention policies 列表和 settings fallback 摘要。"""

    generated_at: datetime
    fallback_retention_days: int
    effective: list[EffectiveFileRetentionPolicyResponse] = Field(default_factory=list)
    items: list[FileRetentionPolicyResponse] = Field(default_factory=list)


class FileRetentionPolicyImpactItemResponse(BaseModel):
    """返回单个 document_file 在候选 retention policy 下的影响。"""

    file_id: str
    job_id: str | None = None
    file_type: str
    status: str
    storage_provider: str
    current_expires_at: datetime | None = None
    projected_expires_at: datetime
    currently_expired: bool
    would_be_expired: bool
    would_change_expires_at: bool


class FileRetentionPolicyImpactResponse(BaseModel):
    """返回 retention policy impact dry-run 结果。"""

    generated_at: datetime
    policy: FileRetentionPolicyResponse
    totals: dict[str, int] = Field(default_factory=dict)
    items: list[FileRetentionPolicyImpactItemResponse] = Field(default_factory=list)


class FileStorageUsageGroupResponse(BaseModel):
    """返回一个 document_files storage usage 分组汇总。"""

    key: str
    file_count: int
    size_bytes: int
    expired_count: int
    expired_size_bytes: int
    estimated_reclaimable_count: int
    estimated_reclaimable_size_bytes: int


class FileStorageUsageResponse(BaseModel):
    """返回 document_files storage usage 和 quota readiness 只读汇总。"""

    generated_at: datetime
    artifact_storage: str
    artifact_root_writable: bool | None = None
    artifact_disk_free_bytes: int | None = None
    totals: dict[str, int] = Field(default_factory=dict)
    reclaim: dict[str, int | str] = Field(default_factory=dict)
    quota: dict[str, int | float | bool | str | None] = Field(default_factory=dict)
    by_storage_provider: list[FileStorageUsageGroupResponse] = Field(default_factory=list)
    by_file_type: list[FileStorageUsageGroupResponse] = Field(default_factory=list)
    by_status: list[FileStorageUsageGroupResponse] = Field(default_factory=list)


class FileQuotaPolicyDryRunRequest(BaseModel):
    """请求预演拟上传文件在 staged quota policy 下的结果。"""

    size_bytes: int = Field(ge=0)
    file_type: str = "source_pdf"
    filename: str | None = None


class FileQuotaPolicyConfigResponse(BaseModel):
    """返回归一化后的 staged quota policy 配置摘要。"""

    enabled: bool
    dry_run: bool
    configured: bool
    quota_bytes: int | None = None
    warning_threshold_ratio: float | None = None
    block_threshold_ratio: float | None = None
    warning_threshold_bytes: int | None = None
    block_threshold_bytes: int | None = None
    upload_max_bytes: int
    status: Literal["disabled", "not_configured", "invalid", "dry_run", "ready"]
    config_errors: list[str] = Field(default_factory=list)


class FileQuotaPolicyUsageResponse(BaseModel):
    """返回当前和 projected quota 使用量。"""

    current_used_size_bytes: int
    proposed_upload_size_bytes: int
    projected_used_size_bytes: int
    current_usage_ratio: float | None = None
    projected_usage_ratio: float | None = None


class FileQuotaPolicySafetyResponse(BaseModel):
    """声明 quota dry-run 没有执行上传、阻断、审计或外部副作用。"""

    read_only: bool = True
    upload_authorization_created: bool = False
    upload_content_written: bool = False
    upload_blocking_executed: bool = False
    metadata_mutated: bool = False
    audit_events_written: bool = False
    provider_calls_executed: bool = False
    delete_executed: bool = False
    conversion_workflow_executed: bool = False


class FileQuotaPolicyDryRunResponse(BaseModel):
    """返回 quota policy dry-run 结果，不代表真实上传授权被阻断。"""

    generated_at: datetime
    action_mode: Literal["quota_policy_dry_run"]
    file_type: str
    filename: str | None = None
    policy: FileQuotaPolicyConfigResponse
    usage: FileQuotaPolicyUsageResponse
    would_warn: bool
    would_block: bool
    reasons: list[str] = Field(default_factory=list)
    safety: FileQuotaPolicySafetyResponse


class FileQuotaPolicyOpsSafetyResponse(BaseModel):
    """声明 quota ops summary 没有执行阻断、rollback、清理或外部副作用。"""

    read_only: bool = True
    upload_authorization_created: bool = False
    upload_content_written: bool = False
    upload_blocking_executed: bool = False
    metadata_mutated: bool = False
    audit_events_written: bool = False
    provider_calls_executed: bool = False
    delete_executed: bool = False
    cleanup_executed: bool = False
    scheduler_loop_executed: bool = False
    conversion_workflow_executed: bool = False


class FileQuotaPolicyRollbackOptionResponse(BaseModel):
    """返回一个只读 rollback 开关建议，不代表后端已执行配置变更。"""

    option_id: str
    label: str
    env_var: str
    target_value: str
    current_value: str
    currently_effective: bool
    effect: str
    requires_restart: bool


class FileQuotaPolicyAuditReplayItemResponse(BaseModel):
    """返回 quota enforcement 审计事件的安全重放摘要。"""

    audit_id: str
    action: Literal["file.quota_policy_block", "file.quota_policy_override"]
    target_type: str
    target_id: str
    actor_role: str
    actor_id: str | None = None
    reason: str | None = None
    trace_id: str
    created_at: datetime
    outcome: str | None = None
    file_type: str | None = None
    filename: str | None = None
    would_block: bool | None = None
    override_applied: bool | None = None
    current_used_size_bytes: int | None = None
    proposed_upload_size_bytes: int | None = None
    projected_used_size_bytes: int | None = None
    quota_bytes: int | None = None
    policy_status: str | None = None
    reasons: list[str] = Field(default_factory=list)
    details: dict[str, Any] | None = None


class FileQuotaPolicyOpsSummaryResponse(BaseModel):
    """返回 Admin-only quota enforcement 运维摘要、rollback 和 audit replay。"""

    generated_at: datetime
    action_mode: Literal["quota_policy_ops_summary"]
    policy: FileQuotaPolicyConfigResponse
    usage: FileQuotaPolicyUsageResponse
    enforcement_ready: bool
    current_usage_would_warn: bool
    current_usage_would_block: bool
    kill_switch_enabled: bool
    reasons: list[str] = Field(default_factory=list)
    rollback_options: list[FileQuotaPolicyRollbackOptionResponse] = Field(default_factory=list)
    audit_replay: list[FileQuotaPolicyAuditReplayItemResponse] = Field(default_factory=list)
    audit_replay_total: int
    audit_replay_limit: int
    audit_replay_truncated: bool
    safety: FileQuotaPolicyOpsSafetyResponse
