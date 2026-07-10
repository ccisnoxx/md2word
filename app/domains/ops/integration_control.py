# File: app/domains/ops/integration_control.py
# Purpose: 生成真实集成能力的只读就绪状态与安全报告。

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.core.config import Settings
from app.domains.files.service import S3_DELETE_FAKE_CONTRACT_VERSION
from app.domains.resources.models import utc_now
from app.domains.ops.alert_delivery_contract import ALERT_DELIVERY_ADAPTER_CONTRACT_VERSION
from app.domains.ops.provider_cancellation_semantics import (
    PROVIDER_CANCELLATION_SEMANTICS_DECISION,
    PROVIDER_CANCELLATION_SEMANTICS_STATUS,
)
from app.domains.ops.real_alert_delivery import (
    REAL_ALERT_DELIVERY_ALERT_CODE,
    REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE,
    REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES,
    REAL_ALERT_DELIVERY_DESTINATION_ID,
    REAL_ALERT_DELIVERY_RATE_LIMIT_PER_HOUR,
    REAL_ALERT_DELIVERY_SECRET_REF,
    REAL_ALERT_DELIVERY_TARGET_LABEL,
    REAL_ALERT_DELIVERY_TIMEOUT_SECONDS,
)
from app.domains.ops.s3_delete_contract import (
    S3_DELETE_ADAPTER_CONTRACT_VERSION,
    S3_DELETE_LOCALSTACK_HARNESS,
)


OpsIntegrationCapabilityId = Literal[
    "alert_delivery",
    "provider_cancellation",
    "s3_deletion",
    "cleanup_scheduler_execute",
    "quota_enforcement",
]
OpsIntegrationCapabilityStatus = Literal["blocked", "dry_run_only", "ready"]
OpsIntegrationOverallStatus = Literal["blocked", "partial", "ready"]


@dataclass(frozen=True, slots=True)
class OpsIntegrationCapability:
    """描述单个真实集成能力当前是否可执行以及被哪些 gate 阻断。"""

    capability_id: OpsIntegrationCapabilityId
    label: str
    category: str
    status: OpsIntegrationCapabilityStatus
    real_execution_enabled: bool
    dry_run_only: bool
    kill_switch_active: bool
    configured: bool
    ready: bool
    blocking_reasons: list[str]
    required_gates: list[str]
    safe_config: dict[str, str | int | float | bool | None]

    def to_dict(self) -> dict[str, object]:
        """转换为 API response 可校验的 JSON-safe 字典。"""

        return {
            "capability_id": self.capability_id,
            "label": self.label,
            "category": self.category,
            "status": self.status,
            "real_execution_enabled": self.real_execution_enabled,
            "dry_run_only": self.dry_run_only,
            "kill_switch_active": self.kill_switch_active,
            "configured": self.configured,
            "ready": self.ready,
            "blocking_reasons": list(self.blocking_reasons),
            "required_gates": list(self.required_gates),
            "safe_config": dict(self.safe_config),
        }


@dataclass(frozen=True, slots=True)
class OpsIntegrationControlPlaneReport:
    """汇总真实集成控制面的只读状态和无副作用安全声明。"""

    generated_at: datetime
    action_mode: Literal["read_only"]
    overall_status: OpsIntegrationOverallStatus
    capabilities: list[OpsIntegrationCapability]
    safety: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        """转换为 API response 可校验的 JSON-safe 字典。"""

        return {
            "generated_at": self.generated_at,
            "action_mode": self.action_mode,
            "overall_status": self.overall_status,
            "capabilities": [capability.to_dict() for capability in self.capabilities],
            "safety": dict(self.safety),
        }


class OpsIntegrationControlPlaneService:
    """根据当前 settings 生成真实集成能力状态，不读取 secret 或调用外部系统。"""

    def __init__(self, settings: Settings, *, mineru_api_token_configured: bool) -> None:
        """保存运行配置和已脱敏的 MinerU 配置状态。"""

        self.settings = settings
        self.mineru_api_token_configured = mineru_api_token_configured

    def build_report(self) -> OpsIntegrationControlPlaneReport:
        """构建所有真实外部/破坏性能力的只读 readiness 报告。"""

        capabilities = [
            self._alert_delivery_capability(),
            self._provider_cancellation_capability(),
            self._s3_deletion_capability(),
            self._cleanup_scheduler_execute_capability(),
            self._quota_enforcement_capability(),
        ]
        return OpsIntegrationControlPlaneReport(
            generated_at=utc_now(),
            action_mode="read_only",
            overall_status=self._overall_status(capabilities),
            capabilities=capabilities,
            safety=self._safety(),
        )

    def _alert_delivery_capability(self) -> OpsIntegrationCapability:
        """返回真实 Slack/email/webhook delivery 能力状态。"""

        enabled = self.settings.integration_alert_delivery_enabled
        dry_run_only = self.settings.integration_alert_delivery_dry_run
        kill_switch = self.settings.integration_alert_delivery_kill_switch
        configured_destinations = self._configured_alert_destination_count()
        pilot_summary = self._alert_delivery_pilot_summary()
        reasons = self._base_blocking_reasons(
            enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch=kill_switch,
            disabled_reason="integration_alert_delivery_disabled",
        )
        if configured_destinations == 0:
            reasons.append("alert_destinations_not_configured")
        reasons.extend(pilot_summary["blocking_reasons"])
        return self._capability(
            capability_id="alert_delivery",
            label="Real alert delivery",
            category="external_delivery",
            enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch=kill_switch,
            configured=bool(pilot_summary["pilot_destination_ready"]),
            blocking_reasons=reasons,
            required_gates=[
                "phase7_slack_pilot_destination",
                "destination_allowlist",
                "secret_ref_resolver",
                "real_delivery_adapter",
                "rate_limit",
                "idempotency",
                "structured_audit",
            ],
            safe_config={
                "destination_count": configured_destinations,
                "adapter_contract_version": ALERT_DELIVERY_ADAPTER_CONTRACT_VERSION,
                "fake_adapter_parity": True,
                "real_delivery_adapter_implemented": True,
                "pilot_destination_id": REAL_ALERT_DELIVERY_DESTINATION_ID,
                "pilot_destination_ready": bool(pilot_summary["pilot_destination_ready"]),
                "pilot_alert_code": REAL_ALERT_DELIVERY_ALERT_CODE,
                "pilot_secret_ref": REAL_ALERT_DELIVERY_SECRET_REF,
                "pilot_target_label": REAL_ALERT_DELIVERY_TARGET_LABEL,
                "pilot_rate_limit_per_hour": REAL_ALERT_DELIVERY_RATE_LIMIT_PER_HOUR,
                "pilot_dedupe_window_minutes": REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES,
                "pilot_timeout_seconds": REAL_ALERT_DELIVERY_TIMEOUT_SECONDS,
                "pilot_confirmation_phrase": REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE,
                "secret_values_exposed": False,
            },
        )

    def _provider_cancellation_capability(self) -> OpsIntegrationCapability:
        """返回真实 provider cancellation 能力状态。"""

        enabled = self.settings.integration_provider_cancellation_enabled
        dry_run_only = self.settings.integration_provider_cancellation_dry_run
        kill_switch = self.settings.integration_provider_cancellation_kill_switch
        reasons = self._base_blocking_reasons(
            enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch=kill_switch,
            disabled_reason="integration_provider_cancellation_disabled",
        )
        reasons.extend(
            [
                "provider_cancellation_unsupported_by_public_docs",
                "real_provider_cancellation_adapter_not_implemented",
            ]
        )
        return self._capability(
            capability_id="provider_cancellation",
            label="Real provider cancellation",
            category="provider",
            enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch=kill_switch,
            configured=self.mineru_api_token_configured,
            blocking_reasons=reasons,
            required_gates=[
                "provider_semantics_verification",
                "real_provider_cancel_adapter",
                "exact_target",
                "idempotency",
                "bounded_timeout",
                "structured_audit",
            ],
            safe_config={
                "provider": "mineru",
                "mineru_api_token_configured": self.mineru_api_token_configured,
                "semantics_verification_status": PROVIDER_CANCELLATION_SEMANTICS_STATUS,
                "semantics_decision": PROVIDER_CANCELLATION_SEMANTICS_DECISION,
                "real_provider_cancel_supported": False,
                "secret_values_exposed": False,
            },
        )

    def _s3_deletion_capability(self) -> OpsIntegrationCapability:
        """返回真实 S3 deletion 能力状态。"""

        enabled = self.settings.integration_s3_deletion_enabled
        dry_run_only = self.settings.integration_s3_deletion_dry_run
        kill_switch = self.settings.integration_s3_deletion_kill_switch
        configured = self.settings.jobs_artifact_storage_backend == "s3" and bool(self.settings.jobs_artifact_s3_bucket)
        reasons = self._base_blocking_reasons(
            enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch=kill_switch,
            disabled_reason="integration_s3_deletion_disabled",
        )
        if self.settings.jobs_artifact_storage_backend != "s3":
            reasons.append("artifact_storage_backend_not_s3")
        if not self.settings.jobs_artifact_s3_bucket:
            reasons.append("s3_bucket_not_configured")
        reasons.append("localstack_contract_not_executed_in_runtime")
        reasons.append("real_s3_delete_adapter_not_implemented")
        return self._capability(
            capability_id="s3_deletion",
            label="Real S3 deletion",
            category="storage_delete",
            enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch=kill_switch,
            configured=configured,
            blocking_reasons=reasons,
            required_gates=[
                "exact_bucket_key_version",
                "signed_cleanup_plan",
                "real_s3_delete_adapter",
                "idempotency",
                "structured_audit",
                "rollback_runbook",
            ],
            safe_config={
                "artifact_storage_backend": self.settings.jobs_artifact_storage_backend,
                "s3_bucket_configured": bool(self.settings.jobs_artifact_s3_bucket),
                "s3_endpoint_configured": bool(self.settings.jobs_artifact_s3_endpoint_url),
                "s3_delete_adapter_contract_version": S3_DELETE_ADAPTER_CONTRACT_VERSION,
                "fake_file_retention_contract_version": S3_DELETE_FAKE_CONTRACT_VERSION,
                "localstack_harness": S3_DELETE_LOCALSTACK_HARNESS,
                "localstack_fake_parity_contract": True,
                "real_s3_delete_adapter_implemented": False,
                "secret_values_exposed": False,
            },
        )

    def _cleanup_scheduler_execute_capability(self) -> OpsIntegrationCapability:
        """返回自主 cleanup scheduler 执行能力状态。"""

        enabled = self.settings.integration_cleanup_scheduler_execute_enabled
        dry_run_only = self.settings.integration_cleanup_scheduler_execute_dry_run
        kill_switch = self.settings.integration_cleanup_scheduler_execute_kill_switch
        reasons = self._base_blocking_reasons(
            enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch=kill_switch,
            disabled_reason="integration_cleanup_scheduler_execute_disabled",
        )
        reasons.extend(
            [
                "cleanup_scheduler_execute_loop_not_implemented",
                "real_s3_deletion_capability_not_ready",
            ]
        )
        return self._capability(
            capability_id="cleanup_scheduler_execute",
            label="Cleanup scheduler execute",
            category="automation",
            enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch=kill_switch,
            configured=True,
            blocking_reasons=reasons,
            required_gates=[
                "distributed_lock",
                "bounded_batch",
                "signed_cleanup_plan",
                "real_delete_capability_ready",
                "history_recording",
                "rollback_runbook",
            ],
            safe_config={
                "manual_scheduler_dry_run_available": True,
                "autonomous_execute_loop_configured": False,
            },
        )

    def _quota_enforcement_capability(self) -> OpsIntegrationCapability:
        """返回 quota upload enforcement 能力状态。"""

        enabled = self.settings.files_quota_policy_enabled
        dry_run_only = self.settings.files_quota_policy_dry_run
        kill_switch = self.settings.files_quota_policy_kill_switch
        configured = self.settings.files_quota_bytes > 0 and not self._quota_config_errors()
        reasons = self._base_blocking_reasons(
            enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch=kill_switch,
            disabled_reason="files_quota_policy_disabled",
        )
        if self.settings.files_quota_bytes <= 0:
            reasons.append("files_quota_bytes_not_configured")
        reasons.extend(self._quota_config_errors())
        return self._capability(
            capability_id="quota_enforcement",
            label="Quota upload enforcement",
            category="quota",
            enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch=kill_switch,
            configured=configured,
            blocking_reasons=reasons,
            required_gates=[
                "quota_bytes",
                "thresholds",
                "admin_override",
                "structured_audit",
                "rollback_to_dry_run",
            ],
            safe_config={
                "quota_bytes": self.settings.files_quota_bytes,
                "warning_threshold_ratio": self.settings.files_quota_warning_threshold_ratio,
                "block_threshold_ratio": self.settings.files_quota_block_threshold_ratio,
                "upload_max_bytes": self.settings.jobs_upload_max_bytes,
            },
        )

    def _capability(
        self,
        *,
        capability_id: OpsIntegrationCapabilityId,
        label: str,
        category: str,
        enabled: bool,
        dry_run_only: bool,
        kill_switch: bool,
        configured: bool,
        blocking_reasons: list[str],
        required_gates: list[str],
        safe_config: dict[str, str | int | float | bool | None],
    ) -> OpsIntegrationCapability:
        """根据阻断原因计算统一 capability status。"""

        unique_reasons = self._unique(blocking_reasons)
        ready = enabled and not dry_run_only and not kill_switch and configured and not unique_reasons
        if ready:
            status: OpsIntegrationCapabilityStatus = "ready"
        elif enabled and dry_run_only and configured and not kill_switch:
            status = "dry_run_only"
        else:
            status = "blocked"
        return OpsIntegrationCapability(
            capability_id=capability_id,
            label=label,
            category=category,
            status=status,
            real_execution_enabled=enabled,
            dry_run_only=dry_run_only,
            kill_switch_active=kill_switch,
            configured=configured,
            ready=ready,
            blocking_reasons=unique_reasons,
            required_gates=required_gates,
            safe_config=safe_config,
        )

    def _base_blocking_reasons(
        self,
        *,
        enabled: bool,
        dry_run_only: bool,
        kill_switch: bool,
        disabled_reason: str,
    ) -> list[str]:
        """生成通用 enable/dry-run/kill-switch 阻断原因。"""

        reasons: list[str] = []
        if not enabled:
            reasons.append(disabled_reason)
        if dry_run_only:
            reasons.append("dry_run_only")
        if kill_switch:
            reasons.append("kill_switch_active")
        return reasons

    def _configured_alert_destination_count(self) -> int:
        """统计 staged alert destinations 数量；解析失败时返回 0 且不暴露原始配置。"""

        try:
            raw_destinations = json.loads(self.settings.ops_alert_destinations_json)
        except json.JSONDecodeError:
            return 0
        if not isinstance(raw_destinations, list):
            return 0
        return len(raw_destinations)

    def _alert_delivery_pilot_summary(self) -> dict[str, object]:
        """检查 Phase 7 Slack pilot destination 摘要，不读取 secret value。"""

        summary: dict[str, object] = {
            "pilot_destination_ready": False,
            "blocking_reasons": [],
        }
        try:
            raw_destinations = json.loads(self.settings.ops_alert_destinations_json)
        except json.JSONDecodeError:
            summary["blocking_reasons"] = ["alert_destinations_json_invalid"]
            return summary
        if not isinstance(raw_destinations, list):
            summary["blocking_reasons"] = ["alert_destinations_json_not_array"]
            return summary
        destination = next(
            (
                item
                for item in raw_destinations
                if isinstance(item, dict)
                and item.get("destination_id") == REAL_ALERT_DELIVERY_DESTINATION_ID
            ),
            None,
        )
        if destination is None:
            summary["blocking_reasons"] = ["phase7_slack_pilot_destination_not_configured"]
            return summary
        reasons: list[str] = []
        if destination.get("channel") != "slack":
            reasons.append("phase7_slack_pilot_channel_mismatch")
        if destination.get("enabled") is not True:
            reasons.append("phase7_slack_pilot_destination_disabled")
        if destination.get("secret_ref") != REAL_ALERT_DELIVERY_SECRET_REF:
            reasons.append("phase7_slack_pilot_secret_ref_mismatch")
        if destination.get("target_label") != REAL_ALERT_DELIVERY_TARGET_LABEL:
            reasons.append("phase7_slack_pilot_target_label_mismatch")
        allowlist = destination.get("allowlist")
        if not isinstance(allowlist, list) or REAL_ALERT_DELIVERY_ALERT_CODE not in allowlist:
            reasons.append("phase7_slack_pilot_alert_not_allowlisted")
        if destination.get("rate_limit_per_hour") != REAL_ALERT_DELIVERY_RATE_LIMIT_PER_HOUR:
            reasons.append("phase7_slack_pilot_rate_limit_mismatch")
        if destination.get("dedupe_window_minutes") != REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES:
            reasons.append("phase7_slack_pilot_dedupe_window_mismatch")
        summary["blocking_reasons"] = reasons
        summary["pilot_destination_ready"] = not reasons
        return summary

    def _quota_config_errors(self) -> list[str]:
        """复用 quota policy 的阈值约束，返回控制面可展示的配置错误。"""

        errors: list[str] = []
        if self.settings.files_quota_bytes <= 0:
            return errors
        if self.settings.files_quota_warning_threshold_ratio <= 0:
            errors.append("files_quota_warning_threshold_ratio_must_be_positive")
        if self.settings.files_quota_block_threshold_ratio <= 0:
            errors.append("files_quota_block_threshold_ratio_must_be_positive")
        if self.settings.files_quota_warning_threshold_ratio > self.settings.files_quota_block_threshold_ratio:
            errors.append("files_quota_warning_threshold_ratio_exceeds_block_threshold_ratio")
        return errors

    def _overall_status(self, capabilities: list[OpsIntegrationCapability]) -> OpsIntegrationOverallStatus:
        """根据 capability readiness 汇总整体状态。"""

        ready_count = sum(1 for capability in capabilities if capability.ready)
        if ready_count == 0:
            return "blocked"
        if ready_count == len(capabilities):
            return "ready"
        return "partial"

    def _safety(self) -> dict[str, bool]:
        """声明控制面只读检查没有执行任何真实副作用或暴露 secret。"""

        return {
            "read_only": True,
            "provider_calls_executed": False,
            "external_delivery_executed": False,
            "s3_delete_executed": False,
            "cleanup_scheduler_executed": False,
            "quota_enforcement_executed": False,
            "cleanup_executed": False,
            "delete_executed": False,
            "conversion_workflow_executed": False,
            "audit_events_written": False,
            "secret_values_exposed": False,
        }

    def _unique(self, values: list[str]) -> list[str]:
        """保持输入顺序去重，避免重复 blocking reason 干扰审阅。"""

        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                result.append(value)
                seen.add(value)
        return result
