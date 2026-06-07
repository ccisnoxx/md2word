# File: app/domains/files/quota_policy.py
# Purpose: Evaluate staged file upload quota policy for dry-run and guarded upload blocking.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.core.config import Settings
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
        """只有 ready policy 且 would_block=true 时才执行真实上传阻断。"""

        return report.policy.status == "ready" and report.would_block

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
