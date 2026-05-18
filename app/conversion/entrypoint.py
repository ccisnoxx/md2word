from __future__ import annotations

from app.conversion.contracts import ConversionEntrypoint, ConversionRequest
from app.conversion.service import ConversionService
from app.core.config import Settings
from app.core.job_models import JobRecord
from app.core.job_paths import JobPaths


def build_job_conversion_request(
    *,
    job: JobRecord,
    job_paths: JobPaths,
    settings: Settings,
    template_path: Path | None = None,
    subscript_config_path: Path | None = None,
) -> ConversionRequest:
    return ConversionRequest(
        job_id=job.id,
        package_path=job_paths.source_package,
        output_path=job_paths.result_docx,
        template_path=template_path if template_path is not None else settings.default_template_path,
        subscript_config_path=subscript_config_path if subscript_config_path is not None else settings.subscript_config_path,
        translation_mode=job.translation_mode,
        document_language=job.document_language,
        use_mineru_header_footer=job.use_mineru_header_footer,
        translation_model=settings.openai_model,
        translation_api_key=settings.openai_api_key or None,
        translation_base_url=settings.openai_base_url or None,
        translation_max_pages=settings.translation_max_pages,
        translation_max_chars=settings.translation_max_chars,
        translation_request_output=job_paths.translation_request if job.translation_mode == "en2zh" else None,
    )


def create_conversion_entrypoint() -> ConversionEntrypoint:
    return ConversionService()
