# tests/test_fastapi_jobs_backend.py: 覆盖 FastAPI jobs API、workflow 和 artifact 合同。

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

import yaml

VENDOR_DIR = Path(__file__).resolve().parents[1] / ".python_packages"
if VENDOR_DIR.exists():
    vendor_path = str(VENDOR_DIR)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)

from fastapi.testclient import TestClient

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
from app.main import create_app
from app.domains.term_rules.file_repository import FileTermRuleRepository
from app.domains.audit.service import AuditService
from app.services.auth import AuthService, hash_password
from app.domains.document_jobs.execution import DocumentJobExecutionService, EagerDocumentJobTaskQueue
from app.domains.document_jobs.service import DocumentJobService
from app.services.document_ir import MinerUToDocumentIRService
from app.domains.files import FileUploadService
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
from app.services.renderer import DocumentIRWordRenderer
from app.domains.resources.service import ResourceVersionService
from app.domains.term_rules.bootstrap import TermRuleBootstrapService
from app.domains.term_rules.import_validation import TermRuleImportValidationService
from app.domains.term_rules.service import TermRuleService
from app.domains.term_rules.sync_files import TermRuleFileSyncService
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID, TermRuleSetVersionService
from app.domains.term_rules.yaml_codec import CURRENT_SCHEMA_VERSION, TermRuleYamlCodec
from app.domains.templates.read_service import TemplateReadService
from app.domains.translation.audit import TranslationAuditService
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.domains.translation.profiles_service import DEFAULT_TRANSLATION_PROFILE_ID, TranslationProfileVersionService
from app.domains.translation.provider import build_translation_provider
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


def build_test_runtime(
    data_dir: Path,
    *,
    repository_factory: Callable[[Path], PersistenceAdapters] | None = None,
    jobs_repository_backend: str = "file",
    jobs_artifact_storage_backend: str = "local_file",
    jobs_worker_mode: str = "in_process",
    openai_api_key: str = "",
    mineru_api_token: str = "",
    public_deployment_mode: str = "internal",
    mineru_callback_token: str = "",
    mineru_callback_url: str = "",
    mineru_uid: str = "",
    mineru_result_host_allowlist: str = "mineru.net,cdn-mineru.openxlab.org.cn",
    jobs_access_mode: str = "open",
    jobs_access_token: str = "",
    jobs_ops_access_mode: str = "admin",
    admin_token: str = "",
    auth_jwt_secret_key: str = "",
    auth_access_token_expire_minutes: int = 120,
    auth_internal_users_file: str = "",
    auth_internal_users_json: str = "",
    jobs_upload_max_bytes: int = 52_428_800,
    pdf_upload_max_pages: int = 200,
    p0_document_job_timeout_seconds: int = 1200,
    p0_document_job_max_retries: int = 2,
    default_translation_mode: str = "direct",
    document_jobs_worker_backend: str = "disabled",
    translation_debug_archive_enabled: bool = False,
    translation_debug_archive_retention_days: int = 1,
    templates_manifest_path: str | None = None,
    term_rules_seed_path: str | None = None,
) -> AppRuntime:
    settings = Settings(
        _env_file=None,
        data_dir=str(data_dir),
        app_name="md2word_file_test",
        jobs_repository_backend=jobs_repository_backend,
        jobs_artifact_storage_backend=jobs_artifact_storage_backend,
        jobs_worker_mode=jobs_worker_mode,
        openai_api_key=openai_api_key,
        openai_base_url="",
        openai_model="deepseek-v4-flash",
        mineru_api_token=mineru_api_token,
        public_deployment_mode=public_deployment_mode,
        mineru_callback_token=mineru_callback_token,
        mineru_callback_url=mineru_callback_url,
        mineru_uid=mineru_uid,
        mineru_result_host_allowlist=mineru_result_host_allowlist,
        jobs_access_mode=jobs_access_mode,
        jobs_access_token=jobs_access_token,
        jobs_ops_access_mode=jobs_ops_access_mode,
        admin_token=admin_token,
        auth_jwt_secret_key=auth_jwt_secret_key,
        auth_access_token_expire_minutes=auth_access_token_expire_minutes,
        auth_internal_users_file=auth_internal_users_file,
        auth_internal_users_json=auth_internal_users_json,
        jobs_upload_max_bytes=jobs_upload_max_bytes,
        pdf_upload_max_pages=pdf_upload_max_pages,
        p0_document_job_timeout_seconds=p0_document_job_timeout_seconds,
        p0_document_job_max_retries=p0_document_job_max_retries,
        default_translation_mode=default_translation_mode,
        document_jobs_worker_backend=document_jobs_worker_backend,
        translation_debug_archive_enabled=translation_debug_archive_enabled,
        translation_debug_archive_retention_days=translation_debug_archive_retention_days,
        **({"templates_manifest_path": templates_manifest_path} if templates_manifest_path else {}),
        **({"term_rules_seed_path": term_rules_seed_path} if term_rules_seed_path else {}),
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
    document_file_repository = persistence_adapters.document_file_repository
    document_job_repository = persistence_adapters.document_job_repository
    document_job_event_repository = persistence_adapters.document_job_event_repository
    stage_message_store = persistence_adapters.stage_message_store
    audit_service = AuditService(audit_event_repository)
    auth_service = AuthService(settings)
    file_upload_service = FileUploadService(settings, document_file_repository)
    document_ir_service = MinerUToDocumentIRService()
    translation_provider = build_translation_provider(settings)
    document_ir_translation_service = DocumentIRTranslationService(translation_provider)
    translation_audit_service = TranslationAuditService(settings, file_upload_service)
    term_version_service = TermVersionService(
        settings.translation_terms_file,
        default_term_version_id=settings.default_translation_term_version_id,
    )
    resource_version_service = (
        ResourceVersionService(persistence_adapters.resource_version_repository)
        if persistence_adapters.resource_version_repository is not None
        else None
    )
    template_read_service = TemplateReadService(settings, resource_version_service, audit_service)
    document_word_renderer = DocumentIRWordRenderer()
    document_job_mineru_client = FakeMinerUClient()
    document_job_mineru_client.result_zip_bytes = make_mineru_zip_bytes()
    document_job_execution_service = DocumentJobExecutionService(
        settings,
        document_job_repository,
        document_job_event_repository,
        document_file_repository,
        file_upload_service,
        document_ir_service,
        template_read_service,
        document_word_renderer,
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
    document_job_service = DocumentJobService(
        settings,
        document_job_repository,
        document_job_event_repository,
        document_file_repository,
        document_job_task_queue,
        template_read_service,
        term_version_service,
    )
    health_service = HealthService(
        settings,
        stage_message_store,
        effective_repository_backend=jobs_repository_backend,
        stage_message_store_backend=jobs_repository_backend,
        artifact_storage_backend=jobs_artifact_storage_backend,
        stage_dispatcher_backend="external_worker" if jobs_worker_mode == "external" else "background_tasks",
        job_repository=job_repository,
        audit_event_repository=audit_event_repository,
        resource_version_repository=resource_version_service.repository if resource_version_service is not None else None,
        default_template_id_getter=template_read_service.get_default_template_id,
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
        )
        if resource_version_service is not None
        else None
    )
    translation_profile_service = (
        TranslationProfileVersionService(settings, resource_version_service, audit_service)
        if resource_version_service is not None
        else None
    )
    job_resource_snapshot_service = JobResourceSnapshotService(settings, resource_version_service)
    TermRuleBootstrapService(
        term_rule_repository,
        settings.term_rules_runtime_yaml_file,
        settings.term_rules_seed_file,
        repository_backend="file",
    ).bootstrap()
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
        stage_worker_id="md2word-worker" if jobs_worker_mode == "external" else "in_process",
        mineru_client_factory=lambda: fake_mineru_client,
        resolve_template_path=template_read_service.resolve_job_template_path,
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
    )
    query_service = JobQueryService(job_repository, job_file_repository, job_event_repository)
    return AppRuntime(
        settings=settings,
        persistence_adapters=persistence_adapters,
        job_repository=job_repository,
        job_file_repository=job_file_repository,
        job_event_repository=job_event_repository,
        audit_event_repository=audit_event_repository,
        document_file_repository=document_file_repository,
        document_job_repository=document_job_repository,
        document_job_event_repository=document_job_event_repository,
        audit_service=audit_service,
        auth_service=auth_service,
        file_upload_service=file_upload_service,
        document_ir_service=document_ir_service,
        translation_provider=translation_provider,
        document_ir_translation_service=document_ir_translation_service,
        translation_audit_service=translation_audit_service,
        term_version_service=term_version_service,
        document_word_renderer=document_word_renderer,
        document_job_service=document_job_service,
        document_job_execution_service=document_job_execution_service,
        document_job_task_queue=document_job_task_queue,
        health_service=health_service,
        template_read_service=template_read_service,
        term_rule_service=term_rule_service,
        term_rule_import_validation_service=term_rule_import_validation_service,
        term_rule_file_sync_service=term_rule_file_sync_service,
        term_rule_set_version_service=term_rule_set_version_service,
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
    )


def make_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", "[]")
    return buffer.getvalue()


def make_mineru_zip_bytes(*, include_image: bool = True) -> bytes:
    buffer = io.BytesIO()
    blocks = [
        {"type": "title", "text": "数据手册", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "主要特性", "page_idx": 0},
        {
            "type": "table",
            "table_caption": "参数表",
            "table_body": "<table><tr><td>VCC</td></tr></table>",
            "page_idx": 0,
        },
        {"type": "list", "items": ["低功耗", "高可靠"], "page_idx": 1},
        {"type": "interline_equation", "latex": "E=mc^2", "page_idx": 1},
    ]
    if include_image:
        blocks.insert(3, {"type": "image", "img_path": "images/figure1.png", "caption": "管脚图", "page_idx": 0})
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", json.dumps(blocks, ensure_ascii=False))
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


def write_templates_manifest(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"templates": entries}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def resource_payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


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
) -> None:
    service = runtime.resource_version_service
    if service is None:
        raise AssertionError("resource_version_service is required for this test")
    payload = {
        "translation_profile_id": translation_profile_id,
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
    def test_jobs_api_response_contract_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                create_payload = create_response.json()
                job_id = create_payload["job_id"]

                list_payload = client.get("/api/v1/jobs").json()
                detail_payload = client.get(f"/api/v1/jobs/{job_id}").json()
                files_payload = client.get(f"/api/v1/jobs/{job_id}/files").json()
                events_payload = client.get(f"/api/v1/jobs/{job_id}/events").json()
                result_payload = client.get(f"/api/v1/jobs/{job_id}/result").json()

        self.assertEqual(list(create_payload), JOB_ACCEPTED_RESPONSE_KEYS)
        self.assertEqual(list(list_payload), JOB_LIST_RESPONSE_KEYS)
        self.assertEqual(list(list_payload["items"][0]), JOB_SUMMARY_RESPONSE_KEYS)
        self.assertEqual(list(detail_payload), JOB_DETAIL_RESPONSE_KEYS)
        self.assertEqual(list(detail_payload["files"][0]), JOB_FILE_RESPONSE_KEYS)
        self.assertEqual(list(detail_payload["events"][0]), JOB_EVENT_RESPONSE_KEYS)
        self.assertEqual(list(files_payload), JOB_FILE_LIST_RESPONSE_KEYS)
        self.assertEqual(list(files_payload["files"][0]), JOB_FILE_RESPONSE_KEYS)
        self.assertEqual(list(events_payload), JOB_EVENT_LIST_RESPONSE_KEYS)
        self.assertEqual(list(events_payload["items"][0]), JOB_EVENT_RESPONSE_KEYS)
        self.assertEqual(list(result_payload), JOB_FILE_RESPONSE_KEYS)

    def test_api_v1_schema_imports_use_final_owners_after_resource_split(self):
        from app.api.v1.routers.health_schemas import HealthReadyResponse
        from app.domains.document_jobs.schemas import DocumentJobCreateResponse
        from app.domains.document_jobs.schemas import DocumentJobRetryResponse
        from app.domains.files.schemas import DocumentFileResponse
        from app.domains.jobs.schemas import JobDetailResponse

        self.assertEqual(JobDetailResponse.__module__, "app.domains.jobs.schemas")
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
        self.assertEqual(payload["dependency_checks"]["configured_repository_backend"], "file")
        self.assertEqual(payload["dependency_checks"]["effective_repository_backend"], "file")
        self.assertEqual(payload["dependency_checks"]["worker_mode"], "in_process")
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
        self.assertTrue(payload["dependency_checks"]["translation_client_configured"] is False)
        self.assertTrue(payload["dependency_checks"]["translation_prompt_exists"])
        self.assertFalse(payload["dependency_checks"]["mineru_api_token_configured"])
        self.assertFalse(payload["dependency_checks"]["pdf_submission_available"])
        self.assertTrue(payload["dependency_checks"]["deployment_init_ready"])
        self.assertEqual(payload["dependency_checks"]["readiness_blockers"], [])
        self.assertIn("mineru_api_token_missing", payload["dependency_checks"]["readiness_warnings"])
        self.assertIn("translation_unavailable", payload["dependency_checks"]["readiness_warnings"])
        self.assertIsNone(payload["dependency_checks"]["default_template_version"])
        self.assertIsNone(payload["dependency_checks"]["default_term_rule_version"])
        self.assertIsNone(payload["dependency_checks"]["default_translation_profile_version"])
        self.assertFalse(payload["dependency_checks"]["mysql_schema_bootstrap_available"])

    def test_health_metrics_reports_runtime_counters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                response = client.get("/api/v1/health/metrics")

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["metadata_store"], "file")
        self.assertEqual(payload["artifact_storage"], "local_file")
        self.assertEqual(payload["worker_mode"], "in_process")
        self.assertEqual(payload["stage_dispatcher"], "background_tasks")
        self.assertEqual(payload["jobs"], {"completed": 1})
        self.assertEqual(payload["stage_messages"], {"pending": 0, "running": 0, "failed": 0})
        self.assertEqual(payload["resources"]["template_versions"], 0)
        self.assertEqual(payload["audit_events"]["total"], 0)
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("ADMIN_TOKEN", serialized)

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
        self.assertEqual(payload["resources"]["term_rule_set_versions"], 1)
        self.assertEqual(payload["resources"]["translation_profile_versions"], 1)
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

    def test_health_ready_blocks_when_default_translation_mode_requires_missing_client(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), default_translation_mode="en2zh")
            checks = runtime.health_service.build_dependency_checks()

        self.assertTrue(checks["translation_required_for_default_mode"])
        self.assertFalse(checks["translation_available"])
        self.assertFalse(checks["deployment_init_ready"])
        self.assertIn("default_translation_unavailable", checks["readiness_blockers"])

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
        self.assertGreater(admin_login.json()["expires_in"], 0)
        self.assertEqual(operator_login.status_code, 200)
        self.assertEqual(operator_login.json()["role"], "operator")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["id"], "user_admin")
        self.assertEqual(me_response.json()["role"], "admin")

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
                        "template_version_id": "default",
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
            raw_bytes = runtime.file_upload_service.read_file_content(raw_file)
            ir_payload = json.loads(runtime.file_upload_service.read_file_content(ir_file).decode("utf-8"))
            image_bytes = runtime.file_upload_service.read_file_content(image_files[0])
            word_bytes = runtime.file_upload_service.read_file_content(word_file)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(stored_job.stage, "completed")
        self.assertEqual(raw_file.file_type, "mineru_raw_result")
        self.assertEqual(ir_file.file_type, "document_ir")
        self.assertEqual(word_file.file_type, "generated_word")
        self.assertEqual(word_file.metadata["template_version_id"], "default@1")
        self.assertEqual([file.file_type for file in image_files], ["image_asset"])
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
            self.assertIn("content_list_v2.json", archive.namelist())
        with zipfile.ZipFile(io.BytesIO(word_bytes)) as archive:
            self.assertIn("word/document.xml", archive.namelist())
        self.assertEqual(ir_payload["schema_version"], "document-ir/v1")
        self.assertEqual(
            [block["type"] for block in ir_payload["blocks"]],
            ["heading", "paragraph", "table", "image", "list", "formula"],
        )
        self.assertEqual(ir_payload["assets"][0]["file_id"], image_files[0].id)
        self.assertEqual(ir_payload["assets"][0]["object_key"], image_files[0].object_key)
        self.assertEqual(ir_payload["blocks"][3]["asset_ref"], ir_payload["assets"][0]["id"])
        self.assertEqual(image_bytes, MINIMAL_PNG_BYTES)

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
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            runtime.document_job_execution_service.document_ir_translation_service = runtime.document_ir_translation_service
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = make_english_mineru_zip_bytes()
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = build_auth_header(client)
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

            stored_job = runtime.document_job_repository.get_document_job(job_id)
            files = [
                file
                for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id
            ]
            files_by_type = {file.file_type: file for file in files}
            ir_payload = json.loads(
                runtime.file_upload_service.read_file_content(files_by_type["document_ir"]).decode("utf-8")
            )
            ai_log_text = runtime.file_upload_service.read_file_content(files_by_type["ai_call_log"]).decode("utf-8")
            ai_log_payload = json.loads(ai_log_text)
            debug_text = runtime.file_upload_service.read_file_content(files_by_type["ai_debug_archive"]).decode("utf-8")
            debug_payload = json.loads(debug_text)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "succeeded")
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.term_version_id, "en2zh@v1")
        self.assertTrue(stored_job.debug_full_text_enabled)
        self.assertEqual(len(provider.requests), 1)
        self.assertEqual(ir_payload["metadata"]["document_language"], "zh")
        self.assertEqual(ir_payload["blocks"][0]["text"], "1 特性")
        self.assertEqual(ir_payload["blocks"][1]["text"], "输入失调电压很低。")
        self.assertIn("<th>参数</th>", ir_payload["blocks"][2]["html"])
        self.assertEqual(ir_payload["blocks"][4]["list_items"], ["低噪声", "高压摆率"])
        self.assertEqual(files_by_type["document_ir"].metadata["translation"]["applied"], True)
        self.assertEqual(files_by_type["ai_call_log"].metadata["status"], "succeeded")
        self.assertEqual(ai_log_payload["status"], "succeeded")
        self.assertEqual(ai_log_payload["request"]["item_count"], 8)
        self.assertIn("sha256:", ai_log_payload["request"]["redacted_items"][0]["sha256"])
        self.assertNotIn("The input offset voltage is low.", ai_log_text)
        self.assertIn("The input offset voltage is low.", debug_text)
        self.assertIn("输入失调电压很低。", debug_text)
        self.assertEqual(debug_payload["schema_version"], "translation-debug-archive/v1")
        self.assertEqual(files_by_type["ai_debug_archive"].metadata["contains_full_text"], True)
        self.assertLessEqual(
            files_by_type["ai_debug_archive"].expires_at - files_by_type["ai_debug_archive"].created_at,
            timedelta(days=1, seconds=1),
        )
        event_types = [event["event_type"] for event in events_response.json()["items"]]
        self.assertIn("ai_call_logged", event_types)
        self.assertIn("debug_archive_saved", event_types)

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

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "failed")
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.error_code, "translation_failed")
        self.assertEqual(len(provider.requests), 1)
        self.assertEqual(len(ai_logs), 1)
        self.assertEqual(debug_archives, [])
        self.assertEqual(ai_log_payload["status"], "failed")
        self.assertEqual(ai_log_payload["error"]["type"], "RuntimeError")
        self.assertNotIn("The input offset voltage is low.", ai_log_text)

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

        render_failed_job = render_failed_response.json()["job"]
        self.assertEqual(render_failed_job["status"], "failed")
        self.assertEqual(render_failed_job["failed_stage"], "rendering")
        self.assertEqual(render_failed_job["error_code"], "render_failed")

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
                operator_list = client.get("/api/v1/document-jobs", headers=operator_headers)
                admin_detail = client.get(
                    f"/api/v1/document-jobs/{other_job['job_id']}",
                    headers=admin_headers,
                )
                admin_list = client.get("/api/v1/document-jobs", headers=admin_headers)

        self.assertEqual(forbidden_detail.status_code, 403)
        self.assertEqual(forbidden_detail.json()["error_code"], "forbidden")
        self.assertEqual(operator_list.status_code, 200)
        self.assertEqual(operator_list.json()["total"], 0)
        self.assertEqual(admin_detail.status_code, 200)
        self.assertEqual(admin_detail.json()["created_by"], "user_operator_2")
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

    def test_templates_manifest_supports_multiple_visible_templates_and_admin_default_switch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            alt_template_path = temp_root / "alt_template.docx"
            alt_template_path.write_bytes(b"alt-docx")
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
                    },
                    {
                        "id": "alt",
                        "name": "Alt Template",
                        "description": "alt",
                        "enabled": True,
                        "is_default_seed": False,
                        "template_path": str(alt_template_path.resolve()),
                        "layout_config_path": str((repo_root / "resources" / "template_configs" / "datasheet_template.yaml").resolve()),
                    },
                ],
            )

            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                templates_manifest_path=str(manifest_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                list_response = client.get("/api/v1/templates")
                self.assertEqual(list_response.status_code, 200)
                items = list_response.json()["items"]
                self.assertEqual([item["id"] for item in items], ["default", "alt"])
                self.assertTrue(items[0]["is_default"])
                self.assertFalse(items[1]["is_default"])

                denied = client.patch("/api/v1/templates/alt/default")
                self.assertEqual(denied.status_code, 403)

                switch_response = client.patch(
                    "/api/v1/templates/alt/default",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(switch_response.status_code, 200)
                self.assertEqual(switch_response.json()["id"], "alt")
                self.assertTrue(switch_response.json()["is_default"])

                refreshed = client.get("/api/v1/templates").json()["items"]
                self.assertFalse(refreshed[0]["is_default"])
                self.assertTrue(refreshed[1]["is_default"])

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
                versions_response = client.get("/api/v1/templates/managed/versions")
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

                publish_v1_response = client.post(
                    "/api/v1/templates/managed/versions/1/publish",
                    json={"make_default": True},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(publish_v1_response.status_code, 200)
                self.assertEqual(publish_v1_response.json()["status"], "published")
                self.assertTrue(publish_v1_response.json()["is_default"])

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

                publish_v2_response = client.post(
                    "/api/v1/templates/managed/versions/2/publish",
                    json={"make_default": False},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                set_default_v2_response = client.post(
                    "/api/v1/templates/managed/versions/2/set-default",
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
                versions_response = client.get("/api/v1/templates/managed/versions")

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

        records = {record.version: record for record in runtime.resource_version_service.repository.list_resource_versions("template", "managed")}
        default_record = runtime.resource_version_service.repository.get_default_resource_version("template", "managed")
        self.assertEqual(records["1"].status.value, "disabled")
        self.assertEqual(records["2"].status.value, "published")
        self.assertEqual(default_record.version, "2")
        self.assertEqual(records["2"].payload["render_policy"], {"density": "compact"})
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
        self.assertEqual(audit_events[-1].target_id, "managed@1")
        self.assertNotIn("term_rules", records["2"].payload)

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
                default_after_draft_response = client.get("/api/v1/term-rule-sets/electronics-default")
                self.assertEqual(default_after_draft_response.json()["default_version"], version_v1)

                draft_v2_response = client.put(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    json={"yaml_text": yaml_v2},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(draft_v2_response.status_code, 200)
                self.assertIn("VTWO", draft_v2_response.json()["yaml_text"])
                self.assertNotIn("VTWO", runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8"))

                publish_v2_response = client.post(
                    "/api/v1/term-rule-sets/electronics-default/publish",
                    json={"make_default": False},
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
                export_response = client.get("/api/v1/term-rules/export")
                detail_response = client.get("/api/v1/term-rule-sets/electronics-default")

        self.assertEqual(rollback_response.status_code, 200)
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
        self.assertEqual(len(detail_response.json()["versions"]), 2)

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
                draft_before_response = client.get("/api/v1/term-rule-sets/electronics-default/draft")
                self.assertEqual(draft_before_response.status_code, 200)

                invalid_response = client.put(
                    "/api/v1/term-rule-sets/electronics-default/draft/rules",
                    json={"yaml_text": "schema_version: 2\ncategories: [bad]\nrules: []\n"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                draft_after_response = client.get("/api/v1/term-rule-sets/electronics-default/draft")

        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.json()["detail"]["code"], "invalid_term_rule_set_draft")
        self.assertEqual(
            draft_after_response.json()["snapshot_hash"],
            draft_before_response.json()["snapshot_hash"],
        )

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

    def test_term_rule_categories_export_and_simulate_are_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                categories_response = client.get("/api/v1/term-rule-categories")
                self.assertEqual(categories_response.status_code, 200)
                self.assertGreater(len(categories_response.json()["items"]), 0)

                export_response = client.get("/api/v1/term-rules/export")
                self.assertEqual(export_response.status_code, 200)
                self.assertIn("schema_version: 2", export_response.json()["yaml_text"])

                simulate_response = client.post(
                    "/api/v1/term-rules/simulate",
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
                validate_response = client.post("/api/v1/term-rules/import/validate", json=payload)
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

                export_response = client.get("/api/v1/term-rules/export")
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

    def test_jobs_accept_visible_template_id_and_fallback_to_runtime_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            alt_template_path = temp_root / "alt_template.docx"
            alt_template_path.write_bytes(b"alt-docx")
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
                    },
                    {
                        "id": "alt",
                        "name": "Alt Template",
                        "description": "alt",
                        "enabled": True,
                        "is_default_seed": False,
                        "template_path": str(alt_template_path.resolve()),
                        "layout_config_path": str((repo_root / "resources" / "template_configs" / "datasheet_template.yaml").resolve()),
                    },
                ],
            )

            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                templates_manifest_path=str(manifest_path),
            )
            runtime.template_read_service.set_default_template("alt")
            app = create_app(runtime)
            with TestClient(app) as client:
                explicit_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct", "template_id": "alt"},
                )
                self.assertEqual(explicit_response.status_code, 201)
                explicit_job_id = explicit_response.json()["job_id"]
                explicit_detail = client.get(f"/api/v1/jobs/{explicit_job_id}").json()
                self.assertEqual(explicit_detail["template_id"], "alt")

                default_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(default_response.status_code, 201)
                default_job_id = default_response.json()["job_id"]
                default_detail = client.get(f"/api/v1/jobs/{default_job_id}").json()
                self.assertEqual(default_detail["template_id"], "alt")

            fake_service = runtime.stage_service.conversion_entrypoint
            self.assertEqual(len(fake_service.requests), 2)
            self.assertEqual(fake_service.requests[0].template_path, alt_template_path.resolve())
            self.assertEqual(fake_service.requests[1].template_path, alt_template_path.resolve())

    def test_upload_zip_runs_background_conversion_and_downloads_docx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]

                detail_response = client.get(f"/api/v1/jobs/{job_id}")
                self.assertEqual(detail_response.status_code, 200)
                detail_payload = detail_response.json()
                self.assertEqual(detail_payload["status"], "completed")
                self.assertTrue(detail_payload["result_ready"])
                self.assertEqual(detail_payload["files"][0]["file_type"], "source_package")
                self.assertEqual(detail_payload["files"][1]["file_type"], "result_docx")
                for item in detail_payload["files"]:
                    self.assertGreater(item["size_bytes"], 0)
                    self.assertTrue(item["sha256"].startswith("sha256:"))

                result_response = client.get(f"/api/v1/jobs/{job_id}/result")
                self.assertEqual(result_response.status_code, 200)
                self.assertIn(f"/api/v1/jobs/{job_id}/download/result", result_response.json()["download_url"])

                download_response = client.get(
                    f"/api/v1/jobs/{job_id}/download/result",
                    headers={"X-Actor-Id": "spoofed-anonymous"},
                )
                self.assertEqual(download_response.status_code, 200)
                self.assertEqual(download_response.content, b"fake-docx")
                audit_events = runtime.audit_event_repository.list_audit_events()
                self.assertEqual([event.action for event in audit_events], ["artifact.download"])
                self.assertEqual(audit_events[0].actor_role, "anonymous")
                self.assertIsNone(audit_events[0].actor_id)
                self.assertEqual(audit_events[0].target_id, f"{job_id}:result")
                self.assertNotIn(str(Path(temp_dir)), audit_events[0].target_id)

                events_response = client.get(f"/api/v1/jobs/{job_id}/events")
                self.assertEqual(events_response.status_code, 200)
                event_stages = [item["stage"] for item in events_response.json()["items"]]
                self.assertIn("job_created", event_stages)
                self.assertIn("job_completed", event_stages)

    def test_download_artifact_maps_storage_errors(self):
        class BrokenArtifactStorage:
            """测试用 adapter：模拟 artifact storage 在下载解析阶段抛错。"""

            def __init__(self, error: FileNotFoundError | ValueError) -> None:
                self.error = error

            def resolve_download(self, paths, file):
                raise self.error

        cases = [
            (FileNotFoundError("artifact missing"), 404),
            (ValueError("artifact path invalid"), 400),
            (ArtifactFingerprintMismatch("artifact fingerprint mismatch"), 409),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            app = create_app(runtime)
            job = JobRecord(
                id="job_download_error",
                source_filename="download-error.zip",
                status="completed",
                progress=100,
                result_ready=True,
                completed_at=utc_now(),
            )
            runtime.job_repository.create_job(job)
            runtime.job_file_repository.upsert_file(job.id, JobFile(file_type="result_docx", path="output/result.docx"))

            with TestClient(app) as client:
                for error, expected_status in cases:
                    with self.subTest(error=type(error).__name__):
                        runtime.artifact_storage = BrokenArtifactStorage(error)
                        response = client.get(f"/api/v1/jobs/{job.id}/download/result")
                        self.assertEqual(response.status_code, expected_status)
                        self.assertEqual(response.json()["detail"], str(error))

    def test_download_artifact_rejects_fingerprint_mismatch_without_absolute_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            app = create_app(runtime)
            job = JobRecord(
                id="job_fingerprint_mismatch",
                source_filename="mismatch.zip",
                status="completed",
                progress=100,
                result_ready=True,
                completed_at=utc_now(),
            )
            runtime.job_repository.create_job(job)
            job_paths = build_job_paths(runtime.settings.data_path, job.id)
            ensure_job_dirs(job_paths)
            job_paths.result_docx.write_bytes(b"actual-docx")
            runtime.job_file_repository.upsert_file(
                job.id,
                JobFile(
                    file_type="result_docx",
                    path="output/result.docx",
                    size_bytes=1,
                    sha256=f"sha256:{hashlib.sha256(b'expected').hexdigest()}",
                ),
            )

            with TestClient(app) as client:
                response = client.get(f"/api/v1/jobs/{job.id}/download/result")

        detail = response.json()["detail"]
        self.assertEqual(response.status_code, 409)
        self.assertIn("file_type=result_docx", detail)
        self.assertIn("path=output/result.docx", detail)
        self.assertNotIn(str(runtime.settings.data_path), detail)

    def test_core_error_response_contracts_keep_detail_shape_stable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            app = create_app(runtime)
            queued_job = JobRecord(
                id="job_result_not_ready",
                source_filename="queued.zip",
                status="queued",
                progress=0,
            )
            runtime.job_repository.create_job(queued_job)

            with TestClient(app) as client:
                bad_upload_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("bad.txt", b"not-zip", "text/plain")},
                )
                forbidden_ops_response = client.post(
                    f"/api/v1/jobs/{queued_job.id}/cleanup-local-files",
                    data={"reason": "auth-check"},
                )
                result_not_ready_response = client.get(f"/api/v1/jobs/{queued_job.id}/result")

        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                admin_unconfigured_response = client.post(
                    "/api/v1/jobs/job_missing_admin/cleanup-local-files",
                    data={"reason": "auth-check"},
                )

        self.assertEqual(bad_upload_response.status_code, 400)
        self.assertEqual(bad_upload_response.json()["detail"], "上传文件必须是 .zip 格式的 MinerU 输出包。")
        self.assertEqual(bad_upload_response.json()["error_code"], "invalid_request")
        self.assertEqual(forbidden_ops_response.status_code, 403)
        self.assertEqual(forbidden_ops_response.json()["detail"], "admin token 校验失败。")
        self.assertEqual(forbidden_ops_response.json()["error_code"], "forbidden")
        self.assertEqual(result_not_ready_response.status_code, 409)
        self.assertEqual(result_not_ready_response.json()["detail"], "任务尚未完成，result.docx 还不可用。")
        self.assertEqual(result_not_ready_response.json()["error_code"], "conflict")
        self.assertEqual(admin_unconfigured_response.status_code, 503)
        self.assertEqual(admin_unconfigured_response.json()["detail"], "ADMIN_TOKEN 未配置，管理接口不可用。")
        self.assertEqual(admin_unconfigured_response.json()["error_code"], "service_unavailable")

    def test_download_artifact_supports_stream_storage_result(self):
        class StreamArtifactStorage:
            """测试用 adapter：模拟对象存储 SDK 返回流式内容。"""

            def resolve_download(self, paths, file):
                return DownloadArtifact.stream([b"stream-docx"])

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            runtime.artifact_storage = StreamArtifactStorage()
            app = create_app(runtime)
            job = JobRecord(
                id="job_stream_download",
                source_filename="stream-source.zip",
                status="completed",
                progress=100,
                result_ready=True,
                completed_at=utc_now(),
            )
            runtime.job_repository.create_job(job)
            runtime.job_file_repository.upsert_file(job.id, JobFile(file_type="result_docx", path="output/result.docx"))

            with TestClient(app) as client:
                response = client.get(f"/api/v1/jobs/{job.id}/download/result")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"stream-docx")
        self.assertIn("stream-source.docx", response.headers["content-disposition"])

    def test_download_artifact_supports_redirect_storage_result(self):
        class RedirectArtifactStorage:
            """测试用 adapter：模拟对象存储返回临时签名下载地址。"""

            def resolve_download(self, paths, file):
                return DownloadArtifact.redirect("https://storage.example/jobs/job_redirect_download/result.docx")

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            runtime.artifact_storage = RedirectArtifactStorage()
            app = create_app(runtime)
            job = JobRecord(
                id="job_redirect_download",
                source_filename="redirect-source.zip",
                status="completed",
                progress=100,
                result_ready=True,
                completed_at=utc_now(),
            )
            runtime.job_repository.create_job(job)
            runtime.job_file_repository.upsert_file(job.id, JobFile(file_type="result_docx", path="output/result.docx"))

            with TestClient(app) as client:
                response = client.get(f"/api/v1/jobs/{job.id}/download/result", follow_redirects=False)

        self.assertEqual(response.status_code, 307)
        self.assertEqual(
            response.headers["location"],
            "https://storage.example/jobs/job_redirect_download/result.docx",
        )

    def test_upload_zip_dispatches_stage_through_runtime_dispatcher(self):
        class RecordingDispatcher:
            def __init__(self) -> None:
                self.message_ids: list[str] = []
                self.replay_called = False

            def dispatch(self, message_id: str) -> None:
                self.message_ids.append(message_id)

            def replay_pending(self) -> None:
                self.replay_called = True

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            dispatcher = RecordingDispatcher()
            runtime.stage_dispatcher = dispatcher
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)

            pending_messages = runtime.stage_message_store.list_replayable_stage_messages()
            self.assertTrue(dispatcher.replay_called)
            self.assertEqual(dispatcher.message_ids, [pending_messages[0].id])
            self.assertEqual(pending_messages[0].stage, "convert_package")

    def test_external_worker_mode_leaves_stage_for_worker_process(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), jobs_worker_mode="external")
            app = create_app(runtime)
            with TestClient(app) as client:
                health = client.get("/api/v1/health/ready").json()
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]
                queued_detail = client.get(f"/api/v1/jobs/{job_id}").json()

            pending_messages = runtime.stage_message_store.list_replayable_stage_messages()
            requests_before_worker = list(runtime.stage_service.conversion_entrypoint.requests)
            worker = StageWorker(runtime, poll_interval_seconds=0)
            processed_count = worker.run_once()
            completed_job = runtime.job_repository.get_job(job_id)
            remaining_messages = runtime.stage_message_store.list_replayable_stage_messages()

        self.assertEqual(health["dependency_checks"]["worker_mode"], "external")
        self.assertEqual(health["dependency_checks"]["stage_dispatcher"], "external_worker")
        self.assertEqual(queued_detail["status"], "queued")
        self.assertEqual(requests_before_worker, [])
        self.assertEqual(len(runtime.stage_service.conversion_entrypoint.requests), 1)
        self.assertEqual(len(pending_messages), 1)
        self.assertEqual(pending_messages[0].stage, "convert_package")
        self.assertEqual(processed_count, 1)
        self.assertIsNotNone(completed_job)
        self.assertEqual(completed_job.status, "completed")
        self.assertEqual(remaining_messages, [])

    def test_upload_en2zh_preserves_conversion_request_options_and_translation_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), openai_api_key="fake-key")
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={
                        "translation_mode": "en2zh",
                        "document_language": "auto",
                        "use_mineru_header_footer": "true",
                    },
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]

                files_response = client.get(f"/api/v1/jobs/{job_id}/files")
                self.assertEqual(files_response.status_code, 200)
                file_types = [item["file_type"] for item in files_response.json()["files"]]
                self.assertEqual(file_types, ["source_package", "translation_request", "translation_trace", "result_docx"])
                events_response = client.get(f"/api/v1/jobs/{job_id}/events")
                self.assertEqual(events_response.status_code, 200)
                event_stages = [item["stage"] for item in events_response.json()["items"]]
                self.assertIn("translation_started", event_stages)
                self.assertIn("translation_completed", event_stages)

            fake_service = runtime.stage_service.conversion_entrypoint
            self.assertEqual(len(fake_service.requests), 1)
            request = fake_service.requests[0]
            self.assertEqual(request.translation_mode, "en2zh")
            self.assertTrue(request.use_mineru_header_footer)
            self.assertIsNotNone(request.translation_request_output)
            self.assertIsNotNone(request.translation_trace_output)
            self.assertEqual(request.translation_model, "deepseek-v4-flash")

    def test_translation_profile_versioning_overrides_en2zh_request_and_records_trace(self):
        from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                openai_api_key="fake-key",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                draft_response = client.put(
                    "/api/v1/translation-profiles/electronics-en2zh/draft",
                    json={
                        "target_language": "zh-CN",
                        "domain": "electronics datasheet",
                        "prompt_version": "profile-prompt-v2",
                        "model": "profile-model",
                        "max_pages_per_batch": 7,
                        "max_chars_per_batch": 1234,
                    },
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(draft_response.status_code, 200)
                self.assertEqual(draft_response.json()["model"], "profile-model")

                publish_response = client.post(
                    "/api/v1/translation-profiles/electronics-en2zh/publish",
                    json={"make_default": True},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(publish_response.status_code, 200)
                self.assertTrue(publish_response.json()["is_default"])
                version = publish_response.json()["version"]
                publish_template_resource_version(
                    runtime,
                    version="1",
                    content=b"template-v1",
                    make_default=True,
                )
                publish_term_rule_resource_version(runtime, version="1", source_term="VONE", make_default=True)

                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "en2zh"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]
                files_response = client.get(f"/api/v1/jobs/{job_id}/files")
                trace_response = client.get(f"/api/v1/jobs/{job_id}/download/translation-trace")
                detail_response = client.get("/api/v1/translation-profiles/electronics-en2zh")

        request = runtime.stage_service.conversion_entrypoint.requests[0]
        self.assertEqual(request.translation_model, "profile-model")
        self.assertEqual(request.translation_target_language, "zh-CN")
        self.assertEqual(request.translation_domain, "electronics datasheet")
        self.assertEqual(request.translation_prompt_version, "profile-prompt-v2")
        self.assertEqual(request.translation_max_pages, 7)
        self.assertEqual(request.translation_max_chars, 1234)
        self.assertIsNotNone(request.translation_profile)
        self.assertEqual(request.translation_profile.version, version)

        file_types = [item["file_type"] for item in files_response.json()["files"]]
        self.assertEqual(file_types, ["source_package", "translation_request", "translation_trace", "result_docx"])
        trace_payload = json.loads(trace_response.content.decode("utf-8"))
        self.assertEqual(trace_payload["job_id"], job_id)
        self.assertEqual(trace_payload["translation_profile"]["version"], version)
        self.assertEqual(detail_response.json()["default_version"], version)

        records = {
            record.version: record
            for record in runtime.resource_version_service.repository.list_resource_versions("translation_profile", "electronics-en2zh")
        }
        self.assertEqual(records[version].status.value, "published")
        self.assertEqual(records[version].payload["model"], "profile-model")
        self.assertNotIn("api_key", records[version].payload)
        audit_events = runtime.audit_event_repository.list_audit_events()
        self.assertIn("translation_profile.publish", [event.action for event in audit_events])

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

    def test_mysql_direct_job_binds_template_term_snapshot_and_source_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(Path(temp_dir), admin_token="secret-admin")
            template_path, source_term = publish_default_job_resources(runtime)
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                accepted_snapshot = create_response.json()["resource_snapshot"]
                job_id = create_response.json()["job_id"]
                detail_snapshot = client.get(f"/api/v1/jobs/{job_id}").json()["resource_snapshot"]

            request = runtime.stage_service.conversion_entrypoint.requests[0]
            job_paths = build_job_paths(runtime.settings.data_path, job_id)
            resource_subscript_config_exists = job_paths.resource_subscript_config.exists()
            resource_subscript_config_text = job_paths.resource_subscript_config.read_text(encoding="utf-8")

        self.assertEqual(accepted_snapshot["template"]["resource_id"], "default")
        self.assertEqual(accepted_snapshot["template"]["version"], "1")
        self.assertEqual(accepted_snapshot["term_rule_set"]["resource_id"], DEFAULT_TERM_RULE_SET_ID)
        self.assertEqual(accepted_snapshot["term_rule_set"]["version"], "1")
        self.assertIsNone(accepted_snapshot["translation_profile"])
        self.assertEqual(accepted_snapshot["artifact_ids"], {"source": "source_package"})
        self.assertIsNone(accepted_snapshot["mineru"]["model_version"])
        self.assertEqual(detail_snapshot, accepted_snapshot)
        self.assertEqual(request.template_path, template_path)
        self.assertEqual(request.subscript_config_path, job_paths.resource_subscript_config)
        self.assertTrue(resource_subscript_config_exists)
        self.assertIn(source_term, resource_subscript_config_text)

    def test_mysql_en2zh_job_binds_translation_profile_snapshot_and_uses_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                openai_api_key="fake-key",
            )
            publish_default_job_resources(runtime, include_translation=True)
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "en2zh"},
                )
                self.assertEqual(create_response.status_code, 201)
                snapshot = create_response.json()["resource_snapshot"]
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()

            request = runtime.stage_service.conversion_entrypoint.requests[0]

        self.assertEqual(snapshot["translation_profile"]["resource_id"], DEFAULT_TRANSLATION_PROFILE_ID)
        self.assertEqual(snapshot["translation_profile"]["version"], "1")
        self.assertEqual(detail["resource_snapshot"], snapshot)
        self.assertEqual(request.translation_model, "snapshot-model-v1")
        self.assertEqual(request.translation_target_language, "zh-CN")
        self.assertEqual(request.translation_domain, "electronics datasheet")
        self.assertEqual(request.translation_prompt_version, "prompt-1")
        self.assertEqual(request.translation_max_pages, 7)
        self.assertEqual(request.translation_max_chars, 1234)
        self.assertIsNotNone(request.translation_profile)
        self.assertEqual(request.translation_profile.version, "1")

    def test_mysql_default_switch_and_disabled_versions_do_not_change_existing_job_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                jobs_worker_mode="external",
            )
            template_v1, _source_term = publish_default_job_resources(runtime)
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]

            publish_template_resource_version(
                runtime,
                version="2",
                content=b"template-v2",
                make_default=True,
            )
            publish_term_rule_resource_version(runtime, version="2", source_term="VTWO", make_default=True)
            runtime.resource_version_service.disable("template", "default", "1")
            runtime.resource_version_service.mark_superseded("term_rule_set", DEFAULT_TERM_RULE_SET_ID, "1")

            worker = StageWorker(runtime, poll_interval_seconds=0)
            processed_count = worker.run_once()
            request = runtime.stage_service.conversion_entrypoint.requests[0]
            job_paths = build_job_paths(runtime.settings.data_path, job_id)
            updated_job = runtime.job_repository.get_job(job_id)
            materialized_yaml = job_paths.resource_subscript_config.read_text(encoding="utf-8")

        self.assertEqual(processed_count, 1)
        self.assertIsNotNone(updated_job)
        self.assertEqual(updated_job.status, "completed")
        self.assertEqual(request.template_path, template_v1)
        self.assertIn("VONE", materialized_yaml)
        self.assertNotIn("VTWO", materialized_yaml)

    def test_mysql_snapshot_hash_mismatch_fails_stage_without_live_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                jobs_worker_mode="external",
            )
            publish_default_job_resources(runtime)
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]

            message = runtime.stage_message_store.list_replayable_stage_messages()[0]
            record = runtime.resource_version_service.repository.get_resource_version("template", "default", "1")
            self.assertIsNotNone(record)
            runtime.resource_version_service.repository.save_resource_version(
                record.model_copy(update={"snapshot_hash": "sha256:" + "f" * 64})
            )

            worker = StageWorker(runtime, poll_interval_seconds=0)
            processed_count = worker.run_once()
            updated_job = runtime.job_repository.get_job(job_id)
            failed_message = runtime.stage_message_store.get_stage_message(message.id)

        self.assertEqual(processed_count, 1)
        self.assertIsNotNone(updated_job)
        self.assertEqual(updated_job.status, "failed")
        self.assertEqual(updated_job.error_code, "resource_snapshot_hash_mismatch")
        self.assertEqual(runtime.stage_service.conversion_entrypoint.requests, [])
        self.assertIsNotNone(failed_message)
        self.assertEqual(failed_message.status, "failed")
        self.assertEqual(failed_message.error_code, "resource_snapshot_hash_mismatch")

    def test_mysql_resource_mode_requires_default_template_and_term_rules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(Path(temp_dir), admin_token="secret-admin")
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )

        self.assertEqual(response.status_code, 409)
        self.assertIn("默认资源版本不存在", response.json()["detail"])

    def test_file_backend_rejects_versioned_resource_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct", "template_version": "1"},
                )

        self.assertEqual(response.status_code, 503)
        self.assertIn("JOBS_REPOSITORY_BACKEND=mysql", response.json()["detail"])

    def test_mysql_pdf_job_uses_mineru_snapshot_and_source_pdf_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_mysql_test_runtime(
                Path(temp_dir),
                admin_token="secret-admin",
                mineru_api_token="token-123",
                jobs_worker_mode="external",
            )
            publish_default_job_resources(runtime)
            runtime.settings.mineru_language = "en"
            runtime.settings.mineru_enable_formula = False
            runtime.settings.mineru_enable_table = True
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]
                snapshot = create_response.json()["resource_snapshot"]

            runtime.settings.mineru_language = "zh"
            runtime.settings.mineru_enable_formula = True
            runtime.settings.mineru_enable_table = False
            worker = StageWorker(runtime, poll_interval_seconds=0)
            processed_count = worker.run_once()
            updated_job = runtime.job_repository.get_job(job_id)
            fake_call = runtime.stage_service.fake_mineru_client.calls[0]

        self.assertEqual(processed_count, 1)
        self.assertIsNotNone(updated_job)
        self.assertEqual(updated_job.status, "parsing")
        self.assertEqual(snapshot["artifact_ids"], {"source": "source_pdf"})
        self.assertEqual(snapshot["mineru"]["model_version"], "vlm")
        self.assertEqual(snapshot["mineru"]["language"], "en")
        self.assertFalse(snapshot["mineru"]["enable_formula"])
        self.assertTrue(snapshot["mineru"]["enable_table"])
        self.assertEqual(snapshot["mineru"]["data_id"], job_id)
        self.assertEqual(fake_call["task_uuids"], [job_id])
        self.assertEqual(fake_call["language"], "en")
        self.assertFalse(fake_call["enable_formula"])
        self.assertTrue(fake_call["enable_table"])

    def test_upload_en2zh_rejects_when_translation_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir), openai_api_key=""))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "en2zh"},
                )

        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_API_KEY", response.json()["detail"])

    def test_upload_rejects_non_zip_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("bad.txt", b"not-zip", "text/plain")},
                )

        self.assertEqual(response.status_code, 400)
        self.assertIn(".zip", response.json()["detail"])

    def test_upload_pdf_submits_to_mineru_and_enters_parsing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(response.status_code, 201)
                job_id = response.json()["job_id"]

                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(detail["status"], "parsing")
                self.assertEqual(detail["source_kind"], "source_pdf")
                self.assertEqual(detail["mineru_batch_id"], "batch_test_001")
                self.assertEqual(detail["mineru_data_id"], job_id)
                self.assertEqual(detail["mineru_status"], "submitted")
                self.assertEqual(detail["mineru_result_zip_url"], None)
                persisted_job = runtime.job_repository.get_job(job_id)
                self.assertIsNotNone(persisted_job)
                self.assertIsNotNone(persisted_job.source_pdf_context)
                self.assertEqual(persisted_job.source_pdf_context.batch_id, "batch_test_001")
                self.assertEqual(persisted_job.source_pdf_context.data_id, job_id)
                self.assertEqual(persisted_job.source_pdf_context.upstream_status, "submitted")
                self.assertIsNone(persisted_job.source_pdf_context.result_zip_url)

                files = client.get(f"/api/v1/jobs/{job_id}/files").json()["files"]
                self.assertEqual(files[0]["file_type"], "source_pdf")

            fake_client = runtime.stage_service.fake_mineru_client
            self.assertEqual(len(fake_client.calls), 1)
            self.assertEqual(fake_client.calls[0]["task_uuids"], [job_id])

    def test_upload_pdf_rejects_when_mineru_token_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir), mineru_api_token=""))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )

        self.assertEqual(response.status_code, 503)
        self.assertIn("MINERU_API_TOKEN", response.json()["detail"])

    def test_upload_pdf_rejects_invalid_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir), mineru_api_token="token-123"))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("bad.pdf", b"not-pdf", "application/pdf")},
                )

        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF", response.json()["detail"])

    def test_upload_pdf_marks_job_failed_when_mineru_submit_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            runtime.stage_service.fake_mineru_client.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                self.assertEqual(response.status_code, 201)
                job_id = response.json()["job_id"]

                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(detail["status"], "failed")
                self.assertEqual(detail["error_code"], "mineru_submit_failed")
                event_stages = [item["stage"] for item in detail["events"]]
                self.assertIn("mineru_submit_failed", event_stages)
                self.assertIn("job_failed", event_stages)

    def test_retry_requeues_failed_pdf_submit_to_mineru_stage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                admin_token="secret-admin",
            )
            runtime.stage_service.fake_mineru_client.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                self.assertEqual(response.status_code, 201)
                job_id = response.json()["job_id"]

                failed_detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(failed_detail["status"], "failed")

                runtime.stage_service.fake_mineru_client.raise_error = False
                retry_response = client.post(
                    f"/api/v1/jobs/{job_id}/retry",
                    data={"reason": "retry-pdf-submit"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(retry_response.status_code, 200)

                reparsed_detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(reparsed_detail["status"], "parsing")
                self.assertEqual(reparsed_detail["mineru_batch_id"], "batch_test_001")

    def test_callback_internal_mode_accepts_and_auto_completes_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                self.assertEqual(callback_response.status_code, 200)

                updated = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(updated["status"], "completed")
                self.assertEqual(updated["mineru_result_zip_url"], "https://mineru.net/result.zip")
                self.assertTrue(updated["result_ready"])
                persisted_job = runtime.job_repository.get_job(job_id)
                self.assertIsNotNone(persisted_job)
                self.assertIsNotNone(persisted_job.source_pdf_context)
                self.assertEqual(persisted_job.source_pdf_context.result_zip_url, "https://mineru.net/result.zip")
                files = runtime.job_file_repository.list_files(job_id)
                self.assertEqual([item.file_type for item in files], ["source_pdf", "parsed_result_package", "result_docx"])

    def test_recover_mineru_result_queries_provider_when_callback_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                admin_token="secret-admin",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                runtime.stage_service.fake_mineru_client.query_data_id = job_id

                recover_response = client.post(
                    f"/api/v1/jobs/{job_id}/recover-mineru-result",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(recover_response.status_code, 200)
                self.assertTrue(recover_response.json()["accepted"])

                updated = client.get(f"/api/v1/jobs/{job_id}").json()

        self.assertEqual(updated["status"], "completed")
        self.assertEqual(updated["mineru_result_zip_url"], "https://mineru.net/result.zip")
        self.assertEqual(runtime.stage_service.fake_mineru_client.query_calls, [{"batch_id": "batch_test_001"}])
        event_stages = [item["stage"] for item in updated["events"]]
        self.assertIn("mineru_result_polled", event_stages)
        self.assertIn("parsed_result_package_recovered", event_stages)
        self.assertIn("job_completed", event_stages)

    def test_pdf_online_flow_downloads_artifacts_after_object_storage_switch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                jobs_artifact_storage_backend="local_object",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                health = client.get("/api/v1/health/ready").json()
                self.assertEqual(health["dependency_checks"]["artifact_storage"], "local_object")

                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                self.assertEqual(callback_response.status_code, 200)

                source_response = client.get(f"/api/v1/jobs/{job_id}/download/source-pdf")
                parsed_response = client.get(f"/api/v1/jobs/{job_id}/download/parsed-result-package")
                result_response = client.get(f"/api/v1/jobs/{job_id}/download/result")
                files_response = client.get(f"/api/v1/jobs/{job_id}/files").json()

            files = {item.file_type: item for item in runtime.job_file_repository.list_files(job_id)}
            object_root = runtime.settings.jobs_artifact_object_store_dir
            object_exists = {
                "source_pdf": (object_root / f"jobs/{job_id}/input/source.pdf").exists(),
                "parsed_result_package": (object_root / f"jobs/{job_id}/input/parsed-result.zip").exists(),
                "result_docx": (object_root / f"jobs/{job_id}/output/result.docx").exists(),
            }

        self.assertEqual(source_response.status_code, 200)
        self.assertEqual(source_response.content, b"%PDF-1.4\nbody")
        self.assertEqual(parsed_response.status_code, 200)
        self.assertEqual(parsed_response.content, b"fake-parsed-result-zip")
        self.assertEqual(result_response.status_code, 200)
        self.assertEqual(result_response.content, b"fake-docx")
        self.assertEqual([item["storage_backend"] for item in files_response["files"]], ["object", "object", "object"])
        self.assertEqual(files["source_pdf"].object_key, f"jobs/{job_id}/input/source.pdf")
        self.assertEqual(files["parsed_result_package"].object_key, f"jobs/{job_id}/input/parsed-result.zip")
        self.assertEqual(files["result_docx"].object_key, f"jobs/{job_id}/output/result.docx")
        self.assertTrue(object_exists["source_pdf"])
        self.assertTrue(object_exists["parsed_result_package"])
        self.assertTrue(object_exists["result_docx"])

    def test_callback_public_mode_requires_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                public_deployment_mode="single_tenant_public",
                mineru_callback_token="secret-token",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                payload, _content = build_callback_payload(
                    batch_id="batch_x",
                    data_id="job_x",
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)

        self.assertEqual(response.status_code, 403)

    def test_callback_public_mode_accepts_query_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                public_deployment_mode="single_tenant_public",
                mineru_callback_token="secret-token",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                response = client.post(
                    "/api/v1/mineru-callbacks/result?callback_token=secret-token",
                    json=payload,
                )
                self.assertEqual(response.status_code, 200)
                updated = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(updated["status"], "completed")

    def test_callback_public_mode_missing_token_config_returns_503(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                public_deployment_mode="single_tenant_public",
                mineru_callback_token="",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                payload, _content = build_callback_payload(
                    batch_id="batch_x",
                    data_id="job_x",
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)

        self.assertEqual(response.status_code, 503)

    def test_callback_checksum_uses_seed_and_uid_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                mineru_callback_url="https://example.com/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                seed = detail["mineru_callback_seed"]
                checksum = hashlib.sha256(f"mineru-user-1{seed}{content}".encode("utf-8")).hexdigest()
                payload["checksum"] = checksum

                response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                self.assertEqual(response.status_code, 200)
                updated = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(updated["status"], "completed")

    def test_callback_rejects_invalid_checksum_without_leaving_stage_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                mineru_callback_url="https://example.com/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                payload["checksum"] = "bad-checksum"

                response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                updated = client.get(f"/api/v1/jobs/{job_id}").json()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(updated["status"], "parsing")
        self.assertEqual(runtime.stage_message_store.list_replayable_stage_messages(), [])

    def test_callback_rejects_untrusted_result_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="http://evil.example/result.zip",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                updated = client.get(f"/api/v1/jobs/{job_id}").json()

        self.assertEqual(response.status_code, 400)
        self.assertIn("https", response.json()["detail"])
        self.assertEqual(updated["status"], "parsing")
        self.assertIsNone(updated["mineru_result_zip_url"])
        self.assertEqual(runtime.stage_message_store.list_replayable_stage_messages(), [])

    def test_callback_failed_state_marks_job_failed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="failed",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                self.assertEqual(response.status_code, 200)
                updated = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(updated["status"], "failed")
                self.assertEqual(updated["error_code"], "mineru_failed")

    def test_callback_matches_data_id_before_batch_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                first_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("first.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                second_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("second.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                first_job_id = first_response.json()["job_id"]
                second_job_id = second_response.json()["job_id"]

                first_detail = client.get(f"/api/v1/jobs/{first_job_id}").json()
                second_detail = client.get(f"/api/v1/jobs/{second_job_id}").json()
                second_job = runtime.job_repository.get_job(second_job_id)
                self.assertIsNotNone(second_job)
                runtime.job_repository.update_job(
                    second_job_id,
                    **build_source_pdf_context_patch(second_job, batch_id=first_detail["mineru_batch_id"]),
                )

                payload, _content = build_callback_payload(
                    batch_id=first_detail["mineru_batch_id"],
                    data_id=second_detail["mineru_data_id"],
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)

                self.assertEqual(response.status_code, 200)
                first_updated = client.get(f"/api/v1/jobs/{first_job_id}").json()
                second_updated = client.get(f"/api/v1/jobs/{second_job_id}").json()
                self.assertEqual(first_updated["status"], "parsing")
                self.assertEqual(second_updated["status"], "completed")

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

    def test_upload_pdf_submits_to_mineru_and_enters_parsing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(response.status_code, 201)
                job_id = response.json()["job_id"]

                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(detail["status"], "parsing")
                self.assertEqual(detail["source_kind"], "source_pdf")
                self.assertEqual(detail["mineru_batch_id"], "batch_test_001")
                self.assertEqual(detail["mineru_data_id"], job_id)
                self.assertEqual(detail["mineru_status"], "submitted")

                files = client.get(f"/api/v1/jobs/{job_id}/files").json()["files"]
                self.assertEqual(files[0]["file_type"], "source_pdf")

            fake_client = runtime.stage_service.fake_mineru_client
            self.assertEqual(len(fake_client.calls), 1)
            self.assertEqual(fake_client.calls[0]["task_uuids"], [job_id])

    def test_upload_pdf_rejects_when_mineru_token_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir), mineru_api_token=""))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )

        self.assertEqual(response.status_code, 503)
        self.assertIn("MINERU_API_TOKEN", response.json()["detail"])

    def test_upload_pdf_rejects_invalid_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir), mineru_api_token="token-123"))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("bad.pdf", b"not-pdf", "application/pdf")},
                )

        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF", response.json()["detail"])

    def test_upload_pdf_marks_job_failed_when_mineru_submit_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            runtime.stage_service.fake_mineru_client.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                self.assertEqual(response.status_code, 201)
                job_id = response.json()["job_id"]

                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(detail["status"], "failed")
                self.assertEqual(detail["error_code"], "mineru_submit_failed")
                event_stages = [item["stage"] for item in detail["events"]]
                self.assertIn("mineru_submit_failed", event_stages)
                self.assertIn("job_failed", event_stages)

    def test_retry_requeues_failed_job_with_admin_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            runtime.stage_service.conversion_entrypoint.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]

                failed_detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(failed_detail["status"], "failed")

                runtime.stage_service.conversion_entrypoint.raise_error = False
                retry_response = client.post(
                    f"/api/v1/jobs/{job_id}/retry",
                    data={"reason": "rerun"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(retry_response.status_code, 200)
                self.assertEqual(retry_response.json()["operation"], "retry")

                detail_response = client.get(f"/api/v1/jobs/{job_id}")
                self.assertEqual(detail_response.status_code, 200)
                self.assertEqual(detail_response.json()["status"], "completed")
                audit_events = runtime.audit_event_repository.list_audit_events()
                self.assertEqual([event.action for event in audit_events], ["job.retry"])
                self.assertEqual(audit_events[0].target_id, job_id)
                self.assertEqual(audit_events[0].reason, "rerun")

    def test_cancel_queued_job_with_admin_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            runtime.stage_service.dispatch_message = lambda _message_id: None
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]

                queued_detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(queued_detail["status"], "queued")

                cancel_response = client.post(
                    f"/api/v1/jobs/{job_id}/cancel",
                    data={"reason": "stop"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(cancel_response.status_code, 200)
                self.assertEqual(cancel_response.json()["status"], "canceled")
                self.assertEqual(runtime.stage_message_store.list_replayable_stage_messages(), [])
                audit_events = runtime.audit_event_repository.list_audit_events()
                self.assertEqual([event.action for event in audit_events], ["job.cancel"])
                self.assertEqual(audit_events[0].target_id, job_id)
                self.assertEqual(audit_events[0].reason, "stop")

    def test_job_ops_default_admin_only_checks_no_token_jobs_token_and_admin_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_access_mode="token",
                jobs_access_token="jobs-token",
                admin_token="secret-admin",
            )
            app = create_app(runtime)
            job = JobRecord(
                id="job_ops_auth",
                source_filename="sample.zip",
                status="completed",
                progress=100,
                result_ready=True,
                completed_at=utc_now(),
            )
            runtime.job_repository.create_job(job)

            with TestClient(app) as client:
                no_token_response = client.post(
                    f"/api/v1/jobs/{job.id}/cleanup-local-files",
                    data={"reason": "auth-check"},
                )
                jobs_token_response = client.post(
                    f"/api/v1/jobs/{job.id}/cleanup-local-files",
                    data={"reason": "auth-check"},
                    headers={"X-Jobs-Token": "jobs-token"},
                )
                admin_token_response = client.post(
                    f"/api/v1/jobs/{job.id}/cleanup-local-files",
                    data={"reason": "auth-check"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(no_token_response.status_code, 403)
        self.assertEqual(no_token_response.json()["detail"], "admin token 校验失败。")
        self.assertEqual(jobs_token_response.status_code, 403)
        self.assertEqual(jobs_token_response.json()["detail"], "admin token 校验失败。")
        self.assertEqual(admin_token_response.status_code, 200)
        self.assertEqual([event.action for event in audit_events], ["job.cleanup_local_files"])
        self.assertEqual(audit_events[0].actor_role, "admin")
        self.assertEqual(audit_events[0].reason, "auth-check")

    def test_job_ops_can_follow_jobs_access_mode_when_configured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_access_mode="token",
                jobs_access_token="jobs-token",
                jobs_ops_access_mode="jobs",
            )
            app = create_app(runtime)
            job = JobRecord(
                id="job_ops_jobs_mode",
                source_filename="sample.zip",
                status="completed",
                progress=100,
                result_ready=True,
                completed_at=utc_now(),
            )
            runtime.job_repository.create_job(job)

            with TestClient(app) as client:
                denied_response = client.post(
                    f"/api/v1/jobs/{job.id}/cleanup-local-files",
                    data={"reason": "auth-check"},
                )
                accepted_response = client.post(
                    f"/api/v1/jobs/{job.id}/cleanup-local-files",
                    data={"reason": "auth-check"},
                    headers={"X-Jobs-Token": "jobs-token"},
                )
                audit_events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(denied_response.status_code, 403)
        self.assertEqual(accepted_response.status_code, 200)
        self.assertEqual([event.action for event in audit_events], ["job.cleanup_local_files"])
        self.assertEqual(audit_events[0].actor_role, "jobs")
        self.assertEqual(audit_events[0].actor_id, "jobs-client")

    def test_cleanup_local_files_preserves_registered_artifacts_and_removes_work_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            app = create_app(runtime)
            job = JobRecord(
                id="job_cleanup",
                source_filename="sample.zip",
                status="completed",
                progress=100,
                result_ready=True,
                completed_at=utc_now(),
            )
            runtime.job_repository.create_job(job)
            job_paths = build_job_paths(runtime.settings.data_path, job.id)
            ensure_job_dirs(job_paths)
            job_paths.source_package.write_bytes(b"zip")
            job_paths.result_docx.write_bytes(b"docx")
            (job_paths.work_dir / "temp.txt").write_text("tmp", encoding="utf-8")
            runtime.job_file_repository.upsert_file(job.id, JobFile(file_type="source_package", path="input/source.zip"))
            runtime.job_file_repository.upsert_file(job.id, JobFile(file_type="result_docx", path="output/result.docx"))

            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/jobs/{job.id}/cleanup-local-files",
                    data={"reason": "cleanup"},
                    headers={"X-Admin-Token": "secret-admin"},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn(str(job_paths.work_dir), payload["deleted_paths"])
            skipped = {item["path"]: item["reason"] for item in payload["skipped_paths"]}
            self.assertEqual(skipped[str(job_paths.source_package)], "registered_local_artifact")
            self.assertEqual(skipped[str(job_paths.result_docx)], "registered_local_artifact")
            self.assertFalse(job_paths.work_dir.exists())
