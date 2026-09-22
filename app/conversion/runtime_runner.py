from __future__ import annotations

# app/conversion/runtime_runner.py: legacy MinerU 输出到 DOCX 转换链路的共享运行入口。

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from docx import Document
from docx.shared import Mm, Pt
from loguru import logger

from app.conversion import runtime_helpers, runtime_models, runtime_rendering_api
from app.conversion.runtime import (
    input_adapter_runtime,
    llm_client,
    page_layout_runtime,
    page_repair_runtime,
    render_config_runtime,
    text_rendering,
    translation_runtime,
)
from app.conversion.runtime.input_adapter_runtime import load_pages, materialize_input
from app.conversion.runtime.page_layout_runtime import build_document

from app.conversion.docx_rules.text_semantics import PRODUCT_TITLE_RE
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
from app.domains.translation.modes import is_translation_mode, language_pair_for_translation_mode


DEFAULT_TEMPLATE_CANDIDATES = (
    Path("resources/templates/default/datasheet_template_v2.docx"),
    Path(__file__).resolve().parents[2] / "resources" / "templates" / "default" / "datasheet_template_v2.docx",
)
DEFAULT_SUBSCRIPT_CONFIG_CANDIDATES = (
    Path("var/config/runtime_subscripts_dictionary.yaml"),
    Path(__file__).resolve().parents[2] / "var" / "config" / "runtime_subscripts_dictionary.yaml",
    Path("resources/term_rules/subscripts_dictionary.yaml"),
    Path(__file__).resolve().parents[2] / "resources" / "term_rules" / "subscripts_dictionary.yaml",
)
VISUAL_TYPES = {"image", "table", "chart", "equation_interline", "seal"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".svg"}
A4_WIDTH = Mm(210)
A4_HEIGHT = Mm(297)
HEADER_FOOTER_FONT = Pt(8.5)
TOC_ENTRY_RE = re.compile(
    r"^(?:.+?[.·。…]{2,}\s*\d+\s*$|"
    r"(?:(?:\d+[、.])|(?:\d+\.\d+)|(?:附录\s*[A-Z\d.\-]+)|(?:appendix\s+[A-Z\d.\-]+)|"
    r"(?:(?:表|table|图|figure)\s*[A-Z\d.\-]+)|(?:chapter|section|part)\s+(?:[ivxlcdm]+|\d+)).*)",
    re.IGNORECASE,
)
_RUNTIME_BOUND = False


def ensure_runtime_bound() -> None:
    """Bind legacy runtime modules to the official conversion host once."""

    global _RUNTIME_BOUND
    if _RUNTIME_BOUND:
        return

    host = _build_runtime_host()
    for module in (
        input_adapter_runtime,
        page_layout_runtime,
        page_repair_runtime,
        render_config_runtime,
        text_rendering,
    ):
        module.bind_runtime(host)
    _RUNTIME_BOUND = True


def _build_runtime_host() -> SimpleNamespace:
    host = SimpleNamespace(
        logger=logger,
        VISUAL_TYPES=VISUAL_TYPES,
        IMAGE_EXTENSIONS=IMAGE_EXTENSIONS,
        A4_WIDTH=A4_WIDTH,
        A4_HEIGHT=A4_HEIGHT,
        HEADER_FOOTER_FONT=HEADER_FOOTER_FONT,
        PRODUCT_TITLE_RE=PRODUCT_TITLE_RE,
        TOC_ENTRY_RE=TOC_ENTRY_RE,
        find_subscript_config_path=lambda: render_config_runtime.find_subscript_config_path(
            DEFAULT_SUBSCRIPT_CONFIG_CANDIDATES
        ),
    )
    for module in (
        runtime_models,
        runtime_helpers,
        page_repair_runtime,
        input_adapter_runtime,
        text_rendering,
        page_layout_runtime,
        runtime_rendering_api,
    ):
        _copy_public_attributes(host, module)
    return host


def _copy_public_attributes(target: SimpleNamespace, module: Any) -> None:
    for name in dir(module):
        if name.startswith("_"):
            continue
        setattr(target, name, getattr(module, name))


def run_conversion(
    *,
    job_id: str | None = None,
    input_path: str,
    output_path: str | None,
    template_path: str | None,
    subscript_config: str | None,
    no_template: bool,
    use_mineru_header_footer: bool,
    layout_config_path: str | None = None,
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
    ensure_runtime_bound()
    original_input = Path(input_path).expanduser().resolve()
    resolved_output_path = resolve_output_path(original_input, output_path)
    resolved_template_path = None if no_template else resolve_template_path(template_arg=template_path, default_candidates=DEFAULT_TEMPLATE_CANDIDATES)
    resolved_layout_config_path = Path(layout_config_path).expanduser().resolve() if layout_config_path else None
    if resolved_layout_config_path is not None and not resolved_layout_config_path.exists():
        raise FileNotFoundError(f"版式配置文件不存在: {resolved_layout_config_path}")
    resolved_subscript_config = Path(subscript_config).expanduser().resolve() if subscript_config else None
    resolved_translation_request_output = (
        Path(translation_request_output).expanduser().resolve() if translation_request_output else None
    )
    resolved_translation_response = Path(translation_response).expanduser().resolve() if translation_response else None
    resolved_translation_trace_output = (
        Path(translation_trace_output).expanduser().resolve() if translation_trace_output else None
    )
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    if resolved_translation_request_output is not None:
        resolved_translation_request_output.parent.mkdir(parents=True, exist_ok=True)
    if resolved_translation_trace_output is not None:
        resolved_translation_trace_output.parent.mkdir(parents=True, exist_ok=True)

    logger.info("start conversion input={} output={}", original_input, resolved_output_path)
    logger.debug(
        "conversion options template={} layout_config={} subscript_config={} no_template={} use_mineru_header_footer={} document_language={} translation_mode={} translation_request_output={} translation_response={} translation_trace_output={} translation_model={} translation_api_key_present={} translation_base_url={}",
        resolved_template_path,
        resolved_layout_config_path,
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
            language_pair=language_pair_for_translation_mode(translation_mode) or "en2zh",
            target_language=translation_target_language,
            domain=translation_domain,
            prompt_version=translation_prompt_version,
        )
        if is_translation_mode(translation_mode):
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
                        language_pair=translation_config.language_pair,
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
        if is_translation_mode(translation_mode):
            preferred_document_language = "zh"

        resolved_document_language = resolve_document_language(pages, preferred=preferred_document_language)
        render_config = apply_document_language_overrides(
            load_render_config(
                template_document=template_document,
                subscript_config=resolved_subscript_config,
                use_mineru_header_footer=use_mineru_header_footer,
                layout_config_path=resolved_layout_config_path,
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
