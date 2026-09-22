# File: app/core/config.py
# Purpose: 定义 FastAPI 后端运行配置、集成开关和路径派生规则。

from __future__ import annotations

from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """集中定义环境变量驱动的运行配置和派生路径。"""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "md2word_file"
    app_env: str = "dev"
    app_version: str = "dev"
    deployment_id: str = ""
    log_format: Literal["text", "json"] = "text"
    app_cors_origins: str = "http://127.0.0.1:3000,http://localhost:3000"
    data_dir: str = "var"
    # file 保持本地开发默认值；database 表示 sqlite，mysql 需显式配置。
    jobs_repository_backend: Literal["file", "database", "mysql"] = "file"
    jobs_metadata_database_path: str = "var/metadata.sqlite3"
    jobs_mysql_host: str = "127.0.0.1"
    jobs_mysql_port: int = 3306
    jobs_mysql_user: str = "md2word"
    jobs_mysql_password: str = ""
    jobs_mysql_database: str = "md2word"
    jobs_mysql_charset: str = "utf8mb4"
    jobs_mysql_connect_timeout_seconds: int = 10
    jobs_artifact_storage_backend: Literal["local_file", "local_object", "s3"] = "local_file"
    jobs_artifact_object_store_path: str = "var/object_artifacts"
    jobs_artifact_s3_bucket: str = ""
    jobs_artifact_s3_endpoint_url: str = ""
    jobs_artifact_s3_region: str = "us-east-1"
    jobs_artifact_s3_access_key_id: str = ""
    jobs_artifact_s3_secret_access_key: str = ""
    jobs_artifact_s3_key_prefix: str = ""
    jobs_artifact_s3_public_base_url: str = ""
    jobs_artifact_s3_download_mode: Literal["redirect", "stream"] = "redirect"
    jobs_artifact_s3_presign_expires_seconds: int = 3600
    jobs_worker_mode: Literal["in_process", "external"] = "in_process"
    jobs_worker_poll_interval_seconds: float = 2.0
    jobs_worker_id: str = "md2word-worker"
    stage_message_lease_seconds: int = 900
    jobs_upload_max_bytes: int = 52_428_800
    oss_upload_presign_expires_seconds: int = 600
    oss_download_presign_expires_seconds: int = 600
    oss_file_retention_days: int = 90
    pdf_upload_max_pages: int = 200
    p0_document_job_timeout_seconds: int = 1200
    p0_document_job_max_retries: int = 2
    document_jobs_worker_backend: Literal["disabled", "celery", "eager"] = "disabled"
    document_jobs_celery_broker_url: str = "redis://127.0.0.1:6379/0"
    document_jobs_celery_result_backend: str = ""
    document_jobs_celery_queue: str = "document-jobs"
    document_jobs_translation_batch_celery_queue: str = "document-translation-batches"
    translation_provider_batch_max_concurrency_per_job: int = 4
    translation_provider_batch_lease_seconds: int = 900
    translation_provider_batch_max_attempts: int = 2
    jobs_access_mode: Literal["open", "token", "admin"] = "open"
    jobs_access_token: str = ""
    jobs_ops_access_mode: Literal["jobs", "admin"] = "admin"
    admin_token: str = ""
    ops_alert_destinations_json: str = "[]"
    integration_alert_delivery_enabled: bool = False
    integration_alert_delivery_dry_run: bool = True
    integration_alert_delivery_kill_switch: bool = False
    integration_provider_cancellation_enabled: bool = False
    integration_provider_cancellation_dry_run: bool = True
    integration_provider_cancellation_kill_switch: bool = False
    integration_s3_deletion_enabled: bool = False
    integration_s3_deletion_dry_run: bool = True
    integration_s3_deletion_kill_switch: bool = False
    integration_cleanup_scheduler_execute_enabled: bool = False
    integration_cleanup_scheduler_execute_dry_run: bool = True
    integration_cleanup_scheduler_execute_kill_switch: bool = False
    files_quota_policy_enabled: bool = False
    files_quota_policy_dry_run: bool = True
    files_quota_policy_kill_switch: bool = False
    files_quota_bytes: int = 0
    files_quota_warning_threshold_ratio: float = 0.8
    files_quota_block_threshold_ratio: float = 1.0
    auth_jwt_secret_key: str = ""
    auth_jwt_algorithm: Literal["HS256"] = "HS256"
    auth_access_token_expire_minutes: int = 120
    auth_internal_users_file: str = ""
    auth_internal_users_json: str = ""
    default_translation_mode: Literal["direct", "en2zh", "ru2zh", "zh2en", "zh2ru"] = "direct"
    mineru_api_token: str = ""
    mineru_model_version: str = "vlm"
    mineru_language: str = "en"
    mineru_enable_formula: bool = True
    mineru_enable_table: bool = True
    mineru_callback_url: str = ""
    mineru_uid: str = ""
    mineru_result_host_allowlist: str = "mineru.net,cdn-mineru.openxlab.org.cn"
    public_deployment_mode: Literal["internal", "single_tenant_public"] = "internal"
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = "deepseek-v4-flash"
    translation_provider_backend: Literal["disabled", "openai_compatible"] = "disabled"
    translation_provider_timeout_seconds: float = 120.0
    translation_provider_max_output_tokens: int = 12000
    ai_provider_config_path: str = "var/config/ai_provider_config.json"
    translation_debug_archive_enabled: bool = False
    translation_debug_archive_retention_days: int = 1
    translation_max_pages: int = 20
    translation_max_chars: int = 60_000
    translation_terms_path: str = "resources/term_rules/translation_terms.csv"
    default_translation_term_version_id: str = "en2zh@v1"
    default_template_id: str = "default"
    templates_manifest_path: str = "resources/template_configs/templates_manifest.yaml"
    templates_storage_path: str = "var/config/templates"
    template_state_path: str = "var/config/template_state.json"
    term_rules_seed_path: str = "resources/term_rules/term_rules.v2.yaml"
    term_rules_store_path: str = "var/config/term_rules_store.json"
    term_rules_runtime_yaml_path: str = "var/config/runtime_subscripts_dictionary.yaml"

    @property
    def root_dir(self) -> Path:
        return REPO_ROOT

    @property
    def data_path(self) -> Path:
        return (self.root_dir / self.data_dir).resolve()

    @property
    def jobs_dir(self) -> Path:
        return self.data_path / "jobs"

    @property
    def stage_messages_dir(self) -> Path:
        return self.data_path / "stage_messages"

    @property
    def tmp_dir(self) -> Path:
        return self.data_path / "tmp"

    @property
    def jobs_metadata_database_file(self) -> Path:
        return self._resolve_runtime_data_path(self.jobs_metadata_database_path, "metadata.sqlite3")

    @property
    def jobs_artifact_object_store_dir(self) -> Path:
        return self._resolve_runtime_data_path(self.jobs_artifact_object_store_path, "object_artifacts")

    def _resolve_config_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate
        return (self.root_dir / candidate).resolve()

    @property
    def auth_internal_users_file_path(self) -> Path | None:
        """返回内部账号配置文件绝对路径；未配置文件入口时返回 None。"""

        raw_path = self.auth_internal_users_file.strip()
        if not raw_path:
            return None
        return self._resolve_config_path(raw_path)

    @property
    def auth_internal_users_source_label(self) -> str:
        """返回当前内部账号配置来源名称，用于错误信息。"""

        if self.auth_internal_users_file.strip():
            return "AUTH_INTERNAL_USERS_FILE"
        return "AUTH_INTERNAL_USERS_JSON"

    def read_auth_internal_users_json(self) -> str:
        """读取内部账号配置；优先读取文件，兼容旧的 JSON 环境变量。"""

        file_path = self.auth_internal_users_file_path
        if file_path is None:
            return self.auth_internal_users_json
        return file_path.read_text(encoding="utf-8")

    def _resolve_runtime_data_path(self, raw_path: str, fallback_relative_to_data: str) -> Path:
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate
        raw_text = raw_path.strip()
        if raw_text.startswith("var/"):
            suffix = raw_text[len("var/"):]
            return (self.data_path / suffix).resolve()
        return (self.data_path / fallback_relative_to_data).resolve()

    @property
    def cors_origins(self) -> list[str]:
        values = [item.strip() for item in self.app_cors_origins.split(",")]
        return [item for item in values if item]

    @property
    def template_candidates(self) -> tuple[Path, ...]:
        return (
            self.root_dir / "resources" / "templates" / "default" / "datasheet_template_v2.docx",
        )

    @property
    def layout_config_candidates(self) -> tuple[Path, ...]:
        return (
            self.root_dir / "resources" / "template_configs" / "datasheet_template.yaml",
        )

    @property
    def subscript_config_candidates(self) -> tuple[Path, ...]:
        return (
            self.term_rules_runtime_yaml_file,
            self.root_dir / "resources" / "term_rules" / "subscripts_dictionary.yaml",
        )

    @property
    def templates_manifest_file(self) -> Path:
        return self._resolve_config_path(self.templates_manifest_path)

    @property
    def templates_storage_dir(self) -> Path:
        return self._resolve_runtime_data_path(self.templates_storage_path, "config/templates")

    @property
    def template_state_file(self) -> Path:
        return self._resolve_runtime_data_path(self.template_state_path, "config/template_state.json")

    @property
    def term_rules_seed_file(self) -> Path:
        return self._resolve_config_path(self.term_rules_seed_path)

    @property
    def term_rules_store_file(self) -> Path:
        return self._resolve_runtime_data_path(self.term_rules_store_path, "config/term_rules_store.json")

    @property
    def term_rules_runtime_yaml_file(self) -> Path:
        return self._resolve_runtime_data_path(self.term_rules_runtime_yaml_path, "config/runtime_subscripts_dictionary.yaml")

    @property
    def translation_terms_file(self) -> Path:
        return self._resolve_config_path(self.translation_terms_path)

    @property
    def ai_provider_config_file(self) -> Path:
        return self._resolve_runtime_data_path(self.ai_provider_config_path, "config/ai_provider_config.json")

    @property
    def mineru_config_file(self) -> Path:
        """返回 API 与 Worker 共享的 MinerU 运行时配置文件。"""

        return self.data_path / "config" / "mineru_config.json"

    @property
    def default_template_path(self) -> Path | None:
        for candidate in self.template_candidates:
            if candidate.exists():
                return candidate.resolve()
        return None

    @property
    def layout_config_path(self) -> Path | None:
        for candidate in self.layout_config_candidates:
            if candidate.exists():
                return candidate.resolve()
        return None

    @property
    def subscript_config_path(self) -> Path | None:
        for candidate in self.subscript_config_candidates:
            if candidate.exists():
                return candidate.resolve()
        return None

    @property
    def allowed_mineru_result_hosts(self) -> tuple[str, ...]:
        hosts: list[str] = []
        for item in self.mineru_result_host_allowlist.split(","):
            host = item.strip().lower()
            if host and host not in hosts:
                hosts.append(host)
        return tuple(hosts)
