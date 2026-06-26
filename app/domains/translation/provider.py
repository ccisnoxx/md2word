from __future__ import annotations

# app/domains/translation/provider.py: 定义可替换翻译 provider 端口和默认 OpenAI-compatible 适配器。

import json
import hashlib
from collections.abc import Callable
from typing import Any, Protocol

from app.core.config import Settings
from app.domains.translation.provider_config import EffectiveAiProviderConfig
from app.domains.translation.models import (
    TranslationProviderRequest,
    TranslationProviderResult,
    TranslationTextItem,
)
from app.domains.translation.modes import translation_prompt_path


class TranslationProviderResponseError(RuntimeError):
    """Provider response could not be parsed or validated, with non-sensitive metadata."""

    def __init__(
        self,
        message: str,
        *,
        finish_reason: str | None = None,
        usage: dict[str, int] | None = None,
        response_id: str | None = None,
        content: str = "",
        suspected_truncation: bool = False,
    ) -> None:
        super().__init__(message)
        self.finish_reason = finish_reason
        self.usage = usage or {}
        self.response_id = response_id
        self.content_length = len(content)
        self.content_sha256 = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}" if content else None
        self.suspected_truncation = suspected_truncation


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

    def __init__(
        self,
        settings: Settings,
        config_resolver: Callable[[], EffectiveAiProviderConfig] | None = None,
    ) -> None:
        self.settings = settings
        self.config_resolver = config_resolver

    def translate(self, request: TranslationProviderRequest) -> TranslationProviderResult:
        """调用兼容 OpenAI SDK 的 chat completion 接口并解析 JSON 响应。"""

        config = self._effective_config()
        if config.backend != "openai_compatible":
            raise RuntimeError("翻译 provider 未启用。")
        if not config.api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置，无法调用翻译 provider。")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - 依赖缺失路径由运行环境触发。
            raise RuntimeError("未安装 openai Python SDK，无法调用翻译 provider。") from exc

        client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url or None,
            timeout=config.timeout_seconds,
        )
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": self._system_prompt(request)},
                {"role": "user", "content": self._user_prompt(request)},
            ],
            stream=False,
            max_tokens=config.max_output_tokens,
            extra_body={"thinking": {"type": "disabled"}},
        )
        content = self._extract_content(response)
        finish_reason = self._extract_finish_reason(response)
        usage = self._extract_usage(response)
        response_id = self._extract_response_id(response)
        payload = self._parse_json_response(
            content,
            finish_reason=finish_reason,
            usage=usage,
            response_id=response_id,
        )
        content_sha256 = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}" if content else None
        return TranslationProviderResult(
            items=self._parse_items(payload),
            finish_reason=finish_reason,
            usage=usage,
            response_id=response_id,
            content_length=len(content),
            content_sha256=content_sha256,
        )

    def _effective_config(self) -> EffectiveAiProviderConfig:
        if self.config_resolver is not None:
            return self.config_resolver()
        return EffectiveAiProviderConfig(
            backend=self.settings.translation_provider_backend,
            base_url=self.settings.openai_base_url or None,
            api_key=self.settings.openai_api_key or None,
            model=self.settings.openai_model,
            timeout_seconds=self.settings.translation_provider_timeout_seconds,
            max_output_tokens=self.settings.translation_provider_max_output_tokens,
            source="settings",
        )

    def _system_prompt(self, request: TranslationProviderRequest) -> str:
        prompt_path = translation_prompt_path(self.settings.root_dir, request.language_pair)
        if not prompt_path.exists():
            raise RuntimeError(f"system prompt 文件不存在: {prompt_path}")
        prompt = prompt_path.read_text(encoding="utf-8").strip()
        return (
            f"{prompt}\n\n"
            f"Language pair: {request.language_pair}; source={request.source_language}; target={request.target_language}. "
            "Return only JSON with an items array. Preserve every item id exactly."
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

    def _extract_finish_reason(self, response: Any) -> str | None:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return None
        finish_reason = getattr(choices[0], "finish_reason", None)
        return str(finish_reason) if finish_reason is not None else None

    def _extract_response_id(self, response: Any) -> str | None:
        response_id = getattr(response, "id", None)
        return str(response_id) if response_id is not None else None

    def _extract_usage(self, response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            raw_usage = usage.model_dump(mode="json")
        elif isinstance(usage, dict):
            raw_usage = usage
        else:
            raw_usage = {
                key: getattr(usage, key)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if getattr(usage, key, None) is not None
            }
        return {
            str(key): int(value)
            for key, value in raw_usage.items()
            if isinstance(value, int) and not isinstance(value, bool)
        }

    def _parse_json_response(
        self,
        content: str,
        *,
        finish_reason: str | None,
        usage: dict[str, int],
        response_id: str | None,
    ) -> dict[str, Any]:
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
            raise TranslationProviderResponseError(
                "翻译 provider 返回内容不是合法 JSON。",
                finish_reason=finish_reason,
                usage=usage,
                response_id=response_id,
                content=content,
                suspected_truncation=self._looks_truncated(stripped, finish_reason=finish_reason),
            )
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise TranslationProviderResponseError(
                f"翻译 provider 返回 JSON 解析失败: {exc.msg}",
                finish_reason=finish_reason,
                usage=usage,
                response_id=response_id,
                content=content,
                suspected_truncation=self._looks_truncated(stripped, finish_reason=finish_reason),
            ) from exc

    def _looks_truncated(self, content: str, *, finish_reason: str | None) -> bool:
        if finish_reason == "length":
            return True
        stripped = content.strip()
        if not stripped:
            return True
        return stripped.count("{") > stripped.count("}") or stripped.count("[") > stripped.count("]")

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


def build_translation_provider(
    settings: Settings,
    config_resolver: Callable[[], EffectiveAiProviderConfig] | None = None,
) -> TranslationProvider:
    """按配置构建 translation provider。"""

    if config_resolver is not None:
        return OpenAICompatibleTranslationProvider(settings, config_resolver=config_resolver)
    if settings.translation_provider_backend == "openai_compatible":
        return OpenAICompatibleTranslationProvider(settings)
    return DisabledTranslationProvider()
