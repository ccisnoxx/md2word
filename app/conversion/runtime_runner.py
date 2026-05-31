from __future__ import annotations

from pathlib import Path

from docx import Document
from loguru import logger

from app.conversion.runtime import llm_client, translation_runtime
from app.conversion.runtime.input_adapter_runtime import load_pages, materialize_input
from app.conversion.runtime.page_layout_runtime import build_document

from app.conversion.runtime_helpers import (
    apply_document_language_overrides,
    build_translation_config,
    load_render_config,
    load_translations_from_payload,
    resolve_document_language,
    resolve_output_path,
    resolve_template_path,
)
from app.conversion.runtime_config import APP_CONFIG


DEFAULT_TEMPLATE_CANDIDATES = (
    Path("resources/templates/default/datasheet_template.docx"),
    Path(__file__).resolve().parents[2] / "resources" / "templates" / "default" / "datasheet_template.docx",
)


def run_conversion(
    *,
    job_id: str | None = None,
    input_path: str,
    output_path: str | None,
    template_path: str | None,
    subscript_config: str | None,
    no_template: bool,
    use_mineru_header_footer: bool,
    document_language: str = "auto",
    translation_mode: str = "direct",
    translation_request_output: str | None = None,
    translation_response: str | None = None,
    translation_model: str = llm_client.DEFAULT_MODEL,
    translation_api_key: str | None = None,
    translation_base_url: str | None = None,
    translation_target_language: str = translation_runtime.DEFAULT_TARGET_LANGUAGE,
    translation_domain: str = translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
    translation_prompt_version: str = translation_runtime.TRANSLATION_PROMPT_VERSION,
    translation_max_pages: int = APP_CONFIG.translation_max_pages,
    translation_max_chars: int = APP_CONFIG.translation_max_chars,
    translation_profile: dict | None = None,
    translation_trace_output: str | None = None,
) -> None:
    """
    Shared conversion entrypoint used by both CLI and FastAPI-facing adapters.
    """
    original_input = Path(input_path).expanduser().resolve()
    resolved_output_path = resolve_output_path(original_input, output_path)
    resolved_template_path = None if no_template else resolve_template_path(template_arg=template_path, default_candidates=DEFAULT_TEMPLATE_CANDIDATES)
    resolved_subscript_config = Path(subscript_config).expanduser().resolve() if subscript_config else None
    resolved_translation_request_output = (
        Path(translation_request_output).expanduser().resolve() if translation_request_output else None
    )
    resolved_translation_response = Path(translation_response).expanduser().resolve() if translation_response else None
    resolved_translation_trace_output = (
        Path(translation_trace_output).expanduser().resolve() if translation_trace_output else None
    )

    logger.info("start conversion input={} output={}", original_input, resolved_output_path)
    logger.debug(
        "conversion options template={} subscript_config={} no_template={} use_mineru_header_footer={} document_language={} translation_mode={} translation_request_output={} translation_response={} translation_trace_output={} translation_model={} translation_api_key_present={} translation_base_url={}",
        resolved_template_path,
        resolved_subscript_config,
        no_template,
        use_mineru_header_footer,
        document_language,
        translation_mode,
        resolved_translation_request_output,
        resolved_translation_response,
        resolved_translation_trace_output,
        translation_model,
        bool(translation_api_key),
        translation_base_url,
    )

    template_document = Document(str(resolved_template_path)) if resolved_template_path else None
    with materialize_input(original_input) as package_root:
        pages, source_path = load_pages(package_root)
        translation_config = build_translation_config(
            max_pages=translation_max_pages,
            max_chars=translation_max_chars,
            target_language=translation_target_language,
            domain=translation_domain,
            prompt_version=translation_prompt_version,
        )
        if translation_mode == "en2zh":
            if resolved_translation_request_output:
                payload = translation_runtime.write_translation_request_file(pages, resolved_translation_request_output, translation_config)
                logger.info(
                    "translation request output={} batches={}",
                    resolved_translation_request_output,
                    len(payload.get("batches", [])),
                )
            if resolved_translation_response:
                payload = translation_runtime.build_translation_request_payload(pages, translation_config)
                translations = translation_runtime.load_translation_response_file(resolved_translation_response)
                if resolved_translation_trace_output:
                    translation_runtime.write_translation_trace_file(
                        pages,
                        resolved_translation_trace_output,
                        request_payload=payload,
                        translations=translations,
                        config=translation_config,
                        job_id=job_id,
                        model=translation_model,
                        translation_profile=translation_profile,
                    )
                translation_runtime.apply_translation_responses(pages, translations)
                logger.info("translation response applied items={}", len(translations))
            else:
                payload = translation_runtime.build_translation_request_payload(pages, translation_config)
                llm_response = llm_client.translate_payload(
                    payload,
                    llm_client.LLMClientConfig(
                        model=translation_model,
                        api_key=translation_api_key,
                        base_url=translation_base_url,
                    ),
                )
                translations = load_translations_from_payload(llm_response)
                if resolved_translation_trace_output:
                    translation_runtime.write_translation_trace_file(
                        pages,
                        resolved_translation_trace_output,
                        request_payload=payload,
                        translations=translations,
                        config=translation_config,
                        job_id=job_id,
                        model=translation_model,
                        translation_profile=translation_profile,
                    )
                translation_runtime.apply_translation_responses(pages, translations)
                logger.info(
                    "llm translation applied batches={} items={}",
                    len(llm_response.get("batches", [])),
                    len(translations),
                )
        elif resolved_translation_request_output or resolved_translation_response or resolved_translation_trace_output:
            logger.warning("translation_mode=direct 时忽略 translation_request_output / translation_response / translation_trace_output")

        preferred_document_language = document_language
        if translation_mode == "en2zh" and document_language == "auto":
            preferred_document_language = "zh"

        resolved_document_language = resolve_document_language(pages, preferred=preferred_document_language)
        render_config = apply_document_language_overrides(
            load_render_config(
                template_document=template_document,
                subscript_config=resolved_subscript_config,
                use_mineru_header_footer=use_mineru_header_footer,
            ),
            resolved_document_language,
        )
        logger.info("document_language={}", resolved_document_language)
        document = build_document(pages, render_config, template_document)
        document.core_properties.title = source_path.stem
        document.save(resolved_output_path)

    logger.info("source={}", source_path)
    logger.info("output={}", resolved_output_path)
    logger.info("pages={}", len(pages))
    logger.info("template={}", resolved_template_path if resolved_template_path else "none")
