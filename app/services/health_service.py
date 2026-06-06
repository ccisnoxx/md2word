# File: app/services/health_service.py
# Purpose: Aggregate backend readiness, metrics, and read-only operations alert signals.

from __future__ import annotations

import shutil
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from app.api.v1.routers.health_schemas import (
    HealthMetricsResponse,
    HealthOpsAlertItem,
    HealthOpsAlertsResponse,
    HealthOpsAlertSafety,
    HealthOpsAlertSummary,
    HealthReadyResponse,
)
from app.conversion.runtime import llm_client
from app.core.config import Settings
from app.domains.audit.repository import AuditEventRepositoryProtocol
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.jobs.models import JobStageMessage, utc_now
from app.domains.jobs.repository import (
    JobSnapshotRepositoryProtocol,
    StageMessageStoreProtocol,
)
from app.domains.resources.repository import ResourceVersionRepositoryProtocol


DEFAULT_TERM_RULE_SET_ID = "electronics-default"
DEFAULT_TRANSLATION_PROFILE_ID = "electronics-en2zh"
RESOURCE_TYPES = ("template", "term_rule_set", "translation_profile")


READINESS_REQUIRED_CHECKS = (
    "jobs_dir_exists",
    "jobs_dir_writable",
    "stage_spool_dir_exists",
    "tmp_dir_exists",
    "template_docx_exists",
    "layout_config_exists",
    "subscript_config_exists",
)

READINESS_NON_BLOCKING_CHECKS = (
    "mineru_api_token_configured",
    "pdf_submission_available",
    "translation_available",
    "stage_spool_replayable_messages",
    "stage_spool_failed_messages",
    "stage_spool_running_stale_messages",
    "stage_spool_needs_attention",
)


class HealthService:
    """汇总运行时只读健康、metrics 和运维告警 readiness。"""

    def __init__(
        self,
        settings: Settings,
        stage_message_store: StageMessageStoreProtocol,
        *,
        effective_repository_backend: Literal["file", "database", "mysql"] = "file",
        stage_message_store_backend: Literal["file", "database", "mysql"] = "file",
        artifact_storage_backend: str = "local_file",
        stage_dispatcher_backend: Literal["background_tasks", "external_worker"] = "background_tasks",
        job_repository: JobSnapshotRepositoryProtocol | None = None,
        document_job_repository: DocumentJobRepositoryProtocol | None = None,
        audit_event_repository: AuditEventRepositoryProtocol | None = None,
        resource_version_repository: ResourceVersionRepositoryProtocol | None = None,
        default_template_id_getter: Callable[[], str] | None = None,
    ) -> None:
        self.settings = settings
        self.stage_message_store = stage_message_store
        self.effective_repository_backend = effective_repository_backend
        self.stage_message_store_backend = stage_message_store_backend
        self.artifact_storage_backend = artifact_storage_backend
        self.stage_dispatcher_backend = stage_dispatcher_backend
        self.job_repository = job_repository
        self.document_job_repository = document_job_repository
        self.audit_event_repository = audit_event_repository
        self.resource_version_repository = resource_version_repository
        self.default_template_id_getter = default_template_id_getter

    def _is_writable(self, path: Path | None = None) -> bool:
        target = path or self.settings.data_path
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write_probe"
        try:
            probe.write_text("ok", encoding="utf-8")
        except OSError:
            return False
        probe.unlink(missing_ok=True)
        return True

    def build_dependency_checks(self) -> dict[str, Any]:
        template_path = self.settings.default_template_path
        layout_config_path = self.settings.layout_config_path
        subscript_config_path = self.settings.subscript_config_path
        translation_prompt_exists = llm_client.SYSTEM_PROMPT_PATH.exists()
        stage_spool_counts = self.stage_message_store.count_stage_messages_by_status()
        running_observation = self._build_running_stage_observation()
        translation_client_configured = bool(self.settings.openai_api_key) and llm_client.OpenAI is not None
        stage_spool_available = self.stage_message_store_backend in {"database", "mysql"} or self.settings.stage_messages_dir.exists()
        stage_spool_replayable_messages = (
            stage_spool_counts.get("pending", 0)
            + stage_spool_counts.get("running", 0)
        )
        stage_spool_needs_attention = (
            stage_spool_counts.get("failed", 0) > 0
            or running_observation["stale_count"] > 0
        )
        pdf_submission_available = bool(self.settings.mineru_api_token)
        artifact_root = self._artifact_root()
        resource_labels = self._build_default_resource_labels()
        mineru_callback_url_configured = bool(self.settings.mineru_callback_url)
        mineru_uid_configured = bool(self.settings.mineru_uid)

        checks: dict[str, Any] = {
            "readiness_required_checks": list(READINESS_REQUIRED_CHECKS),
            "readiness_non_blocking_checks": list(READINESS_NON_BLOCKING_CHECKS),
            "configured_repository_backend": self.settings.jobs_repository_backend,
            "effective_repository_backend": self.effective_repository_backend,
            "worker_mode": self.settings.jobs_worker_mode,
            "stage_dispatcher": self.stage_dispatcher_backend,
            "stage_message_store": self.stage_message_store_backend,
            "artifact_storage": self.artifact_storage_backend,
            "jobs_dir_exists": self.settings.jobs_dir.exists(),
            "jobs_dir_writable": self._is_writable(),
            "artifact_root_writable": self._is_writable(artifact_root),
            "artifact_disk_free_bytes": self._disk_free_bytes(artifact_root),
            "stage_spool_dir_exists": stage_spool_available,
            "stage_spool_pending_messages": stage_spool_counts.get("pending", 0),
            "stage_spool_running_messages": stage_spool_counts.get("running", 0),
            "stage_spool_failed_messages": stage_spool_counts.get("failed", 0),
            "stage_spool_replayable_messages": stage_spool_replayable_messages,
            "stage_spool_running_stale_messages": running_observation["stale_count"],
            "stage_spool_oldest_running_age_seconds": running_observation["oldest_age_seconds"],
            "stage_spool_needs_attention": stage_spool_needs_attention,
            "stage_spool_observation_status": self._build_stage_spool_observation_status(
                replayable_count=stage_spool_replayable_messages,
                needs_attention=stage_spool_needs_attention,
            ),
            "tmp_dir_exists": self.settings.tmp_dir.exists(),
            "template_docx_exists": template_path is not None and template_path.exists(),
            "layout_config_exists": layout_config_path is not None and layout_config_path.exists(),
            "subscript_config_exists": subscript_config_path is not None and subscript_config_path.exists(),
            "translation_prompt_exists": translation_prompt_exists,
            "mineru_api_token_configured": bool(self.settings.mineru_api_token),
            "mineru_callback_url_configured": mineru_callback_url_configured,
            "mineru_uid_configured": mineru_uid_configured,
            "pdf_submission_available": pdf_submission_available,
            "public_deployment_mode": self.settings.public_deployment_mode,
            "openai_api_key_configured": bool(self.settings.openai_api_key),
            "openai_base_url_configured": bool(self.settings.openai_base_url),
            "openai_model": self.settings.openai_model,
            "default_translation_mode": self.settings.default_translation_mode,
            "translation_required_for_default_mode": self.settings.default_translation_mode == "en2zh",
            "translation_client_configured": translation_client_configured,
            "translation_available": translation_client_configured and translation_prompt_exists,
            "default_template_version": resource_labels["template"],
            "default_term_rule_version": resource_labels["term_rule_set"],
            "default_translation_profile_version": resource_labels["translation_profile"],
            "mysql_schema_bootstrap_available": self.effective_repository_backend == "mysql",
        }

        blockers: list[str] = []
        if not checks["jobs_dir_exists"]:
            blockers.append("jobs_dir_missing")
        if not checks["jobs_dir_writable"]:
            blockers.append("data_dir_not_writable")
        if self.stage_message_store_backend == "file" and not checks["stage_spool_dir_exists"]:
            blockers.append("stage_spool_dir_missing")
        if not checks["tmp_dir_exists"]:
            blockers.append("tmp_dir_missing")
        if not checks["template_docx_exists"]:
            blockers.append("default_template_missing")
        if not checks["layout_config_exists"]:
            blockers.append("layout_config_missing")
        if not checks["subscript_config_exists"]:
            blockers.append("subscript_config_missing")
        if checks["translation_required_for_default_mode"] and not checks["translation_available"]:
            blockers.append("default_translation_unavailable")
        if mineru_callback_url_configured and not mineru_uid_configured:
            blockers.append("mineru_uid_missing")

        warnings: list[str] = []
        if not checks["pdf_submission_available"]:
            warnings.append("mineru_api_token_missing")
            checks["pdf_submission_unavailable_reason"] = "MINERU_API_TOKEN 未配置"
        if checks["pdf_submission_available"] and not mineru_callback_url_configured:
            warnings.append("mineru_callback_url_missing")
        if not checks["translation_available"] and not checks["translation_required_for_default_mode"]:
            warnings.append("translation_unavailable")
        if stage_spool_replayable_messages > 0:
            warnings.append("stage_spool_replayable_messages_present")
        if stage_spool_counts.get("failed", 0) > 0:
            warnings.append("stage_spool_failed_messages_present")
        if running_observation["stale_count"] > 0:
            warnings.append("stage_spool_stale_running_messages_present")

        checks["deployment_init_ready"] = not blockers
        checks["deployment_init_missing_steps"] = blockers
        checks["readiness_blockers"] = blockers
        checks["readiness_warnings"] = warnings
        if not checks["translation_available"]:
            if not checks["openai_api_key_configured"]:
                checks["translation_unavailable_reason"] = "OPENAI_API_KEY 未配置"
            elif llm_client.OpenAI is None:
                checks["translation_unavailable_reason"] = "openai Python SDK 不可用"
            elif not checks["translation_prompt_exists"]:
                checks["translation_unavailable_reason"] = "translation_en2zh prompt 文件缺失"
        return checks

    def build_ops_alerts_response(self) -> HealthOpsAlertsResponse:
        """生成 Admin-only 只读运维告警 readiness 响应。"""

        checks = self.build_dependency_checks()
        document_job_counts = self._build_document_job_status_counts()
        summary = self._build_ops_alert_summary(checks, document_job_counts)
        alerts = self._build_ops_alert_items(checks, document_job_counts)
        return HealthOpsAlertsResponse(
            status=self._build_ops_alert_status(alerts),
            app_name=self.settings.app_name,
            generated_at=utc_now(),
            summary=summary,
            alerts=alerts,
            safety=HealthOpsAlertSafety(),
        )

    def build_metrics_response(self) -> HealthMetricsResponse:
        stage_spool_counts = self.stage_message_store.count_stage_messages_by_status()
        resource_counts = self._build_resource_version_counts()
        resource_labels = self._build_default_resource_labels()
        resources: dict[str, int | str | None] = {
            "template_versions": resource_counts["template"],
            "term_rule_set_versions": resource_counts["term_rule_set"],
            "translation_profile_versions": resource_counts["translation_profile"],
            "default_template_version": resource_labels["template"],
            "default_term_rule_version": resource_labels["term_rule_set"],
            "default_translation_profile_version": resource_labels["translation_profile"],
        }
        return HealthMetricsResponse(
            status="ok",
            app_name=self.settings.app_name,
            generated_at=utc_now(),
            metadata_store=self.effective_repository_backend,
            artifact_storage=self.artifact_storage_backend,
            worker_mode=self.settings.jobs_worker_mode,
            stage_dispatcher=self.stage_dispatcher_backend,
            jobs=self._build_job_status_counts(),
            stage_messages=stage_spool_counts,
            resources=resources,
            audit_events={"total": self._count_audit_events()},
        )

    def _build_ops_alert_summary(
        self,
        checks: dict[str, Any],
        document_job_counts: dict[str, int],
    ) -> HealthOpsAlertSummary:
        """把 readiness、stage spool 和 document_jobs 计数收敛成稳定摘要。"""

        return HealthOpsAlertSummary(
            readiness_blockers=len(self._string_list_check(checks, "readiness_blockers")),
            readiness_warnings=len(self._string_list_check(checks, "readiness_warnings")),
            stage_failed_messages=self._int_check(checks, "stage_spool_failed_messages"),
            stage_stale_running_messages=self._int_check(checks, "stage_spool_running_stale_messages"),
            stage_replayable_messages=self._int_check(checks, "stage_spool_replayable_messages"),
            failed_jobs=document_job_counts.get("failed", 0),
            running_jobs=document_job_counts.get("running", 0),
            worker_mode=str(checks.get("worker_mode") or self.settings.jobs_worker_mode),
            stage_dispatcher=str(checks.get("stage_dispatcher") or self.stage_dispatcher_backend),
            stage_message_store=str(checks.get("stage_message_store") or self.stage_message_store_backend),
            artifact_storage=str(checks.get("artifact_storage") or self.artifact_storage_backend),
        )

    def _build_ops_alert_items(
        self,
        checks: dict[str, Any],
        document_job_counts: dict[str, int],
    ) -> list[HealthOpsAlertItem]:
        """根据只读计数生成告警项，不执行任何恢复动作。"""

        alerts: list[HealthOpsAlertItem] = []
        blockers = self._string_list_check(checks, "readiness_blockers")
        warnings = self._string_list_check(checks, "readiness_warnings")
        stage_failed_count = self._int_check(checks, "stage_spool_failed_messages")
        stage_stale_count = self._int_check(checks, "stage_spool_running_stale_messages")
        stage_replayable_count = self._int_check(checks, "stage_spool_replayable_messages")
        failed_jobs = document_job_counts.get("failed", 0)
        running_jobs = document_job_counts.get("running", 0)

        if blockers:
            alerts.append(
                HealthOpsAlertItem(
                    code="readiness_blockers_present",
                    severity="critical",
                    source="readiness",
                    title="Readiness blockers present",
                    description="、".join(blockers),
                    count=len(blockers),
                    suggested_route="/system-status",
                    suggested_action="查看系统状态中的 blockers，并按部署修复流程处理缺失依赖。",
                )
            )
        if warnings:
            alerts.append(
                HealthOpsAlertItem(
                    code="readiness_warnings_present",
                    severity="warning",
                    source="readiness",
                    title="Readiness warnings present",
                    description="、".join(warnings),
                    count=len(warnings),
                    suggested_route="/system-status",
                    suggested_action="查看 readiness 详情；warning 只提示风险，不在此接口触发修复动作。",
                )
            )
        if stage_failed_count > 0:
            alerts.append(
                HealthOpsAlertItem(
                    code="stage_spool_failed_messages_present",
                    severity="critical",
                    source="stage_spool",
                    title="Failed stage messages present",
                    description="failed stage message 不会自动 replay，需要结合任务详情和事件流判断下一步。",
                    count=stage_failed_count,
                    suggested_route="/jobs?status=failed&sort=updated_at_desc",
                    suggested_action="查看失败任务和事件；如需 retry，使用既有任务流程手动处理。",
                )
            )
        if stage_stale_count > 0:
            alerts.append(
                HealthOpsAlertItem(
                    code="stage_spool_stale_running_messages_present",
                    severity="critical",
                    source="stage_spool",
                    title="Stale running stage messages present",
                    description="running stage message 已超过 lease 观察窗口，可能来自 worker 退出或处理卡住。",
                    count=stage_stale_count,
                    suggested_route="/jobs?status=running&sort=updated_at_desc",
                    suggested_action="先确认 worker 进程和任务事件，再按既有运维流程处理。",
                )
            )
        if stage_replayable_count > 0:
            alerts.append(
                HealthOpsAlertItem(
                    code="stage_spool_replayable_messages_present",
                    severity="warning",
                    source="stage_spool",
                    title="Replayable stage messages present",
                    description="pending/running stage message 属于可观察的 replayable 信号，可能随 worker 恢复继续处理。",
                    count=stage_replayable_count,
                    suggested_route="/jobs?status=running&sort=updated_at_desc",
                    suggested_action="观察 worker 和任务事件进展；本接口不会启动 replay。",
                )
            )
        if failed_jobs > 0:
            alerts.append(
                HealthOpsAlertItem(
                    code="document_jobs_failed_present",
                    severity="warning",
                    source="jobs",
                    title="Failed document jobs present",
                    description="存在失败 document job，应从任务详情查看错误阶段、事件流和文件区。",
                    count=failed_jobs,
                    suggested_route="/jobs?status=failed&sort=updated_at_desc",
                    suggested_action="如需重试，使用既有任务页面流程手动执行。",
                )
            )
        if running_jobs > 0:
            alerts.append(
                HealthOpsAlertItem(
                    code="document_jobs_running_present",
                    severity="info",
                    source="jobs",
                    title="Running document jobs present",
                    description="存在运行中 document job；该信号用于观察，不代表需要人工干预。",
                    count=running_jobs,
                    suggested_route="/jobs?status=running&sort=updated_at_desc",
                    suggested_action="查看运行中任务样例和事件进展；本接口不取消或恢复任务。",
                )
            )
        return alerts

    @staticmethod
    def _build_ops_alert_status(alerts: list[HealthOpsAlertItem]) -> str:
        """按告警最高严重级别生成整体运维状态。"""

        if any(alert.severity == "critical" for alert in alerts):
            return "needs_attention"
        if alerts:
            return "watch"
        return "ok"

    def _artifact_root(self) -> Path:
        if self.artifact_storage_backend == "local_object":
            return self.settings.jobs_artifact_object_store_dir
        return self.settings.jobs_dir

    @staticmethod
    def _disk_free_bytes(path: Path) -> int:
        probe = path if path.exists() else path.parent
        try:
            return shutil.disk_usage(probe).free
        except OSError:
            return 0

    def _build_job_status_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        if self.job_repository is None:
            return {}
        for job in self.job_repository.list_jobs():
            counts[job.status] += 1
        return dict(sorted(counts.items()))

    def _build_document_job_status_counts(self) -> dict[str, int]:
        """统计未归档 document_jobs 的状态，匹配运维看板只读列表语义。"""

        counts: Counter[str] = Counter()
        if self.document_job_repository is None:
            return {}
        for job in self.document_job_repository.list_document_jobs():
            if job.archived_at is None:
                counts[job.status] += 1
        return dict(sorted(counts.items()))

    def _count_audit_events(self) -> int:
        if self.audit_event_repository is None:
            return 0
        return len(self.audit_event_repository.list_audit_events())

    def _build_resource_version_counts(self) -> dict[str, int]:
        counts = {resource_type: 0 for resource_type in RESOURCE_TYPES}
        repository = self.resource_version_repository
        if repository is None:
            return counts
        count_method = getattr(repository, "count_resource_versions_by_type", None)
        if callable(count_method):
            counts.update({key: int(value) for key, value in count_method().items() if key in counts})
            return counts
        for resource_type, resource_id in self._known_resource_ids().items():
            counts[resource_type] = len(repository.list_resource_versions(resource_type, resource_id))
        return counts

    def _build_default_resource_labels(self) -> dict[str, str | None]:
        labels = {resource_type: None for resource_type in RESOURCE_TYPES}
        repository = self.resource_version_repository
        if repository is None:
            return labels
        for resource_type, resource_id in self._known_resource_ids().items():
            record = repository.get_default_resource_version(resource_type, resource_id)
            if record is not None:
                labels[resource_type] = f"{record.resource_id}@{record.version}"
        return labels

    def _known_resource_ids(self) -> dict[str, str]:
        template_id = self.settings.default_template_id
        if self.default_template_id_getter is not None:
            try:
                template_id = self.default_template_id_getter()
            except Exception:
                template_id = self.settings.default_template_id
        return {
            "template": template_id,
            "term_rule_set": DEFAULT_TERM_RULE_SET_ID,
            "translation_profile": DEFAULT_TRANSLATION_PROFILE_ID,
        }

    @staticmethod
    def _string_list_check(checks: dict[str, Any], key: str) -> list[str]:
        """从 readiness checks 中安全读取字符串列表字段。"""

        value = checks.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str) and item.strip()]
        if isinstance(value, str) and value.strip():
            return [value]
        return []

    @staticmethod
    def _int_check(checks: dict[str, Any], key: str) -> int:
        """从 readiness checks 中安全读取非负整数计数字段。"""

        value = checks.get(key)
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return max(0, value)
        return 0

    def _build_running_stage_observation(self) -> dict[str, int]:
        """汇总 running stage message 中已过 lease 的数量和最老运行时长。"""

        now = utc_now()
        stale_count = 0
        oldest_age_seconds = 0
        for message in self.stage_message_store.list_replayable_stage_messages():
            if message.status != "running":
                continue
            age_seconds = max(0, int((now - message.updated_at).total_seconds()))
            oldest_age_seconds = max(oldest_age_seconds, age_seconds)
            if self._is_running_stage_stale(message):
                stale_count += 1
        return {
            "stale_count": stale_count,
            "oldest_age_seconds": oldest_age_seconds,
        }

    @staticmethod
    def _build_stage_spool_observation_status(*, replayable_count: int, needs_attention: bool) -> str:
        if needs_attention:
            return "needs_attention"
        if replayable_count > 0:
            return "replayable"
        return "ok"

    def _is_running_stage_stale(self, message: JobStageMessage) -> bool:
        now = utc_now()
        if message.lease_expires_at is not None:
            return message.lease_expires_at <= now
        return (now - message.updated_at).total_seconds() >= self.settings.stage_message_lease_seconds

    def build_ready_response(self) -> HealthReadyResponse:
        return HealthReadyResponse(
            status="ok",
            app_name=self.settings.app_name,
            jobs_dir=str(self.settings.jobs_dir),
            dependency_checks=self.build_dependency_checks(),
        )
