from __future__ import annotations

# app/conversion/runtime_config.py: 读取 legacy 转换链路的 OpenAI 和翻译限制配置。

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DOTENV_PATH = ROOT_DIR / ".env"


def load_dotenv_file(path: Path = DOTENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        values[key] = value
    return values


def _env(key: str, default: str = "", *, dotenv_values: dict[str, str] | None = None) -> str:
    value = os.getenv(key)
    if value is not None:
        return value
    if dotenv_values is None:
        return default
    return dotenv_values.get(key, default)


@dataclass(slots=True)
class AppConfig:
    openai_base_url: str
    openai_api_key: str
    openai_model: str
    openai_http_referer: str
    openai_x_title: str
    openai_user_agent: str
    openai_accept_language: str
    translation_max_pages: int
    translation_max_chars: int


def load_app_config() -> AppConfig:
    dotenv_values = load_dotenv_file()
    return AppConfig(
        openai_base_url=_env("OPENAI_BASE_URL", dotenv_values=dotenv_values),
        openai_api_key=_env("OPENAI_API_KEY", dotenv_values=dotenv_values),
        openai_model=_env("OPENAI_MODEL", "deepseek-v4-flash", dotenv_values=dotenv_values),
        openai_http_referer=_env("OPENAI_HTTP_REFERER", "https://cherry-ai.com", dotenv_values=dotenv_values),
        openai_x_title=_env("OPENAI_X_TITLE", "Cherry Studio", dotenv_values=dotenv_values),
        openai_user_agent=_env(
            "OPENAI_USER_AGENT",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "CherryStudio/1.7.24 Chrome/144.0.7559.220 "
                "Electron/40.6.1 Safari/537.36"
            ),
            dotenv_values=dotenv_values,
        ),
        openai_accept_language=_env("OPENAI_ACCEPT_LANGUAGE", "zh-CN", dotenv_values=dotenv_values),
        translation_max_pages=max(int(_env("TRANSLATION_MAX_PAGES", "20", dotenv_values=dotenv_values) or "20"), 1),
        translation_max_chars=max(int(_env("TRANSLATION_MAX_CHARS", "60000", dotenv_values=dotenv_values) or "60000"), 1),
    )


APP_CONFIG = load_app_config()
