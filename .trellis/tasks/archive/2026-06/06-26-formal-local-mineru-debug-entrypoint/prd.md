# Formal core local MinerU debug entrypoint

## Goal

把本地 MinerU 转 Word 调试入口收敛到线上正式 Document Jobs 使用的 DocumentIR 转换与 Word renderer 核心，使本地入口能快速复现排版问题，同时保证所有排版修复只落在正式转换核心，不再通过 legacy `runtime_runner` 形成第二套逻辑。

用户价值：

- 本地可用 `scripts/dev/run_local_mineru_conversion.py` 和 JSON/PyCharm 入口快速复现 DOCX 版式问题。
- 修复点默认进入 `app/services/document_ir/*`、`app/services/renderer/*` 或共享规则 `app/conversion/docx_rules/*`，线上正式转换自动受益。
- 本地质量矩阵和长期样例回归不再把 legacy runtime 当作正确性来源。

## Confirmed Facts

- `scripts/dev/run_local_mineru_conversion.py`、`scripts/dev/run_local_mineru_debug_config.py` 和 `scripts/dev/run_local_mineru_quality_matrix.py` 当前调用 `app.conversion.runtime_runner.run_conversion()`。
- 当前公开 P0 主链路是 Files + Document Jobs；`docs/dev/backend-local-setup-and-architecture.md` 明确 `/api/v1/jobs` 是 legacy 历史链路。
- 正式主链路在 `DocumentJobExecutionService` 中调用 `MinerUToDocumentIRService.convert_zip()`，随后调用 `DocumentIRWordRenderer.render_to_bytes()`。
- `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` 记录了 renderer parity 的收口方向：修复入口应收敛到 `document_jobs -> DocumentIR -> app/services/renderer/*`。
- 本任务不需要修改 HTTP API、数据库 schema 或线上 job 状态机。

## Requirements

- R1. 本地单样例入口必须通过正式 DocumentIR converter 和 `DocumentIRWordRenderer` 生成 DOCX，不再默认调用 `runtime_runner`。
- R2. JSON/PyCharm 配置入口必须保持现有常用字段兼容，包括 input/output/template/layout/subscript/language/translation/log level。
- R3. 本地质量矩阵和长期 component PDF 回归如果用于排版验收，也必须走正式核心，避免报告继续验证 legacy 输出。
- R4. 翻译模式不得静默回退 direct；缺少 provider/key 或离线响应时保持明确 blocked/failure。
- R5. 本地入口可以写本地诊断产物到 `tests/tmp/`，但不能引入脚本层排版补丁、后处理修复或第二套 renderer。
- R6. 文档和测试必须明确 legacy `/api/v1/jobs` / `runtime_runner` 仅作历史路径，正式排版修复以 DocumentIR renderer 为准。

## Acceptance Criteria

- [ ] `scripts/dev/run_local_mineru_conversion.py` 和 `scripts/dev/run_local_mineru_debug_config.py` 的主执行路径不再 import/call `app.conversion.runtime_runner.run_conversion()`。
- [ ] `scripts/dev/run_local_mineru_quality_matrix.py` 的实际转换路径使用正式本地 adapter；缺 key/response 的 en2zh/ru2zh 仍被标记为 blocked。
- [ ] `scripts/dev/run_component_pdf_regression.py` 使用同一正式本地 adapter，或文档明确它不是排版验收入口；推荐迁移为同一 adapter。
- [ ] 新增或更新单测覆盖 CLI/config 参数映射、正式 adapter 调用、最小 MinerU 包生成可打开 DOCX、quality matrix blocked 分支。
- [ ] 现有正式核心测试通过：`tests.test_document_ir_mineru_converter_layout`、`tests.test_document_ir_word_renderer_layout`。
- [ ] 入口治理测试通过：`tests.test_conversion_sandbox_dev_tools`、`tests.test_local_mineru_quality_matrix`、`tests.test_component_pdf_sample_governance`。
- [ ] 文档更新 `docs/dev/local-conversion-sandbox.md` 和相关 component PDF 调试说明，删除“本地入口调用 runtime_runner 作为 official runtime”的表述。

## Out Of Scope

- 不重写排版策略本身；发现排版 bug 时另按正式核心补测试和修复。
- 不迁移线上 `/api/v1/jobs` legacy 链路。
- 不新增 public API、数据库迁移、Redis/Celery/MinerU 在线调用门禁。
- 不提交 `mineru_result/`、`tests/tmp/`、生成 DOCX/PNG/PDF、真实 key 或真实 trace。
