from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from app.conversion.runtime_config import APP_CONFIG, ROOT_DIR


try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised through runtime error path
    OpenAI = None


DEFAULT_MODEL = APP_CONFIG.openai_model or "deepseek-v4-flash"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_OUTPUT_TOKENS = 12000
SYSTEM_PROMPT_PATH = ROOT_DIR / "resources" / "prompts" / "translation_en2zh.md"


@dataclass(slots=True)
class LLMClientConfig:
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    default_headers: dict[str, str] | None = None


def translate_payload(payload: dict[str, Any], config: LLMClientConfig) -> dict[str, Any]:
    client = build_client(config)
    translated_batches: list[dict[str, Any]] = []
    for batch in payload.get("batches", []):
        translated_batches.append(
            {
                "batch_id": batch.get("batch_id"),
                "items": translate_batch(client, batch, payload, config),
            }
        )
    return {"batches": translated_batches}


def build_client(config: LLMClientConfig) -> Any:
    if OpenAI is None:
        raise RuntimeError(
            "未安装 openai Python SDK。请先执行 `python3 -m pip install openai`，"
            "或在可用环境中安装后再启用 llm_en_to_zh 模式。"
        )

    api_key = config.api_key or os.getenv("OPENAI_API_KEY") or APP_CONFIG.openai_api_key
    if not api_key:
        raise RuntimeError("未提供 OPENAI_API_KEY，无法调用翻译模型。")

    base_url = config.base_url or os.getenv("OPENAI_BASE_URL") or APP_CONFIG.openai_base_url
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=config.timeout_seconds,
        default_headers=config.default_headers or build_default_headers(),
    )


def translate_batch(client: Any, batch: dict[str, Any], payload: dict[str, Any], config: LLMClientConfig) -> list[dict[str, str]]:
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(),
        },
        {
            "role": "user",
            "content": build_user_prompt(batch),
        },
    ]
    raw_response = client.chat.completions.with_raw_response.create(
        model=config.model or os.getenv("OPENAI_MODEL") or APP_CONFIG.openai_model or DEFAULT_MODEL,
        messages=messages,
        stream=False,
        extra_body={"thinking": {"type": "disabled"}},
        max_tokens=config.max_output_tokens,
    )
    completion = raw_response.parse()
    content = extract_message_content(completion)
    if not content:
        raise RuntimeError("LLM 未返回可解析的翻译内容。")

    logger.info("模型输出: {}", content)
    if getattr(completion, "usage", None) is not None:
        logger.info("输入 token: {}", getattr(completion.usage, "prompt_tokens", 0))
        logger.info("输出 token: {}", getattr(completion.usage, "completion_tokens", 0))
        logger.info("总 token: {}", getattr(completion.usage, "total_tokens", 0))

    parsed = parse_json_response(content)
    items = parsed.get("items")
    if not isinstance(items, list):
        raise RuntimeError("LLM 返回 JSON 缺少 items 数组。")
    return [{"id": str(item["id"]), "text": str(item["text"])} for item in items]


def build_default_headers() -> dict[str, str]:
    return {
        "Accept": "*/*",
        "Accept-Language": APP_CONFIG.openai_accept_language or "zh-CN",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "HTTP-Referer": APP_CONFIG.openai_http_referer or "https://cherry-ai.com",
        "X-Title": APP_CONFIG.openai_x_title or "Cherry Studio",
        "User-Agent": APP_CONFIG.openai_user_agent,
    }


def extract_message_content(completion: Any) -> str:
    choices = getattr(completion, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    content = getattr(message, "content", "")
    return str(content or "").strip()


def parse_json_response(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError("LLM 返回内容不是合法 JSON。")
    return json.loads(stripped[start : end + 1])


def build_system_prompt() -> str:
    return load_system_prompt_template()


def load_system_prompt_template(path: Path = SYSTEM_PROMPT_PATH) -> str:
    if not path.exists():
        raise RuntimeError(f"system prompt 文件不存在: {path}")
    return path.read_text(encoding="utf-8")


def build_user_prompt(batch: dict[str, Any]) -> str:
    request_payload = {
        "batch_id": batch.get("batch_id"),
        "section": batch.get("section"),
        "section_continuation": bool(batch.get("section_continuation", False)),
        "page_range": batch.get("page_range"),
        "items": batch.get("items", []),
    }
    return json.dumps(request_payload, ensure_ascii=False, indent=2)
