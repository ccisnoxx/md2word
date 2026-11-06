# 设计

将 runtime_config 的 AppConfig、dotenv 读取和 APP_CONFIG 单例移至 app/core/conversion_config.py；保留原始环境优先级、空值、整型下限、导入时机语义，不直接改用 Settings。legacy runtime_config 重新导出原名，避免双单例。

翻译目标语言、领域与 Prompt 版本置于已有 app/domains/translation/modes.py。模型默认值与 OpenAI ImportError 探测置于 app/clients/openai_sdk.py，legacy 导入；不得改成 find_spec 探测或调整健康判定。配置读取和 SDK 探测分开，保留只加载配置时不导入 SDK 的原有边界；正式 Provider 仍保留调用时延迟导入。

指定消费者仅换依赖，沙箱生成文本保留 APP_CONFIG/ROOT_DIR 接口。保护 docx_rules/parser/jobs；不移除旧链路、不添加旧入口迁移适配器。
