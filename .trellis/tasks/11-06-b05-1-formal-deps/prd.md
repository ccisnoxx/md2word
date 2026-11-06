# B05 第 1 步：解除正式消费者的 legacy 配置依赖

正式服务和三个本地 MinerU CLI、沙箱兼容配置生成器改读正式 owner；默认值逐字相同，健康检查字段与判定、CLI 行为不变，legacy 保留可导入运行。

## 验收
- AC-1：指定正式消费者不再依赖 legacy llm_client、translation_runtime、runtime_config，保存 AST 前后对比。
- AC-2：迁移值/探测只有一个 owner，legacy 只导入。
- AC-3：默认值、健康检查、CLI 默认行为通过定向验证。
- AC-4：指定 runtime facade 模型绑定测试通过。
- AC-5：docx_rules、table_html_parser、jobs 共享能力不移动或删除。

范围为指定消费者、正式 owner、legacy 对应导入、相关测试及本任务文档。禁止提交、推送、发布、仓库外写入、真实外部调用、数据库、全仓/在线门禁、归档及 add_session；不改任务 manifest。
