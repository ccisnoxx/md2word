from __future__ import annotations

from typing import Any

from app.conversion.runtime import llm_client
from app.core.config import Settings
from app.schemas.api_v1 import HealthReadyResponse


class HealthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _is_writable(self) -> bool:
        self.settings.data_path.mkdir(parents=True, exist_ok=True)
        probe = self.settings.data_path / ".write_probe"
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
        stage_spool_files = list(self.settings.stage_messages_dir.glob("*.json")) if self.settings.stage_messages_dir.exists() else []
        translation_client_configured = bool(self.settings.openai_api_key) and llm_client.OpenAI is not None

        checks: dict[str, Any] = {
            "configured_repository_backend": "file",
            "effective_repository_backend": "file",
            "jobs_dir_exists": self.settings.jobs_dir.exists(),
            "jobs_dir_writable": self._is_writable(),
            "stage_spool_dir_exists": self.settings.stage_messages_dir.exists(),
            "stage_spool_pending_messages": len(stage_spool_files),
            "tmp_dir_exists": self.settings.tmp_dir.exists(),
            "template_docx_exists": template_path is not None and template_path.exists(),
            "layout_config_exists": layout_config_path is not None and layout_config_path.exists(),
            "subscript_config_exists": subscript_config_path is not None and subscript_config_path.exists(),
            "translation_prompt_exists": translation_prompt_exists,
            "mineru_api_token_configured": bool(self.settings.mineru_api_token),
            "openai_api_key_configured": bool(self.settings.openai_api_key),
            "openai_base_url_configured": bool(self.settings.openai_base_url),
            "openai_model": self.settings.openai_model,
            "default_translation_mode": self.settings.default_translation_mode,
            "translation_client_configured": translation_client_configured,
            "translation_available": translation_client_configured and translation_prompt_exists,
        }

        missing_steps: list[str] = []
        if not checks["jobs_dir_exists"]:
            missing_steps.append("jobs_dir_missing")
        if not checks["jobs_dir_writable"]:
            missing_steps.append("data_dir_not_writable")
        if not checks["stage_spool_dir_exists"]:
            missing_steps.append("stage_spool_dir_missing")
        if not checks["tmp_dir_exists"]:
            missing_steps.append("tmp_dir_missing")
        if not checks["template_docx_exists"]:
            missing_steps.append("default_template_missing")
        if not checks["layout_config_exists"]:
            missing_steps.append("layout_config_missing")
        if not checks["subscript_config_exists"]:
            missing_steps.append("subscript_config_missing")
        if not checks["translation_prompt_exists"]:
            missing_steps.append("translation_prompt_missing")

        checks["deployment_init_ready"] = not missing_steps
        checks["deployment_init_missing_steps"] = missing_steps
        if not checks["translation_available"]:
            if not checks["openai_api_key_configured"]:
                checks["translation_unavailable_reason"] = "OPENAI_API_KEY 未配置"
            elif llm_client.OpenAI is None:
                checks["translation_unavailable_reason"] = "openai Python SDK 不可用"
            elif not checks["translation_prompt_exists"]:
                checks["translation_unavailable_reason"] = "translation_en2zh prompt 文件缺失"
        return checks

    def build_ready_response(self) -> HealthReadyResponse:
        return HealthReadyResponse(
            status="ok",
            app_name=self.settings.app_name,
            jobs_dir=str(self.settings.jobs_dir),
            dependency_checks=self.build_dependency_checks(),
        )
