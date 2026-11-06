"""共享 OpenAI SDK 可用性探测与导入时的默认模型。"""

from app.core.conversion_config import APP_CONFIG


try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


DEFAULT_MODEL = APP_CONFIG.openai_model or "deepseek-v4-flash"
