# File: app/domains/files/quota_policy.py
# Purpose: Evaluate staged file upload quota policy for dry-run and guarded upload blocking.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from app.core.config import Settings
from app.domains.audit.models import AuditDetails, AuditEvent
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.models import utc_now


FileQuotaPolicyStatus = Literal["disabled", "not_configured", "invalid", "dry_run", "ready"]
FILE_QUOTA_POLICY_OVERRIDE_CONFIRMATION_PHRASE = "OVERRIDE FILE QUOTA POLICY"


@dataclass(frozen=True, slots=True)
class FileQuotaPolicyConfig:
    """保存归一化后的 quota policy 配置和配置错误。"""

    enabled: bool
    dry_run: bool
    configured: bool
    quota_bytes: int | None
    warning_threshold_ratio: float | None
    block_threshold_ratio: float | None
    warning_threshold_bytes: int | None
    block_threshold_bytes: int | None
    upload_max_bytes: int
    status: FileQuotaPolicyStatus
    config_errors: list[str]


@dataclass(frozen=True, slots=True)
class FileQuotaPolicyUsage:
    """保存当前 metadata 使用量和拟上传后的 projected 使用量。"""

    current_used_size_bytes: int
    proposed_upload_size_bytes: int
    projected_used_size_bytes: int
    current_usage_ratio: float | None
    projected_usage_ratio: float | None


@dataclass(frozen=True, slots=True)
class FileQuotaPolicySafety:
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


@dataclass(frozen=True, slots=True)
class FileQuotaPolicyDryRunReport:
    """quota policy dry-run 的完整结果，不代表真实上传授权已被阻断。"""

    generated_at: datetime
    action_mode: Literal["quota_policy_dry_run"]
    file_type: str
    filename: str | None
    policy: FileQuotaPolicyConfig
    usage: FileQuotaPolicyUsage
    would_warn: bool
    would_block: bool
    reasons: list[str]
    safety: FileQuotaPolicySafety


@dataclass(frozen=True, slots=True)
class FileQuotaPolicyOpsSafety:
    """声明 quota ops summary 只读取 metadata 和 audit，不执行任何运维动作。"""

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


@dataclass(frozen=True, slots=True)
class FileQuotaPolicyRollbackOption:
    """描述一个只读 rollback 开关建议，不在运行时修改配置。"""

    option_id: str
    label: str
    env_var: str
    target_value: str
    current_value: str
    currently_effective: bool
    effect: str
    requires_restart: bool


@dataclass(frozen=True, slots=True)
class FileQuotaPolicyAuditReplayItem:
    """保存 quota enforcement 审计事件的安全重放摘要。"""

    audit_id: str
    action: str
    target_type: str
    target_id: str
    actor_role: str
    actor_id: str | None
    reason: str | None
    trace_id: str
    created_at: datetime
    outcome: str | None
    file_type: str | None
    filename: str | None
    would_block: bool | None
    override_applied: bool | None
    current_used_size_bytes: int | None
    proposed_upload_size_bytes: int | None
    projected_used_size_bytes: int | None
    quota_bytes: int | None
    policy_status: str | None
    reasons: list[str]
    details: AuditDetails | None


@dataclass(frozen=True, slots=True)
class FileQuotaPolicyOpsSummary:
    """汇总 quota enforcement 运维状态、rollback 选项和 audit replay。"""

    generated_at: datetime
    action_mode: Literal["quota_policy_ops_summary"]
    policy: FileQuotaPolicyConfig
    usage: FileQuotaPolicyUsage
    enforcement_ready: bool
    current_usage_would_warn: bool
    current_usage_would_block: bool
    kill_switch_enabled: bool
    reasons: list[str]
    rollback_options: list[FileQuotaPolicyRollbackOption]
    audit_replay: list[FileQuotaPolicyAuditReplayItem]
    audit_replay_total: int
    audit_replay_limit: int
    audit_replay_truncated: bool
    safety: FileQuotaPolicyOpsSafety


@dataclass(frozen=True, slots=True)
class FileQuotaPolicyEnforcementDecision:
    """保存 upload authorization quota preflight 的阻断、override 和审计决策。"""

    report: FileQuotaPolicyDryRunReport
    actor_role: str
    enforcement_required: bool
    blocked: bool
    override_requested: bool
    override_allowed: bool
    override_applied: bool
    audit_action: Literal["file.quota_policy_block", "file.quota_policy_override"] | None
    audit_reason: str | None
    message: str | None
    reasons: list[str]

    def audit_outcome(self) -> str:
        """返回审计用 outcome，保持 compact reason 稳定。"""

        if self.override_applied:
            return "overridden"
        if self.blocked:
            return "blocked"
        return "allowed"


class FileQuotaPolicyDryRunService:
    """基于 document_files metadata 评估 quota dry-run 和上传授权阻断结果。"""

    def __init__(self, settings: Settings, repository: DocumentFileRepositoryProtocol) -> None:
        self.settings = settings
        self.repository = repository

    def dry_run(
        self,
        *,
        size_bytes: int,
        file_type: str,
        filename: str | None = None,
        now: datetime | None = None,
    ) -> FileQuotaPolicyDryRunReport:
        """评估拟上传文件是否会触发 warning/block；不创建上传授权。"""

        generated_at = _normalize_datetime(now or utc_now())
        policy = self._build_policy()
        proposed_size = max(0, size_bytes)
        current_used = self._active_used_size_bytes()
        projected_used = current_used + proposed_size
        usage = self._build_usage(
            current_used=current_used,
            proposed_size=proposed_size,
            projected_used=projected_used,
            quota_bytes=policy.quota_bytes,
        )
        would_warn, would_block, reasons = self._evaluate(policy=policy, usage=usage)
        if proposed_size > policy.upload_max_bytes:
            would_block = True
            reasons.append("upload_size_exceeds_max_bytes")
        return FileQuotaPolicyDryRunReport(
            generated_at=generated_at,
            action_mode="quota_policy_dry_run",
            file_type=file_type,
            filename=filename,
            policy=policy,
            usage=usage,
            would_warn=would_warn,
            would_block=would_block,
            reasons=reasons,
            safety=FileQuotaPolicySafety(),
        )

    def ops_summary(
        self,
        *,
        audit_events: list[AuditEvent],
        replay_limit: int = 20,
        now: datetime | None = None,
    ) -> FileQuotaPolicyOpsSummary:
        """生成 Admin-only quota enforcement 运维摘要，不执行 rollback 或阻断。"""

        current_usage_report = self.dry_run(
            size_bytes=0,
            file_type="source_pdf",
            filename=None,
            now=now,
        )
        normalized_limit = max(1, min(100, replay_limit))
        replay_total, replay_items = self._build_audit_replay(
            audit_events=audit_events,
            replay_limit=normalized_limit,
        )
        return FileQuotaPolicyOpsSummary(
            generated_at=current_usage_report.generated_at,
            action_mode="quota_policy_ops_summary",
            policy=current_usage_report.policy,
            usage=current_usage_report.usage,
            enforcement_ready=current_usage_report.policy.status == "ready"
            and not self.settings.files_quota_policy_kill_switch,
            current_usage_would_warn=current_usage_report.would_warn,
            current_usage_would_block=self._should_enforce_block(current_usage_report),
            kill_switch_enabled=self.settings.files_quota_policy_kill_switch,
            reasons=current_usage_report.reasons,
            rollback_options=self._build_rollback_options(),
            audit_replay=replay_items,
            audit_replay_total=replay_total,
            audit_replay_limit=normalized_limit,
            audit_replay_truncated=replay_total > normalized_limit,
            safety=FileQuotaPolicyOpsSafety(),
        )

    def evaluate_upload_authorization(
        self,
        *,
        size_bytes: int,
        file_type: str,
        filename: str | None = None,
        actor_role: str,
        override_reason: str | None = None,
        override_confirmation: str | None = None,
        now: datetime | None = None,
    ) -> FileQuotaPolicyEnforcementDecision:
        """评估真实上传授权是否应被 quota policy 阻断或允许 admin override。"""

        report = self.dry_run(
            size_bytes=size_bytes,
            file_type=file_type,
            filename=filename,
            now=now,
        )
        enforcement_required = self._should_enforce_block(report)
        override_reason_text = _normalize_optional_text(override_reason)
        override_confirmation_text = _normalize_optional_text(override_confirmation)
        override_requested = override_reason_text is not None or override_confirmation_text is not None
        reasons = list(report.reasons)
        if not enforcement_required:
            return self._build_enforcement_decision(
                report=report,
                actor_role=actor_role,
                enforcement_required=False,
                blocked=False,
                override_requested=override_requested,
                override_allowed=False,
                override_applied=False,
                audit_action=None,
                message=None,
                reasons=reasons,
            )

        reasons.append("quota_policy_enforced_block")
        override_allowed = (
            actor_role == "admin"
            and override_reason_text is not None
            and override_confirmation_text == FILE_QUOTA_POLICY_OVERRIDE_CONFIRMATION_PHRASE
        )
        if override_requested and not override_allowed:
            reasons.extend(
                self._override_rejection_reasons(
                    actor_role=actor_role,
                    override_reason=override_reason_text,
                    override_confirmation=override_confirmation_text,
                )
            )
        if override_allowed:
            return self._build_enforcement_decision(
                report=report,
                actor_role=actor_role,
                enforcement_required=True,
                blocked=False,
                override_requested=True,
                override_allowed=True,
                override_applied=True,
                audit_action="file.quota_policy_override",
                message=None,
                reasons=[*reasons, "quota_policy_admin_override_applied"],
                override_reason=override_reason_text,
            )
        return self._build_enforcement_decision(
            report=report,
            actor_role=actor_role,
            enforcement_required=True,
            blocked=True,
            override_requested=override_requested,
            override_allowed=False,
            override_applied=False,
            audit_action="file.quota_policy_block",
            message="文件上传授权被 quota policy 阻断。",
            reasons=reasons,
        )

    def _build_policy(self) -> FileQuotaPolicyConfig:
        """归一化 settings 中的 staged quota policy 配置。"""

        config_errors: list[str] = []
        enabled = self.settings.files_quota_policy_enabled
        dry_run = self.settings.files_quota_policy_dry_run
        quota_bytes = self.settings.files_quota_bytes if self.settings.files_quota_bytes > 0 else None
        warning_ratio = self.settings.files_quota_warning_threshold_ratio
        block_ratio = self.settings.files_quota_block_threshold_ratio

        if quota_bytes is not None and warning_ratio <= 0:
            config_errors.append("files_quota_warning_threshold_ratio_must_be_positive")
        if quota_bytes is not None and block_ratio <= 0:
            config_errors.append("files_quota_block_threshold_ratio_must_be_positive")
        if quota_bytes is not None and warning_ratio > block_ratio:
            config_errors.append("files_quota_warning_threshold_ratio_exceeds_block_threshold_ratio")

        status: FileQuotaPolicyStatus = "disabled"
        if enabled and quota_bytes is None:
            status = "not_configured"
        elif enabled and config_errors:
            status = "invalid"
        elif enabled and dry_run:
            status = "dry_run"
        elif enabled:
            status = "ready"

        return FileQuotaPolicyConfig(
            enabled=enabled,
            dry_run=dry_run,
            configured=quota_bytes is not None,
            quota_bytes=quota_bytes,
            warning_threshold_ratio=warning_ratio if quota_bytes is not None else None,
            block_threshold_ratio=block_ratio if quota_bytes is not None else None,
            warning_threshold_bytes=int(quota_bytes * warning_ratio) if quota_bytes is not None and warning_ratio > 0 else None,
            block_threshold_bytes=int(quota_bytes * block_ratio) if quota_bytes is not None and block_ratio > 0 else None,
            upload_max_bytes=self.settings.jobs_upload_max_bytes,
            status=status,
            config_errors=config_errors,
        )

    def _active_used_size_bytes(self) -> int:
        """累加非 deleted 的 document_files metadata bytes，保持与 storage usage 语义一致。"""

        return sum(
            max(0, record.size_bytes)
            for record in self.repository.list_document_files()
            if record.status != "deleted"
        )

    def _build_usage(
        self,
        *,
        current_used: int,
        proposed_size: int,
        projected_used: int,
        quota_bytes: int | None,
    ) -> FileQuotaPolicyUsage:
        """构造当前和 projected 使用量，未配置 quota 时 ratio 为 None。"""

        if quota_bytes is None or quota_bytes <= 0:
            current_ratio = None
            projected_ratio = None
        else:
            current_ratio = current_used / quota_bytes
            projected_ratio = projected_used / quota_bytes
        return FileQuotaPolicyUsage(
            current_used_size_bytes=current_used,
            proposed_upload_size_bytes=proposed_size,
            projected_used_size_bytes=projected_used,
            current_usage_ratio=current_ratio,
            projected_usage_ratio=projected_ratio,
        )

    def _evaluate(
        self,
        *,
        policy: FileQuotaPolicyConfig,
        usage: FileQuotaPolicyUsage,
    ) -> tuple[bool, bool, list[str]]:
        """根据 staged policy 计算 would_warn/would_block 和原因列表。"""

        reasons: list[str] = []
        if not policy.enabled:
            return False, False, ["quota_policy_disabled"]
        if not policy.configured:
            return False, False, ["quota_not_configured"]
        if policy.config_errors:
            return False, False, ["quota_policy_config_invalid", *policy.config_errors]

        projected_ratio = usage.projected_usage_ratio or 0.0
        warning_ratio = policy.warning_threshold_ratio or 0.0
        block_ratio = policy.block_threshold_ratio or 0.0
        would_warn = projected_ratio >= warning_ratio
        would_block = projected_ratio >= block_ratio
        if would_warn:
            reasons.append("projected_usage_reaches_warning_threshold")
        if would_block:
            reasons.append("projected_usage_reaches_block_threshold")
        if policy.dry_run:
            reasons.append("quota_policy_dry_run_only")
        return would_warn, would_block, reasons or ["quota_policy_ok"]

    def _should_enforce_block(self, report: FileQuotaPolicyDryRunReport) -> bool:
        """只有 ready policy、未触发 kill switch 且 would_block=true 时才执行真实上传阻断。"""

        return report.policy.status == "ready" and report.would_block and not self.settings.files_quota_policy_kill_switch

    def _override_rejection_reasons(
        self,
        *,
        actor_role: str,
        override_reason: str | None,
        override_confirmation: str | None,
    ) -> list[str]:
        """列出 override 请求未被接受的原因，避免静默忽略错误 override。"""

        reasons: list[str] = []
        if actor_role != "admin":
            reasons.append("quota_override_requires_admin")
        if override_reason is None:
            reasons.append("quota_override_reason_required")
        if override_confirmation != FILE_QUOTA_POLICY_OVERRIDE_CONFIRMATION_PHRASE:
            reasons.append("quota_override_confirmation_invalid")
        return reasons

    def _build_enforcement_decision(
        self,
        *,
        report: FileQuotaPolicyDryRunReport,
        actor_role: str,
        enforcement_required: bool,
        blocked: bool,
        override_requested: bool,
        override_allowed: bool,
        override_applied: bool,
        audit_action: Literal["file.quota_policy_block", "file.quota_policy_override"] | None,
        message: str | None,
        reasons: list[str],
        override_reason: str | None = None,
    ) -> FileQuotaPolicyEnforcementDecision:
        """组装 enforcement decision 和 compact audit reason。"""

        audit_reason = None
        if audit_action is not None:
            audit_reason = self._build_audit_reason(
                report=report,
                actor_role=actor_role,
                blocked=blocked,
                override_applied=override_applied,
                reasons=reasons,
                override_reason=override_reason,
            )
        return FileQuotaPolicyEnforcementDecision(
            report=report,
            actor_role=actor_role,
            enforcement_required=enforcement_required,
            blocked=blocked,
            override_requested=override_requested,
            override_allowed=override_allowed,
            override_applied=override_applied,
            audit_action=audit_action,
            audit_reason=audit_reason,
            message=message,
            reasons=reasons,
        )

    def _build_audit_reason(
        self,
        *,
        report: FileQuotaPolicyDryRunReport,
        actor_role: str,
        blocked: bool,
        override_applied: bool,
        reasons: list[str],
        override_reason: str | None,
    ) -> str:
        """生成 quota enforcement compact audit reason，不包含文件内容或对象定位。"""

        outcome = "overridden" if override_applied else "blocked" if blocked else "allowed"
        parts = [
            f"outcome={outcome}",
            f"actor_role={actor_role}",
            f"file_type={report.file_type}",
            f"proposed_size={report.usage.proposed_upload_size_bytes}",
            f"current_used={report.usage.current_used_size_bytes}",
            f"projected_used={report.usage.projected_used_size_bytes}",
            f"quota_bytes={report.policy.quota_bytes or 0}",
            f"reasons={','.join(reasons)}",
        ]
        if override_reason:
            parts.append(f"override_reason={'_'.join(override_reason.split())}")
        return " ".join(parts)

    def _build_rollback_options(self) -> list[FileQuotaPolicyRollbackOption]:
        """列出可回滚真实阻断能力的配置开关，不修改当前 settings。"""

        return [
            FileQuotaPolicyRollbackOption(
                option_id="enable_kill_switch",
                label="Enable quota policy kill switch",
                env_var="FILES_QUOTA_POLICY_KILL_SWITCH",
                target_value="true",
                current_value=_bool_text(self.settings.files_quota_policy_kill_switch),
                currently_effective=self.settings.files_quota_policy_kill_switch,
                effect="prevents_ready_policy_from_executing_upload_blocks",
                requires_restart=True,
            ),
            FileQuotaPolicyRollbackOption(
                option_id="force_dry_run",
                label="Force quota policy dry-run",
                env_var="FILES_QUOTA_POLICY_DRY_RUN",
                target_value="true",
                current_value=_bool_text(self.settings.files_quota_policy_dry_run),
                currently_effective=self.settings.files_quota_policy_dry_run,
                effect="reports_would_block_without_blocking_upload_authorization",
                requires_restart=True,
            ),
            FileQuotaPolicyRollbackOption(
                option_id="disable_policy",
                label="Disable quota policy",
                env_var="FILES_QUOTA_POLICY_ENABLED",
                target_value="false",
                current_value=_bool_text(self.settings.files_quota_policy_enabled),
                currently_effective=not self.settings.files_quota_policy_enabled,
                effect="turns_off_quota_policy_evaluation_for_upload_authorization",
                requires_restart=True,
            ),
        ]

    def _build_audit_replay(
        self,
        *,
        audit_events: list[AuditEvent],
        replay_limit: int,
    ) -> tuple[int, list[FileQuotaPolicyAuditReplayItem]]:
        """筛选 quota enforcement 审计事件并按时间倒序生成 replay 摘要。"""

        quota_events = [
            event
            for event in audit_events
            if event.action in {"file.quota_policy_block", "file.quota_policy_override"}
        ]
        quota_events.sort(
            key=lambda event: (_normalize_datetime(event.created_at), event.audit_id),
            reverse=True,
        )
        return len(quota_events), [
            self._build_audit_replay_item(event)
            for event in quota_events[:replay_limit]
        ]

    def _build_audit_replay_item(self, event: AuditEvent) -> FileQuotaPolicyAuditReplayItem:
        """从单条 quota audit event 中提取稳定 replay 字段。"""

        details = event.details if isinstance(event.details, dict) else None
        policy = _as_dict(details.get("policy") if details else None)
        usage = _as_dict(details.get("usage") if details else None)
        override = _as_dict(details.get("override") if details else None)
        return FileQuotaPolicyAuditReplayItem(
            audit_id=event.audit_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            actor_role=event.actor_role,
            actor_id=event.actor_id,
            reason=event.reason,
            trace_id=event.trace_id,
            created_at=_normalize_datetime(event.created_at),
            outcome=_string_or_none(details.get("outcome") if details else None) or _outcome_from_action(event.action),
            file_type=_string_or_none(details.get("file_type") if details else None),
            filename=_string_or_none(details.get("filename") if details else None),
            would_block=_bool_or_none(details.get("would_block") if details else None),
            override_applied=_bool_or_none(override.get("applied") if override else None),
            current_used_size_bytes=_int_or_none(usage.get("current_used_size_bytes") if usage else None),
            proposed_upload_size_bytes=_int_or_none(usage.get("proposed_upload_size_bytes") if usage else None),
            projected_used_size_bytes=_int_or_none(usage.get("projected_used_size_bytes") if usage else None),
            quota_bytes=_int_or_none(policy.get("quota_bytes") if policy else None),
            policy_status=_string_or_none(policy.get("status") if policy else None),
            reasons=_string_list(details.get("reasons") if details else None),
            details=details,
        )


def _normalize_datetime(value: datetime) -> datetime:
    """统一为 timezone-aware UTC datetime，兼容测试传入 naive 时间。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalize_optional_text(value: str | None) -> str | None:
    """清理可选文本，空白字符串视为未传。"""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _bool_text(value: bool) -> str:
    """把 bool 配置值转换成 env var 友好的小写文本。"""

    return "true" if value else "false"


def _as_dict(value: Any) -> dict[str, Any] | None:
    """仅接受普通 dict，避免从 JSON details 中误读非对象值。"""

    if isinstance(value, dict):
        return value
    return None


def _string_or_none(value: Any) -> str | None:
    """从 JSON details 中安全读取字符串。"""

    if isinstance(value, str):
        return value
    return None


def _bool_or_none(value: Any) -> bool | None:
    """从 JSON details 中安全读取布尔值。"""

    if isinstance(value, bool):
        return value
    return None


def _int_or_none(value: Any) -> int | None:
    """从 JSON details 中安全读取整数，排除 bool 这个 int 子类。"""

    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _string_list(value: Any) -> list[str]:
    """从 JSON details 中安全读取字符串列表。"""

    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _outcome_from_action(action: str) -> str | None:
    """在旧审计缺少 details 时，根据 action 推断 replay outcome。"""

    if action == "file.quota_policy_block":
        return "blocked"
    if action == "file.quota_policy_override":
        return "overridden"
    return None
