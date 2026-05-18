from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "md2word_file"
    app_env: str = "dev"
    app_cors_origins: str = "http://127.0.0.1:3000,http://localhost:3000"
    data_dir: str = "data"
    jobs_upload_max_bytes: int = 52_428_800
    jobs_access_mode: Literal["open", "token", "admin"] = "open"
    jobs_access_token: str = ""
    admin_token: str = ""
    default_translation_mode: Literal["direct", "en2zh"] = "direct"
    mineru_api_token: str = ""
    mineru_model_version: str = "vlm"
    mineru_language: str = "en"
    mineru_enable_formula: bool = True
    mineru_enable_table: bool = True
    mineru_callback_url: str = ""
    mineru_uid: str = ""
    mineru_callback_token: str = ""
    mineru_callback_token_query_name: str = "callback_token"
    mineru_result_host_allowlist: str = "mineru.net,cdn-mineru.openxlab.org.cn"
    public_deployment_mode: Literal["internal", "single_tenant_public"] = "internal"
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = "deepseek-v4-flash"
    translation_max_pages: int = 20
    translation_max_chars: int = 60_000
    default_template_id: str = "default"

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
    def cors_origins(self) -> list[str]:
        values = [item.strip() for item in self.app_cors_origins.split(",")]
        return [item for item in values if item]

    @property
    def template_candidates(self) -> tuple[Path, ...]:
        return (
            self.root_dir / "template" / "datasheet_template.docx",
            self.root_dir / "templates" / "datasheet_template.docx",
        )

    @property
    def layout_config_candidates(self) -> tuple[Path, ...]:
        return (
            self.root_dir / "template_configs" / "datasheet_template.yaml",
        )

    @property
    def subscript_config_candidates(self) -> tuple[Path, ...]:
        return (
            self.root_dir / "template_configs" / "subscripts_dictionary.yaml",
        )

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
