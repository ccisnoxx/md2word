from __future__ import annotations

# app/services/health_service.py: 汇总后端运行时 readiness 和依赖检查状态。

import shutil
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from app.conversion.runtime import llm_client
from app.core.config import Settings
from app.domains.audit.repository import AuditEventRepositoryProtocol
from app.domains.jobs.models import JobStageMessage, utc_now
from app.domains.jobs.repository import (
    JobSnapshotRepositoryProtocol,
    StageMessageStoreProtocol,
)
from app.domains.resources.repository import ResourceVersionRepositoryProtocol
from app.api.v1.routers.health_schemas import HealthMetricsResponse, HealthReadyResponse


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
            "pdf_submission_available": pdf_submission_available,
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

        warnings: list[str] = []
        if not checks["pdf_submission_available"]:
            warnings.append("mineru_api_token_missing")
            checks["pdf_submission_unavailable_reason"] = "MINERU_API_TOKEN 未配置"
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
