from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
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
        os.environ.setdefault(key, value)
    return values


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


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
    load_dotenv_file()
    return AppConfig(
        openai_base_url=_env("OPENAI_BASE_URL"),
        openai_api_key=_env("OPENAI_API_KEY"),
        openai_model=_env("OPENAI_MODEL", "deepseek-v4-flash"),
        openai_http_referer=_env("OPENAI_HTTP_REFERER", "https://cherry-ai.com"),
        openai_x_title=_env("OPENAI_X_TITLE", "Cherry Studio"),
        openai_user_agent=_env(
            "OPENAI_USER_AGENT",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "CherryStudio/1.7.24 Chrome/144.0.7559.220 "
                "Electron/40.6.1 Safari/537.36"
            ),
        ),
        openai_accept_language=_env("OPENAI_ACCEPT_LANGUAGE", "zh-CN"),
        translation_max_pages=max(int(_env("TRANSLATION_MAX_PAGES", "20") or "20"), 1),
        translation_max_chars=max(int(_env("TRANSLATION_MAX_CHARS", "60000") or "60000"), 1),
    )


APP_CONFIG = load_app_config()
