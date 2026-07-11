# 文件：tests/test_fastapi_jobs_backend.py
# 用途：覆盖 FastAPI jobs/files API、ops governance、workflow 和 artifact 合同。

import ast
import csv
import io
import json
import hashlib
import sys
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable
from unittest import TestCase
from unittest.mock import patch

import yaml

VENDOR_DIR = Path(__file__).resolve().parents[1] / ".python_packages"
if VENDOR_DIR.exists():
    vendor_path = str(VENDOR_DIR)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)

from fastapi.testclient import TestClient
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.conversion.contracts import ArtifactDescriptor, ConversionFailure, ConversionResult
from app.core.config import Settings
from app.domains.jobs.models import JobFile, JobRecord, JobStageMessage, SourcePdfJobContext, build_source_pdf_context_patch, utc_now
from app.domains.jobs.workflow import JobWorkflowViolation
from app.domains.jobs.paths import build_job_paths, ensure_job_dirs
from app.core.runtime import AppRuntime
from app.infrastructure.persistence import (
    PersistenceAdapters,
    build_file_persistence_adapters,
    build_mysql_persistence_adapters,
    build_sqlite_persistence_adapters,
)
from app.infrastructure.persistence.mysql import MysqlPersistenceConfig
from app.main import build_runtime, create_app
from app.domains.term_rules.file_repository import FileTermRuleRepository
from app.domains.acceptance.service import AcceptanceRunService
from app.domains.audit.models import AuditEvent
from app.domains.audit.service import AuditService
from app.domains.document_jobs.models import DocumentJobCallbackMessage, DocumentJobRecord
from app.services.auth import AuthService, hash_password
from app.domains.users.service import InternalUserManagementService
from app.domains.document_jobs.execution import (
    DocumentJobExecutionService,
    EagerDocumentJobTaskQueue,
    EagerDocumentTranslationBatchTaskQueue,
)
from app.domains.document_jobs.incidents import DocumentJobIncidentService
from app.domains.document_jobs.recovery import DocumentJobRecoveryService
from app.domains.document_jobs.service import DocumentJobService
from app.domains.saved_views.service import SavedViewService
from app.services.document_ir import MinerUToDocumentIRService
from app.domains.files import FileRetentionPolicyService, FileUploadService
from app.domains.files.cleanup_lock import FileRetentionCleanupLockService
from app.domains.files.models import DocumentFileRecord
from app.services.health_service import HealthService
from app.domains.jobs.artifact_integrity import ArtifactFingerprintMismatch
from app.domains.jobs.artifact_storage import DownloadArtifact, LocalArtifactStorageAdapter
from app.domains.jobs.artifacts import JobArtifactService
from app.domains.jobs.command import JobCommandService
from app.domains.jobs.dispatch import ExternalWorkerStageDispatcher, InProcessStageDispatcher
from app.domains.jobs.lifecycle import JobLifecycleService
from app.domains.jobs.object_artifact_storage import ObjectArtifactStorageAdapter
from app.domains.jobs.resource_snapshots import JobResourceSnapshotService
from app.domains.jobs.query import JobQueryService
from app.domains.jobs.stage import JobStageService
from app.api.mineru_callback_guards import verify_mineru_callback_checksum_for_job
from app.domains.mineru.config import MinerUConfigError, MinerUConfigService
from app.domains.ops.real_alert_delivery import RealAlertDeliveryProviderResult
from app.services.renderer import DocumentIRWordRenderer
from app.domains.resources.service import ResourceVersionService
from app.domains.term_rules.bootstrap import TermRuleBootstrapService
from app.domains.term_rules.import_validation import TermRuleImportValidationService
from app.domains.term_rules.models import TermRuleCategoryRecord, TermRulesStore
from app.domains.term_rules.proposals_service import TermRuleProposalService
from app.domains.term_rules.service import TermRuleService
from app.domains.term_rules.sync_files import TermRuleFileSyncService
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID, TermRuleSetVersionService
from app.domains.term_rules.yaml_codec import CURRENT_SCHEMA_VERSION, TermRuleYamlCodec
from app.domains.templates.read_service import TemplateReadService
from app.domains.translation.audit import TranslationAuditService
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.domains.translation.models import TranslationTermEntry, TranslationTermProposalChangeRecord
from app.domains.translation.modes import derive_translation_term_set_id
from app.domains.translation.provider_config import AiProviderConfigService
from app.domains.translation.profiles_service import DEFAULT_TRANSLATION_PROFILE_ID, TranslationProfileVersionService
from app.domains.translation.proposals_service import TranslationTermProposalService
from app.domains.translation.provider import TranslationProviderResponseError, build_translation_provider
from app.domains.translation.term_set_version_service import TranslationTermSetVersionService
from app.domains.translation.term_version_service import TermVersionService
from app.workers.stage_worker import StageWorker


MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeMinerUClient:
    def __init__(self) -> None:
        self.calls = []
        self.raise_error = False
        self.download_calls = []
        self.raise_download_error = False
        self.query_calls = []
        self.query_data_id = None
        self.query_state = "done"
        self.query_full_zip_url = "https://mineru.net/result.zip"
        self.result_zip_bytes: bytes | None = None

    def upload_files_batch(
        self,
        file_paths,
        *,
        task_uuids=None,
        enable_formula=True,
        enable_table=True,
        language="en",
        callback=None,
        seed=None,
    ):
        if self.raise_error:
            raise RuntimeError("mineru boom")
        self.calls.append(
            {
                "file_paths": [str(path) for path in file_paths],
                "task_uuids": task_uuids,
                "enable_formula": enable_formula,
                "enable_table": enable_table,
                "language": language,
                "callback": callback,
                "seed": seed,
            }
        )
        return "batch_test_001", ["https://example.com/upload"]

    def download_result_zip(self, result_url, output_path):
        if self.raise_download_error:
            raise RuntimeError("mineru download boom")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self.result_zip_bytes or b"fake-parsed-result-zip")
        self.download_calls.append({"result_url": result_url, "output_path": str(output_path)})
        return output_path

    def query_batch_extract_results(self, batch_id):
        self.query_calls.append({"batch_id": batch_id})
        item = {
            "data_id": self.query_data_id,
            "state": self.query_state,
        }
        if self.query_full_zip_url:
            item["full_zip_url"] = self.query_full_zip_url
        return {
            "batch_id": batch_id,
            "extract_result": [item],
        }


class FakeConversionService:
    def __init__(self) -> None:
        self.requests = []
        self.raise_error = False

    def convert(self, request):
        if self.raise_error:
            raise ConversionFailure("conversion_failed", "boom")
        self.requests.append(request)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"fake-docx")
        artifacts = [ArtifactDescriptor(file_type="result_docx", path=request.output_path)]
        if request.translation_request_output is not None:
            request.translation_request_output.parent.mkdir(parents=True, exist_ok=True)
            request.translation_request_output.write_text(
                json.dumps({"items": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            artifacts.append(
                ArtifactDescriptor(
                    file_type="translation_request",
                    path=request.translation_request_output,
                    )
            )
        if request.translation_trace_output is not None:
            request.translation_trace_output.parent.mkdir(parents=True, exist_ok=True)
            request.translation_trace_output.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "job_id": request.job_id,
                        "translation_profile": (
                            {
                                "translation_profile_id": request.translation_profile.translation_profile_id,
                                "language_pair": request.translation_profile.language_pair,
                                "version": request.translation_profile.version,
                                "snapshot_hash": request.translation_profile.snapshot_hash,
                            }
                            if request.translation_profile is not None
                            else None
                        ),
                        "segments": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            artifacts.append(
                ArtifactDescriptor(
                    file_type="translation_trace",
                    path=request.translation_trace_output,
                )
            )
        return ConversionResult(
            source_path=request.package_path,
            output_docx_path=request.output_path,
            pages=2,
            document_language="zh",
            artifacts=artifacts,
        )


class FakeDocumentJobTranslationProvider:
    def __init__(self, *, raise_error: bool = False) -> None:
        self.raise_error = raise_error
        self.requests = []

    def translate(self, request):
        self.requests.append(request)
        if self.raise_error:
            raise RuntimeError("provider unavailable")
        translations = {
            "block_0001.text": "1 特性",
            "block_0002.text": "输入失调电压很低。",
            "block_0003.text": "电气特性",
            "block_0003.html.0000": "参数",
            "block_0003.html.0001": "输入电压",
            "block_0004.text": "图 1. 引脚图",
            "block_0005.list_items.0000": "低噪声",
            "block_0005.list_items.0001": "高压摆率",
        }
        from app.domains.translation.models import TranslationProviderResult, TranslationTextItem

        return TranslationProviderResult(
            items=tuple(
                TranslationTextItem(id=item.id, text=translations.get(item.id, f"译文:{item.text}"))
                for item in request.items
            )
        )


class TruncatingOnceDocumentJobTranslationProvider(FakeDocumentJobTranslationProvider):
    def __init__(self) -> None:
        super().__init__(raise_error=False)
        self.truncated_once = False

    def translate(self, request):
        if not self.truncated_once and len(request.items) > 1:
            self.requests.append(request)
            self.truncated_once = True
            raise TranslationProviderResponseError(
                "provider returned incomplete JSON",
                finish_reason="length",
                usage={"completion_tokens": 8192},
                response_id="resp_truncated_once",
                content='{"items": [',
                suspected_truncation=True,
            )
        return super().translate(request)


class FakeAlertDeliveryProvider:
    """记录 Phase 7 alert delivery provider 调用，避免测试触发真实 Slack webhook。"""

    def __init__(self, *, outcome: str = "sent") -> None:
        self.outcome = outcome
        self.calls = []

    def send(self, attempt):
        """返回脱敏 provider 结果，并保留调用摘要供测试断言。"""

        self.calls.append(
            {
                "destination_id": attempt.destination_id,
                "alert_code": attempt.alert_code,
                "webhook_url": attempt.webhook_url,
                "idempotency_key": attempt.idempotency_key,
            }
        )
        return RealAlertDeliveryProviderResult(
            outcome=self.outcome,
            provider_request_id="fake-slack-request-001",
            error_code=None if self.outcome == "sent" else "fake_failure",
            retryable=self.outcome != "sent",
            provider_calls_executed=True,
            external_delivery_executed=self.outcome == "sent",
        )


class FakeSecretResolver:
    """按测试提供的映射返回 secret value，并记录解析次数。"""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}
        self.calls = []

    def resolve_secret(self, secret_ref: str) -> str | None:
        """记录 secret ref 查询；不把 secret value 写到外部输出。"""

        self.calls.append(secret_ref)
        return self.values.get(secret_ref)


def build_test_runtime(
    data_dir: Path,
    *,
    repository_factory: Callable[[Path], PersistenceAdapters] | None = None,
    app_env: str = "dev",
    app_version: str = "dev",
    deployment_id: str = "",
    jobs_repository_backend: str = "file",
    jobs_artifact_storage_backend: str = "local_file",
    jobs_worker_mode: str = "in_process",
    openai_api_key: str = "",
    translation_provider_backend: str = "disabled",
    mineru_api_token: str = "",
    public_deployment_mode: str = "internal",
    mineru_callback_url: str = "",
    mineru_uid: str = "",
    mineru_result_host_allowlist: str = "mineru.net,cdn-mineru.openxlab.org.cn",
    jobs_access_mode: str = "open",
    jobs_access_token: str = "",
    jobs_ops_access_mode: str = "admin",
    admin_token: str = "",
    jobs_artifact_s3_bucket: str = "",
    jobs_artifact_s3_endpoint_url: str = "",
    jobs_artifact_s3_region: str = "us-east-1",
    jobs_artifact_s3_access_key_id: str = "",
    jobs_artifact_s3_secret_access_key: str = "",
    jobs_artifact_s3_key_prefix: str = "",
    ops_alert_destinations_json: str = "[]",
    integration_alert_delivery_enabled: bool = False,
    integration_alert_delivery_dry_run: bool = True,
    integration_alert_delivery_kill_switch: bool = False,
    integration_provider_cancellation_enabled: bool = False,
    integration_provider_cancellation_dry_run: bool = True,
    integration_provider_cancellation_kill_switch: bool = False,
    integration_s3_deletion_enabled: bool = False,
    integration_s3_deletion_dry_run: bool = True,
    integration_s3_deletion_kill_switch: bool = False,
    integration_cleanup_scheduler_execute_enabled: bool = False,
    integration_cleanup_scheduler_execute_dry_run: bool = True,
    integration_cleanup_scheduler_execute_kill_switch: bool = False,
    auth_jwt_secret_key: str = "",
    auth_access_token_expire_minutes: int = 120,
    auth_internal_users_file: str = "",
    auth_internal_users_json: str = "",
    jobs_upload_max_bytes: int = 52_428_800,
    files_quota_policy_enabled: bool = False,
    files_quota_policy_dry_run: bool = True,
    files_quota_bytes: int = 0,
    files_quota_warning_threshold_ratio: float = 0.8,
    files_quota_block_threshold_ratio: float = 1.0,
    pdf_upload_max_pages: int = 200,
    p0_document_job_timeout_seconds: int = 1200,
    p0_document_job_max_retries: int = 2,
    default_translation_mode: str = "direct",
    document_jobs_worker_backend: str = "disabled",
    document_jobs_celery_broker_url: str = "redis://127.0.0.1:6379/0",
    document_jobs_celery_result_backend: str = "",
    document_jobs_celery_queue: str = "document-jobs",
    document_jobs_translation_batch_celery_queue: str = "document-translation-batches",
    translation_debug_archive_enabled: bool = False,
    translation_debug_archive_retention_days: int = 1,
    templates_manifest_path: str | None = None,
    term_rules_seed_path: str | None = None,
    translation_terms_path: str | None = None,
    alert_delivery_provider: Any | None = None,
    secret_resolver: Any | None = None,
) -> AppRuntime:
    """构建隔离测试运行时，使用 fake adapter 避免触发真实外部 provider。"""

    settings = Settings(
        _env_file=None,
        data_dir=str(data_dir),
        app_name="md2word_file_test",
        app_env=app_env,
        app_version=app_version,
        deployment_id=deployment_id,
        jobs_repository_backend=jobs_repository_backend,
        jobs_artifact_storage_backend=jobs_artifact_storage_backend,
        jobs_worker_mode=jobs_worker_mode,
        openai_api_key=openai_api_key,
        openai_base_url="",
        openai_model="deepseek-v4-flash",
        translation_provider_backend=translation_provider_backend,
        mineru_api_token=mineru_api_token,
        public_deployment_mode=public_deployment_mode,
        mineru_callback_url=mineru_callback_url,
        mineru_uid=mineru_uid,
        mineru_result_host_allowlist=mineru_result_host_allowlist,
        jobs_access_mode=jobs_access_mode,
        jobs_access_token=jobs_access_token,
        jobs_ops_access_mode=jobs_ops_access_mode,
        admin_token=admin_token,
        jobs_artifact_s3_bucket=jobs_artifact_s3_bucket,
        jobs_artifact_s3_endpoint_url=jobs_artifact_s3_endpoint_url,
        jobs_artifact_s3_region=jobs_artifact_s3_region,
        jobs_artifact_s3_access_key_id=jobs_artifact_s3_access_key_id,
        jobs_artifact_s3_secret_access_key=jobs_artifact_s3_secret_access_key,
        jobs_artifact_s3_key_prefix=jobs_artifact_s3_key_prefix,
        ops_alert_destinations_json=ops_alert_destinations_json,
        integration_alert_delivery_enabled=integration_alert_delivery_enabled,
        integration_alert_delivery_dry_run=integration_alert_delivery_dry_run,
        integration_alert_delivery_kill_switch=integration_alert_delivery_kill_switch,
        integration_provider_cancellation_enabled=integration_provider_cancellation_enabled,
        integration_provider_cancellation_dry_run=integration_provider_cancellation_dry_run,
        integration_provider_cancellation_kill_switch=integration_provider_cancellation_kill_switch,
        integration_s3_deletion_enabled=integration_s3_deletion_enabled,
        integration_s3_deletion_dry_run=integration_s3_deletion_dry_run,
        integration_s3_deletion_kill_switch=integration_s3_deletion_kill_switch,
        integration_cleanup_scheduler_execute_enabled=integration_cleanup_scheduler_execute_enabled,
        integration_cleanup_scheduler_execute_dry_run=integration_cleanup_scheduler_execute_dry_run,
        integration_cleanup_scheduler_execute_kill_switch=integration_cleanup_scheduler_execute_kill_switch,
        auth_jwt_secret_key=auth_jwt_secret_key,
        auth_access_token_expire_minutes=auth_access_token_expire_minutes,
        auth_internal_users_file=auth_internal_users_file,
        auth_internal_users_json=auth_internal_users_json,
        jobs_upload_max_bytes=jobs_upload_max_bytes,
        files_quota_policy_enabled=files_quota_policy_enabled,
        files_quota_policy_dry_run=files_quota_policy_dry_run,
        files_quota_bytes=files_quota_bytes,
        files_quota_warning_threshold_ratio=files_quota_warning_threshold_ratio,
        files_quota_block_threshold_ratio=files_quota_block_threshold_ratio,
        pdf_upload_max_pages=pdf_upload_max_pages,
        p0_document_job_timeout_seconds=p0_document_job_timeout_seconds,
        p0_document_job_max_retries=p0_document_job_max_retries,
        default_translation_mode=default_translation_mode,
        document_jobs_worker_backend=document_jobs_worker_backend,
        document_jobs_celery_broker_url=document_jobs_celery_broker_url,
        document_jobs_celery_result_backend=document_jobs_celery_result_backend,
        document_jobs_celery_queue=document_jobs_celery_queue,
        document_jobs_translation_batch_celery_queue=document_jobs_translation_batch_celery_queue,
        translation_debug_archive_enabled=translation_debug_archive_enabled,
        translation_debug_archive_retention_days=translation_debug_archive_retention_days,
        **({"templates_manifest_path": templates_manifest_path} if templates_manifest_path else {}),
        **({"term_rules_seed_path": term_rules_seed_path} if term_rules_seed_path else {}),
        **({"translation_terms_path": translation_terms_path} if translation_terms_path else {}),
    )
    if repository_factory is not None:
        persistence_adapters = repository_factory(settings.data_path)
    elif jobs_repository_backend == "database":
        settings.jobs_dir.mkdir(parents=True, exist_ok=True)
        settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        persistence_adapters = build_sqlite_persistence_adapters(settings.jobs_metadata_database_file)
    elif jobs_repository_backend == "mysql":
        settings.jobs_dir.mkdir(parents=True, exist_ok=True)
        settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        persistence_adapters = build_mysql_persistence_adapters(
            MysqlPersistenceConfig(
                host=settings.jobs_mysql_host,
                port=settings.jobs_mysql_port,
                user=settings.jobs_mysql_user,
                password=settings.jobs_mysql_password,
                database=settings.jobs_mysql_database,
                charset=settings.jobs_mysql_charset,
                connect_timeout_seconds=settings.jobs_mysql_connect_timeout_seconds,
            )
        )
    else:
        persistence_adapters = build_file_persistence_adapters(settings.data_path)
    job_repository = persistence_adapters.job_repository
    job_file_repository = persistence_adapters.job_file_repository
    job_event_repository = persistence_adapters.job_event_repository
    audit_event_repository = persistence_adapters.audit_event_repository
    acceptance_run_repository = persistence_adapters.acceptance_run_repository
    document_file_repository = persistence_adapters.document_file_repository
    file_retention_policy_repository = persistence_adapters.file_retention_policy_repository
    file_retention_cleanup_lock_repository = persistence_adapters.file_retention_cleanup_lock_repository
    file_retention_cleanup_run_history_repository = persistence_adapters.file_retention_cleanup_run_history_repository
    document_job_repository = persistence_adapters.document_job_repository
    document_job_event_repository = persistence_adapters.document_job_event_repository
    document_job_callback_message_store = persistence_adapters.document_job_callback_message_store
    document_job_translation_batch_repository = persistence_adapters.document_job_translation_batch_repository
    internal_user_repository = persistence_adapters.internal_user_repository
    saved_view_repository = persistence_adapters.saved_view_repository
    stage_message_store = persistence_adapters.stage_message_store
    audit_service = AuditService(audit_event_repository)
    acceptance_run_service = AcceptanceRunService(acceptance_run_repository)
    auth_service = AuthService(settings, internal_user_repository)
    internal_user_management_service = InternalUserManagementService(internal_user_repository)
    file_retention_policy_service = FileRetentionPolicyService(
        settings,
        file_retention_policy_repository,
        document_file_repository,
    )
    file_upload_service = FileUploadService(
        settings,
        document_file_repository,
        retention_days_resolver=file_retention_policy_service.resolve_retention_days,
    )
    document_ir_service = MinerUToDocumentIRService()
    ai_provider_config_service = AiProviderConfigService(settings)
    mineru_config_service = MinerUConfigService(settings)
    translation_provider = build_translation_provider(
        settings,
        config_resolver=ai_provider_config_service.get_effective_config,
    )
    document_ir_translation_service = DocumentIRTranslationService(translation_provider)
    translation_audit_service = TranslationAuditService(
        settings,
        file_upload_service,
        config_resolver=ai_provider_config_service.get_effective_config,
    )
    term_version_service = TermVersionService(
        settings.translation_terms_file,
        default_term_version_id=settings.default_translation_term_version_id,
        repository=persistence_adapters.translation_term_repository,
    )
    term_version_service.bootstrap_repository_from_csv_if_empty()
    resource_version_service = (
        ResourceVersionService(persistence_adapters.resource_version_repository)
        if persistence_adapters.resource_version_repository is not None
        else None
    )
    job_resource_snapshot_service = JobResourceSnapshotService(
        settings,
        resource_version_service,
        persistence_adapters.translation_term_repository,
    )
    template_read_service = TemplateReadService(
        settings,
        resource_version_service,
        audit_service,
        document_job_repository=document_job_repository,
    )
    document_word_renderer = DocumentIRWordRenderer()
    document_job_mineru_client = FakeMinerUClient()
    document_job_mineru_client.result_zip_bytes = make_mineru_zip_bytes()
    document_job_execution_service = DocumentJobExecutionService(
        settings,
        document_job_repository,
        document_job_event_repository,
        document_job_callback_message_store,
        document_job_translation_batch_repository,
        document_file_repository,
        file_upload_service,
        document_ir_service,
        template_read_service,
        document_word_renderer,
        mineru_config_service.get_effective_config,
        document_ir_translation_service,
        term_version_service,
        translation_audit_service,
        mineru_client_factory=lambda: document_job_mineru_client,
    )
    document_job_execution_service.fake_mineru_client = document_job_mineru_client
    document_job_task_queue = (
        EagerDocumentJobTaskQueue(document_job_execution_service)
        if document_jobs_worker_backend == "eager"
        else None
    )
    document_translation_batch_task_queue = (
        EagerDocumentTranslationBatchTaskQueue(document_job_execution_service)
        if document_jobs_worker_backend == "eager"
        else None
    )
    document_job_execution_service.set_translation_batch_task_queue(document_translation_batch_task_queue)
    document_job_recovery_service = DocumentJobRecoveryService(
        settings,
        document_job_repository,
        document_job_event_repository,
        document_job_callback_message_store,
        document_job_task_queue,
    )
    document_job_service = DocumentJobService(
        settings,
        document_job_repository,
        document_job_event_repository,
        document_file_repository,
        document_job_task_queue,
        template_read_service,
        term_version_service,
        job_resource_snapshot_service,
        document_job_translation_batch_repository=document_job_translation_batch_repository,
        file_upload_service=file_upload_service,
    )
    document_job_incident_service = DocumentJobIncidentService(document_job_service)
    health_service = HealthService(
        settings,
        stage_message_store,
        effective_repository_backend=jobs_repository_backend,
        stage_message_store_backend=jobs_repository_backend,
        artifact_storage_backend=jobs_artifact_storage_backend,
        stage_dispatcher_backend="external_worker" if jobs_worker_mode == "external" else "background_tasks",
        job_repository=job_repository,
        document_job_repository=document_job_repository,
        document_job_callback_message_store=document_job_callback_message_store,
        internal_user_repository=internal_user_repository,
        audit_event_repository=audit_event_repository,
        resource_version_repository=resource_version_service.repository if resource_version_service is not None else None,
        default_template_id_getter=template_read_service.get_default_template_id,
        ai_provider_config_service=ai_provider_config_service,
        mineru_config_service=mineru_config_service,
    )
    term_rule_repository = FileTermRuleRepository(settings.term_rules_store_file)
    term_rule_service = TermRuleService(
        term_rule_repository,
        settings.term_rules_runtime_yaml_file,
        settings.term_rules_seed_file,
    )
    term_rule_import_validation_service = TermRuleImportValidationService()
    term_rule_file_sync_service = TermRuleFileSyncService(
        term_rule_repository,
        settings.term_rules_runtime_yaml_file,
        settings.term_rules_seed_file,
        repository_backend="file",
    )
    term_rule_set_version_service = (
        TermRuleSetVersionService(
            repository=term_rule_repository,
            runtime_yaml_path=settings.term_rules_runtime_yaml_file,
            resource_version_service=resource_version_service,
            audit_service=audit_service,
            asset_repository=persistence_adapters.term_rule_asset_repository,
        )
        if resource_version_service is not None
        else None
    )
    term_rule_proposal_service = (
        TermRuleProposalService(
            repository=persistence_adapters.term_rule_proposal_repository,
            term_rule_service=term_rule_service,
            term_rule_set_version_service=term_rule_set_version_service,
            audit_service=audit_service,
        )
        if persistence_adapters.term_rule_proposal_repository is not None
        and term_rule_set_version_service is not None
        else None
    )
    translation_profile_service = (
        TranslationProfileVersionService(settings, resource_version_service, audit_service)
        if resource_version_service is not None
        else None
    )
    translation_term_set_version_service = (
        TranslationTermSetVersionService(persistence_adapters.translation_term_repository, audit_service)
        if persistence_adapters.translation_term_repository is not None
        else None
    )
    translation_term_proposal_service = (
        TranslationTermProposalService(
            repository=persistence_adapters.translation_term_repository,
            term_set_version_service=translation_term_set_version_service,
            audit_service=audit_service,
        )
        if persistence_adapters.translation_term_repository is not None
        and translation_term_set_version_service is not None
        else None
    )
    if term_rule_set_version_service is not None:
        term_rule_set_version_service.bootstrap_seed_as_default_if_empty(settings.term_rules_seed_file)
    else:
        TermRuleBootstrapService(
            term_rule_repository,
            settings.term_rules_runtime_yaml_file,
            settings.term_rules_seed_file,
            repository_backend="file",
        ).bootstrap()
    if translation_profile_service is not None:
        translation_profile_service.bootstrap_default_profiles_if_missing()
    template_read_service.get_default_template_id()
    conversion_service = FakeConversionService()
    artifact_service = JobArtifactService()
    if jobs_artifact_storage_backend == "local_object":
        artifact_storage = ObjectArtifactStorageAdapter(artifact_service, settings.jobs_artifact_object_store_dir)
    else:
        artifact_storage = LocalArtifactStorageAdapter(artifact_service)
    fake_mineru_client = FakeMinerUClient()
    stage_service = JobStageService(
        settings,
        job_repository,
        job_file_repository,
        job_event_repository,
        conversion_service,
        artifact_storage,
        stage_message_store=stage_message_store,
        mineru_config_resolver=mineru_config_service.get_effective_config,
        stage_worker_id="md2word-worker" if jobs_worker_mode == "external" else "in_process",
        mineru_client_factory=lambda: fake_mineru_client,
        resolve_template_path=template_read_service.resolve_job_template_path,
        resolve_layout_config_path=template_read_service.resolve_job_layout_config_path,
        resolve_subscript_config_path=lambda: settings.subscript_config_path,
        resolve_translation_profile_snapshot=(
            translation_profile_service.resolve_default_snapshot
            if translation_profile_service is not None
            else None
        ),
        resource_snapshot_service=job_resource_snapshot_service,
    )
    stage_service.fake_mineru_client = fake_mineru_client
    if jobs_worker_mode == "external":
        stage_dispatcher = ExternalWorkerStageDispatcher()
    else:
        stage_dispatcher = InProcessStageDispatcher(stage_service)
    command_service = JobCommandService(
        settings,
        job_repository,
        job_file_repository,
        job_event_repository,
        stage_service,
        artifact_storage,
        job_resource_snapshot_service,
    )
    lifecycle_service = JobLifecycleService(
        job_repository=job_repository,
        job_file_repository=job_file_repository,
        job_event_repository=job_event_repository,
        audit_service=audit_service,
        stage_message_store=stage_message_store,
        stage_service=stage_service,
        artifact_service=artifact_service,
        artifact_storage=artifact_storage,
        resource_snapshot_service=job_resource_snapshot_service,
    )
    query_service = JobQueryService(job_repository, job_file_repository, job_event_repository)
    saved_view_service = SavedViewService(saved_view_repository)
    return AppRuntime(
        settings=settings,
        persistence_adapters=persistence_adapters,
        job_repository=job_repository,
        job_file_repository=job_file_repository,
        job_event_repository=job_event_repository,
        audit_event_repository=audit_event_repository,
        acceptance_run_repository=acceptance_run_repository,
        document_file_repository=document_file_repository,
        file_retention_policy_repository=file_retention_policy_repository,
        file_retention_cleanup_lock_repository=file_retention_cleanup_lock_repository,
        file_retention_cleanup_run_history_repository=file_retention_cleanup_run_history_repository,
        document_job_repository=document_job_repository,
        document_job_event_repository=document_job_event_repository,
        document_job_callback_message_store=document_job_callback_message_store,
        document_job_translation_batch_repository=document_job_translation_batch_repository,
        internal_user_repository=internal_user_repository,
        saved_view_repository=saved_view_repository,
        terminology_release_repository=persistence_adapters.terminology_release_repository,
        audit_service=audit_service,
        acceptance_run_service=acceptance_run_service,
        auth_service=auth_service,
        internal_user_management_service=internal_user_management_service,
        file_upload_service=file_upload_service,
        file_retention_policy_service=file_retention_policy_service,
        document_ir_service=document_ir_service,
        ai_provider_config_service=ai_provider_config_service,
        mineru_config_service=mineru_config_service,
        translation_provider=translation_provider,
        document_ir_translation_service=document_ir_translation_service,
        translation_audit_service=translation_audit_service,
        term_version_service=term_version_service,
        document_word_renderer=document_word_renderer,
        document_job_service=document_job_service,
        saved_view_service=saved_view_service,
        document_job_incident_service=document_job_incident_service,
        document_job_execution_service=document_job_execution_service,
        document_job_recovery_service=document_job_recovery_service,
        document_job_task_queue=document_job_task_queue,
        health_service=health_service,
        template_read_service=template_read_service,
        term_rule_service=term_rule_service,
        term_rule_import_validation_service=term_rule_import_validation_service,
        term_rule_file_sync_service=term_rule_file_sync_service,
        term_rule_set_version_service=term_rule_set_version_service,
        term_rule_proposal_service=term_rule_proposal_service,
        term_rule_review_service=None,
        translation_term_set_version_service=translation_term_set_version_service,
        translation_term_proposal_service=translation_term_proposal_service,
        terminology_release_service=None,
        translation_profile_service=translation_profile_service,
        resource_version_service=resource_version_service,
        job_resource_snapshot_service=job_resource_snapshot_service,
        artifact_service=artifact_service,
        artifact_storage=artifact_storage,
        command_service=command_service,
        lifecycle_service=lifecycle_service,
        query_service=query_service,
        stage_service=stage_service,
        stage_dispatcher=stage_dispatcher,
        stage_message_store=stage_message_store,
        alert_delivery_provider=alert_delivery_provider,
        secret_resolver=secret_resolver,
    )


def make_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", "[]")
    return buffer.getvalue()


def make_mineru_zip_bytes(*, include_image: bool = True) -> bytes:
    buffer = io.BytesIO()
    blocks = [
        {"type": "title", "text": "数据手册", "text_level": 1, "page_idx": 0, "bbox": [72, 80, 180, 100]},
        {"type": "text", "text": "主要特性", "page_idx": 0, "bbox": [72, 120, 260, 150]},
        {
            "type": "table",
            "table_caption": "参数表",
            "table_body": "<table><tr><td>VCC</td></tr></table>",
            "page_idx": 0,
            "bbox": [72, 180, 560, 260],
        },
        {"type": "list", "items": ["低功耗", "高可靠"], "page_idx": 1, "bbox": [72, 80, 260, 140]},
        {"type": "interline_equation", "latex": "E=mc^2", "page_idx": 1, "bbox": [72, 160, 260, 180]},
    ]
    if include_image:
        blocks.insert(
            3,
            {
                "type": "image",
                "img_path": "images/figure1.png",
                "caption": "管脚图",
                "page_idx": 0,
                "bbox": [300, 120, 520, 210],
            },
        )
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", json.dumps(blocks, ensure_ascii=False))
        archive.writestr(
            "layout.json",
            json.dumps(
                {
                    "pdf_info": [
                        {"page_idx": 0, "page_size": [612, 792]},
                        {"page_idx": 1, "page_size": [792, 612]},
                    ]
                },
                ensure_ascii=False,
            ),
        )
        if include_image:
            archive.writestr("images/figure1.png", MINIMAL_PNG_BYTES)
    return buffer.getvalue()


def make_english_mineru_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    blocks = [
        {"type": "title", "text": "1 Features", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "The input offset voltage is low.", "page_idx": 0},
        {
            "type": "table",
            "table_caption": "Electrical Characteristics",
            "table_body": "<table><tr><th>Parameter</th><td>Input voltage</td></tr></table>",
            "page_idx": 0,
        },
        {"type": "image", "img_path": "images/figure1.png", "caption": "Figure 1. Pin diagram", "page_idx": 0},
        {"type": "list", "items": ["Low noise", "High slew rate"], "page_idx": 1},
        {"type": "interline_equation", "latex": "E=mc^2", "page_idx": 1},
    ]
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", json.dumps(blocks, ensure_ascii=False))
        archive.writestr("images/figure1.png", MINIMAL_PNG_BYTES)
    return buffer.getvalue()


def make_semantic_mineru_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    blocks = [
        {
            "type": "title",
            "text": "6.5 Thermal Information",
            "text_level": 2,
            "page_idx": 0,
            "bbox": [72, 80, 360, 105],
        },
        {
            "type": "list",
            "items": ["• Low noise", "- Stable supply"],
            "page_idx": 0,
            "bbox": [72, 120, 360, 170],
        },
        {
            "type": "interline_equation",
            "latex": r"$R_{\theta JA}$, E=mc^2, nV/ \sqrt{Hz}",
            "page_idx": 0,
            "bbox": [72, 190, 360, 215],
        },
        {
            "type": "table",
            "table_caption": "Table 1: Electrical Characteristics",
            "table_body": (
                r"<table><tr><th>Parameter</th><th>Value</th></tr>"
                r"<tr><td>$R_{\theta JA}$</td><td>nV/ \sqrt{Hz}</td></tr></table>"
            ),
            "table_footnote": r"Note: E=mc^2",
            "page_idx": 0,
            "bbox": [40, 240, 580, 330],
        },
    ]
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", json.dumps(blocks, ensure_ascii=False))
        archive.writestr(
            "layout.json",
            json.dumps({"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]}, ensure_ascii=False),
        )
    return buffer.getvalue()


def make_portrait_wide_table_condition_mineru_zip_bytes() -> bytes:
    condition = (
        "at TA = +25°C, VS = ±5 V to ±15 V, VCM = VOUT = VS / 2, "
        "and RL = 10 kΩ connected to VS / 2 (unless otherwise noted)"
    )
    headers = "".join(f"<th>PARAMETER {index}</th>" for index in range(1, 9))
    values = "".join(f"<td>Value {index}</td>" for index in range(1, 9))
    buffer = io.BytesIO()
    blocks = [
        {
            "type": "title",
            "text": "6.8 Electrical Characteristics",
            "text_level": 2,
            "page_idx": 0,
            "bbox": [72, 80, 360, 105],
        },
        {
            "type": "table",
            "table_caption": [condition],
            "table_body": f"<table><tr>{headers}</tr><tr>{values}</tr></table>",
            "page_idx": 0,
            "bbox": [40, 130, 580, 260],
        },
    ]
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", json.dumps(blocks, ensure_ascii=False))
        archive.writestr(
            "layout.json",
            json.dumps({"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]}, ensure_ascii=False),
        )
    return buffer.getvalue()


def make_subscript_mineru_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    blocks = [
        {"type": "text", "text": "VOS and IOS are specified.", "page_idx": 0, "bbox": [72, 80, 360, 120]},
        {
            "type": "table",
            "table_caption": "Table 1: VOS limits",
            "table_body": "<table><tr><th>Parameter</th></tr><tr><td>VOS</td></tr></table>",
            "page_idx": 0,
            "bbox": [72, 150, 420, 260],
        },
    ]
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", json.dumps(blocks, ensure_ascii=False))
        archive.writestr(
            "layout.json",
            json.dumps({"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]}, ensure_ascii=False),
        )
    return buffer.getvalue()


def make_pdf_bytes(page_count: int = 1) -> bytes:
    pages = "\n".join(
        f"{index} 0 obj << /Type /Page /Parent 0 0 R >> endobj"
        for index in range(1, page_count + 1)
    )
    return f"%PDF-1.4\n{pages}\n%%EOF\n".encode("utf-8")


def build_callback_payload(*, batch_id: str, data_id: str, state: str, full_zip_url: str | None = None, uid: str | None = None) -> tuple[dict, str]:
    data = {
        "batch_id": batch_id,
        "extract_result": [
            {
                "data_id": data_id,
                "state": state,
                **({"full_zip_url": full_zip_url} if full_zip_url else {}),
            }
        ],
    }
    content = json.dumps(data, ensure_ascii=False)
    payload = {"batch_id": batch_id, "content": content}
    if uid is not None:
        payload["uid"] = uid
    return payload, content


def build_callback_checksum(*, uid: str, seed: str, content: str) -> str:
    return hashlib.sha256(f"{uid}{seed}{content}".encode("utf-8")).hexdigest()


def read_legacy_callback_seed(runtime: AppRuntime, job_id: str) -> str:
    job = runtime.job_repository.get_job(job_id)
    if job is None:
        raise AssertionError(f"job not found: {job_id}")
    seed = job.read_mineru_callback_seed()
    if seed is None:
        raise AssertionError(f"mineru callback seed missing: {job_id}")
    return seed


def write_templates_manifest(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"templates": entries}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def resource_payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def create_template_verification_job(
    runtime: AppRuntime,
    *,
    job_id: str,
    template_version_id: str,
    status: str = "succeeded",
) -> DocumentJobRecord:
    stage = "completed" if status == "succeeded" else "uploaded"
    now = utc_now()
    return runtime.document_job_repository.create_document_job(
        DocumentJobRecord(
            id=job_id,
            tenant_id="tenant_demo",
            company_id="company_demo",
            created_by="user_admin",
            source_file_id=f"file_{job_id}",
            status=status,
            stage=stage,
            progress=100 if status == "succeeded" else 0,
            template_version_id=template_version_id,
            completed_at=now if status == "succeeded" else None,
        )
    )


def publish_template_resource_version(
    runtime: AppRuntime,
    *,
    version: str,
    content: bytes,
    make_default: bool,
    template_id: str = "default",
) -> Path:
    service = runtime.resource_version_service
    if service is None:
        raise AssertionError("resource_version_service is required for this test")
    template_path = runtime.settings.data_path / "test_resources" / "templates" / template_id / f"v{version}.docx"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_bytes(content)
    payload = {
        "template_id": template_id,
        "version": version,
        "name": f"Template {version}",
        "description": "test template resource",
        "docx_path": str(template_path.resolve()),
        "docx_sha256": f"sha256:{hashlib.sha256(content).hexdigest()}",
        "layout_config_path": str(runtime.settings.layout_config_path) if runtime.settings.layout_config_path else None,
        "layout_config_sha256": None,
        "render_policy": {},
    }
    service.create_or_update_draft(
        resource_type="template",
        resource_id=template_id,
        version=version,
        snapshot_hash=resource_payload_hash(payload),
        payload_ref=f"template:{template_id}@{version}",
        payload=payload,
    )
    service.publish("template", template_id, version, make_default=make_default)
    return template_path.resolve()


def build_test_term_rules_store(source_term: str):
    yaml_text = (
        "schema_version: 2\n"
        "categories:\n"
        "  voltage_terms:\n"
        "    name: 电压相关\n"
        "    priority: 10\n"
        "    enabled: true\n"
        "    description: ''\n"
        "rules:\n"
        f"  - source_term: {source_term}\n"
        "    category: voltage_terms\n"
        "    segments:\n"
        "      - segment_text: V\n"
        "        render_type: plain\n"
        f"      - segment_text: {source_term.removeprefix('V') or source_term}\n"
        "        render_type: subscript\n"
        "    apply_scope: both\n"
        "    case_sensitive: true\n"
        "    enabled: true\n"
        "    priority: 10\n"
        "    notes: ''\n"
    )
    return TermRuleYamlCodec().parse_yaml_text(yaml_text)


def publish_term_rule_resource_version(
    runtime: AppRuntime,
    *,
    version: str,
    source_term: str,
    make_default: bool,
    term_rule_set_id: str = DEFAULT_TERM_RULE_SET_ID,
) -> None:
    service = runtime.resource_version_service
    if service is None:
        raise AssertionError("resource_version_service is required for this test")
    store = build_test_term_rules_store(source_term)
    payload = {
        "term_rule_set_id": term_rule_set_id,
        "version": version,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "base_version": None,
        "rule_count": len(store.rules),
        "enabled_rule_count": sum(1 for rule in store.rules if rule.enabled),
        "published_by": "test",
        "publish_reason": "test resource snapshot",
        "published_at": None,
        "store": store.model_dump(mode="json"),
    }
    service.create_or_update_draft(
        resource_type="term_rule_set",
        resource_id=term_rule_set_id,
        version=version,
        snapshot_hash=resource_payload_hash(payload),
        payload_ref=f"term_rule_set:{term_rule_set_id}@{version}",
        payload=payload,
    )
    service.publish("term_rule_set", term_rule_set_id, version, make_default=make_default)


def publish_translation_profile_resource_version(
    runtime: AppRuntime,
    *,
    version: str,
    model: str,
    make_default: bool,
    translation_profile_id: str = DEFAULT_TRANSLATION_PROFILE_ID,
    language_pair: str = "en2zh",
) -> None:
    service = runtime.resource_version_service
    if service is None:
        raise AssertionError("resource_version_service is required for this test")
    payload = {
        "translation_profile_id": translation_profile_id,
        "language_pair": language_pair,
        "version": version,
        "base_version": None,
        "target_language": "zh-CN",
        "domain": "electronics datasheet",
        "prompt_version": f"prompt-{version}",
        "model": model,
        "max_pages_per_batch": 7,
        "max_chars_per_batch": 1234,
    }
    service.create_or_update_draft(
        resource_type="translation_profile",
        resource_id=translation_profile_id,
        version=version,
        snapshot_hash=resource_payload_hash(payload),
        payload_ref=f"translation_profile:{translation_profile_id}@{version}",
        payload=payload,
    )
    service.publish("translation_profile", translation_profile_id, version, make_default=make_default)


def publish_translation_term_set_version(
    runtime: AppRuntime,
    *,
    source_term: str,
    target_term: str,
    make_default: bool,
    set_id: str = "translation-terms-en2zh",
) -> str:
    service = runtime.translation_term_set_version_service
    if service is None:
        raise AssertionError("translation_term_set_version_service is required for this test")
    draft = service.get_draft(set_id)
    entries = [
        TranslationTermEntry(
            language_pair=draft.language_pair,
            source_term=source_term,
            target_term=target_term,
            version=draft.version,
        )
    ]
    service.update_draft(set_id, entries)
    published = service.publish_draft(
        set_id,
        make_default=make_default,
        published_by="admin",
        release_note="test translation term resource snapshot",
    )
    return published.version.version


def publish_default_job_resources(runtime: AppRuntime, *, include_translation: bool = False) -> tuple[Path, str]:
    template_path = publish_template_resource_version(
        runtime,
        version="1",
        content=b"template-v1",
        make_default=True,
    )
    publish_term_rule_resource_version(runtime, version="1", source_term="VONE", make_default=True)
    if include_translation:
        publish_translation_profile_resource_version(
            runtime,
            version="1",
            model="snapshot-model-v1",
            make_default=True,
        )
    return template_path, "VONE"


def build_mysql_test_runtime(data_dir: Path, **kwargs) -> AppRuntime:
    from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

    fake_mysql = _FakeMysqlDatabase()
    return build_test_runtime(
        data_dir,
        jobs_repository_backend="mysql",
        repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
            _mysql_config(),
            connect_factory=fake_mysql.connect,
        ),
        **kwargs,
    )


JOB_ACCEPTED_RESPONSE_KEYS = ["job_id", "trace_id", "status", "translation_mode", "resource_snapshot"]
JOB_FILE_RESPONSE_KEYS = [
    "file_type",
    "path",
    "storage_backend",
    "object_key",
    "public_url",
    "size_bytes",
    "sha256",
    "download_url",
    "created_at",
]
JOB_EVENT_RESPONSE_KEYS = ["stage", "message", "status", "error_code", "details", "trace_id", "created_at"]
JOB_SUMMARY_RESPONSE_KEYS = [
    "id",
    "source_filename",
    "status",
    "progress",
    "translation_mode",
    "result_ready",
    "result_download_url",
    "created_at",
    "updated_at",
]
JOB_LIST_RESPONSE_KEYS = ["items", "page", "page_size", "total", "summary"]
JOB_DETAIL_RESPONSE_KEYS = [
    "id",
    "source_filename",
    "status",
    "progress",
    "source_kind",
    "translation_mode",
    "document_language",
    "resolved_document_language",
    "template_id",
    "resource_snapshot",
    "mineru_batch_id",
    "mineru_data_id",
    "mineru_callback_seed",
    "mineru_status",
    "mineru_result_zip_url",
    "error_code",
    "error_message",
    "result_ready",
    "created_at",
    "updated_at",
    "started_at",
    "completed_at",
    "files",
    "events",
]
JOB_FILE_LIST_RESPONSE_KEYS = ["job_id", "files"]
JOB_EVENT_LIST_RESPONSE_KEYS = ["job_id", "items"]


def build_auth_users_json() -> str:
    return json.dumps(
        [
            {
                "id": "user_admin",
                "username": "admin",
                "password_hash": hash_password("admin-pass", salt="admin-salt", iterations=1000),
                "role": "admin",
                "tenant_id": "tenant_default",
                "company_id": "company_default",
                "status": "active",
                "display_name": "Admin User",
            },
            {
                "id": "user_operator",
                "username": "operator",
                "password_hash": hash_password("operator-pass", salt="operator-salt", iterations=1000),
                "role": "operator",
                "tenant_id": "tenant_default",
                "company_id": "company_default",
                "status": "active",
                "display_name": "Operator User",
            },
        ],
        ensure_ascii=False,
    )


def build_multi_operator_auth_users_json() -> str:
    users = json.loads(build_auth_users_json())
    users.append(
        {
            "id": "user_operator_2",
            "username": "operator2",
            "password_hash": hash_password("operator2-pass", salt="operator2-salt", iterations=1000),
            "role": "operator",
            "tenant_id": "tenant_default",
            "company_id": "company_default",
            "status": "active",
            "display_name": "Operator Two",
        }
    )
    return json.dumps(users, ensure_ascii=False)


def build_auth_header(client: TestClient, username: str = "operator", password: str = "operator-pass") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    if response.status_code != 200:
        raise AssertionError(response.json())
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class FastAPIJobsBackendTests(TestCase):
    def test_legacy_jobs_api_paths_are_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                responses = [
                    client.get("/api/v1/jobs"),
                    client.post("/api/v1/jobs", files={"package": ("mineru-output.zip", b"zip", "application/zip")}),
                    client.post("/api/v1/jobs/pdf", files={"file": ("source.pdf", b"%PDF", "application/pdf")}),
                    client.get("/api/v1/jobs/job_removed"),
                    client.get("/api/v1/jobs/job_removed/files"),
                    client.get("/api/v1/jobs/job_removed/events"),
                    client.get("/api/v1/jobs/job_removed/result"),
                    client.get("/api/v1/jobs/job_removed/download/result"),
                    client.post("/api/v1/jobs/job_removed/retry"),
                    client.post("/api/v1/jobs/job_removed/cancel"),
                    client.post("/api/v1/jobs/job_removed/recover-mineru-result"),
                    client.post("/api/v1/jobs/job_removed/cleanup-local-files"),
                ]

        self.assertTrue(all(response.status_code == 404 for response in responses))

    def test_legacy_jobs_api_references_stay_limited_to_removal_assertion(self):
        legacy_path = "/api/v1/" + "jobs"
        source = Path(__file__).read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source)
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            if node.name == "test_legacy_jobs_api_paths_are_removed":
                continue
            segment = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            if legacy_path in segment:
                offenders.append(node.name)

        self.assertEqual(offenders, [])

    def test_api_v1_schema_imports_use_final_owners_after_resource_split(self):
        from app.api.v1.routers.health_schemas import HealthReadyResponse
        from app.domains.document_jobs.schemas import DocumentJobCreateResponse
        from app.domains.document_jobs.schemas import DocumentJobRetryResponse
        from app.domains.files.schemas import DocumentFileResponse

        self.assertEqual(DocumentFileResponse.__module__, "app.domains.files.schemas")
        self.assertEqual(DocumentJobCreateResponse.__module__, "app.domains.document_jobs.schemas")
        self.assertEqual(DocumentJobRetryResponse.__module__, "app.domains.document_jobs.schemas")
        self.assertEqual(HealthReadyResponse.__module__, "app.api.v1.routers.health_schemas")

    def test_health_ready_reports_runtime_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                response = client.get("/api/v1/health/ready")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["app_name"], "md2word_file_test")
        self.assertEqual(payload["deployment"]["environment"], "dev")
        self.assertEqual(payload["deployment"]["public_deployment_mode"], "internal")
        self.assertEqual(payload["deployment"]["version"], "dev")
        self.assertIsNone(payload["deployment"]["deployment_id"])
        self.assertTrue(payload["deployment"]["started_at"])
        self.assertEqual(payload["dependency_checks"]["configured_repository_backend"], "file")
        self.assertEqual(payload["dependency_checks"]["effective_repository_backend"], "file")
        self.assertEqual(payload["dependency_checks"]["worker_mode"], "in_process")
        self.assertEqual(payload["dependency_checks"]["document_jobs_worker_backend"], "disabled")
        self.assertEqual(payload["dependency_checks"]["document_jobs_celery_queue"], "document-jobs")
        self.assertEqual(
            payload["dependency_checks"]["document_jobs_translation_batch_celery_queue"],
            "document-translation-batches",
        )
        self.assertEqual(payload["dependency_checks"]["stage_dispatcher"], "background_tasks")
        self.assertEqual(payload["dependency_checks"]["stage_message_store"], "file")
        self.assertEqual(payload["dependency_checks"]["artifact_storage"], "local_file")
        self.assertIn("jobs_dir_writable", payload["dependency_checks"]["readiness_required_checks"])
        self.assertIn("translation_available", payload["dependency_checks"]["readiness_non_blocking_checks"])
        self.assertTrue(payload["dependency_checks"]["jobs_dir_exists"])
        self.assertTrue(payload["dependency_checks"]["stage_spool_dir_exists"])
        self.assertTrue(payload["dependency_checks"]["jobs_dir_writable"])
        self.assertTrue(payload["dependency_checks"]["artifact_root_writable"])
        self.assertGreater(payload["dependency_checks"]["artifact_disk_free_bytes"], 0)
        self.assertEqual(payload["dependency_checks"]["stage_spool_pending_messages"], 0)
        self.assertEqual(payload["dependency_checks"]["stage_spool_running_messages"], 0)
        self.assertEqual(payload["dependency_checks"]["stage_spool_failed_messages"], 0)
        self.assertEqual(payload["dependency_checks"]["stage_spool_replayable_messages"], 0)
        self.assertEqual(payload["dependency_checks"]["stage_spool_running_stale_messages"], 0)
        self.assertEqual(payload["dependency_checks"]["stage_spool_oldest_running_age_seconds"], 0)
        self.assertFalse(payload["dependency_checks"]["stage_spool_needs_attention"])
        self.assertEqual(payload["dependency_checks"]["stage_spool_observation_status"], "ok")
        self.assertEqual(payload["dependency_checks"]["default_translation_mode"], "direct")
        self.assertFalse(payload["dependency_checks"]["translation_required_for_default_mode"])
        self.assertEqual(payload["dependency_checks"]["translation_provider_backend"], "disabled")
        self.assertFalse(payload["dependency_checks"]["translation_debug_archive_enabled"])
        self.assertTrue(payload["dependency_checks"]["translation_client_configured"] is False)
        self.assertTrue(payload["dependency_checks"]["translation_prompt_exists"])
        self.assertFalse(payload["dependency_checks"]["mineru_api_token_configured"])
        self.assertFalse(payload["dependency_checks"]["mineru_callback_url_configured"])
        self.assertFalse(payload["dependency_checks"]["mineru_uid_configured"])
        self.assertFalse(payload["dependency_checks"]["pdf_submission_available"])
        self.assertFalse(payload["dependency_checks"]["p0_document_jobs_required"])
        self.assertTrue(payload["dependency_checks"]["p0_document_jobs_ready"])
        self.assertFalse(payload["dependency_checks"]["document_jobs_automatic_execution_enabled"])
        self.assertEqual(payload["dependency_checks"]["p0_document_jobs_blockers"], [])
        self.assertIn("document_jobs_worker_backend_disabled", payload["dependency_checks"]["p0_document_jobs_warnings"])
        self.assertEqual(payload["dependency_checks"]["document_jobs_running_stale_count"], 0)
        self.assertEqual(payload["dependency_checks"]["document_jobs_timed_out_count"], 0)
        self.assertEqual(payload["dependency_checks"]["document_jobs_running_oldest_age_seconds"], 0)
        self.assertTrue(payload["dependency_checks"]["deployment_init_ready"])
        self.assertEqual(payload["dependency_checks"]["readiness_blockers"], [])
        self.assertIn("mineru_api_token_missing", payload["dependency_checks"]["readiness_warnings"])
        self.assertIn("document_jobs_worker_backend_disabled", payload["dependency_checks"]["readiness_warnings"])
        self.assertIn("translation_unavailable", payload["dependency_checks"]["readiness_warnings"])
        self.assertIsNone(payload["dependency_checks"]["default_template_version"])
        self.assertIsNone(payload["dependency_checks"]["default_term_rule_version"])
        self.assertIsNone(payload["dependency_checks"]["default_translation_profile_version"])
        self.assertFalse(payload["dependency_checks"]["mysql_schema_bootstrap_available"])

    def test_ai_provider_config_api_updates_runtime_config_and_masks_secret(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_get_response = client.get("/api/v1/ai-provider-config", headers=operator_headers)
                update_response = client.put(
                    "/api/v1/ai-provider-config",
                    headers={**admin_headers, "X-Trace-Id": "trace_ai_provider_update"},
                    json={
                        "backend": "openai_compatible",
                        "base_url": "https://llm.example.test/v1",
                        "model": "deepseek-v4-flash",
                        "timeout_seconds": 45,
                        "max_output_tokens": 16000,
                        "api_key": "sk-test-secret-123456",
                    },
                )
                get_response = client.get("/api/v1/ai-provider-config", headers=admin_headers)
                health_response = client.get("/api/v1/health/ready")

            config_file_exists = runtime.settings.ai_provider_config_file.exists()
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(operator_get_response.status_code, 403)
        self.assertEqual(update_response.status_code, 200)
        payload = update_response.json()
        self.assertEqual(payload["backend"], "openai_compatible")
        self.assertEqual(payload["base_url"], "https://llm.example.test/v1")
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["timeout_seconds"], 45)
        self.assertEqual(payload["max_output_tokens"], 16000)
        self.assertTrue(payload["api_key_configured"])
        self.assertEqual(payload["api_key_mask"], "sk-t...3456")
        self.assertEqual(payload["source"], "runtime_config")
        self.assertEqual(payload["updated_by"], "user_admin")
        self.assertNotIn("sk-test-secret-123456", update_response.text)
        self.assertEqual(get_response.json()["api_key_mask"], "sk-t...3456")
        self.assertTrue(config_file_exists)

        checks = health_response.json()["dependency_checks"]
        self.assertEqual(checks["translation_provider_backend"], "openai_compatible")
        self.assertEqual(checks["openai_model"], "deepseek-v4-flash")
        self.assertTrue(checks["openai_api_key_configured"])
        self.assertTrue(checks["openai_base_url_configured"])
        self.assertEqual(checks["ai_provider_config_source"], "runtime_config")

        matching_events = [
            event
            for event in audit_events
            if event.action == "ai_provider_config.update"
        ]
        self.assertEqual(len(matching_events), 1)
        self.assertEqual(matching_events[0].actor_id, "user_admin")
        self.assertEqual(matching_events[0].trace_id, "trace_ai_provider_update")
        self.assertTrue(matching_events[0].details["api_key_configured"])
        self.assertNotIn("sk-test-secret-123456", json.dumps(matching_events[0].details, ensure_ascii=False))

    def test_mineru_config_api_updates_runtime_token_without_exposing_secret(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="old-env-token",
                mineru_uid="old-env-uid",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            old_stage_client = runtime.stage_service._build_mineru_client()
            old_document_client = runtime.document_job_execution_service._build_mineru_client()
            app = create_app(runtime)

            with TestClient(app) as client:
                anonymous_get = client.get("/api/v1/mineru-config")
                anonymous_put = client.put(
                    "/api/v1/mineru-config",
                    json={"api_token": "anonymous-token", "uid": "anonymous-uid"},
                )
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_get = client.get("/api/v1/mineru-config", headers=operator_headers)
                operator_put = client.put(
                    "/api/v1/mineru-config",
                    headers=operator_headers,
                    json={"api_token": "forbidden-token", "uid": "forbidden-uid"},
                )
                initial_get = client.get("/api/v1/mineru-config", headers=admin_headers)
                blank_update = client.put(
                    "/api/v1/mineru-config",
                    headers=admin_headers,
                    json={"api_token": "   ", "uid": "new-uid"},
                )
                blank_created_file = runtime.settings.mineru_config_file.exists()
                missing_uid_update = client.put(
                    "/api/v1/mineru-config",
                    headers=admin_headers,
                    json={"api_token": "partial-token"},
                )
                oversized_token = "oversized-secret-" + ("x" * 4096)
                oversized_update = client.put(
                    "/api/v1/mineru-config",
                    headers=admin_headers,
                    json={"api_token": oversized_token, "uid": "new-uid"},
                )
                oversized_uid = "oversized-uid-" + ("x" * 256)
                oversized_uid_update = client.put(
                    "/api/v1/mineru-config",
                    headers=admin_headers,
                    json={"api_token": "new-token", "uid": oversized_uid},
                )
                update_response = client.put(
                    "/api/v1/mineru-config",
                    headers={**admin_headers, "X-Trace-Id": "trace_mineru_config_update"},
                    json={"api_token": "  new-runtime-token  ", "uid": "  new-runtime-uid  "},
                )
                get_response = client.get("/api/v1/mineru-config", headers=admin_headers)
                health_response = client.get("/api/v1/health/ready")
                integration_response = client.get(
                    "/api/v1/ops/integration-capabilities",
                    headers=admin_headers,
                )

            new_stage_client = runtime.stage_service._build_mineru_client()
            new_document_client = runtime.document_job_execution_service._build_mineru_client()
            callback_seed = "runtime-config-uid-seed"
            callback_content = "{}"
            callback_job = JobRecord(
                id="job_runtime_config_uid",
                source_filename="source.pdf",
                status="parsing",
                mineru_callback_seed=callback_seed,
            )
            verify_mineru_callback_checksum_for_job(
                {
                    "content": callback_content,
                    "checksum": build_callback_checksum(
                        uid="new-runtime-uid",
                        seed=callback_seed,
                        content=callback_content,
                    ),
                },
                callback_job,
                runtime,
            )
            config_payload = json.loads(runtime.settings.mineru_config_file.read_text(encoding="utf-8"))
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(anonymous_get.status_code, 401)
        self.assertEqual(anonymous_put.status_code, 401)
        self.assertEqual(operator_get.status_code, 403)
        self.assertEqual(operator_put.status_code, 403)
        self.assertEqual(initial_get.status_code, 200)
        self.assertEqual(
            initial_get.json(),
            {
                "api_token_configured": True,
                "uid_configured": True,
                "source": "settings",
                "updated_at": None,
                "updated_by": None,
            },
        )
        self.assertEqual(blank_update.status_code, 422)
        self.assertFalse(blank_created_file)
        self.assertEqual(missing_uid_update.status_code, 422)
        self.assertEqual(oversized_update.status_code, 422)
        self.assertNotIn(oversized_token, oversized_update.text)
        self.assertNotIn("input", json.dumps(oversized_update.json()["detail"], ensure_ascii=False))
        self.assertEqual(oversized_uid_update.status_code, 422)
        self.assertNotIn(oversized_uid, oversized_uid_update.text)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(get_response.status_code, 200)
        response_payload = update_response.json()
        self.assertEqual(
            set(response_payload),
            {"api_token_configured", "uid_configured", "source", "updated_at", "updated_by"},
        )
        self.assertTrue(response_payload["api_token_configured"])
        self.assertTrue(response_payload["uid_configured"])
        self.assertEqual(response_payload["source"], "runtime_config")
        self.assertEqual(response_payload["updated_by"], "user_admin")
        self.assertNotIn("new-runtime-token", update_response.text)
        self.assertNotIn("new-runtime-uid", update_response.text)
        self.assertEqual(get_response.json(), response_payload)
        self.assertEqual(config_payload["api_token"], "new-runtime-token")
        self.assertEqual(config_payload["uid"], "new-runtime-uid")

        checks = health_response.json()["dependency_checks"]
        self.assertTrue(checks["mineru_api_token_configured"])
        self.assertTrue(checks["mineru_uid_configured"])
        self.assertTrue(checks["pdf_submission_available"])
        self.assertEqual(checks["mineru_config_source"], "runtime_config")
        self.assertIsNone(checks["mineru_config_error"])
        self.assertEqual(old_stage_client.api_token, "old-env-token")
        self.assertEqual(old_document_client.api_token, "old-env-token")
        self.assertEqual(old_stage_client.session.headers.get("token"), "old-env-uid")
        self.assertEqual(old_document_client.session.headers.get("token"), "old-env-uid")
        self.assertEqual(new_stage_client.api_token, "new-runtime-token")
        self.assertEqual(new_document_client.api_token, "new-runtime-token")
        self.assertEqual(new_stage_client.session.headers.get("token"), "new-runtime-uid")
        self.assertEqual(new_document_client.session.headers.get("token"), "new-runtime-uid")
        self.assertEqual(integration_response.status_code, 200)
        capabilities = {item["capability_id"]: item for item in integration_response.json()["capabilities"]}
        provider_cancellation = capabilities["provider_cancellation"]
        self.assertTrue(provider_cancellation["configured"])
        self.assertTrue(provider_cancellation["safe_config"]["mineru_api_token_configured"])

        matching_events = [event for event in audit_events if event.action == "mineru_config.update"]
        self.assertEqual(len(matching_events), 1)
        event = matching_events[0]
        self.assertEqual(event.actor_id, "user_admin")
        self.assertEqual(event.target_type, "mineru_config")
        self.assertEqual(event.target_id, "default")
        self.assertEqual(event.trace_id, "trace_mineru_config_update")
        self.assertEqual(event.details, {"api_token_configured": True, "uid_configured": True})
        self.assertNotIn("new-runtime-token", event.model_dump_json())
        self.assertNotIn("new-runtime-uid", event.model_dump_json())

    def test_mineru_config_invalid_file_blocks_without_settings_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="valid-env-token",
                mineru_uid="valid-env-uid",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            runtime.settings.mineru_config_file.parent.mkdir(parents=True, exist_ok=True)
            runtime.settings.mineru_config_file.write_text('{"api_token":', encoding="utf-8")
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                get_response = client.get("/api/v1/mineru-config", headers=admin_headers)
                health_before = client.get("/api/v1/health/ready")
                with self.assertRaisesRegex(MinerUConfigError, "配置文件"):
                    runtime.stage_service._build_mineru_client()
                invalid_callback_job = JobRecord(
                    id="job_invalid_runtime_config_uid",
                    source_filename="source.pdf",
                    status="parsing",
                    mineru_callback_seed="invalid-runtime-seed",
                )
                with self.assertRaises(MinerUConfigError):
                    verify_mineru_callback_checksum_for_job(
                        {
                            "uid": "payload-uid",
                            "content": "{}",
                            "checksum": build_callback_checksum(
                                uid="payload-uid",
                                seed="invalid-runtime-seed",
                                content="{}",
                            ),
                        },
                        invalid_callback_job,
                        runtime,
                    )
                repair_response = client.put(
                    "/api/v1/mineru-config",
                    headers=admin_headers,
                    json={"api_token": "repaired-token", "uid": "repaired-uid"},
                )
                health_after = client.get("/api/v1/health/ready")

        self.assertEqual(get_response.status_code, 503)
        self.assertEqual(get_response.json()["error_code"], "mineru_config_invalid")
        before_checks = health_before.json()["dependency_checks"]
        self.assertFalse(before_checks["mineru_api_token_configured"])
        self.assertFalse(before_checks["mineru_uid_configured"])
        self.assertFalse(before_checks["pdf_submission_available"])
        self.assertEqual(before_checks["mineru_config_source"], "runtime_config")
        self.assertEqual(before_checks["mineru_config_error"], "mineru_config_invalid")
        self.assertIn("mineru_config_invalid", before_checks["readiness_warnings"])
        self.assertNotIn("mineru_api_token_missing", before_checks["readiness_warnings"])
        self.assertEqual(repair_response.status_code, 200)
        after_checks = health_after.json()["dependency_checks"]
        self.assertTrue(after_checks["mineru_api_token_configured"])
        self.assertTrue(after_checks["mineru_uid_configured"])
        self.assertIsNone(after_checks["mineru_config_error"])

    def test_mineru_config_audit_failure_keeps_updated_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="old-token",
                mineru_uid="old-uid",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                with patch.object(runtime.audit_service, "record", side_effect=RuntimeError("audit unavailable")):
                    update_response = client.put(
                        "/api/v1/mineru-config",
                        headers=admin_headers,
                        json={
                            "api_token": "new-token-after-audit-error",
                            "uid": "new-uid-after-audit-error",
                        },
                    )
                get_response = client.get("/api/v1/mineru-config", headers=admin_headers)

            effective = runtime.mineru_config_service.get_effective_config()

        self.assertEqual(update_response.status_code, 503)
        self.assertEqual(update_response.json()["error_code"], "service_unavailable")
        self.assertIn("配置已保存", update_response.json()["detail"])
        self.assertNotIn("new-token-after-audit-error", update_response.text)
        self.assertNotIn("new-uid-after-audit-error", update_response.text)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["source"], "runtime_config")
        self.assertEqual(effective.api_token, "new-token-after-audit-error")
        self.assertEqual(effective.uid, "new-uid-after-audit-error")

    def test_health_ready_reports_invalid_ai_provider_config_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            runtime.settings.ai_provider_config_file.parent.mkdir(parents=True, exist_ok=True)
            runtime.settings.ai_provider_config_file.write_text(
                json.dumps({"backend": "bad_backend"}),
                encoding="utf-8",
            )
            checks = runtime.health_service.build_dependency_checks()

        self.assertEqual(checks["ai_provider_config_error"], "ai_provider_config_invalid")
        self.assertIn("ai_provider_config_invalid", checks["readiness_warnings"])
        self.assertNotIn("ai_provider_config_invalid", checks["readiness_blockers"])

    def test_health_ready_blocks_p0_document_jobs_in_production_when_required_config_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), app_env="prod")
            checks = runtime.health_service.build_dependency_checks()

        self.assertTrue(checks["p0_document_jobs_required"])
        self.assertFalse(checks["p0_document_jobs_ready"])
        self.assertFalse(checks["document_jobs_automatic_execution_enabled"])
        self.assertFalse(checks["deployment_init_ready"])
        self.assertIn("document_jobs_metadata_store_not_mysql", checks["p0_document_jobs_blockers"])
        self.assertIn("document_jobs_worker_backend_disabled", checks["p0_document_jobs_blockers"])
        self.assertIn("auth_jwt_secret_key_missing", checks["p0_document_jobs_blockers"])
        self.assertIn("auth_internal_users_source_missing", checks["p0_document_jobs_blockers"])
        self.assertIn("mineru_api_token_missing", checks["p0_document_jobs_blockers"])
        self.assertIn("mineru_callback_url_missing", checks["p0_document_jobs_blockers"])
        self.assertIn("document_jobs_metadata_store_not_mysql", checks["readiness_blockers"])
        self.assertIn("document_jobs_worker_backend_disabled", checks["readiness_blockers"])

    def test_health_ready_blocks_p0_document_jobs_when_production_uses_non_mysql_metadata_store(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                app_env="prod",
                document_jobs_worker_backend="celery",
                document_jobs_celery_broker_url="redis://redis:6379/0",
                document_jobs_celery_queue="document-jobs",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                mineru_api_token="token-123",
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            runtime.settings.jobs_dir.mkdir(parents=True, exist_ok=True)
            runtime.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
            checks = runtime.health_service.build_dependency_checks()

        self.assertTrue(checks["p0_document_jobs_required"])
        self.assertFalse(checks["p0_document_jobs_ready"])
        self.assertTrue(checks["document_jobs_automatic_execution_enabled"])
        self.assertEqual(checks["p0_document_jobs_blockers"], ["document_jobs_metadata_store_not_mysql"])
        self.assertFalse(checks["deployment_init_ready"])
        self.assertIn("document_jobs_metadata_store_not_mysql", checks["readiness_blockers"])

    def test_health_ready_blocks_p0_document_jobs_when_production_uses_eager_worker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                app_env="prod",
                document_jobs_worker_backend="eager",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                mineru_api_token="token-123",
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            checks = runtime.health_service.build_dependency_checks()

        self.assertTrue(checks["p0_document_jobs_required"])
        self.assertFalse(checks["p0_document_jobs_ready"])
        self.assertTrue(checks["document_jobs_automatic_execution_enabled"])
        self.assertEqual(checks["p0_document_jobs_blockers"], ["document_jobs_worker_backend_eager_in_production"])
        self.assertFalse(checks["deployment_init_ready"])
        self.assertIn("document_jobs_worker_backend_eager_in_production", checks["readiness_blockers"])

    def test_health_ready_blocks_celery_when_translation_batch_queue_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                app_env="prod",
                document_jobs_worker_backend="celery",
                document_jobs_celery_broker_url="redis://redis:6379/0",
                document_jobs_celery_queue="document-jobs",
                document_jobs_translation_batch_celery_queue="",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                mineru_api_token="token-123",
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            checks = runtime.health_service.build_dependency_checks()

        self.assertTrue(checks["p0_document_jobs_required"])
        self.assertFalse(checks["p0_document_jobs_ready"])
        self.assertEqual(
            checks["p0_document_jobs_blockers"],
            ["document_jobs_translation_batch_celery_queue_missing"],
        )
        self.assertIn(
            "document_jobs_translation_batch_celery_queue_missing",
            checks["readiness_blockers"],
        )

    def test_health_ready_allows_p0_document_jobs_when_production_config_is_complete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                app_env="prod",
                document_jobs_worker_backend="celery",
                document_jobs_celery_broker_url="redis://redis:6379/0",
                document_jobs_celery_queue="document-jobs",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                mineru_api_token="token-123",
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            runtime.settings.jobs_dir.mkdir(parents=True, exist_ok=True)
            runtime.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
            checks = runtime.health_service.build_dependency_checks()

        self.assertEqual(checks["effective_repository_backend"], "mysql")
        self.assertTrue(checks["p0_document_jobs_required"])
        self.assertTrue(checks["p0_document_jobs_ready"])
        self.assertTrue(checks["document_jobs_automatic_execution_enabled"])
        self.assertEqual(checks["p0_document_jobs_blockers"], [])
        self.assertTrue(checks["deployment_init_ready"])
        self.assertNotIn("document_jobs_metadata_store_not_mysql", checks["readiness_blockers"])
        self.assertNotIn("document_jobs_worker_backend_disabled", checks["readiness_blockers"])
        self.assertNotIn("auth_jwt_secret_key_missing", checks["readiness_blockers"])

    def test_build_runtime_blocks_open_jobs_access_in_production_like_deployments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                data_dir=temp_dir,
                app_env="prod",
                jobs_access_mode="open",
            )
            with self.assertRaisesRegex(RuntimeError, "JOBS_ACCESS_MODE=open"):
                build_runtime(settings)

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                data_dir=temp_dir,
                app_env="dev",
                public_deployment_mode="single_tenant_public",
                jobs_access_mode="open",
            )
            with self.assertRaisesRegex(RuntimeError, "JOBS_ACCESS_MODE=open"):
                build_runtime(settings)

    def test_config_workbench_summary_is_admin_only_and_reports_file_mode_unavailable_groups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_response = client.get("/api/v1/config-workbench/summary", headers=operator_headers)
                admin_response = client.get("/api/v1/config-workbench/summary", headers=admin_headers)

        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        groups = {item["id"]: item for item in payload["groups"]}
        self.assertEqual(payload["release_gate"]["p0_document_jobs_required"], False)
        self.assertEqual(payload["release_gate"]["p0_document_jobs_ready"], True)
        self.assertIn("blocker_findings", payload["release_gate"])
        self.assertEqual(groups["runtime_readiness"]["detail_status"], "complete")
        self.assertEqual(groups["runtime_readiness"]["route"], "/system-status")
        self.assertEqual(groups["term_rule_sets"]["status"], "unavailable")
        self.assertEqual(groups["translation_profiles"]["status"], "unavailable")
        self.assertEqual(groups["translation_term_sets"]["status"], "unavailable")
        self.assertNotIn("test-jwt-secret", json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("admin-pass", json.dumps(payload, ensure_ascii=False))

    def test_config_workbench_summary_reports_p0_blockers_in_production(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                app_env="prod",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.get("/api/v1/config-workbench/summary", headers=admin_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        blockers = payload["release_gate"]["blockers"]
        groups = {item["id"]: item for item in payload["groups"]}
        self.assertEqual(payload["overall_status"], "blocked")
        self.assertTrue(payload["release_gate"]["p0_document_jobs_required"])
        self.assertFalse(payload["release_gate"]["p0_document_jobs_ready"])
        self.assertIn("document_jobs_metadata_store_not_mysql", blockers)
        self.assertIn("document_jobs_worker_backend_disabled", blockers)
        self.assertIn("mineru_api_token_missing", blockers)
        self.assertIn("mineru_uid_missing", blockers)
        blocker_findings = payload["release_gate"]["blocker_findings"]
        self.assertIn("p0.document_jobs_metadata_store_not_mysql", [item["code"] for item in blocker_findings])
        self.assertIn("p0.document_jobs_worker_backend_disabled", [item["code"] for item in blocker_findings])
        self.assertTrue(any("MySQL" in item["message"] for item in blocker_findings))
        self.assertTrue(any("文档任务执行器" in item["message"] for item in blocker_findings))
        token_finding = next(item for item in blocker_findings if item["code"] == "p0.mineru_api_token_missing")
        self.assertEqual(token_finding["route"], "/settings/mineru")
        uid_finding = next(item for item in blocker_findings if item["code"] == "p0.mineru_uid_missing")
        self.assertEqual(uid_finding["route"], "/settings/mineru")
        self.assertEqual(groups["runtime_readiness"]["status"], "blocked")
        self.assertNotIn("test-jwt-secret", json.dumps(payload, ensure_ascii=False))

    def test_config_workbench_summary_reports_versioned_mysql_configuration_groups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            publish_default_job_resources(runtime, include_translation=True)
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.get("/api/v1/config-workbench/summary", headers=admin_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        groups = {item["id"]: item for item in payload["groups"]}
        self.assertNotEqual(groups["term_rule_sets"]["status"], "unavailable")
        self.assertNotEqual(groups["translation_profiles"]["status"], "unavailable")
        self.assertNotEqual(groups["translation_term_sets"]["status"], "unavailable")
        self.assertEqual(groups["templates"]["default_label"], "default@1")
        self.assertEqual(groups["term_rule_sets"]["default_label"], "electronics-default@1")
        self.assertEqual(groups["term_rule_sets"]["detail_status"], "complete")
        self.assertEqual(groups["translation_profiles"]["default_label"], "electronics-en2zh@1")
        self.assertTrue(groups["translation_term_sets"]["default_label"].startswith("translation-terms-en2zh@"))
        self.assertEqual(groups["translation_term_sets"]["detail_status"], "complete")
        self.assertNotIn("test-jwt-secret", json.dumps(payload, ensure_ascii=False))

    def test_config_workbench_overview_defers_deep_resource_checks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            publish_default_job_resources(runtime, include_translation=True)

            def fail_deep_check(*_args, **_kwargs):
                raise AssertionError("overview must not call deep config workbench checks")

            runtime.term_rule_set_version_service.build_preflight = fail_deep_check
            runtime.translation_term_set_version_service.get_preflight_response = fail_deep_check
            runtime.translation_term_set_version_service.get_proposal_compatibility_response = fail_deep_check

            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.get("/api/v1/config-workbench/summary?mode=overview", headers=admin_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        groups = {item["id"]: item for item in payload["groups"]}
        self.assertEqual(groups["term_rule_sets"]["detail_status"], "deferred")
        self.assertEqual(groups["translation_term_sets"]["detail_status"], "deferred")

    def test_config_workbench_group_endpoint_returns_full_group_detail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            publish_default_job_resources(runtime, include_translation=True)
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.get(
                    "/api/v1/config-workbench/groups/translation_term_sets",
                    headers=admin_headers,
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], "translation_term_sets")
        self.assertEqual(payload["detail_status"], "complete")
        self.assertNotEqual(payload["status"], "unavailable")

    def test_health_metrics_reports_runtime_counters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "direct_pdf_to_word",
                    },
                )
                response = client.get("/api/v1/health/metrics")

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["deployment"]["environment"], "dev")
        self.assertEqual(payload["deployment"]["version"], "dev")
        self.assertIsNone(payload["deployment"]["deployment_id"])
        self.assertTrue(payload["deployment"]["started_at"])
        self.assertEqual(payload["metadata_store"], "file")
        self.assertEqual(payload["artifact_storage"], "local_file")
        self.assertEqual(payload["worker_mode"], "in_process")
        self.assertEqual(payload["stage_dispatcher"], "background_tasks")
        self.assertEqual(payload["jobs"], {})
        self.assertEqual(payload["document_jobs"], {"pending": 1})
        self.assertEqual(payload["stage_messages"], {"pending": 0, "running": 0, "failed": 0})
        self.assertEqual(payload["resources"]["template_versions"], 0)
        self.assertGreaterEqual(payload["audit_events"]["total"], 1)
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("ADMIN_TOKEN", serialized)

    def test_audit_events_api_filters_sorts_and_paginates_for_admin(self):
        """验证 Admin 可按稳定审计字段筛选、排序和分页查询审计事件。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            base_time = utc_now()
            runtime.audit_event_repository.append_audit_event(
                AuditEvent(
                    audit_id="audit_archive_old",
                    actor_id="user_operator",
                    actor_role="operator",
                    action="document_job.archive",
                    target_type="document_job",
                    target_id="job_archive",
                    reason="archive terminal job",
                    trace_id="trace_archive",
                    created_at=base_time - timedelta(minutes=3),
                )
            )
            runtime.audit_event_repository.append_audit_event(
                AuditEvent(
                    audit_id="audit_retry_mid",
                    actor_id="user_admin",
                    actor_role="admin",
                    action="document_job.retry",
                    target_type="document_job",
                    target_id="job_retry",
                    reason="rerun issue",
                    details={
                        "workflow": "manual_retry",
                        "evidence": {"source": "audit-details-search"},
                    },
                    trace_id="trace_retry",
                    created_at=base_time - timedelta(minutes=2),
                )
            )
            runtime.audit_event_repository.append_audit_event(
                AuditEvent(
                    audit_id="audit_retention_new",
                    actor_id="user_admin",
                    actor_role="admin",
                    action="file.retention_mark_expired",
                    target_type="document_file_retention",
                    target_id="document_files",
                    reason="marked=1 candidates=1",
                    trace_id="trace_retention",
                    created_at=base_time - timedelta(minutes=1),
                )
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                page_response = client.get(
                    "/api/v1/audit-events",
                    headers=admin_headers,
                    params={
                        "target_type": "document_job",
                        "sort": "created_at_asc",
                        "page": 2,
                        "page_size": 1,
                    },
                )
                filter_response = client.get(
                    "/api/v1/audit-events",
                    headers=admin_headers,
                    params={
                        "actor_role": "admin",
                        "actor_id": "user_admin",
                        "action": "document_job.retry",
                        "target_id": "job_retry",
                        "q": "audit-details-search",
                        "created_from": (base_time - timedelta(minutes=2, seconds=30)).isoformat(),
                        "created_to": (base_time - timedelta(minutes=1, seconds=30)).isoformat(),
                    },
                )

        self.assertEqual(page_response.status_code, 200)
        page_payload = page_response.json()
        self.assertEqual(page_payload["total"], 2)
        self.assertEqual(page_payload["page"], 2)
        self.assertEqual(page_payload["page_size"], 1)
        self.assertEqual([item["audit_id"] for item in page_payload["items"]], ["audit_retry_mid"])

        self.assertEqual(filter_response.status_code, 200)
        filter_payload = filter_response.json()
        self.assertEqual(filter_payload["total"], 1)
        self.assertEqual(filter_payload["items"][0]["audit_id"], "audit_retry_mid")
        self.assertEqual(filter_payload["items"][0]["reason"], "rerun issue")
        self.assertEqual(filter_payload["items"][0]["details"]["workflow"], "manual_retry")
        self.assertEqual(filter_payload["items"][0]["details"]["evidence"]["source"], "audit-details-search")

    def test_audit_events_api_rejects_operator(self):
        """验证 Operator 不能访问 Admin-only 审计事件查询接口。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                response = client.get("/api/v1/audit-events", headers=operator_headers)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error_code"], "role_forbidden")

    def test_audit_events_export_api_is_admin_only_bounded_and_audited(self):
        """验证 Admin 可按当前筛选导出受限 CSV，且导出动作写入审计。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            base_time = utc_now()
            runtime.audit_event_repository.append_audit_event(
                AuditEvent(
                    audit_id="audit_archive_old",
                    actor_id="user_operator",
                    actor_role="operator",
                    action="document_job.archive",
                    target_type="document_job",
                    target_id="job_archive",
                    reason="archive, \"terminal\"\njob",
                    details={
                        "operation": "archive",
                        "counts": {"files": 0, "events": 1},
                    },
                    trace_id="trace_archive",
                    created_at=base_time - timedelta(minutes=3),
                )
            )
            runtime.audit_event_repository.append_audit_event(
                AuditEvent(
                    audit_id="audit_retry_mid",
                    actor_id="user_admin",
                    actor_role="admin",
                    action="document_job.retry",
                    target_type="document_job",
                    target_id="job_retry",
                    reason="rerun issue",
                    trace_id="trace_retry",
                    created_at=base_time - timedelta(minutes=2),
                )
            )
            runtime.audit_event_repository.append_audit_event(
                AuditEvent(
                    audit_id="audit_retention_new",
                    actor_id="user_admin",
                    actor_role="admin",
                    action="file.retention_mark_expired",
                    target_type="document_file_retention",
                    target_id="document_files",
                    reason="marked=1 candidates=1",
                    trace_id="trace_retention",
                    created_at=base_time - timedelta(minutes=1),
                )
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.get(
                    "/api/v1/audit-events/export",
                    headers=admin_headers,
                    params={
                        "target_type": "document_job",
                        "sort": "created_at_asc",
                        "max_rows": 1,
                    },
                )
                over_cap_response = client.get(
                    "/api/v1/audit-events/export",
                    headers=admin_headers,
                    params={"target_type": "document_job", "max_rows": 10001},
                )
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(over_cap_response.status_code, 422)
        payload = response.json()
        manifest = payload["manifest"]
        rows = list(csv.DictReader(io.StringIO(payload["csv_text"])))
        export_events = [event for event in audit_events if event.action == "audit_events.export"]

        self.assertEqual(manifest["requested_by"], "user_admin")
        self.assertEqual(manifest["filters"], {"target_type": "document_job"})
        self.assertEqual(manifest["matched_count"], 2)
        self.assertEqual(manifest["exported_count"], 1)
        self.assertEqual(manifest["max_rows"], 1)
        self.assertEqual(manifest["truncated"], True)
        self.assertEqual(manifest["columns"][0], "created_at")
        self.assertIn("details_json", manifest["columns"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["audit_id"], "audit_archive_old")
        self.assertEqual(rows[0]["reason"], "archive, \"terminal\"\njob")
        self.assertEqual(
            rows[0]["details_json"],
            '{"counts":{"events":1,"files":0},"operation":"archive"}',
        )
        self.assertEqual(len(export_events), 1)
        self.assertEqual(export_events[0].audit_id, manifest["audit_id"])
        self.assertEqual(export_events[0].actor_id, "user_admin")
        self.assertEqual(export_events[0].target_type, "audit_events")
        self.assertIn("exported=1 matched=2", export_events[0].reason or "")
        self.assertEqual(export_events[0].details["matched_count"], 2)
        self.assertEqual(export_events[0].details["exported_count"], 1)
        self.assertEqual(export_events[0].details["filters"], {"target_type": "document_job"})
        self.assertNotEqual(rows[0]["audit_id"], export_events[0].audit_id)

    def test_audit_events_export_api_rejects_operator(self):
        """验证 Operator 不能调用审计导出接口，且不会写导出审计事件。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                response = client.get("/api/v1/audit-events/export", headers=operator_headers)
            export_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "audit_events.export"
            ]

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error_code"], "role_forbidden")
        self.assertEqual(export_events, [])

    def test_health_metrics_reports_default_resource_versions_in_mysql_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(Path(temp_dir))
            publish_default_job_resources(runtime, include_translation=True)
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.get("/api/v1/health/metrics")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["metadata_store"], "mysql")
        self.assertEqual(payload["resources"]["template_versions"], 1)
        self.assertEqual(payload["resources"]["term_rule_set_versions"], 2)
        self.assertEqual(payload["resources"]["translation_profile_versions"], 2)
        self.assertEqual(payload["resources"]["default_template_version"], "default@1")
        self.assertEqual(payload["resources"]["default_term_rule_version"], "electronics-default@1")
        self.assertEqual(payload["resources"]["default_translation_profile_version"], "electronics-en2zh@1")

    def test_health_ready_reports_stage_spool_status_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_health_pending",
                    job_id="job_health",
                    stage="convert_package",
                    trace_id="trace_health",
                    status="pending",
                )
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_health_running",
                    job_id="job_health",
                    stage="submit_to_mineru",
                    trace_id="trace_health",
                    status="running",
                    updated_at=utc_now() - timedelta(seconds=1200),
                    lease_expires_at=utc_now() - timedelta(seconds=1),
                )
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_health_failed",
                    job_id="job_health",
                    stage="process_callback",
                    trace_id="trace_health",
                    status="failed",
                )
            )
            checks = runtime.health_service.build_dependency_checks()

        self.assertEqual(checks["stage_spool_pending_messages"], 1)
        self.assertEqual(checks["stage_spool_running_messages"], 1)
        self.assertEqual(checks["stage_spool_failed_messages"], 1)
        self.assertEqual(checks["stage_spool_replayable_messages"], 2)
        self.assertEqual(checks["stage_spool_running_stale_messages"], 1)
        self.assertGreaterEqual(checks["stage_spool_oldest_running_age_seconds"], 1199)
        self.assertTrue(checks["stage_spool_needs_attention"])
        self.assertEqual(checks["stage_spool_observation_status"], "needs_attention")
        self.assertIn("stage_spool_replayable_messages_present", checks["readiness_warnings"])
        self.assertIn("stage_spool_failed_messages_present", checks["readiness_warnings"])
        self.assertIn("stage_spool_stale_running_messages_present", checks["readiness_warnings"])

    def test_health_ops_alerts_is_admin_only_readonly_and_reports_recovery_readiness(self):
        """验证 ops-alerts 只允许 Admin 读取，并只返回恢复建议不执行动作。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_worker_mode="external",
                admin_token="secret-admin",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            now = utc_now()
            runtime.document_job_repository.create_document_job(
                DocumentJobRecord(
                    id="docjob_ops_failed",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    created_by="user_operator",
                    source_file_id="file_ops_failed",
                    status="failed",
                    stage="failed",
                    progress=30,
                    template_version_id="template_default",
                    failed_stage="parsing",
                    error_code="parse_failed",
                    error_message="parse failed",
                    updated_at=now - timedelta(minutes=2),
                )
            )
            runtime.document_job_repository.create_document_job(
                DocumentJobRecord(
                    id="docjob_ops_running",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    created_by="user_operator",
                    source_file_id="file_ops_running",
                    status="running",
                    stage="parsing",
                    progress=25,
                    template_version_id="template_default",
                    started_at=now - timedelta(minutes=3),
                    updated_at=now - timedelta(minutes=1),
                )
            )
            runtime.document_job_repository.create_document_job(
                DocumentJobRecord(
                    id="docjob_ops_timed_out",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    created_by="user_operator",
                    source_file_id="file_ops_timed_out",
                    status="running",
                    stage="parsing",
                    progress=10,
                    template_version_id="template_default",
                    started_at=now - timedelta(minutes=20),
                    timeout_at=now - timedelta(seconds=1),
                    updated_at=now - timedelta(minutes=20),
                )
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_ops_pending",
                    job_id="docjob_ops_running",
                    stage="submit_to_mineru",
                    trace_id="trace_ops_pending",
                    status="pending",
                )
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_ops_running_stale",
                    job_id="docjob_ops_running",
                    stage="process_callback",
                    trace_id="trace_ops_running_stale",
                    status="running",
                    updated_at=now - timedelta(seconds=1200),
                    lease_expires_at=now - timedelta(seconds=1),
                )
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_ops_failed",
                    job_id="docjob_ops_failed",
                    stage="convert_package",
                    trace_id="trace_ops_failed",
                    status="failed",
                )
            )
            runtime.document_job_callback_message_store.put_or_get_callback_message(
                DocumentJobCallbackMessage(
                    id="doccb_ops_pending",
                    job_id="docjob_ops_running",
                    status="pending",
                    dedupe_key="doccb_ops_pending",
                    payload={"state": "done"},
                    created_at=now - timedelta(seconds=900),
                    updated_at=now - timedelta(seconds=900),
                )
            )
            runtime.document_job_callback_message_store.put_or_get_callback_message(
                DocumentJobCallbackMessage(
                    id="doccb_ops_failed",
                    job_id="docjob_ops_running",
                    status="failed",
                    dedupe_key="doccb_ops_failed",
                    payload={"state": "done"},
                    error_code="callback_failed",
                    error_message="callback failed",
                    created_at=now - timedelta(seconds=30),
                    updated_at=now - timedelta(seconds=30),
                )
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                admin_response = client.get("/api/v1/health/ops-alerts", headers=admin_headers)
                legacy_admin_response = client.get("/api/v1/health/ops-alerts", headers={"X-Admin-Token": "secret-admin"})
                operator_response = client.get("/api/v1/health/ops-alerts", headers=operator_headers)
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(legacy_admin_response.status_code, 200)
        self.assertEqual(legacy_admin_response.json()["safety"]["read_only"], True)
        payload = admin_response.json()
        self.assertEqual(payload["status"], "needs_attention")
        self.assertEqual(payload["summary"]["stage_failed_messages"], 1)
        self.assertEqual(payload["summary"]["stage_stale_running_messages"], 1)
        self.assertEqual(payload["summary"]["stage_replayable_messages"], 2)
        self.assertEqual(payload["summary"]["callback_failed_messages"], 1)
        self.assertEqual(payload["summary"]["callback_replayable_messages"], 1)
        self.assertGreaterEqual(payload["summary"]["callback_oldest_replayable_age_seconds"], 899)
        self.assertEqual(payload["summary"]["failed_jobs"], 1)
        self.assertEqual(payload["summary"]["running_jobs"], 2)
        self.assertTrue(payload["safety"]["read_only"])
        self.assertFalse(payload["safety"]["writes_performed"])
        self.assertFalse(payload["safety"]["recovery_actions_executed"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["notification_delivery_executed"])
        self.assertFalse(payload["safety"]["audit_events_written"])

        alerts_by_code = {item["code"]: item for item in payload["alerts"]}
        self.assertIn("readiness_warnings_present", alerts_by_code)
        self.assertIn("stage_spool_failed_messages_present", alerts_by_code)
        self.assertIn("stage_spool_stale_running_messages_present", alerts_by_code)
        self.assertIn("stage_spool_replayable_messages_present", alerts_by_code)
        self.assertIn("document_jobs_failed_present", alerts_by_code)
        self.assertIn("document_jobs_timed_out_present", alerts_by_code)
        self.assertIn("document_jobs_stale_running_present", alerts_by_code)
        self.assertIn("document_jobs_running_present", alerts_by_code)
        self.assertIn("document_job_callback_failed_messages_present", alerts_by_code)
        self.assertIn("document_job_callback_replayable_messages_present", alerts_by_code)
        self.assertIn("document_job_callback_oldest_replayable_stale", alerts_by_code)
        self.assertEqual(alerts_by_code["stage_spool_failed_messages_present"]["severity"], "critical")
        self.assertEqual(alerts_by_code["stage_spool_failed_messages_present"]["source"], "stage_spool")
        self.assertEqual(alerts_by_code["document_jobs_failed_present"]["source"], "jobs")
        self.assertEqual(
            alerts_by_code["document_job_callback_failed_messages_present"]["source"],
            "document_job_callbacks",
        )
        self.assertEqual(alerts_by_code["document_jobs_timed_out_present"]["severity"], "critical")
        self.assertEqual(alerts_by_code["document_jobs_stale_running_present"]["severity"], "warning")
        self.assertEqual(alerts_by_code["document_jobs_running_present"]["severity"], "info")
        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(audit_actions_after, audit_actions_before)

    def test_ops_recovery_action_registry_is_admin_only_readonly_and_lists_safety_flags(self):
        """验证 recovery action registry 只允许 Admin 读取，并暴露候选动作安全边界。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                admin_response = client.get("/api/v1/ops/recovery-actions", headers=admin_headers)
                operator_response = client.get("/api/v1/ops/recovery-actions", headers=operator_headers)
                candidate_preview_response = client.post(
                    "/api/v1/ops/recovery-actions/preview",
                    headers=admin_headers,
                    json={
                        "action_id": "provider.cancel",
                        "target_type": "provider_operation",
                        "target_id": "provider_batch_001",
                    },
                )
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertTrue(payload["safety"]["read_only"])
        self.assertFalse(payload["safety"]["execution_performed"])
        self.assertFalse(payload["safety"]["metadata_mutated"])
        self.assertFalse(payload["safety"]["queue_mutated"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["notification_delivery_executed"])
        self.assertFalse(payload["safety"]["cleanup_executed"])
        self.assertFalse(payload["safety"]["delete_executed"])
        self.assertFalse(payload["safety"]["audit_events_written"])

        actions_by_id = {item["action_id"]: item for item in payload["actions"]}
        self.assertEqual(
            set(actions_by_id),
            {
                "document_job.replay_execution",
                "document_job.retry",
                "document_job.cancel",
                "document_job.archive",
                "provider.cancel",
                "alert.delivery",
                "file_retention.automated_cleanup_execute",
            },
        )
        self.assertTrue(actions_by_id["document_job.retry"]["available"])
        self.assertTrue(actions_by_id["document_job.replay_execution"]["available"])
        self.assertTrue(actions_by_id["document_job.replay_execution"]["requires_reason"])
        self.assertTrue(actions_by_id["document_job.replay_execution"]["mutates_metadata"])
        self.assertTrue(actions_by_id["document_job.replay_execution"]["mutates_queue"])
        self.assertFalse(actions_by_id["document_job.replay_execution"]["calls_provider"])
        self.assertEqual(
            actions_by_id["document_job.replay_execution"]["audit_action"],
            "document_job.replay_execution",
        )
        self.assertTrue(actions_by_id["document_job.retry"]["requires_admin"])
        self.assertTrue(actions_by_id["document_job.retry"]["requires_reason"])
        self.assertTrue(actions_by_id["document_job.retry"]["mutates_metadata"])
        self.assertTrue(actions_by_id["document_job.retry"]["mutates_queue"])
        self.assertFalse(actions_by_id["document_job.retry"]["calls_provider"])
        self.assertTrue(actions_by_id["provider.cancel"]["available"])
        self.assertTrue(actions_by_id["provider.cancel"]["requires_reason"])
        self.assertTrue(actions_by_id["provider.cancel"]["requires_confirmation"])
        self.assertFalse(actions_by_id["provider.cancel"]["calls_provider"])
        self.assertEqual(actions_by_id["provider.cancel"]["audit_action"], "ops.provider_cancellation_fake")
        self.assertTrue(actions_by_id["alert.delivery"]["available"])
        self.assertTrue(actions_by_id["alert.delivery"]["requires_reason"])
        self.assertTrue(actions_by_id["alert.delivery"]["requires_confirmation"])
        self.assertFalse(actions_by_id["alert.delivery"]["sends_notification"])
        self.assertEqual(actions_by_id["alert.delivery"]["audit_action"], "ops.alert_delivery_fake")
        self.assertTrue(actions_by_id["file_retention.automated_cleanup_execute"]["available"])
        self.assertEqual(
            actions_by_id["file_retention.automated_cleanup_execute"]["audit_action"],
            "file.retention_automated_cleanup_execute",
        )
        self.assertTrue(actions_by_id["file_retention.automated_cleanup_execute"]["deletes_data"])

        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(candidate_preview_response.status_code, 200)
        candidate_preview = candidate_preview_response.json()
        self.assertFalse(candidate_preview["eligible"])
        self.assertIn("use_dedicated_execution_endpoint", candidate_preview["missing_gates"])
        self.assertFalse(candidate_preview["risk_flags"]["calls_provider"])
        self.assertFalse(candidate_preview["safety"]["provider_calls_executed"])
        self.assertEqual(audit_actions_after, audit_actions_before)

    def test_ops_alert_delivery_preview_is_admin_only_and_readonly(self):
        """验证 Ops alert delivery preview 只允许 Admin 且不写审计或外发通知。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_alert_delivery_preview_failed",
                    job_id="docjob_alert_delivery",
                    stage="convert_package",
                    trace_id="trace_alert_delivery_preview",
                    status="failed",
                )
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                admin_response = client.post(
                    "/api/v1/ops/alert-deliveries/preview",
                    headers=admin_headers,
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "channel": "local_outbox",
                        "dedupe_window_minutes": 60,
                    },
                )
                operator_response = client.post(
                    "/api/v1/ops/alert-deliveries/preview",
                    headers=operator_headers,
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "channel": "local_outbox",
                    },
                )
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "dry_run")
        self.assertEqual(payload["confirmation_phrase"], "SEND FAKE OPS ALERTS")
        self.assertEqual(payload["totals"]["deliverable"], 1)
        self.assertEqual(payload["items"][0]["outcome"], "deliverable")
        self.assertFalse(payload["items"][0]["audit_event_written"])
        self.assertFalse(payload["safety"]["external_delivery_executed"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(audit_actions_after, audit_actions_before)

    def test_ops_alert_delivery_adapter_contract_is_admin_only_readonly_and_blocks_real_send(self):
        """验证 alert delivery adapter contract 只读，并且真实发送能力仍保持 blocked。"""

        destination_config = [
            {
                "destination_id": "ops-webhook-primary",
                "channel": "webhook",
                "enabled": True,
                "secret_ref": "OPS_WEBHOOK_SECRET",
                "secret_value": "should-not-leak",
                "target_label": "ops-webhook",
                "allowlist": ["stage_spool_failed_messages_present"],
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                ops_alert_destinations_json=json.dumps(destination_config),
                integration_alert_delivery_enabled=True,
                integration_alert_delivery_dry_run=False,
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                admin_response = client.get(
                    "/api/v1/ops/alert-deliveries/adapter-contract",
                    headers=admin_headers,
                )
                operator_response = client.get(
                    "/api/v1/ops/alert-deliveries/adapter-contract",
                    headers=operator_headers,
                )
                capabilities_response = client.get(
                    "/api/v1/ops/integration-capabilities",
                    headers=admin_headers,
                )
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "adapter_contract")
        self.assertEqual(payload["contract_version"], "ops-alert-delivery-adapter-v1")
        self.assertEqual(payload["fake_adapter_id"], "local_outbox_fake")
        self.assertEqual(payload["fake_adapter_mode"], "fake")
        self.assertEqual(set(payload["real_channels"]), {"slack", "email", "webhook"})
        self.assertEqual(payload["destination_count"], 1)
        self.assertEqual(payload["destination_channels"], ["webhook"])
        self.assertTrue(payload["parity_checks"]["fake_uses_same_contract_version"])
        self.assertTrue(payload["parity_checks"]["fake_records_structured_audit_details"])
        self.assertTrue(payload["parity_checks"]["fake_never_calls_provider"])
        self.assertIn("idempotency_key", payload["required_request_fields"])
        self.assertIn("adapter_result", payload["required_audit_fields"])
        self.assertIn("real_send_requires_explicit_endpoint_and_confirmation", payload["blocking_reasons"])
        self.assertTrue(payload["safety"]["read_only"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["external_delivery_executed"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertFalse(payload["safety"]["secret_values_exposed"])
        self.assertNotIn("should-not-leak", admin_response.text)

        capabilities = {
            item["capability_id"]: item
            for item in capabilities_response.json()["capabilities"]
        }
        alert_delivery = capabilities["alert_delivery"]
        self.assertEqual(alert_delivery["status"], "blocked")
        self.assertTrue(alert_delivery["real_execution_enabled"])
        self.assertFalse(alert_delivery["ready"])
        self.assertEqual(alert_delivery["safe_config"]["adapter_contract_version"], "ops-alert-delivery-adapter-v1")
        self.assertTrue(alert_delivery["safe_config"]["fake_adapter_parity"])
        self.assertTrue(alert_delivery["safe_config"]["real_delivery_adapter_implemented"])
        self.assertFalse(alert_delivery["safe_config"]["pilot_destination_ready"])
        self.assertIn("phase7_slack_pilot_destination_not_configured", alert_delivery["blocking_reasons"])
        self.assertEqual(audit_actions_after, audit_actions_before)

    def test_ops_alert_delivery_fake_send_audits_and_dedupes_without_external_delivery(self):
        """验证 fake alert delivery 写一次审计，dedupe 窗口内重复请求不重复写。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_alert_delivery_fake_failed",
                    job_id="docjob_alert_delivery",
                    stage="convert_package",
                    trace_id="trace_alert_delivery_fake",
                    status="failed",
                )
            )
            app = create_app(runtime)
            payload = {
                "alert_codes": ["stage_spool_failed_messages_present"],
                "channel": "local_outbox",
                "reason": "ops drill",
                "confirmation": "SEND FAKE OPS ALERTS",
                "dedupe_window_minutes": 60,
            }
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                first_response = client.post(
                    "/api/v1/ops/alert-deliveries/fake-send",
                    headers={**admin_headers, "X-Trace-Id": "trace_alert_delivery_fake"},
                    json=payload,
                )
                second_response = client.post(
                    "/api/v1/ops/alert-deliveries/fake-send",
                    headers=admin_headers,
                    json=payload,
                )
            delivery_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "ops.alert_delivery_fake"
            ]

        self.assertEqual(first_response.status_code, 200)
        first_payload = first_response.json()
        self.assertEqual(first_payload["action_mode"], "fake_send")
        self.assertEqual(first_payload["totals"]["fake_delivered"], 1)
        self.assertEqual(first_payload["totals"]["audit_events_written"], 1)
        self.assertEqual(first_payload["items"][0]["outcome"], "fake_delivered")
        self.assertTrue(first_payload["items"][0]["audit_event_written"])
        self.assertFalse(first_payload["safety"]["external_delivery_executed"])
        self.assertFalse(first_payload["safety"]["provider_calls_executed"])
        self.assertTrue(first_payload["safety"]["audit_events_written"])

        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.json()
        self.assertEqual(second_payload["totals"]["deduped"], 1)
        self.assertEqual(second_payload["totals"]["audit_events_written"], 0)
        self.assertEqual(second_payload["items"][0]["outcome"], "deduped")
        self.assertFalse(second_payload["items"][0]["audit_event_written"])
        self.assertFalse(second_payload["safety"]["audit_events_written"])

        self.assertEqual(len(delivery_events), 1)
        self.assertEqual(delivery_events[0].trace_id, "trace_alert_delivery_fake")
        self.assertIn("stage_spool_failed_messages_present:local_outbox", delivery_events[0].reason)
        self.assertIn("fake_delivered=1", delivery_events[0].reason)
        self.assertIsNotNone(delivery_events[0].details)
        self.assertEqual(delivery_events[0].details["delivery_id"], first_payload["delivery_id"])
        self.assertEqual(delivery_events[0].details["channel"], "local_outbox")
        self.assertEqual(delivery_events[0].details["totals"]["fake_delivered"], 1)
        self.assertFalse(delivery_events[0].details["safety"]["external_delivery_executed"])
        self.assertEqual(
            delivery_events[0].details["items"][0]["alert_code"],
            "stage_spool_failed_messages_present",
        )

    def test_ops_alert_delivery_fake_send_includes_adapter_contract_parity_in_audit(self):
        """验证 fake-send response 和 audit details 都包含同版 adapter contract 证据。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_alert_delivery_contract_failed",
                    job_id="docjob_alert_delivery_contract",
                    stage="convert_package",
                    trace_id="trace_alert_delivery_contract",
                    status="failed",
                )
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.post(
                    "/api/v1/ops/alert-deliveries/fake-send",
                    headers={**admin_headers, "X-Trace-Id": "trace_alert_delivery_contract"},
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "channel": "local_outbox",
                        "reason": "adapter contract parity drill",
                        "confirmation": "SEND FAKE OPS ALERTS",
                    },
                )
            delivery_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "ops.alert_delivery_fake"
            ]

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        adapter_result = payload["items"][0]["adapter_result"]
        self.assertEqual(adapter_result["contract_version"], "ops-alert-delivery-adapter-v1")
        self.assertEqual(adapter_result["adapter_id"], "local_outbox_fake")
        self.assertEqual(adapter_result["adapter_mode"], "fake")
        self.assertEqual(adapter_result["channel"], "local_outbox")
        self.assertEqual(adapter_result["alert_code"], "stage_spool_failed_messages_present")
        self.assertEqual(adapter_result["dedupe_key"], "stage_spool_failed_messages_present:local_outbox")
        self.assertEqual(adapter_result["idempotency_key"], "ops_alert_delivery:stage_spool_failed_messages_present:local_outbox")
        self.assertEqual(adapter_result["timeout_seconds"], 10)
        self.assertFalse(adapter_result["provider_calls_executed"])
        self.assertFalse(adapter_result["external_delivery_executed"])
        self.assertFalse(adapter_result["payload_persisted"])
        self.assertFalse(adapter_result["secret_values_exposed"])

        self.assertEqual(len(delivery_events), 1)
        audit_item = delivery_events[0].details["items"][0]
        self.assertEqual(audit_item["adapter_result"], adapter_result)
        self.assertFalse(delivery_events[0].details["safety"]["provider_calls_executed"])
        self.assertFalse(delivery_events[0].details["safety"]["external_delivery_executed"])

    def test_ops_alert_delivery_rejects_invalid_targets_and_updates_action_registry(self):
        """验证 alert delivery 拒绝非精确目标，并暴露 fake outbox registry 合同。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                empty_response = client.post(
                    "/api/v1/ops/alert-deliveries/fake-send",
                    headers=admin_headers,
                    json={
                        "alert_codes": [],
                        "reason": "ops drill",
                        "confirmation": "SEND FAKE OPS ALERTS",
                    },
                )
                duplicate_response = client.post(
                    "/api/v1/ops/alert-deliveries/fake-send",
                    headers=admin_headers,
                    json={
                        "alert_codes": ["readiness_warnings_present", "readiness_warnings_present"],
                        "reason": "ops drill",
                        "confirmation": "SEND FAKE OPS ALERTS",
                    },
                )
                too_many_response = client.post(
                    "/api/v1/ops/alert-deliveries/fake-send",
                    headers=admin_headers,
                    json={
                        "alert_codes": [f"alert_{index}" for index in range(11)],
                        "reason": "ops drill",
                        "confirmation": "SEND FAKE OPS ALERTS",
                    },
                )
                inactive_response = client.post(
                    "/api/v1/ops/alert-deliveries/preview",
                    headers=admin_headers,
                    json={"alert_codes": ["stage_spool_failed_messages_present"]},
                )
                bad_confirmation_response = client.post(
                    "/api/v1/ops/alert-deliveries/fake-send",
                    headers=admin_headers,
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "reason": "ops drill",
                        "confirmation": "SEND",
                    },
                )
                registry_response = client.get("/api/v1/ops/recovery-actions", headers=admin_headers)

        self.assertEqual(empty_response.status_code, 400)
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertEqual(too_many_response.status_code, 400)
        self.assertEqual(inactive_response.status_code, 409)
        self.assertEqual(inactive_response.json()["error_code"], "conflict")
        self.assertEqual(bad_confirmation_response.status_code, 400)
        actions_by_id = {item["action_id"]: item for item in registry_response.json()["actions"]}
        alert_action = actions_by_id["alert.delivery"]
        self.assertTrue(alert_action["available"])
        self.assertEqual(alert_action["audit_action"], "ops.alert_delivery_fake")
        self.assertTrue(alert_action["requires_reason"])
        self.assertTrue(alert_action["requires_confirmation"])
        self.assertFalse(alert_action["sends_notification"])

    def test_ops_alert_destination_dry_run_is_admin_only_readonly_and_masks_secrets(self):
        """验证 alert destination dry-run 只读、Admin-only，并且不返回 secret value。"""

        destination_config = [
            {
                "destination_id": "ops-slack-primary",
                "channel": "slack",
                "enabled": True,
                "secret_ref": "OPS_SLACK_WEBHOOK_URL",
                "secret_value": "should-not-leak",
                "target_label": "#ops-alerts",
                "allowlist": ["stage_spool_failed_messages_present"],
                "rate_limit_per_hour": 30,
                "dedupe_window_minutes": 60,
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                ops_alert_destinations_json=json.dumps(destination_config),
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_alert_destination_dry_run_failed",
                    job_id="docjob_alert_destination",
                    stage="convert_package",
                    trace_id="trace_alert_destination",
                    status="failed",
                )
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                admin_response = client.post(
                    "/api/v1/ops/alert-destinations/dry-run",
                    headers=admin_headers,
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "destination_ids": ["ops-slack-primary"],
                    },
                )
                operator_response = client.post(
                    "/api/v1/ops/alert-destinations/dry-run",
                    headers=operator_headers,
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "destination_ids": ["ops-slack-primary"],
                    },
                )
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "config_dry_run")
        self.assertEqual(payload["configured_count"], 1)
        self.assertEqual(payload["selected_count"], 1)
        self.assertEqual(payload["config_errors"], [])
        self.assertFalse(payload["safety"]["external_delivery_executed"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertFalse(payload["safety"]["secret_values_exposed"])
        destination = payload["destinations"][0]
        self.assertEqual(destination["destination_id"], "ops-slack-primary")
        self.assertEqual(destination["channel"], "slack")
        self.assertEqual(destination["status"], "dry_run_passed")
        self.assertEqual(destination["secret_ref"], "OPS_SLACK_WEBHOOK_URL")
        self.assertTrue(destination["secret_ref_present"])
        self.assertEqual(destination["matched_alert_codes"], ["stage_spool_failed_messages_present"])
        self.assertEqual(destination["blocked_alert_codes"], [])
        self.assertIn("real_delivery_requires_explicit_real_send", destination["missing_gates"])
        self.assertNotIn("should-not-leak", admin_response.text)
        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(audit_actions_after, audit_actions_before)

    def test_ops_alert_destination_dry_run_reports_invalid_config_without_side_effects(self):
        """验证 alert destination invalid config 作为 dry-run error 返回且无副作用。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                ops_alert_destinations_json=json.dumps(
                    [
                        {
                            "destination_id": "bad-destination",
                            "channel": "sms",
                            "enabled": "yes",
                            "allowlist": "not-a-list",
                        }
                    ]
                ),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                response = client.post(
                    "/api/v1/ops/alert-destinations/dry-run",
                    headers=admin_headers,
                    json={},
                )
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["configured_count"], 0)
        self.assertEqual(payload["selected_count"], 0)
        self.assertEqual(payload["destinations"], [])
        self.assertGreaterEqual(len(payload["config_errors"]), 3)
        self.assertTrue(any("channel" in error for error in payload["config_errors"]))
        self.assertTrue(any("enabled" in error for error in payload["config_errors"]))
        self.assertTrue(any("allowlist" in error for error in payload["config_errors"]))
        self.assertFalse(payload["safety"]["external_delivery_executed"])
        self.assertFalse(payload["safety"]["secret_values_exposed"])
        self.assertEqual(audit_actions_after, audit_actions_before)

    def test_ops_real_alert_delivery_preview_is_admin_only_and_blocked_by_default(self):
        """验证 real-send preview 默认 blocked，且不解析 secret、不调用 provider、不写 audit。"""

        destination_config = [
            {
                "destination_id": "ops-slack-primary",
                "channel": "slack",
                "enabled": True,
                "secret_ref": "OPS_SLACK_WEBHOOK_URL",
                "target_label": "#ops-alerts-phase7-pilot",
                "allowlist": ["stage_spool_failed_messages_present"],
                "rate_limit_per_hour": 3,
                "dedupe_window_minutes": 60,
            }
        ]
        provider = FakeAlertDeliveryProvider()
        secret_resolver = FakeSecretResolver({"OPS_SLACK_WEBHOOK_URL": "https://hooks.slack.test/secret-token"})
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                ops_alert_destinations_json=json.dumps(destination_config),
                alert_delivery_provider=provider,
                secret_resolver=secret_resolver,
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_real_alert_preview_failed",
                    job_id="docjob_real_alert_preview",
                    stage="convert_package",
                    trace_id="trace_real_alert_preview",
                    status="failed",
                )
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                admin_response = client.post(
                    "/api/v1/ops/alert-deliveries/real-send/preview",
                    headers=admin_headers,
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "destination_ids": ["ops-slack-primary"],
                        "dedupe_window_minutes": 60,
                    },
                )
                operator_response = client.post(
                    "/api/v1/ops/alert-deliveries/real-send/preview",
                    headers=operator_headers,
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "destination_ids": ["ops-slack-primary"],
                    },
                )
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "real_send_preview")
        self.assertEqual(payload["channel"], "slack")
        self.assertEqual(payload["confirmation_phrase"], "SEND REAL OPS ALERTS")
        self.assertEqual(payload["requested_destination_ids"], ["ops-slack-primary"])
        self.assertEqual(payload["items"][0]["outcome"], "blocked")
        self.assertEqual(payload["items"][0]["destination_id"], "ops-slack-primary")
        self.assertIn("integration_alert_delivery_disabled", payload["items"][0]["missing_gates"])
        self.assertIn("dry_run_only", payload["items"][0]["missing_gates"])
        self.assertFalse(payload["items"][0]["audit_event_written"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["external_delivery_executed"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertFalse(payload["safety"]["secret_values_exposed"])
        self.assertNotIn("secret-token", admin_response.text)
        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(provider.calls, [])
        self.assertEqual(secret_resolver.calls, [])
        self.assertEqual(audit_actions_after, audit_actions_before)

    def test_ops_real_alert_delivery_rejects_non_pilot_targets_and_bad_confirmation(self):
        """验证 real-send 只接受固定 pilot destination、alert code 和 confirmation。"""

        destination_config = [
            {
                "destination_id": "ops-slack-primary",
                "channel": "slack",
                "enabled": True,
                "secret_ref": "OPS_SLACK_WEBHOOK_URL",
                "target_label": "#ops-alerts-phase7-pilot",
                "allowlist": ["stage_spool_failed_messages_present"],
                "rate_limit_per_hour": 3,
                "dedupe_window_minutes": 60,
            }
        ]
        provider = FakeAlertDeliveryProvider()
        secret_resolver = FakeSecretResolver({"OPS_SLACK_WEBHOOK_URL": "https://hooks.slack.test/secret-token"})
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                ops_alert_destinations_json=json.dumps(destination_config),
                integration_alert_delivery_enabled=True,
                integration_alert_delivery_dry_run=False,
                alert_delivery_provider=provider,
                secret_resolver=secret_resolver,
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_real_alert_invalid_failed",
                    job_id="docjob_real_alert_invalid",
                    stage="convert_package",
                    trace_id="trace_real_alert_invalid",
                    status="failed",
                )
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                wrong_destination_response = client.post(
                    "/api/v1/ops/alert-deliveries/real-send/preview",
                    headers=admin_headers,
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "destination_ids": ["ops-slack-secondary"],
                    },
                )
                wrong_alert_response = client.post(
                    "/api/v1/ops/alert-deliveries/real-send/preview",
                    headers=admin_headers,
                    json={
                        "alert_codes": ["readiness_warnings_present"],
                        "destination_ids": ["ops-slack-primary"],
                    },
                )
                bad_confirmation_response = client.post(
                    "/api/v1/ops/alert-deliveries/real-send",
                    headers=admin_headers,
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "destination_ids": ["ops-slack-primary"],
                        "reason": "phase7 pilot",
                        "confirmation": "SEND",
                    },
                )

        self.assertEqual(wrong_destination_response.status_code, 400)
        self.assertEqual(wrong_alert_response.status_code, 400)
        self.assertEqual(bad_confirmation_response.status_code, 400)
        self.assertEqual(provider.calls, [])
        self.assertEqual(secret_resolver.calls, [])
        self.assertEqual(runtime.audit_event_repository.list_audit_events(), [])

    def test_ops_real_alert_delivery_kill_switch_blocks_before_secret_and_provider(self):
        """验证 kill switch 在解析 secret 和调用 provider 前阻断，并写入脱敏 audit。"""

        destination_config = [
            {
                "destination_id": "ops-slack-primary",
                "channel": "slack",
                "enabled": True,
                "secret_ref": "OPS_SLACK_WEBHOOK_URL",
                "target_label": "#ops-alerts-phase7-pilot",
                "allowlist": ["stage_spool_failed_messages_present"],
                "rate_limit_per_hour": 3,
                "dedupe_window_minutes": 60,
            }
        ]
        provider = FakeAlertDeliveryProvider()
        secret_resolver = FakeSecretResolver({"OPS_SLACK_WEBHOOK_URL": "https://hooks.slack.test/secret-token"})
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                ops_alert_destinations_json=json.dumps(destination_config),
                integration_alert_delivery_enabled=True,
                integration_alert_delivery_dry_run=False,
                integration_alert_delivery_kill_switch=True,
                alert_delivery_provider=provider,
                secret_resolver=secret_resolver,
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_real_alert_kill_failed",
                    job_id="docjob_real_alert_kill",
                    stage="convert_package",
                    trace_id="trace_real_alert_kill",
                    status="failed",
                )
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.post(
                    "/api/v1/ops/alert-deliveries/real-send",
                    headers={**admin_headers, "X-Trace-Id": "trace_real_alert_kill"},
                    json={
                        "alert_codes": ["stage_spool_failed_messages_present"],
                        "destination_ids": ["ops-slack-primary"],
                        "reason": "phase7 pilot kill switch drill",
                        "confirmation": "SEND REAL OPS ALERTS",
                    },
                )
            delivery_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "ops.alert_delivery_real"
            ]

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"][0]["outcome"], "blocked")
        self.assertIn("kill_switch_active", payload["items"][0]["missing_gates"])
        self.assertTrue(payload["items"][0]["audit_event_written"])
        self.assertTrue(payload["safety"]["audit_events_written"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["external_delivery_executed"])
        self.assertFalse(payload["safety"]["secret_values_exposed"])
        self.assertNotIn("secret-token", response.text)
        self.assertEqual(provider.calls, [])
        self.assertEqual(secret_resolver.calls, [])
        self.assertEqual(len(delivery_events), 1)
        self.assertEqual(delivery_events[0].trace_id, "trace_real_alert_kill")
        self.assertEqual(delivery_events[0].details["outcome"], "blocked")
        self.assertFalse(delivery_events[0].details["safety"]["provider_calls_executed"])
        self.assertFalse(delivery_events[0].details["safety"]["secret_values_exposed"])
        self.assertNotIn("secret-token", json.dumps(delivery_events[0].details, ensure_ascii=False))

    def test_ops_real_alert_delivery_success_uses_injected_provider_and_dedupes(self):
        """验证 real-send 成功路径使用注入 provider，重复请求 dedupe 且不泄露 secret。"""

        destination_config = [
            {
                "destination_id": "ops-slack-primary",
                "channel": "slack",
                "enabled": True,
                "secret_ref": "OPS_SLACK_WEBHOOK_URL",
                "target_label": "#ops-alerts-phase7-pilot",
                "allowlist": ["stage_spool_failed_messages_present"],
                "rate_limit_per_hour": 3,
                "dedupe_window_minutes": 60,
            }
        ]
        provider = FakeAlertDeliveryProvider(outcome="sent")
        secret_resolver = FakeSecretResolver({"OPS_SLACK_WEBHOOK_URL": "https://hooks.slack.test/secret-token"})
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                ops_alert_destinations_json=json.dumps(destination_config),
                integration_alert_delivery_enabled=True,
                integration_alert_delivery_dry_run=False,
                alert_delivery_provider=provider,
                secret_resolver=secret_resolver,
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_real_alert_success_failed",
                    job_id="docjob_real_alert_success",
                    stage="convert_package",
                    trace_id="trace_real_alert_success",
                    status="failed",
                )
            )
            app = create_app(runtime)
            payload = {
                "alert_codes": ["stage_spool_failed_messages_present"],
                "destination_ids": ["ops-slack-primary"],
                "reason": "phase7 pilot success drill",
                "confirmation": "SEND REAL OPS ALERTS",
            }
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                first_response = client.post(
                    "/api/v1/ops/alert-deliveries/real-send",
                    headers={**admin_headers, "X-Trace-Id": "trace_real_alert_success"},
                    json=payload,
                )
                second_response = client.post(
                    "/api/v1/ops/alert-deliveries/real-send",
                    headers=admin_headers,
                    json=payload,
                )
            delivery_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "ops.alert_delivery_real"
            ]

        self.assertEqual(first_response.status_code, 200)
        first_payload = first_response.json()
        self.assertEqual(first_payload["items"][0]["outcome"], "sent")
        self.assertEqual(first_payload["items"][0]["adapter_result"]["adapter_mode"], "real")
        self.assertTrue(first_payload["items"][0]["adapter_result"]["provider_calls_executed"])
        self.assertTrue(first_payload["safety"]["provider_calls_executed"])
        self.assertTrue(first_payload["safety"]["external_delivery_executed"])
        self.assertFalse(first_payload["safety"]["secret_values_exposed"])
        self.assertNotIn("secret-token", first_response.text)

        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.json()
        self.assertEqual(second_payload["items"][0]["outcome"], "deduped")
        self.assertFalse(second_payload["items"][0]["adapter_result"]["provider_calls_executed"])
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]["webhook_url"], "https://hooks.slack.test/secret-token")
        self.assertEqual(secret_resolver.calls, ["OPS_SLACK_WEBHOOK_URL", "OPS_SLACK_WEBHOOK_URL"])
        self.assertEqual(len(delivery_events), 2)
        self.assertEqual(delivery_events[0].details["outcome"], "sent")
        self.assertEqual(delivery_events[1].details["outcome"], "deduped")
        self.assertNotIn("secret-token", json.dumps([event.details for event in delivery_events], ensure_ascii=False))

    def test_ops_real_alert_delivery_rate_limits_failed_provider_attempts(self):
        """验证 provider 失败尝试达到 Phase 7 rate limit 后不再调用 provider。"""

        destination_config = [
            {
                "destination_id": "ops-slack-primary",
                "channel": "slack",
                "enabled": True,
                "secret_ref": "OPS_SLACK_WEBHOOK_URL",
                "target_label": "#ops-alerts-phase7-pilot",
                "allowlist": ["stage_spool_failed_messages_present"],
                "rate_limit_per_hour": 3,
                "dedupe_window_minutes": 60,
            }
        ]
        provider = FakeAlertDeliveryProvider(outcome="failed")
        secret_resolver = FakeSecretResolver({"OPS_SLACK_WEBHOOK_URL": "https://hooks.slack.test/secret-token"})
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                ops_alert_destinations_json=json.dumps(destination_config),
                integration_alert_delivery_enabled=True,
                integration_alert_delivery_dry_run=False,
                alert_delivery_provider=provider,
                secret_resolver=secret_resolver,
            )
            runtime.stage_message_store.put_stage_message(
                JobStageMessage(
                    id="msg_real_alert_rate_failed",
                    job_id="docjob_real_alert_rate",
                    stage="convert_package",
                    trace_id="trace_real_alert_rate",
                    status="failed",
                )
            )
            app = create_app(runtime)
            payload = {
                "alert_codes": ["stage_spool_failed_messages_present"],
                "destination_ids": ["ops-slack-primary"],
                "reason": "phase7 pilot rate drill",
                "confirmation": "SEND REAL OPS ALERTS",
            }
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                responses = [
                    client.post("/api/v1/ops/alert-deliveries/real-send", headers=admin_headers, json=payload)
                    for _ in range(4)
                ]
            delivery_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "ops.alert_delivery_real"
            ]

        self.assertEqual([response.status_code for response in responses], [200, 200, 200, 200])
        self.assertEqual(
            [response.json()["items"][0]["outcome"] for response in responses],
            ["failed", "failed", "failed", "rate_limited"],
        )
        self.assertEqual(len(provider.calls), 3)
        self.assertFalse(responses[-1].json()["items"][0]["adapter_result"]["provider_calls_executed"])
        self.assertFalse(responses[-1].json()["safety"]["provider_calls_executed"])
        self.assertEqual(len(delivery_events), 4)
        self.assertEqual(delivery_events[-1].details["outcome"], "rate_limited")
        self.assertNotIn("secret-token", json.dumps([event.details for event in delivery_events], ensure_ascii=False))

    def test_ops_provider_cancellation_preview_is_admin_only_and_metadata_only(self):
        """验证 provider cancellation preview 只读、Admin-only，且不调用 provider。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            runtime.document_job_repository.create_document_job(
                DocumentJobRecord(
                    id="docjob_provider_cancel_preview",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    created_by="user_operator",
                    source_file_id="file_provider_cancel_preview",
                    status="running",
                    stage="parsing",
                    progress=20,
                    template_version_id="template_default",
                    mineru_batch_id="batch_provider_cancel_preview",
                    mineru_data_id="docjob_provider_cancel_preview",
                )
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                admin_response = client.post(
                    "/api/v1/ops/provider-cancellations/preview",
                    headers=admin_headers,
                    json={
                        "target_type": "document_job",
                        "target_id": "docjob_provider_cancel_preview",
                        "provider": "mineru",
                    },
                )
                operator_response = client.post(
                    "/api/v1/ops/provider-cancellations/preview",
                    headers=operator_headers,
                    json={
                        "target_type": "document_job",
                        "target_id": "docjob_provider_cancel_preview",
                        "provider": "mineru",
                    },
                )
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "dry_run")
        self.assertTrue(payload["eligible"])
        self.assertEqual(payload["outcome"], "cancelable")
        self.assertEqual(payload["provider_operation"]["operation_id"], "batch_provider_cancel_preview")
        self.assertEqual(payload["confirmation_phrase"], "FAKE CANCEL PROVIDER OPERATION")
        self.assertFalse(payload["audit_event_written"])
        self.assertFalse(payload["safety"]["real_provider_cancel_executed"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(audit_actions_after, audit_actions_before)
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.query_calls, [])
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.calls, [])

    def test_ops_provider_cancellation_fake_cancel_audits_dedupes_and_does_not_mutate_jobs(self):
        """验证 provider fake-cancel 写审计和 dedupe，但不修改本地 job 或调用 provider。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            runtime.document_job_repository.create_document_job(
                DocumentJobRecord(
                    id="docjob_provider_cancel_fake",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    created_by="user_operator",
                    source_file_id="file_provider_cancel_fake",
                    status="running",
                    stage="parsing",
                    progress=20,
                    template_version_id="template_default",
                    mineru_batch_id="batch_provider_cancel_fake",
                    mineru_data_id="docjob_provider_cancel_fake",
                )
            )
            app = create_app(runtime)
            payload = {
                "target_type": "document_job",
                "target_id": "docjob_provider_cancel_fake",
                "provider": "mineru",
                "reason": "ops provider cancellation drill",
                "confirmation": "FAKE CANCEL PROVIDER OPERATION",
                "dedupe_window_minutes": 60,
            }
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                first_response = client.post(
                    "/api/v1/ops/provider-cancellations/fake-cancel",
                    headers={**admin_headers, "X-Trace-Id": "trace_provider_cancel_fake"},
                    json=payload,
                )
                second_response = client.post(
                    "/api/v1/ops/provider-cancellations/fake-cancel",
                    headers=admin_headers,
                    json=payload,
                )
            stored_job = runtime.document_job_repository.get_document_job("docjob_provider_cancel_fake")
            cancel_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "ops.provider_cancellation_fake"
            ]

        self.assertEqual(first_response.status_code, 200)
        first_payload = first_response.json()
        self.assertEqual(first_payload["outcome"], "fake_canceled")
        self.assertTrue(first_payload["audit_event_written"])
        self.assertFalse(first_payload["safety"]["real_provider_cancel_executed"])
        self.assertFalse(first_payload["safety"]["provider_calls_executed"])
        self.assertFalse(first_payload["safety"]["local_job_mutated"])
        self.assertTrue(first_payload["safety"]["audit_events_written"])

        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.json()
        self.assertEqual(second_payload["outcome"], "deduped")
        self.assertFalse(second_payload["audit_event_written"])
        self.assertFalse(second_payload["safety"]["audit_events_written"])

        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.status, "running")
        self.assertEqual(stored_job.stage, "parsing")
        self.assertEqual(stored_job.mineru_batch_id, "batch_provider_cancel_fake")
        self.assertEqual(len(cancel_events), 1)
        self.assertEqual(cancel_events[0].trace_id, "trace_provider_cancel_fake")
        self.assertIn("mineru:document_job:docjob_provider_cancel_fake:batch_provider_cancel_fake", cancel_events[0].reason)
        self.assertIsNotNone(cancel_events[0].details)
        self.assertEqual(cancel_events[0].details["provider"], "mineru")
        self.assertEqual(cancel_events[0].details["target"]["target_id"], "docjob_provider_cancel_fake")
        self.assertEqual(cancel_events[0].details["provider_operation"]["operation_id"], "batch_provider_cancel_fake")
        provider_adapter = cancel_events[0].details["provider_adapter"]
        self.assertEqual(provider_adapter["contract_version"], "provider-cancel-fake-v1")
        self.assertEqual(provider_adapter["adapter_mode"], "fake")
        self.assertEqual(
            provider_adapter["idempotency_key"],
            "mineru:document_job:docjob_provider_cancel_fake:batch_provider_cancel_fake",
        )
        self.assertEqual(provider_adapter["timeout_seconds"], 0)
        self.assertFalse(provider_adapter["timed_out"])
        self.assertEqual(provider_adapter["outcome"], "fake_canceled")
        self.assertIsNone(provider_adapter["error_code"])
        self.assertIsNone(provider_adapter["error_message"])
        self.assertTrue(provider_adapter["safety"]["fake_adapter_executed"])
        self.assertTrue(provider_adapter["safety"]["timeout_checked"])
        self.assertTrue(provider_adapter["safety"]["idempotency_key_checked"])
        self.assertFalse(provider_adapter["safety"]["real_provider_cancel_executed"])
        self.assertFalse(provider_adapter["safety"]["provider_calls_executed"])
        self.assertFalse(cancel_events[0].details["safety"]["real_provider_cancel_executed"])
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.query_calls, [])
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.calls, [])

    def test_ops_provider_cancellation_dedupes_from_structured_adapter_details(self):
        """验证 provider fake-cancel dedupe 优先使用结构化 adapter 幂等 key。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            runtime.document_job_repository.create_document_job(
                DocumentJobRecord(
                    id="docjob_provider_cancel_details_dedupe",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    created_by="user_operator",
                    source_file_id="file_provider_cancel_details_dedupe",
                    status="running",
                    stage="parsing",
                    progress=20,
                    template_version_id="template_default",
                    mineru_batch_id="batch_provider_cancel_details_dedupe",
                    mineru_data_id="docjob_provider_cancel_details_dedupe",
                )
            )
            runtime.audit_event_repository.append_audit_event(
                AuditEvent(
                    audit_id="audit_provider_cancel_details_dedupe",
                    actor_id="admin",
                    actor_role="admin",
                    action="ops.provider_cancellation_fake",
                    target_type="provider_operation",
                    target_id="mineru:document_job:docjob_provider_cancel_details_dedupe",
                    reason="reason=seeded_provider_cancel outcome=fake_canceled",
                    details={
                        "provider_adapter": {
                            "contract_version": "provider-cancel-fake-v1",
                            "adapter_mode": "fake",
                            "idempotency_key": (
                                "mineru:document_job:"
                                "docjob_provider_cancel_details_dedupe:"
                                "batch_provider_cancel_details_dedupe"
                            ),
                            "timeout_seconds": 0,
                            "timed_out": False,
                            "outcome": "fake_canceled",
                            "error_code": None,
                            "error_message": None,
                            "safety": {
                                "fake_adapter_executed": True,
                                "real_provider_cancel_executed": False,
                                "provider_calls_executed": False,
                                "local_job_mutated": False,
                                "queue_mutated": False,
                                "timeout_checked": True,
                                "idempotency_key_checked": True,
                                "error_recorded": False,
                            },
                        }
                    },
                    trace_id="trace_seed_provider_cancel_details_dedupe",
                    created_at=utc_now(),
                )
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.post(
                    "/api/v1/ops/provider-cancellations/fake-cancel",
                    headers=admin_headers,
                    json={
                        "target_type": "document_job",
                        "target_id": "docjob_provider_cancel_details_dedupe",
                        "provider": "mineru",
                        "reason": "ops provider cancellation drill",
                        "confirmation": "FAKE CANCEL PROVIDER OPERATION",
                        "dedupe_window_minutes": 60,
                    },
                )
            cancel_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "ops.provider_cancellation_fake"
            ]

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "deduped")
        self.assertFalse(payload["audit_event_written"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertEqual(len(cancel_events), 1)

    def test_ops_provider_cancellation_gates_and_registry_contract(self):
        """验证 provider fake-cancel gate 和 registry 合同。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            runtime.document_job_repository.create_document_job(
                DocumentJobRecord(
                    id="docjob_provider_cancel_missing_batch",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    created_by="user_operator",
                    source_file_id="file_provider_cancel_missing_batch",
                    status="running",
                    stage="parsing",
                    progress=20,
                    template_version_id="template_default",
                )
            )
            runtime.document_job_repository.create_document_job(
                DocumentJobRecord(
                    id="docjob_provider_cancel_succeeded",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    created_by="user_operator",
                    source_file_id="file_provider_cancel_succeeded",
                    status="succeeded",
                    stage="completed",
                    progress=100,
                    template_version_id="template_default",
                    mineru_batch_id="batch_provider_cancel_done",
                )
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                missing_batch_preview = client.post(
                    "/api/v1/ops/provider-cancellations/preview",
                    headers=admin_headers,
                    json={
                        "target_type": "document_job",
                        "target_id": "docjob_provider_cancel_missing_batch",
                        "provider": "mineru",
                    },
                )
                terminal_preview = client.post(
                    "/api/v1/ops/provider-cancellations/preview",
                    headers=admin_headers,
                    json={
                        "target_type": "document_job",
                        "target_id": "docjob_provider_cancel_succeeded",
                        "provider": "mineru",
                    },
                )
                fake_ineligible = client.post(
                    "/api/v1/ops/provider-cancellations/fake-cancel",
                    headers=admin_headers,
                    json={
                        "target_type": "document_job",
                        "target_id": "docjob_provider_cancel_missing_batch",
                        "provider": "mineru",
                        "reason": "ops drill",
                        "confirmation": "FAKE CANCEL PROVIDER OPERATION",
                    },
                )
                bad_confirmation = client.post(
                    "/api/v1/ops/provider-cancellations/fake-cancel",
                    headers=admin_headers,
                    json={
                        "target_type": "document_job",
                        "target_id": "docjob_provider_cancel_missing_batch",
                        "provider": "mineru",
                        "reason": "ops drill",
                        "confirmation": "CANCEL",
                    },
                )
                registry_response = client.get("/api/v1/ops/recovery-actions", headers=admin_headers)

        self.assertEqual(missing_batch_preview.status_code, 200)
        missing_payload = missing_batch_preview.json()
        self.assertFalse(missing_payload["eligible"])
        self.assertEqual(missing_payload["outcome"], "ineligible")
        self.assertIn("provider_operation_id_missing", missing_payload["missing_gates"])
        self.assertEqual(terminal_preview.status_code, 200)
        terminal_payload = terminal_preview.json()
        self.assertIn("status_not_provider_cancelable", terminal_payload["missing_gates"])
        self.assertEqual(fake_ineligible.status_code, 409)
        self.assertEqual(fake_ineligible.json()["error_code"], "conflict")
        self.assertEqual(bad_confirmation.status_code, 400)
        actions_by_id = {item["action_id"]: item for item in registry_response.json()["actions"]}
        provider_action = actions_by_id["provider.cancel"]
        self.assertTrue(provider_action["available"])
        self.assertEqual(provider_action["audit_action"], "ops.provider_cancellation_fake")
        self.assertFalse(provider_action["calls_provider"])
        self.assertTrue(provider_action["requires_reason"])
        self.assertTrue(provider_action["requires_confirmation"])

    def test_ops_provider_cancellation_semantics_verification_is_admin_only_readonly_and_blocks_real_cancel(self):
        """验证 provider cancellation 语义核查只读，并阻断真实 provider cancellation。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                admin_response = client.get(
                    "/api/v1/ops/provider-cancellations/semantics-verification",
                    headers=admin_headers,
                )
                operator_response = client.get(
                    "/api/v1/ops/provider-cancellations/semantics-verification",
                    headers=operator_headers,
                )
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "semantics_verification")
        self.assertEqual(payload["provider"], "mineru")
        self.assertEqual(payload["verification_status"], "verified_blocked")
        self.assertEqual(payload["decision"], "unsupported_by_public_docs")
        self.assertFalse(payload["public_docs_support_real_cancel"])
        self.assertFalse(payload["real_provider_cancel_allowed"])
        self.assertIn("extract_task_submit", payload["supported_provider_operations"])
        self.assertIn("running", payload["documented_task_statuses"])
        self.assertIn("provider_cancel_endpoint_not_documented", payload["unsupported_operations"])
        self.assertIn("provider_cancellation_unsupported_by_public_docs", payload["blocking_reasons"])
        self.assertIn("real_provider_cancellation_adapter_not_implemented", payload["blocking_reasons"])
        self.assertGreaterEqual(len(payload["sources"]), 2)
        self.assertTrue(all(source["source_type"] == "primary_docs" for source in payload["sources"]))
        self.assertIn("https://mineru.net/doc/docs/index_en/", [source["url"] for source in payload["sources"]])
        self.assertTrue(payload["safety"]["read_only"])
        self.assertFalse(payload["safety"]["real_provider_cancel_executed"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["local_job_mutated"])
        self.assertFalse(payload["safety"]["queue_mutated"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertFalse(payload["safety"]["secret_values_exposed"])
        self.assertEqual(audit_actions_after, audit_actions_before)
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.query_calls, [])
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.calls, [])

    def test_ops_integration_capabilities_report_provider_cancellation_semantics_verified_but_blocked(self):
        """验证 control plane 展示 provider cancellation 语义已核查但仍阻断真实执行。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                integration_provider_cancellation_enabled=True,
                integration_provider_cancellation_dry_run=False,
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.get("/api/v1/ops/integration-capabilities", headers=admin_headers)

        self.assertEqual(response.status_code, 200)
        capabilities = {item["capability_id"]: item for item in response.json()["capabilities"]}
        provider_cancellation = capabilities["provider_cancellation"]
        self.assertEqual(provider_cancellation["status"], "blocked")
        self.assertTrue(provider_cancellation["real_execution_enabled"])
        self.assertFalse(provider_cancellation["dry_run_only"])
        self.assertFalse(provider_cancellation["ready"])
        self.assertIn(
            "provider_cancellation_unsupported_by_public_docs",
            provider_cancellation["blocking_reasons"],
        )
        self.assertNotIn(
            "provider_cancellation_semantics_unverified",
            provider_cancellation["blocking_reasons"],
        )
        self.assertEqual(provider_cancellation["safe_config"]["semantics_verification_status"], "verified_blocked")
        self.assertEqual(provider_cancellation["safe_config"]["semantics_decision"], "unsupported_by_public_docs")
        self.assertFalse(provider_cancellation["safe_config"]["real_provider_cancel_supported"])

    def test_ops_s3_delete_adapter_contract_is_admin_only_readonly_and_keeps_real_delete_blocked(self):
        """验证 S3 delete contract 只读、Admin-only，且 control plane 继续阻断真实删除。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="s3",
                jobs_artifact_s3_bucket="test-bucket",
                jobs_artifact_s3_endpoint_url="http://127.0.0.1:4566",
                jobs_artifact_s3_access_key_id="test-access-key",
                jobs_artifact_s3_secret_access_key="test-secret-key",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                integration_s3_deletion_enabled=True,
                integration_s3_deletion_dry_run=False,
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                admin_response = client.get("/api/v1/ops/s3-deletions/adapter-contract", headers=admin_headers)
                operator_response = client.get("/api/v1/ops/s3-deletions/adapter-contract", headers=operator_headers)
                control_response = client.get("/api/v1/ops/integration-capabilities", headers=admin_headers)
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "adapter_contract")
        self.assertEqual(payload["contract_version"], "ops-s3-delete-adapter-v1")
        self.assertEqual(payload["fake_adapter_id"], "file_retention_s3_fake")
        self.assertEqual(payload["fake_adapter_mode"], "fake")
        self.assertEqual(payload["fake_file_retention_contract_version"], "s3-delete-fake-v1")
        self.assertEqual(payload["localstack_profile"]["harness"], "localstack")
        self.assertFalse(payload["localstack_profile"]["runtime_executed"])
        self.assertTrue(payload["storage_config_summary"]["s3_endpoint_localstack_like"])
        self.assertFalse(payload["storage_config_summary"]["secret_values_exposed"])
        self.assertTrue(payload["parity_checks"]["fake_file_retention_contract_version_linked"])
        self.assertTrue(payload["parity_checks"]["fake_preserves_version_id"])
        self.assertTrue(payload["parity_checks"]["metadata_mutation_requires_provider_success"])
        self.assertIn("real_s3_delete_adapter_not_implemented", payload["blocking_reasons"])
        self.assertIn("localstack_contract_not_executed_in_runtime", payload["blocking_reasons"])
        self.assertTrue(payload["safety"]["read_only"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["real_s3_delete_executed"])
        self.assertFalse(payload["safety"]["localstack_calls_executed"])
        self.assertFalse(payload["safety"]["cleanup_executed"])
        self.assertFalse(payload["safety"]["scheduler_loop_executed"])
        self.assertFalse(payload["safety"]["delete_executed"])
        self.assertFalse(payload["safety"]["metadata_mutated"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertFalse(payload["safety"]["secret_values_exposed"])
        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(audit_actions_after, audit_actions_before)
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.query_calls, [])
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.calls, [])

        self.assertEqual(control_response.status_code, 200)
        capabilities = {item["capability_id"]: item for item in control_response.json()["capabilities"]}
        s3_deletion = capabilities["s3_deletion"]
        self.assertEqual(s3_deletion["status"], "blocked")
        self.assertTrue(s3_deletion["real_execution_enabled"])
        self.assertFalse(s3_deletion["dry_run_only"])
        self.assertTrue(s3_deletion["configured"])
        self.assertFalse(s3_deletion["ready"])
        self.assertIn("real_s3_delete_adapter_not_implemented", s3_deletion["blocking_reasons"])
        self.assertIn("localstack_contract_not_executed_in_runtime", s3_deletion["blocking_reasons"])
        self.assertEqual(s3_deletion["safe_config"]["s3_delete_adapter_contract_version"], "ops-s3-delete-adapter-v1")
        self.assertEqual(s3_deletion["safe_config"]["fake_file_retention_contract_version"], "s3-delete-fake-v1")
        self.assertTrue(s3_deletion["safe_config"]["localstack_fake_parity_contract"])
        self.assertFalse(s3_deletion["safe_config"]["real_s3_delete_adapter_implemented"])

    def test_ops_integration_capabilities_are_admin_only_and_disabled_by_default(self):
        """验证 integration control plane 默认全部阻断、Admin-only 且无副作用。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                admin_response = client.get("/api/v1/ops/integration-capabilities", headers=admin_headers)
                operator_response = client.get("/api/v1/ops/integration-capabilities", headers=operator_headers)
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "read_only")
        self.assertEqual(payload["overall_status"], "blocked")
        capabilities = {item["capability_id"]: item for item in payload["capabilities"]}
        self.assertEqual(
            set(capabilities),
            {
                "alert_delivery",
                "provider_cancellation",
                "s3_deletion",
                "cleanup_scheduler_execute",
                "quota_enforcement",
            },
        )
        for capability in capabilities.values():
            self.assertEqual(capability["status"], "blocked")
            self.assertFalse(capability["real_execution_enabled"])
            self.assertTrue(capability["dry_run_only"])
            self.assertFalse(capability["ready"])
        self.assertIn("integration_alert_delivery_disabled", capabilities["alert_delivery"]["blocking_reasons"])
        self.assertFalse(capabilities["alert_delivery"]["safe_config"]["pilot_destination_ready"])
        self.assertIn(
            "real_provider_cancellation_adapter_not_implemented",
            capabilities["provider_cancellation"]["blocking_reasons"],
        )
        self.assertIn("real_s3_delete_adapter_not_implemented", capabilities["s3_deletion"]["blocking_reasons"])
        self.assertIn(
            "cleanup_scheduler_execute_loop_not_implemented",
            capabilities["cleanup_scheduler_execute"]["blocking_reasons"],
        )
        self.assertIn("files_quota_policy_disabled", capabilities["quota_enforcement"]["blocking_reasons"])
        self.assertTrue(payload["safety"]["read_only"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["external_delivery_executed"])
        self.assertFalse(payload["safety"]["s3_delete_executed"])
        self.assertFalse(payload["safety"]["cleanup_scheduler_executed"])
        self.assertFalse(payload["safety"]["quota_enforcement_executed"])
        self.assertFalse(payload["safety"]["secret_values_exposed"])
        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(audit_actions_after, audit_actions_before)
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.query_calls, [])
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.calls, [])

    def test_ops_integration_capabilities_report_enabled_quota_without_external_side_effects(self):
        """验证 control plane 可报告 ready quota，同时其他真实外部能力仍保持 blocked。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                files_quota_policy_enabled=True,
                files_quota_policy_dry_run=False,
                files_quota_bytes=2_000,
                integration_alert_delivery_enabled=True,
                integration_alert_delivery_dry_run=False,
                ops_alert_destinations_json=json.dumps(
                    [
                        {
                            "destination_id": "ops-slack-primary",
                            "channel": "slack",
                            "enabled": True,
                            "secret_ref": "OPS_SLACK_WEBHOOK_URL",
                            "target_label": "#ops",
                        }
                    ]
                ),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.get("/api/v1/ops/integration-capabilities", headers=admin_headers)
            audit_actions = [
                event.action
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action.startswith("ops.integration") or event.action.startswith("file.quota")
            ]

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["overall_status"], "partial")
        capabilities = {item["capability_id"]: item for item in payload["capabilities"]}
        quota = capabilities["quota_enforcement"]
        self.assertEqual(quota["status"], "ready")
        self.assertTrue(quota["ready"])
        self.assertTrue(quota["real_execution_enabled"])
        self.assertFalse(quota["dry_run_only"])
        self.assertEqual(quota["blocking_reasons"], [])
        self.assertEqual(quota["safe_config"]["quota_bytes"], 2_000)
        alert_delivery = capabilities["alert_delivery"]
        self.assertEqual(alert_delivery["status"], "blocked")
        self.assertTrue(alert_delivery["real_execution_enabled"])
        self.assertTrue(alert_delivery["safe_config"]["real_delivery_adapter_implemented"])
        self.assertFalse(alert_delivery["safe_config"]["pilot_destination_ready"])
        self.assertIn("phase7_slack_pilot_target_label_mismatch", alert_delivery["blocking_reasons"])
        self.assertIn("phase7_slack_pilot_alert_not_allowlisted", alert_delivery["blocking_reasons"])
        self.assertFalse(payload["safety"]["external_delivery_executed"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["quota_enforcement_executed"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertEqual(audit_actions, [])
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.query_calls, [])
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.calls, [])

    def test_ops_integration_capabilities_report_phase7_slack_pilot_ready_without_side_effects(self):
        """验证 control plane 可报告 Phase 7 Slack pilot ready，但不解析 secret 或调用 provider。"""

        destination_config = [
            {
                "destination_id": "ops-slack-primary",
                "channel": "slack",
                "enabled": True,
                "secret_ref": "OPS_SLACK_WEBHOOK_URL",
                "target_label": "#ops-alerts-phase7-pilot",
                "allowlist": ["stage_spool_failed_messages_present"],
                "rate_limit_per_hour": 3,
                "dedupe_window_minutes": 60,
            }
        ]
        provider = FakeAlertDeliveryProvider()
        secret_resolver = FakeSecretResolver({"OPS_SLACK_WEBHOOK_URL": "https://hooks.slack.test/secret-token"})
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                ops_alert_destinations_json=json.dumps(destination_config),
                integration_alert_delivery_enabled=True,
                integration_alert_delivery_dry_run=False,
                alert_delivery_provider=provider,
                secret_resolver=secret_resolver,
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.get("/api/v1/ops/integration-capabilities", headers=admin_headers)

        self.assertEqual(response.status_code, 200)
        capabilities = {item["capability_id"]: item for item in response.json()["capabilities"]}
        alert_delivery = capabilities["alert_delivery"]
        self.assertEqual(alert_delivery["status"], "ready")
        self.assertTrue(alert_delivery["ready"])
        self.assertTrue(alert_delivery["real_execution_enabled"])
        self.assertFalse(alert_delivery["dry_run_only"])
        self.assertEqual(alert_delivery["blocking_reasons"], [])
        self.assertTrue(alert_delivery["safe_config"]["real_delivery_adapter_implemented"])
        self.assertTrue(alert_delivery["safe_config"]["pilot_destination_ready"])
        self.assertEqual(alert_delivery["safe_config"]["pilot_secret_ref"], "OPS_SLACK_WEBHOOK_URL")
        self.assertFalse(response.json()["safety"]["external_delivery_executed"])
        self.assertFalse(response.json()["safety"]["provider_calls_executed"])
        self.assertFalse(response.json()["safety"]["audit_events_written"])
        self.assertNotIn("secret-token", response.text)
        self.assertEqual(provider.calls, [])
        self.assertEqual(secret_resolver.calls, [])

    def test_ops_recovery_action_preview_reports_document_job_eligibility_without_execution(self):
        """验证 recovery action preview 做精确目标判断，且不触发 provider、队列或 audit 副作用。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            now = utc_now()
            failed_job = runtime.document_job_repository.create_document_job(
                DocumentJobRecord(
                    id="docjob_ops_preview_failed",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    created_by="user_operator",
                    source_file_id="file_ops_preview_failed",
                    status="failed",
                    stage="failed",
                    progress=40,
                    template_version_id="template_default",
                    failed_stage="parsing",
                    error_code="parse_failed",
                    error_message="parse failed",
                    updated_at=now - timedelta(minutes=2),
                )
            )
            terminal_job = runtime.document_job_repository.create_document_job(
                DocumentJobRecord(
                    id="docjob_ops_preview_succeeded",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    created_by="user_operator",
                    source_file_id="file_ops_preview_succeeded",
                    status="succeeded",
                    stage="completed",
                    progress=100,
                    template_version_id="template_default",
                    completed_at=now - timedelta(minutes=1),
                    updated_at=now - timedelta(minutes=1),
                )
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                retry_preview_response = client.post(
                    "/api/v1/ops/recovery-actions/preview",
                    headers=admin_headers,
                    json={
                        "action_id": "document_job.retry",
                        "target_type": "document_job",
                        "target_id": failed_job.id,
                    },
                )
                cancel_preview_response = client.post(
                    "/api/v1/ops/recovery-actions/preview",
                    headers=admin_headers,
                    json={
                        "action_id": "document_job.cancel",
                        "target_type": "document_job",
                        "target_id": terminal_job.id,
                    },
                )
                missing_preview_response = client.post(
                    "/api/v1/ops/recovery-actions/preview",
                    headers=admin_headers,
                    json={
                        "action_id": "document_job.retry",
                        "target_type": "document_job",
                        "target_id": "docjob_missing",
                    },
                )
                mismatch_response = client.post(
                    "/api/v1/ops/recovery-actions/preview",
                    headers=admin_headers,
                    json={
                        "action_id": "document_job.retry",
                        "target_type": "provider_operation",
                        "target_id": failed_job.id,
                    },
                )
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                failed_job_after = runtime.document_job_repository.get_document_job(failed_job.id)
                terminal_job_after = runtime.document_job_repository.get_document_job(terminal_job.id)

        self.assertEqual(retry_preview_response.status_code, 200)
        retry_preview = retry_preview_response.json()
        self.assertTrue(retry_preview["eligible"])
        self.assertEqual(retry_preview["missing_gates"], [])
        self.assertEqual(retry_preview["target"]["status"], "failed")
        self.assertEqual(retry_preview["target"]["stage"], "failed")
        self.assertTrue(retry_preview["risk_flags"]["mutates_metadata"])
        self.assertTrue(retry_preview["risk_flags"]["mutates_queue"])
        self.assertFalse(retry_preview["safety"]["execution_performed"])
        self.assertFalse(retry_preview["safety"]["metadata_mutated"])
        self.assertFalse(retry_preview["safety"]["queue_mutated"])

        self.assertEqual(cancel_preview_response.status_code, 200)
        cancel_preview = cancel_preview_response.json()
        self.assertFalse(cancel_preview["eligible"])
        self.assertIn("status_not_cancelable", cancel_preview["missing_gates"])
        self.assertEqual(cancel_preview["target"]["status"], "succeeded")

        self.assertEqual(missing_preview_response.status_code, 200)
        missing_preview = missing_preview_response.json()
        self.assertFalse(missing_preview["eligible"])
        self.assertIn("target_not_found", missing_preview["missing_gates"])
        self.assertFalse(missing_preview["target"]["exists"])
        self.assertEqual(mismatch_response.status_code, 400)
        self.assertEqual(mismatch_response.json()["error_code"], "invalid_request")
        self.assertEqual(audit_actions_after, audit_actions_before)
        self.assertIsNotNone(failed_job_after)
        self.assertIsNotNone(terminal_job_after)
        self.assertEqual(failed_job_after.status, "failed")
        self.assertEqual(terminal_job_after.status, "succeeded")

    def test_ops_recovery_action_execute_replays_document_job_without_inline_provider_work(self):
        """验证 document_job.replay_execution 执行端只投递 Worker、写审计，不在 HTTP 内消费 callback。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                now = utc_now()
                job = runtime.document_job_repository.create_document_job(
                    DocumentJobRecord(
                        id="docjob_ops_replay",
                        tenant_id="tenant_default",
                        company_id="company_default",
                        created_by="user_operator",
                        source_file_id="file_ops_replay",
                        status="running",
                        stage="parsing",
                        progress=20,
                        template_version_id="template_default",
                        mineru_batch_id="batch_ops_replay",
                        mineru_data_id="docjob_ops_replay",
                        started_at=now - timedelta(minutes=2),
                        updated_at=now - timedelta(minutes=2),
                    )
                )
                runtime.document_job_callback_message_store.put_or_get_callback_message(
                    DocumentJobCallbackMessage(
                        id="doccb_ops_replay",
                        job_id=job.id,
                        status="pending",
                        dedupe_key="doccb_ops_replay",
                        payload={
                            "batch_id": "batch_ops_replay",
                            "data_id": job.id,
                            "state": "done",
                            "full_zip_url": "https://mineru.net/result.zip",
                        },
                        created_at=now - timedelta(minutes=1),
                        updated_at=now - timedelta(minutes=1),
                    )
                )
                preview_response = client.post(
                    "/api/v1/ops/recovery-actions/preview",
                    headers=admin_headers,
                    json={
                        "action_id": "document_job.replay_execution",
                        "target_type": "document_job",
                        "target_id": job.id,
                    },
                )
                execute_response = client.post(
                    "/api/v1/ops/recovery-actions/execute",
                    headers={**admin_headers, "X-Trace-Id": "trace_ops_replay_execute"},
                    json={
                        "action_id": "document_job.replay_execution",
                        "target_type": "document_job",
                        "target_id": job.id,
                        "reason": "manual replay from ops test",
                    },
                )
                unsupported_response = client.post(
                    "/api/v1/ops/recovery-actions/execute",
                    headers=admin_headers,
                    json={
                        "action_id": "document_job.retry",
                        "target_type": "document_job",
                        "target_id": job.id,
                        "reason": "unsupported execute",
                    },
                )
                operator_response = client.post(
                    "/api/v1/ops/recovery-actions/execute",
                    headers=operator_headers,
                    json={
                        "action_id": "document_job.replay_execution",
                        "target_type": "document_job",
                        "target_id": job.id,
                        "reason": "operator replay",
                    },
                )
                callback_counts = runtime.document_job_callback_message_store.count_callback_messages_by_status(job.id)
                events = runtime.document_job_event_repository.list_document_job_events(job.id)
                audit_events = runtime.audit_event_repository.list_audit_events()
                fake_client = runtime.document_job_execution_service.fake_mineru_client

        self.assertEqual(preview_response.status_code, 200)
        preview = preview_response.json()
        self.assertTrue(preview["eligible"])
        self.assertEqual(preview["target"]["summary"]["callback_replayable_messages"], 1)
        self.assertEqual(preview["target"]["summary"]["worker_backend"], "eager")
        self.assertFalse(preview["risk_flags"]["calls_provider"])
        self.assertFalse(preview["safety"]["execution_performed"])

        self.assertEqual(execute_response.status_code, 200)
        execute_payload = execute_response.json()
        self.assertTrue(execute_payload["executed"])
        self.assertEqual(execute_payload["queued_task_id"], f"eager:{job.id}")
        self.assertEqual(execute_payload["replayable_callback_messages"], 1)
        self.assertEqual(execute_payload["ignored_callback_messages"], 0)
        self.assertEqual(execute_payload["audit_events_written"], 1)
        self.assertTrue(execute_payload["safety"]["execution_performed"])
        self.assertTrue(execute_payload["safety"]["metadata_mutated"])
        self.assertTrue(execute_payload["safety"]["queue_mutated"])
        self.assertFalse(execute_payload["safety"]["provider_calls_executed"])
        self.assertEqual(callback_counts["pending"], 1)
        self.assertEqual(fake_client.download_calls, [])
        self.assertIn("recovery_replay_queued", [event.event_type for event in events])
        replay_audit_events = [event for event in audit_events if event.action == "document_job.replay_execution"]
        self.assertEqual(len(replay_audit_events), 1)
        self.assertEqual(replay_audit_events[0].reason, "manual replay from ops test")
        self.assertEqual(replay_audit_events[0].details["queued_task_id"], f"eager:{job.id}")
        self.assertEqual(unsupported_response.status_code, 409)
        self.assertEqual(operator_response.status_code, 403)

    def test_health_ready_blocks_when_default_translation_mode_requires_missing_client(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), default_translation_mode="en2zh")
            checks = runtime.health_service.build_dependency_checks()

        self.assertTrue(checks["translation_required_for_default_mode"])
        self.assertFalse(checks["translation_available"])
        self.assertFalse(checks["deployment_init_ready"])
        self.assertIn("default_translation_unavailable", checks["readiness_blockers"])

    def test_health_ready_marks_translation_unavailable_when_provider_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), openai_api_key="fake-key")
            checks = runtime.health_service.build_dependency_checks()

        self.assertEqual(checks["translation_provider_backend"], "disabled")
        self.assertTrue(checks["translation_client_configured"])
        self.assertTrue(checks["translation_prompt_exists"])
        self.assertFalse(checks["translation_available"])
        self.assertIn("translation_unavailable", checks["readiness_warnings"])

    def test_health_ready_blocks_when_callback_uid_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
                mineru_uid="",
            )
            checks = runtime.health_service.build_dependency_checks()

        self.assertFalse(checks["deployment_init_ready"])
        self.assertIn("mineru_uid_missing", checks["readiness_blockers"])

    def test_api_error_handlers_map_domain_exceptions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))

            @app.get("/test-errors/workflow")
            def raise_workflow_error():
                raise JobWorkflowViolation("当前状态不允许执行。")

            @app.get("/test-errors/conversion")
            def raise_conversion_error():
                raise ConversionFailure("conversion_failed", "转换失败。")

            with TestClient(app, raise_server_exceptions=False) as client:
                workflow_response = client.get("/test-errors/workflow")
                conversion_response = client.get("/test-errors/conversion")

        self.assertEqual(workflow_response.status_code, 409)
        self.assertEqual(workflow_response.json()["detail"], "当前状态不允许执行。")
        self.assertEqual(conversion_response.status_code, 503)
        self.assertEqual(conversion_response.json()["detail"], "转换失败。")
        self.assertEqual(workflow_response.json()["error_code"], "job_state_conflict")
        self.assertEqual(workflow_response.json()["request_id"], workflow_response.json()["error"]["request_id"])
        self.assertEqual(workflow_response.json()["trace_id"], workflow_response.json()["error"]["trace_id"])
        self.assertEqual(conversion_response.json()["error_code"], "conversion_failed")

    def test_internal_auth_login_and_me_support_admin_and_operator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_login = client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "admin-pass"},
                )
                operator_login = client.post(
                    "/api/v1/auth/login",
                    json={"username": "operator", "password": "operator-pass"},
                )
                me_response = client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
                )

        self.assertEqual(admin_login.status_code, 200)
        self.assertEqual(admin_login.json()["token_type"], "bearer")
        self.assertEqual(admin_login.json()["role"], "admin")
        self.assertEqual(admin_login.json()["roles"], ["admin"])
        self.assertIn("document_jobs:read", admin_login.json()["permissions"])
        self.assertIn("ops:read", admin_login.json()["permissions"])
        self.assertGreater(admin_login.json()["expires_in"], 0)
        self.assertEqual(operator_login.status_code, 200)
        self.assertEqual(operator_login.json()["role"], "operator")
        self.assertEqual(operator_login.json()["roles"], ["operator"])
        self.assertIn("document_jobs:read", operator_login.json()["permissions"])
        self.assertNotIn("ops:read", operator_login.json()["permissions"])
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["id"], "user_admin")
        self.assertEqual(me_response.json()["role"], "admin")
        self.assertEqual(me_response.json()["roles"], ["admin"])
        self.assertIn("settings:read", me_response.json()["permissions"])

    def test_internal_auth_loads_users_from_file_to_avoid_env_dollar_escaping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            users_file = Path(temp_dir) / "auth_internal_users.json"
            users_file.write_text(build_auth_users_json(), encoding="utf-8")
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_file=str(users_file),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/auth/login",
                    json={"username": "operator", "password": "operator-pass"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "operator")

    def test_internal_auth_rejects_missing_invalid_expired_and_wrong_role(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                auth_access_token_expire_minutes=-1,
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                missing_token = client.get("/api/v1/auth/me")
                invalid_token = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad-token"})
                expired_login = client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "admin-pass"},
                )
                expired_token = client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {expired_login.json()['access_token']}"},
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_login = client.post(
                    "/api/v1/auth/login",
                    json={"username": "operator", "password": "operator-pass"},
                )
                wrong_role = client.patch(
                    "/api/v1/templates/default/default",
                    headers={"Authorization": f"Bearer {operator_login.json()['access_token']}"},
                )
                invalid_credentials = client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "bad-pass"},
                )

        self.assertEqual(missing_token.status_code, 401)
        self.assertEqual(missing_token.json()["error_code"], "unauthorized")
        self.assertEqual(invalid_token.status_code, 401)
        self.assertEqual(invalid_token.json()["error_code"], "invalid_token")
        self.assertEqual(expired_token.status_code, 401)
        self.assertEqual(expired_token.json()["error_code"], "token_expired")
        self.assertEqual(wrong_role.status_code, 403)
        self.assertEqual(wrong_role.json()["error_code"], "role_forbidden")
        self.assertEqual(invalid_credentials.status_code, 401)
        self.assertEqual(invalid_credentials.json()["error_code"], "invalid_credentials")

    def test_file_upload_url_registers_source_pdf_metadata_for_operator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            pdf_content = make_pdf_bytes(page_count=2)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                response = client.post(
                    "/api/v1/files/upload-url",
                    headers=headers,
                    json={
                        "filename": "source.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(pdf_content),
                        "file_type": "source_pdf",
                    },
                )
                self.assertEqual(response.status_code, 201)
                payload = response.json()
                file_id = payload["file_id"]
                detail_response = client.get(f"/api/v1/files/{file_id}", headers=headers)

            record = runtime.document_file_repository.get_document_file(file_id)

        self.assertEqual(payload["method"], "PUT")
        self.assertTrue(payload["upload_url"].endswith(f"/api/v1/files/{file_id}/content"))
        self.assertTrue(payload["object_key"].startswith(f"document-files/tenant_default/{file_id}/"))
        self.assertEqual(payload["file"]["status"], "pending_upload")
        self.assertEqual(payload["file"]["created_by"], "user_operator")
        self.assertEqual(detail_response.status_code, 200)
        self.assertIsNotNone(record)
        self.assertEqual(record.file_type, "source_pdf")
        self.assertEqual(record.storage_provider, "local_object")
        self.assertEqual(record.bucket, "local-object")

    def test_file_upload_rejects_prebound_job_id_for_document_job_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            pdf_content = make_pdf_bytes(page_count=1)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                response = client.post(
                    "/api/v1/files/upload-url",
                    headers=headers,
                    json={
                        "filename": "source.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(pdf_content),
                        "file_type": "source_pdf",
                        "job_id": "job_prebound",
                    },
                )

            records = runtime.document_file_repository.list_document_files()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "invalid_request")
        self.assertEqual(records, [])

    def test_file_upload_metadata_and_content_are_owner_or_admin_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_multi_operator_auth_users_json(),
            )
            app = create_app(runtime)
            pdf_content = make_pdf_bytes(page_count=1)

            with TestClient(app) as client:
                owner_headers = build_auth_header(client)
                other_headers = build_auth_header(client, username="operator2", password="operator2-pass")
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.post(
                    "/api/v1/files/upload-url",
                    headers=owner_headers,
                    json={
                        "filename": "owner-source.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(pdf_content),
                        "file_type": "source_pdf",
                    },
                )
                self.assertEqual(response.status_code, 201)
                file_id = response.json()["file_id"]

                other_detail_response = client.get(f"/api/v1/files/{file_id}", headers=other_headers)
                admin_detail_response = client.get(f"/api/v1/files/{file_id}", headers=admin_headers)
                other_upload_response = client.put(
                    f"/api/v1/files/{file_id}/content",
                    headers={**other_headers, "Content-Type": "application/pdf"},
                    content=pdf_content,
                )

                owner_uploaded_response = client.put(
                    f"/api/v1/files/{file_id}/content",
                    headers={**owner_headers, "Content-Type": "application/pdf"},
                    content=pdf_content,
                )
                other_uploaded_detail_response = client.get(f"/api/v1/files/{file_id}", headers=other_headers)

                admin_authorization_response = client.post(
                    "/api/v1/files/upload-url",
                    headers=owner_headers,
                    json={
                        "filename": "admin-uploadable-source.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(pdf_content),
                        "file_type": "source_pdf",
                    },
                )
                self.assertEqual(admin_authorization_response.status_code, 201)
                admin_upload_file_id = admin_authorization_response.json()["file_id"]
                admin_upload_response = client.put(
                    f"/api/v1/files/{admin_upload_file_id}/content",
                    headers={**admin_headers, "Content-Type": "application/pdf"},
                    content=pdf_content,
                )

            record = runtime.document_file_repository.get_document_file(file_id)
            admin_uploaded_record = runtime.document_file_repository.get_document_file(admin_upload_file_id)

        self.assertEqual(other_detail_response.status_code, 403)
        self.assertEqual(other_detail_response.json()["error_code"], "forbidden")
        self.assertEqual(admin_detail_response.status_code, 200)
        self.assertEqual(other_upload_response.status_code, 403)
        self.assertEqual(other_upload_response.json()["error_code"], "forbidden")
        self.assertEqual(owner_uploaded_response.status_code, 201)
        self.assertEqual(other_uploaded_detail_response.status_code, 403)
        self.assertEqual(admin_upload_response.status_code, 201)
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "uploaded")
        self.assertEqual(record.created_by, "user_operator")
        self.assertIsNotNone(admin_uploaded_record)
        self.assertEqual(admin_uploaded_record.status, "uploaded")
        self.assertEqual(admin_uploaded_record.created_by, "user_operator")

    def test_file_retention_plan_is_admin_only_and_reports_dry_run_candidates(self):
        """验证 Admin 可查看保留期计划，Operator 不能访问且接口不删除文件。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_old")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                admin_response = client.get("/api/v1/files/retention/plan", headers=admin_headers)
                operator_response = client.get("/api/v1/files/retention/plan", headers=operator_headers)
            object_still_exists = stale_path.exists()

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "dry_run")
        self.assertFalse(payload["deletion_supported"])
        self.assertEqual(payload["totals"]["candidate_files"], 1)
        self.assertEqual(payload["candidates"][0]["file_id"], stale_file.id)
        self.assertEqual(payload["candidates"][0]["job_id"], stale_file.job_id)
        self.assertTrue(object_still_exists)
        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")

    def test_file_retention_mark_expired_updates_metadata_without_removing_object(self):
        """验证标记过期只更新 metadata，保留对象文件并记录审计事件。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_mark")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                mark_response = client.post(
                    "/api/v1/files/retention/mark-expired",
                    headers={**admin_headers, "X-Trace-Id": "trace_retention_mark"},
                )
                plan_after_response = client.get("/api/v1/files/retention/plan", headers=admin_headers)

            updated_file = runtime.document_file_repository.get_document_file(stale_file.id)
            audit_events = runtime.audit_event_repository.list_audit_events()
            object_still_exists = stale_path.exists()
            object_bytes = stale_path.read_bytes()

        self.assertEqual(mark_response.status_code, 200)
        mark_payload = mark_response.json()
        self.assertEqual(mark_payload["action_mode"], "mark_expired")
        self.assertEqual(mark_payload["marked_file_ids"], [stale_file.id])
        self.assertEqual(mark_payload["candidates"][0]["status"], "expired")
        self.assertIsNotNone(updated_file)
        self.assertEqual(updated_file.status, "expired")
        self.assertTrue(object_still_exists)
        self.assertEqual(object_bytes, b"expired-file-content")
        self.assertEqual(plan_after_response.status_code, 200)
        self.assertEqual(plan_after_response.json()["candidates"][0]["status"], "expired")
        retention_events = [
            event
            for event in audit_events
            if event.action == "file.retention_mark_expired"
        ]
        self.assertEqual(len(retention_events), 1)
        self.assertEqual(retention_events[0].trace_id, "trace_retention_mark")

    def test_file_storage_usage_is_admin_only_readonly_and_reports_reclaim_estimates(self):
        """验证 storage usage 只读汇总 metadata，并按物理删除前置条件估算可回收空间。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            now = utc_now()
            reclaimable_file = DocumentFileRecord(
                id="file_storage_usage_reclaimable",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_storage_usage",
                file_type="generated_word",
                storage_provider="local_object",
                bucket="local-object",
                object_key="document-jobs/tenant_default/docjob_storage_usage/generated_word/reclaimable.docx",
                original_filename="reclaimable.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=100,
                status="expired",
                expires_at=now - timedelta(days=1),
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=1),
            )
            unsupported_s3_file = DocumentFileRecord(
                id="file_storage_usage_s3",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_storage_usage",
                file_type="source_pdf",
                storage_provider="s3",
                bucket="bucket",
                object_key="document-files/source.pdf",
                original_filename="source.pdf",
                mime_type="application/pdf",
                size_bytes=200,
                status="expired",
                expires_at=now - timedelta(days=1),
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=1),
            )
            missing_key_file = DocumentFileRecord(
                id="file_storage_usage_missing_key",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_storage_usage",
                file_type="generated_word",
                storage_provider="local_object",
                bucket="local-object",
                object_key="",
                original_filename="missing-key.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=300,
                status="expired",
                expires_at=now - timedelta(days=1),
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=1),
            )
            uploaded_expired_file = DocumentFileRecord(
                id="file_storage_usage_uploaded_expired",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_storage_usage",
                file_type="image_asset",
                storage_provider="local_object",
                bucket="local-object",
                object_key="document-jobs/tenant_default/docjob_storage_usage/image_asset/uploaded.png",
                original_filename="uploaded.png",
                mime_type="image/png",
                size_bytes=400,
                status="uploaded",
                expires_at=now - timedelta(days=1),
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=1),
            )
            active_file = DocumentFileRecord(
                id="file_storage_usage_active",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_storage_usage",
                file_type="source_pdf",
                storage_provider="local_object",
                bucket="local-object",
                object_key="document-files/active.pdf",
                original_filename="active.pdf",
                mime_type="application/pdf",
                size_bytes=500,
                status="uploaded",
                expires_at=now + timedelta(days=1),
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(days=1),
            )
            deleted_file = DocumentFileRecord(
                id="file_storage_usage_deleted",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_storage_usage",
                file_type="generated_word",
                storage_provider="local_object",
                bucket="local-object",
                object_key="document-jobs/tenant_default/docjob_storage_usage/generated_word/deleted.docx",
                original_filename="deleted.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=600,
                status="deleted",
                expires_at=now - timedelta(days=1),
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=1),
            )
            for record in [
                reclaimable_file,
                unsupported_s3_file,
                missing_key_file,
                uploaded_expired_file,
                active_file,
                deleted_file,
            ]:
                runtime.document_file_repository.create_document_file(record)
            reclaimable_path = runtime.file_upload_service.resolve_local_object_path(reclaimable_file.object_key)
            reclaimable_path.parent.mkdir(parents=True, exist_ok=True)
            reclaimable_path.write_bytes(b"still-present")
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                admin_response = client.get("/api/v1/files/storage/usage", headers=admin_headers)
                operator_response = client.get("/api/v1/files/storage/usage", headers=operator_headers)

            record_after_usage = runtime.document_file_repository.get_document_file(reclaimable_file.id)
            audit_events = runtime.audit_event_repository.list_audit_events()
            object_still_exists = reclaimable_path.exists()

        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["artifact_storage"], "local_object")
        self.assertTrue(payload["artifact_root_writable"])
        self.assertIsInstance(payload["artifact_disk_free_bytes"], int)
        self.assertEqual(payload["totals"]["files_seen"], 6)
        self.assertEqual(payload["totals"]["active_files"], 5)
        self.assertEqual(payload["totals"]["expired_files"], 4)
        self.assertEqual(payload["totals"]["deleted_files"], 1)
        self.assertEqual(payload["totals"]["total_size_bytes"], 2100)
        self.assertEqual(payload["totals"]["active_size_bytes"], 1500)
        self.assertEqual(payload["totals"]["expired_size_bytes"], 1000)
        self.assertEqual(payload["totals"]["deleted_metadata_size_bytes"], 600)
        self.assertEqual(payload["reclaim"]["estimated_reclaimable_files"], 1)
        self.assertEqual(payload["reclaim"]["estimated_reclaimable_size_bytes"], 100)
        self.assertEqual(payload["reclaim"]["unsupported_storage_files"], 1)
        self.assertEqual(payload["reclaim"]["unsupported_storage_size_bytes"], 200)
        self.assertEqual(payload["reclaim"]["blocked_missing_object_key_files"], 1)
        self.assertEqual(payload["reclaim"]["blocked_missing_object_key_size_bytes"], 300)
        self.assertEqual(payload["reclaim"]["blocked_not_expired_status_files"], 1)
        self.assertEqual(payload["reclaim"]["blocked_not_expired_status_size_bytes"], 400)
        self.assertEqual(payload["reclaim"]["deleted_metadata_files"], 1)
        self.assertEqual(payload["reclaim"]["estimation_basis"], "metadata_only")
        self.assertEqual(payload["quota"]["configured"], False)
        self.assertEqual(payload["quota"]["status"], "not_configured")
        self.assertEqual(payload["quota"]["used_size_bytes"], 1500)
        groups_by_provider = {group["key"]: group for group in payload["by_storage_provider"]}
        self.assertEqual(groups_by_provider["local_object"]["file_count"], 5)
        self.assertEqual(groups_by_provider["local_object"]["estimated_reclaimable_size_bytes"], 100)
        self.assertEqual(groups_by_provider["s3"]["expired_size_bytes"], 200)
        groups_by_file_type = {group["key"]: group for group in payload["by_file_type"]}
        self.assertEqual(groups_by_file_type["generated_word"]["file_count"], 3)
        self.assertEqual(groups_by_file_type["source_pdf"]["size_bytes"], 700)
        groups_by_status = {group["key"]: group for group in payload["by_status"]}
        self.assertEqual(groups_by_status["expired"]["estimated_reclaimable_count"], 1)
        self.assertEqual(groups_by_status["uploaded"]["expired_size_bytes"], 400)
        self.assertTrue(object_still_exists)
        self.assertIsNotNone(record_after_usage)
        self.assertEqual(record_after_usage.status, "expired")
        self.assertEqual(
            [
                event
                for event in audit_events
                if event.action.startswith("file.storage") or event.action == "file.storage_usage"
            ],
            [],
        )

    def test_file_quota_policy_dry_run_reports_would_block_without_side_effects(self):
        """验证 quota policy dry-run 只报告 would_block，不创建上传授权或写审计。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_internal_users_json=build_auth_users_json(),
                auth_jwt_secret_key="test-secret",
                jobs_upload_max_bytes=5_000,
                files_quota_policy_enabled=True,
                files_quota_policy_dry_run=True,
                files_quota_bytes=2_000,
                files_quota_warning_threshold_ratio=0.8,
                files_quota_block_threshold_ratio=1.0,
            )
            active_file = DocumentFileRecord(
                id="file_quota_active",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_quota",
                file_type="source_pdf",
                storage_provider="local_object",
                bucket="local-object",
                object_key="document-files/quota/active.pdf",
                original_filename="active.pdf",
                mime_type="application/pdf",
                size_bytes=1_500,
                status="uploaded",
                expires_at=utc_now() + timedelta(days=1),
            )
            deleted_file = DocumentFileRecord(
                id="file_quota_deleted",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_quota",
                file_type="generated_word",
                storage_provider="local_object",
                bucket="local-object",
                object_key="document-files/quota/deleted.docx",
                original_filename="deleted.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=10_000,
                status="deleted",
                expires_at=utc_now() - timedelta(days=1),
            )
            runtime.document_file_repository.create_document_file(active_file)
            runtime.document_file_repository.create_document_file(deleted_file)
            before_file_ids = [
                record.id
                for record in runtime.document_file_repository.list_document_files()
            ]
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.post(
                    "/api/v1/files/quota-policy/dry-run",
                    headers=admin_headers,
                    json={
                        "filename": "large.pdf",
                        "file_type": "source_pdf",
                        "size_bytes": 700,
                    },
                )

            after_file_ids = [
                record.id
                for record in runtime.document_file_repository.list_document_files()
            ]
            after_audit_actions = [
                event.action
                for event in runtime.audit_event_repository.list_audit_events()
            ]

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["action_mode"], "quota_policy_dry_run")
        self.assertEqual(payload["file_type"], "source_pdf")
        self.assertEqual(payload["filename"], "large.pdf")
        self.assertEqual(payload["policy"]["status"], "dry_run")
        self.assertEqual(payload["policy"]["quota_bytes"], 2_000)
        self.assertEqual(payload["policy"]["upload_max_bytes"], 5_000)
        self.assertEqual(payload["usage"]["current_used_size_bytes"], 1_500)
        self.assertEqual(payload["usage"]["proposed_upload_size_bytes"], 700)
        self.assertEqual(payload["usage"]["projected_used_size_bytes"], 2_200)
        self.assertTrue(payload["would_warn"])
        self.assertTrue(payload["would_block"])
        self.assertIn("projected_usage_reaches_warning_threshold", payload["reasons"])
        self.assertIn("projected_usage_reaches_block_threshold", payload["reasons"])
        self.assertIn("quota_policy_dry_run_only", payload["reasons"])
        self.assertTrue(payload["safety"]["read_only"])
        self.assertFalse(payload["safety"]["upload_authorization_created"])
        self.assertFalse(payload["safety"]["upload_blocking_executed"])
        self.assertFalse(payload["safety"]["metadata_mutated"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertEqual(before_file_ids, after_file_ids)
        self.assertEqual(
            [
                action
                for action in after_audit_actions
                if action.startswith("file.quota") or action == "file.upload_authorize"
            ],
            [],
        )

    def test_file_quota_policy_dry_run_is_admin_only_and_upload_url_unchanged(self):
        """验证 quota dry-run 只允许 Admin，且 staged would_block 不改变真实上传授权。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_internal_users_json=build_auth_users_json(),
                auth_jwt_secret_key="test-secret",
                jobs_upload_max_bytes=5_000,
                files_quota_policy_enabled=True,
                files_quota_policy_dry_run=True,
                files_quota_bytes=2_000,
            )
            runtime.document_file_repository.create_document_file(
                DocumentFileRecord(
                    id="file_quota_existing",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    job_id="docjob_quota",
                    file_type="source_pdf",
                    storage_provider="local_object",
                    bucket="local-object",
                    object_key="document-files/quota/existing.pdf",
                    original_filename="existing.pdf",
                    mime_type="application/pdf",
                    size_bytes=1_500,
                    status="uploaded",
                    expires_at=utc_now() + timedelta(days=1),
                )
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                admin_dry_run = client.post(
                    "/api/v1/files/quota-policy/dry-run",
                    headers=admin_headers,
                    json={"filename": "still-authorized.pdf", "size_bytes": 700},
                )
                operator_dry_run = client.post(
                    "/api/v1/files/quota-policy/dry-run",
                    headers=operator_headers,
                    json={"filename": "still-authorized.pdf", "size_bytes": 700},
                )
                upload_response = client.post(
                    "/api/v1/files/upload-url",
                    headers=operator_headers,
                    json={
                        "filename": "still-authorized.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": 700,
                    },
                )

            audit_actions = [
                event.action
                for event in runtime.audit_event_repository.list_audit_events()
            ]

        self.assertEqual(admin_dry_run.status_code, 200)
        self.assertTrue(admin_dry_run.json()["would_block"])
        self.assertEqual(operator_dry_run.status_code, 403)
        self.assertEqual(operator_dry_run.json()["error_code"], "role_forbidden")
        self.assertEqual(upload_response.status_code, 201)
        self.assertEqual(upload_response.json()["file"]["status"], "pending_upload")
        self.assertEqual(upload_response.json()["file"]["size_bytes"], 700)
        self.assertEqual(audit_actions.count("file.upload_authorize"), 1)
        self.assertNotIn("file.quota_policy_dry_run", audit_actions)

    def test_file_quota_policy_ready_blocks_upload_authorization_and_audits(self):
        """验证 ready quota policy 超额时阻断上传授权并写结构化审计。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_internal_users_json=build_auth_users_json(),
                auth_jwt_secret_key="test-secret",
                jobs_upload_max_bytes=5_000,
                files_quota_policy_enabled=True,
                files_quota_policy_dry_run=False,
                files_quota_bytes=2_000,
            )
            runtime.document_file_repository.create_document_file(
                DocumentFileRecord(
                    id="file_quota_enforce_existing",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    job_id="docjob_quota",
                    file_type="source_pdf",
                    storage_provider="local_object",
                    bucket="local-object",
                    object_key="document-files/quota/enforce-existing.pdf",
                    original_filename="existing.pdf",
                    mime_type="application/pdf",
                    size_bytes=1_500,
                    status="uploaded",
                    expires_at=utc_now() + timedelta(days=1),
                )
            )
            before_file_ids = [
                record.id
                for record in runtime.document_file_repository.list_document_files()
            ]
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                response = client.post(
                    "/api/v1/files/upload-url",
                    headers={**operator_headers, "X-Trace-Id": "trace_quota_block"},
                    json={
                        "filename": "blocked.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": 700,
                    },
                )

            after_file_ids = [
                record.id
                for record in runtime.document_file_repository.list_document_files()
            ]
            quota_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "file.quota_policy_block"
            ]
            upload_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "file.upload_authorize"
            ]

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "conflict")
        self.assertIn("quota policy", response.json()["detail"])
        self.assertEqual(before_file_ids, after_file_ids)
        self.assertEqual(upload_events, [])
        self.assertEqual(len(quota_events), 1)
        self.assertEqual(quota_events[0].trace_id, "trace_quota_block")
        self.assertIn("outcome=blocked", quota_events[0].reason)
        self.assertIsNotNone(quota_events[0].details)
        self.assertEqual(quota_events[0].details["outcome"], "blocked")
        self.assertEqual(quota_events[0].details["policy"]["status"], "ready")
        self.assertEqual(quota_events[0].details["usage"]["current_used_size_bytes"], 1_500)
        self.assertEqual(quota_events[0].details["usage"]["projected_used_size_bytes"], 2_200)
        self.assertTrue(quota_events[0].details["would_block"])
        self.assertTrue(quota_events[0].details["safety"]["upload_blocking_executed"])
        self.assertFalse(quota_events[0].details["safety"]["upload_authorization_created_by_quota_policy"])

    def test_file_quota_policy_admin_override_allows_upload_and_audits(self):
        """验证 Admin override 可放行 quota block，并写 override 与 upload 授权审计。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_internal_users_json=build_auth_users_json(),
                auth_jwt_secret_key="test-secret",
                jobs_upload_max_bytes=5_000,
                files_quota_policy_enabled=True,
                files_quota_policy_dry_run=False,
                files_quota_bytes=2_000,
            )
            runtime.document_file_repository.create_document_file(
                DocumentFileRecord(
                    id="file_quota_override_existing",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    job_id="docjob_quota",
                    file_type="source_pdf",
                    storage_provider="local_object",
                    bucket="local-object",
                    object_key="document-files/quota/override-existing.pdf",
                    original_filename="existing.pdf",
                    mime_type="application/pdf",
                    size_bytes=1_500,
                    status="uploaded",
                    expires_at=utc_now() + timedelta(days=1),
                )
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.post(
                    "/api/v1/files/upload-url",
                    headers={**admin_headers, "X-Trace-Id": "trace_quota_override"},
                    json={
                        "filename": "override.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": 700,
                        "quota_override_reason": "temporary customer migration",
                        "quota_override_confirmation": "OVERRIDE FILE QUOTA POLICY",
                    },
                )

            quota_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "file.quota_policy_override"
            ]
            upload_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "file.upload_authorize"
            ]
            stored_files = runtime.document_file_repository.list_document_files()

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["file"]["status"], "pending_upload")
        self.assertEqual(payload["file"]["size_bytes"], 700)
        self.assertEqual(len(stored_files), 2)
        self.assertEqual(len(quota_events), 1)
        self.assertEqual(len(upload_events), 1)
        self.assertEqual(quota_events[0].trace_id, "trace_quota_override")
        self.assertIn("outcome=overridden", quota_events[0].reason)
        self.assertIsNotNone(quota_events[0].details)
        self.assertEqual(quota_events[0].details["outcome"], "overridden")
        self.assertTrue(quota_events[0].details["override"]["requested"])
        self.assertTrue(quota_events[0].details["override"]["allowed"])
        self.assertTrue(quota_events[0].details["override"]["applied"])
        self.assertFalse(quota_events[0].details["safety"]["upload_blocking_executed"])

    def test_file_quota_policy_ops_summary_is_admin_only_readonly_and_reports_rollback(self):
        """验证 quota ops summary 只允许 Admin 读取，并返回回滚开关和只读安全合同。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_internal_users_json=build_auth_users_json(),
                auth_jwt_secret_key="test-secret",
                jobs_upload_max_bytes=5_000,
                files_quota_policy_enabled=True,
                files_quota_policy_dry_run=False,
                files_quota_bytes=2_000,
            )
            runtime.document_file_repository.create_document_file(
                DocumentFileRecord(
                    id="file_quota_ops_existing",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    job_id="docjob_quota_ops",
                    file_type="source_pdf",
                    storage_provider="local_object",
                    bucket="local-object",
                    object_key="document-files/quota/ops-existing.pdf",
                    original_filename="existing.pdf",
                    mime_type="application/pdf",
                    size_bytes=1_500,
                    status="uploaded",
                    expires_at=utc_now() + timedelta(days=1),
                )
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                files_before = runtime.document_file_repository.list_document_files()
                audit_events_before = runtime.audit_event_repository.list_audit_events()
                admin_response = client.get(
                    "/api/v1/files/quota-policy/ops-summary",
                    headers=admin_headers,
                )
                operator_response = client.get(
                    "/api/v1/files/quota-policy/ops-summary",
                    headers=operator_headers,
                )
                files_after = runtime.document_file_repository.list_document_files()
                audit_events_after = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "quota_policy_ops_summary")
        self.assertEqual(payload["policy"]["status"], "ready")
        self.assertTrue(payload["enforcement_ready"])
        self.assertFalse(payload["kill_switch_enabled"])
        self.assertEqual(payload["usage"]["current_used_size_bytes"], 1_500)
        self.assertEqual(payload["usage"]["proposed_upload_size_bytes"], 0)
        self.assertEqual(payload["usage"]["projected_used_size_bytes"], 1_500)
        self.assertFalse(payload["current_usage_would_block"])
        rollback_by_id = {option["option_id"]: option for option in payload["rollback_options"]}
        self.assertEqual(rollback_by_id["enable_kill_switch"]["env_var"], "FILES_QUOTA_POLICY_KILL_SWITCH")
        self.assertEqual(rollback_by_id["enable_kill_switch"]["target_value"], "true")
        self.assertFalse(rollback_by_id["enable_kill_switch"]["currently_effective"])
        self.assertEqual(rollback_by_id["force_dry_run"]["env_var"], "FILES_QUOTA_POLICY_DRY_RUN")
        self.assertEqual(rollback_by_id["disable_policy"]["env_var"], "FILES_QUOTA_POLICY_ENABLED")
        self.assertTrue(payload["safety"]["read_only"])
        self.assertFalse(payload["safety"]["upload_authorization_created"])
        self.assertFalse(payload["safety"]["upload_blocking_executed"])
        self.assertFalse(payload["safety"]["metadata_mutated"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["delete_executed"])
        self.assertFalse(payload["safety"]["cleanup_executed"])
        self.assertFalse(payload["safety"]["scheduler_loop_executed"])
        self.assertFalse(payload["safety"]["conversion_workflow_executed"])
        self.assertEqual([record.model_dump() for record in files_before], [record.model_dump() for record in files_after])
        self.assertEqual(audit_events_before, audit_events_after)

    def test_file_quota_policy_ops_summary_replays_block_and_override_audits(self):
        """验证 quota ops summary 能重放最近 quota block/override 审计细节。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_internal_users_json=build_auth_users_json(),
                auth_jwt_secret_key="test-secret",
            )
            base_time = utc_now()
            runtime.audit_event_repository.append_audit_event(
                AuditEvent(
                    audit_id="audit_quota_block_old",
                    actor_id="user_operator",
                    actor_role="operator",
                    action="file.quota_policy_block",
                    target_type="file_quota_policy",
                    target_id="document_files",
                    reason="outcome=blocked actor_role=operator",
                    details={
                        "outcome": "blocked",
                        "file_type": "source_pdf",
                        "filename": "blocked.pdf",
                        "policy": {"status": "ready", "quota_bytes": 2_000},
                        "usage": {
                            "current_used_size_bytes": 1_500,
                            "proposed_upload_size_bytes": 700,
                            "projected_used_size_bytes": 2_200,
                        },
                        "would_block": True,
                        "reasons": ["projected_usage_reaches_block_threshold", "quota_policy_enforced_block"],
                        "override": {"applied": False},
                    },
                    trace_id="trace_quota_block_replay",
                    created_at=base_time - timedelta(minutes=2),
                )
            )
            runtime.audit_event_repository.append_audit_event(
                AuditEvent(
                    audit_id="audit_quota_override_new",
                    actor_id="user_admin",
                    actor_role="admin",
                    action="file.quota_policy_override",
                    target_type="file_quota_policy",
                    target_id="document_files",
                    reason="outcome=overridden actor_role=admin",
                    details={
                        "outcome": "overridden",
                        "file_type": "source_pdf",
                        "filename": "override.pdf",
                        "policy": {"status": "ready", "quota_bytes": 2_000},
                        "usage": {
                            "current_used_size_bytes": 1_500,
                            "proposed_upload_size_bytes": 700,
                            "projected_used_size_bytes": 2_200,
                        },
                        "would_block": True,
                        "reasons": ["quota_policy_admin_override_applied"],
                        "override": {"applied": True},
                    },
                    trace_id="trace_quota_override_replay",
                    created_at=base_time - timedelta(minutes=1),
                )
            )
            runtime.audit_event_repository.append_audit_event(
                AuditEvent(
                    audit_id="audit_unrelated",
                    actor_id="user_admin",
                    actor_role="admin",
                    action="file.retention_mark_expired",
                    target_type="document_file_retention",
                    target_id="document_files",
                    reason="marked=1",
                    trace_id="trace_unrelated",
                    created_at=base_time,
                )
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                audit_events_before = runtime.audit_event_repository.list_audit_events()
                response = client.get(
                    "/api/v1/files/quota-policy/ops-summary",
                    headers=admin_headers,
                    params={"replay_limit": 2},
                )
                truncated_response = client.get(
                    "/api/v1/files/quota-policy/ops-summary",
                    headers=admin_headers,
                    params={"replay_limit": 1},
                )
                audit_events_after = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["audit_replay_total"], 2)
        self.assertEqual(payload["audit_replay_limit"], 2)
        self.assertFalse(payload["audit_replay_truncated"])
        self.assertEqual([item["audit_id"] for item in payload["audit_replay"]], ["audit_quota_override_new", "audit_quota_block_old"])
        override_item = payload["audit_replay"][0]
        block_item = payload["audit_replay"][1]
        self.assertEqual(override_item["outcome"], "overridden")
        self.assertEqual(override_item["trace_id"], "trace_quota_override_replay")
        self.assertTrue(override_item["would_block"])
        self.assertTrue(override_item["override_applied"])
        self.assertEqual(override_item["projected_used_size_bytes"], 2_200)
        self.assertEqual(override_item["quota_bytes"], 2_000)
        self.assertEqual(override_item["policy_status"], "ready")
        self.assertEqual(override_item["details"]["usage"]["projected_used_size_bytes"], 2_200)
        self.assertEqual(block_item["outcome"], "blocked")
        self.assertEqual(block_item["trace_id"], "trace_quota_block_replay")
        self.assertFalse(block_item["override_applied"])
        self.assertIn("quota_policy_enforced_block", block_item["reasons"])
        self.assertEqual(truncated_response.status_code, 200)
        truncated_payload = truncated_response.json()
        self.assertEqual(truncated_payload["audit_replay_total"], 2)
        self.assertEqual(truncated_payload["audit_replay_limit"], 1)
        self.assertTrue(truncated_payload["audit_replay_truncated"])
        self.assertEqual([item["audit_id"] for item in truncated_payload["audit_replay"]], ["audit_quota_override_new"])
        self.assertEqual(audit_events_before, audit_events_after)

    def test_file_library_search_is_admin_only_readonly_safe_and_filterable(self):
        """验证 Admin-only 文件库搜索只返回安全摘要，并支持筛选、排序和分页。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            now = utc_now()
            local_expired = DocumentFileRecord(
                id="file_library_local_expired",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_library_a",
                file_type="generated_word",
                storage_provider="local_object",
                bucket="private-bucket",
                object_key="secret/local/report-final.docx",
                original_filename="report-final.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=900,
                checksum_sha256="secret-checksum",
                etag="secret-etag",
                status="expired",
                expires_at=now - timedelta(days=1),
                metadata={"prompt": "secret prompt"},
                created_by="user_operator",
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=1),
            )
            s3_expired = DocumentFileRecord(
                id="file_library_s3_expired",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_library_b",
                file_type="generated_word",
                storage_provider="s3",
                bucket="s3-secret-bucket",
                object_key="secret/s3/report-archive.docx",
                original_filename="report-archive.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=200,
                status="expired",
                expires_at=now - timedelta(days=1),
                created_by="user_admin",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=1),
            )
            active_source = DocumentFileRecord(
                id="file_library_active_source",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_library_c",
                file_type="source_pdf",
                storage_provider="local_object",
                bucket="private-bucket",
                object_key="secret/local/source.pdf",
                original_filename="source.pdf",
                mime_type="application/pdf",
                size_bytes=100,
                status="uploaded",
                expires_at=now + timedelta(days=1),
                created_by="user_operator",
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(days=1),
            )
            for record in [local_expired, s3_expired, active_source]:
                runtime.document_file_repository.create_document_file(record)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                first_page_response = client.get(
                    "/api/v1/files/library/search",
                    headers=admin_headers,
                    params={
                        "q": "report",
                        "file_type": "generated_word",
                        "status": "expired",
                        "sort": "size_bytes_desc",
                        "page": 1,
                        "page_size": 1,
                    },
                )
                second_page_response = client.get(
                    "/api/v1/files/library/search",
                    headers=admin_headers,
                    params={
                        "q": "report",
                        "file_type": "generated_word",
                        "status": "expired",
                        "sort": "size_bytes_desc",
                        "page": 2,
                        "page_size": 1,
                    },
                )
                operator_response = client.get("/api/v1/files/library/search", headers=operator_headers)
            record_after_search = runtime.document_file_repository.get_document_file(local_expired.id)
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(first_page_response.status_code, 200)
        first_payload = first_page_response.json()
        second_payload = second_page_response.json()
        serialized_payload = json.dumps(first_payload, ensure_ascii=False)
        first_item = first_payload["items"][0]

        self.assertEqual(first_payload["total"], 2)
        self.assertEqual(first_payload["page"], 1)
        self.assertEqual(first_payload["page_size"], 1)
        self.assertEqual(first_payload["filters"]["q"], "report")
        self.assertEqual(first_payload["filters"]["status"], "expired")
        self.assertEqual(first_item["file_id"], local_expired.id)
        self.assertEqual(first_item["original_filename"], "report-final.docx")
        self.assertEqual(first_item["size_bytes"], 900)
        self.assertEqual(first_item["expired"], True)
        self.assertEqual(first_item["physical_delete_candidate"], True)
        self.assertEqual(second_payload["items"][0]["file_id"], s3_expired.id)
        self.assertEqual(second_payload["items"][0]["physical_delete_candidate"], False)
        self.assertNotIn("object_key", first_item)
        self.assertNotIn("bucket", first_item)
        self.assertNotIn("checksum_sha256", first_item)
        self.assertNotIn("etag", first_item)
        self.assertNotIn("metadata", first_item)
        self.assertNotIn("secret/local/report-final.docx", serialized_payload)
        self.assertNotIn("secret-checksum", serialized_payload)
        self.assertNotIn("secret-etag", serialized_payload)
        self.assertNotIn("secret prompt", serialized_payload)
        self.assertIsNotNone(record_after_search)
        self.assertEqual(record_after_search.status, "expired")
        self.assertEqual(
            [event for event in audit_events if event.action.startswith("file.library")],
            [],
        )

    def test_file_retention_readonly_cleanup_runner_reports_without_mutation(self):
        """验证只读 cleanup runner 生成报告但不修改 metadata 或删除对象。"""

        from scripts.ops.run_file_retention_cleanup_readonly import run_readonly_cleanup_report

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_runner")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            output_path = Path(temp_dir) / "reports" / "retention-readonly.json"

            report = run_readonly_cleanup_report(runtime, output_path=output_path)
            report_from_disk = json.loads(output_path.read_text(encoding="utf-8"))
            file_after_runner = runtime.document_file_repository.get_document_file(stale_file.id)
            object_still_exists = stale_path.exists()
            object_bytes = stale_path.read_bytes()
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(report["mode"], "readonly_plan")
        self.assertEqual(report["safety"]["metadata_mutated"], False)
        self.assertEqual(report["safety"]["objects_deleted"], False)
        self.assertEqual(report["safety"]["physical_delete_executed"], False)
        self.assertEqual(report["retention"]["totals"]["candidate_files"], 1)
        self.assertEqual(report["retention"]["candidates"][0]["file_id"], stale_file.id)
        self.assertNotIn("object_key", report["retention"]["candidates"][0])
        self.assertNotIn("bucket", report["retention"]["candidates"][0])
        self.assertEqual(report["storage_usage"]["reclaim"]["estimated_reclaimable_files"], 1)
        self.assertEqual(report_from_disk["run_id"], report["run_id"])
        self.assertTrue(object_still_exists)
        self.assertEqual(object_bytes, b"expired-file-content")
        self.assertIsNotNone(file_after_runner)
        self.assertEqual(file_after_runner.status, "expired")
        self.assertEqual(audit_events, [])

    def test_cleanup_scheduler_dry_run_manual_runner_records_history_and_releases_lock(self):
        """验证手动 scheduler dry-run 只读生成报告、释放 lock 并写入 durable history。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_scheduler_dry_run")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_events_before = list(runtime.audit_event_repository.list_audit_events())
                operator_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/scheduler-dry-run",
                    headers=operator_headers,
                    json={},
                )
                admin_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/scheduler-dry-run",
                    headers={**admin_headers, "X-Trace-Id": "trace_scheduler_dry_run"},
                    json={"owner_id": "manual-test-owner", "lock_ttl_seconds": 60},
                )
                payload = admin_response.json()
                history_response = client.get(
                    f"/api/v1/files/retention/cleanup-runs/history/{payload['run_id']}",
                    headers=admin_headers,
                )
                history_list_response = client.get(
                    "/api/v1/files/retention/cleanup-runs/history",
                    headers=admin_headers,
                )
                audit_events_after = runtime.audit_event_repository.list_audit_events()

            file_after_dry_run = runtime.document_file_repository.get_document_file(stale_file.id)
            object_still_exists = stale_path.exists()
            object_bytes = stale_path.read_bytes()
            lock_status = FileRetentionCleanupLockService(
                runtime.file_retention_cleanup_lock_repository,
            ).get_status()

        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(payload["action_mode"], "scheduler_dry_run")
        self.assertEqual(payload["readonly_report"]["mode"], "readonly_plan")
        self.assertEqual(payload["readonly_report"]["retention"]["totals"]["candidate_files"], 1)
        candidate_payload = payload["readonly_report"]["retention"]["candidates"][0]
        self.assertEqual(candidate_payload["file_id"], stale_file.id)
        self.assertNotIn("object_key", candidate_payload)
        self.assertNotIn("bucket", candidate_payload)
        self.assertFalse(payload["safety"]["scheduler_loop_executed"])
        self.assertTrue(payload["safety"]["scheduler_manual_dry_run_executed"])
        self.assertFalse(payload["safety"]["metadata_mutated"])
        self.assertFalse(payload["safety"]["objects_deleted"])
        self.assertFalse(payload["safety"]["physical_delete_executed"])
        self.assertFalse(payload["safety"]["provider_calls_executed"])
        self.assertFalse(payload["safety"]["s3_delete_executed"])
        self.assertTrue(payload["safety"]["cleanup_lock_acquired"])
        self.assertTrue(payload["safety"]["cleanup_lock_released"])
        self.assertEqual(payload["lock"]["owner_id"], "manual-test-owner")
        self.assertEqual(payload["lock"]["status"], "released")
        self.assertTrue(payload["lock"]["released"])
        self.assertEqual(history_response.status_code, 200)
        history_payload = history_response.json()
        self.assertEqual(history_payload["status"], "dry_run")
        self.assertEqual(history_payload["action_mode"], "scheduler_dry_run")
        self.assertTrue(history_payload["preview_hash"].startswith("sha256:"))
        self.assertEqual(history_payload["requested_file_ids"], [stale_file.id])
        self.assertEqual(history_payload["readonly_report"]["run_id"], payload["run_id"])
        self.assertEqual(history_payload["lock"]["owner_id"], "manual-test-owner")
        self.assertEqual(history_payload["lock"]["status"], "released")
        self.assertTrue(history_payload["lock"]["released"])
        self.assertEqual(history_list_response.status_code, 200)
        self.assertEqual(history_list_response.json()["total"], 1)
        self.assertNotIn(stale_file.object_key, json.dumps(payload, ensure_ascii=False))
        self.assertNotIn(stale_file.bucket, json.dumps(payload, ensure_ascii=False))
        self.assertIsNotNone(file_after_dry_run)
        self.assertEqual(file_after_dry_run.status, "expired")
        self.assertTrue(object_still_exists)
        self.assertEqual(object_bytes, b"expired-file-content")
        self.assertEqual(lock_status.effective_status, "released")
        self.assertEqual(audit_events_after, audit_events_before)

    def test_cleanup_scheduler_dry_run_manual_runner_rejects_active_lock(self):
        """验证已有 active cleanup lock 时手动 scheduler dry-run 返回 409 且不写 history。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_scheduler_dry_run_lock")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            lock_service = FileRetentionCleanupLockService(runtime.file_retention_cleanup_lock_repository)
            lock_service.acquire(owner_id="existing-owner", ttl_seconds=60)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                audit_events_before = list(runtime.audit_event_repository.list_audit_events())
                response = client.post(
                    "/api/v1/files/retention/cleanup-runs/scheduler-dry-run",
                    headers=admin_headers,
                    json={"owner_id": "second-owner", "lock_ttl_seconds": 60},
                )
                history_response = client.get(
                    "/api/v1/files/retention/cleanup-runs/history",
                    headers=admin_headers,
                )
                audit_events_after = runtime.audit_event_repository.list_audit_events()

            file_after_conflict = runtime.document_file_repository.get_document_file(stale_file.id)
            object_still_exists = stale_path.exists()
            lock_status = lock_service.get_status()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "conflict")
        self.assertIn("cleanup lock 已被 existing-owner 持有", json.dumps(response.json(), ensure_ascii=False))
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history_response.json()["total"], 0)
        self.assertEqual(lock_status.effective_status, "active")
        self.assertEqual(lock_status.owner_id, "existing-owner")
        self.assertIsNotNone(file_after_conflict)
        self.assertEqual(file_after_conflict.status, "expired")
        self.assertTrue(object_still_exists)
        self.assertEqual(audit_events_after, audit_events_before)

    def test_file_retention_cleanup_run_preview_is_admin_only_and_readonly(self):
        """验证 cleanup run preview Admin-only 且不修改 metadata 或删除对象。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_cleanup_preview")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                audit_events_before = runtime.audit_event_repository.list_audit_events()
                admin_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/preview",
                    headers=admin_headers,
                    json={"file_ids": [stale_file.id], "max_files": 50},
                )
                operator_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/preview",
                    headers=operator_headers,
                    json={"file_ids": [stale_file.id], "max_files": 50},
                )
                audit_events_after = runtime.audit_event_repository.list_audit_events()

            file_after_preview = runtime.document_file_repository.get_document_file(stale_file.id)
            object_still_exists = stale_path.exists()

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "cleanup_preview")
        self.assertTrue(payload["preview_hash"].startswith("sha256:"))
        self.assertEqual(payload["physical_delete"]["action_mode"], "delete_preview")
        self.assertEqual(payload["physical_delete"]["totals"]["deletable"], 1)
        self.assertFalse(payload["safety"]["scheduler_loop_executed"])
        self.assertFalse(payload["safety"]["physical_delete_executed"])
        self.assertTrue(payload["safety"]["physical_delete_contract_reused"])
        self.assertFalse(payload["safety"]["audit_events_written"])
        self.assertTrue(object_still_exists)
        self.assertIsNotNone(file_after_preview)
        self.assertEqual(file_after_preview.status, "expired")
        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(audit_events_after, audit_events_before)

    def test_file_retention_cleanup_run_execute_reuses_physical_delete_contract_and_audits(self):
        """验证 cleanup run execute 复用物理删除合同、写审计且不会执行 S3 删除。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_cleanup_execute")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            now = utc_now()
            s3_file = DocumentFileRecord(
                id="file_retention_cleanup_s3",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_retention",
                file_type="generated_word",
                storage_provider="s3",
                bucket="test-bucket",
                object_key="document-jobs/tenant_default/docjob_retention/generated_word/s3.docx",
                original_filename="s3.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=10,
                status="expired",
                expires_at=now - timedelta(seconds=1),
                metadata={"s3_version_id": "version-cleanup-001"},
                created_by="user_operator",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=2),
            )
            runtime.document_file_repository.create_document_file(s3_file)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                preview_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/preview",
                    headers=admin_headers,
                    json={"file_ids": [stale_file.id, s3_file.id], "max_files": 50},
                )
                preview_hash = preview_response.json()["preview_hash"]
                execute_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/execute",
                    headers={**admin_headers, "X-Trace-Id": "trace_cleanup_execute"},
                    json={
                        "file_ids": [stale_file.id, s3_file.id],
                        "max_files": 50,
                        "preview_hash": preview_hash,
                        "reason": "monthly cleanup",
                        "confirmation": "EXECUTE AUTOMATED RETENTION CLEANUP",
                    },
                )
                replay_preview = client.post(
                    "/api/v1/files/retention/cleanup-runs/preview",
                    headers=admin_headers,
                    json={"file_ids": [stale_file.id], "max_files": 50},
                )
                replay_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/execute",
                    headers=admin_headers,
                    json={
                        "file_ids": [stale_file.id],
                        "max_files": 50,
                        "preview_hash": replay_preview.json()["preview_hash"],
                        "reason": "idempotent replay",
                        "confirmation": "EXECUTE AUTOMATED RETENTION CLEANUP",
                    },
                )

            stale_after_execute = runtime.document_file_repository.get_document_file(stale_file.id)
            s3_after_execute = runtime.document_file_repository.get_document_file(s3_file.id)
            object_still_exists = stale_path.exists()
            cleanup_events = [
                event
                for event in runtime.audit_event_repository.list_audit_events()
                if event.action == "file.retention_automated_cleanup_execute"
            ]

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(execute_response.status_code, 200)
        payload = execute_response.json()
        preview_payload = preview_response.json()
        self.assertEqual(payload["action_mode"], "cleanup_execute")
        self.assertEqual(payload["physical_delete"]["totals"]["deleted"], 1)
        self.assertEqual(payload["physical_delete"]["totals"]["skipped"], 1)
        outcomes = {item["file_id"]: item["outcome"] for item in payload["physical_delete"]["items"]}
        self.assertEqual(outcomes[stale_file.id], "deleted")
        self.assertEqual(outcomes[s3_file.id], "skipped_unsupported_storage")
        preview_s3_item = next(
            item
            for item in preview_payload["physical_delete"]["items"]
            if item["file_id"] == s3_file.id
        )
        execute_s3_item = next(
            item
            for item in payload["physical_delete"]["items"]
            if item["file_id"] == s3_file.id
        )
        self.assertEqual(preview_s3_item["s3_delete_contract"]["adapter_mode"], "fake")
        self.assertEqual(execute_s3_item["s3_delete_contract"]["bucket"], "test-bucket")
        self.assertEqual(execute_s3_item["s3_delete_contract"]["version_id"], "version-cleanup-001")
        self.assertTrue(execute_s3_item["s3_delete_contract"]["target_exact"])
        self.assertFalse(execute_s3_item["s3_delete_contract"]["safety"]["real_s3_delete_executed"])
        self.assertTrue(execute_s3_item["s3_delete_contract"]["safety"]["fake_s3_delete_executed"])
        self.assertTrue(payload["safety"]["physical_delete_executed"])
        self.assertTrue(payload["safety"]["physical_delete_contract_reused"])
        self.assertFalse(payload["safety"]["s3_delete_executed"])
        self.assertTrue(payload["safety"]["audit_events_written"])
        self.assertFalse(object_still_exists)
        self.assertIsNotNone(stale_after_execute)
        self.assertEqual(stale_after_execute.status, "deleted")
        self.assertIsNotNone(s3_after_execute)
        self.assertEqual(s3_after_execute.status, "expired")
        self.assertEqual(replay_response.status_code, 200)
        self.assertEqual(replay_response.json()["physical_delete"]["items"][0]["outcome"], "skipped_already_deleted")
        self.assertEqual(len(cleanup_events), 2)
        self.assertEqual(cleanup_events[0].trace_id, "trace_cleanup_execute")
        self.assertIn("preview_hash=sha256:", cleanup_events[0].reason)
        self.assertIn("deleted=1", cleanup_events[0].reason)

    def test_cleanup_run_preview_and_execute_records_history(self):
        """验证 cleanup run preview/execute 会落 durable history 并沿用同一 run_id。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_cleanup_history_execute")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                preview_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/preview",
                    headers=admin_headers,
                    json={"file_ids": [stale_file.id], "max_files": 50},
                )
                preview_payload = preview_response.json()
                preview_history_response = client.get(
                    f"/api/v1/files/retention/cleanup-runs/history/{preview_payload['run_id']}",
                    headers=admin_headers,
                )
                execute_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/execute",
                    headers=admin_headers,
                    json={
                        "run_id": preview_payload["run_id"],
                        "file_ids": [stale_file.id],
                        "max_files": 50,
                        "preview_hash": preview_payload["preview_hash"],
                        "plan_id": preview_payload["cleanup_plan"]["plan_id"],
                        "plan_signature": preview_payload["cleanup_plan"]["signature"],
                        "reason": "history execute",
                        "confirmation": "EXECUTE AUTOMATED RETENTION CLEANUP",
                    },
                )
                execute_payload = execute_response.json()
                executed_history_response = client.get(
                    f"/api/v1/files/retention/cleanup-runs/history/{preview_payload['run_id']}",
                    headers=admin_headers,
                )
                history_list_response = client.get(
                    "/api/v1/files/retention/cleanup-runs/history",
                    headers=admin_headers,
                )

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_history_response.status_code, 200)
        preview_history = preview_history_response.json()
        self.assertEqual(preview_history["status"], "previewed")
        self.assertEqual(preview_history["action_mode"], "cleanup_preview")
        self.assertEqual(preview_history["run_id"], preview_payload["run_id"])
        self.assertEqual(preview_history["requested_file_ids"], [stale_file.id])
        self.assertEqual(preview_payload["cleanup_plan"]["run_id"], preview_payload["run_id"])
        self.assertEqual(preview_payload["cleanup_plan"]["requested_file_ids"], [stale_file.id])
        self.assertEqual(preview_payload["cleanup_plan"]["signature_algorithm"], "hmac-sha256")
        self.assertEqual(preview_history["cleanup_plan"]["plan_id"], preview_payload["cleanup_plan"]["plan_id"])
        self.assertEqual(preview_history["safety"]["history_recorded"], True)
        self.assertTrue(preview_history["safety"]["signed_plan_created"])
        self.assertFalse(preview_history["safety"]["physical_delete_executed"])
        self.assertNotIn("object_key", json.dumps(preview_history, ensure_ascii=False))
        self.assertEqual(execute_response.status_code, 200)
        self.assertEqual(execute_payload["run_id"], preview_payload["run_id"])
        self.assertTrue(execute_payload["safety"]["history_recorded"])
        self.assertTrue(execute_payload["safety"]["signed_plan_verified"])
        self.assertEqual(execute_payload["cleanup_plan"]["plan_id"], preview_payload["cleanup_plan"]["plan_id"])
        executed_history = executed_history_response.json()
        self.assertEqual(executed_history["status"], "executed")
        self.assertEqual(executed_history["action_mode"], "cleanup_execute")
        self.assertEqual(executed_history["reason"], "history execute")
        self.assertEqual(executed_history["totals"]["deleted"], 1)
        self.assertTrue(executed_history["safety"]["physical_delete_executed"])
        self.assertTrue(executed_history["safety"]["audit_events_written"])
        self.assertTrue(executed_history["safety"]["signed_plan_verified"])
        self.assertIsNotNone(executed_history["executed_at"])
        self.assertEqual(history_list_response.status_code, 200)
        self.assertEqual(history_list_response.json()["total"], 1)
        self.assertEqual(history_list_response.json()["items"][0]["run_id"], preview_payload["run_id"])

    def test_cleanup_run_signed_plan_blocks_tampering(self):
        """验证 signed cleanup plan 篡改会在物理删除前被阻断并记录 failed history。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_cleanup_plan_tamper")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                preview_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/preview",
                    headers=admin_headers,
                    json={"file_ids": [stale_file.id], "max_files": 50},
                )
                preview_payload = preview_response.json()
                audit_events_before_execute = list(runtime.audit_event_repository.list_audit_events())
                tampered_signature_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/execute",
                    headers=admin_headers,
                    json={
                        "run_id": preview_payload["run_id"],
                        "file_ids": [stale_file.id],
                        "max_files": 50,
                        "preview_hash": preview_payload["preview_hash"],
                        "plan_id": preview_payload["cleanup_plan"]["plan_id"],
                        "plan_signature": "hmac-sha256:tampered",
                        "reason": "tamper plan",
                        "confirmation": "EXECUTE AUTOMATED RETENTION CLEANUP",
                    },
                )
                failed_history_response = client.get(
                    f"/api/v1/files/retention/cleanup-runs/history/{preview_payload['run_id']}",
                    headers=admin_headers,
                )
                audit_events_after_execute = runtime.audit_event_repository.list_audit_events()

            file_after_execute = runtime.document_file_repository.get_document_file(stale_file.id)
            object_still_exists = stale_path.exists()

        self.assertEqual(preview_response.status_code, 200)
        self.assertIsNotNone(preview_payload["cleanup_plan"])
        self.assertEqual(tampered_signature_response.status_code, 409)
        self.assertEqual(tampered_signature_response.json()["error_code"], "conflict")
        failed_history = failed_history_response.json()
        self.assertEqual(failed_history["status"], "failed")
        self.assertEqual(failed_history["error_code"], "cleanup_run_plan_signature_mismatch")
        self.assertEqual(failed_history["cleanup_plan"]["plan_id"], preview_payload["cleanup_plan"]["plan_id"])
        self.assertFalse(failed_history["safety"]["physical_delete_executed"])
        self.assertTrue(failed_history["safety"]["signed_plan_created"])
        self.assertFalse(failed_history["safety"]["signed_plan_verified"])
        self.assertTrue(object_still_exists)
        self.assertIsNotNone(file_after_execute)
        self.assertEqual(file_after_execute.status, "expired")
        self.assertEqual(audit_events_after_execute, audit_events_before_execute)

    def test_cleanup_run_history_is_admin_only_and_not_destructive(self):
        """验证 cleanup run history API Admin-only 且读取历史不会删除或写审计。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_cleanup_history_readonly")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                preview_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/preview",
                    headers=admin_headers,
                    json={"file_ids": [stale_file.id], "max_files": 50},
                )
                audit_events_before_read = list(runtime.audit_event_repository.list_audit_events())
                operator_list_response = client.get(
                    "/api/v1/files/retention/cleanup-runs/history",
                    headers=operator_headers,
                )
                admin_list_response = client.get(
                    "/api/v1/files/retention/cleanup-runs/history",
                    headers=admin_headers,
                )
                missing_detail_response = client.get(
                    "/api/v1/files/retention/cleanup-runs/history/cleanup_run_missing",
                    headers=admin_headers,
                )
                unknown_run_execute_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/execute",
                    headers=admin_headers,
                    json={
                        "run_id": "cleanup_run_unknown",
                        "file_ids": [stale_file.id],
                        "max_files": 50,
                        "preview_hash": preview_response.json()["preview_hash"],
                        "reason": "unknown run guard",
                        "confirmation": "EXECUTE AUTOMATED RETENTION CLEANUP",
                    },
                )
                failed_history_response = client.get(
                    "/api/v1/files/retention/cleanup-runs/history/cleanup_run_unknown",
                    headers=admin_headers,
                )
                audit_events_after_read = runtime.audit_event_repository.list_audit_events()

            file_after_history_reads = runtime.document_file_repository.get_document_file(stale_file.id)
            object_still_exists = stale_path.exists()

        self.assertEqual(operator_list_response.status_code, 403)
        self.assertEqual(operator_list_response.json()["error_code"], "role_forbidden")
        self.assertEqual(admin_list_response.status_code, 200)
        self.assertEqual(admin_list_response.json()["total"], 1)
        self.assertEqual(missing_detail_response.status_code, 404)
        self.assertEqual(unknown_run_execute_response.status_code, 409)
        failed_history = failed_history_response.json()
        self.assertEqual(failed_history["status"], "failed")
        self.assertEqual(failed_history["error_code"], "cleanup_run_preview_not_found")
        self.assertFalse(failed_history["safety"]["physical_delete_executed"])
        self.assertTrue(failed_history["safety"]["history_recorded"])
        self.assertTrue(object_still_exists)
        self.assertIsNotNone(file_after_history_reads)
        self.assertEqual(file_after_history_reads.status, "expired")
        self.assertEqual(audit_events_after_read, audit_events_before_read)

    def test_file_retention_cleanup_run_guards_hash_limits_and_registry_contract(self):
        """验证 cleanup run 的 hash、限流、确认短语和 registry contract。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_cleanup_guard")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                preview_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/preview",
                    headers=admin_headers,
                    json={"file_ids": [stale_file.id], "max_files": 50},
                )
                bad_hash_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/execute",
                    headers=admin_headers,
                    json={
                        "file_ids": [stale_file.id],
                        "max_files": 50,
                        "preview_hash": "sha256:bad",
                        "reason": "cleanup",
                        "confirmation": "EXECUTE AUTOMATED RETENTION CLEANUP",
                    },
                )
                bad_confirmation_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/execute",
                    headers=admin_headers,
                    json={
                        "file_ids": [stale_file.id],
                        "max_files": 50,
                        "preview_hash": preview_response.json()["preview_hash"],
                        "reason": "cleanup",
                        "confirmation": "DELETE EXPIRED FILES",
                    },
                )
                empty_reason_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/execute",
                    headers=admin_headers,
                    json={
                        "file_ids": [stale_file.id],
                        "max_files": 50,
                        "preview_hash": preview_response.json()["preview_hash"],
                        "reason": " ",
                        "confirmation": "EXECUTE AUTOMATED RETENTION CLEANUP",
                    },
                )
                too_many_for_limit_response = client.post(
                    "/api/v1/files/retention/cleanup-runs/preview",
                    headers=admin_headers,
                    json={"file_ids": [stale_file.id, "file_other"], "max_files": 1},
                )
                registry_response = client.get("/api/v1/ops/recovery-actions", headers=admin_headers)

            stale_after_checks = runtime.document_file_repository.get_document_file(stale_file.id)

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(bad_hash_response.status_code, 409)
        self.assertEqual(bad_hash_response.json()["error_code"], "conflict")
        self.assertEqual(bad_confirmation_response.status_code, 400)
        self.assertEqual(empty_reason_response.status_code, 400)
        self.assertEqual(too_many_for_limit_response.status_code, 400)
        self.assertIsNotNone(stale_after_checks)
        self.assertEqual(stale_after_checks.status, "expired")
        actions_by_id = {item["action_id"]: item for item in registry_response.json()["actions"]}
        cleanup_action = actions_by_id["file_retention.automated_cleanup_execute"]
        self.assertTrue(cleanup_action["available"])
        self.assertEqual(cleanup_action["audit_action"], "file.retention_automated_cleanup_execute")
        self.assertTrue(cleanup_action["requires_reason"])
        self.assertTrue(cleanup_action["requires_confirmation"])
        self.assertTrue(cleanup_action["deletes_data"])

    def test_file_retention_policy_crud_is_admin_only_and_audited(self):
        """验证保留策略治理接口 Admin-only，写操作记录审计且不触发物理删除。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                operator_response = client.get("/api/v1/files/retention/policies", headers=operator_headers)
                create_response = client.post(
                    "/api/v1/files/retention/policies",
                    headers={**admin_headers, "X-Trace-Id": "trace_retention_policy_create"},
                    json={
                        "name": "Generated Word short retention",
                        "scope_type": "file_type",
                        "file_type": "generated_word",
                        "retention_days": 14,
                        "description": "test policy",
                    },
                )
                policy_id = create_response.json()["policy_id"]
                update_response = client.patch(
                    f"/api/v1/files/retention/policies/{policy_id}",
                    headers={**admin_headers, "X-Trace-Id": "trace_retention_policy_update"},
                    json={"retention_days": 10},
                )
                publish_response = client.post(
                    f"/api/v1/files/retention/policies/{policy_id}/publish",
                    headers={**admin_headers, "X-Trace-Id": "trace_retention_policy_publish"},
                    json={"reason": "policy governance test"},
                )
                disable_response = client.post(
                    f"/api/v1/files/retention/policies/{policy_id}/disable",
                    headers={**admin_headers, "X-Trace-Id": "trace_retention_policy_disable"},
                    json={"reason": "rollback policy governance test"},
                )

            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "draft")
        self.assertFalse(create_response.json()["is_default"])
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["retention_days"], 10)
        self.assertEqual(publish_response.status_code, 200)
        self.assertEqual(publish_response.json()["status"], "published")
        self.assertTrue(publish_response.json()["is_default"])
        self.assertEqual(disable_response.status_code, 200)
        self.assertEqual(disable_response.json()["status"], "disabled")
        self.assertFalse(disable_response.json()["is_default"])
        retention_policy_events = [
            event
            for event in audit_events
            if event.action.startswith("file.retention_policy_")
        ]
        self.assertEqual(
            [event.action for event in retention_policy_events],
            [
                "file.retention_policy_create",
                "file.retention_policy_update",
                "file.retention_policy_publish",
                "file.retention_policy_disable",
            ],
        )
        self.assertEqual(retention_policy_events[2].trace_id, "trace_retention_policy_publish")
        self.assertIn("retention_days=10", retention_policy_events[2].reason)

    def test_file_retention_policy_impact_preview_and_default_selection_do_not_backfill(self):
        """验证 impact preview 和默认策略切换不回填历史 document_files。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_policy_impact")
            original_expires_at = stale_file.expires_at
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                first_create_response = client.post(
                    "/api/v1/files/retention/policies",
                    headers=admin_headers,
                    json={
                        "name": "Generated Word one day",
                        "scope_type": "file_type",
                        "file_type": "generated_word",
                        "retention_days": 1,
                    },
                )
                first_policy_id = first_create_response.json()["policy_id"]
                preview_response = client.post(
                    f"/api/v1/files/retention/policies/{first_policy_id}/impact-preview",
                    headers=admin_headers,
                    json={"mode": "candidate_policy"},
                )
                first_publish_response = client.post(
                    f"/api/v1/files/retention/policies/{first_policy_id}/publish",
                    headers=admin_headers,
                    json={"reason": "short generated word retention"},
                )
                second_create_response = client.post(
                    "/api/v1/files/retention/policies",
                    headers=admin_headers,
                    json={
                        "name": "Generated Word thirty days",
                        "scope_type": "file_type",
                        "file_type": "generated_word",
                        "retention_days": 30,
                    },
                )
                second_policy_id = second_create_response.json()["policy_id"]
                second_publish_response = client.post(
                    f"/api/v1/files/retention/policies/{second_policy_id}/publish",
                    headers=admin_headers,
                    json={"reason": "longer generated word retention"},
                )
                set_default_response = client.post(
                    f"/api/v1/files/retention/policies/{first_policy_id}/set-default",
                    headers=admin_headers,
                    json={"reason": "restore short generated word retention"},
                )
                first_detail_response = client.get(
                    f"/api/v1/files/retention/policies/{first_policy_id}",
                    headers=admin_headers,
                )
                second_detail_response = client.get(
                    f"/api/v1/files/retention/policies/{second_policy_id}",
                    headers=admin_headers,
                )

            file_after_policy_actions = runtime.document_file_repository.get_document_file(stale_file.id)

        self.assertEqual(preview_response.status_code, 200)
        preview_payload = preview_response.json()
        self.assertEqual(preview_payload["totals"]["matching_files"], 1)
        self.assertEqual(preview_payload["totals"]["would_be_expired"], 1)
        self.assertTrue(preview_payload["items"][0]["would_change_expires_at"])
        self.assertEqual(first_publish_response.status_code, 200)
        self.assertTrue(first_publish_response.json()["is_default"])
        self.assertEqual(second_publish_response.status_code, 200)
        self.assertTrue(second_publish_response.json()["is_default"])
        self.assertEqual(set_default_response.status_code, 200)
        self.assertTrue(set_default_response.json()["is_default"])
        self.assertTrue(first_detail_response.json()["is_default"])
        self.assertFalse(second_detail_response.json()["is_default"])
        self.assertIsNotNone(file_after_policy_actions)
        self.assertEqual(file_after_policy_actions.expires_at, original_expires_at)
        self.assertEqual(file_after_policy_actions.status, "uploaded")

    def test_file_retention_policy_applies_to_new_uploads_and_preserves_fallback(self):
        """验证 published policy 只影响后续新文件，未命中的 file_type 继续使用 settings fallback。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                create_response = client.post(
                    "/api/v1/files/retention/policies",
                    headers=admin_headers,
                    json={
                        "name": "Source PDF seven days",
                        "scope_type": "file_type",
                        "file_type": "source_pdf",
                        "retention_days": 7,
                    },
                )
                policy_id = create_response.json()["policy_id"]
                publish_response = client.post(
                    f"/api/v1/files/retention/policies/{policy_id}/publish",
                    headers=admin_headers,
                    json={"reason": "source pdf retention policy"},
                )
                list_response = client.get("/api/v1/files/retention/policies", headers=admin_headers)
                upload_response = client.post(
                    "/api/v1/files/upload-url",
                    headers=operator_headers,
                    json={
                        "filename": "policy.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(make_pdf_bytes()),
                    },
                )

            uploaded_file_id = upload_response.json()["file_id"]
            uploaded_file = runtime.document_file_repository.get_document_file(uploaded_file_id)

        self.assertEqual(publish_response.status_code, 200)
        self.assertEqual(upload_response.status_code, 201)
        self.assertIsNotNone(uploaded_file)
        self.assertEqual((uploaded_file.expires_at - uploaded_file.created_at).days, 7)
        effective_by_type = {item["file_type"]: item for item in list_response.json()["effective"]}
        self.assertEqual(effective_by_type["source_pdf"]["source"], "published_policy")
        self.assertEqual(effective_by_type["source_pdf"]["retention_days"], 7)
        self.assertEqual(effective_by_type["generated_word"]["source"], "settings_fallback")
        self.assertEqual(effective_by_type["generated_word"]["retention_days"], 90)

    def test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate(self):
        """验证物理删除预览只读，且只有 Admin 可访问。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_delete_preview")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                admin_response = client.post(
                    "/api/v1/files/retention/delete-preview",
                    headers=admin_headers,
                    json={"file_ids": [stale_file.id]},
                )
                operator_response = client.post(
                    "/api/v1/files/retention/delete-preview",
                    headers=operator_headers,
                    json={"file_ids": [stale_file.id]},
                )

            file_after_preview = runtime.document_file_repository.get_document_file(stale_file.id)
            audit_events = runtime.audit_event_repository.list_audit_events()
            object_still_exists = stale_path.exists()

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["action_mode"], "delete_preview")
        self.assertEqual(payload["confirmation_phrase"], "DELETE EXPIRED FILES")
        self.assertEqual(payload["items"][0]["outcome"], "deletable")
        self.assertFalse(payload["items"][0]["deleted"])
        self.assertFalse(payload["items"][0]["metadata_updated"])
        self.assertTrue(object_still_exists)
        self.assertIsNotNone(file_after_preview)
        self.assertEqual(file_after_preview.status, "expired")
        self.assertEqual(
            [
                event
                for event in audit_events
                if event.action == "file.retention_physical_delete"
            ],
            [],
        )
        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(operator_response.json()["error_code"], "role_forbidden")

    def test_file_retention_physical_delete_requires_reason_and_confirmation(self):
        """验证执行物理删除必须带 reason 和确认短语。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_delete_guard")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                bad_confirmation_response = client.post(
                    "/api/v1/files/retention/delete-expired",
                    headers=admin_headers,
                    json={
                        "file_ids": [stale_file.id],
                        "reason": "manual cleanup",
                        "confirmation": "DELETE",
                    },
                )
                padded_confirmation_response = client.post(
                    "/api/v1/files/retention/delete-expired",
                    headers=admin_headers,
                    json={
                        "file_ids": [stale_file.id],
                        "reason": "manual cleanup",
                        "confirmation": " DELETE EXPIRED FILES ",
                    },
                )
                empty_reason_response = client.post(
                    "/api/v1/files/retention/delete-expired",
                    headers=admin_headers,
                    json={
                        "file_ids": [stale_file.id],
                        "reason": "  ",
                        "confirmation": "DELETE EXPIRED FILES",
                    },
                )

            file_after_checks = runtime.document_file_repository.get_document_file(stale_file.id)
            object_still_exists = stale_path.exists()

        self.assertEqual(bad_confirmation_response.status_code, 400)
        self.assertEqual(bad_confirmation_response.json()["error_code"], "invalid_request")
        self.assertEqual(padded_confirmation_response.status_code, 400)
        self.assertEqual(padded_confirmation_response.json()["error_code"], "invalid_request")
        self.assertEqual(empty_reason_response.status_code, 400)
        self.assertEqual(empty_reason_response.json()["error_code"], "invalid_request")
        self.assertTrue(object_still_exists)
        self.assertIsNotNone(file_after_checks)
        self.assertEqual(file_after_checks.status, "expired")

    def test_file_retention_physical_delete_rejects_invalid_file_ids(self):
        """验证物理删除执行拒绝空列表、空白项、重复项和过大批次。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                responses = [
                    client.post(
                        "/api/v1/files/retention/delete-expired",
                        headers=admin_headers,
                        json={
                            "file_ids": file_ids,
                            "reason": "manual cleanup",
                            "confirmation": "DELETE EXPIRED FILES",
                        },
                    )
                    for file_ids in (
                        [],
                        ["file_a", " "],
                        ["file_a", "file_a"],
                        [f"file_{index}" for index in range(51)],
                    )
                ]

        self.assertEqual([response.status_code for response in responses], [400, 400, 400, 400])
        self.assertEqual([response.json()["error_code"] for response in responses], ["invalid_request"] * 4)

    def test_file_retention_physical_delete_removes_expired_local_object_and_marks_deleted(self):
        """验证 eligible expired 本地对象会被删除，metadata 行保留并标记 deleted。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_delete_local")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.post(
                    "/api/v1/files/retention/delete-expired",
                    headers={**admin_headers, "X-Trace-Id": "trace_retention_delete"},
                    json={
                        "file_ids": [stale_file.id],
                        "reason": "manual cleanup",
                        "confirmation": "DELETE EXPIRED FILES",
                    },
                )

            file_after_delete = runtime.document_file_repository.get_document_file(stale_file.id)
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["action_mode"], "delete_execute")
        self.assertEqual(payload["totals"]["deleted"], 1)
        self.assertEqual(payload["totals"]["metadata_updated"], 1)
        self.assertEqual(payload["items"][0]["outcome"], "deleted")
        self.assertTrue(payload["items"][0]["deleted"])
        self.assertTrue(payload["items"][0]["metadata_updated"])
        self.assertFalse(stale_path.exists())
        self.assertIsNotNone(file_after_delete)
        self.assertEqual(file_after_delete.status, "deleted")
        self.assertEqual(file_after_delete.object_key, stale_file.object_key)
        retention_events = [
            event
            for event in audit_events
            if event.action == "file.retention_physical_delete"
        ]
        self.assertEqual(len(retention_events), 1)
        self.assertEqual(retention_events[0].trace_id, "trace_retention_delete")
        self.assertIn("deleted=1", retention_events[0].reason)

    def test_file_retention_physical_delete_treats_missing_local_object_as_idempotent(self):
        """验证 eligible expired 文件内容已缺失时仍可幂等标记 metadata deleted。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_delete_missing")
            runtime.document_file_repository.update_document_file(stale_file.id, status="expired")
            stale_path = runtime.file_upload_service.resolve_local_object_path(stale_file.object_key)
            stale_path.unlink()
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.post(
                    "/api/v1/files/retention/delete-expired",
                    headers=admin_headers,
                    json={
                        "file_ids": [stale_file.id],
                        "reason": "manual cleanup",
                        "confirmation": "DELETE EXPIRED FILES",
                    },
                )

            file_after_delete = runtime.document_file_repository.get_document_file(stale_file.id)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["totals"]["already_missing"], 1)
        self.assertEqual(payload["items"][0]["outcome"], "already_missing")
        self.assertFalse(payload["items"][0]["deleted"])
        self.assertTrue(payload["items"][0]["metadata_updated"])
        self.assertIsNotNone(file_after_delete)
        self.assertEqual(file_after_delete.status, "deleted")

    def test_file_retention_physical_delete_skips_missing_object_key(self):
        """验证缺少 object_key 的本地文件不会进入物理删除执行路径。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            stale_file = self._seed_expired_document_file(runtime, file_id="file_retention_delete_no_key")
            runtime.document_file_repository.update_document_file(
                stale_file.id,
                status="expired",
                object_key="",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.post(
                    "/api/v1/files/retention/delete-expired",
                    headers=admin_headers,
                    json={
                        "file_ids": [stale_file.id],
                        "reason": "manual cleanup",
                        "confirmation": "DELETE EXPIRED FILES",
                    },
                )

            file_after_delete = runtime.document_file_repository.get_document_file(stale_file.id)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["totals"]["skipped"], 1)
        self.assertEqual(payload["items"][0]["outcome"], "skipped_missing_object_key")
        self.assertFalse(payload["items"][0]["metadata_updated"])
        self.assertIsNotNone(file_after_delete)
        self.assertEqual(file_after_delete.status, "expired")

    def test_file_retention_physical_delete_skips_s3_without_mutating_metadata(self):
        """验证 S3 fake delete contract 不执行真实删除，且不会修改 S3 metadata。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            now = utc_now()
            s3_file = DocumentFileRecord(
                id="file_retention_delete_s3",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_retention",
                file_type="generated_word",
                storage_provider="s3",
                bucket="test-bucket",
                object_key="document-jobs/tenant_default/docjob_retention/generated_word/s3.docx",
                original_filename="s3.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=10,
                status="expired",
                expires_at=now - timedelta(seconds=1),
                metadata={"s3_version_id": "version-delete-001"},
                created_by="user_operator",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=2),
            )
            runtime.document_file_repository.create_document_file(s3_file)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                preview_response = client.post(
                    "/api/v1/files/retention/delete-preview",
                    headers=admin_headers,
                    json={"file_ids": [s3_file.id]},
                )
                response = client.post(
                    "/api/v1/files/retention/delete-expired",
                    headers=admin_headers,
                    json={
                        "file_ids": [s3_file.id],
                        "reason": "manual cleanup",
                        "confirmation": "DELETE EXPIRED FILES",
                    },
                )

            file_after_delete = runtime.document_file_repository.get_document_file(s3_file.id)

        self.assertEqual(preview_response.status_code, 200)
        preview_payload = preview_response.json()
        self.assertEqual(preview_payload["items"][0]["outcome"], "skipped_unsupported_storage")
        self.assertEqual(preview_payload["items"][0]["s3_delete_contract"]["adapter_mode"], "fake")
        self.assertEqual(preview_payload["items"][0]["s3_delete_contract"]["expected_outcome"], "fake_skipped")
        self.assertFalse(preview_payload["items"][0]["s3_delete_contract"]["safety"]["real_s3_delete_executed"])
        self.assertTrue(preview_payload["items"][0]["s3_delete_contract"]["safety"]["fake_s3_delete_executed"])
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["totals"]["skipped"], 1)
        self.assertEqual(payload["items"][0]["outcome"], "skipped_unsupported_storage")
        self.assertEqual(payload["items"][0]["s3_delete_contract"]["contract_version"], "s3-delete-fake-v1")
        self.assertEqual(payload["items"][0]["s3_delete_contract"]["bucket"], "test-bucket")
        self.assertEqual(
            payload["items"][0]["s3_delete_contract"]["object_key"],
            "document-jobs/tenant_default/docjob_retention/generated_word/s3.docx",
        )
        self.assertEqual(payload["items"][0]["s3_delete_contract"]["version_id"], "version-delete-001")
        self.assertTrue(payload["items"][0]["s3_delete_contract"]["target_exact"])
        self.assertEqual(payload["items"][0]["s3_delete_contract"]["missing_target_fields"], [])
        self.assertFalse(payload["items"][0]["metadata_updated"])
        self.assertIsNotNone(file_after_delete)
        self.assertEqual(file_after_delete.status, "expired")

    def test_file_retention_s3_fake_delete_preview_matches_ops_s3_adapter_contract(self):
        """验证 retention S3 fake preview 与 Ops S3 adapter contract 版本和安全语义一致。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            now = utc_now()
            s3_file = DocumentFileRecord(
                id="file_retention_delete_s3_parity",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_retention",
                file_type="generated_word",
                storage_provider="s3",
                bucket="test-bucket",
                object_key="document-jobs/tenant_default/docjob_retention/generated_word/parity.docx",
                original_filename="parity.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=10,
                status="expired",
                expires_at=now - timedelta(seconds=1),
                metadata={"s3_version_id": "version-parity-001"},
                created_by="user_operator",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=2),
            )
            runtime.document_file_repository.create_document_file(s3_file)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                audit_actions_before = [event.action for event in runtime.audit_event_repository.list_audit_events()]
                contract_response = client.get("/api/v1/ops/s3-deletions/adapter-contract", headers=admin_headers)
                preview_response = client.post(
                    "/api/v1/files/retention/delete-preview",
                    headers=admin_headers,
                    json={"file_ids": [s3_file.id]},
                )
                audit_actions_after = [event.action for event in runtime.audit_event_repository.list_audit_events()]

            file_after_preview = runtime.document_file_repository.get_document_file(s3_file.id)

        self.assertEqual(contract_response.status_code, 200)
        self.assertEqual(preview_response.status_code, 200)
        contract_payload = contract_response.json()
        preview_item = preview_response.json()["items"][0]
        fake_contract = preview_item["s3_delete_contract"]
        self.assertEqual(fake_contract["contract_version"], contract_payload["fake_file_retention_contract_version"])
        self.assertEqual(fake_contract["adapter_mode"], contract_payload["fake_adapter_mode"])
        self.assertEqual(fake_contract["bucket"], "test-bucket")
        self.assertEqual(fake_contract["object_key"], "document-jobs/tenant_default/docjob_retention/generated_word/parity.docx")
        self.assertEqual(fake_contract["version_id"], "version-parity-001")
        self.assertTrue(fake_contract["target_exact"])
        self.assertEqual(fake_contract["expected_outcome"], "fake_skipped")
        self.assertTrue(fake_contract["safety"]["fake_s3_delete_executed"])
        self.assertFalse(fake_contract["safety"]["real_s3_delete_executed"])
        self.assertFalse(fake_contract["safety"]["metadata_mutated"])
        self.assertFalse(fake_contract["safety"]["audit_events_written"])
        self.assertTrue(contract_payload["parity_checks"]["fake_uses_exact_bucket_key"])
        self.assertTrue(contract_payload["parity_checks"]["fake_preserves_version_id"])
        self.assertTrue(contract_payload["parity_checks"]["fake_never_calls_s3"])
        self.assertFalse(contract_payload["safety"]["real_s3_delete_executed"])
        self.assertFalse(contract_payload["safety"]["metadata_mutated"])
        self.assertEqual(audit_actions_after, audit_actions_before)
        self.assertIsNotNone(file_after_preview)
        self.assertEqual(file_after_preview.status, "expired")

    def test_file_retention_physical_delete_skips_uploaded_without_deleting(self):
        """验证 uploaded 过期候选必须先 mark-expired，不能直接物理删除。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            uploaded_file = self._seed_expired_document_file(runtime, file_id="file_retention_delete_uploaded")
            uploaded_path = runtime.file_upload_service.resolve_local_object_path(uploaded_file.object_key)
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                response = client.post(
                    "/api/v1/files/retention/delete-expired",
                    headers=admin_headers,
                    json={
                        "file_ids": [uploaded_file.id],
                        "reason": "manual cleanup",
                        "confirmation": "DELETE EXPIRED FILES",
                    },
                )

            file_after_delete = runtime.document_file_repository.get_document_file(uploaded_file.id)
            object_still_exists = uploaded_path.exists()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["totals"]["skipped"], 1)
        self.assertEqual(payload["items"][0]["outcome"], "skipped_not_expired_status")
        self.assertTrue(object_still_exists)
        self.assertIsNotNone(file_after_delete)
        self.assertEqual(file_after_delete.status, "uploaded")

    def test_file_authorized_content_upload_validates_pdf_and_writes_object(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            pdf_content = make_pdf_bytes(page_count=2)
            checksum = f"sha256:{hashlib.sha256(pdf_content).hexdigest()}"

            with TestClient(app) as client:
                headers = build_auth_header(client)
                authorize_response = client.post(
                    "/api/v1/files/upload-url",
                    headers=headers,
                    json={
                        "filename": "source.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(pdf_content),
                        "checksum_sha256": checksum,
                    },
                )
                upload_path = authorize_response.json()["upload_url"].replace("http://testserver", "")
                upload_response = client.put(
                    upload_path,
                    headers={**headers, "Content-Type": "application/pdf"},
                    content=pdf_content,
                )

            payload = upload_response.json()["file"]
            record = runtime.document_file_repository.get_document_file(payload["id"])
            object_path = runtime.file_upload_service.resolve_local_object_path(payload["object_key"])
            object_bytes = object_path.read_bytes()

        self.assertEqual(authorize_response.status_code, 201)
        self.assertEqual(upload_response.status_code, 201)
        self.assertEqual(payload["status"], "uploaded")
        self.assertEqual(payload["checksum_sha256"], checksum)
        self.assertEqual(payload["metadata"]["page_count"], 2)
        self.assertEqual(record.status, "uploaded")
        self.assertEqual(object_bytes, pdf_content)

    def test_file_upload_url_uses_forwarded_https_scheme(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            pdf_content = make_pdf_bytes(page_count=1)

            with TestClient(app) as client:
                headers = {**build_auth_header(client), "X-Forwarded-Proto": "https"}
                response = client.post(
                    "/api/v1/files/upload-url",
                    headers=headers,
                    json={
                        "filename": "source.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(pdf_content),
                    },
                )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["upload_url"].startswith("https://testserver/"))

    def test_file_upload_rejects_missing_token_bad_type_oversize_and_too_many_pages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                jobs_upload_max_bytes=300,
                pdf_upload_max_pages=2,
            )
            app = create_app(runtime)
            valid_pdf = make_pdf_bytes(page_count=1)
            too_many_pages_pdf = make_pdf_bytes(page_count=3)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                missing_token = client.post(
                    "/api/v1/files/upload-url",
                    json={
                        "filename": "source.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(valid_pdf),
                    },
                )
                bad_type = client.post(
                    "/api/v1/files/upload-url",
                    headers=headers,
                    json={
                        "filename": "source.txt",
                        "mime_type": "text/plain",
                        "size_bytes": len(valid_pdf),
                    },
                )
                oversize = client.post(
                    "/api/v1/files/upload-url",
                    headers=headers,
                    json={
                        "filename": "source.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": 301,
                    },
                )
                authorize_response = client.post(
                    "/api/v1/files/upload-url",
                    headers=headers,
                    json={
                        "filename": "source.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(too_many_pages_pdf),
                    },
                )
                upload_path = authorize_response.json()["upload_url"].replace("http://testserver", "")
                too_many_pages = client.put(
                    upload_path,
                    headers={**headers, "Content-Type": "application/pdf"},
                    content=too_many_pages_pdf,
                )

        self.assertEqual(missing_token.status_code, 401)
        self.assertEqual(missing_token.json()["error_code"], "unauthorized")
        self.assertEqual(bad_type.status_code, 400)
        self.assertEqual(bad_type.json()["error_code"], "invalid_request")
        self.assertEqual(oversize.status_code, 413)
        self.assertEqual(oversize.json()["error_code"], "file_too_large")
        self.assertEqual(authorize_response.status_code, 201)
        self.assertEqual(too_many_pages.status_code, 400)
        self.assertEqual(too_many_pages.json()["error_code"], "invalid_request")
        self.assertIn("页数", too_many_pages.json()["detail"])

    def test_document_job_create_detail_list_and_events_for_operator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers={**headers, "X-Trace-Id": "trace_docjob_create"},
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "direct_pdf_to_word",
                    },
                )
                job_id = create_response.json()["job_id"]
                detail_response = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers)
                list_response = client.get("/api/v1/document-jobs", headers=headers)
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers)

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            stored_file = runtime.document_file_repository.get_document_file(source_file["id"])

        self.assertEqual(create_response.status_code, 201)
        create_payload = create_response.json()
        self.assertTrue(job_id.startswith("docjob_"))
        self.assertEqual(create_payload["status"], "pending")
        self.assertEqual(create_payload["stage"], "uploaded")
        self.assertEqual(create_payload["progress"], 0)
        self.assertEqual(create_payload["job"]["created_by"], "user_operator")
        self.assertEqual(create_payload["job"]["source_file_id"], source_file["id"])
        self.assertEqual(create_payload["job"]["request_snapshot"]["source_file"]["id"], source_file["id"])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["id"], job_id)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 1)
        self.assertEqual(list_response.json()["summary"], {"pending": 1})
        self.assertEqual(events_response.status_code, 200)
        events = events_response.json()["items"]
        self.assertEqual([event["event_type"] for event in events], ["job_created"])
        self.assertEqual(events[0]["stage"], "uploaded")
        self.assertEqual(events[0]["trace_id"], "trace_docjob_create")
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.status, "pending")
        self.assertEqual(stored_file.job_id, job_id)

    def test_document_job_create_rejects_unready_required_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                app_env="production",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="disabled",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="blocked-source.pdf")
                response = client.post(
                    "/api/v1/document-jobs",
                    headers={**headers, "X-Trace-Id": "trace_docjob_not_ready"},
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "direct_pdf_to_word",
                    },
                )

            stored_file = runtime.document_file_repository.get_document_file(source_file["id"])
            stored_jobs = runtime.document_job_repository.list_document_jobs()

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["error_code"], "document_jobs_not_ready")
        self.assertEqual(payload["error"]["code"], "document_jobs_not_ready")
        self.assertIn("document_jobs_worker_backend_disabled", payload["detail"])
        self.assertEqual(stored_jobs, [])
        self.assertIsNotNone(stored_file)
        self.assertIsNone(stored_file.job_id)

    def test_document_job_config_summary_lists_options_for_operator_and_admin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                admin_token="secret-admin",
            )
            publish_default_job_resources(runtime, include_translation=True)
            publish_translation_profile_resource_version(
                runtime,
                version="1",
                model="snapshot-model-ru",
                make_default=True,
                translation_profile_id="electronics-ru2zh",
                language_pair="ru2zh",
            )
            ru_translation_term_version = publish_translation_term_set_version(
                runtime,
                source_term="Постоянное обратное напряжение диода",
                target_term="反向直流电压",
                make_default=True,
                set_id=derive_translation_term_set_id("ru2zh"),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_response = client.get("/api/v1/document-jobs/config-summary", headers=operator_headers)
                admin_response = client.get("/api/v1/document-jobs/config-summary", headers=admin_headers)
                admin_token_response = client.get(
                    "/api/v1/document-jobs/config-summary",
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(operator_response.status_code, 200)
        operator_payload = operator_response.json()
        self.assertEqual(operator_payload["role"], "operator")
        self.assertEqual(operator_payload["resource_mode"], "versioned")
        self.assertEqual(operator_payload["defaults"]["template"]["label"], "default@1")
        self.assertEqual(operator_payload["defaults"]["term_rule_set"]["label"], "electronics-default@1")
        self.assertEqual(operator_payload["defaults"]["translation_term_set"]["label"], "translation-terms-en2zh@v1")
        self.assertEqual(operator_payload["defaults"]["translation_profile"]["label"], "electronics-en2zh@1")
        self.assertEqual(
            operator_payload["translation_defaults"]["en2zh"]["translation_term_set"]["label"],
            "translation-terms-en2zh@v1",
        )
        self.assertEqual(
            operator_payload["translation_defaults"]["ru2zh"]["translation_term_set"]["label"],
            f"translation-terms-ru2zh@{ru_translation_term_version}",
        )
        self.assertEqual(
            operator_payload["translation_defaults"]["ru2zh"]["translation_profile"]["label"],
            "electronics-ru2zh@1",
        )
        self.assertIn("default@1", [item["label"] for item in operator_payload["options"]["templates"]])
        self.assertIn("electronics-default@1", [item["label"] for item in operator_payload["options"]["term_rule_sets"]])
        self.assertIn(
            "translation-terms-en2zh@v1",
            [item["label"] for item in operator_payload["options"]["translation_term_sets"]],
        )
        self.assertIn(
            f"translation-terms-ru2zh@{ru_translation_term_version}",
            [item["label"] for item in operator_payload["options"]["translation_term_sets"]],
        )
        self.assertIn("electronics-en2zh@1", [item["label"] for item in operator_payload["options"]["translation_profiles"]])
        self.assertIn("electronics-ru2zh@1", [item["label"] for item in operator_payload["options"]["translation_profiles"]])
        self.assertTrue(operator_payload["readiness"]["en2zh_available"])
        self.assertTrue(operator_payload["readiness"]["ru2zh_available"])
        self.assertTrue(operator_payload["readiness"]["translation_modes"]["ru2zh"])
        self.assertFalse(operator_payload["readiness"]["p0_document_jobs_required"])
        self.assertTrue(operator_payload["readiness"]["p0_document_jobs_ready"])
        self.assertEqual(operator_payload["readiness"]["document_jobs_worker_backend"], "disabled")
        self.assertFalse(operator_payload["readiness"]["document_jobs_automatic_execution_enabled"])
        self.assertEqual(operator_payload["readiness"]["blockers"], [])
        self.assertIn("document_jobs_worker_backend_disabled", operator_payload["readiness"]["warnings"])
        self.assertEqual(admin_response.status_code, 200)
        admin_payload = admin_response.json()
        self.assertEqual(admin_payload["role"], "admin")
        self.assertIn("default@1", [item["label"] for item in admin_payload["options"]["templates"]])
        self.assertIn("electronics-default@1", [item["label"] for item in admin_payload["options"]["term_rule_sets"]])
        self.assertIn(
            "translation-terms-en2zh@v1",
            [item["label"] for item in admin_payload["options"]["translation_term_sets"]],
        )
        self.assertIn(
            f"translation-terms-ru2zh@{ru_translation_term_version}",
            [item["label"] for item in admin_payload["options"]["translation_term_sets"]],
        )
        self.assertIn("electronics-en2zh@1", [item["label"] for item in admin_payload["options"]["translation_profiles"]])
        self.assertIn("electronics-ru2zh@1", [item["label"] for item in admin_payload["options"]["translation_profiles"]])
        self.assertEqual(admin_token_response.status_code, 200)
        admin_token_payload = admin_token_response.json()
        self.assertEqual(admin_token_payload["role"], "admin")
        self.assertTrue(admin_token_payload["readiness"]["en2zh_available"])

    def test_document_job_operator_can_bind_explicit_create_resource_versions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            publish_default_job_resources(runtime, include_translation=True)
            publish_template_resource_version(runtime, version="2", content=b"template-v2", make_default=False)
            publish_term_rule_resource_version(runtime, version="2", source_term="VTWO", make_default=False)
            publish_translation_profile_resource_version(
                runtime,
                version="2",
                model="snapshot-model-v2",
                make_default=False,
            )
            translation_term_version = publish_translation_term_set_version(
                runtime,
                source_term="FPGA",
                target_term="现场可编程门阵列",
                make_default=False,
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                        "template_version_id": "default@2",
                        "term_rule_set_version": "2",
                        "translation_term_version": translation_term_version,
                        "translation_profile_version": "2",
                    },
                )

        self.assertEqual(create_response.status_code, 201)
        snapshot = create_response.json()["job"]["request_snapshot"]["resources"]
        self.assertEqual(snapshot["template"]["resource_id"], "default")
        self.assertEqual(snapshot["template"]["version"], "2")
        self.assertEqual(snapshot["term_rule_set"]["resource_id"], "electronics-default")
        self.assertEqual(snapshot["term_rule_set"]["version"], "2")
        self.assertEqual(snapshot["translation_term_set"]["set_id"], "translation-terms-en2zh")
        self.assertEqual(snapshot["translation_term_set"]["version"], translation_term_version)
        self.assertEqual(snapshot["translation_profile"]["resource_id"], "electronics-en2zh")
        self.assertEqual(snapshot["translation_profile"]["version"], "2")

    def test_document_job_admin_can_bind_explicit_create_resource_versions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            publish_default_job_resources(runtime, include_translation=True)
            publish_template_resource_version(runtime, version="2", content=b"template-v2", make_default=False)
            publish_term_rule_resource_version(runtime, version="2", source_term="VTWO", make_default=False)
            publish_translation_profile_resource_version(
                runtime,
                version="2",
                model="snapshot-model-v2",
                make_default=False,
            )
            translation_term_version = publish_translation_term_set_version(
                runtime,
                source_term="FPGA",
                target_term="现场可编程门阵列",
                make_default=False,
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                source_file = self._upload_source_pdf(client, admin_headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=admin_headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                        "template_version_id": "default@2",
                        "term_rule_set_version": "2",
                        "translation_term_version": translation_term_version,
                        "translation_profile_version": "2",
                    },
                )

        self.assertEqual(create_response.status_code, 201)
        snapshot = create_response.json()["job"]["request_snapshot"]["resources"]
        self.assertEqual(snapshot["template"]["resource_id"], "default")
        self.assertEqual(snapshot["template"]["version"], "2")
        self.assertEqual(snapshot["term_rule_set"]["resource_id"], "electronics-default")
        self.assertEqual(snapshot["term_rule_set"]["version"], "2")
        self.assertEqual(snapshot["translation_term_set"]["set_id"], "translation-terms-en2zh")
        self.assertEqual(snapshot["translation_term_set"]["version"], translation_term_version)
        self.assertEqual(snapshot["translation_profile"]["resource_id"], "electronics-en2zh")
        self.assertEqual(snapshot["translation_profile"]["version"], "2")

    def test_only_admin_can_create_validation_job_with_draft_template_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            publish_default_job_resources(runtime, include_translation=False)
            service = runtime.resource_version_service
            self.assertIsNotNone(service)
            assert service is not None
            template_path = runtime.settings.default_template_path
            layout_path = runtime.settings.layout_config_path
            self.assertIsNotNone(template_path)
            self.assertIsNotNone(layout_path)
            assert template_path is not None and layout_path is not None
            payload = {
                "template_id": "default",
                "version": "2",
                "name": "Draft Template 2",
                "description": "admin validation draft",
                "docx_path": str(template_path.resolve()),
                "docx_sha256": f"sha256:{hashlib.sha256(template_path.read_bytes()).hexdigest()}",
                "layout_config_path": str(layout_path.resolve()),
                "layout_config_sha256": f"sha256:{hashlib.sha256(layout_path.read_bytes()).hexdigest()}",
                "render_policy": {},
            }
            service.create_or_update_draft(
                resource_type="template",
                resource_id="default",
                version="2",
                snapshot_hash=resource_payload_hash(payload),
                payload_ref="template:default@2",
                payload=payload,
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                operator_source = self._upload_source_pdf(client, operator_headers)
                operator_response = client.post(
                    "/api/v1/document-jobs",
                    headers=operator_headers,
                    json={
                        "source_file_id": operator_source["id"],
                        "mode": "direct_pdf_to_word",
                        "document_language": "en",
                        "template_version_id": "default@2",
                    },
                )
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                admin_source = self._upload_source_pdf(client, admin_headers)
                admin_response = client.post(
                    "/api/v1/document-jobs",
                    headers=admin_headers,
                    json={
                        "source_file_id": admin_source["id"],
                        "mode": "direct_pdf_to_word",
                        "document_language": "en",
                        "template_version_id": "default@2",
                    },
                )

        self.assertEqual(operator_response.status_code, 400)
        self.assertIn("draft", operator_response.json()["detail"])
        self.assertEqual(admin_response.status_code, 201)
        self.assertEqual(admin_response.json()["job"]["template_version_id"], "default@2")
        self.assertEqual(admin_response.json()["job"]["request_snapshot"]["resources"]["template"]["status"], "draft")

    def test_document_job_retry_resource_selection_requires_admin_and_rebinds_term_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            publish_default_job_resources(runtime, include_translation=True)
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_source = self._upload_source_pdf(client, operator_headers, filename="operator-retry.pdf")
                latest_source = self._upload_source_pdf(client, admin_headers, filename="latest-retry.pdf")
                explicit_source = self._upload_source_pdf(client, admin_headers, filename="explicit-retry.pdf")
                operator_job_id = client.post(
                    "/api/v1/document-jobs",
                    headers=operator_headers,
                    json={
                        "source_file_id": operator_source["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                ).json()["job_id"]
                latest_job_id = client.post(
                    "/api/v1/document-jobs",
                    headers=admin_headers,
                    json={
                        "source_file_id": latest_source["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                ).json()["job_id"]
                explicit_job_id = client.post(
                    "/api/v1/document-jobs",
                    headers=admin_headers,
                    json={
                        "source_file_id": explicit_source["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                ).json()["job_id"]
                for job_id in (operator_job_id, latest_job_id, explicit_job_id):
                    runtime.document_job_repository.update_document_job(
                        job_id,
                        status="failed",
                        stage="failed",
                        failed_stage="parsing",
                        error_code="mineru_failed",
                        error_message="retryable",
                    )
                publish_term_rule_resource_version(runtime, version="2", source_term="VTWO", make_default=True)
                latest_translation_term_version = publish_translation_term_set_version(
                    runtime,
                    source_term="FPGA",
                    target_term="现场可编程门阵列",
                    make_default=True,
                )
                operator_retry_response = client.post(
                    f"/api/v1/document-jobs/{operator_job_id}/retry",
                    headers=operator_headers,
                    json={"use_latest_term_assets": True},
                )
                latest_retry_response = client.post(
                    f"/api/v1/document-jobs/{latest_job_id}/retry",
                    headers=admin_headers,
                    json={"use_latest_term_assets": True},
                )
                explicit_retry_response = client.post(
                    f"/api/v1/document-jobs/{explicit_job_id}/retry",
                    headers=admin_headers,
                    json={
                        "term_rule_set_version": "1",
                        "translation_term_version": "v1",
                    },
                )

        self.assertEqual(operator_retry_response.status_code, 403)
        self.assertIn("operator 不能选择任务资源版本", operator_retry_response.json()["detail"])
        self.assertEqual(latest_retry_response.status_code, 200)
        latest_snapshot = latest_retry_response.json()["job"]["request_snapshot"]
        self.assertTrue(latest_snapshot["term_assets"]["use_latest_term_assets"])
        self.assertEqual(latest_snapshot["resources"]["template"]["version"], "1")
        self.assertEqual(latest_snapshot["resources"]["term_rule_set"]["version"], "2")
        self.assertEqual(latest_snapshot["resources"]["translation_term_set"]["version"], latest_translation_term_version)
        self.assertEqual(latest_snapshot["resources"]["translation_profile"]["version"], "1")
        self.assertEqual(explicit_retry_response.status_code, 200)
        explicit_snapshot = explicit_retry_response.json()["job"]["request_snapshot"]
        self.assertEqual(explicit_snapshot["term_assets"]["term_rule_set_version"], "1")
        self.assertEqual(explicit_snapshot["term_assets"]["translation_term_version"], "v1")
        self.assertEqual(explicit_snapshot["resources"]["template"]["version"], "1")
        self.assertEqual(explicit_snapshot["resources"]["term_rule_set"]["version"], "1")
        self.assertEqual(explicit_snapshot["resources"]["translation_term_set"]["version"], "v1")
        self.assertEqual(explicit_snapshot["resources"]["translation_profile"]["version"], "1")

    def test_document_job_list_supports_workbench_filters_without_running_worker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            now = utc_now()
            old_time = now - timedelta(days=2)
            middle_time = now - timedelta(days=1)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                alpha_source = self._upload_source_pdf(client, headers, filename="alpha-source.pdf")
                beta_source = self._upload_source_pdf(client, headers, filename="beta-source.pdf")
                queued_source = self._upload_source_pdf(client, headers, filename="queued-source.pdf")
                running_source = self._upload_source_pdf(client, headers, filename="running-source.pdf")
                archived_source = self._upload_source_pdf(client, headers, filename="archived-source.pdf")
                alpha_job_id = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": alpha_source["id"]},
                ).json()["job_id"]
                beta_job_id = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": beta_source["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                ).json()["job_id"]
                queued_job_id = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": queued_source["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                ).json()["job_id"]
                running_job_id = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": running_source["id"],
                        "translation_mode": "ru2zh",
                        "document_language": "ru",
                    },
                ).json()["job_id"]
                archived_job_id = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": archived_source["id"]},
                ).json()["job_id"]
                runtime.document_job_repository.update_document_job(
                    alpha_job_id,
                    status="failed",
                    stage="failed",
                    failed_stage="parsing",
                    error_code="alpha_error",
                    error_message="Needs OCR",
                    created_at=old_time,
                    updated_at=old_time,
                )
                runtime.document_job_repository.update_document_job(
                    beta_job_id,
                    translation_qa_status="approved",
                    translation_qa_reviewed_by="user_operator",
                    translation_qa_reviewed_at=middle_time,
                    created_at=middle_time,
                    updated_at=middle_time,
                )
                runtime.document_job_repository.update_document_job(
                    queued_job_id,
                    status="queued",
                    stage="uploaded",
                    translation_qa_status="needs_fix",
                    translation_qa_issue_type="terminology",
                    translation_qa_note="Term mismatch",
                    created_at=middle_time + timedelta(hours=2),
                    updated_at=middle_time + timedelta(hours=2),
                )
                runtime.document_job_repository.update_document_job(
                    running_job_id,
                    status="running",
                    stage="parsing",
                    translation_qa_status="blocked",
                    translation_qa_issue_type="artifact_missing",
                    translation_qa_note="Missing IR",
                    started_at=middle_time + timedelta(hours=4),
                    created_at=middle_time + timedelta(hours=4),
                    updated_at=middle_time + timedelta(hours=4),
                )
                runtime.document_job_repository.update_document_job(
                    archived_job_id,
                    status="failed",
                    stage="failed",
                    failed_stage="parsing",
                    error_code="archived_error",
                    error_message="Archived failure",
                    created_at=now,
                    updated_at=now,
                )
                archive_response = client.delete(f"/api/v1/document-jobs/{archived_job_id}", headers=headers)
                default_response = client.get("/api/v1/document-jobs", headers=headers)
                include_archived_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"include_archived": True, "sort": "created_at_asc"},
                )
                paginated_default_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"page_size": 1},
                )
                filename_search_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"q": "beta-source"},
                )
                error_search_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"q": "alpha_error"},
                )
                range_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={
                        "created_from": (middle_time - timedelta(hours=1)).isoformat(),
                        "created_to": (middle_time + timedelta(hours=1)).isoformat(),
                    },
                )
                active_group_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"status_group": "active", "sort": "created_at_asc"},
                )
                qa_status_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"translation_qa_status": "approved"},
                )
                qa_all_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"translation_qa_status": "all"},
                )
                qa_unreviewed_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"translation_qa_status": "unreviewed"},
                )
                status_group_conflict_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"status": "pending", "status_group": "active"},
                )
                invalid_status_group_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"status_group": "stuck"},
                )
                invalid_sort_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"sort": "status_desc"},
                )
                invalid_qa_status_response = client.get(
                    "/api/v1/document-jobs",
                    headers=headers,
                    params={"translation_qa_status": "ready"},
                )

        self.assertEqual(archive_response.status_code, 200)
        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(default_response.json()["total"], 4)
        expected_default_summary = {"failed": 1, "pending": 1, "queued": 1, "running": 1}
        expected_qa_summary = {"unreviewed": 0, "approved": 1, "needs_fix": 1, "blocked": 1}
        self.assertEqual(default_response.json()["summary"], expected_default_summary)
        self.assertEqual(default_response.json()["filtered_summary"], expected_default_summary)
        self.assertEqual(
            default_response.json()["translation_qa_summary"],
            expected_qa_summary,
        )
        self.assertEqual(include_archived_response.status_code, 200)
        include_archived_payload = include_archived_response.json()
        self.assertEqual(include_archived_payload["total"], 5)
        expected_include_archived_summary = {"failed": 2, "pending": 1, "queued": 1, "running": 1}
        self.assertEqual(include_archived_payload["summary"], expected_include_archived_summary)
        self.assertEqual(include_archived_payload["filtered_summary"], expected_include_archived_summary)
        self.assertEqual(
            [item["id"] for item in include_archived_payload["items"]],
            [alpha_job_id, beta_job_id, queued_job_id, running_job_id, archived_job_id],
        )
        self.assertEqual(paginated_default_response.status_code, 200)
        self.assertEqual(len(paginated_default_response.json()["items"]), 1)
        self.assertEqual(paginated_default_response.json()["total"], 4)
        self.assertEqual(paginated_default_response.json()["filtered_summary"], expected_default_summary)
        self.assertEqual(paginated_default_response.json()["translation_qa_summary"], expected_qa_summary)
        self.assertEqual(filename_search_response.status_code, 200)
        self.assertEqual([item["id"] for item in filename_search_response.json()["items"]], [beta_job_id])
        self.assertEqual(error_search_response.status_code, 200)
        self.assertEqual([item["id"] for item in error_search_response.json()["items"]], [alpha_job_id])
        self.assertEqual(range_response.status_code, 200)
        self.assertEqual([item["id"] for item in range_response.json()["items"]], [beta_job_id])
        self.assertEqual(range_response.json()["filtered_summary"], {"pending": 1})
        self.assertEqual(active_group_response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in active_group_response.json()["items"]],
            [beta_job_id, queued_job_id, running_job_id],
        )
        self.assertEqual(active_group_response.json()["filtered_summary"], {"pending": 1, "queued": 1, "running": 1})
        self.assertEqual(active_group_response.json()["translation_qa_summary"], expected_qa_summary)
        self.assertEqual(qa_status_response.status_code, 200)
        self.assertEqual([item["id"] for item in qa_status_response.json()["items"]], [beta_job_id])
        self.assertEqual(qa_status_response.json()["filtered_summary"], {"pending": 1})
        self.assertEqual(
            qa_status_response.json()["translation_qa_summary"],
            expected_qa_summary,
        )
        self.assertEqual(qa_all_response.status_code, 200)
        self.assertEqual([item["id"] for item in qa_all_response.json()["items"]], [running_job_id, queued_job_id, beta_job_id])
        self.assertEqual(qa_all_response.json()["items"][0]["translation_mode"], "ru2zh")
        self.assertEqual(qa_all_response.json()["total"], 3)
        self.assertEqual(qa_all_response.json()["filtered_summary"], {"pending": 1, "queued": 1, "running": 1})
        self.assertEqual(qa_all_response.json()["translation_qa_summary"], expected_qa_summary)
        self.assertEqual(qa_unreviewed_response.status_code, 200)
        self.assertEqual(qa_unreviewed_response.json()["items"], [])
        self.assertEqual(qa_unreviewed_response.json()["filtered_summary"], {})
        self.assertEqual(qa_unreviewed_response.json()["translation_qa_summary"], expected_qa_summary)
        self.assertEqual(status_group_conflict_response.status_code, 400)
        self.assertEqual(status_group_conflict_response.json()["error_code"], "invalid_request")
        self.assertIn("status_group", status_group_conflict_response.json()["detail"])
        self.assertEqual(invalid_status_group_response.status_code, 400)
        self.assertEqual(invalid_status_group_response.json()["error_code"], "invalid_request")
        self.assertIn("status_group", invalid_status_group_response.json()["detail"])
        self.assertEqual(invalid_sort_response.status_code, 400)
        self.assertEqual(invalid_sort_response.json()["error_code"], "invalid_request")
        self.assertIn("sort", invalid_sort_response.json()["detail"])
        self.assertEqual(invalid_qa_status_response.status_code, 400)
        self.assertEqual(invalid_qa_status_response.json()["error_code"], "invalid_request")
        self.assertIn("translation_qa_status", invalid_qa_status_response.json()["detail"])

    def test_document_job_response_includes_server_action_availability(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="actions-source.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                list_response = client.get("/api/v1/document-jobs", headers=headers)
                runtime.document_job_repository.update_document_job(
                    job_id,
                    status="failed",
                    stage="failed",
                    failed_stage="parsing",
                    error_code="document_job_invalid_input",
                    error_message="bad input",
                )
                failed_detail_response = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers)
                archive_response = client.delete(f"/api/v1/document-jobs/{job_id}", headers=headers)
                archived_detail_response = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers)

        self.assertEqual(create_response.status_code, 201)
        pending_actions = list_response.json()["items"][0]["available_actions"]
        self.assertEqual(set(pending_actions), {"download", "retry", "cancel", "archive", "unarchive", "clone", "delete"})
        self.assertTrue(pending_actions["cancel"]["enabled"])
        self.assertTrue(pending_actions["clone"]["enabled"])
        self.assertFalse(pending_actions["delete"]["enabled"])
        self.assertIn("admin", pending_actions["delete"]["disabled_reason"])
        self.assertFalse(pending_actions["retry"]["retryable"])
        self.assertFalse(pending_actions["download"]["enabled"])
        self.assertIn("succeeded", pending_actions["download"]["disabled_reason"])
        failed_actions = failed_detail_response.json()["available_actions"]
        self.assertTrue(failed_actions["archive"]["enabled"])
        self.assertFalse(failed_actions["retry"]["enabled"])
        self.assertFalse(failed_actions["retry"]["retryable"])
        self.assertIn("不可重试", failed_actions["retry"]["disabled_reason"])
        self.assertEqual(archive_response.status_code, 200)
        archived_actions = archived_detail_response.json()["available_actions"]
        self.assertTrue(archived_actions["unarchive"]["enabled"])
        self.assertFalse(archived_actions["archive"]["enabled"])
        self.assertFalse(archived_actions["retry"]["enabled"])
        self.assertIn("已归档", archived_actions["retry"]["disabled_reason"])

    def test_document_job_incident_queue_filters_priority_and_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            now = utc_now()

            with TestClient(app) as client:
                headers = build_auth_header(client)
                retryable_job_id = self._create_document_job_from_upload(client, headers, filename="retryable-incident.pdf")
                non_retryable_job_id = self._create_document_job_from_upload(client, headers, filename="bad-input-incident.pdf")
                blocked_job_id = self._create_document_job_from_upload(client, headers, filename="blocked-qa-incident.pdf")
                stalled_job_id = self._create_document_job_from_upload(client, headers, filename="stalled-incident.pdf")
                runtime.document_job_repository.update_document_job(
                    retryable_job_id,
                    status="failed",
                    stage="failed",
                    failed_stage="parsing",
                    error_code="mineru_failed",
                    error_message="MinerU failed",
                    retry_count=1,
                    updated_at=now - timedelta(minutes=8),
                )
                runtime.document_job_repository.update_document_job(
                    non_retryable_job_id,
                    status="failed",
                    stage="failed",
                    failed_stage="parsing",
                    error_code="document_job_invalid_input",
                    error_message="bad input",
                    updated_at=now - timedelta(minutes=6),
                )
                runtime.document_job_repository.update_document_job(
                    blocked_job_id,
                    mode="en2zh_pdf_to_word",
                    status="running",
                    stage="parsing",
                    translation_qa_status="blocked",
                    translation_qa_issue_type="artifact_missing",
                    translation_qa_note="DocumentIR missing",
                    updated_at=now - timedelta(minutes=1),
                )
                runtime.document_job_repository.update_document_job(
                    stalled_job_id,
                    status="queued",
                    stage="uploaded",
                    updated_at=now - timedelta(minutes=25),
                    timeout_at=now + timedelta(minutes=5),
                )
                list_response = client.get("/api/v1/document-job-incidents", headers=headers)
                retryable_response = client.get(
                    "/api/v1/document-job-incidents",
                    headers=headers,
                    params={"retryable": True},
                )
                artifact_response = client.get(
                    "/api/v1/document-job-incidents",
                    headers=headers,
                    params={"failure_type": "artifact_missing"},
                )
                stage_response = client.get(
                    "/api/v1/document-job-incidents",
                    headers=headers,
                    params={"stage": "parsing", "sort": "updated_at_desc"},
                )
                stalled_response = client.get(
                    "/api/v1/document-job-incidents",
                    headers=headers,
                    params={"stalled_minutes": 20},
                )
                diagnostics_response = client.get(
                    f"/api/v1/document-job-incidents/{retryable_job_id}/diagnostics",
                    headers=headers,
                )
                invalid_response = client.get(
                    "/api/v1/document-job-incidents",
                    headers=headers,
                    params={"failure_type": "not_real"},
                )

        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertEqual(payload["total"], 4)
        self.assertEqual(
            [item["job"]["id"] for item in payload["items"]],
            [blocked_job_id, stalled_job_id, retryable_job_id, non_retryable_job_id],
        )
        self.assertEqual(payload["summary"]["failed"], 2)
        self.assertEqual(payload["summary"]["blocked"], 1)
        self.assertEqual(payload["summary"]["stalled"], 1)
        self.assertEqual(payload["summary"]["retryable"], 1)
        self.assertEqual(payload["summary"]["non_retryable"], 1)
        self.assertEqual(payload["summary"]["by_failure_type"]["artifact_missing"], 1)
        self.assertEqual(payload["summary"]["by_failure_type"]["timeout_or_stalled"], 1)
        self.assertEqual(retryable_response.status_code, 200)
        self.assertEqual([item["job"]["id"] for item in retryable_response.json()["items"]], [retryable_job_id])
        self.assertEqual(artifact_response.status_code, 200)
        self.assertEqual([item["job"]["id"] for item in artifact_response.json()["items"]], [blocked_job_id])
        self.assertEqual(stage_response.status_code, 200)
        self.assertEqual([item["job"]["id"] for item in stage_response.json()["items"]], [blocked_job_id, non_retryable_job_id, retryable_job_id])
        self.assertEqual(stalled_response.status_code, 200)
        self.assertEqual([item["job"]["id"] for item in stalled_response.json()["items"]], [stalled_job_id])
        self.assertEqual(diagnostics_response.status_code, 200)
        diagnostics_payload = diagnostics_response.json()
        self.assertTrue(diagnostics_payload["item"]["retryable"])
        self.assertEqual(diagnostics_payload["item"]["failure_type"], "conversion_failed")
        self.assertIn("MinerU failed", diagnostics_payload["item"]["evidence_summary"])
        self.assertTrue(any(link["kind"] == "detail" for link in diagnostics_payload["evidence_links"]))
        self.assertTrue(diagnostics_payload["recent_events"])
        self.assertTrue(diagnostics_payload["files"])
        self.assertNotIn("object_key", diagnostics_payload["files"][0])
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.json()["error_code"], "invalid_request")

    def test_document_job_incident_bulk_retry_skips_non_retryable_and_refreshes_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                retryable_job_id = self._create_document_job_from_upload(client, headers, filename="incident-bulk-retry.pdf")
                non_retryable_job_id = self._create_document_job_from_upload(client, headers, filename="incident-bulk-invalid.pdf")
                active_job_id = self._create_document_job_from_upload(client, headers, filename="incident-bulk-active.pdf")
                runtime.document_job_repository.update_document_job(
                    retryable_job_id,
                    status="failed",
                    stage="failed",
                    failed_stage="rendering",
                    error_code="render_failed",
                    error_message="render failed",
                )
                runtime.document_job_repository.update_document_job(
                    non_retryable_job_id,
                    status="failed",
                    stage="failed",
                    failed_stage="parsing",
                    error_code="document_job_invalid_input",
                    error_message="bad input",
                )
                runtime.document_job_repository.update_document_job(
                    active_job_id,
                    status="running",
                    stage="parsing",
                )
                retry_response = client.post(
                    "/api/v1/document-job-incidents/bulk-retry",
                    headers={**headers, "X-Trace-Id": "trace_incident_bulk_retry"},
                    json={
                        "job_ids": [retryable_job_id, non_retryable_job_id, active_job_id],
                        "reason": "incident bulk retry",
                    },
                )
                refresh_response = client.post(
                    "/api/v1/document-job-incidents/bulk-refresh",
                    headers=headers,
                    json={"job_ids": [retryable_job_id, non_retryable_job_id, active_job_id]},
                )

            retried_job = runtime.document_job_repository.get_document_job(retryable_job_id)
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(retry_response.status_code, 200)
        retry_payload = retry_response.json()
        self.assertEqual(retry_payload["action"], "retry")
        self.assertEqual(retry_payload["succeeded"], 1)
        self.assertEqual(retry_payload["skipped"], 2)
        self.assertEqual(retry_payload["failed"], 0)
        self.assertEqual(retried_job.status, "pending")
        skipped_details = {item["job_id"]: item["detail"] for item in retry_payload["items"] if item["skipped"]}
        self.assertIn("不可重试", skipped_details[non_retryable_job_id])
        self.assertIn("failed", skipped_details[active_job_id])
        retry_audit_events = [event for event in audit_events if event.action == "document_job.retry"]
        self.assertEqual(len(retry_audit_events), 1)
        self.assertEqual(retry_audit_events[0].target_id, retryable_job_id)
        self.assertEqual(refresh_response.status_code, 200)
        refresh_payload = refresh_response.json()
        self.assertEqual(refresh_payload["action"], "refresh")
        self.assertEqual(refresh_payload["succeeded"], 3)
        self.assertEqual(refresh_payload["failed"], 0)
        self.assertEqual(refresh_payload["skipped"], 0)
        self.assertEqual({item["job_id"] for item in refresh_payload["items"]}, {retryable_job_id, non_retryable_job_id, active_job_id})

    def test_document_job_unarchive_restores_default_list_and_writes_audit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="unarchive-source.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                archive_response = client.delete(f"/api/v1/document-jobs/{job_id}", headers=headers)
                hidden_list_response = client.get("/api/v1/document-jobs", headers=headers)
                unarchive_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/unarchive",
                    headers={**headers, "X-Trace-Id": "trace_docjob_unarchive"},
                )
                restored_list_response = client.get("/api/v1/document-jobs", headers=headers)
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers)

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(archive_response.status_code, 200)
        self.assertEqual(hidden_list_response.json()["total"], 0)
        self.assertEqual(unarchive_response.status_code, 200)
        payload = unarchive_response.json()
        self.assertEqual(payload["job_id"], job_id)
        self.assertIsNotNone(payload["restored_at"])
        self.assertIsNone(payload["job"]["archived_at"])
        self.assertIsNone(payload["job"]["archived_by"])
        self.assertFalse(payload["job"]["available_actions"]["unarchive"]["enabled"])
        self.assertEqual(restored_list_response.json()["total"], 1)
        self.assertIsNotNone(stored_job)
        self.assertIsNone(stored_job.archived_at)
        self.assertIsNone(stored_job.archived_by)
        event_types = [event["event_type"] for event in events_response.json()["items"]]
        self.assertIn("job_unarchived", event_types)
        unarchive_audit_events = [event for event in audit_events if event.action == "document_job.unarchive"]
        self.assertEqual(len(unarchive_audit_events), 1)
        self.assertEqual(unarchive_audit_events[0].target_id, job_id)

    def test_document_job_clone_creates_new_job_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="clone-source.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                source_job_id = create_response.json()["job_id"]
                clone_response = client.post(
                    f"/api/v1/document-jobs/{source_job_id}/clone",
                    headers={**headers, "X-Trace-Id": "trace_docjob_clone"},
                    json={"reason": "rerun as new job"},
                )
                cloned_job_id = clone_response.json()["job_id"]
                cloned_files_response = client.get(f"/api/v1/document-jobs/{cloned_job_id}/files", headers=headers)
                source_detail_response = client.get(f"/api/v1/document-jobs/{source_job_id}", headers=headers)
                cloned_events_response = client.get(f"/api/v1/document-jobs/{cloned_job_id}/events", headers=headers)

            source_job = runtime.document_job_repository.get_document_job(source_job_id)
            cloned_job = runtime.document_job_repository.get_document_job(cloned_job_id)
            source_file_after = runtime.document_file_repository.get_document_file(source_file["id"])
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(clone_response.status_code, 201)
        clone_payload = clone_response.json()
        self.assertEqual(clone_payload["source_job_id"], source_job_id)
        self.assertNotEqual(clone_payload["job_id"], source_job_id)
        self.assertEqual(clone_payload["status"], "pending")
        self.assertEqual(clone_payload["job"]["source_job_id"], source_job_id)
        self.assertEqual(clone_payload["job"]["source_file_id"], source_file["id"])
        self.assertEqual(clone_payload["job"]["request_snapshot"]["clone"]["source_job_id"], source_job_id)
        self.assertEqual(clone_payload["job"]["request_snapshot"]["clone"]["config_strategy"], "keep_source_snapshot")
        self.assertIsNotNone(source_job)
        self.assertEqual(source_job.retry_count, 0)
        self.assertIsNone(source_job.source_job_id)
        self.assertIsNotNone(cloned_job)
        self.assertEqual(cloned_job.source_job_id, source_job_id)
        self.assertEqual(cloned_job.source_file_id, source_job.source_file_id)
        self.assertIsNotNone(source_file_after)
        self.assertEqual(source_file_after.job_id, source_job_id)
        self.assertEqual([file["id"] for file in cloned_files_response.json()["files"]], [source_file["id"]])
        self.assertIsNone(source_detail_response.json()["source_job_id"])
        self.assertIn("job_cloned", [event["event_type"] for event in cloned_events_response.json()["items"]])
        clone_audit_events = [event for event in audit_events if event.action == "document_job.clone"]
        self.assertEqual(len(clone_audit_events), 1)
        self.assertEqual(clone_audit_events[0].target_id, cloned_job_id)
        self.assertEqual(clone_audit_events[0].reason, "rerun as new job")
        self.assertEqual(clone_audit_events[0].details["source_job_id"], source_job_id)
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.calls, [])

    def test_document_job_clone_rejects_expired_source_and_reports_disabled_reason(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="clone-expired.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                runtime.document_file_repository.update_document_file(
                    source_file["id"],
                    expires_at=utc_now() - timedelta(seconds=1),
                )
                detail_response = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers)
                clone_response = client.post(f"/api/v1/document-jobs/{job_id}/clone", headers=headers, json={})

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(detail_response.status_code, 200)
        clone_action = detail_response.json()["available_actions"]["clone"]
        self.assertFalse(clone_action["enabled"])
        self.assertIn("过期", clone_action["disabled_reason"])
        self.assertEqual(clone_response.status_code, 409)
        self.assertEqual(clone_response.json()["error_code"], "conflict")
        self.assertIn("过期", clone_response.json()["detail"])

    def test_document_job_clone_explicit_resource_selection_requires_admin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="clone-operator-explicit.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                clone_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/clone",
                    headers=headers,
                    json={
                        "config_strategy": "select_published_versions",
                        "template_version_id": "default@1",
                    },
                )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(clone_response.status_code, 403)
        self.assertIn("operator 不能选择任务资源版本", clone_response.json()["detail"])

    def test_document_job_clone_rejects_operator_inheriting_debug_full_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                translation_debug_archive_enabled=True,
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, admin_headers, filename="clone-debug-source.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=admin_headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                        "debug_full_text": True,
                    },
                )
                job_id = create_response.json()["job_id"]
                runtime.document_job_repository.update_document_job(job_id, created_by="user_operator")
                clone_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/clone",
                    headers=operator_headers,
                    json={"config_strategy": "keep_source_snapshot"},
                )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(clone_response.status_code, 403)
        self.assertEqual(clone_response.json()["error_code"], "role_forbidden")

    def test_document_job_create_en2zh_binds_default_term_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )
                job_id = create_response.json()["job_id"]
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers)

            stored_job = runtime.document_job_repository.get_document_job(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["job"]["term_version_id"], "en2zh@v1")
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.term_version_id, "en2zh@v1")
        self.assertEqual(stored_job.request_snapshot["term_version_id"], "en2zh@v1")
        self.assertEqual(events_response.json()["items"][0]["payload"]["term_version_id"], "en2zh@v1")

    def test_document_job_create_ru2zh_uses_translation_mode_and_binds_default_terms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="ru-diode.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "translation_mode": "ru2zh",
                        "document_language": "auto",
                    },
                )
                job_id = create_response.json()["job_id"]
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers)

            stored_job = runtime.document_job_repository.get_document_job(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["job"]["mode"], "ru2zh_pdf_to_word")
        self.assertEqual(create_response.json()["job"]["translation_mode"], "ru2zh")
        self.assertEqual(create_response.json()["job"]["term_version_id"], "ru2zh@v1")
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.mode, "ru2zh_pdf_to_word")
        self.assertEqual(stored_job.term_version_id, "ru2zh@v1")
        self.assertEqual(stored_job.request_snapshot["translation_mode"], "ru2zh")
        self.assertEqual(events_response.json()["items"][0]["payload"]["translation_mode"], "ru2zh")

    def test_document_job_create_rejects_conflicting_mode_and_translation_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="conflict.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "translation_mode": "ru2zh",
                    },
                )

        self.assertEqual(create_response.status_code, 400)
        self.assertEqual(create_response.json()["error_code"], "invalid_request")
        self.assertIn("translation_mode 与 mode 不一致", create_response.json()["detail"])

    def test_document_job_create_ru2zh_binds_language_pair_resources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            publish_default_job_resources(runtime)
            publish_translation_profile_resource_version(
                runtime,
                version="1",
                model="snapshot-model-ru",
                make_default=True,
                translation_profile_id="electronics-ru2zh",
                language_pair="ru2zh",
            )
            ru_term_version = publish_translation_term_set_version(
                runtime,
                source_term="Постоянное обратное напряжение диода",
                target_term="反向直流电压",
                make_default=True,
                set_id=derive_translation_term_set_id("ru2zh"),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="ru-diode.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "translation_mode": "ru2zh",
                    },
                )

        self.assertEqual(create_response.status_code, 201)
        snapshot = create_response.json()["job"]["request_snapshot"]["resources"]
        self.assertEqual(snapshot["translation_profile"]["resource_id"], "electronics-ru2zh")
        self.assertEqual(snapshot["translation_profile"]["version"], "1")
        self.assertEqual(snapshot["translation_term_set"]["set_id"], "translation-terms-ru2zh")
        self.assertEqual(snapshot["translation_term_set"]["language_pair"], "ru2zh")
        self.assertEqual(snapshot["translation_term_set"]["version"], ru_term_version)
        self.assertEqual(snapshot["mineru"]["language"], "ru")

    def test_document_job_create_rejects_translation_profile_language_pair_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            publish_default_job_resources(runtime, include_translation=True)
            publish_translation_term_set_version(
                runtime,
                source_term="Постоянное обратное напряжение диода",
                target_term="反向直流电压",
                make_default=True,
                set_id=derive_translation_term_set_id("ru2zh"),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="ru-profile-mismatch.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "translation_mode": "ru2zh",
                        "translation_profile_id": "electronics-en2zh",
                        "translation_profile_version": "1",
                    },
                )

        self.assertEqual(create_response.status_code, 400)
        self.assertEqual(create_response.json()["error_code"], "translation_profile_language_pair_mismatch")
        self.assertIn("expected=ru2zh actual=en2zh", create_response.json()["detail"])

    def test_document_job_create_enqueues_eager_worker_and_updates_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers={**headers, "X-Trace-Id": "trace_docjob_worker"},
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                detail_response = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers)
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers)

            stored_job = runtime.document_job_repository.get_document_job(job_id)

        self.assertEqual(create_response.status_code, 201)
        create_payload = create_response.json()
        self.assertEqual(create_payload["status"], "succeeded")
        self.assertEqual(create_payload["stage"], "completed")
        self.assertEqual(create_payload["progress"], 100)
        self.assertEqual(detail_response.json()["status"], "succeeded")
        self.assertEqual(detail_response.json()["stage"], "completed")
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.status, "succeeded")
        self.assertEqual(stored_job.stage, "completed")
        self.assertIsNotNone(stored_job.started_at)
        self.assertIsNotNone(stored_job.mineru_raw_result_file_id)
        self.assertIsNotNone(stored_job.document_ir_file_id)
        self.assertIsNotNone(stored_job.result_file_id)
        self.assertEqual(len(stored_job.image_asset_file_ids), 1)
        events = events_response.json()["items"]
        self.assertIn(("file_registered", "parsing"), [(event["event_type"], event["stage"]) for event in events])
        self.assertIn(("file_registered", "ir_converting"), [(event["event_type"], event["stage"]) for event in events])
        self.assertIn(("file_registered", "uploading"), [(event["event_type"], event["stage"]) for event in events])
        self.assertEqual(events[-1]["stage"], "completed")
        self.assertEqual(events[-1]["event_type"], "stage_succeeded")
        self.assertEqual(events[-1]["payload"]["result_file_id"], stored_job.result_file_id)
        self.assertEqual({event["trace_id"] for event in events}, {"trace_docjob_worker"})

    def test_document_job_archive_hides_terminal_job_without_deleting_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="archive-source.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                archive_response = client.delete(
                    f"/api/v1/document-jobs/{job_id}",
                    headers={**headers, "X-Trace-Id": "trace_docjob_archive"},
                )
                list_response = client.get("/api/v1/document-jobs", headers=headers)
                detail_response = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers)
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers)
                download_url_response = client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=headers)

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            stored_source_file = runtime.document_file_repository.get_document_file(source_file["id"])
            stored_result_file = runtime.document_file_repository.get_document_file(stored_job.result_file_id)
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "succeeded")
        self.assertEqual(archive_response.status_code, 200)
        archive_payload = archive_response.json()
        self.assertEqual(archive_payload["job_id"], job_id)
        self.assertIsNotNone(archive_payload["archived_at"])
        self.assertEqual(archive_payload["job"]["archived_by"], "user_operator")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 0)
        self.assertEqual(list_response.json()["summary"], {})
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["id"], job_id)
        self.assertIsNotNone(detail_response.json()["archived_at"])
        self.assertEqual(download_url_response.status_code, 200)
        self.assertIsNotNone(stored_job)
        self.assertIsNotNone(stored_job.archived_at)
        self.assertEqual(stored_job.archived_by, "user_operator")
        self.assertIsNotNone(stored_source_file)
        self.assertIsNotNone(stored_result_file)
        event_types = [event["event_type"] for event in events_response.json()["items"]]
        self.assertIn("stage_succeeded", event_types)
        self.assertIn("job_archived", event_types)
        archive_audit_events = [event for event in audit_events if event.action == "document_job.archive"]
        self.assertEqual(len(archive_audit_events), 1)
        self.assertEqual(archive_audit_events[0].target_id, job_id)

    def test_document_job_delete_requires_admin_preview_and_removes_owned_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                source_file = self._upload_source_pdf(client, operator_headers, filename="delete-source.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=operator_headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                operator_preview_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/delete-preview",
                    headers=operator_headers,
                )
                operator_delete_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/delete",
                    headers=operator_headers,
                    json={
                        "reason": "operator should not delete",
                        "confirmation": f"DELETE {job_id}",
                        "preview_hash": "preview",
                    },
                )
                preview_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/delete-preview",
                    headers=admin_headers,
                )
                preview_payload = preview_response.json()
                delete_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/delete",
                    headers={**admin_headers, "X-Trace-Id": "trace_docjob_delete"},
                    json={"preview_hash": preview_payload["preview_hash"]},
                )
                list_response = client.get("/api/v1/document-jobs", headers=admin_headers)
                detail_response = client.get(f"/api/v1/document-jobs/{job_id}", headers=admin_headers)
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=admin_headers)
                download_url_response = client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=admin_headers)
                repeated_preview_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/delete-preview",
                    headers=admin_headers,
                )

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            stored_files = {
                item["file_id"]: runtime.document_file_repository.get_document_file(item["file_id"])
                for item in preview_payload["files"]
            }
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "succeeded")
        self.assertEqual(operator_preview_response.status_code, 403)
        self.assertEqual(operator_delete_response.status_code, 403)
        self.assertEqual(operator_delete_response.json()["error_code"], "role_forbidden")
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_payload["action_mode"], "delete_preview")
        self.assertEqual(preview_payload["confirmation_phrase"], f"DELETE {job_id}")
        self.assertEqual(preview_payload["totals"]["keep"], 0)
        self.assertGreater(preview_payload["totals"]["delete"], 0)
        self.assertEqual(delete_response.status_code, 200)
        delete_payload = delete_response.json()
        self.assertEqual(delete_payload["action_mode"], "delete_execute")
        self.assertEqual(delete_payload["preview_hash"], preview_payload["preview_hash"])
        self.assertTrue(delete_payload["safety"]["physical_delete_executed"])
        self.assertTrue(delete_payload["safety"]["metadata_mutated"])
        self.assertTrue(delete_payload["safety"]["audit_events_written"])
        self.assertFalse(delete_payload["safety"]["s3_delete_executed"])
        self.assertIsNotNone(delete_payload["job"]["deleted_at"])
        self.assertEqual(delete_payload["job"]["deleted_by"], "user_admin")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 0)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["id"], job_id)
        self.assertIsNotNone(detail_response.json()["deleted_at"])
        self.assertFalse(detail_response.json()["available_actions"]["delete"]["enabled"])
        self.assertEqual(download_url_response.status_code, 409)
        self.assertIn("已删除", download_url_response.json()["detail"])
        self.assertEqual(repeated_preview_response.status_code, 409)
        self.assertIn("已删除", repeated_preview_response.json()["detail"])
        self.assertIsNotNone(stored_job)
        self.assertIsNotNone(stored_job.deleted_at)
        self.assertEqual(stored_job.deleted_by, "user_admin")
        self.assertEqual(stored_job.delete_reason, "admin_preview_confirm_delete")
        for record in stored_files.values():
            self.assertIsNotNone(record)
            self.assertEqual(record.status, "deleted")
        event_types = [event["event_type"] for event in events_response.json()["items"]]
        self.assertIn("job_deleted", event_types)
        delete_audit_events = [event for event in audit_events if event.action == "document_job.delete"]
        self.assertEqual(len(delete_audit_events), 1)
        self.assertEqual(delete_audit_events[0].target_id, job_id)
        self.assertEqual(delete_audit_events[0].reason, "admin_preview_confirm_delete")

    def test_document_job_delete_preserves_shared_source_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                source_file = self._upload_source_pdf(client, operator_headers, filename="delete-shared-source.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=operator_headers,
                    json={"source_file_id": source_file["id"]},
                )
                source_job_id = create_response.json()["job_id"]
                clone_response = client.post(
                    f"/api/v1/document-jobs/{source_job_id}/clone",
                    headers=operator_headers,
                    json={"reason": "keep source alive"},
                )
                preview_response = client.post(
                    f"/api/v1/document-jobs/{source_job_id}/delete-preview",
                    headers=admin_headers,
                )
                preview_payload = preview_response.json()
                delete_response = client.post(
                    f"/api/v1/document-jobs/{source_job_id}/delete",
                    headers=admin_headers,
                    json={
                        "reason": "remove old run after clone",
                        "confirmation": preview_payload["confirmation_phrase"],
                        "preview_hash": preview_payload["preview_hash"],
                    },
                )

            source_job = runtime.document_job_repository.get_document_job(source_job_id)
            source_file_after = runtime.document_file_repository.get_document_file(source_file["id"])
            result_file_after = runtime.document_file_repository.get_document_file(source_job.result_file_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(clone_response.status_code, 201)
        self.assertEqual(preview_response.status_code, 200)
        keep_items = [item for item in preview_payload["files"] if item["action"] == "keep"]
        delete_items = [item for item in preview_payload["files"] if item["action"] == "delete"]
        self.assertEqual([item["file_id"] for item in keep_items], [source_file["id"]])
        self.assertIn("其他任务引用", keep_items[0]["reason"])
        self.assertGreater(len(delete_items), 0)
        self.assertEqual(delete_response.status_code, 200)
        self.assertIsNotNone(source_file_after)
        self.assertEqual(source_file_after.status, "uploaded")
        self.assertIsNotNone(result_file_after)
        self.assertEqual(result_file_after.status, "deleted")

    def test_document_job_archive_rejects_non_terminal_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                archive_response = client.delete(f"/api/v1/document-jobs/{job_id}", headers=headers)
                list_response = client.get("/api/v1/document-jobs", headers=headers)

            stored_job = runtime.document_job_repository.get_document_job(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "pending")
        self.assertEqual(archive_response.status_code, 409)
        self.assertEqual(archive_response.json()["error_code"], "conflict")
        self.assertIn("终态", archive_response.json()["detail"])
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 1)
        self.assertIsNotNone(stored_job)
        self.assertIsNone(stored_job.archived_at)

    def test_document_job_cancel_running_job_and_then_archive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                runtime.document_job_repository.update_document_job(
                    job_id,
                    status="running",
                    stage="parsing",
                    progress=20,
                )
                cancel_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/cancel",
                    headers={**headers, "X-Trace-Id": "trace_docjob_cancel"},
                )
                archive_response = client.delete(f"/api/v1/document-jobs/{job_id}", headers=headers)
                list_response = client.get("/api/v1/document-jobs", headers=headers)
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers)

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(cancel_response.status_code, 200)
        cancel_payload = cancel_response.json()
        self.assertEqual(cancel_payload["job_id"], job_id)
        self.assertEqual(cancel_payload["status"], "canceled")
        self.assertEqual(cancel_payload["stage"], "canceled")
        self.assertIsNotNone(cancel_payload["canceled_at"])
        self.assertEqual(archive_response.status_code, 200)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 0)
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.status, "canceled")
        self.assertEqual(stored_job.stage, "canceled")
        self.assertIsNotNone(stored_job.canceled_at)
        self.assertIsNotNone(stored_job.archived_at)
        cancel_events = [
            event for event in events_response.json()["items"]
            if event["event_type"] == "job_canceled"
        ]
        self.assertEqual(len(cancel_events), 1)
        self.assertEqual(cancel_events[0]["payload"]["previous_status"], "running")
        self.assertEqual(cancel_events[0]["payload"]["previous_stage"], "parsing")
        cancel_audit_events = [event for event in audit_events if event.action == "document_job.cancel"]
        self.assertEqual(len(cancel_audit_events), 1)
        self.assertEqual(cancel_audit_events[0].target_id, job_id)

    def test_document_job_cancel_rejects_terminal_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                runtime.document_job_repository.update_document_job(
                    job_id,
                    status="failed",
                    stage="failed",
                    failed_stage="parsing",
                    error_code="historical_failure",
                    error_message="terminal job",
                )
                cancel_response = client.post(f"/api/v1/document-jobs/{job_id}/cancel", headers=headers)

            stored_job = runtime.document_job_repository.get_document_job(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(cancel_response.status_code, 409)
        self.assertEqual(cancel_response.json()["error_code"], "conflict")
        self.assertIn("pending", cancel_response.json()["detail"])
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.status, "failed")
        self.assertIsNone(stored_job.canceled_at)

    def test_document_job_bulk_archive_returns_per_item_results_and_writes_audit(self):
        """验证批量归档支持部分失败，并且只隐藏任务不删除文件。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                succeeded_job_id = self._create_document_job_from_upload(client, headers, filename="bulk-archive-ok.pdf")
                failed_job_id = self._create_document_job_from_upload(client, headers, filename="bulk-archive-failed.pdf")
                pending_job_id = self._create_document_job_from_upload(client, headers, filename="bulk-archive-pending.pdf")
                now = utc_now()
                runtime.document_job_repository.update_document_job(
                    succeeded_job_id,
                    status="succeeded",
                    stage="completed",
                    progress=100,
                    completed_at=now,
                )
                runtime.document_job_repository.update_document_job(
                    failed_job_id,
                    status="failed",
                    stage="failed",
                    failed_stage="parsing",
                    error_code="historical_failure",
                    error_message="failed before archive",
                    completed_at=now,
                )
                response = client.post(
                    "/api/v1/document-jobs/bulk-archive",
                    headers={**headers, "X-Trace-Id": "trace_docjob_bulk_archive"},
                    json={"job_ids": [succeeded_job_id, failed_job_id, pending_job_id]},
                )

            succeeded_job = runtime.document_job_repository.get_document_job(succeeded_job_id)
            failed_job = runtime.document_job_repository.get_document_job(failed_job_id)
            pending_job = runtime.document_job_repository.get_document_job(pending_job_id)
            audit_events = runtime.audit_event_repository.list_audit_events()
            succeeded_events = runtime.document_job_event_repository.list_document_job_events(succeeded_job_id)
            failed_events = runtime.document_job_event_repository.list_document_job_events(failed_job_id)
            succeeded_source_file = runtime.document_file_repository.get_document_file(succeeded_job.source_file_id)
            failed_source_file = runtime.document_file_repository.get_document_file(failed_job.source_file_id)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["action"], "archive")
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["succeeded"], 2)
        self.assertEqual(payload["failed"], 1)
        self.assertTrue(payload["items"][0]["ok"])
        self.assertTrue(payload["items"][1]["ok"])
        self.assertFalse(payload["items"][2]["ok"])
        self.assertEqual(payload["items"][2]["job_id"], pending_job_id)
        self.assertEqual(payload["items"][2]["status_code"], 409)
        self.assertEqual(payload["items"][2]["error_code"], "conflict")
        self.assertIn("终态", payload["items"][2]["detail"])
        self.assertIsNotNone(succeeded_job.archived_at)
        self.assertIsNotNone(failed_job.archived_at)
        self.assertIsNone(pending_job.archived_at)
        self.assertIsNotNone(succeeded_source_file)
        self.assertIsNotNone(failed_source_file)
        self.assertIn("job_archived", [event.event_type for event in succeeded_events])
        self.assertIn("job_archived", [event.event_type for event in failed_events])
        archive_audit_events = [event for event in audit_events if event.action == "document_job.archive"]
        self.assertEqual(len(archive_audit_events), 2)
        self.assertEqual({event.target_id for event in archive_audit_events}, {succeeded_job_id, failed_job_id})

    def test_document_job_bulk_cancel_returns_per_item_results_and_writes_audit(self):
        """验证批量取消复用单任务取消语义，并保留终态失败项。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                pending_job_id = self._create_document_job_from_upload(client, headers, filename="bulk-cancel-pending.pdf")
                running_job_id = self._create_document_job_from_upload(client, headers, filename="bulk-cancel-running.pdf")
                failed_job_id = self._create_document_job_from_upload(client, headers, filename="bulk-cancel-failed.pdf")
                runtime.document_job_repository.update_document_job(
                    running_job_id,
                    status="running",
                    stage="parsing",
                    progress=20,
                )
                runtime.document_job_repository.update_document_job(
                    failed_job_id,
                    status="failed",
                    stage="failed",
                    failed_stage="parsing",
                    error_code="historical_failure",
                    error_message="terminal job",
                )
                response = client.post(
                    "/api/v1/document-jobs/bulk-cancel",
                    headers={**headers, "X-Trace-Id": "trace_docjob_bulk_cancel"},
                    json={"job_ids": [pending_job_id, running_job_id, failed_job_id]},
                )

            pending_job = runtime.document_job_repository.get_document_job(pending_job_id)
            running_job = runtime.document_job_repository.get_document_job(running_job_id)
            failed_job = runtime.document_job_repository.get_document_job(failed_job_id)
            audit_events = runtime.audit_event_repository.list_audit_events()
            running_events = runtime.document_job_event_repository.list_document_job_events(running_job_id)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["action"], "cancel")
        self.assertEqual(payload["succeeded"], 2)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(pending_job.status, "canceled")
        self.assertEqual(running_job.status, "canceled")
        self.assertEqual(running_job.stage, "canceled")
        self.assertIsNotNone(pending_job.canceled_at)
        self.assertIsNotNone(running_job.canceled_at)
        self.assertEqual(failed_job.status, "failed")
        self.assertIsNone(failed_job.canceled_at)
        failed_item = payload["items"][2]
        self.assertFalse(failed_item["ok"])
        self.assertEqual(failed_item["status_code"], 409)
        self.assertEqual(failed_item["error_code"], "conflict")
        self.assertIn("pending", failed_item["detail"])
        cancel_audit_events = [event for event in audit_events if event.action == "document_job.cancel"]
        self.assertEqual(len(cancel_audit_events), 2)
        self.assertEqual({event.target_id for event in cancel_audit_events}, {pending_job_id, running_job_id})
        cancel_events = [event for event in running_events if event.event_type == "job_canceled"]
        self.assertEqual(len(cancel_events), 1)
        self.assertEqual(cancel_events[0].payload["previous_status"], "running")

    def test_document_job_bulk_retry_requeues_failed_jobs_without_eager_worker(self):
        """验证批量重试只重新排队失败任务，不运行解析或生成主流程。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                failed_a_id = self._create_document_job_from_upload(client, headers, filename="bulk-retry-a.pdf")
                failed_b_id = self._create_document_job_from_upload(client, headers, filename="bulk-retry-b.pdf")
                pending_job_id = self._create_document_job_from_upload(client, headers, filename="bulk-retry-pending.pdf")
                runtime.document_job_repository.update_document_job(
                    failed_a_id,
                    status="failed",
                    stage="failed",
                    failed_stage="parsing",
                    error_code="mineru_failed",
                    error_message="mineru failed",
                )
                runtime.document_job_repository.update_document_job(
                    failed_b_id,
                    status="failed",
                    stage="failed",
                    failed_stage="rendering",
                    error_code="render_failed",
                    error_message="render failed",
                )
                response = client.post(
                    "/api/v1/document-jobs/bulk-retry",
                    headers={**headers, "X-Trace-Id": "trace_docjob_bulk_retry"},
                    json={
                        "job_ids": [failed_a_id, failed_b_id, pending_job_id],
                        "reason": "bulk retry after failures",
                    },
                )

            failed_a = runtime.document_job_repository.get_document_job(failed_a_id)
            failed_b = runtime.document_job_repository.get_document_job(failed_b_id)
            pending_job = runtime.document_job_repository.get_document_job(pending_job_id)
            audit_events = runtime.audit_event_repository.list_audit_events()
            retry_events = runtime.document_job_event_repository.list_document_job_events(failed_a_id)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["action"], "retry")
        self.assertEqual(payload["succeeded"], 2)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(failed_a.status, "pending")
        self.assertEqual(failed_b.status, "pending")
        self.assertEqual(failed_a.retry_count, 1)
        self.assertEqual(failed_b.retry_count, 1)
        self.assertIsNone(failed_a.error_code)
        self.assertIsNone(failed_b.error_code)
        self.assertEqual(pending_job.status, "pending")
        self.assertEqual(pending_job.retry_count, 0)
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.calls, [])
        failed_item = payload["items"][2]
        self.assertFalse(failed_item["ok"])
        self.assertEqual(failed_item["status_code"], 409)
        self.assertIn("failed", failed_item["detail"])
        retry_audit_events = [event for event in audit_events if event.action == "document_job.retry"]
        self.assertEqual(len(retry_audit_events), 2)
        self.assertEqual({event.target_id for event in retry_audit_events}, {failed_a_id, failed_b_id})
        self.assertEqual({event.reason for event in retry_audit_events}, {"bulk retry after failures"})
        retry_requested_events = [event for event in retry_events if event.event_type == "retry_requested"]
        self.assertEqual(len(retry_requested_events), 1)
        self.assertEqual(retry_requested_events[0].payload["reason"], "bulk retry after failures")

    def test_document_job_bulk_request_validation_rejects_invalid_job_ids(self):
        """验证批量接口对空列表、重复项和超上限列表返回 400。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(
                build_test_runtime(
                    Path(temp_dir),
                    auth_jwt_secret_key="test-jwt-secret",
                    auth_internal_users_json=build_auth_users_json(),
                )
            )
            with TestClient(app) as client:
                headers = build_auth_header(client)
                empty_response = client.post(
                    "/api/v1/document-jobs/bulk-archive",
                    headers=headers,
                    json={"job_ids": []},
                )
                duplicate_response = client.post(
                    "/api/v1/document-jobs/bulk-cancel",
                    headers=headers,
                    json={"job_ids": ["docjob_duplicate", "docjob_duplicate"]},
                )
                too_many_response = client.post(
                    "/api/v1/document-jobs/bulk-retry",
                    headers=headers,
                    json={"job_ids": [f"docjob_{index:02d}" for index in range(51)]},
                )

        self.assertEqual(empty_response.status_code, 400)
        self.assertEqual(empty_response.json()["error_code"], "invalid_request")
        self.assertIn("不能为空", empty_response.json()["detail"])
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertEqual(duplicate_response.json()["error_code"], "invalid_request")
        self.assertIn("重复", duplicate_response.json()["detail"])
        self.assertEqual(too_many_response.status_code, 400)
        self.assertEqual(too_many_response.json()["error_code"], "invalid_request")
        self.assertIn("最多支持 50", too_many_response.json()["detail"])

    def test_document_job_mineru_callback_queues_before_worker_completes_parse(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
                public_deployment_mode="single_tenant_public",
                mineru_api_token="token-123",
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            runtime.document_job_execution_service.fake_mineru_client.query_state = "running"
            runtime.document_job_execution_service.fake_mineru_client.query_full_zip_url = None
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                waiting_job = runtime.document_job_repository.get_document_job(job_id)
                payload, content = build_callback_payload(
                    batch_id=waiting_job.mineru_batch_id,
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                payload["checksum"] = build_callback_checksum(
                    uid="mineru-user-1",
                    seed=waiting_job.mineru_callback_seed,
                    content=content,
                )
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                detail_before_worker_response = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers)
                callback_summary_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/callback-messages/summary",
                    headers=headers,
                )
                metrics_response = client.get("/api/v1/health/metrics")

                queued_counts = runtime.document_job_callback_message_store.count_callback_messages_by_status()
                replayable_messages = runtime.document_job_callback_message_store.list_replayable_callback_messages(job_id)
                download_calls_before_worker = list(runtime.document_job_execution_service.fake_mineru_client.download_calls)
                worker_result = runtime.document_job_execution_service.execute_job(job_id, trace_id="trace_callback_worker")
                detail_after_worker_response = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers)

                completed_job = runtime.document_job_repository.get_document_job(job_id)
                processed_counts = runtime.document_job_callback_message_store.count_callback_messages_by_status()
                fake_client = runtime.document_job_execution_service.fake_mineru_client

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "running")
        self.assertEqual(create_response.json()["stage"], "parsing")
        self.assertIsNotNone(waiting_job)
        self.assertIsNotNone(waiting_job.mineru_callback_seed)
        self.assertEqual(
            fake_client.calls[0]["callback"],
            "https://md2word.example/api/v1/mineru-callbacks/result",
        )
        self.assertEqual(callback_response.status_code, 200)
        self.assertEqual(callback_response.json()["id"], job_id)
        self.assertEqual(detail_before_worker_response.json()["status"], "running")
        self.assertEqual(detail_before_worker_response.json()["stage"], "parsing")
        self.assertEqual(callback_summary_response.status_code, 200)
        self.assertEqual(callback_summary_response.json()["status_counts"]["pending"], 1)
        self.assertEqual(callback_summary_response.json()["replayable_count"], 1)
        self.assertEqual(callback_summary_response.json()["recent_problem_messages"], [])
        self.assertEqual(metrics_response.status_code, 200)
        self.assertEqual(metrics_response.json()["document_job_callback_messages"]["pending"], 1)
        self.assertEqual(metrics_response.json()["document_jobs"]["running"], 1)
        self.assertEqual(queued_counts["pending"], 1)
        self.assertEqual(len(replayable_messages), 1)
        self.assertEqual(download_calls_before_worker, [])
        self.assertIsNotNone(worker_result)
        self.assertEqual(worker_result.status, "succeeded")
        self.assertEqual(detail_after_worker_response.json()["status"], "succeeded")
        self.assertIsNotNone(completed_job)
        self.assertEqual(completed_job.status, "succeeded")
        self.assertEqual(completed_job.stage, "completed")
        self.assertEqual(processed_counts["processed"], 1)
        self.assertEqual(fake_client.download_calls[0]["result_url"], "https://mineru.net/result.zip")

    def test_document_job_mineru_callback_dedupes_duplicate_delivery_before_worker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
                public_deployment_mode="single_tenant_public",
                mineru_api_token="token-123",
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            runtime.document_job_execution_service.fake_mineru_client.query_state = "running"
            runtime.document_job_execution_service.fake_mineru_client.query_full_zip_url = None
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                waiting_job = runtime.document_job_repository.get_document_job(job_id)
                payload, content = build_callback_payload(
                    batch_id=waiting_job.mineru_batch_id,
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                payload["checksum"] = build_callback_checksum(
                    uid="mineru-user-1",
                    seed=waiting_job.mineru_callback_seed,
                    content=content,
                )
                first_callback_response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                second_callback_response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                queued_counts = runtime.document_job_callback_message_store.count_callback_messages_by_status()
                replayable_messages = runtime.document_job_callback_message_store.list_replayable_callback_messages(job_id)
                worker_result = runtime.document_job_execution_service.execute_job(job_id, trace_id="trace_duplicate_callback")
                second_worker_result = runtime.document_job_execution_service.execute_job(job_id, trace_id="trace_duplicate_callback")
                processed_counts = runtime.document_job_callback_message_store.count_callback_messages_by_status()
                fake_client = runtime.document_job_execution_service.fake_mineru_client

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(first_callback_response.status_code, 200)
        self.assertEqual(second_callback_response.status_code, 200)
        self.assertEqual(queued_counts["pending"], 1)
        self.assertEqual(len(replayable_messages), 1)
        self.assertIsNotNone(worker_result)
        self.assertEqual(worker_result.status, "succeeded")
        self.assertIsNotNone(second_worker_result)
        self.assertEqual(second_worker_result.status, "succeeded")
        self.assertEqual(processed_counts["processed"], 1)
        self.assertEqual(len(fake_client.download_calls), 1)

    def test_document_job_worker_ignores_queued_callback_after_cancel(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
                public_deployment_mode="single_tenant_public",
                mineru_api_token="token-123",
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            runtime.document_job_execution_service.fake_mineru_client.query_state = "running"
            runtime.document_job_execution_service.fake_mineru_client.query_full_zip_url = None
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                waiting_job = runtime.document_job_repository.get_document_job(job_id)
                payload, content = build_callback_payload(
                    batch_id=waiting_job.mineru_batch_id,
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                payload["checksum"] = build_callback_checksum(
                    uid="mineru-user-1",
                    seed=waiting_job.mineru_callback_seed,
                    content=content,
                )
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                cancel_response = client.post(f"/api/v1/document-jobs/{job_id}/cancel", headers=headers)
                worker_result = runtime.document_job_execution_service.execute_job(job_id, trace_id="trace_cancel_callback")
                ignored_counts = runtime.document_job_callback_message_store.count_callback_messages_by_status()
                final_job = runtime.document_job_repository.get_document_job(job_id)
                fake_client = runtime.document_job_execution_service.fake_mineru_client

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(callback_response.status_code, 200)
        self.assertEqual(cancel_response.status_code, 200)
        self.assertIsNotNone(worker_result)
        self.assertEqual(worker_result.status, "canceled")
        self.assertIsNotNone(final_job)
        self.assertEqual(final_job.status, "canceled")
        self.assertEqual(final_job.stage, "canceled")
        self.assertEqual(ignored_counts["ignored"], 1)
        self.assertEqual(fake_client.download_calls, [])

    def test_document_job_failed_mineru_callback_is_queued_then_worker_marks_failed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
                public_deployment_mode="single_tenant_public",
                mineru_api_token="token-123",
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            runtime.document_job_execution_service.fake_mineru_client.query_state = "running"
            runtime.document_job_execution_service.fake_mineru_client.query_full_zip_url = None
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                waiting_job = runtime.document_job_repository.get_document_job(job_id)
                payload, content = build_callback_payload(
                    batch_id=waiting_job.mineru_batch_id,
                    data_id=job_id,
                    state="failed",
                )
                payload["checksum"] = build_callback_checksum(
                    uid="mineru-user-1",
                    seed=waiting_job.mineru_callback_seed,
                    content=content,
                )
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                before_worker_job = runtime.document_job_repository.get_document_job(job_id)
                worker_result = runtime.document_job_execution_service.execute_job(job_id, trace_id="trace_failed_callback")
                processed_counts = runtime.document_job_callback_message_store.count_callback_messages_by_status()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(callback_response.status_code, 200)
        self.assertIsNotNone(before_worker_job)
        self.assertEqual(before_worker_job.status, "running")
        self.assertIsNotNone(worker_result)
        self.assertEqual(worker_result.status, "failed")
        self.assertEqual(worker_result.stage, "failed")
        self.assertEqual(worker_result.failed_stage, "parsing")
        self.assertEqual(worker_result.error_code, "mineru_failed")
        self.assertEqual(processed_counts["processed"], 1)

    def test_document_job_invalid_callback_checksum_leaves_no_callback_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
                public_deployment_mode="single_tenant_public",
                mineru_api_token="token-123",
                mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            runtime.document_job_execution_service.fake_mineru_client.query_state = "running"
            runtime.document_job_execution_service.fake_mineru_client.query_full_zip_url = None
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                waiting_job = runtime.document_job_repository.get_document_job(job_id)
                payload, _content = build_callback_payload(
                    batch_id=waiting_job.mineru_batch_id,
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                payload["checksum"] = "bad-checksum"
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                counts = runtime.document_job_callback_message_store.count_callback_messages_by_status()
                final_job = runtime.document_job_repository.get_document_job(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(callback_response.status_code, 403)
        self.assertEqual(sum(counts.values()), 0)
        self.assertIsNotNone(final_job)
        self.assertEqual(final_job.status, "running")
        self.assertEqual(final_job.stage, "parsing")

    def test_document_job_execution_skeleton_is_idempotent_for_duplicate_delivery(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]

            first_result = runtime.document_job_execution_service.execute_job(job_id, trace_id="trace_duplicate")
            first_events = runtime.document_job_event_repository.list_document_job_events(job_id)
            second_result = runtime.document_job_execution_service.execute_job(job_id, trace_id="trace_duplicate")
            second_events = runtime.document_job_event_repository.list_document_job_events(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertIsNotNone(first_result)
        self.assertEqual(first_result.status, "succeeded")
        self.assertEqual(first_result.stage, "completed")
        self.assertIsNotNone(first_result.mineru_raw_result_file_id)
        self.assertIsNotNone(first_result.document_ir_file_id)
        self.assertIsNotNone(first_result.result_file_id)
        self.assertIsNotNone(second_result)
        self.assertEqual(second_result.status, "succeeded")
        self.assertEqual(second_result.stage, "completed")
        self.assertEqual(second_result.mineru_raw_result_file_id, first_result.mineru_raw_result_file_id)
        self.assertEqual(second_result.document_ir_file_id, first_result.document_ir_file_id)
        self.assertEqual(second_result.image_asset_file_ids, first_result.image_asset_file_ids)
        self.assertEqual(second_result.result_file_id, first_result.result_file_id)
        self.assertEqual([event.id for event in second_events], [event.id for event in first_events])
        self.assertEqual(second_events[-1].event_type, "stage_succeeded")
        self.assertEqual(second_events[-1].stage, "completed")

    def test_document_job_worker_saves_mineru_raw_ir_and_image_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            raw_file = runtime.document_file_repository.get_document_file(stored_job.mineru_raw_result_file_id)
            ir_file = runtime.document_file_repository.get_document_file(stored_job.document_ir_file_id)
            word_file = runtime.document_file_repository.get_document_file(stored_job.result_file_id)
            image_files = [
                runtime.document_file_repository.get_document_file(file_id)
                for file_id in stored_job.image_asset_file_ids
            ]
            image_archive_files = [
                file
                for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id and file.file_type == "image_assets_archive"
            ]
            raw_bytes = runtime.file_upload_service.read_file_content(raw_file)
            ir_payload = json.loads(runtime.file_upload_service.read_file_content(ir_file).decode("utf-8"))
            image_bytes = runtime.file_upload_service.read_file_content(image_files[0])
            image_archive_bytes = runtime.file_upload_service.read_file_content(image_archive_files[0])
            word_bytes = runtime.file_upload_service.read_file_content(word_file)
            events = runtime.document_job_event_repository.list_document_job_events(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(stored_job.stage, "completed")
        expected_layout_page_count = len(ir_payload["pages"])
        self.assertEqual(raw_file.file_type, "mineru_raw_result")
        self.assertEqual(ir_file.file_type, "document_ir")
        self.assertEqual(ir_file.original_filename, "document_ir_v2.json")
        self.assertEqual(word_file.file_type, "generated_word")
        self.assertEqual(ir_file.metadata["schema_version"], "document-ir/v2")
        self.assertEqual(ir_file.metadata["layout_page_count"], expected_layout_page_count)
        self.assertEqual(ir_file.metadata["layout_block_count"], 6)
        self.assertEqual(word_file.metadata["schema_version"], "document-ir/v2")
        self.assertEqual(word_file.metadata["renderer_mode"], "layout_v2")
        self.assertEqual(word_file.metadata["layout_page_count"], expected_layout_page_count)
        self.assertEqual(word_file.metadata["layout_block_count"], 6)
        self.assertIn("layout_wide_table:block_0003", word_file.metadata["layout_quality_flags"])
        self.assertEqual(word_file.metadata["quality_flags"], [])
        self.assertTrue(word_file.metadata["docx_quality"]["editable_content_available"])
        self.assertFalse(word_file.metadata["docx_quality"]["image_only_suspected"])
        self.assertGreaterEqual(word_file.metadata["docx_quality"]["landscape_sections"], 1)
        self.assertEqual(word_file.metadata["template_version_id"], "default@1")
        self.assertEqual([file.file_type for file in image_files], ["image_asset"])
        self.assertEqual([file.file_type for file in image_archive_files], ["image_assets_archive"])
        self.assertEqual(image_archive_files[0].metadata["image_asset_count"], 1)
        self.assertEqual(image_archive_files[0].metadata["retry_count"], 0)
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
            self.assertIn("content_list_v2.json", archive.namelist())
        with zipfile.ZipFile(io.BytesIO(image_archive_bytes)) as archive:
            self.assertIn("manifest.json", archive.namelist())
            self.assertIn("images/asset_block_0004_figure1.png", archive.namelist())
        with zipfile.ZipFile(io.BytesIO(word_bytes)) as archive:
            self.assertIn("word/document.xml", archive.namelist())
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertEqual(ir_payload["schema_version"], "document-ir/v2")
        self.assertTrue(ir_payload["pages"])
        self.assertEqual(ir_payload["pages"][0]["metadata"]["orientation"], "portrait")
        self.assertEqual(ir_payload["pages"][1]["metadata"]["orientation"], "landscape")
        self.assertIn('w:orient="landscape"', document_xml)
        self.assertEqual(
            [block["type"] for block in ir_payload["blocks"]],
            ["heading", "paragraph", "table", "image", "list", "formula"],
        )
        self.assertEqual(ir_payload["blocks"][0]["layout"]["page_index"], 0)
        self.assertEqual(ir_payload["blocks"][2]["layout"]["column_hint"], "wide")
        self.assertEqual(ir_payload["blocks"][3]["layout"]["column_hint"], "right")
        self.assertIn("layout_wide_table:block_0003", ir_payload["quality_flags"])
        self.assertIn("layout_caption_binding:block_0003", ir_payload["quality_flags"])
        self.assertEqual(ir_payload["assets"][0]["file_id"], image_files[0].id)
        self.assertEqual(ir_payload["assets"][0]["object_key"], image_files[0].object_key)
        self.assertEqual(ir_payload["blocks"][3]["asset_ref"], ir_payload["assets"][0]["id"])
        self.assertEqual(image_bytes, MINIMAL_PNG_BYTES)
        ir_registered_event = next(
            event
            for event in events
            if event.event_type == "file_registered" and event.payload.get("file_type") == "document_ir"
        )
        rendered_event = next(event for event in events if event.event_type == "stage_succeeded" and event.stage == "rendering")
        word_registered_event = next(
            event
            for event in events
            if event.event_type == "file_registered" and event.payload.get("file_type") == "generated_word"
        )
        self.assertEqual(ir_registered_event.payload["schema_version"], "document-ir/v2")
        self.assertEqual(ir_registered_event.payload["layout_block_count"], 6)
        self.assertEqual(rendered_event.payload["renderer_mode"], "layout_v2")
        self.assertIn("layout_wide_table:block_0003", rendered_event.payload["layout_quality_flags"])
        self.assertEqual(word_registered_event.payload["renderer_mode"], "layout_v2")
        self.assertIn("layout_wide_table:block_0003", word_registered_event.payload["layout_quality_flags"])

    def test_document_job_worker_generated_word_keeps_renderer_ooxml_semantics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = make_semantic_mineru_zip_bytes()
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            word_file = runtime.document_file_repository.get_document_file(stored_job.result_file_id)
            word_bytes = runtime.file_upload_service.read_file_content(word_file)

        with zipfile.ZipFile(io.BytesIO(word_bytes)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
            numbering_xml = archive.read("word/numbering.xml").decode("utf-8")

        table_index = document_xml.index("<w:tbl>")
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(stored_job.status, "succeeded")
        self.assertEqual(word_file.file_type, "generated_word")
        self.assertEqual(word_file.metadata["quality_flags"], [])
        self.assertGreaterEqual(word_file.metadata["docx_quality"]["heading_paragraphs"], 1)
        self.assertGreaterEqual(word_file.metadata["docx_quality"]["numbering_paragraphs"], 1)
        self.assertGreaterEqual(word_file.metadata["docx_quality"]["table_header_rows"], 1)
        self.assertGreaterEqual(word_file.metadata["docx_quality"]["table_no_split_rows"], 1)
        self.assertEqual(word_file.metadata["docx_quality"]["latex_residue_count"], 0)
        self.assertFalse(word_file.metadata["docx_quality"]["image_only_suspected"])
        self.assertIn("<w:pStyle", document_xml[: document_xml.index("6.5 Thermal Information")])
        self.assertIn("<w:numPr>", document_xml)
        self.assertIn('w:val="bullet"', numbering_xml)
        self.assertIn('w:val="subscript"', document_xml)
        self.assertIn('w:val="superscript"', document_xml)
        self.assertLess(document_xml.index("Table 1: Electrical Characteristics"), table_index)
        self.assertLess(table_index, document_xml.index("Note: E=mc"))
        self.assertIn("<w:keepNext/>", document_xml[:table_index])
        self.assertNotIn("• Low noise", document_xml)
        self.assertNotIn(r"\sqrt", document_xml)
        self.assertNotIn(r"\theta", document_xml)

    def test_document_job_worker_keeps_portrait_wide_table_and_condition_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = (
                make_portrait_wide_table_condition_mineru_zip_bytes()
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"], "document_language": "en"},
                )
                job_id = create_response.json()["job_id"]

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            files = [
                file
                for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id
            ]
            files_by_type = {file.file_type: file for file in files}
            word_file = files_by_type["generated_word"]
            word_bytes = runtime.file_upload_service.read_file_content(word_file)
            ir_payload = json.loads(
                runtime.file_upload_service.read_file_content(files_by_type["document_ir"]).decode("utf-8")
            )

        with zipfile.ZipFile(io.BytesIO(word_bytes)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        rendered = Document(io.BytesIO(word_bytes))
        table_index = document_xml.index("<w:tbl>")
        condition_paragraph = next(
            paragraph
            for paragraph in rendered.paragraphs
            if paragraph.text.startswith("at TA = +25°C")
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(stored_job.status, "succeeded")
        self.assertEqual(word_file.file_type, "generated_word")
        self.assertEqual(ir_payload["pages"][0]["metadata"]["orientation"], "portrait")
        self.assertEqual([block["type"] for block in ir_payload["blocks"]], ["heading", "paragraph", "table"])
        self.assertEqual(ir_payload["blocks"][1]["metadata"]["annotation_role"], "table_context")
        self.assertEqual(ir_payload["blocks"][1]["metadata"]["source_block_id"], "block_0002")
        self.assertTrue(ir_payload["blocks"][1]["text"].startswith("at TA = +25°C"))
        self.assertEqual(ir_payload["blocks"][2]["captions"], [])
        self.assertIn("layout_table_context_binding:block_0002", ir_payload["quality_flags"])
        self.assertIn("layout_wide_table:block_0002", ir_payload["quality_flags"])
        self.assertNotIn("layout_caption_binding:block_0002", ir_payload["quality_flags"])
        self.assertEqual(word_file.metadata["docx_quality"]["landscape_sections"], 0)
        self.assertGreaterEqual(word_file.metadata["docx_quality"]["wide_table_count"], 1)
        self.assertTrue(word_file.metadata["docx_quality"]["editable_content_available"])
        self.assertFalse(word_file.metadata["docx_quality"]["image_only_suspected"])
        self.assertLess(document_xml.index("at TA = +25°C"), table_index)
        self.assertNotIn('w:orient="landscape"', document_xml)
        self.assertNotIn('<w:jc w:val="center"', document_xml[:table_index])
        self.assertNotEqual(condition_paragraph.alignment, WD_ALIGN_PARAGRAPH.CENTER)

    def test_document_job_worker_passes_subscript_config_to_document_ir_renderer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            runtime.settings.term_rules_runtime_yaml_file.write_text(
                "\n".join(
                    [
                        "subscript_rules:",
                        "  electrical:",
                        "    VOS: V<sub>OS</sub>",
                        "    IOS: I<sub>OS</sub>",
                    ]
                ),
                encoding="utf-8",
            )
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = make_subscript_mineru_zip_bytes()
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"], "document_language": "en"},
                )
                job_id = create_response.json()["job_id"]

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            word_file = runtime.document_file_repository.get_document_file(stored_job.result_file_id)
            word_bytes = runtime.file_upload_service.read_file_content(word_file)

        with zipfile.ZipFile(io.BytesIO(word_bytes)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(stored_job.status, "succeeded")
        self.assertEqual(word_file.file_type, "generated_word")
        self.assertGreaterEqual(document_xml.count('w:val="subscript"'), 4)
        self.assertNotIn("&lt;sub&gt;", document_xml)

    def test_document_job_en2zh_worker_translates_ir_and_saves_ai_audit_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
                translation_debug_archive_enabled=True,
            )
            provider = FakeDocumentJobTranslationProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(
                provider,
                max_items_per_request=3,
                max_chars_per_request=10_000,
            )
            runtime.document_job_execution_service.document_ir_translation_service = runtime.document_ir_translation_service
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = make_english_mineru_zip_bytes()
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client, username="admin", password="admin-pass")
                source_file = self._upload_source_pdf(client, headers, filename="english-datasheet.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                        "debug_full_text": True,
                    },
                )
                job_id = create_response.json()["job_id"]
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers)
                files_response = client.get(f"/api/v1/document-jobs/{job_id}/files", headers=headers)
                batches_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/translation-batches",
                    headers=headers,
                )

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            files = [
                file
                for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id
            ]
            files_by_type = {file.file_type: file for file in files}
            ai_log_files = sorted(
                [file for file in files if file.file_type == "ai_call_log"],
                key=lambda item: (item.created_at, item.id),
            )
            debug_archive_files = sorted(
                [file for file in files if file.file_type == "ai_debug_archive"],
                key=lambda item: (item.created_at, item.id),
            )
            ir_payload = json.loads(
                runtime.file_upload_service.read_file_content(files_by_type["document_ir"]).decode("utf-8")
            )
            ai_log_payloads = [
                json.loads(runtime.file_upload_service.read_file_content(file).decode("utf-8"))
                for file in ai_log_files
            ]
            ai_log_text = "\n".join(
                runtime.file_upload_service.read_file_content(file).decode("utf-8")
                for file in ai_log_files
            )
            debug_payloads = [
                json.loads(runtime.file_upload_service.read_file_content(file).decode("utf-8"))
                for file in debug_archive_files
            ]
            debug_text = "\n".join(
                runtime.file_upload_service.read_file_content(file).decode("utf-8")
                for file in debug_archive_files
            )
            batch_result_files = [file for file in files if file.file_type == "translation_batch_result"]

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "succeeded")
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.term_version_id, "en2zh@v1")
        self.assertTrue(stored_job.debug_full_text_enabled)
        self.assertEqual([len(request.items) for request in provider.requests], [3, 3, 2])
        self.assertEqual(ir_payload["metadata"]["document_language"], "zh")
        self.assertEqual(ir_payload["blocks"][0]["text"], "1 特性")
        self.assertEqual(ir_payload["blocks"][1]["text"], "输入失调电压很低。")
        self.assertIn("<th>参数</th>", ir_payload["blocks"][2]["html"])
        self.assertEqual(ir_payload["blocks"][4]["list_items"], ["低噪声", "高压摆率"])
        self.assertEqual(files_by_type["document_ir"].metadata["translation"]["applied"], True)
        self.assertEqual(len(ai_log_files), 3)
        self.assertEqual(len(debug_archive_files), 3)
        self.assertEqual(len(batch_result_files), 3)
        self.assertTrue(all(file.metadata["status"] == "succeeded" for file in ai_log_files))
        self.assertTrue(all(payload["status"] == "succeeded" for payload in ai_log_payloads))
        self.assertEqual(sum(payload["request"]["item_count"] for payload in ai_log_payloads), 8)
        self.assertIn("sha256:", ai_log_payloads[0]["request"]["redacted_items"][0]["sha256"])
        self.assertNotIn("The input offset voltage is low.", ai_log_text)
        self.assertIn("The input offset voltage is low.", debug_text)
        self.assertIn("输入失调电压很低。", debug_text)
        self.assertTrue(all(payload["schema_version"] == "translation-debug-archive/v1" for payload in debug_payloads))
        self.assertTrue(all(file.metadata["contains_full_text"] is True for file in debug_archive_files))
        self.assertTrue(
            all(
                file.expires_at - file.created_at <= timedelta(days=1, seconds=1)
                for file in debug_archive_files
            )
        )
        event_types = [event["event_type"] for event in events_response.json()["items"]]
        self.assertIn("ai_call_logged", event_types)
        self.assertIn("debug_archive_saved", event_types)
        self.assertEqual(files_response.status_code, 200)
        file_types = [file["file_type"] for file in files_response.json()["files"]]
        self.assertIn("ai_call_log", file_types)
        self.assertIn("ai_debug_archive", file_types)
        self.assertEqual(batches_response.status_code, 200)
        batches_payload = batches_response.json()
        self.assertEqual(len(batches_payload["items"]), 3)
        self.assertEqual([item["status"] for item in batches_payload["items"]], ["succeeded", "succeeded", "succeeded"])
        self.assertEqual(sum(item["item_count"] for item in batches_payload["items"]), 8)
        self.assertTrue(all(item["result_file_id"] for item in batches_payload["items"]))
        self.assertTrue(all(item["ai_call_log_file_ids"] for item in batches_payload["items"]))

    def test_document_job_en2zh_debug_full_text_is_admin_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
                translation_debug_archive_enabled=True,
            )
            runtime.document_ir_translation_service = DocumentIRTranslationService(FakeDocumentJobTranslationProvider())
            runtime.document_job_execution_service.document_ir_translation_service = runtime.document_ir_translation_service
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = make_english_mineru_zip_bytes()
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, operator_headers, filename="operator-debug.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=operator_headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                        "debug_full_text": True,
                    },
                )

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(create_response.json()["error_code"], "role_forbidden")

    def test_document_job_translation_qa_reads_existing_artifacts_and_updates_review_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
                translation_debug_archive_enabled=True,
            )
            provider = FakeDocumentJobTranslationProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            runtime.document_job_execution_service.document_ir_translation_service = runtime.document_ir_translation_service
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = make_english_mineru_zip_bytes()
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, admin_headers, filename="qa-english.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=admin_headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                        "debug_full_text": True,
                    },
                )
                job_id = create_response.json()["job_id"]

                qa_response = client.get(f"/api/v1/document-jobs/{job_id}/translation-qa", headers=admin_headers)
                update_response = client.patch(
                    f"/api/v1/document-jobs/{job_id}/translation-qa",
                    headers=admin_headers,
                    json={
                        "status": "needs_fix",
                        "issue_type": "terminology",
                        "note": "术语译法需要复核。",
                    },
                )
                detail_response = client.get(f"/api/v1/document-jobs/{job_id}", headers=admin_headers)
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=admin_headers)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(qa_response.status_code, 200)
        qa_payload = qa_response.json()
        self.assertTrue(qa_payload["available"])
        self.assertIsNone(qa_payload["availability_reason"])
        self.assertEqual(qa_payload["qa"]["status"], "unreviewed")
        self.assertGreater(qa_payload["summary"]["final_segment_count"], 0)
        self.assertGreater(qa_payload["summary"]["ai_call_count"], 0)
        self.assertGreater(qa_payload["summary"]["term_trace_count"], 0)
        self.assertTrue(qa_payload["summary"]["debug_full_text_enabled"])
        self.assertTrue(qa_payload["summary"]["source_comparison_available"])
        self.assertIn("document_ir_file_id", qa_payload["artifacts"])
        self.assertTrue(qa_payload["artifacts"]["ai_call_log_file_ids"])
        self.assertTrue(qa_payload["artifacts"]["ai_debug_archive_file_ids"])
        self.assertTrue(qa_payload["artifacts"]["ai_debug_archive_contains_full_text"])
        self.assertFalse(qa_payload["artifacts"]["ai_debug_archive_expired"])
        self.assertIsNotNone(qa_payload["artifacts"]["ai_debug_archive_expires_at"])
        self.assertTrue(any(call["status"] == "succeeded" for call in qa_payload["ai_calls"]))
        self.assertTrue(any(trace["source_term"] == "input offset voltage" for trace in qa_payload["term_traces"]))
        matching_segments = [
            segment
            for segment in qa_payload["segments"]
            if segment["id"] == "block_0002.text"
        ]
        self.assertEqual(matching_segments[0]["source_text"], "The input offset voltage is low.")
        self.assertEqual(matching_segments[0]["final_text"], "输入失调电压很低。")

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["qa"]["status"], "needs_fix")
        self.assertEqual(update_response.json()["qa"]["issue_type"], "terminology")
        self.assertEqual(detail_response.json()["translation_qa_status"], "needs_fix")
        self.assertEqual(detail_response.json()["translation_qa_issue_type"], "terminology")
        qa_events = [
            event
            for event in events_response.json()["items"]
            if event["event_type"] == "translation_qa_updated"
        ]
        self.assertEqual(len(qa_events), 1)
        self.assertEqual(qa_events[0]["payload"]["note_length"], len("术语译法需要复核。"))
        self.assertNotIn("note", qa_events[0]["payload"])
        self.assertNotIn("The input offset voltage is low.", json.dumps(qa_events[0]["payload"], ensure_ascii=False))

    def test_document_job_translation_qa_marks_direct_jobs_unavailable_and_rejects_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="direct-qa.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                qa_response = client.get(f"/api/v1/document-jobs/{job_id}/translation-qa", headers=headers)
                update_response = client.patch(
                    f"/api/v1/document-jobs/{job_id}/translation-qa",
                    headers=headers,
                    json={"status": "approved", "issue_type": None, "note": None},
                )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(qa_response.status_code, 200)
        self.assertFalse(qa_response.json()["available"])
        self.assertEqual(qa_response.json()["availability_reason"], "unsupported_mode")
        self.assertEqual(update_response.status_code, 409)

    def test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = FakeDocumentJobTranslationProvider(raise_error=True)
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            runtime.document_job_execution_service.document_ir_translation_service = runtime.document_ir_translation_service
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = make_english_mineru_zip_bytes()
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="english-failure.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )
                job_id = create_response.json()["job_id"]

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            files = [
                file
                for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id
            ]
            ai_logs = [file for file in files if file.file_type == "ai_call_log"]
            debug_archives = [file for file in files if file.file_type == "ai_debug_archive"]
            ai_log_text = runtime.file_upload_service.read_file_content(ai_logs[0]).decode("utf-8")
            ai_log_payload = json.loads(ai_log_text)
            batches = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "failed")
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.error_code, "translation_failed")
        self.assertEqual(len(provider.requests), 2)
        self.assertEqual(len(ai_logs), 2)
        self.assertEqual(debug_archives, [])
        self.assertEqual(ai_log_payload["status"], "failed")
        self.assertEqual(ai_log_payload["error"]["type"], "RuntimeError")
        self.assertNotIn("The input offset voltage is low.", ai_log_text)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].status, "failed")
        self.assertEqual(batches[0].attempt_count, 2)
        self.assertFalse(batches[0].retryable)

    def test_document_job_en2zh_truncated_batch_is_split_and_fanned_in(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = TruncatingOnceDocumentJobTranslationProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            runtime.document_job_execution_service.document_ir_translation_service = runtime.document_ir_translation_service
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = make_english_mineru_zip_bytes()
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="english-truncated.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )
                job_id = create_response.json()["job_id"]
                batches_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/translation-batches",
                    headers=headers,
                )

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            files = [
                file
                for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id
            ]
            ir_file = next(file for file in files if file.id == stored_job.document_ir_file_id)
            ir_payload = json.loads(runtime.file_upload_service.read_file_content(ir_file).decode("utf-8"))
            batches = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)
            split_batches = [batch for batch in batches if batch.status == "split"]
            succeeded_batches = [batch for batch in batches if batch.status == "succeeded"]
            events = runtime.document_job_event_repository.list_document_job_events(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "succeeded")
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.status, "succeeded")
        self.assertEqual(len(provider.requests), 3)
        self.assertEqual(len(split_batches), 1)
        self.assertEqual(split_batches[0].finish_reason, "length")
        self.assertEqual(split_batches[0].error_code, "translation_provider_truncated")
        self.assertEqual({batch.provider_call_budget for batch in batches}, {12})
        self.assertEqual(len(succeeded_batches), 2)
        self.assertEqual(sum(batch.item_count for batch in succeeded_batches), 8)
        self.assertEqual(ir_payload["blocks"][1]["text"], "输入失调电压很低。")
        self.assertEqual(batches_response.status_code, 200)
        self.assertEqual(
            sorted(item["status"] for item in batches_response.json()["items"]),
            ["split", "succeeded", "succeeded"],
        )
        self.assertIn("translation_batch_split", [event.event_type for event in events])

    def test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = FakeDocumentJobTranslationProvider(raise_error=True)
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            runtime.document_job_execution_service.document_ir_translation_service = runtime.document_ir_translation_service
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = make_english_mineru_zip_bytes()
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="english-retry.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )
                job_id = create_response.json()["job_id"]
                first_job = runtime.document_job_repository.get_document_job(job_id)
                old_ai_log = next(
                    file
                    for file in runtime.document_file_repository.list_document_files()
                    if file.job_id == job_id and file.file_type == "ai_call_log"
                )

                provider.raise_error = False
                retry_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/retry",
                    headers={**headers, "X-Trace-Id": "trace_translation_retry"},
                    json={"reason": "provider fixed"},
                )
                files_response = client.get(f"/api/v1/document-jobs/{job_id}/files", headers=headers)
                old_log_download_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/download-url",
                    headers=headers,
                    params={"file_id": old_ai_log.id},
                )

            all_job_files = [
                file
                for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id
            ]
            retry_events = [
                event
                for event in runtime.document_job_event_repository.list_document_job_events(job_id)
                if event.event_type == "retry_requested"
            ]

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "failed")
        self.assertIsNotNone(first_job)
        self.assertEqual(first_job.error_code, "translation_failed")
        self.assertIsNotNone(first_job.mineru_raw_result_file_id)
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.json()["status"], "succeeded")
        self.assertEqual(retry_response.json()["retry_count"], 1)
        self.assertEqual(len(provider.requests), 3)
        self.assertEqual(len(runtime.document_job_execution_service.fake_mineru_client.calls), 1)
        self.assertEqual(len(runtime.document_job_execution_service.fake_mineru_client.download_calls), 1)
        self.assertEqual(retry_events[-1].payload["resume_stage"], "parsed")
        self.assertEqual(old_log_download_response.status_code, 409)

        repository_file_types = [file.file_type for file in all_job_files]
        self.assertEqual(repository_file_types.count("ai_call_log"), 3)
        self.assertEqual(repository_file_types.count("image_assets_archive"), 1)
        visible_file_types = [file["file_type"] for file in files_response.json()["files"]]
        self.assertEqual(visible_file_types.count("ai_call_log"), 1)
        self.assertEqual(visible_file_types.count("image_assets_archive"), 0)
        self.assertIn("generated_word", visible_file_types)
        self.assertNotIn("image_asset", visible_file_types)

    def test_document_job_download_url_returns_temporary_generated_word_link(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                download_url_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/download-url",
                    headers={**headers, "X-Trace-Id": "trace_download_url"},
                )
                download_path = download_url_response.json()["download_url"].replace("http://testserver", "")
                download_response = client.get(download_path)
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers)
                audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(download_url_response.status_code, 200)
        payload = download_url_response.json()
        self.assertEqual(payload["job_id"], job_id)
        self.assertEqual(payload["file"]["file_type"], "generated_word")
        self.assertIn(f"/api/v1/document-jobs/{job_id}/download?token=", payload["download_url"])
        self.assertEqual(download_response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(download_response.content)) as archive:
            self.assertIn("word/document.xml", archive.namelist())
        download_events = [
            event for event in events_response.json()["items"]
            if event["event_type"] == "download_authorized"
        ]
        self.assertEqual(len(download_events), 1)
        self.assertEqual(download_events[0]["trace_id"], "trace_download_url")
        download_audit_events = [
            event for event in audit_events
            if event.action == "document_job.download_authorize"
        ]
        self.assertEqual(len(download_audit_events), 1)
        self.assertEqual(download_audit_events[0].target_id, job_id)

    def test_document_job_download_url_uses_forwarded_https_scheme(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                download_url_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/download-url",
                    headers={**headers, "X-Forwarded-Proto": "https"},
                )

        self.assertEqual(download_url_response.status_code, 200)
        self.assertTrue(download_url_response.json()["download_url"].startswith("https://testserver/"))

    def test_document_job_download_url_rejects_unfinished_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                download_url_response = client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=headers)

        self.assertEqual(download_url_response.status_code, 409)
        self.assertEqual(download_url_response.json()["error_code"], "conflict")

    def test_document_job_files_endpoint_lists_artifacts_and_authorizes_source_download(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="files-source.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                files_response = client.get(f"/api/v1/document-jobs/{job_id}/files", headers=headers)
                source_download_url_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/download-url",
                    headers={**headers, "X-Trace-Id": "trace_source_download"},
                    params={"file_id": source_file["id"]},
                )
                source_download_path = source_download_url_response.json()["download_url"].replace("http://testserver", "")
                source_download_response = client.get(source_download_path)
                result_file_id = create_response.json()["job"]["result_file_id"]
                runtime.document_file_repository.update_document_file(
                    result_file_id,
                    expires_at=utc_now() - timedelta(seconds=1),
                )
                expired_result_download_url_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/download-url",
                    headers=headers,
                )
                events_response = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(files_response.status_code, 200)
        file_payloads = files_response.json()["files"]
        file_types = [file["file_type"] for file in file_payloads]
        self.assertEqual(file_types[0], "source_pdf")
        self.assertIn("generated_word", file_types)
        self.assertIn("mineru_raw_result", file_types)
        self.assertIn("document_ir", file_types)
        self.assertIn("image_assets_archive", file_types)
        self.assertNotIn("image_asset", file_types)
        for file_payload in file_payloads:
            self.assertIn("quality_evidence", file_payload)
            self.assertNotIn("bucket", file_payload)
            self.assertNotIn("object_key", file_payload)
            self.assertNotIn("checksum_sha256", file_payload)
            self.assertNotIn("etag", file_payload)
            self.assertNotIn("metadata", file_payload)
        generated_word_payload = next(file for file in file_payloads if file["file_type"] == "generated_word")
        self.assertIn("docx_quality", generated_word_payload["quality_evidence"])
        self.assertEqual(source_download_url_response.status_code, 200)
        self.assertEqual(source_download_url_response.json()["file_id"], source_file["id"])
        source_download_file = source_download_url_response.json()["file"]
        self.assertEqual(source_download_file["file_type"], "source_pdf")
        self.assertNotIn("bucket", source_download_file)
        self.assertNotIn("object_key", source_download_file)
        self.assertNotIn("metadata", source_download_file)
        self.assertEqual(source_download_response.status_code, 200)
        self.assertTrue(source_download_response.content.startswith(b"%PDF"))
        self.assertEqual(expired_result_download_url_response.status_code, 409)
        self.assertEqual(expired_result_download_url_response.json()["error_code"], "conflict")
        download_events = [
            event for event in events_response.json()["items"]
            if event["event_type"] == "download_authorized" and event["payload"]["file_id"] == source_file["id"]
        ]
        self.assertEqual(len(download_events), 1)
        self.assertEqual(download_events[0]["trace_id"], "trace_source_download")

    def test_document_job_file_download_rejects_mismatched_and_expired_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers, filename="download-source.pdf")
                other_file = self._upload_source_pdf(client, headers, filename="other-source.pdf")
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                mismatched_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/download-url",
                    headers=headers,
                    params={"file_id": other_file["id"]},
                )
                runtime.document_file_repository.update_document_file(
                    source_file["id"],
                    expires_at=utc_now() - timedelta(seconds=1),
                )
                expired_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/download-url",
                    headers=headers,
                    params={"file_id": source_file["id"]},
                )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(mismatched_response.status_code, 403)
        self.assertEqual(mismatched_response.json()["error_code"], "forbidden")
        self.assertEqual(expired_response.status_code, 409)
        self.assertEqual(expired_response.json()["error_code"], "conflict")

    def test_document_job_worker_waits_when_mineru_result_is_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.fake_mineru_client.query_state = "running"
            runtime.document_job_execution_service.fake_mineru_client.query_full_zip_url = None
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            events = runtime.document_job_event_repository.list_document_job_events(job_id)
            job_files = [
                file
                for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id
            ]

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["stage"], "parsing")
        self.assertEqual(create_response.json()["progress"], 20)
        self.assertEqual(stored_job.status, "running")
        self.assertEqual(stored_job.stage, "parsing")
        self.assertIsNotNone(stored_job.mineru_batch_id)
        self.assertIsNone(stored_job.mineru_raw_result_file_id)
        self.assertIsNone(stored_job.document_ir_file_id)
        self.assertEqual([file.file_type for file in job_files], ["source_pdf"])
        self.assertEqual(runtime.document_job_execution_service.fake_mineru_client.download_calls, [])
        self.assertEqual(events[-1].payload["mineru_state"], "running")

    def test_document_job_worker_classifies_timeout_mineru_render_and_oss_failures(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                p0_document_job_timeout_seconds=1,
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
            runtime.document_job_repository.update_document_job(
                job_id,
                timeout_at=utc_now() - timedelta(seconds=1),
            )
            timed_out = runtime.document_job_execution_service.execute_job(job_id, trace_id="trace_timeout")

        self.assertEqual(timed_out.status, "failed")
        self.assertEqual(timed_out.error_code, "document_job_timeout")
        self.assertEqual(timed_out.failed_stage, "uploaded")

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.fake_mineru_client.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                mineru_failed_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )

        self.assertEqual(mineru_failed_response.status_code, 201)
        mineru_failed_job = mineru_failed_response.json()["job"]
        self.assertEqual(mineru_failed_job["status"], "failed")
        self.assertEqual(mineru_failed_job["failed_stage"], "parsing")
        self.assertEqual(mineru_failed_job["error_code"], "mineru_failed")

        class BrokenRenderer:
            def render_to_bytes(self, *args, **kwargs):
                raise RuntimeError("render boom")

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.word_renderer = BrokenRenderer()
            app = create_app(runtime)
            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                render_failed_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                render_failed_job_id = render_failed_response.json()["job_id"]
            render_failed_events = runtime.document_job_event_repository.list_document_job_events(render_failed_job_id)

        render_failed_job = render_failed_response.json()["job"]
        self.assertEqual(render_failed_job["status"], "failed")
        self.assertEqual(render_failed_job["failed_stage"], "rendering")
        self.assertEqual(render_failed_job["error_code"], "render_failed")
        render_failed_event = render_failed_events[-1]
        self.assertEqual(render_failed_event.event_type, "stage_failed")
        self.assertEqual(render_failed_event.stage, "rendering")
        self.assertEqual(render_failed_event.level, "error")
        self.assertEqual(render_failed_event.payload["error_code"], "render_failed")

        class UnexpectedRendererError(Exception):
            pass

        class UnexpectedRenderer:
            def render_to_bytes(self, *args, **kwargs):
                raise UnexpectedRendererError("unexpected render boom")

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.word_renderer = UnexpectedRenderer()
            app = create_app(runtime)
            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                unexpected_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                unexpected_job_id = unexpected_response.json()["job_id"]
            unexpected_events = runtime.document_job_event_repository.list_document_job_events(unexpected_job_id)

        unexpected_job = unexpected_response.json()["job"]
        self.assertEqual(unexpected_job["status"], "failed")
        self.assertEqual(unexpected_job["failed_stage"], "rendering")
        self.assertEqual(unexpected_job["error_code"], "document_job_unexpected_error")
        unexpected_event = unexpected_events[-1]
        self.assertEqual(unexpected_event.event_type, "stage_failed")
        self.assertEqual(unexpected_event.level, "error")
        self.assertEqual(unexpected_event.payload["error_code"], "document_job_unexpected_error")

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            original_register = runtime.file_upload_service.register_generated_content

            def broken_register_generated_content(**kwargs):
                if kwargs["file_type"] == "generated_word":
                    raise RuntimeError("oss boom")
                return original_register(**kwargs)

            runtime.file_upload_service.register_generated_content = broken_register_generated_content
            app = create_app(runtime)
            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                oss_failed_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )

        oss_failed_job = oss_failed_response.json()["job"]
        self.assertEqual(oss_failed_job["status"], "failed")
        self.assertEqual(oss_failed_job["failed_stage"], "uploading")
        self.assertEqual(oss_failed_job["error_code"], "oss_failed")

    def test_document_job_retry_requeues_failed_job_and_writes_audit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.fake_mineru_client.raise_error = True
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                runtime.document_job_execution_service.fake_mineru_client.raise_error = False
                retry_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/retry",
                    headers={**headers, "X-Trace-Id": "trace_docjob_retry"},
                    json={"reason": "rerun after mineru"},
                )
                retry_again_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/retry",
                    headers=headers,
                    json={"reason": "already done"},
                )

            events = runtime.document_job_event_repository.list_document_job_events(job_id)
            audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "failed")
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.json()["status"], "succeeded")
        self.assertEqual(retry_response.json()["retry_count"], 1)
        self.assertEqual(retry_again_response.status_code, 409)
        self.assertIn("failed", retry_again_response.json()["detail"])
        retry_events = [event for event in events if event.event_type == "retry_requested"]
        self.assertEqual(len(retry_events), 1)
        self.assertEqual(retry_events[0].payload["reason"], "rerun after mineru")
        retry_audit_events = [event for event in audit_events if event.action == "document_job.retry"]
        self.assertEqual(len(retry_audit_events), 1)
        self.assertEqual(retry_audit_events[0].target_id, job_id)
        self.assertEqual(retry_audit_events[0].reason, "rerun after mineru")
        self.assertIn("auth.login", [event.action for event in audit_events])
        self.assertIn("file.upload_authorize", [event.action for event in audit_events])
        self.assertIn("file.upload_content", [event.action for event in audit_events])
        self.assertIn("document_job.create", [event.action for event in audit_events])

    def test_document_job_retry_rejects_retry_count_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                document_jobs_worker_backend="eager",
                p0_document_job_max_retries=1,
            )
            runtime.document_job_execution_service.fake_mineru_client.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                headers = build_auth_header(client)
                source_file = self._upload_source_pdf(client, headers)
                create_response = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                job_id = create_response.json()["job_id"]
                runtime.document_job_repository.update_document_job(job_id, retry_count=1)
                retry_response = client.post(
                    f"/api/v1/document-jobs/{job_id}/retry",
                    headers=headers,
                    json={"reason": "too many"},
                )

        self.assertEqual(retry_response.status_code, 409)
        self.assertIn("上限", retry_response.json()["detail"])

    def test_document_job_rejects_missing_token_pending_file_and_reused_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            pdf_content = make_pdf_bytes(page_count=1)

            with TestClient(app) as client:
                headers = build_auth_header(client)
                authorize_response = client.post(
                    "/api/v1/files/upload-url",
                    headers=headers,
                    json={
                        "filename": "source.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(pdf_content),
                    },
                )
                pending_file_id = authorize_response.json()["file_id"]
                missing_token = client.post(
                    "/api/v1/document-jobs",
                    json={"source_file_id": pending_file_id},
                )
                pending_file = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": pending_file_id},
                )
                source_file = self._upload_source_pdf(client, headers, filename="ready.pdf")
                first_create = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )
                reused_file = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"]},
                )

        self.assertEqual(authorize_response.status_code, 201)
        self.assertEqual(missing_token.status_code, 401)
        self.assertEqual(missing_token.json()["error_code"], "unauthorized")
        self.assertEqual(pending_file.status_code, 409)
        self.assertEqual(pending_file.json()["error_code"], "conflict")
        self.assertEqual(first_create.status_code, 201)
        self.assertEqual(reused_file.status_code, 409)
        self.assertEqual(reused_file.json()["error_code"], "conflict")

    def test_document_job_operator_scope_and_admin_visibility(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_multi_operator_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                other_operator_headers = build_auth_header(client, username="operator2", password="operator2-pass")
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                other_source_file = self._upload_source_pdf(client, other_operator_headers)
                other_job = client.post(
                    "/api/v1/document-jobs",
                    headers=other_operator_headers,
                    json={"source_file_id": other_source_file["id"]},
                ).json()
                forbidden_detail = client.get(
                    f"/api/v1/document-jobs/{other_job['job_id']}",
                    headers=operator_headers,
                )
                forbidden_files = client.get(
                    f"/api/v1/document-jobs/{other_job['job_id']}/files",
                    headers=operator_headers,
                )
                operator_list = client.get("/api/v1/document-jobs", headers=operator_headers)
                admin_detail = client.get(
                    f"/api/v1/document-jobs/{other_job['job_id']}",
                    headers=admin_headers,
                )
                admin_files = client.get(
                    f"/api/v1/document-jobs/{other_job['job_id']}/files",
                    headers=admin_headers,
                )
                admin_list = client.get("/api/v1/document-jobs", headers=admin_headers)

        self.assertEqual(forbidden_detail.status_code, 403)
        self.assertEqual(forbidden_detail.json()["error_code"], "forbidden")
        self.assertEqual(forbidden_files.status_code, 403)
        self.assertEqual(forbidden_files.json()["error_code"], "forbidden")
        self.assertEqual(operator_list.status_code, 200)
        self.assertEqual(operator_list.json()["total"], 0)
        self.assertEqual(admin_detail.status_code, 200)
        self.assertEqual(admin_detail.json()["created_by"], "user_operator_2")
        self.assertEqual(admin_files.status_code, 200)
        self.assertEqual([file["file_type"] for file in admin_files.json()["files"]], ["source_pdf"])
        self.assertEqual(admin_list.status_code, 200)
        self.assertEqual(admin_list.json()["total"], 1)

    def _upload_source_pdf(
        self,
        client: TestClient,
        headers: dict[str, str],
        *,
        filename: str = "source.pdf",
        pdf_content: bytes | None = None,
    ) -> dict:
        content = pdf_content or make_pdf_bytes(page_count=1)
        authorize_response = client.post(
            "/api/v1/files/upload-url",
            headers=headers,
            json={
                "filename": filename,
                "mime_type": "application/pdf",
                "size_bytes": len(content),
            },
        )
        if authorize_response.status_code != 201:
            raise AssertionError(authorize_response.json())
        upload_path = authorize_response.json()["upload_url"].replace("http://testserver", "")
        upload_response = client.put(
            upload_path,
            headers={**headers, "Content-Type": "application/pdf"},
            content=content,
        )
        if upload_response.status_code != 201:
            raise AssertionError(upload_response.json())
        return upload_response.json()["file"]

    def _create_document_job_from_upload(
        self,
        client: TestClient,
        headers: dict[str, str],
        *,
        filename: str,
    ) -> str:
        """上传源 PDF 并创建一个 document_job，返回任务 ID。"""

        source_file = self._upload_source_pdf(client, headers, filename=filename)
        response = client.post(
            "/api/v1/document-jobs",
            headers=headers,
            json={"source_file_id": source_file["id"]},
        )
        if response.status_code != 201:
            raise AssertionError(response.json())
        return response.json()["job_id"]

    def _seed_expired_document_file(self, runtime: AppRuntime, *, file_id: str) -> DocumentFileRecord:
        """创建一个已过 expires_at 的 document_file，并写入对应本地对象内容。"""

        now = utc_now()
        record = DocumentFileRecord(
            id=file_id,
            tenant_id="tenant_default",
            company_id="company_default",
            job_id="docjob_retention",
            file_type="generated_word",
            storage_provider="local_object",
            bucket="local-object",
            object_key=f"document-jobs/tenant_default/docjob_retention/generated_word/{file_id}.docx",
            original_filename=f"{file_id}.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=len(b"expired-file-content"),
            status="uploaded",
            expires_at=now - timedelta(seconds=1),
            created_by="user_operator",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        )
        runtime.document_file_repository.create_document_file(record)
        object_path = runtime.file_upload_service.resolve_local_object_path(record.object_key)
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(b"expired-file-content")
        return record

    def test_templates_read_api_returns_default_template_and_bound_configs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                list_response = client.get("/api/v1/templates")
                self.assertEqual(list_response.status_code, 200)
                items = list_response.json()["items"]
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["id"], "default")
                self.assertTrue(items[0]["is_default"])
                self.assertTrue(items[0]["template"]["exists"])
                self.assertTrue(items[0]["layout_config"]["exists"])
                self.assertTrue(items[0]["subscript_config"]["exists"])

                detail_response = client.get("/api/v1/templates/default")
                self.assertEqual(detail_response.status_code, 200)
                detail = detail_response.json()
                self.assertEqual(detail["id"], "default")
                self.assertEqual(detail["template"]["file_name"], "datasheet_template.docx")
                self.assertIsNotNone(detail["template"]["sha256"])
                self.assertEqual(detail["layout_config"]["file_name"], "datasheet_template.yaml")
                self.assertEqual(detail["subscript_config"]["file_name"], "runtime_subscripts_dictionary.yaml")

    def test_template_download_returns_docx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                response = client.get("/api/v1/templates/default/download")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            response.headers["content-type"],
        )
        self.assertGreater(len(response.content), 0)


    def test_templates_crud_replace_and_versions_preserve_uploaded_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = temp_root / "templates_manifest.yaml"
            repo_root = Path(__file__).resolve().parents[1]
            write_templates_manifest(
                manifest_path,
                [
                    {
                        "id": "default",
                        "name": "Default Template",
                        "description": "default",
                        "enabled": True,
                        "is_default_seed": True,
                        "template_path": str((repo_root / "resources" / "templates" / "default" / "datasheet_template.docx").resolve()),
                        "layout_config_path": str((repo_root / "resources" / "template_configs" / "datasheet_template.yaml").resolve()),
                    }
                ],
            )
            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                templates_manifest_path=str(manifest_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/templates",
                    data={
                        "template_id": "managed",
                        "name": "Managed Template",
                        "description": "created by api",
                    },
                    files={
                        "template": (
                            "managed.docx",
                            b"managed-template-v1",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(create_response.status_code, 201)
                self.assertEqual(create_response.json()["version"], 1)

                update_response = client.patch(
                    "/api/v1/templates/managed",
                    json={"name": "Managed Template Updated"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(update_response.status_code, 200)
                self.assertEqual(update_response.json()["name"], "Managed Template Updated")

                replace_response = client.put(
                    "/api/v1/templates/managed/file",
                    files={
                        "template": (
                            "managed-v2.docx",
                            b"managed-template-v2",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(replace_response.status_code, 200)
                self.assertEqual(replace_response.json()["version"], 2)

                download_response = client.get("/api/v1/templates/managed/download")
                versions_response = client.get(
                    "/api/v1/templates/managed/versions",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                delete_response = client.delete(
                    "/api/v1/templates/managed",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                missing_response = client.get("/api/v1/templates/managed")

        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.content, b"managed-template-v2")
        self.assertEqual(versions_response.status_code, 200)
        self.assertEqual([item["version"] for item in versions_response.json()["items"]], [2, 1])
        self.assertTrue(versions_response.json()["items"][0]["is_current"])
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.json()["deleted"])
        self.assertEqual(missing_response.status_code, 404)

    def test_template_profile_versioning_publishes_defaults_and_disables_versions(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = temp_root / "templates_manifest.yaml"
            repo_root = Path(__file__).resolve().parents[1]
            write_templates_manifest(
                manifest_path,
                [
                    {
                        "id": "default",
                        "name": "Default Template",
                        "description": "default",
                        "enabled": True,
                        "is_default_seed": True,
                        "template_path": str((repo_root / "resources" / "templates" / "default" / "datasheet_template.docx").resolve()),
                        "layout_config_path": str((repo_root / "resources" / "template_configs" / "datasheet_template.yaml").resolve()),
                    }
                ],
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                templates_manifest_path=str(manifest_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/templates",
                    data={
                        "template_id": "managed",
                        "name": "Managed Template",
                        "description": "created by api",
                        "render_policy_json": '{"page_size": "A4"}',
                    },
                    files={
                        "template": (
                            "managed.docx",
                            b"managed-template-v1",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(create_response.status_code, 201)

                create_template_verification_job(
                    runtime,
                    job_id="docjob_template_v1",
                    template_version_id="managed@1",
                )
                publish_v1_response = client.post(
                    "/api/v1/templates/managed/versions/1/publish",
                    json={
                        "make_default": True,
                        "publish_reason": "initial template verification",
                        "verification_job_id": "docjob_template_v1",
                        "verification_note": "v1 validation succeeded",
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(publish_v1_response.status_code, 200)
                self.assertEqual(publish_v1_response.json()["status"], "published")
                self.assertTrue(publish_v1_response.json()["is_default"])
                self.assertEqual(publish_v1_response.json()["verification_job_id"], "docjob_template_v1")
                self.assertEqual(publish_v1_response.json()["publish_reason"], "initial template verification")

                create_v2_response = client.post(
                    "/api/v1/templates/managed/versions",
                    data={"render_policy_json": '{"density": "compact"}'},
                    files={
                        "template": (
                            "managed-v2.docx",
                            b"managed-template-v2",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(create_v2_response.status_code, 201)
                self.assertEqual(create_v2_response.json()["version"], 2)
                self.assertEqual(create_v2_response.json()["status"], "draft")

                invalid_publish_v2_response = client.post(
                    "/api/v1/templates/managed/versions/2/publish",
                    json={
                        "make_default": False,
                        "publish_reason": "missing verification evidence",
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                create_template_verification_job(
                    runtime,
                    job_id="docjob_template_v2_pending",
                    template_version_id="managed@2",
                    status="pending",
                )
                pending_job_publish_v2_response = client.post(
                    "/api/v1/templates/managed/versions/2/publish",
                    json={
                        "make_default": False,
                        "publish_reason": "pending validation should fail",
                        "verification_job_id": "docjob_template_v2_pending",
                        "verification_note": "v2 validation is not done",
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                create_template_verification_job(
                    runtime,
                    job_id="docjob_template_v2",
                    template_version_id="managed@2",
                )
                publish_v2_response = client.post(
                    "/api/v1/templates/managed/versions/2/publish",
                    json={
                        "make_default": False,
                        "publish_reason": "validated compact density",
                        "verification_job_id": "docjob_template_v2",
                        "verification_note": "v2 validation succeeded",
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                set_default_v2_response = client.post(
                    "/api/v1/templates/managed/versions/2/set-default",
                    json={"set_default_reason": "switch production to compact density"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                download_response = client.get("/api/v1/templates/managed/download")
                disable_v1_response = client.post(
                    "/api/v1/templates/managed/versions/1/disable",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                disable_v2_response = client.post(
                    "/api/v1/templates/managed/versions/2/disable",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                versions_response = client.get(
                    "/api/v1/templates/managed/versions",
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(invalid_publish_v2_response.status_code, 422)
        self.assertEqual(pending_job_publish_v2_response.status_code, 400)
        self.assertIn("succeeded", pending_job_publish_v2_response.json()["detail"])
        self.assertEqual(publish_v2_response.status_code, 200)
        self.assertEqual(set_default_v2_response.status_code, 200)
        self.assertTrue(set_default_v2_response.json()["is_default"])
        self.assertEqual(download_response.content, b"managed-template-v2")
        self.assertEqual(disable_v1_response.status_code, 200)
        self.assertEqual(disable_v1_response.json()["status"], "disabled")
        self.assertEqual(disable_v2_response.status_code, 400)

        versions = {item["version"]: item for item in versions_response.json()["items"]}
        self.assertEqual(versions[1]["status"], "disabled")
        self.assertEqual(versions[2]["status"], "published")
        self.assertTrue(versions[2]["is_default"])
        self.assertEqual(versions[2]["render_policy"], {"density": "compact"})
        self.assertEqual(versions[2]["verification_job_id"], "docjob_template_v2")
        self.assertEqual(versions[2]["verification_note"], "v2 validation succeeded")
        self.assertEqual(versions[2]["verified_by"], "admin")
        self.assertIsNotNone(versions[2]["verified_at"])
        self.assertEqual(versions[2]["publish_reason"], "validated compact density")

        records = {record.version: record for record in runtime.resource_version_service.repository.list_resource_versions("template", "managed")}
        default_record = runtime.resource_version_service.repository.get_default_resource_version("template", "managed")
        self.assertEqual(records["1"].status.value, "disabled")
        self.assertEqual(records["2"].status.value, "published")
        self.assertEqual(default_record.version, "2")
        self.assertEqual(records["2"].payload["render_policy"], {"density": "compact"})
        self.assertEqual(records["2"].payload["verification_job_id"], "docjob_template_v2")
        self.assertEqual(records["2"].payload["verification_note"], "v2 validation succeeded")
        self.assertEqual(records["2"].payload["verified_by"], "admin")
        self.assertIsNotNone(records["2"].payload["verified_at"])
        self.assertEqual(records["2"].payload["publish_reason"], "validated compact density")
        audit_events = runtime.audit_event_repository.list_audit_events()
        self.assertEqual(
            [event.action for event in audit_events],
            [
                "template.create",
                "template.publish",
                "template.version_create",
                "template.publish",
                "template.set_default",
                "template.disable",
            ],
        )
        self.assertEqual(audit_events[0].actor_role, "admin")
        self.assertEqual(audit_events[1].target_id, "managed@1")
        self.assertEqual(audit_events[1].reason, "initial template verification")
        self.assertEqual(audit_events[4].reason, "switch production to compact density")
        self.assertEqual(audit_events[-1].target_id, "managed@1")
        self.assertNotIn("term_rules", records["2"].payload)

    def test_template_layout_config_admin_creates_draft_version_without_mutating_source_yaml(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = temp_root / "templates_manifest.yaml"
            repo_root = Path(__file__).resolve().parents[1]
            source_layout_path = repo_root / "resources" / "template_configs" / "datasheet_template.yaml"
            original_source_text = source_layout_path.read_text(encoding="utf-8")
            write_templates_manifest(
                manifest_path,
                [
                    {
                        "id": "default",
                        "name": "Default Template",
                        "description": "default",
                        "enabled": True,
                        "is_default_seed": True,
                        "template_path": str((repo_root / "resources" / "templates" / "default" / "datasheet_template.docx").resolve()),
                        "layout_config_path": str(source_layout_path.resolve()),
                    }
                ],
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                templates_manifest_path=str(manifest_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                denied_read = client.get("/api/v1/templates/default/layout-config")
                denied_write = client.post(
                    "/api/v1/templates/default/layout-config/versions",
                    json={
                        "base_template_version_id": "default@1",
                        "expected_config_sha256": "sha256:" + "0" * 64,
                        "expected_active_template_version_id": "default@1",
                        "changes": {"normal": {"font_size": 11}},
                    },
                )
                read_response = client.get(
                    "/api/v1/templates/default/layout-config",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(read_response.status_code, 200)
                read_payload = read_response.json()
                create_response = client.post(
                    "/api/v1/templates/default/layout-config/versions",
                    json={
                        "base_template_version_id": read_payload["template_version_id"],
                        "expected_config_sha256": read_payload["config_sha256"],
                        "expected_active_template_version_id": read_payload["active_template_version_id"],
                        "changes": {"page_setup": {"top_margin": 1.7}, "normal": {"font_size": 11}},
                        "change_note": "调整页面与正文字号",
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                invalid_response = client.post(
                    "/api/v1/templates/default/layout-config/versions",
                    json={
                        "base_template_version_id": read_payload["template_version_id"],
                        "expected_config_sha256": read_payload["config_sha256"],
                        "expected_active_template_version_id": read_payload["active_template_version_id"],
                        "changes": {"sample_content": {"normal_text": "not supported"}},
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                readonly_meta_response = client.post(
                    "/api/v1/templates/default/layout-config/versions",
                    json={
                        "base_template_version_id": read_payload["template_version_id"],
                        "expected_config_sha256": read_payload["config_sha256"],
                        "expected_active_template_version_id": read_payload["active_template_version_id"],
                        "changes": {"page_setup": {"page_width_cm": 20}},
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                conflict_response = client.post(
                    "/api/v1/templates/default/layout-config/versions",
                    json={
                        "base_template_version_id": read_payload["template_version_id"],
                        "expected_config_sha256": "sha256:" + "0" * 64,
                        "expected_active_template_version_id": read_payload["active_template_version_id"],
                        "changes": {"normal": {"font_size": 12}},
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                unknown_word_style_response = client.post(
                    "/api/v1/templates/default/layout-config/versions",
                    json={
                        "base_template_version_id": read_payload["template_version_id"],
                        "expected_config_sha256": read_payload["config_sha256"],
                        "expected_active_template_version_id": read_payload["active_template_version_id"],
                        "changes": {"table_style": {"style_name": "Not A Real Table Style"}},
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                draft_read_response = client.get(
                    "/api/v1/templates/default/layout-config?version=2",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                create_template_verification_job(
                    runtime,
                    job_id="docjob_layout_config_v2",
                    template_version_id="default@2",
                )
                publish_response = client.post(
                    "/api/v1/templates/default/versions/2/publish",
                    json={
                        "make_default": False,
                        "publish_reason": "样式验证通过",
                        "verification_job_id": "docjob_layout_config_v2",
                        "verification_note": "真实 Word 样式检查通过",
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                set_default_response = client.post(
                    "/api/v1/templates/default/versions/2/set-default",
                    json={"set_default_reason": "启用已验证样式"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                active_read_response = client.get(
                    "/api/v1/templates/default/layout-config",
                    headers={"X-Admin-Token": "secret-admin"},
                )

            self.assertEqual(denied_read.status_code, 403)
            self.assertEqual(denied_write.status_code, 403)
            self.assertEqual(read_payload["meta"]["schema_version"], "template-config/v1")
            self.assertEqual(read_payload["meta"]["template_name"], "数据手册模板")
            self.assertNotIn("schema_version", read_payload["config"])
            self.assertNotIn("template_name", read_payload["config"])
            self.assertNotIn("output_filename", read_payload["config"])
            self.assertNotIn("sample_content", read_payload["config"])
            self.assertIn("normal_text", read_payload["preview_samples"])
            self.assertIn("page_setup", read_payload["field_schema"]["groups"])
            self.assertIn("top_margin", read_payload["field_schema"]["groups"]["page_setup"])
            self.assertTrue(read_payload["field_schema"]["groups"]["page_setup"]["page_width_cm"]["readonly"])
            self.assertTrue(read_payload["field_schema"]["meta"]["template_name"]["readonly"])
            self.assertFalse(Path(read_payload["source_path"]).is_absolute())
            self.assertEqual(create_response.status_code, 201)
            created_payload = create_response.json()
            self.assertEqual(created_payload["version"], 2)
            self.assertEqual(created_payload["status"], "draft")
            self.assertTrue(created_payload["layout_config"]["exists"])
            self.assertEqual(invalid_response.status_code, 422)
            self.assertIn("sample_content", invalid_response.json()["detail"]["message"])
            self.assertEqual(invalid_response.json()["detail"]["field_errors"][0]["path"], "sample_content")
            self.assertEqual(invalid_response.json()["detail"]["field_errors"][0]["code"], "unknown_group")
            self.assertEqual(readonly_meta_response.status_code, 422)
            self.assertIn("只读", readonly_meta_response.json()["detail"]["message"])
            self.assertEqual(readonly_meta_response.json()["detail"]["field_errors"][0]["path"], "page_setup.page_width_cm")
            self.assertEqual(conflict_response.status_code, 409)
            self.assertEqual(conflict_response.json()["detail"]["active_template_version_id"], "default@1")
            self.assertEqual(conflict_response.json()["detail"]["config_sha256"], read_payload["config_sha256"])
            self.assertEqual(unknown_word_style_response.status_code, 422)
            self.assertEqual(
                unknown_word_style_response.json()["detail"]["field_errors"][0],
                {
                    "path": "table_style.style_name",
                    "code": "unknown_word_style",
                    "message": "table_style.style_name 在模板文档中不存在: Not A Real Table Style",
                },
            )
            self.assertEqual(draft_read_response.status_code, 200)
            self.assertEqual(draft_read_response.json()["status"], "draft")
            self.assertFalse(draft_read_response.json()["is_default"])
            self.assertEqual(publish_response.status_code, 200)
            self.assertEqual(set_default_response.status_code, 200)
            self.assertEqual(active_read_response.status_code, 200)
            self.assertEqual(active_read_response.json()["template_version_id"], "default@2")
            self.assertEqual(active_read_response.json()["config"]["normal"]["font_size"], 11)
            self.assertEqual(source_layout_path.read_text(encoding="utf-8"), original_source_text)

            record = runtime.resource_version_service.repository.get_resource_version("template", "default", "2")
            self.assertIsNotNone(record)
            layout_path = Path(record.payload["layout_config_path"])
            self.assertEqual(runtime.template_read_service.resolve_template_version(None).layout_config_path, layout_path)
            self.assertTrue(layout_path.exists())
            written_config = yaml.safe_load(layout_path.read_text(encoding="utf-8"))
            self.assertEqual(written_config["schema_version"], "template-config/v1")
            self.assertEqual(written_config["template_name"], "数据手册模板")
            self.assertEqual(written_config["output_filename"], "datasheet_template.docx")
            self.assertEqual(written_config["page_setup"]["top_margin"], 1.7)
            self.assertEqual(written_config["normal"]["font_size"], 11)
            self.assertEqual(written_config["page_setup"]["page_width_cm"], 21.0)
            self.assertIn("sample_content", written_config)
            self.assertEqual(record.payload["layout_config_sha256"], f"sha256:{hashlib.sha256(layout_path.read_bytes()).hexdigest()}")
            self.assertTrue(Path(record.payload["docx_path"]).exists())
            audit_events = runtime.audit_event_repository.list_audit_events()
            self.assertEqual(
                [event.action for event in audit_events],
                ["template.layout_config_version_create", "template.publish", "template.set_default"],
            )
            self.assertEqual(audit_events[0].target_id, "default@2")

    def test_template_layout_config_database_failure_removes_staged_version_directory(self):
        """数据库拒绝创建 draft 时不得遗留可被误识别为版本的文件目录。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repo_root = Path(__file__).resolve().parents[1]
            manifest_path = temp_root / "templates_manifest.yaml"
            write_templates_manifest(
                manifest_path,
                [
                    {
                        "id": "default",
                        "name": "Default Template",
                        "description": "default",
                        "enabled": True,
                        "is_default_seed": True,
                        "template_path": str((repo_root / "resources/templates/default/datasheet_template.docx").resolve()),
                        "layout_config_path": str((repo_root / "resources/template_configs/datasheet_template.yaml").resolve()),
                    }
                ],
            )
            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=_FakeMysqlDatabase().connect,
                ),
                templates_manifest_path=str(manifest_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                read_payload = client.get(
                    "/api/v1/templates/default/layout-config",
                    headers={"X-Admin-Token": "secret-admin"},
                ).json()
                with patch.object(runtime.resource_version_service, "create_draft", side_effect=RuntimeError("db unavailable")):
                    response = client.post(
                        "/api/v1/templates/default/layout-config/versions",
                        json={
                            "base_template_version_id": read_payload["template_version_id"],
                            "expected_config_sha256": read_payload["config_sha256"],
                            "expected_active_template_version_id": read_payload["active_template_version_id"],
                            "changes": {"normal": {"font_size": 11}},
                        },
                        headers={"X-Admin-Token": "secret-admin"},
                    )

            self.assertEqual(response.status_code, 503)
            self.assertFalse((runtime.settings.templates_storage_dir / "default" / "v2").exists())
            self.assertIsNone(runtime.resource_version_service.repository.get_resource_version("template", "default", "2"))

    def test_template_versioning_endpoints_require_mysql_resource_service(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/templates/default/versions",
                    files={
                        "template": (
                            "default-v2.docx",
                            b"default-template-v2",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(response.status_code, 503)
        self.assertIn("JOBS_REPOSITORY_BACKEND=mysql", response.json()["detail"])

    def test_term_rule_set_versioning_draft_publish_default_and_rollback(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        yaml_v1 = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "    description: ''\n"
            "rules:\n"
            "  - source_term: VONE\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: ONE\n"
            "        render_type: subscript\n"
            "    apply_scope: both\n"
            "    case_sensitive: true\n"
            "    enabled: true\n"
            "    priority: 10\n"
            "    notes: ''\n"
        )
        yaml_v2 = yaml_v1.replace("VONE", "VTWO").replace("ONE", "TWO")

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            )
            original_runtime_yaml = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")
            app = create_app(runtime)
            with TestClient(app) as client:
                draft_response = client.put(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    json={"yaml_text": yaml_v1},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(draft_response.status_code, 200)
                self.assertEqual(draft_response.json()["rule_count"], 1)
                self.assertEqual(
                    runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8"),
                    original_runtime_yaml,
                )

                publish_v1_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/publish",
                    json={
                        "make_default": True,
                        "published_by": "tester",
                        "publish_reason": "first version",
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(publish_v1_response.status_code, 200)
                version_v1 = publish_v1_response.json()["version"]
                self.assertEqual(publish_v1_response.json()["status"], "published")
                self.assertTrue(publish_v1_response.json()["is_default"])
                self.assertIn("VONE", runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8"))

                draft_default_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/versions/draft/set-default",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(draft_default_response.status_code, 400)
                self.assertIn("published", draft_default_response.json()["detail"])
                default_after_draft_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(default_after_draft_response.json()["default_version"], version_v1)

                draft_v2_response = client.put(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    json={"yaml_text": yaml_v2},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(draft_v2_response.status_code, 200)
                self.assertIn("VTWO", draft_v2_response.json()["yaml_text"])
                self.assertNotIn("VTWO", runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8"))

                missing_reason_publish_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/publish",
                    json={"make_default": False},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                publish_v2_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/publish",
                    json={"make_default": False, "publish_reason": "second version"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(publish_v2_response.status_code, 200)
                version_v2 = publish_v2_response.json()["version"]
                self.assertFalse(publish_v2_response.json()["is_default"])
                self.assertNotEqual(version_v1, version_v2)
                self.assertNotIn("VTWO", runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8"))

                set_default_v2_response = client.post(
                    f"/api/v1/term-rule-sets/electronics-default/versions/{version_v2}/set-default",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(set_default_v2_response.status_code, 200)
                self.assertTrue(set_default_v2_response.json()["is_default"])
                self.assertIn("VTWO", runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8"))

                records_before_rollback = {
                    record.version: record.payload
                    for record in runtime.resource_version_service.repository.list_resource_versions("term_rule_set", "electronics-default")
                }
                rollback_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/rollback",
                    json={"version": version_v1},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                export_response = client.get("/api/v1/term-rules/export", headers={"X-Admin-Token": "secret-admin"})
                detail_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default",
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(rollback_response.status_code, 200)
        self.assertEqual(missing_reason_publish_response.status_code, 422)
        self.assertTrue(rollback_response.json()["is_default"])
        self.assertIn("VONE", export_response.json()["yaml_text"])
        self.assertNotIn("VTWO", export_response.json()["yaml_text"])
        records_after_rollback = {
            record.version: record.payload
            for record in runtime.resource_version_service.repository.list_resource_versions("term_rule_set", "electronics-default")
        }
        self.assertEqual(records_after_rollback[version_v1], records_before_rollback[version_v1])
        self.assertEqual(detail_response.status_code, 200)
        audit_events = runtime.audit_event_repository.list_audit_events()
        self.assertEqual(
            [event.action for event in audit_events],
            [
                "term_rule_set.publish",
                "term_rule_set.publish",
                "term_rule_set.set_default",
                "term_rule_set.rollback",
            ],
        )
        self.assertEqual(audit_events[0].reason, "first version")
        self.assertEqual(audit_events[-1].target_id, f"electronics-default@{version_v1}")
        self.assertEqual(detail_response.json()["default_version"], version_v1)
        self.assertEqual(len(detail_response.json()["versions"]), 3)

    def test_term_rule_set_publish_default_blocks_legacy_runtime_yaml_half_success(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        yaml_v2 = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VFAIL\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: FAIL\n"
            "        render_type: subscript\n"
            "    apply_scope: both\n"
            "    case_sensitive: true\n"
            "    enabled: true\n"
            "    priority: 10\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            )
            service = runtime.term_rule_set_version_service
            original_default = runtime.resource_version_service.repository.get_default_resource_version(
                "term_rule_set",
                "electronics-default",
            )
            original_runtime_yaml = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")

            def fail_sync(_record):
                raise ValueError("legacy runtime yaml write failed")

            service._sync_live_store = fail_sync
            app = create_app(runtime)
            with TestClient(app) as client:
                draft_response = client.put(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    json={"yaml_text": yaml_v2},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                publish_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/publish",
                    json={
                        "make_default": True,
                        "published_by": "tester",
                        "publish_reason": "should fail before default switch",
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                detail_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default",
                    headers={"X-Admin-Token": "secret-admin"},
                )

            default_after_failure = runtime.resource_version_service.repository.get_default_resource_version(
                "term_rule_set",
                "electronics-default",
            )
            runtime_yaml_after_failure = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")

        self.assertEqual(draft_response.status_code, 200)
        self.assertEqual(publish_response.status_code, 400)
        self.assertIn("默认版本切换失败", publish_response.json()["detail"])
        self.assertIsNotNone(original_default)
        self.assertIsNotNone(default_after_failure)
        self.assertEqual(default_after_failure.version, original_default.version)
        self.assertEqual(detail_response.json()["default_version"], original_default.version)
        self.assertEqual(runtime_yaml_after_failure, original_runtime_yaml)
        self.assertEqual(runtime.audit_event_repository.list_audit_events(), [])

    def test_term_rule_set_draft_rejects_invalid_yaml_without_mutating_draft(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                draft_before_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(draft_before_response.status_code, 200)

                invalid_response = client.put(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    json={"yaml_text": "schema_version: 2\ncategories: [bad]\nrules: []\n"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                draft_after_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.json()["detail"]["code"], "invalid_term_rule_set_draft")
        self.assertEqual(
            draft_after_response.json()["snapshot_hash"],
            draft_before_response.json()["snapshot_hash"],
        )

    def test_term_rule_set_draft_rule_crud_only_mutates_draft(self):
        """验证结构化 draft rule CRUD 不会提前刷新 live runtime YAML。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: OLD\n"
            "        render_type: subscript\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            original_runtime_yaml = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")
            app = create_app(runtime)
            with TestClient(app) as client:
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                list_before_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules?q=VOLD",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                existing_rule_id = list_before_response.json()["items"][0]["id"]
                get_before_response = client.get(
                    f"/api/v1/term-rule-sets/electronics-default/draft/rules/{existing_rule_id}",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                create_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={
                        "id": "rule_draft_vin",
                        "category_id": category_id,
                        "source_term": "VIN",
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "IN", "render_type": "subscript"},
                        ],
                        "apply_scope": "both",
                        "priority": 20,
                        "notes": "draft only",
                    },
                )
                runtime_yaml_after_create = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")
                duplicate_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={
                        "category_id": category_id,
                        "source_term": "VIN",
                        "segments": [{"segment_text": "VIN", "render_type": "plain"}],
                    },
                )
                patch_response = client.patch(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules/rule_draft_vin",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={
                        "enabled": False,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "IN2", "render_type": "subscript"},
                        ],
                        "notes": "disabled before publish",
                    },
                )
                disabled_list_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules?enabled=false&q=VIN",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                runtime_yaml_after_patch = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")
                delete_response = client.delete(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules/rule_draft_vin",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                missing_after_delete_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules/rule_draft_vin",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                runtime_yaml_after_delete = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")

        self.assertEqual(list_before_response.status_code, 200)
        self.assertEqual(list_before_response.json()["total"], 1)
        self.assertEqual(get_before_response.status_code, 200)
        self.assertEqual(get_before_response.json()["source_term"], "VOLD")
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["rule"]["source_term"], "VIN")
        self.assertEqual(create_response.json()["draft"]["rule_count"], 2)
        self.assertEqual(runtime_yaml_after_create, original_runtime_yaml)
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertIn("source_term", duplicate_response.json()["detail"])
        self.assertEqual(patch_response.status_code, 200)
        self.assertFalse(patch_response.json()["rule"]["enabled"])
        self.assertIn("IN2", patch_response.json()["rule"]["custom_html"])
        self.assertEqual(patch_response.json()["draft"]["enabled_rule_count"], 1)
        self.assertEqual(disabled_list_response.status_code, 200)
        self.assertEqual(disabled_list_response.json()["total"], 1)
        self.assertEqual(runtime_yaml_after_patch, original_runtime_yaml)
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.json()["removed"])
        self.assertEqual(delete_response.json()["draft"]["rule_count"], 1)
        self.assertEqual(missing_after_delete_response.status_code, 404)
        self.assertEqual(runtime_yaml_after_delete, original_runtime_yaml)

    def test_term_rule_set_draft_rule_mutations_reject_stale_snapshot_hash(self):
        """验证结构化 draft rule 写入可用 snapshot hash 防止覆盖较新的 draft。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                draft_before_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                stale_snapshot_hash = draft_before_response.json()["snapshot_hash"]
                create_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={
                        "id": "rule_snapshot_guard",
                        "expected_snapshot_hash": stale_snapshot_hash,
                        "category_id": category_id,
                        "source_term": "VSNAPSHOT",
                        "segments": [{"segment_text": "VSNAPSHOT", "render_type": "plain"}],
                    },
                )
                snapshot_after_create = create_response.json()["draft"]["snapshot_hash"]
                stale_update_response = client.patch(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules/rule_snapshot_guard",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={
                        "expected_snapshot_hash": stale_snapshot_hash,
                        "notes": "stale update",
                    },
                )
                current_update_response = client.patch(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules/rule_snapshot_guard",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={
                        "expected_snapshot_hash": snapshot_after_create,
                        "notes": "current update",
                    },
                )
                snapshot_after_update = current_update_response.json()["draft"]["snapshot_hash"]
                stale_delete_response = client.delete(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules/rule_snapshot_guard",
                    params={"expected_snapshot_hash": snapshot_after_create},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                current_delete_response = client.delete(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules/rule_snapshot_guard",
                    params={"expected_snapshot_hash": snapshot_after_update},
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(draft_before_response.status_code, 200)
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(stale_update_response.status_code, 409)
        self.assertEqual(stale_update_response.json()["detail"]["code"], "draft_snapshot_conflict")
        self.assertEqual(stale_update_response.json()["detail"]["expected_snapshot_hash"], stale_snapshot_hash)
        self.assertEqual(stale_update_response.json()["detail"]["actual_snapshot_hash"], snapshot_after_create)
        self.assertEqual(current_update_response.status_code, 200)
        self.assertEqual(stale_delete_response.status_code, 409)
        self.assertEqual(stale_delete_response.json()["detail"]["actual_snapshot_hash"], snapshot_after_update)
        self.assertEqual(current_delete_response.status_code, 200)
        self.assertTrue(current_delete_response.json()["removed"])

    def test_term_rule_set_draft_rule_crud_auth_backend_and_validation_errors(self):
        """覆盖 draft rule CRUD 的鉴权、后端开关和基础校验错误。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: OLD\n"
            "        render_type: subscript\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            file_runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            app = create_app(file_runtime)
            with TestClient(app) as client:
                file_list_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                file_create_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={
                        "category_id": "missing",
                        "source_term": "VFILE",
                        "segments": [{"segment_text": "VFILE", "render_type": "plain"}],
                    },
                )

        self.assertEqual(file_list_response.status_code, 503)
        self.assertEqual(file_create_response.status_code, 503)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                operator_create_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers=operator_headers,
                    json={
                        "category_id": category_id,
                        "source_term": "VOP",
                        "segments": [{"segment_text": "VOP", "render_type": "plain"}],
                    },
                )
                duplicate_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers=admin_headers,
                    json={
                        "category_id": category_id,
                        "source_term": "VOLD",
                        "segments": [{"segment_text": "VOLD", "render_type": "plain"}],
                    },
                )
                unknown_category_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers=admin_headers,
                    json={
                        "category_id": "missing_category",
                        "source_term": "VMISSING",
                        "segments": [{"segment_text": "VMISSING", "render_type": "plain"}],
                    },
                )
                empty_segments_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers=admin_headers,
                    json={
                        "category_id": category_id,
                        "source_term": "VEMPTY",
                        "segments": [],
                    },
                )
                invalid_render_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers=admin_headers,
                    json={
                        "category_id": category_id,
                        "source_term": "VBADRENDER",
                        "segments": [{"segment_text": "VBAD", "render_type": "bad"}],
                    },
                )
                invalid_scope_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers=admin_headers,
                    json={
                        "category_id": category_id,
                        "source_term": "VBADSCOPE",
                        "apply_scope": "bad",
                        "segments": [{"segment_text": "VBAD", "render_type": "plain"}],
                    },
                )

        self.assertEqual(operator_create_response.status_code, 403)
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertIn("source_term", duplicate_response.json()["detail"])
        self.assertEqual(unknown_category_response.status_code, 404)
        self.assertIn("分类不存在", unknown_category_response.json()["detail"])
        self.assertEqual(empty_segments_response.status_code, 400)
        self.assertIn("segments", empty_segments_response.json()["detail"])
        self.assertEqual(invalid_render_response.status_code, 400)
        self.assertIn("render_type", invalid_render_response.json()["detail"])
        self.assertEqual(invalid_scope_response.status_code, 400)
        self.assertIn("apply_scope", invalid_scope_response.json()["detail"])

    def test_term_rule_set_diff_preflight_reports_changes_and_allows_warning_publish(self):
        """验证 draft diff/preflight 能报告变更，并允许 warning-only 发布。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VKEEP\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: VKEEP\n"
            "        render_type: plain\n"
            "    enabled: true\n"
            "  - source_term: VUPDATE\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: VUPDATE\n"
            "        render_type: plain\n"
            "    enabled: true\n"
            "  - source_term: VDISABLE\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: VDISABLE\n"
            "        render_type: plain\n"
            "    enabled: true\n"
            "  - source_term: VREMOVE\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: VREMOVE\n"
            "        render_type: plain\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                default_version = client.get(
                    "/api/v1/term-rule-sets/electronics-default",
                    headers={"X-Admin-Token": "secret-admin"},
                ).json()["default_version"]
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                draft_rules = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules?page_size=20",
                    headers={"X-Admin-Token": "secret-admin"},
                ).json()["items"]
                rule_ids = {item["source_term"]: item["id"] for item in draft_rules}
                update_response = client.patch(
                    f"/api/v1/term-rule-sets/electronics-default/draft/rules/{rule_ids['VUPDATE']}",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={
                        "source_term": "VUPDATED",
                        "segments": [{"segment_text": "VUPDATED", "render_type": "plain"}],
                    },
                )
                disable_response = client.patch(
                    f"/api/v1/term-rule-sets/electronics-default/draft/rules/{rule_ids['VDISABLE']}",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={"enabled": False},
                )
                remove_response = client.delete(
                    f"/api/v1/term-rule-sets/electronics-default/draft/rules/{rule_ids['VREMOVE']}",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                add_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={
                        "id": "rule_added_vadd",
                        "category_id": category_id,
                        "source_term": "VADD",
                        "segments": [{"segment_text": "VADD", "render_type": "plain"}],
                    },
                )
                diff_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/diff?from=default",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                explicit_diff_response = client.get(
                    f"/api/v1/term-rule-sets/electronics-default/diff?from={default_version}&to=draft",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                include_unchanged_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/diff?include_unchanged=true",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                preflight_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/preflight",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                runtime_yaml_before_publish = runtime.settings.term_rules_runtime_yaml_file.read_text(
                    encoding="utf-8"
                )
                publish_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/publish",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={"make_default": False, "publish_reason": "warning-only diff publish"},
                )
                runtime_yaml_after_publish = runtime.settings.term_rules_runtime_yaml_file.read_text(
                    encoding="utf-8"
                )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(disable_response.status_code, 200)
        self.assertEqual(remove_response.status_code, 200)
        self.assertEqual(add_response.status_code, 201)
        self.assertEqual(diff_response.status_code, 200)
        self.assertEqual(
            diff_response.json()["summary"],
            {
                "added": 1,
                "updated": 1,
                "disabled": 1,
                "removed": 1,
                "unchanged": 1,
                "total": 5,
            },
        )
        self.assertEqual(explicit_diff_response.status_code, 200)
        self.assertEqual(explicit_diff_response.json()["summary"], diff_response.json()["summary"])
        self.assertEqual(len(diff_response.json()["items"]), 4)
        self.assertEqual(len(include_unchanged_response.json()["items"]), 5)
        updated_item = next(item for item in diff_response.json()["items"] if item["change_type"] == "updated")
        disabled_item = next(item for item in diff_response.json()["items"] if item["change_type"] == "disabled")
        removed_item = next(item for item in diff_response.json()["items"] if item["change_type"] == "removed")
        added_item = next(item for item in diff_response.json()["items"] if item["change_type"] == "added")
        self.assertIn("source_term", updated_item["changed_fields"])
        self.assertIn("segments", updated_item["changed_fields"])
        self.assertEqual(disabled_item["changed_fields"], ["enabled"])
        self.assertIsNone(removed_item["after"])
        self.assertEqual(removed_item["before"]["source_term"], "VREMOVE")
        self.assertIsNone(added_item["before"])
        self.assertEqual(added_item["after"]["source_term"], "VADD")
        self.assertEqual(preflight_response.status_code, 200)
        self.assertTrue(preflight_response.json()["valid"])
        self.assertFalse(preflight_response.json()["blocking"])
        warning_codes = {item["code"] for item in preflight_response.json()["warnings"]}
        self.assertIn("removed_rules", warning_codes)
        self.assertIn("disabled_rules", warning_codes)
        self.assertEqual(publish_response.status_code, 200)
        self.assertEqual(runtime_yaml_after_publish, runtime_yaml_before_publish)

    def test_term_rule_set_preflight_blocks_invalid_draft_publish(self):
        """验证 preflight blocking finding 会阻止发布且不产生新版本。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: VOLD\n"
            "        render_type: plain\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            file_runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            file_app = create_app(file_runtime)
            with TestClient(file_app) as client:
                file_diff_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/diff",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                file_preflight_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/preflight",
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(file_diff_response.status_code, 503)
        self.assertEqual(file_preflight_response.status_code, 503)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            service = runtime.term_rule_set_version_service
            store = service.get_draft_store("electronics-default")
            duplicate_rule = store.rules[0].model_copy(update={"id": "rule_duplicate_vold"})
            missing_category_rule = store.rules[0].model_copy(
                update={
                    "id": "rule_missing_category",
                    "source_term": "VMISSING",
                    "category_id": "missing_category",
                    "segments": [],
                }
            )
            invalid_store = store.model_copy(update={"rules": [*store.rules, duplicate_rule, missing_category_rule]})
            service.update_draft("electronics-default", invalid_store)
            versions_before_publish = {
                record.version: record.status.value
                for record in runtime.resource_version_service.repository.list_resource_versions(
                    "term_rule_set",
                    "electronics-default",
                )
            }
            runtime_yaml_before_publish = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")
            app = create_app(runtime)
            with TestClient(app) as client:
                preflight_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/preflight",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                publish_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/publish",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={"make_default": True, "publish_reason": "must be blocked"},
                )
            versions_after_publish = {
                record.version: record.status.value
                for record in runtime.resource_version_service.repository.list_resource_versions(
                    "term_rule_set",
                    "electronics-default",
                )
            }
            runtime_yaml_after_publish = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")

        self.assertEqual(preflight_response.status_code, 200)
        self.assertFalse(preflight_response.json()["valid"])
        self.assertTrue(preflight_response.json()["blocking"])
        error_codes = {item["code"] for item in preflight_response.json()["errors"]}
        self.assertIn("duplicate_source_term", error_codes)
        self.assertIn("missing_category", error_codes)
        self.assertIn("empty_segments", error_codes)
        self.assertEqual(publish_response.status_code, 400)
        self.assertEqual(publish_response.json()["detail"]["code"], "term_rule_set_preflight_failed")
        self.assertGreaterEqual(publish_response.json()["detail"]["report"]["summary"]["error_count"], 3)
        self.assertEqual(versions_after_publish, versions_before_publish)
        self.assertEqual(runtime_yaml_after_publish, runtime_yaml_before_publish)
        self.assertEqual(runtime.audit_event_repository.list_audit_events(), [])

    def test_term_rule_set_versioning_backend_requirements_and_legacy_write_guard(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        yaml_text = "schema_version: 2\ncategories: {}\nrules: []\n"

        with tempfile.TemporaryDirectory() as temp_dir:
            file_runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            app = create_app(file_runtime)
            with TestClient(app) as client:
                versioned_response = client.put(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    json={"yaml_text": yaml_text},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                legacy_response = client.post(
                    "/api/v1/term-rule-categories",
                    json={"id": "file_legacy", "code": "file_legacy", "name": "文件兼容"},
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(versioned_response.status_code, 503)
        self.assertEqual(legacy_response.status_code, 201)

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_mysql = _FakeMysqlDatabase()
            mysql_runtime = build_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            )
            app = create_app(mysql_runtime)
            with TestClient(app) as client:
                guarded_response = client.post(
                    "/api/v1/term-rule-categories",
                    json={"id": "mysql_legacy", "code": "mysql_legacy", "name": "MySQL 直写"},
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(guarded_response.status_code, 400)
        self.assertIn("/api/v1/term-rule-sets", guarded_response.json()["detail"])

    def test_term_rule_yaml_codec_preserves_custom_render_fields(self):
        """验证 v2.1 YAML 高级渲染字段导入导出后不退化为 segments 生成值。"""

        codec = TermRuleYamlCodec()
        yaml_text = (
            "schema_version: 2.1\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VADV\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: ADV\n"
            "        render_type: superscript\n"
            "    custom_markdown: 'V^ADV-custom^'\n"
            "    custom_html: '<span class=\"term\">V<sup>ADV-custom</sup></span>'\n"
            "    enabled: true\n"
        )

        store = codec.parse_yaml_text(yaml_text)
        exported = codec.dump_store(store)
        reparsed = codec.parse_yaml_text(exported)

        self.assertEqual(len(store.rules), 1)
        self.assertEqual(store.rules[0].custom_markdown, "V^ADV-custom^")
        self.assertEqual(store.rules[0].custom_html, '<span class="term">V<sup>ADV-custom</sup></span>')
        self.assertIn("custom_markdown: V^ADV-custom^", exported)
        self.assertIn("custom_html: <span class=\"term\">V<sup>ADV-custom</sup></span>", exported)
        self.assertEqual(reparsed.rules[0].custom_markdown, store.rules[0].custom_markdown)
        self.assertEqual(reparsed.rules[0].custom_html, store.rules[0].custom_html)

    def test_term_rule_set_import_export_api_reports_duplicates_and_exports_history(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        yaml_with_duplicate = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "    description: ''\n"
            "rules:\n"
            "  - source_term: VIN\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: IN\n"
            "        render_type: subscript\n"
            "    apply_scope: both\n"
            "    case_sensitive: true\n"
            "    enabled: true\n"
            "    priority: 10\n"
            "    notes: ''\n"
            "  - source_term: VIN\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: duplicate\n"
            "        render_type: plain\n"
            "    apply_scope: both\n"
            "    case_sensitive: true\n"
            "    enabled: true\n"
            "    priority: 20\n"
            "    notes: ''\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                reject_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/import",
                    json={"yaml_text": yaml_with_duplicate},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                import_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/import",
                    json={
                        "yaml_text": yaml_with_duplicate,
                        "dedupe": "keep_first",
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                publish_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/publish",
                    json={"make_default": False, "publish_reason": "publish imported yaml"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                version = publish_response.json()["version"]
                yaml_export_response = client.get(
                    f"/api/v1/term-rule-sets/electronics-default/export?version={version}",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                legacy_export_response = client.get(
                    f"/api/v1/term-rule-sets/electronics-default/export?version={version}&format=legacy_runtime",
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(reject_response.status_code, 400)
        self.assertEqual(reject_response.json()["detail"]["code"], "invalid_term_rule_set_import")
        self.assertEqual(import_response.status_code, 200)
        self.assertEqual(import_response.json()["version"], "draft")
        self.assertEqual(import_response.json()["import_report"]["duplicate_rules"], 1)
        self.assertEqual(import_response.json()["import_report"]["duplicates"][0]["source_term"], "VIN")
        self.assertEqual(publish_response.status_code, 200)
        self.assertEqual(yaml_export_response.status_code, 200)
        self.assertEqual(yaml_export_response.json()["manifest"]["version"], version)
        self.assertEqual(yaml_export_response.json()["manifest"]["format"], "term_rules_v2")
        self.assertEqual(yaml_export_response.json()["manifest"]["exported_by"], "admin")
        self.assertIn("source_term: VIN", yaml_export_response.json()["yaml_text"])
        self.assertEqual(legacy_export_response.status_code, 200)
        self.assertEqual(legacy_export_response.json()["manifest"]["format"], "legacy_runtime")
        self.assertIn("subscript_rules", legacy_export_response.json()["yaml_text"])
        audit_actions = [event.action for event in runtime.audit_event_repository.list_audit_events()]
        self.assertIn("term_rule_set.import", audit_actions)
        self.assertIn("term_rule_set.export", audit_actions)

    def test_term_rule_proposals_persist_and_approve_into_draft(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: OLD\n"
            "        render_type: subscript\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                create_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "create",
                        "source_term": "VIN",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "IN", "render_type": "subscript"},
                        ],
                        "reason": "VIN should render with IN as subscript",
                        "source_job_id": "docjob_source",
                        "source_file_id": "file_source",
                        "page_number": 3,
                        "context_before": "input voltage",
                        "context_after": "pin should render",
                        "observed_term_rule_set_id": "electronics-default",
                        "observed_term_rule_version": "seed",
                    },
                )
                proposal_id = create_response.json()["id"]
                my_list_response = client.get("/api/v1/term-rule-proposals", headers=operator_headers)
                forbidden_list_response = client.get(
                    "/api/v1/term-rule-proposals?scope=all",
                    headers=operator_headers,
                )
                operator_approve_response = client.post(
                    f"/api/v1/term-rule-proposals/{proposal_id}/approve",
                    headers=operator_headers,
                    json={"review_comment": "operator should not approve"},
                )
                approve_response = client.post(
                    f"/api/v1/term-rule-proposals/{proposal_id}/approve",
                    headers=admin_headers,
                    json={"review_comment": "approved for draft"},
                )
                approved_unpublished_before_publish_response = client.get(
                    "/api/v1/term-rule-proposals?scope=approved_unpublished",
                    headers=admin_headers,
                )
                refreshed_response = client.get(
                    f"/api/v1/term-rule-proposals/{proposal_id}",
                    headers=operator_headers,
                )
                runtime_yaml_text = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")
                draft_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )
                publish_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/publish",
                    headers=admin_headers,
                    json={"make_default": True, "publish_reason": "publish approved VIN proposal"},
                )
                approved_unpublished_after_publish_response = client.get(
                    "/api/v1/term-rule-proposals?scope=approved_unpublished",
                    headers=admin_headers,
                )
                published_proposal_response = client.get(
                    f"/api/v1/term-rule-proposals/{proposal_id}",
                    headers=operator_headers,
                )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "pending_review")
        self.assertEqual(create_response.json()["created_by"], "user_operator")
        self.assertEqual(create_response.json()["page_number"], 3)
        self.assertEqual(create_response.json()["context_before"], "input voltage")
        self.assertEqual(create_response.json()["context_after"], "pin should render")
        self.assertEqual(create_response.json()["observed_term_rule_set_id"], "electronics-default")
        self.assertEqual(create_response.json()["observed_term_rule_version"], "seed")
        self.assertEqual(my_list_response.status_code, 200)
        self.assertEqual(my_list_response.json()["total"], 1)
        self.assertEqual(forbidden_list_response.status_code, 403)
        self.assertEqual(operator_approve_response.status_code, 403)
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["status"], "approved")
        self.assertEqual(approve_response.json()["reviewed_by"], "user_admin")
        self.assertEqual(approve_response.json()["merged_term_rule_set_id"], "electronics-default")
        self.assertIsNotNone(approve_response.json()["merged_draft_snapshot_hash"])
        self.assertEqual(approved_unpublished_before_publish_response.status_code, 200)
        self.assertEqual(approved_unpublished_before_publish_response.json()["total"], 1)
        self.assertEqual(refreshed_response.json()["status"], "approved")
        self.assertIn("VIN", draft_response.json()["yaml_text"])
        self.assertEqual(publish_response.status_code, 200)
        self.assertEqual(approved_unpublished_after_publish_response.json()["total"], 0)
        self.assertEqual(
            published_proposal_response.json()["published_term_rule_set_version"],
            publish_response.json()["version"],
        )
        stored = runtime.term_rule_proposal_service.get_proposal(proposal_id)
        self.assertEqual(stored.status.value, "published")
        self.assertEqual(stored.created_by, "user_operator")
        self.assertEqual(stored.published_term_rule_set_version, publish_response.json()["version"])
        audit_events = runtime.audit_event_repository.list_audit_events()
        self.assertIn("term_rule_proposal.approve", [event.action for event in audit_events])

    def test_term_rule_proposal_admin_can_approve_and_publish_default_version(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules: []\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                create_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "create",
                        "source_term": "VFAST",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "FAST", "render_type": "subscript"},
                        ],
                        "reason": "missing term from job detail",
                        "source_job_id": "docjob_source",
                        "source_file_id": "file_source",
                    },
                )
                proposal_id = create_response.json()["id"]
                operator_publish_response = client.post(
                    f"/api/v1/term-rule-proposals/{proposal_id}/approve-and-publish",
                    headers=operator_headers,
                    json={"review_comment": "operator should not publish"},
                )
                publish_response = client.post(
                    f"/api/v1/term-rule-proposals/{proposal_id}/approve-and-publish",
                    headers=admin_headers,
                    json={
                        "review_comment": "approved and publish now",
                        "publish_reason": "publish urgent missing rule",
                    },
                )
                detail_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default",
                    headers=admin_headers,
                )
                refreshed_response = client.get(
                    f"/api/v1/term-rule-proposals/{proposal_id}",
                    headers=operator_headers,
                )
                runtime_yaml_text = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(operator_publish_response.status_code, 403)
        self.assertEqual(publish_response.status_code, 200)
        self.assertEqual(publish_response.json()["status"], "published")
        self.assertIsNotNone(publish_response.json()["published_term_rule_set_version"])
        self.assertEqual(
            publish_response.json()["published_term_rule_set_version"],
            detail_response.json()["default_version"],
        )
        self.assertEqual(refreshed_response.json()["published_term_rule_set_id"], "electronics-default")
        self.assertIn("VFAST", runtime_yaml_text)
        self.assertTrue(
            any(row["term_rule_set_id"] == "electronics-default" and row["source_term"] == "VFAST" for row in fake_mysql.term_rules.values())
        )
        audit_actions = [event.action for event in runtime.audit_event_repository.list_audit_events()]
        self.assertIn("term_rule_proposal.approve", audit_actions)
        self.assertIn("term_rule_set.publish", audit_actions)

    def test_term_rule_proposal_update_disable_snapshots_and_reject_reason(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: OLD\n"
            "        render_type: subscript\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                target_rule_id = client.get("/api/v1/term-rules?q=VOLD", headers=operator_headers).json()["items"][0]["id"]
                update_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "update",
                        "target_rule_id": target_rule_id,
                        "source_term": "VNEW",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "NEW", "render_type": "subscript"},
                        ],
                        "reason": "update VOLD display",
                    },
                )
                disable_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "disable",
                        "target_rule_id": target_rule_id,
                        "reason": "disable obsolete VOLD",
                    },
                )
                reject_without_reason_response = client.post(
                    f"/api/v1/term-rule-proposals/{disable_response.json()['id']}/reject",
                    headers=admin_headers,
                    json={"review_comment": ""},
                )
                reject_response = client.post(
                    f"/api/v1/term-rule-proposals/{disable_response.json()['id']}/reject",
                    headers=admin_headers,
                    json={"review_comment": "obsolete term should not change now"},
                )

        self.assertEqual(update_response.status_code, 201)
        self.assertEqual(update_response.json()["intent"], "update")
        self.assertEqual(update_response.json()["target_rule_id"], target_rule_id)
        self.assertEqual(update_response.json()["target_rule_snapshot"]["id"], target_rule_id)
        self.assertEqual(disable_response.status_code, 201)
        self.assertEqual(disable_response.json()["intent"], "disable")
        self.assertEqual(disable_response.json()["source_term"], "VOLD")
        self.assertEqual(disable_response.json()["target_rule_snapshot"]["id"], target_rule_id)
        self.assertEqual(reject_without_reason_response.status_code, 400)
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.json()["status"], "rejected")
        self.assertEqual(reject_response.json()["review_comment"], "obsolete term should not change now")

    def test_term_rule_proposal_update_conflict_keeps_pending_status(self):
        """验证目标规则已从 draft 消失时返回结构化冲突且 proposal 保持待审核。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: OLD\n"
            "        render_type: subscript\n"
            "    enabled: true\n"
        )
        changed_yaml = seed_yaml.replace("VOLD", "VCHANGED").replace("OLD", "CHANGED")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                target_rule_id = client.get("/api/v1/term-rules?q=VOLD", headers=operator_headers).json()["items"][0]["id"]
                create_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "update",
                        "target_rule_id": target_rule_id,
                        "source_term": "VNEW",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "NEW", "render_type": "subscript"},
                        ],
                        "reason": "update VOLD display",
                    },
                )
                proposal_id = create_response.json()["id"]
                draft_mutation_response = client.put(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    headers=admin_headers,
                    json={"yaml_text": changed_yaml},
                )
                draft_before_approve_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )
                approve_response = client.post(
                    f"/api/v1/term-rule-proposals/{proposal_id}/approve",
                    headers=admin_headers,
                    json={"review_comment": "try approve stale snapshot"},
                )
                draft_after_approve_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )
                refreshed_response = client.get(
                    f"/api/v1/term-rule-proposals/{proposal_id}",
                    headers=operator_headers,
                )

        self.assertEqual(create_response.status_code, 201)
        self.assertIsNotNone(create_response.json()["target_rule_snapshot"])
        self.assertEqual(draft_mutation_response.status_code, 200)
        self.assertEqual(approve_response.status_code, 409)
        detail = approve_response.json()["detail"]
        self.assertEqual(detail["code"], "term_rule_proposal_conflict")
        self.assertEqual(detail["message"], "proposal 与当前 draft 存在冲突，请重新核对后处理。")
        conflict = detail["conflicts"][0]
        self.assertEqual(conflict["type"], "missing_target_rule")
        self.assertEqual(conflict["proposal_id"], proposal_id)
        self.assertEqual(conflict["target_rule_id"], target_rule_id)
        self.assertEqual(conflict["source_term"], "VNEW")
        self.assertEqual(conflict["category_id"], category_id)
        self.assertIsNone(conflict["current_rule"])
        self.assertEqual(conflict["target_rule_snapshot"]["id"], target_rule_id)
        self.assertEqual(draft_before_approve_response.json()["snapshot_hash"], draft_after_approve_response.json()["snapshot_hash"])
        self.assertEqual(draft_before_approve_response.json()["yaml_text"], draft_after_approve_response.json()["yaml_text"])
        self.assertEqual(refreshed_response.json()["status"], "pending_review")

    def test_term_rule_proposal_stale_target_conflict_returns_current_rule(self):
        """验证目标规则仍存在但内容变化时返回 stale_target_rule 和当前规则。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: OLD\n"
            "        render_type: subscript\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                target_rule_id = client.get("/api/v1/term-rules?q=VOLD", headers=operator_headers).json()["items"][0]["id"]
                create_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "update",
                        "target_rule_id": target_rule_id,
                        "source_term": "VNEW",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "NEW", "render_type": "subscript"},
                        ],
                        "reason": "update VOLD display",
                    },
                )
                proposal_id = create_response.json()["id"]
                draft_patch_response = client.patch(
                    f"/api/v1/term-rule-sets/electronics-default/draft/rules/{target_rule_id}",
                    headers=admin_headers,
                    json={"notes": "admin direct edit before review"},
                )
                draft_before_approve_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )
                approve_response = client.post(
                    f"/api/v1/term-rule-proposals/{proposal_id}/approve",
                    headers=admin_headers,
                    json={"review_comment": "try approve stale snapshot"},
                )
                draft_after_approve_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )
                refreshed_response = client.get(
                    f"/api/v1/term-rule-proposals/{proposal_id}",
                    headers=operator_headers,
                )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(draft_patch_response.status_code, 200)
        self.assertEqual(draft_patch_response.json()["rule"]["id"], target_rule_id)
        self.assertEqual(approve_response.status_code, 409)
        detail = approve_response.json()["detail"]
        self.assertEqual(detail["code"], "term_rule_proposal_conflict")
        conflict = detail["conflicts"][0]
        self.assertEqual(conflict["type"], "stale_target_rule")
        self.assertEqual(conflict["proposal_id"], proposal_id)
        self.assertEqual(conflict["target_rule_id"], target_rule_id)
        self.assertEqual(conflict["current_rule"]["id"], target_rule_id)
        self.assertEqual(conflict["current_rule"]["notes"], "admin direct edit before review")
        self.assertEqual(conflict["target_rule_snapshot"]["id"], target_rule_id)
        self.assertEqual(draft_before_approve_response.json()["snapshot_hash"], draft_after_approve_response.json()["snapshot_hash"])
        self.assertEqual(refreshed_response.json()["status"], "pending_review")

    def test_term_rule_proposal_create_source_term_segments_conflict_keeps_draft(self):
        """验证 create proposal 遇到同名不同 segments 时返回结构化冲突且不改 draft。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: OLD\n"
            "        render_type: subscript\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                existing_rule = client.get("/api/v1/term-rules?q=VOLD", headers=operator_headers).json()["items"][0]
                create_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "create",
                        "source_term": "VOLD",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "VO", "render_type": "plain"},
                            {"segment_text": "LD", "render_type": "subscript"},
                        ],
                        "reason": "operator proposes conflicting VOLD rendering",
                    },
                )
                proposal_id = create_response.json()["id"]
                draft_before_approve_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )
                approve_response = client.post(
                    f"/api/v1/term-rule-proposals/{proposal_id}/approve",
                    headers=admin_headers,
                    json={"review_comment": "try conflicting create"},
                )
                draft_after_approve_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )
                refreshed_response = client.get(
                    f"/api/v1/term-rule-proposals/{proposal_id}",
                    headers=operator_headers,
                )

        self.assertEqual(create_response.status_code, 201)
        self.assertIsNone(create_response.json()["target_rule_snapshot"])
        self.assertEqual(approve_response.status_code, 409)
        detail = approve_response.json()["detail"]
        self.assertEqual(detail["code"], "term_rule_proposal_conflict")
        conflict = detail["conflicts"][0]
        self.assertEqual(conflict["type"], "source_term_segments_conflict")
        self.assertEqual(conflict["proposal_id"], proposal_id)
        self.assertEqual(conflict["target_rule_id"], existing_rule["id"])
        self.assertEqual(conflict["source_term"], "VOLD")
        self.assertEqual(conflict["current_rule"]["source_term"], "VOLD")
        self.assertIsNone(conflict["target_rule_snapshot"])
        self.assertEqual(conflict["metadata"]["proposed_segments"][0]["segment_text"], "VO")
        self.assertEqual(conflict["metadata"]["existing_segments"][0]["segment_text"], "V")
        self.assertEqual(draft_before_approve_response.json()["snapshot_hash"], draft_after_approve_response.json()["snapshot_hash"])
        self.assertEqual(refreshed_response.json()["status"], "pending_review")

    def test_term_rule_proposal_approve_and_publish_conflict_does_not_publish(self):
        """验证 approve-and-publish 在 approve 冲突时不发布规则集版本。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: OLD\n"
            "        render_type: subscript\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                target_rule_id = client.get("/api/v1/term-rules?q=VOLD", headers=operator_headers).json()["items"][0]["id"]
                detail_before_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default",
                    headers=admin_headers,
                )
                create_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "update",
                        "target_rule_id": target_rule_id,
                        "source_term": "VNEW",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "NEW", "render_type": "subscript"},
                        ],
                        "reason": "update VOLD display",
                    },
                )
                proposal_id = create_response.json()["id"]
                draft_patch_response = client.patch(
                    f"/api/v1/term-rule-sets/electronics-default/draft/rules/{target_rule_id}",
                    headers=admin_headers,
                    json={"notes": "admin direct edit before approve and publish"},
                )
                draft_before_publish_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )
                publish_response = client.post(
                    f"/api/v1/term-rule-proposals/{proposal_id}/approve-and-publish",
                    headers=admin_headers,
                    json={
                        "review_comment": "try stale approve and publish",
                        "publish_reason": "should not publish stale proposal",
                    },
                )
                draft_after_publish_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )
                detail_after_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default",
                    headers=admin_headers,
                )
                refreshed_response = client.get(
                    f"/api/v1/term-rule-proposals/{proposal_id}",
                    headers=operator_headers,
                )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(draft_patch_response.status_code, 200)
        self.assertEqual(publish_response.status_code, 409)
        detail = publish_response.json()["detail"]
        self.assertEqual(detail["code"], "term_rule_proposal_conflict")
        self.assertEqual(detail["conflicts"][0]["type"], "stale_target_rule")
        self.assertEqual(refreshed_response.json()["status"], "pending_review")
        self.assertIsNone(refreshed_response.json()["published_term_rule_set_version"])
        self.assertEqual(detail_before_response.json()["default_version"], detail_after_response.json()["default_version"])
        self.assertEqual(len(detail_before_response.json()["versions"]), len(detail_after_response.json()["versions"]))
        self.assertEqual(draft_before_publish_response.json()["snapshot_hash"], draft_after_publish_response.json()["snapshot_hash"])
        audit_actions = [event.action for event in runtime.audit_event_repository.list_audit_events()]
        self.assertNotIn("term_rule_proposal.approve_and_publish", audit_actions)
        self.assertNotIn("term_rule_set.publish", audit_actions)

    def test_term_rule_proposal_bulk_approve_partial_success_and_conflict(self):
        """验证批量 approve 支持部分成功，并保留结构化冲突且不改失败 proposal。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: OLD\n"
            "        render_type: subscript\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                target_rule_id = client.get("/api/v1/term-rules?q=VOLD", headers=operator_headers).json()["items"][0]["id"]
                create_ok_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "create",
                        "source_term": "VBULK",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "BULK", "render_type": "subscript"},
                        ],
                        "reason": "bulk approve success candidate",
                    },
                )
                create_conflict_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "update",
                        "target_rule_id": target_rule_id,
                        "source_term": "VNEW",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "NEW", "render_type": "subscript"},
                        ],
                        "reason": "bulk approve stale target candidate",
                    },
                )
                ok_proposal_id = create_ok_response.json()["id"]
                conflict_proposal_id = create_conflict_response.json()["id"]
                client.patch(
                    f"/api/v1/term-rule-sets/electronics-default/draft/rules/{target_rule_id}",
                    headers=admin_headers,
                    json={"notes": "admin direct edit before bulk approve"},
                )
                bulk_response = client.post(
                    "/api/v1/term-rule-proposals/bulk-approve",
                    headers=admin_headers,
                    json={
                        "proposal_ids": [ok_proposal_id, conflict_proposal_id],
                        "review_comment": "bulk approve review",
                    },
                )
                draft_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )

            ok_proposal = runtime.term_rule_proposal_service.get_proposal(ok_proposal_id)
            conflict_proposal = runtime.term_rule_proposal_service.get_proposal(conflict_proposal_id)

        self.assertEqual(create_ok_response.status_code, 201)
        self.assertEqual(create_conflict_response.status_code, 201)
        self.assertEqual(bulk_response.status_code, 200)
        payload = bulk_response.json()
        self.assertEqual(payload["action"], "approve")
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["succeeded"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertTrue(payload["items"][0]["ok"])
        self.assertEqual(payload["items"][0]["proposal"]["status"], "approved")
        self.assertFalse(payload["items"][1]["ok"])
        self.assertEqual(payload["items"][1]["proposal_id"], conflict_proposal_id)
        self.assertEqual(payload["items"][1]["status_code"], 409)
        self.assertEqual(payload["items"][1]["error_code"], "term_rule_proposal_conflict")
        self.assertEqual(payload["items"][1]["detail"]["code"], "term_rule_proposal_conflict")
        self.assertEqual(payload["items"][1]["detail"]["conflicts"][0]["type"], "stale_target_rule")
        self.assertEqual(ok_proposal.status.value, "approved")
        self.assertEqual(conflict_proposal.status.value, "pending_review")
        self.assertIn("VBULK", draft_response.json()["yaml_text"])
        self.assertNotIn("VNEW", draft_response.json()["yaml_text"])

    def test_term_rule_proposal_uses_draft_categories_when_legacy_store_diverges(self):
        """验证版本化模式下 proposal 使用 Term Rule Set draft 分类，不依赖 legacy store 同步。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VBASE\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: VBASE\n"
            "        render_type: plain\n"
            "    enabled: true\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            draft_store = runtime.term_rule_set_version_service.get_draft_store(DEFAULT_TERM_RULE_SET_ID)
            draft_category_id = draft_store.categories[0].id
            runtime.term_rule_service.repository.save(
                TermRulesStore(
                    categories=[
                        TermRuleCategoryRecord(
                            id="legacy_only_category",
                            code="legacy_only",
                            name="Legacy Only",
                        )
                    ],
                    rules=[],
                )
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                categories_response = client.get("/api/v1/term-rule-categories")
                category_id = categories_response.json()["items"][0]["id"]
                create_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "create",
                        "source_term": "VDRIFTFIX",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "DRIFTFIX", "render_type": "subscript"},
                        ],
                        "reason": "proposal should follow draft categories",
                    },
                )
                proposal_id = create_response.json()["id"]
                bulk_response = client.post(
                    "/api/v1/term-rule-proposals/bulk-approve",
                    headers=admin_headers,
                    json={
                        "proposal_ids": [proposal_id],
                        "review_comment": "approve draft category proposal",
                    },
                )
                draft_response = client.get(
                    "/api/v1/term-rule-sets/electronics-default/draft",
                    headers=admin_headers,
                )

            approved_proposal = runtime.term_rule_proposal_service.get_proposal(proposal_id)

        self.assertEqual(categories_response.status_code, 200)
        self.assertEqual(category_id, draft_category_id)
        self.assertNotEqual(category_id, "legacy_only_category")
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["category_id"], draft_category_id)
        self.assertEqual(bulk_response.status_code, 200)
        self.assertEqual(bulk_response.json()["succeeded"], 1)
        self.assertEqual(bulk_response.json()["failed"], 0)
        self.assertEqual(approved_proposal.status.value, "approved")
        self.assertIn("VDRIFTFIX", draft_response.json()["yaml_text"])

    def test_term_rule_proposal_bulk_reject_partial_success_preserves_failed_item(self):
        """验证批量 reject 支持部分成功，并且失败项不会被二次覆盖。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules: []\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules_seed.yaml"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                term_rules_seed_path=str(seed_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                category_id = client.get("/api/v1/term-rule-categories").json()["items"][0]["id"]
                create_pending_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "create",
                        "source_term": "VREJECT",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "REJECT", "render_type": "subscript"},
                        ],
                        "reason": "bulk reject success candidate",
                    },
                )
                create_failed_response = client.post(
                    "/api/v1/term-rule-proposals",
                    headers=operator_headers,
                    json={
                        "intent": "create",
                        "source_term": "VALREADY",
                        "category_id": category_id,
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "ALREADY", "render_type": "subscript"},
                        ],
                        "reason": "already rejected candidate",
                    },
                )
                pending_proposal_id = create_pending_response.json()["id"]
                failed_proposal_id = create_failed_response.json()["id"]
                pre_reject_response = client.post(
                    f"/api/v1/term-rule-proposals/{failed_proposal_id}/reject",
                    headers=admin_headers,
                    json={"review_comment": "pre rejected before bulk"},
                )
                bulk_response = client.post(
                    "/api/v1/term-rule-proposals/bulk-reject",
                    headers=admin_headers,
                    json={
                        "proposal_ids": [pending_proposal_id, failed_proposal_id],
                        "review_comment": "bulk reject review",
                    },
                )

            pending_proposal = runtime.term_rule_proposal_service.get_proposal(pending_proposal_id)
            failed_proposal = runtime.term_rule_proposal_service.get_proposal(failed_proposal_id)

        self.assertEqual(create_pending_response.status_code, 201)
        self.assertEqual(create_failed_response.status_code, 201)
        self.assertEqual(pre_reject_response.status_code, 200)
        self.assertEqual(bulk_response.status_code, 200)
        payload = bulk_response.json()
        self.assertEqual(payload["action"], "reject")
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["succeeded"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertTrue(payload["items"][0]["ok"])
        self.assertEqual(payload["items"][0]["proposal"]["status"], "rejected")
        self.assertFalse(payload["items"][1]["ok"])
        self.assertEqual(payload["items"][1]["proposal_id"], failed_proposal_id)
        self.assertEqual(payload["items"][1]["status_code"], 400)
        self.assertEqual(payload["items"][1]["error_code"], "invalid_request")
        self.assertIn("pending_review", payload["items"][1]["detail"])
        self.assertEqual(pending_proposal.status.value, "rejected")
        self.assertEqual(pending_proposal.review_comment, "bulk reject review")
        self.assertEqual(failed_proposal.status.value, "rejected")
        self.assertEqual(failed_proposal.review_comment, "pre rejected before bulk")

    def test_term_rule_categories_export_and_simulate_are_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                categories_response = client.get("/api/v1/term-rule-categories")
                self.assertEqual(categories_response.status_code, 200)
                self.assertGreater(len(categories_response.json()["items"]), 0)

                anonymous_rules_response = client.get("/api/v1/term-rules")
                self.assertEqual(anonymous_rules_response.status_code, 401)

                denied_export_response = client.get("/api/v1/term-rules/export", headers=headers)
                self.assertEqual(denied_export_response.status_code, 403)

                export_response = client.get("/api/v1/term-rules/export", headers=admin_headers)
                self.assertEqual(export_response.status_code, 200)
                self.assertIn("schema_version: 2", export_response.json()["yaml_text"])

                simulate_response = client.post(
                    "/api/v1/term-rules/simulate",
                    headers=headers,
                    json={"text": "VIN VOUT"},
                )
                self.assertEqual(simulate_response.status_code, 200)
                self.assertIn("V<sub>IN</sub>", simulate_response.json()["html_preview"])

    def test_term_rule_import_and_sync_files_use_admin_boundary_and_replace_live_store(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            app = create_app(runtime)
            payload = {
                "yaml_text": (
                    "schema_version: 2\n"
                    "categories:\n"
                    "  voltage_terms:\n"
                    "    name: 电压相关\n"
                    "    priority: 10\n"
                    "    enabled: true\n"
                    "    description: ''\n"
                    "rules:\n"
                    "  - source_term: VIN\n"
                    "    category: voltage_terms\n"
                    "    segments:\n"
                    "      - segment_text: V\n"
                    "        render_type: plain\n"
                    "      - segment_text: IN\n"
                    "        render_type: subscript\n"
                    "    apply_scope: both\n"
                    "    case_sensitive: true\n"
                    "    enabled: true\n"
                    "    priority: 10\n"
                    "    notes: ''\n"
                )
            }
            with TestClient(app) as client:
                validate_denied_response = client.post("/api/v1/term-rules/import/validate", json=payload)
                self.assertEqual(validate_denied_response.status_code, 403)

                validate_response = client.post(
                    "/api/v1/term-rules/import/validate",
                    json=payload,
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(validate_response.status_code, 200)
                self.assertTrue(validate_response.json()["valid"])

                denied_import = client.post("/api/v1/term-rules/import", json=payload)
                self.assertEqual(denied_import.status_code, 403)

                import_response = client.post(
                    "/api/v1/term-rules/import",
                    json=payload,
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(import_response.status_code, 200)
                self.assertEqual(import_response.json()["total"], 1)

                export_response = client.get("/api/v1/term-rules/export", headers={"X-Admin-Token": "secret-admin"})
                self.assertIn("source_term: VIN", export_response.json()["yaml_text"])

                sync_response = client.post(
                    "/api/v1/term-rules/sync-files",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(sync_response.status_code, 200)
                runtime_yaml_path = Path(sync_response.json()["runtime_yaml_path"])
                self.assertTrue(runtime_yaml_path.exists())
                self.assertIn("subscript_rules", runtime_yaml_path.read_text(encoding="utf-8"))

    def test_term_rule_category_and_rule_crud_refresh_runtime_yaml(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            app = create_app(runtime)
            with TestClient(app) as client:
                category_response = client.post(
                    "/api/v1/term-rule-categories",
                    json={
                        "id": "dynamic_category",
                        "code": "dynamic_terms",
                        "name": "动态术语",
                        "priority": 50,
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(category_response.status_code, 201)
                category = category_response.json()
                self.assertEqual(category["code"], "dynamic_terms")

                create_rule_response = client.post(
                    "/api/v1/term-rules",
                    json={
                        "id": "rule_dynamic_vtest",
                        "category_id": category["id"],
                        "source_term": "VTEST",
                        "segments": [
                            {"segment_text": "V", "render_type": "plain"},
                            {"segment_text": "TEST", "render_type": "subscript"},
                        ],
                        "apply_scope": "both",
                        "priority": 50,
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(create_rule_response.status_code, 201)
                self.assertEqual(create_rule_response.json()["source_term"], "VTEST")
                self.assertIn("VTEST", runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8"))

                patch_rule_response = client.patch(
                    "/api/v1/term-rules/rule_dynamic_vtest",
                    json={"enabled": False, "notes": "disabled in api"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(patch_rule_response.status_code, 200)
                self.assertFalse(patch_rule_response.json()["enabled"])

                delete_rule_response = client.delete(
                    "/api/v1/term-rules/rule_dynamic_vtest",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                delete_category_response = client.delete(
                    "/api/v1/term-rule-categories/dynamic_category",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                runtime_yaml_after_delete = runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")

        self.assertEqual(delete_rule_response.status_code, 200)
        self.assertTrue(delete_rule_response.json()["deleted"])
        self.assertEqual(delete_category_response.status_code, 200)
        self.assertTrue(delete_category_response.json()["deleted"])
        self.assertNotIn("VTEST", runtime_yaml_after_delete)











    def test_translation_term_set_version_service_draft_publish_default_rollback_and_archive(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n"
                "en2zh,DAC,数模转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            service = runtime.translation_term_set_version_service
            self.assertIsNotNone(service)

            draft = service.get_draft("translation-terms-en2zh")
            self.assertEqual(draft.version, "draft")
            self.assertEqual(draft.base_version, "v1")
            self.assertEqual([entry.source_term for entry in draft.entries], ["ADC", "DAC"])
            self.assertEqual(fake_mysql.translation_term_sets["translation-terms-en2zh"]["draft_version"], "draft")

            edited_entries = list(draft.entries) + [
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="High Speed ADC",
                    target_term="高速模数转换器",
                    version="draft",
                    priority=10,
                )
            ]
            edited_draft = service.update_draft("translation-terms-en2zh", edited_entries)
            publish_result = service.publish_draft(
                "translation-terms-en2zh",
                make_default=False,
                published_by="admin",
                release_note="add high speed adc",
            )
            published_version = publish_result.version.version
            set_after_publish = runtime.persistence_adapters.translation_term_repository.get_set("translation-terms-en2zh")

            self.assertRegex(published_version, r"^\d{8}-\d{6}-\d{3}$")
            self.assertIn("overlapping_source_term", [item.code for item in edited_draft.validation.warnings])
            self.assertIn("overlapping_source_term", [item.code for item in publish_result.validation.warnings])
            self.assertEqual(publish_result.version.status, "published")
            self.assertEqual(publish_result.version.published_by, "admin")
            self.assertEqual(publish_result.version.release_note, "add high speed adc")
            self.assertEqual(set_after_publish.default_version, "v1")
            self.assertIsNone(set_after_publish.draft_version)

            service.set_default_version("translation-terms-en2zh", published_version)
            set_after_default = runtime.persistence_adapters.translation_term_repository.get_set("translation-terms-en2zh")
            versions_before_rollback = runtime.persistence_adapters.translation_term_repository.list_versions("translation-terms-en2zh")
            service.rollback("translation-terms-en2zh", "v1")
            set_after_rollback = runtime.persistence_adapters.translation_term_repository.get_set("translation-terms-en2zh")
            versions_after_rollback = runtime.persistence_adapters.translation_term_repository.list_versions("translation-terms-en2zh")
            archived = service.archive("translation-terms-en2zh", published_version)

        self.assertEqual(set_after_default.default_version, published_version)
        self.assertEqual(set_after_rollback.default_version, "v1")
        self.assertEqual([item.version for item in versions_after_rollback], [item.version for item in versions_before_rollback])
        self.assertEqual(archived.status, "archived")
        with self.assertRaises(ValueError):
            service.set_default_version("translation-terms-en2zh", published_version)
        with self.assertRaises(ValueError):
            service.archive("translation-terms-en2zh", "v1")

    def test_translation_term_set_version_service_blocks_errors_and_reports_warnings(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            service = runtime.translation_term_set_version_service
            draft = service.get_draft("translation-terms-en2zh")

            duplicate_entries = list(draft.entries) + [
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term=" adc ",
                    target_term="重复项",
                    version="draft",
                )
            ]
            empty_target_entries = [
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="FPGA",
                    target_term=" ",
                    version="draft",
                )
            ]
            missing_change_report = service.validate_changes(
                list(draft.entries),
                [
                    TranslationTermProposalChangeRecord(
                        proposal_id="proposal_1",
                        seq=1,
                        action="update",
                        source_term="FPGA",
                        target_term="现场可编程门阵列",
                    ),
                    TranslationTermProposalChangeRecord(
                        proposal_id="proposal_1",
                        seq=2,
                        action="delete",
                        source_term="DSP",
                    ),
                ],
                observed_version="old-version",
                current_version="v1",
            )
            no_change_report = service.validate_changes(
                list(draft.entries),
                [
                    TranslationTermProposalChangeRecord(
                        proposal_id="proposal_2",
                        seq=1,
                        action="update",
                        source_term="ADC",
                        target_term="模数转换器",
                    ),
                ],
            )
            no_change_entry_report = service.validate_entries(list(draft.entries), base_entries=list(draft.entries))

        with self.assertRaises(ValueError):
            service.update_draft("translation-terms-en2zh", duplicate_entries)
        with self.assertRaises(ValueError):
            service.update_draft("translation-terms-en2zh", empty_target_entries)
        self.assertEqual(
            [item.code for item in missing_change_report.errors],
            ["update_missing_term", "delete_missing_term"],
        )
        self.assertEqual([item.code for item in missing_change_report.warnings], ["stale_observed_version"])
        self.assertEqual([item.code for item in no_change_report.warnings], ["no_actual_changes"])
        self.assertEqual([item.code for item in no_change_entry_report.warnings], ["no_actual_changes"])

    def test_translation_term_set_import_export_api_reports_duplicates_and_exports_manifest(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n",
                encoding="utf-8",
            )
            csv_with_duplicate = (
                "language_pair,source_term,target_term,version,case_sensitive,status,priority,domain,category,note\n"
                "en2zh,FPGA,现场可编程门阵列,draft,false,active,5,electronics,chip,first\n"
                "en2zh, fpga ,重复项,draft,false,active,9,electronics,chip,duplicate\n"
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                reject_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/import",
                    json={"csv_text": csv_with_duplicate},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                import_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/import",
                    json={
                        "csv_text": csv_with_duplicate,
                        "dedupe": "keep_first",
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                published = runtime.translation_term_set_version_service.publish_draft(
                    "translation-terms-en2zh",
                    make_default=False,
                    published_by="admin",
                    release_note="publish imported csv",
                )
                default_export_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/export",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                version_export_response = client.get(
                    f"/api/v1/translation-term-sets/translation-terms-en2zh/export?version={published.version.version}",
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(reject_response.status_code, 400)
        self.assertIn("重复 normalized_source_term", reject_response.json()["detail"])
        self.assertEqual(import_response.status_code, 200)
        self.assertEqual(import_response.json()["version"], "draft")
        self.assertEqual(import_response.json()["term_count"], 1)
        self.assertEqual(import_response.json()["import_report"]["duplicate_rows"], 1)
        self.assertEqual(import_response.json()["import_report"]["duplicates"][0]["normalized_source_term"], "fpga")
        self.assertEqual(default_export_response.status_code, 200)
        self.assertEqual(default_export_response.json()["manifest"]["version"], "v1")
        self.assertIn("ADC", default_export_response.json()["csv_text"])
        self.assertEqual(version_export_response.status_code, 200)
        self.assertEqual(version_export_response.json()["manifest"]["version"], published.version.version)
        self.assertEqual(version_export_response.json()["manifest"]["format"], "csv")
        self.assertEqual(version_export_response.json()["manifest"]["exported_by"], "admin")
        self.assertIn("FPGA", version_export_response.json()["csv_text"])
        self.assertNotIn("重复项", version_export_response.json()["csv_text"])
        audit_actions = [event.action for event in runtime.audit_event_repository.list_audit_events()]
        self.assertIn("translation_term_set.import", audit_actions)
        self.assertIn("translation_term_set.export", audit_actions)

    def test_translation_term_set_management_api_lists_draft_publishes_defaults_and_rolls_back(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n"
                "en2zh,DAC,数模转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                list_response = client.get("/api/v1/translation-term-sets", headers=operator_headers)
                detail_response = client.get("/api/v1/translation-term-sets/translation-terms-en2zh", headers=operator_headers)
                draft_response = client.get("/api/v1/translation-term-sets/translation-terms-en2zh/draft", headers=operator_headers)
                missing_response = client.get("/api/v1/translation-term-sets/missing-set", headers=operator_headers)
                operator_publish_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/publish",
                    headers=operator_headers,
                    json={"make_default": True, "release_note": "operator should not publish"},
                )
                import_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/import",
                    headers=admin_headers,
                    json={
                        "csv_text": (
                            "language_pair,source_term,target_term,version\n"
                            "en2zh,FPGA,现场可编程门阵列,draft\n"
                        )
                    },
                )
                publish_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/publish",
                    headers=admin_headers,
                    json={"make_default": False, "release_note": "add FPGA term"},
                )
                published_version = publish_response.json()["version"]
                set_default_response = client.post(
                    f"/api/v1/translation-term-sets/translation-terms-en2zh/versions/{published_version}/set-default",
                    headers=admin_headers,
                )
                draft_default_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/versions/draft/set-default",
                    headers=admin_headers,
                )
                rollback_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/rollback",
                    headers=admin_headers,
                    json={"version": "v1"},
                )
                final_detail_response = client.get("/api/v1/translation-term-sets/translation-terms-en2zh", headers=operator_headers)

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["items"][0]["set_id"], "translation-terms-en2zh")
        self.assertEqual(list_response.json()["items"][0]["language_pair"], "en2zh")
        self.assertEqual(list_response.json()["items"][0]["default_version"], "v1")
        self.assertEqual(list_response.json()["items"][0]["version_count"], 1)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["versions"][0]["term_count"], 2)
        self.assertTrue(detail_response.json()["versions"][0]["is_default"])
        self.assertEqual(draft_response.status_code, 200)
        self.assertEqual(draft_response.json()["base_version"], "v1")
        self.assertEqual(draft_response.json()["term_count"], 2)
        self.assertEqual([entry["source_term"] for entry in draft_response.json()["entries"]], ["ADC", "DAC"])
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(operator_publish_response.status_code, 403)
        self.assertEqual(import_response.status_code, 200)
        self.assertEqual(publish_response.status_code, 200)
        self.assertFalse(publish_response.json()["is_default"])
        self.assertEqual(publish_response.json()["published_by"], "user_admin")
        self.assertEqual(publish_response.json()["release_note"], "add FPGA term")
        self.assertEqual(set_default_response.status_code, 200)
        self.assertTrue(set_default_response.json()["is_default"])
        self.assertEqual(draft_default_response.status_code, 400)
        self.assertEqual(rollback_response.status_code, 200)
        self.assertEqual(rollback_response.json()["version"], "v1")
        self.assertTrue(rollback_response.json()["is_default"])
        self.assertEqual(final_detail_response.json()["default_version"], "v1")
        self.assertEqual(len(final_detail_response.json()["versions"]), 2)
        audit_actions = [event.action for event in runtime.audit_event_repository.list_audit_events()]
        self.assertIn("translation_term_set.publish", audit_actions)
        self.assertIn("translation_term_set.set_default", audit_actions)
        self.assertIn("translation_term_set.rollback", audit_actions)

    def test_translation_term_set_management_api_returns_503_without_mysql_service(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.get("/api/v1/translation-term-sets")

        self.assertEqual(response.status_code, 503)

    def test_translation_term_set_draft_changes_api_edits_draft_and_publishes(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n"
                "en2zh,DAC,数模转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                draft_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft",
                    headers=admin_headers,
                )
                operator_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft/changes",
                    headers=operator_headers,
                    json={
                        "expected_snapshot_hash": draft_response.json()["snapshot_hash"],
                        "changes": [
                            {
                                "action": "add",
                                "source_term": "FPGA",
                                "target_term": "现场可编程门阵列",
                            }
                        ],
                    },
                )
                changes_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft/changes",
                    headers=admin_headers,
                    json={
                        "expected_snapshot_hash": draft_response.json()["snapshot_hash"],
                        "reason": "row CRUD smoke",
                        "changes": [
                            {
                                "action": "add",
                                "source_term": "FPGA",
                                "target_term": "现场可编程门阵列",
                                "priority": 5,
                                "domain": "electronics",
                            },
                            {
                                "action": "add",
                                "source_term": "TMP",
                                "target_term": "临时术语",
                            },
                            {
                                "action": "update",
                                "source_term": "TMP",
                                "status": "disabled",
                                "note": "disabled from row CRUD",
                            },
                            {
                                "action": "update",
                                "source_term": "ADC",
                                "target_term": "模拟数字转换器",
                                "note": "admin correction",
                            },
                            {
                                "action": "delete",
                                "source_term": "DAC",
                            },
                        ],
                    },
                )
                diff_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/diff",
                    headers=admin_headers,
                )
                preflight_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/preflight",
                    headers=admin_headers,
                )
                publish_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/publish",
                    headers=admin_headers,
                    json={"make_default": False, "release_note": "publish row CRUD draft"},
                )
                export_response = client.get(
                    f"/api/v1/translation-term-sets/translation-terms-en2zh/export?version={publish_response.json()['version']}",
                    headers=admin_headers,
                )

        self.assertEqual(operator_response.status_code, 403)
        self.assertEqual(changes_response.status_code, 200)
        changed_payload = changes_response.json()
        self.assertEqual(changed_payload["term_count"], 3)
        entries_by_key = {entry["normalized_source_term"]: entry for entry in changed_payload["entries"]}
        self.assertEqual(entries_by_key["adc"]["target_term"], "模拟数字转换器")
        self.assertEqual(entries_by_key["adc"]["source_term"], "ADC")
        self.assertEqual(entries_by_key["fpga"]["priority"], 5)
        self.assertEqual(entries_by_key["tmp"]["status"], "disabled")
        self.assertNotIn("dac", entries_by_key)
        self.assertEqual(diff_response.status_code, 200)
        self.assertEqual(diff_response.json()["summary"]["added"], 2)
        self.assertEqual(diff_response.json()["summary"]["changed"], 1)
        self.assertEqual(diff_response.json()["summary"]["removed"], 1)
        self.assertEqual(preflight_response.status_code, 200)
        self.assertFalse(preflight_response.json()["publish_blocked"])
        self.assertEqual(publish_response.status_code, 200)
        self.assertFalse(publish_response.json()["is_default"])
        self.assertEqual(export_response.status_code, 200)
        self.assertIn("FPGA", export_response.json()["csv_text"])
        self.assertIn("disabled", export_response.json()["csv_text"])
        self.assertNotIn("DAC", export_response.json()["csv_text"])
        audit_actions = [event.action for event in runtime.audit_event_repository.list_audit_events()]
        self.assertIn("translation_term_set.draft_change", audit_actions)
        self.assertIn("translation_term_set.publish", audit_actions)

    def test_translation_term_set_draft_changes_api_preserves_error_boundaries(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                draft_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft",
                    headers=admin_headers,
                )
                snapshot_hash = draft_response.json()["snapshot_hash"]
                stale_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft/changes",
                    headers=admin_headers,
                    json={
                        "expected_snapshot_hash": "sha256:stale",
                        "changes": [
                            {
                                "action": "add",
                                "source_term": "FPGA",
                                "target_term": "现场可编程门阵列",
                            }
                        ],
                    },
                )
                duplicate_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft/changes",
                    headers=admin_headers,
                    json={
                        "expected_snapshot_hash": snapshot_hash,
                        "changes": [
                            {
                                "action": "add",
                                "source_term": " adc ",
                                "target_term": "重复项",
                            }
                        ],
                    },
                )
                missing_update_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft/changes",
                    headers=admin_headers,
                    json={
                        "expected_snapshot_hash": snapshot_hash,
                        "changes": [
                            {
                                "action": "update",
                                "source_term": "FPGA",
                                "target_term": "现场可编程门阵列",
                            }
                        ],
                    },
                )
                invalid_status_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft/changes",
                    headers=admin_headers,
                    json={
                        "expected_snapshot_hash": snapshot_hash,
                        "changes": [
                            {
                                "action": "update",
                                "source_term": "ADC",
                                "status": "paused",
                            }
                        ],
                    },
                )
                empty_target_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft/changes",
                    headers=admin_headers,
                    json={
                        "expected_snapshot_hash": snapshot_hash,
                        "changes": [
                            {
                                "action": "add",
                                "source_term": "FPGA",
                                "target_term": " ",
                            }
                        ],
                    },
                )
                draft_after_errors = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft",
                    headers=admin_headers,
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            unavailable_runtime = build_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
            )
            unavailable_app = create_app(unavailable_runtime)
            with TestClient(unavailable_app) as client:
                unavailable_response = client.post(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/draft/changes",
                    headers={"X-Admin-Token": "secret-admin"},
                    json={
                        "expected_snapshot_hash": snapshot_hash,
                        "changes": [
                            {
                                "action": "add",
                                "source_term": "FPGA",
                                "target_term": "现场可编程门阵列",
                            }
                        ],
                    },
                )

        self.assertEqual(stale_response.status_code, 409)
        self.assertEqual(stale_response.json()["detail"]["code"], "draft_snapshot_conflict")
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertEqual(missing_update_response.status_code, 400)
        self.assertEqual(invalid_status_response.status_code, 400)
        self.assertEqual(empty_target_response.status_code, 400)
        self.assertEqual(unavailable_response.status_code, 503)
        self.assertEqual(draft_after_errors.json()["snapshot_hash"], snapshot_hash)
        self.assertEqual([entry["source_term"] for entry in draft_after_errors.json()["entries"]], ["ADC"])

    def test_translation_term_set_diff_and_preflight_reports_draft_changes(self):
        """验证 Admin 可读取 default-vs-draft diff 和发布前预检摘要。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n"
                "en2zh,DAC,数模转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            runtime.translation_term_set_version_service.update_draft(
                "translation-terms-en2zh",
                [
                    TranslationTermEntry(
                        language_pair="en2zh",
                        source_term="ADC",
                        target_term="模拟数字转换器",
                        version="draft",
                        note="operator correction",
                    ),
                    TranslationTermEntry(
                        language_pair="en2zh",
                        source_term="FPGA",
                        target_term="现场可编程门阵列",
                        version="draft",
                        priority=5,
                    ),
                ],
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                diff_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/diff",
                    headers=admin_headers,
                )
                preflight_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/preflight",
                    headers=admin_headers,
                )

        self.assertEqual(diff_response.status_code, 200)
        diff_payload = diff_response.json()
        self.assertEqual(diff_payload["base_version"], "v1")
        self.assertEqual(diff_payload["target_version"], "draft")
        self.assertEqual(
            diff_payload["summary"],
            {
                "added": 1,
                "removed": 1,
                "changed": 1,
                "unchanged": 0,
                "total_before": 2,
                "total_after": 2,
            },
        )
        diff_by_key = {item["normalized_source_term"]: item for item in diff_payload["items"]}
        self.assertEqual(diff_by_key["adc"]["kind"], "changed")
        self.assertIn("target_term", diff_by_key["adc"]["changed_fields"])
        self.assertIn("note", diff_by_key["adc"]["changed_fields"])
        self.assertEqual(diff_by_key["dac"]["kind"], "removed")
        self.assertEqual(diff_by_key["fpga"]["kind"], "added")
        self.assertEqual(preflight_response.status_code, 200)
        preflight_payload = preflight_response.json()
        self.assertFalse(preflight_payload["publish_blocked"])
        self.assertTrue(preflight_payload["validation"]["valid"])
        self.assertEqual(preflight_payload["diff_summary"]["changed"], 1)

    def test_translation_term_set_preflight_blocks_invalid_draft_and_preserves_error_boundaries(self):
        """验证 preflight 能报告阻断项，并保持 admin-only、404 和 503 边界。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            runtime.persistence_adapters.translation_term_repository.replace_version(
                "en2zh",
                "draft",
                [
                    TranslationTermEntry(
                        language_pair="en2zh",
                        source_term="BROKEN",
                        target_term=" ",
                        version="draft",
                    )
                ],
                "sha256:manual-invalid-draft",
                status="draft",
                set_draft=True,
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                forbidden_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/diff",
                    headers=operator_headers,
                )
                missing_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/diff?base_version=missing",
                    headers=admin_headers,
                )
                preflight_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/preflight",
                    headers=admin_headers,
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            unavailable_runtime = build_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
            )
            unavailable_app = create_app(unavailable_runtime)
            with TestClient(unavailable_app) as client:
                unavailable_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/diff",
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(forbidden_response.status_code, 403)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(unavailable_response.status_code, 503)
        self.assertEqual(preflight_response.status_code, 200)
        preflight_payload = preflight_response.json()
        self.assertTrue(preflight_payload["publish_blocked"])
        self.assertFalse(preflight_payload["validation"]["valid"])
        self.assertEqual(preflight_payload["validation"]["errors"][0]["code"], "empty_target_term")
        self.assertIn("target_term 不能为空", preflight_payload["blocking_reasons"][0])

    def test_translation_term_set_proposal_compatibility_preview_is_read_only(self):
        """验证 proposal compatibility preview 返回结构化冲突且不改变 proposal/draft。"""

        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n"
                "en2zh,DAC,数模转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                compatible_create_response = client.post(
                    "/api/v1/translation-term-proposals",
                    headers=operator_headers,
                    json={
                        "language_pair": "en2zh",
                        "observed_translation_term_version": "v1",
                        "changes": [
                            {
                                "action": "add",
                                "source_term": "FPGA",
                                "target_term": "现场可编程门阵列",
                            }
                        ],
                    },
                )
                conflict_create_response = client.post(
                    "/api/v1/translation-term-proposals",
                    headers=operator_headers,
                    json={
                        "language_pair": "en2zh",
                        "observed_translation_term_version": "v1",
                        "changes": [
                            {
                                "action": "update",
                                "source_term": "ADC",
                                "target_term": "模拟数字转换器",
                            }
                        ],
                    },
                )
                runtime.translation_term_set_version_service.update_draft(
                    "translation-terms-en2zh",
                    [
                        TranslationTermEntry(
                            language_pair="en2zh",
                            source_term="ADC",
                            target_term="另一个译文",
                            version="draft",
                        ),
                        TranslationTermEntry(
                            language_pair="en2zh",
                            source_term="DAC",
                            target_term="数模转换器",
                            version="draft",
                        ),
                    ],
                )
                preview_response = client.get(
                    "/api/v1/translation-term-sets/translation-terms-en2zh/proposal-compatibility",
                    headers=admin_headers,
                )
                compatible_after = client.get(
                    f"/api/v1/translation-term-proposals/{compatible_create_response.json()['id']}",
                    headers=operator_headers,
                )
                conflict_after = client.get(
                    f"/api/v1/translation-term-proposals/{conflict_create_response.json()['id']}",
                    headers=operator_headers,
                )
                draft_after = runtime.translation_term_set_version_service.get_draft("translation-terms-en2zh")

        self.assertEqual(preview_response.status_code, 200)
        preview_payload = preview_response.json()
        self.assertEqual(preview_payload["summary"]["total"], 2)
        self.assertEqual(preview_payload["summary"]["compatible"], 1)
        self.assertEqual(preview_payload["summary"]["conflict"], 1)
        preview_by_id = {item["proposal_id"]: item for item in preview_payload["items"]}
        compatible_item = preview_by_id[compatible_create_response.json()["id"]]
        conflict_item = preview_by_id[conflict_create_response.json()["id"]]
        self.assertEqual(compatible_item["compatibility"], "compatible")
        self.assertEqual(conflict_item["compatibility"], "conflict")
        self.assertEqual(conflict_item["conflicts"][0]["code"], "stale_target_term")
        self.assertEqual(conflict_item["conflicts"][0]["normalized_source_term"], "adc")
        self.assertEqual(compatible_after.json()["status"], "pending")
        self.assertEqual(conflict_after.json()["status"], "pending")
        self.assertEqual({entry.source_term for entry in draft_after.entries}, {"ADC", "DAC"})

    def test_translation_term_proposals_approve_batch_changes_into_draft_and_reject(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n"
                "en2zh,DAC,数模转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                create_response = client.post(
                    "/api/v1/translation-term-proposals",
                    headers=operator_headers,
                    json={
                        "language_pair": "en2zh",
                        "source_job_id": "docjob_source",
                        "source_file_id": "file_source",
                        "observed_translation_term_version": "v1",
                        "changes": [
                            {
                                "action": "add",
                                "source_term": "FPGA",
                                "target_term": "现场可编程门阵列",
                                "priority": 5,
                                "domain": "electronics",
                            },
                            {
                                "action": "update",
                                "source_term": "ADC",
                                "target_term": "模拟数字转换器",
                                "note": "operator correction",
                            },
                        ],
                    },
                )
                proposal_id = create_response.json()["id"]
                my_list_response = client.get("/api/v1/translation-term-proposals", headers=operator_headers)
                forbidden_list_response = client.get(
                    "/api/v1/translation-term-proposals?scope=all",
                    headers=operator_headers,
                )
                operator_approve_response = client.post(
                    f"/api/v1/translation-term-proposals/{proposal_id}/approve",
                    headers=operator_headers,
                    json={"review_note": "operator should not approve"},
                )
                approve_response = client.post(
                    f"/api/v1/translation-term-proposals/{proposal_id}/approve",
                    headers=admin_headers,
                    json={"review_note": "approved for draft"},
                )
                reject_create_response = client.post(
                    "/api/v1/translation-term-proposals",
                    headers=operator_headers,
                    json={
                        "language_pair": "en2zh",
                        "changes": [
                            {
                                "action": "delete",
                                "source_term": "DAC",
                            }
                        ],
                    },
                )
                reject_without_note_response = client.post(
                    f"/api/v1/translation-term-proposals/{reject_create_response.json()['id']}/reject",
                    headers=admin_headers,
                    json={"review_note": ""},
                )
                reject_response = client.post(
                    f"/api/v1/translation-term-proposals/{reject_create_response.json()['id']}/reject",
                    headers=admin_headers,
                    json={"review_note": "keep DAC for now"},
                )
                draft = runtime.translation_term_set_version_service.get_draft("translation-terms-en2zh")

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "pending")
        self.assertEqual(create_response.json()["submitted_by"], "user_operator")
        self.assertEqual(create_response.json()["source_job_id"], "docjob_source")
        self.assertEqual(create_response.json()["source_file_id"], "file_source")
        self.assertEqual(create_response.json()["observed_translation_term_set_id"], "translation-terms-en2zh")
        self.assertEqual(create_response.json()["observed_translation_term_version"], "v1")
        self.assertEqual([item["action"] for item in create_response.json()["changes"]], ["add", "update"])
        self.assertEqual(my_list_response.status_code, 200)
        self.assertEqual(my_list_response.json()["total"], 1)
        self.assertEqual(forbidden_list_response.status_code, 403)
        self.assertEqual(operator_approve_response.status_code, 403)
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["status"], "approved")
        self.assertEqual(approve_response.json()["reviewed_by"], "user_admin")
        draft_by_source = {entry.source_term: entry for entry in draft.entries}
        self.assertEqual(draft_by_source["ADC"].target_term, "模拟数字转换器")
        self.assertEqual(draft_by_source["FPGA"].target_term, "现场可编程门阵列")
        self.assertEqual(reject_without_note_response.status_code, 400)
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.json()["status"], "rejected")
        audit_actions = [event.action for event in runtime.audit_event_repository.list_audit_events()]
        self.assertIn("translation_term_proposal.create", audit_actions)
        self.assertIn("translation_term_proposal.approve", audit_actions)
        self.assertIn("translation_term_proposal.reject", audit_actions)
        self.assertIn("translation_term_set.draft_update", audit_actions)

    def test_translation_term_proposal_bulk_approve_partial_success_and_conflict(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n"
                "en2zh,DAC,数模转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                ok_create_response = client.post(
                    "/api/v1/translation-term-proposals",
                    headers=operator_headers,
                    json={
                        "language_pair": "en2zh",
                        "observed_translation_term_version": "v1",
                        "changes": [
                            {
                                "action": "add",
                                "source_term": "FPGA",
                                "target_term": "现场可编程门阵列",
                            }
                        ],
                    },
                )
                conflict_create_response = client.post(
                    "/api/v1/translation-term-proposals",
                    headers=operator_headers,
                    json={
                        "language_pair": "en2zh",
                        "observed_translation_term_version": "v1",
                        "changes": [
                            {
                                "action": "update",
                                "source_term": "ADC",
                                "target_term": "模拟数字转换器",
                            }
                        ],
                    },
                )
                runtime.translation_term_set_version_service.update_draft(
                    "translation-terms-en2zh",
                    [
                        TranslationTermEntry(
                            language_pair="en2zh",
                            source_term="ADC",
                            target_term="另一个译文",
                            version="draft",
                        ),
                        TranslationTermEntry(
                            language_pair="en2zh",
                            source_term="DAC",
                            target_term="数模转换器",
                            version="draft",
                        ),
                    ],
                )
                bulk_response = client.post(
                    "/api/v1/translation-term-proposals/bulk-approve",
                    headers=admin_headers,
                    json={
                        "proposal_ids": [
                            ok_create_response.json()["id"],
                            conflict_create_response.json()["id"],
                        ],
                        "review_note": "bulk approve smoke",
                    },
                )
                conflict_after_response = client.get(
                    f"/api/v1/translation-term-proposals/{conflict_create_response.json()['id']}",
                    headers=operator_headers,
                )
                draft = runtime.translation_term_set_version_service.get_draft("translation-terms-en2zh")

        self.assertEqual(ok_create_response.status_code, 201)
        self.assertEqual(conflict_create_response.status_code, 201)
        self.assertEqual(bulk_response.status_code, 200)
        payload = bulk_response.json()
        self.assertEqual(payload["action"], "approve")
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["succeeded"], 1)
        self.assertEqual(payload["failed"], 1)
        items_by_id = {item["proposal_id"]: item for item in payload["items"]}
        ok_item = items_by_id[ok_create_response.json()["id"]]
        conflict_item = items_by_id[conflict_create_response.json()["id"]]
        self.assertTrue(ok_item["ok"])
        self.assertEqual(ok_item["proposal"]["status"], "approved")
        self.assertFalse(conflict_item["ok"])
        self.assertEqual(conflict_item["status_code"], 409)
        self.assertEqual(conflict_item["error_code"], "translation_term_proposal_conflict")
        self.assertEqual(conflict_item["detail"]["code"], "translation_term_proposal_conflict")
        self.assertEqual(conflict_item["detail"]["conflicts"][0]["code"], "stale_target_term")
        self.assertEqual(conflict_item["detail"]["conflicts"][0]["normalized_source_term"], "adc")
        self.assertEqual(conflict_after_response.json()["status"], "pending")
        draft_by_source = {entry.source_term: entry for entry in draft.entries}
        self.assertEqual(draft_by_source["FPGA"].target_term, "现场可编程门阵列")
        self.assertEqual(draft_by_source["ADC"].target_term, "另一个译文")

    def test_translation_term_proposal_bulk_reject_partial_success_preserves_failed_item(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n"
                "en2zh,DAC,数模转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                reject_create_response = client.post(
                    "/api/v1/translation-term-proposals",
                    headers=operator_headers,
                    json={
                        "language_pair": "en2zh",
                        "changes": [
                            {
                                "action": "delete",
                                "source_term": "DAC",
                            }
                        ],
                    },
                )
                approved_create_response = client.post(
                    "/api/v1/translation-term-proposals",
                    headers=operator_headers,
                    json={
                        "language_pair": "en2zh",
                        "changes": [
                            {
                                "action": "add",
                                "source_term": "FPGA",
                                "target_term": "现场可编程门阵列",
                            }
                        ],
                    },
                )
                approve_response = client.post(
                    f"/api/v1/translation-term-proposals/{approved_create_response.json()['id']}/approve",
                    headers=admin_headers,
                    json={"review_note": "prepare non-pending item"},
                )
                bulk_response = client.post(
                    "/api/v1/translation-term-proposals/bulk-reject",
                    headers=admin_headers,
                    json={
                        "proposal_ids": [
                            reject_create_response.json()["id"],
                            approved_create_response.json()["id"],
                        ],
                        "review_note": "bulk reject smoke",
                    },
                )
                failed_after_response = client.get(
                    f"/api/v1/translation-term-proposals/{approved_create_response.json()['id']}",
                    headers=operator_headers,
                )

        self.assertEqual(reject_create_response.status_code, 201)
        self.assertEqual(approved_create_response.status_code, 201)
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(bulk_response.status_code, 200)
        payload = bulk_response.json()
        self.assertEqual(payload["action"], "reject")
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["succeeded"], 1)
        self.assertEqual(payload["failed"], 1)
        items_by_id = {item["proposal_id"]: item for item in payload["items"]}
        rejected_item = items_by_id[reject_create_response.json()["id"]]
        failed_item = items_by_id[approved_create_response.json()["id"]]
        self.assertTrue(rejected_item["ok"])
        self.assertEqual(rejected_item["proposal"]["status"], "rejected")
        self.assertFalse(failed_item["ok"])
        self.assertEqual(failed_item["status_code"], 400)
        self.assertEqual(failed_item["error_code"], "invalid_request")
        self.assertIn("只有 pending proposal 可以审核", failed_item["detail"])
        self.assertEqual(failed_after_response.json()["status"], "approved")

    def test_translation_term_proposal_approve_and_publish_sets_default_and_conflict_blocks_merge(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            terms_path = temp_root / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,ADC,模数转换器,v1\n",
                encoding="utf-8",
            )
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                temp_root,
                jobs_repository_backend="mysql",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
                translation_terms_path=str(terms_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                operator_headers = build_auth_header(client)
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                publish_create_response = client.post(
                    "/api/v1/translation-term-proposals",
                    headers=operator_headers,
                    json={
                        "language_pair": "en2zh",
                        "changes": [
                            {
                                "action": "add",
                                "source_term": "FPGA",
                                "target_term": "现场可编程门阵列",
                            }
                        ],
                    },
                )
                proposal_id = publish_create_response.json()["id"]
                operator_publish_response = client.post(
                    f"/api/v1/translation-term-proposals/{proposal_id}/approve-and-publish",
                    headers=operator_headers,
                    json={"review_note": "operator should not publish"},
                )
                publish_response = client.post(
                    f"/api/v1/translation-term-proposals/{proposal_id}/approve-and-publish",
                    headers=admin_headers,
                    json={
                        "review_note": "approved and publish now",
                        "release_note": "add FPGA term",
                    },
                )
                stale_create_response = client.post(
                    "/api/v1/translation-term-proposals",
                    headers=operator_headers,
                    json={
                        "language_pair": "en2zh",
                        "observed_translation_term_version": "v1",
                        "changes": [
                            {
                                "action": "update",
                                "source_term": "ADC",
                                "target_term": "模拟数字转换器",
                            }
                        ],
                    },
                )
                draft = runtime.translation_term_set_version_service.get_draft("translation-terms-en2zh")
                runtime.translation_term_set_version_service.update_draft(
                    "translation-terms-en2zh",
                    [
                        TranslationTermEntry(
                            language_pair="en2zh",
                            source_term="ADC",
                            target_term="另一个译文",
                            version="draft",
                        )
                    ],
                )
                conflict_response = client.post(
                    f"/api/v1/translation-term-proposals/{stale_create_response.json()['id']}/approve",
                    headers=admin_headers,
                    json={"review_note": "try stale update"},
                )
                refreshed_conflict_response = client.get(
                    f"/api/v1/translation-term-proposals/{stale_create_response.json()['id']}",
                    headers=operator_headers,
                )
                term_set = runtime.persistence_adapters.translation_term_repository.get_set("translation-terms-en2zh")

        self.assertEqual(publish_create_response.status_code, 201)
        self.assertEqual(operator_publish_response.status_code, 403)
        self.assertEqual(publish_response.status_code, 200)
        self.assertEqual(publish_response.json()["status"], "published")
        self.assertEqual(publish_response.json()["published_translation_term_set_id"], "translation-terms-en2zh")
        self.assertIsNotNone(publish_response.json()["published_translation_term_version"])
        self.assertEqual(term_set.default_version, publish_response.json()["published_translation_term_version"])
        self.assertIn("FPGA", [row["source_term"] for row in fake_mysql.translation_terms.values()])
        self.assertEqual(stale_create_response.status_code, 201)
        self.assertEqual(conflict_response.status_code, 409)
        self.assertEqual(conflict_response.json()["detail"]["code"], "translation_term_proposal_conflict")
        self.assertIn("已被其他变更修改", conflict_response.json()["detail"]["conflicts"][0]["message"])
        self.assertEqual(conflict_response.json()["detail"]["conflicts"][0]["code"], "stale_target_term")
        self.assertEqual(refreshed_conflict_response.json()["status"], "pending")
        audit_actions = [event.action for event in runtime.audit_event_repository.list_audit_events()]
        self.assertIn("translation_term_proposal.approve_and_publish", audit_actions)
        self.assertIn("translation_term_set.publish", audit_actions)



    def test_translation_profile_rollback_writes_audit_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(Path(temp_dir), admin_token="secret-admin")
            publish_translation_profile_resource_version(
                runtime,
                version="1",
                model="profile-model-v1",
                make_default=True,
            )
            publish_translation_profile_resource_version(
                runtime,
                version="2",
                model="profile-model-v2",
                make_default=True,
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/translation-profiles/electronics-en2zh/rollback",
                    json={"version": "1"},
                    headers={"X-Admin-Token": "secret-admin"},
                )

        self.assertEqual(response.status_code, 200)
        audit_events = runtime.audit_event_repository.list_audit_events()
        self.assertEqual([event.action for event in audit_events], ["translation_profile.rollback"])
        self.assertEqual(audit_events[0].target_id, "electronics-en2zh@1")
        self.assertEqual(audit_events[0].actor_role, "admin")




























    def test_callback_rejects_non_parsing_job_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            app = create_app(runtime)
            job = JobRecord(
                id="job_completed_callback",
                source_filename="done.zip",
                status="completed",
                progress=100,
                result_ready=True,
                source_kind="source_pdf",
                source_pdf_context=SourcePdfJobContext(
                    batch_id="batch_completed",
                    data_id="job_completed_callback",
                ),
                completed_at=utc_now(),
            )
            runtime.job_repository.create_job(job)
            with TestClient(app) as client:
                payload, _content = build_callback_payload(
                    batch_id="batch_completed",
                    data_id="job_completed_callback",
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)

            self.assertEqual(response.status_code, 400)
            self.assertIn("不允许处理 MinerU callback", response.json()["detail"])
            self.assertEqual(runtime.stage_message_store.list_replayable_stage_messages(), [])

    def test_find_job_for_callback_reads_nested_source_pdf_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            job = JobRecord(
                id="job_nested_callback",
                source_filename="source.pdf",
                status="parsing",
                progress=25,
                source_kind="source_pdf",
                lifecycle_status="uploaded",
                execution_status="parsing",
                source_pdf_context=SourcePdfJobContext(
                    batch_id="batch_nested",
                    data_id="job_nested_callback",
                    callback_seed="seed_nested",
                    upstream_status="submitted",
                ),
            )
            runtime.job_repository.create_job(job)

            by_data_id = runtime.command_service.find_job_for_callback({"data_id": "job_nested_callback"})
            by_batch_id = runtime.command_service.find_job_for_callback({"batch_id": "batch_nested"})

            self.assertEqual(by_data_id.id, "job_nested_callback")
            self.assertEqual(by_batch_id.id, "job_nested_callback")

    def test_replay_pending_replays_pending_and_running_stage_messages_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            job = JobRecord(
                id="job_replay",
                source_filename="source.pdf",
                status="queued",
                progress=10,
                source_kind="source_pdf",
                lifecycle_status="uploaded",
                execution_status="queued",
                source_pdf_context=SourcePdfJobContext(),
            )
            runtime.job_repository.create_job(job)
            pending = JobStageMessage(
                id="msg_pending",
                job_id=job.id,
                stage="submit_to_mineru",
                trace_id="trace_pending",
                status="pending",
            )
            running = JobStageMessage(
                id="msg_running",
                job_id=job.id,
                stage="process_callback",
                trace_id="trace_running",
                status="running",
            )
            failed = JobStageMessage(
                id="msg_failed",
                job_id=job.id,
                stage="convert_package",
                trace_id="trace_failed",
                status="failed",
            )
            runtime.stage_message_store.put_stage_message(pending)
            runtime.stage_message_store.put_stage_message(running)
            runtime.stage_message_store.put_stage_message(failed)
            replayable_messages = runtime.stage_message_store.list_replayable_stage_messages()
            self.assertEqual([message.id for message in replayable_messages], ["msg_pending", "msg_running"])

            dispatched: list[str] = []
            runtime.stage_service.dispatch_message = lambda message_id: dispatched.append(message_id)

            runtime.stage_service.replay_pending()

            self.assertEqual(dispatched, ["msg_pending", "msg_running"])

    def test_dispatch_skips_completed_conversion_message_without_rerunning_conversion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            job = JobRecord(
                id="job_completed_replay",
                source_filename="source.zip",
                status="completed",
                progress=100,
                lifecycle_status="completed",
                execution_status="idle",
                result_ready=True,
                completed_at=utc_now(),
            )
            runtime.job_repository.create_job(job)
            message = JobStageMessage(
                id="msg_completed_replay",
                job_id=job.id,
                stage="convert_package",
                trace_id="trace_completed_replay",
                status="running",
            )
            runtime.stage_message_store.put_stage_message(message)

            runtime.stage_service.dispatch_message(message.id)

            self.assertEqual(runtime.stage_service.conversion_entrypoint.requests, [])
            self.assertIsNone(runtime.stage_message_store.get_stage_message(message.id))
            self.assertEqual(runtime.job_repository.get_job(job.id).status, "completed")

    def test_dispatch_skips_replayed_mineru_submit_after_batch_recorded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            job = JobRecord(
                id="job_submitted_replay",
                source_filename="source.pdf",
                status="parsing",
                progress=25,
                source_kind="source_pdf",
                lifecycle_status="uploaded",
                execution_status="parsing",
                source_pdf_context=SourcePdfJobContext(
                    batch_id="batch_existing",
                    data_id="job_submitted_replay",
                    upstream_status="submitted",
                ),
            )
            runtime.job_repository.create_job(job)
            message = JobStageMessage(
                id="msg_submitted_replay",
                job_id=job.id,
                stage="submit_to_mineru",
                trace_id="trace_submitted_replay",
                status="running",
            )
            runtime.stage_message_store.put_stage_message(message)

            runtime.stage_service.dispatch_message(message.id)

            self.assertEqual(runtime.stage_service.fake_mineru_client.calls, [])
            self.assertIsNone(runtime.stage_message_store.get_stage_message(message.id))
            self.assertEqual(runtime.job_repository.get_job(job.id).status, "parsing")

    def test_dispatch_skips_duplicate_callback_after_job_completed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            job = JobRecord(
                id="job_callback_completed",
                source_filename="source.pdf",
                status="completed",
                progress=100,
                source_kind="source_pdf",
                lifecycle_status="completed",
                execution_status="idle",
                source_pdf_context=SourcePdfJobContext(
                    batch_id="batch_done",
                    data_id="job_callback_completed",
                    upstream_status="done",
                    result_zip_url="https://mineru.net/result.zip",
                ),
                result_ready=True,
                completed_at=utc_now(),
            )
            runtime.job_repository.create_job(job)
            message = JobStageMessage(
                id="msg_callback_completed",
                job_id=job.id,
                stage="process_callback",
                trace_id="trace_callback_completed",
                status="pending",
                payload={
                    "batch_id": "batch_done",
                    "data_id": job.id,
                    "state": "done",
                    "full_zip_url": "https://mineru.net/result.zip",
                },
            )
            runtime.stage_message_store.put_stage_message(message)

            runtime.stage_service.dispatch_message(message.id)

            self.assertEqual(runtime.stage_service.conversion_entrypoint.requests, [])
            self.assertIsNone(runtime.stage_message_store.get_stage_message(message.id))
            self.assertEqual(runtime.job_repository.get_job(job.id).status, "completed")

    def test_enqueue_parsed_result_conversion_downloads_zip_and_completes_docx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            job = JobRecord(
                id="job_parsed_conversion",
                source_filename="source.pdf",
                status="parsed",
                progress=60,
                source_kind="source_pdf",
                lifecycle_status="parsed",
                execution_status="idle",
                source_pdf_context=SourcePdfJobContext(
                    batch_id="batch_parsed",
                    data_id="job_parsed_conversion",
                    upstream_status="done",
                    result_zip_url="https://mineru.net/result.zip",
                ),
            )
            runtime.job_repository.create_job(job)

            message = runtime.stage_service.enqueue_parsed_result_conversion(job, trace_id="trace_parsed")
            queued_job = runtime.job_repository.get_job(job.id)
            self.assertIsNotNone(queued_job)
            self.assertEqual(queued_job.status, "queued")
            self.assertEqual(queued_job.progress, 65)
            self.assertEqual(message.stage, "convert_parsed_result")

            runtime.stage_service.dispatch_message(message.id)

            updated_job = runtime.job_repository.get_job(job.id)
            self.assertIsNotNone(updated_job)
            self.assertEqual(updated_job.status, "completed")
            self.assertEqual(updated_job.resolved_execution_status(), "idle")
            self.assertIsNone(runtime.stage_message_store.get_stage_message(message.id))
            files = runtime.job_file_repository.list_files(job.id)
            self.assertEqual([item.file_type for item in files], ["parsed_result_package", "result_docx"])
            job_paths = build_job_paths(runtime.settings.data_path, job.id)
            self.assertTrue(job_paths.parsed_result_package.exists())
            self.assertEqual(job_paths.parsed_result_package.read_bytes(), b"fake-parsed-result-zip")
            self.assertEqual(runtime.stage_service.fake_mineru_client.download_calls[0]["result_url"], "https://mineru.net/result.zip")
            fake_conversion = runtime.stage_service.conversion_entrypoint
            self.assertEqual(fake_conversion.requests[0].package_path, job_paths.parsed_result_package)
            self.assertEqual(job_paths.result_docx.read_bytes(), b"fake-docx")

            event_stages = [item.stage for item in runtime.job_event_repository.list_events(job.id)]
            self.assertIn("parsed_result_conversion_started", event_stages)
            self.assertIn("parsed_result_package_recovered", event_stages)
            self.assertIn("job_completed", event_stages)

    def test_convert_parsed_result_fails_when_result_zip_download_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            runtime.stage_service.fake_mineru_client.raise_download_error = True
            job = JobRecord(
                id="job_parsed_download_fail",
                source_filename="source.pdf",
                status="parsed",
                progress=60,
                source_kind="source_pdf",
                lifecycle_status="parsed",
                execution_status="idle",
                source_pdf_context=SourcePdfJobContext(
                    batch_id="batch_parsed",
                    data_id="job_parsed_download_fail",
                    upstream_status="done",
                    result_zip_url="https://mineru.net/result.zip",
                ),
            )
            runtime.job_repository.create_job(job)

            message = runtime.stage_service.enqueue_parsed_result_conversion(job, trace_id="trace_parsed_fail")
            runtime.stage_service.dispatch_message(message.id)

            updated_job = runtime.job_repository.get_job(job.id)
            self.assertIsNotNone(updated_job)
            self.assertEqual(updated_job.status, "failed")
            self.assertEqual(updated_job.error_code, "parsed_result_download_failed")
            event_stages = [item.stage for item in runtime.job_event_repository.list_events(job.id)]
            self.assertIn("job_failed", event_stages)
