# Backend Development Guidelines

These guidelines describe the current `md2word` backend as it exists now. They are based on the repository's FastAPI code, backend docs, tests, and release scripts, not on a target architecture.

Primary evidence:

- `README.md`
- `docs/dev/backend-local-setup-and-architecture.md`
- `docs/runbooks/backend.md`
- `docs/dev/runtime-observability-and-health.md`
- `app/main.py`
- `app/core/config.py`
- `app/core/runtime.py`
- `app/api/errors.py`
- `app/infrastructure/persistence/factory.py`
- `tests/test_fastapi_jobs_backend.py`
- `scripts/ops/check_release.py`

## Pre-Development Checklist

Before backend changes:

1. Read [Directory Structure](./directory-structure.md) for ownership boundaries and where files belong.
2. Read [Error Handling](./error-handling.md) for API/service exception behavior.
3. Read [Quality Guidelines](./quality-guidelines.md) for tests and release checks.
4. If the change touches metadata, repositories, stage messages, schema bootstrap, or artifact storage, read [Database Guidelines](./database-guidelines.md).
5. If the change emits logs, affects health/metrics, workers, callbacks, or long-running jobs, read [Logging Guidelines](./logging-guidelines.md).
6. 修改 MinerU 账号与密钥、运行时配置文件或环境变量优先级时，阅读 [Runtime Configuration](./runtime-configuration.md)。
7. 修改 Word 模板样式 schema、版本 API、默认指针、draft 验证权限或多文种字体槽位时，阅读 [Word 模板样式配置合同](./template-layout-configuration.md)。
8. 修改 MinerU content list、DocumentIR、页面/分栏规划、Word renderer、DOCX 字段或输出质量门禁时，必须阅读 [Word 生成规则](./word-generation-rules.md)。
9. 修改 DocumentJob 模式、资源选择或相关 UI 合同时，阅读 [任务模式与 direct 资源合同](./document-job-mode-contract.md)。
10. 修改技术 Token 检测、批次占位、完整性验证或恢复调用时，阅读 [ProtectedTokenCodec 内部合同](./protected-token-codec.md)。
11. 修改正式翻译准备、Provider/Worker/本地接线、批次 evidence 或正文 repr 时，阅读 [翻译完整性验证与消费合同](./translation-integrity-validator.md)。
12. 修改翻译批次树、根计划安装、attempt/lease、自动恢复、终态收口或批次摘要 API 时，阅读 [翻译批次生命周期与原子边界](./translation-batch-lifecycle.md)。

Also read `.trellis/spec/guides/index.md` and the relevant thinking guide when the change crosses API, service, repository, worker, or runtime boundaries.

## Guidelines Index

| Guide | What It Covers | Status |
|---|---|---|
| [Directory Structure](./directory-structure.md) | FastAPI composition root, domain layout, services, conversion, workers, resources, and tests | Current |
| [Database Guidelines](./database-guidelines.md) | file/sqlite/MySQL metadata backends, schema bootstrap, adapter ports, payload storage, migration state | Current |
| [Error Handling](./error-handling.md) | `ApiError`, unified API error responses, workflow errors, validation, trace IDs, bulk failures | Current |
| [任务模式与 direct 资源合同](./document-job-mode-contract.md) | 服务端 alias、direct 零翻译加载、阶段/事件/恢复、历史快照及 UI 展示边界 | 当前 |
| [ProtectedTokenCodec 内部合同](./protected-token-codec.md) | 纯函数检测、批次唯一、碰撞保护、整批计数验证、精确恢复与隐私边界 | 当前 |
| [翻译完整性验证与消费合同](./translation-integrity-validator.md) | 共享编码准备、整批校验、稳定错误、fan-in evidence、默认表示隐私及存储身份边界 | 当前 |
| [翻译批次生命周期与原子边界](./translation-batch-lifecycle.md) | 完整根计划、同 job 原子操作、attempt/lease、终态重放与 API/UI 投影 | 当前 |
| [Logging Guidelines](./logging-guidelines.md) | `access` / `business` / `system` loggers, text/JSON format, trace/job context, sensitive data boundaries | Current |
| [Runtime Configuration](./runtime-configuration.md) | MinerU 账号与密钥绑定、环境变量优先级、安全 API、审计和 Worker 即时生效合同 | Current |
| [Word 模板样式配置合同](./template-layout-configuration.md) | Admin schema、版本治理、旧配置兼容和多文种 OOXML 字体槽位 | Current |
| [Word 生成规则](./word-generation-rules.md) | 正式 MinerU→DocumentIR→Word 输出行为、冲突优先级、回归证据和 legacy 差异 | Current |
| [Quality Guidelines](./quality-guidelines.md) | `unittest` style, targeted checks, release gate, OpenAPI contract checks, local vs online validation | Current |

## Quality Check

Use the smallest check that covers the touched behavior first. Current project-level evidence points to these commands:

```bash
.venv/bin/python -m unittest <specific-test-targets>
.venv/bin/python scripts/ops/check_release.py
```

`README.md` and `docs/runbooks/backend.md` state that local changes should not start frontend, backend, MySQL, Redis/Celery, workers, or Playwright smoke for P0 release evidence. Full API, worker, database, MinerU, and Golden Sample evidence is collected on hostdzire through the online-first workflow.
