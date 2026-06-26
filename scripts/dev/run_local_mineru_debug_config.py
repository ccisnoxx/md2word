#!/usr/bin/env python3
"""Run local MinerU-to-DOCX debugging from a repo-local JSON config."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.conversion.runtime import llm_client
from app.conversion.runtime_config import APP_CONFIG
from scripts.dev import formal_mineru_conversion
from scripts.dev.run_local_mineru_conversion import configure_logging, normalize_translation_mode


DEFAULT_CONFIG_PATH = ROOT / "scripts" / "dev" / "local_mineru_debug_config.json"
PATH_KEYS = {
    "input_path",
    "output_path",
    "template_path",
    "layout_config_path",
    "subscript_config",
    "translation_request_output",
    "translation_response",
    "translation_trace_output",
}
ALIASES = {
    "output": "output_path",
    "template": "template_path",
    "layout_config": "layout_config_path",
}
KNOWN_KEYS = {
    *PATH_KEYS,
    *ALIASES,
    "no_template",
    "use_mineru_header_footer",
    "document_language",
    "translation_mode",
    "translation_model",
    "translation_api_key",
    "translation_base_url",
    "translation_max_pages",
    "translation_max_chars",
    "log_level",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local MinerU result package through the official md2word "
            "runtime using a repo-local JSON config. Designed for PyCharm Run."
        )
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="JSON config path. Defaults to scripts/dev/local_mineru_debug_config.json.",
    )
    return parser.parse_args(argv)


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"local MinerU debug config not found: {config_path}")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("local MinerU debug config must be a JSON object.")
    return payload


def build_conversion_kwargs(config_path: Path = DEFAULT_CONFIG_PATH, *, repo_root: Path = ROOT) -> dict[str, Any]:
    config = _canonicalize_config(load_config(config_path))
    input_path = str(config.get("input_path") or "").strip()
    if not input_path:
        raise ValueError("local MinerU debug config requires input_path.")

    return {
        "input_path": resolve_config_path(input_path, repo_root=repo_root),
        "output_path": _resolve_optional_path(config, "output_path", repo_root=repo_root),
        "template_path": _resolve_optional_path(config, "template_path", repo_root=repo_root),
        "layout_config_path": _resolve_optional_path(config, "layout_config_path", repo_root=repo_root),
        "subscript_config": _resolve_optional_path(config, "subscript_config", repo_root=repo_root),
        "no_template": bool(config.get("no_template", False)),
        "use_mineru_header_footer": bool(config.get("use_mineru_header_footer", False)),
        "document_language": str(config.get("document_language") or "auto"),
        "translation_mode": normalize_translation_mode(str(config.get("translation_mode") or "direct")),
        "translation_request_output": _resolve_optional_path(config, "translation_request_output", repo_root=repo_root),
        "translation_response": _resolve_optional_path(config, "translation_response", repo_root=repo_root),
        "translation_trace_output": _resolve_optional_path(config, "translation_trace_output", repo_root=repo_root),
        "translation_model": str(config.get("translation_model") or APP_CONFIG.openai_model or llm_client.DEFAULT_MODEL),
        "translation_api_key": config.get("translation_api_key") or None,
        "translation_base_url": config.get("translation_base_url") or None,
        "translation_max_pages": int(config.get("translation_max_pages") or APP_CONFIG.translation_max_pages),
        "translation_max_chars": int(config.get("translation_max_chars") or APP_CONFIG.translation_max_chars),
    }


def resolve_config_path(raw_value: str, *, repo_root: Path = ROOT) -> str:
    path = Path(str(raw_value)).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return str(path.resolve())


def config_log_level(config_path: Path = DEFAULT_CONFIG_PATH) -> str:
    config = _canonicalize_config(load_config(config_path))
    return str(config.get("log_level") or "INFO").upper()


def _resolve_optional_path(config: Mapping[str, Any], key: str, *, repo_root: Path) -> str | None:
    value = config.get(key)
    if value in (None, ""):
        return None
    return resolve_config_path(str(value), repo_root=repo_root)


def _canonicalize_config(config: Mapping[str, Any]) -> dict[str, Any]:
    unknown_keys = sorted(set(config) - KNOWN_KEYS)
    if unknown_keys:
        raise ValueError(f"unknown local MinerU debug config keys: {', '.join(unknown_keys)}")
    canonical: dict[str, Any] = {}
    for key, value in config.items():
        canonical_key = ALIASES.get(key, key)
        if canonical_key in canonical and canonical[canonical_key] != value:
            raise ValueError(f"duplicate config values for {canonical_key}")
        canonical[canonical_key] = value
    return canonical


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()
    try:
        configure_logging(config_log_level(config_path))
        formal_mineru_conversion.run_conversion(**build_conversion_kwargs(config_path))
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
