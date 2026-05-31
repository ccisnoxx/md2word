from __future__ import annotations

from pathlib import Path

from app.conversion.contracts import ConversionEntrypoint, ConversionRequest
from app.conversion.service import ConversionService
from app.core.config import Settings
from app.domains.jobs.models import JobRecord
from app.domains.jobs.paths import JobPaths
from app.domains.translation.models import TranslationProfileSnapshot


def build_job_conversion_request(
    *,
    job: JobRecord,
    job_paths: JobPaths,
    settings: Settings,
    package_path: Path | None = None,
    template_path: Path | None = None,
    subscript_config_path: Path | None = None,
    translation_profile: TranslationProfileSnapshot | None = None,
) -> ConversionRequest:
    translation_model = (
        translation_profile.model
        if translation_profile is not None and translation_profile.model
        else settings.openai_model
    )
    return ConversionRequest(
        job_id=job.id,
        package_path=package_path if package_path is not None else job_paths.source_package,
        output_path=job_paths.result_docx,
        template_path=template_path if template_path is not None else settings.default_template_path,
        subscript_config_path=subscript_config_path if subscript_config_path is not None else settings.subscript_config_path,
        translation_mode=job.translation_mode,
        document_language=job.document_language,
        use_mineru_header_footer=job.use_mineru_header_footer,
        translation_model=translation_model,
        translation_api_key=settings.openai_api_key or None,
        translation_base_url=settings.openai_base_url or None,
        translation_target_language=(
            translation_profile.target_language
            if translation_profile is not None
            else "zh-CN"
        ),
        translation_domain=(
            translation_profile.domain
            if translation_profile is not None
            else "electronics engineering technical document"
        ),
        translation_prompt_version=(
            translation_profile.prompt_version
            if translation_profile is not None
            else "translation-minimal-v1"
        ),
        translation_max_pages=(
            translation_profile.max_pages_per_batch
            if translation_profile is not None
            else settings.translation_max_pages
        ),
        translation_max_chars=(
            translation_profile.max_chars_per_batch
            if translation_profile is not None
            else settings.translation_max_chars
        ),
        translation_profile=translation_profile,
        translation_request_output=job_paths.translation_request if job.translation_mode == "en2zh" else None,
        translation_trace_output=job_paths.translation_trace if job.translation_mode == "en2zh" else None,
    )


def create_conversion_entrypoint() -> ConversionEntrypoint:
    return ConversionService()
