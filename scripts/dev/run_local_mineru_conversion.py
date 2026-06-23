#!/usr/bin/env python3
"""Run one MinerU result package through the official md2word conversion runtime."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
root_path = str(ROOT)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from loguru import logger

from app.conversion import runtime_runner
from app.conversion.runtime import llm_client, translation_runtime
from app.conversion.runtime_config import APP_CONFIG


DEFAULT_INPUT_ENV = "MD2WORD_LOCAL_MINERU_INPUT"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a MinerU output directory or zip to DOCX through the official "
            "md2word conversion runtime."
        )
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default=None,
        help=f"MinerU output directory or zip. If omitted, {DEFAULT_INPUT_ENV} is used.",
    )
    parser.add_argument("--output", help="Output DOCX path. Defaults to the runtime output rule.")
    parser.add_argument("--template", help="Optional Word template path.")
    parser.add_argument("--layout-config", help="Optional template layout YAML path.")
    parser.add_argument("--subscript-config", help="Optional term/subscript YAML path.")
    parser.add_argument("--no-template", action="store_true", help="Generate without a Word template.")
    parser.add_argument(
        "--use-mineru-header-footer",
        action="store_true",
        help="Use MinerU-detected headers and footers instead of template headers and footers.",
    )
    parser.add_argument(
        "--document-language",
        choices=("auto", "zh", "en"),
        default="auto",
        help="Document language override. Defaults to auto detection.",
    )
    parser.add_argument(
        "--translation-mode",
        choices=("direct", "en2zh", "none", "llm_en_to_zh"),
        default="direct",
        help="direct/none generates the current language; en2zh/llm_en_to_zh translates first.",
    )
    parser.add_argument("--translation-request-output", help="Write the LLM translation request JSON.")
    parser.add_argument("--translation-response", help="Read an LLM translation response JSON.")
    parser.add_argument("--translation-trace-output", help="Write translation trace JSON evidence.")
    parser.add_argument(
        "--translation-model",
        default=APP_CONFIG.openai_model or llm_client.DEFAULT_MODEL,
        help="Translation model for en2zh mode.",
    )
    parser.add_argument("--translation-api-key", help="Optional translation API key.")
    parser.add_argument("--translation-base-url", help="Optional OpenAI-compatible base URL.")
    parser.add_argument(
        "--translation-max-pages",
        type=int,
        default=APP_CONFIG.translation_max_pages,
        help=f"Translation batch page soft limit. Default: {APP_CONFIG.translation_max_pages}.",
    )
    parser.add_argument(
        "--translation-max-chars",
        type=int,
        default=APP_CONFIG.translation_max_chars,
        help=f"Translation batch char hard limit. Default: {APP_CONFIG.translation_max_chars}.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Loguru log level for local conversion diagnostics.",
    )
    return parser.parse_args(argv)


def normalize_translation_mode(mode: str | None) -> str:
    normalized = str(mode or "direct").strip().lower()
    if normalized in {"none", "direct", "zh2zh", "zh_to_zh"}:
        return "direct"
    if normalized in {"en2zh", "llm_en_to_zh", "en_to_zh"}:
        return "en2zh"
    raise ValueError(f"Unsupported translation_mode: {mode}")


def resolve_input_path(raw_input_path: str | None, *, environ: dict[str, str] | None = None) -> str:
    values = os.environ if environ is None else environ
    candidate = str(raw_input_path or values.get(DEFAULT_INPUT_ENV, "")).strip()
    if not candidate:
        raise ValueError(f"input_path is required; pass it as an argument or set {DEFAULT_INPUT_ENV}.")
    return candidate


def build_conversion_kwargs(args: argparse.Namespace, *, environ: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "input_path": resolve_input_path(args.input_path, environ=environ),
        "output_path": args.output,
        "template_path": args.template,
        "layout_config_path": args.layout_config,
        "subscript_config": args.subscript_config,
        "no_template": bool(args.no_template),
        "use_mineru_header_footer": bool(args.use_mineru_header_footer),
        "document_language": args.document_language,
        "translation_mode": normalize_translation_mode(args.translation_mode),
        "translation_request_output": args.translation_request_output,
        "translation_response": args.translation_response,
        "translation_trace_output": args.translation_trace_output,
        "translation_model": args.translation_model,
        "translation_api_key": args.translation_api_key,
        "translation_base_url": args.translation_base_url,
        "translation_max_pages": args.translation_max_pages,
        "translation_max_chars": args.translation_max_chars,
    }


def configure_logging(level_name: str) -> None:
    logger.remove()
    logger.add(
        sink=sys.stderr,
        level=level_name,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:"
            "<cyan>{line}</cyan> - <level>{message}</level>"
        ),
        colorize=True,
        backtrace=False,
        diagnose=False,
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    configure_logging(args.log_level)
    try:
        runtime_runner.run_conversion(**build_conversion_kwargs(args))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
