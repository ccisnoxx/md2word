# File: app/domains/ops/recovery_actions.py
# Purpose: Provide read-only recovery action registry and exact-target preview logic.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import status

from app.core.errors import ApiError
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.jobs.models import JobRecord, utc_now
from app.domains.jobs.repository import JobSnapshotRepositoryProtocol
from app.domains.ops.schemas import (
    OpsRecoveryActionCategory,
    OpsRecoveryActionPreviewRequest,
    OpsRecoveryActionPreviewResponse,
    OpsRecoveryActionRegistryResponse,
    OpsRecoveryActionResponse,
    OpsRecoveryActionRiskFlagsResponse,
    OpsRecoveryActionSafetyResponse,
    OpsRecoveryActionTargetPreviewResponse,
    OpsRecoveryActionTargetType,
)


TERMINAL_DOCUMENT_JOB_STATUSES = {"succeeded", "failed", "canceled"}
TERMINAL_LEGACY_JOB_STATUSES = {"completed", "failed", "canceled"}


@dataclass(frozen=True, slots=True)
class OpsRecoveryActionDefinition:
    """描述一个可治理或候选的 Ops recovery action。"""

    action_id: str
    label: str
    category: OpsRecoveryActionCategory
    target_type: OpsRecoveryActionTargetType
    available: bool
    requires_admin: bool
    requires_reason: bool
    requires_confirmation: bool
    dry_run_supported: bool
    mutates_metadata: bool
    mutates_queue: bool
    calls_provider: bool
    sends_notification: bool
    deletes_data: bool
    audit_action: str | None
    known_gaps: tuple[str, ...]
    suggested_route: str | None = None


OPS_RECOVERY_ACTIONS: tuple[OpsRecoveryActionDefinition, ...] = (
    OpsRecoveryActionDefinition(
        action_id="document_job.retry",
        label="Document job retry",
        category="recovery",
        target_type="document_job",
        available=True,
        requires_admin=True,
        requires_reason=True,
        requires_confirmation=False,
        dry_run_supported=True,
        mutates_metadata=True,
        mutates_queue=True,
        calls_provider=False,
        sends_notification=False,
        deletes_data=False,
        audit_action="document_job.retry",
        known_gaps=("实际执行可能投递 worker，后续阶段可能调用 provider；本 preview 不执行。",),
        suggested_route="/jobs?status=failed&sort=updated_at_desc",
    ),
    OpsRecoveryActionDefinition(
        action_id="document_job.cancel",
        label="Document job cancel",
        category="cancellation",
        target_type="document_job",
        available=True,
        requires_admin=True,
        requires_reason=True,
        requires_confirmation=True,
        dry_run_supported=True,
        mutates_metadata=True,
        mutates_queue=False,
        calls_provider=False,
        sends_notification=False,
        deletes_data=False,
        audit_action="document_job.cancel",
        known_gaps=("现有取消仅更新本地 metadata，不取消 provider-side work。",),
        suggested_route="/jobs?status=running&sort=updated_at_desc",
    ),
    OpsRecoveryActionDefinition(
        action_id="document_job.archive",
        label="Document job archive",
        category="archive",
        target_type="document_job",
        available=True,
        requires_admin=True,
        requires_reason=False,
        requires_confirmation=False,
        dry_run_supported=True,
        mutates_metadata=True,
        mutates_queue=False,
        calls_provider=False,
        sends_notification=False,
        deletes_data=False,
        audit_action="document_job.archive",
        known_gaps=("归档只隐藏默认列表，不删除文件或事件；本 preview 不执行。",),
        suggested_route="/jobs?sort=updated_at_desc",
    ),
    OpsRecoveryActionDefinition(
        action_id="legacy_job.retry",
        label="Legacy job retry",
        category="recovery",
        target_type="legacy_job",
        available=True,
        requires_admin=True,
        requires_reason=True,
        requires_confirmation=False,
        dry_run_supported=True,
        mutates_metadata=True,
        mutates_queue=True,
        calls_provider=False,
        sends_notification=False,
        deletes_data=False,
        audit_action="job.retry",
        known_gaps=("实际执行会重置 job 并投递 stage message；source_pdf 后续可能调用 MinerU。",),
        suggested_route=None,
    ),
    OpsRecoveryActionDefinition(
        action_id="legacy_job.cancel",
        label="Legacy job cancel",
        category="cancellation",
        target_type="legacy_job",
        available=True,
        requires_admin=True,
        requires_reason=True,
        requires_confirmation=True,
        dry_run_supported=True,
        mutates_metadata=True,
        mutates_queue=True,
        calls_provider=False,
        sends_notification=False,
        deletes_data=False,
        audit_action="job.cancel",
        known_gaps=("实际执行会删除 replayable stage messages；本 preview 不触碰队列。",),
        suggested_route=None,
    ),
    OpsRecoveryActionDefinition(
        action_id="legacy_job.recover_mineru_result",
        label="Legacy job recover MinerU result",
        category="recovery",
        target_type="legacy_job",
        available=True,
        requires_admin=True,
        requires_reason=True,
        requires_confirmation=True,
        dry_run_supported=True,
        mutates_metadata=True,
        mutates_queue=True,
        calls_provider=True,
        sends_notification=False,
        deletes_data=False,
        audit_action=None,
        known_gaps=("现有执行入口会同步查询 MinerU 且缺少 reason/audit；本 preview 只检查 metadata。",),
        suggested_route=None,
    ),
    OpsRecoveryActionDefinition(
        action_id="legacy_job.cleanup_local_files",
        label="Legacy job cleanup local files",
        category="cleanup",
        target_type="legacy_job",
        available=True,
        requires_admin=True,
        requires_reason=True,
        requires_confirmation=True,
        dry_run_supported=True,
        mutates_metadata=False,
        mutates_queue=False,
        calls_provider=False,
        sends_notification=False,
        deletes_data=True,
        audit_action="job.cleanup_local_files",
        known_gaps=("现有执行入口无 dry-run 且会删除本地 work dir；本 preview 不返回本地路径。",),
        suggested_route=None,
    ),
    OpsRecoveryActionDefinition(
        action_id="provider.cancel",
        label="Provider cancellation",
        category="provider",
        target_type="provider_operation",
        available=False,
        requires_admin=True,
        requires_reason=True,
        requires_confirmation=True,
        dry_run_supported=True,
        mutates_metadata=True,
        mutates_queue=False,
        calls_provider=True,
        sends_notification=False,
        deletes_data=False,
        audit_action=None,
        known_gaps=("本地 MinerUClient 尚无 cancel method。", "Provider cancellation 语义需要先核对官方文档/API。"),
        suggested_route=None,
    ),
    OpsRecoveryActionDefinition(
        action_id="alert.delivery",
        label="Alert delivery fake outbox",
        category="notification",
        target_type="alert",
        available=True,
        requires_admin=True,
        requires_reason=True,
        requires_confirmation=True,
        dry_run_supported=True,
        mutates_metadata=True,
        mutates_queue=False,
        calls_provider=False,
        sends_notification=False,
        deletes_data=False,
        audit_action="ops.alert_delivery_fake",
        known_gaps=("当前只支持 local_outbox fake delivery；真实 Slack/email/webhook delivery 尚未实现。",),
        suggested_route="/system-status",
    ),
    OpsRecoveryActionDefinition(
        action_id="file_retention.automated_cleanup_execute",
        label="Automated cleanup execution",
        category="automation",
        target_type="cleanup_run",
        available=False,
        requires_admin=True,
        requires_reason=True,
        requires_confirmation=True,
        dry_run_supported=True,
        mutates_metadata=True,
        mutates_queue=True,
        calls_provider=False,
        sends_notification=False,
        deletes_data=True,
        audit_action=None,
        known_gaps=("自动化清理的 run history、lock、signed plan、quota gate 和 rollback 证据尚未实现。",),
        suggested_route="/system-status/file-retention",
    ),
)


class OpsRecoveryActionService:
    """提供 Admin-only recovery action registry 和无副作用 preview。"""

    def __init__(
        self,
        *,
        document_job_repository: DocumentJobRepositoryProtocol,
        job_repository: JobSnapshotRepositoryProtocol,
        document_job_max_retries: int,
        mineru_api_token_configured: bool,
    ) -> None:
        self.document_job_repository = document_job_repository
        self.job_repository = job_repository
        self.document_job_max_retries = document_job_max_retries
        self.mineru_api_token_configured = mineru_api_token_configured

    def list_registry(self) -> OpsRecoveryActionRegistryResponse:
        """返回完整 registry，不读取 provider、不写审计、不修改状态。"""

        return OpsRecoveryActionRegistryResponse(
            generated_at=utc_now(),
            actions=[self._build_action_response(action) for action in OPS_RECOVERY_ACTIONS],
            safety=self._build_safety(),
        )

    def preview_action(self, request: OpsRecoveryActionPreviewRequest) -> OpsRecoveryActionPreviewResponse:
        """对一个 action/target 执行只读 eligibility 检查。"""

        action = self._get_action_definition(request.action_id)
        if request.target_type != action.target_type:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"target_type 与 action 不匹配: action={action.action_id} expected={action.target_type}",
            )
        action_response = self._build_action_response(action)
        if action.target_type == "document_job":
            return self._preview_document_job_action(action_response, request.target_id)
        if action.target_type == "legacy_job":
            return self._preview_legacy_job_action(action_response, request.target_id)
        return self._preview_candidate_only_action(action_response, request.target_id)

    def _get_action_definition(self, action_id: str) -> OpsRecoveryActionDefinition:
        """按稳定 action_id 查找 registry 定义。"""

        for action in OPS_RECOVERY_ACTIONS:
            if action.action_id == action_id:
                return action
        raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"Ops recovery action 不存在: {action_id}")

    def _build_action_response(self, action: OpsRecoveryActionDefinition) -> OpsRecoveryActionResponse:
        """把静态定义映射为包含动态可用性的 API 条目。"""

        available = action.available
        known_gaps = list(action.known_gaps)
        if action.action_id == "legacy_job.recover_mineru_result" and not self.mineru_api_token_configured:
            available = False
            known_gaps.append("MINERU_API_TOKEN 未配置，主动查询 MinerU 结果不可执行。")
        return OpsRecoveryActionResponse(
            action_id=action.action_id,
            label=action.label,
            category=action.category,
            target_type=action.target_type,
            available=available,
            requires_admin=action.requires_admin,
            requires_reason=action.requires_reason,
            requires_confirmation=action.requires_confirmation,
            dry_run_supported=action.dry_run_supported,
            mutates_metadata=action.mutates_metadata,
            mutates_queue=action.mutates_queue,
            calls_provider=action.calls_provider,
            sends_notification=action.sends_notification,
            deletes_data=action.deletes_data,
            audit_action=action.audit_action,
            known_gaps=known_gaps,
            suggested_route=action.suggested_route,
        )

    def _preview_document_job_action(
        self,
        action: OpsRecoveryActionResponse,
        target_id: str,
    ) -> OpsRecoveryActionPreviewResponse:
        """读取 document_job metadata 并计算动作 eligibility。"""

        job = self.document_job_repository.get_document_job(target_id)
        target = self._build_document_job_target(action.target_type, target_id, job)
        missing_gates: list[str] = []
        if job is None:
            missing_gates.append("target_not_found")
        elif job.archived_at is not None:
            missing_gates.append("target_archived")
        elif action.action_id == "document_job.retry":
            self._append_document_job_retry_gates(job, missing_gates)
        elif action.action_id == "document_job.cancel":
            if job.status not in {"pending", "queued", "running"}:
                missing_gates.append("status_not_cancelable")
        elif action.action_id == "document_job.archive" and job.status not in TERMINAL_DOCUMENT_JOB_STATUSES:
            missing_gates.append("status_not_terminal")
        return self._build_preview_response(
            action=action,
            target=target,
            missing_gates=missing_gates,
        )

    def _preview_legacy_job_action(
        self,
        action: OpsRecoveryActionResponse,
        target_id: str,
    ) -> OpsRecoveryActionPreviewResponse:
        """读取 legacy job metadata 并计算动作 eligibility。"""

        job = self.job_repository.get_job(target_id)
        target = self._build_legacy_job_target(action.target_type, target_id, job)
        missing_gates: list[str] = []
        if job is None:
            missing_gates.append("target_not_found")
        elif action.action_id == "legacy_job.retry" and job.projected_status() != "failed":
            missing_gates.append("status_not_failed")
        elif action.action_id == "legacy_job.cancel":
            if job.projected_status() in TERMINAL_LEGACY_JOB_STATUSES:
                missing_gates.append("status_not_cancelable")
            if job.resolved_execution_status() == "converting":
                missing_gates.append("converting_cannot_be_interrupted")
        elif action.action_id == "legacy_job.recover_mineru_result":
            self._append_legacy_mineru_recovery_gates(job, missing_gates)
        elif action.action_id == "legacy_job.cleanup_local_files":
            if job.resolved_lifecycle_status() != "completed" or job.resolved_execution_status() != "idle":
                missing_gates.append("status_not_cleanup_eligible")
        return self._build_preview_response(
            action=action,
            target=target,
            missing_gates=missing_gates,
        )

    def _preview_candidate_only_action(
        self,
        action: OpsRecoveryActionResponse,
        target_id: str,
    ) -> OpsRecoveryActionPreviewResponse:
        """返回候选执行动作的不可用 preview，不要求真实目标记录。"""

        target = OpsRecoveryActionTargetPreviewResponse(
            target_type=action.target_type,
            target_id=target_id,
            exists=False,
            summary={"record_lookup_supported": False},
        )
        return self._build_preview_response(
            action=action,
            target=target,
            missing_gates=["action_not_available", "execution_contract_missing"],
        )

    def _append_document_job_retry_gates(self, job: DocumentJobRecord, missing_gates: list[str]) -> None:
        """为 document_job retry 补充重试状态、次数和失败类型 gate。"""

        if job.status != "failed":
            missing_gates.append("status_not_failed")
        if job.retry_count >= self.document_job_max_retries:
            missing_gates.append("retry_limit_reached")
        if job.error_code in {"document_job_invalid_input"}:
            missing_gates.append("failure_not_retryable")

    def _append_legacy_mineru_recovery_gates(self, job: JobRecord, missing_gates: list[str]) -> None:
        """为 legacy MinerU recovery 补充 provider 配置和 source_pdf metadata gate。"""

        if job.source_kind != "source_pdf":
            missing_gates.append("source_kind_not_source_pdf")
        if not self.mineru_api_token_configured:
            missing_gates.append("mineru_api_token_missing")
        if job.resolved_execution_status() != "parsing":
            missing_gates.append("execution_status_not_parsing")
        if job.projected_status() in {"completed", "canceled"}:
            missing_gates.append("status_terminal")
        if not job.read_mineru_batch_id():
            missing_gates.append("mineru_batch_id_missing")

    def _build_preview_response(
        self,
        *,
        action: OpsRecoveryActionResponse,
        target: OpsRecoveryActionTargetPreviewResponse,
        missing_gates: list[str],
    ) -> OpsRecoveryActionPreviewResponse:
        """组装统一 preview 响应并附加只读安全声明。"""

        unique_missing_gates = _unique_preserve_order(missing_gates)
        if not action.available and "action_not_available" not in unique_missing_gates:
            unique_missing_gates.insert(0, "action_not_available")
        return OpsRecoveryActionPreviewResponse(
            generated_at=utc_now(),
            action=action,
            target=target,
            eligible=target.exists and action.available and not unique_missing_gates,
            missing_gates=unique_missing_gates,
            warnings=action.known_gaps,
            risk_flags=self._build_risk_flags(action),
            audit_action=action.audit_action,
            safety=self._build_safety(),
        )

    def _build_document_job_target(
        self,
        target_type: OpsRecoveryActionTargetType,
        target_id: str,
        job: DocumentJobRecord | None,
    ) -> OpsRecoveryActionTargetPreviewResponse:
        """把 document_job 记录映射为不含敏感字段的 preview target。"""

        if job is None:
            return OpsRecoveryActionTargetPreviewResponse(target_type=target_type, target_id=target_id, exists=False)
        return OpsRecoveryActionTargetPreviewResponse(
            target_type=target_type,
            target_id=target_id,
            exists=True,
            status=job.status,
            stage=job.stage,
            summary={
                "retry_count": job.retry_count,
                "archived": job.archived_at is not None,
                "created_by": job.created_by,
                "updated_at": _format_datetime(job.updated_at),
                "failed_stage": job.failed_stage,
                "error_code": job.error_code,
            },
        )

    def _build_legacy_job_target(
        self,
        target_type: OpsRecoveryActionTargetType,
        target_id: str,
        job: JobRecord | None,
    ) -> OpsRecoveryActionTargetPreviewResponse:
        """把 legacy job 记录映射为不含路径、object key 或 provider secret 的 preview target。"""

        if job is None:
            return OpsRecoveryActionTargetPreviewResponse(target_type=target_type, target_id=target_id, exists=False)
        return OpsRecoveryActionTargetPreviewResponse(
            target_type=target_type,
            target_id=target_id,
            exists=True,
            status=job.projected_status(),
            stage=job.resolved_execution_status(),
            summary={
                "source_kind": job.source_kind,
                "lifecycle_status": job.resolved_lifecycle_status(),
                "execution_status": job.resolved_execution_status(),
                "has_mineru_batch_id": bool(job.read_mineru_batch_id()),
                "result_ready": job.result_ready,
                "updated_at": _format_datetime(job.updated_at),
                "error_code": job.error_code,
            },
        )

    def _build_risk_flags(self, action: OpsRecoveryActionResponse) -> OpsRecoveryActionRiskFlagsResponse:
        """从 action 条目提取执行风险 flags。"""

        return OpsRecoveryActionRiskFlagsResponse(
            mutates_metadata=action.mutates_metadata,
            mutates_queue=action.mutates_queue,
            calls_provider=action.calls_provider,
            sends_notification=action.sends_notification,
            deletes_data=action.deletes_data,
        )

    def _build_safety(self) -> OpsRecoveryActionSafetyResponse:
        """返回固定只读安全声明。"""

        return OpsRecoveryActionSafetyResponse()


def _format_datetime(value: datetime | None) -> str | None:
    """把可选 datetime 转为 ISO 字符串，避免 response summary 暴露对象。"""

    if value is None:
        return None
    return value.isoformat()


def _unique_preserve_order(values: list[str]) -> list[str]:
    """去重并保持 gate 顺序，便于前端稳定展示。"""

    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique
