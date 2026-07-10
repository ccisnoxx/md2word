# MinerU 账号与密钥配置执行计划

## 1. 后端配置领域与 API

1. 在 `app/core/config.py` 增加基于 `DATA_DIR` 的 MinerU 运行时配置文件路径。
2. 新增 `app/domains/mineru/` 配置模型、服务、请求/响应 schema 和管理员路由：
   - `MINERU_API_TOKEN` 与 `MINERU_UID` 共同 fallback 及运行时完整绑定优先级；
   - 严格 JSON 模型、空白校验和 `4096` 长度上限；
   - 唯一临时文件、原子替换与 `0600` 权限；
   - GET/PUT 安全响应，不返回 API 密钥、UID 或 mask；
   - 配置损坏稳定错误和审计失败的“已保存但审计失败”错误。
3. 将路由注册到 `app/api/v1/router.py`，将服务注册到 `AppRuntime` 并在 `app/main.py` 构造。
4. 为新增或实质修改的 Python 模块、公共服务和异常路径补充中文模块说明、docstring 与面向管理员的中文错误信息。

## 2. 统一运行时读取链路

1. 向 `JobStageService` 和 `DocumentJobExecutionService` 注入 MinerU 配置 resolver，客户端创建时读取同一绑定中的最新有效 API 密钥和 UID。
2. 修改 PDF 上传入口和 MinerU 结果恢复入口，移除对 `runtime.settings.mineru_api_token` 的直接判断。
3. 修改 `HealthService`，一次解析 MinerU 配置后统一驱动：
   - `mineru_api_token_configured`；
   - `pdf_submission_available`；
   - readiness warnings/blockers；
   - P0 document_jobs readiness；
   - 安全的 source/updated_at/error 字段。
4. 修改 Ops integration control，使 provider cancellation 的配置状态由有效配置服务提供，响应继续只含布尔摘要。
5. 修改 callback checksum fallback，使 payload 未带 UID 时读取有效配置服务；修改 Config Workbench finding 文案和路由：token missing/UID missing/config invalid 指向 `/settings/mineru`，callback URL 保持现有处理入口。

## 3. 前端配置入口

1. 在 `frontend/src/api/types.ts` 增加 MinerU 配置请求/响应类型，并新增 `frontend/src/api/mineruConfig.ts` typed wrapper。
2. 新增 `frontend/src/pages/MinerUConfigPage.vue`：
   - UID 文本输入框和 API 密钥 password 输入框，必须同时非空提交；
   - 只显示两项 configured/missing、来源、更新时间和更新人；
   - 无显示当前 key、清空、测试或历史操作；
   - 成功后清空输入，失败显示 scoped API error。
3. 更新 Vue Router、`appShell` 导航与面包屑、配置中心入口卡片。
4. 更新 release gate route helper，只把 `mineru_api_token_missing` 与 `mineru_config_invalid` 指向新页面。
5. 新增/更新前端单元测试，覆盖 API method/path、管理员导航、面包屑、配置中心入口和诊断路由。

## 4. 后端与合同测试

1. 新增聚焦的 MinerU 配置服务测试：
   - API 密钥与 UID 环境变量共同 fallback；
   - 运行时文件优先；
   - 空白拒绝；
   - 原子写入与 `0600`；
   - 非法文件不回退；
   - 非法文件可由合法 PUT 覆盖修复；
   - 不保留历史或备份文件。
2. 在 FastAPI 集成测试中覆盖：
   - admin GET/PUT 与 operator/匿名拒绝；
   - 响应、错误和审计无密钥字符/片段/长度；
   - 更新后 health、callback fallback、上传门禁和两个客户端工厂读取新绑定；
   - 已创建客户端保持旧绑定；
   - 配置损坏 readiness；
   - 审计失败后文件仍生效且 API 明确报错。
3. 更新 OpenAPI 快照和健康/配置 API 文档，记录 runtime file 优先级、共享 volume、无外部验证和回滚注意事项。

## 5. 验证命令

先运行最小聚焦检查：

```bash
.venv/bin/python -m unittest tests.test_mineru_config
.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_mineru_config_api_updates_runtime_token_without_exposing_secret
.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_mineru_config_invalid_file_blocks_without_settings_fallback
.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_mineru_config_audit_failure_keeps_updated_token
```

运行相关前端和合同检查：

```bash
npm --prefix frontend run test:unit -- src/api/mineruConfig.test.ts src/pages/MinerUConfigPage.test.ts src/navigation/appShell.test.ts src/utils/releaseGateRoutes.test.ts
npm --prefix frontend run build
.venv/bin/python scripts/ops/export_openapi.py
.venv/bin/python -m unittest tests.test_openapi_export
```

完成前运行聚合检查；若耗时超出本地预算，报告已完成的替代检查和剩余线上风险：

```bash
.venv/bin/python scripts/ops/check_release.py
```

## 6. 评审与回滚点

- 评审单一来源：搜索 `mineru_api_token`，除 `Settings` fallback、配置服务和测试夹具外，不应再有业务代码直接判断或构造客户端使用该字段。
- 评审敏感信息：搜索新增 response、日志、审计和前端状态，不得出现 token、mask、长度、请求体或文件路径泄露。
- 评审失败语义：非法文件不能 fallback 或混用环境变量；审计失败不能回滚已经写入的新绑定；任一字段空白都不能改文件。
- 代码回滚前确认线上 `MINERU_API_TOKEN` 仍有效，因为旧代码忽略共享 volume 中的新运行时文件。
- 本地不启动 API、MySQL、Redis/Celery、Worker 或真实 MinerU；完整共享 volume 和真实任务验证留给 hostdzire 线上优先流程。
