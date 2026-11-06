"""兼容旧配置入口，复用正式配置及其导入时创建的同一单例。"""

from app.core.conversion_config import (
    APP_CONFIG,
    DOTENV_PATH,
    ROOT_DIR,
    AppConfig,
    _env,
    load_app_config,
    load_dotenv_file,
)
