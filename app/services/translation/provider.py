from __future__ import annotations

# app/services/translation/provider.py: 定义可替换翻译 provider 端口和默认 OpenAI-compatible 适配器。

import json
from typing import Any, Protocol

from app.core.config import Settings
from app.core.translation_models import (
    TranslationProviderRequest,
    TranslationProviderResult,
    TranslationTextItem,
)


class TranslationProvider(Protocol):
    """翻译 provider 抽象；私有化模型只需实现这个端口。"""

    def translate(self, request: TranslationProviderRequest) -> TranslationProviderResult:
        """翻译一批文本片段，返回 id 与输入完全对应的结果。"""


class DisabledTranslationProvider:
    """默认禁用 provider，避免未配置外部模型时误发文本。"""

    def translate(self, request: TranslationProviderRequest) -> TranslationProviderResult:
        raise RuntimeError("TRANSLATION_PROVIDER_BACKEND=disabled，翻译 provider 未启用。")


class OpenAICompatibleTranslationProvider:
    """OpenAI-compatible chat completion provider，后续可替换为私有化实现。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def translate(self, request: TranslationProviderRequest) -> TranslationProviderResult:
        """调用兼容 OpenAI SDK 的 chat completion 接口并解析 JSON 响应。"""

        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置，无法调用翻译 provider。")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - 依赖缺失路径由运行环境触发。
            raise RuntimeError("未安装 openai Python SDK，无法调用翻译 provider。") from exc

        client = OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url or None,
            timeout=self.settings.translation_provider_timeout_seconds,
        )
        response = client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {"role": "system", "content": self._system_prompt(request)},
                {"role": "user", "content": self._user_prompt(request)},
            ],
            stream=False,
            max_tokens=self.settings.translation_provider_max_output_tokens,
            extra_body={"thinking": {"type": "disabled"}},
        )
        content = self._extract_content(response)
        payload = self._parse_json_response(content)
        return TranslationProviderResult(items=self._parse_items(payload))

    def _system_prompt(self, request: TranslationProviderRequest) -> str:
        return (
            "You are a technical document translation engine. "
            f"Translate from {request.source_language} to {request.target_language}. "
            "Return only JSON with an items array. Preserve every item id exactly. "
            "Translate only the text value. Do not add, remove, merge, or split items."
        )

    def _user_prompt(self, request: TranslationProviderRequest) -> str:
        payload: dict[str, Any] = {
            "language_pair": request.language_pair,
            "glossary": [
                {
                    "source_term": term.source_term,
                    "target_term": term.target_term,
                }
                for term in request.terms
            ],
            "items": [{"id": item.id, "text": item.text} for item in request.items],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _extract_content(self, response: Any) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        return str(getattr(message, "content", "") or "").strip()

    def _parse_json_response(self, content: str) -> dict[str, Any]:
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
        if start < 0 or end < start:
            raise RuntimeError("翻译 provider 返回内容不是合法 JSON。")
        return json.loads(stripped[start : end + 1])

    def _parse_items(self, payload: dict[str, Any]) -> tuple[TranslationTextItem, ...]:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise RuntimeError("翻译 provider 返回 JSON 缺少 items 数组。")
        items: list[TranslationTextItem] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                raise RuntimeError("翻译 provider 返回 items 包含非法条目。")
            item_id = str(raw_item.get("id") or "").strip()
            text = str(raw_item.get("text") or "").strip()
            if not item_id or not text:
                raise RuntimeError("翻译 provider 返回 items 缺少 id 或 text。")
            items.append(TranslationTextItem(id=item_id, text=text))
        return tuple(items)


def build_translation_provider(settings: Settings) -> TranslationProvider:
    """按配置构建 translation provider。"""

    if settings.translation_provider_backend == "openai_compatible":
        return OpenAICompatibleTranslationProvider(settings)
    return DisabledTranslationProvider()
