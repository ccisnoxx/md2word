# Implement: Formal core local MinerU debug entrypoint

## Checklist

1. 读取 backend spec 与相关代码，确认当前 worktree 干净。
2. 添加 dev-only formal local adapter：
   - 支持 MinerU 目录/zip 输入。
   - 调用 `MinerUToDocumentIRService`、可选正式翻译服务、`DocumentIRWordRenderer`。
   - 写 DOCX、DocumentIR JSON 和质量元数据。
3. 迁移本地入口：
   - `scripts/dev/run_local_mineru_conversion.py`
   - `scripts/dev/run_local_mineru_debug_config.py`
   - `scripts/dev/run_local_mineru_quality_matrix.py`
   - `scripts/dev/run_component_pdf_regression.py`
4. 更新测试：
   - 本地 CLI/config 不再 mock `runtime_runner`，改 mock formal adapter。
   - 最小 committed MinerU sample 可以生成可打开 DOCX。
   - quality matrix translation blocked 分支保持不调用转换 adapter。
5. 更新文档：
   - `docs/dev/local-conversion-sandbox.md`
   - `docs/dev/component-pdf-regression-governance.md`
   - `docs/dev/local-component-pdf-debugging-implementation-plan.md`
6. 搜索残留：
   - `rg "runtime_runner|app.conversion.runtime_runner" scripts docs tests app`
   - 剩余命中必须是 legacy 正式历史链路或明确文档说明。

## Validation

优先运行：

```bash
.venv/bin/python -m unittest tests.test_conversion_sandbox_dev_tools
.venv/bin/python -m unittest tests.test_local_mineru_quality_matrix
.venv/bin/python -m unittest tests.test_component_pdf_sample_governance
```

核心转换回归：

```bash
.venv/bin/python -m unittest tests.test_document_ir_mineru_converter_layout
.venv/bin/python -m unittest tests.test_document_ir_word_renderer_layout
```

必要时运行正式链路 targeted：

```bash
.venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_saves_mineru_raw_ir_and_image_assets \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_generated_word_keeps_renderer_ooxml_semantics \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_passes_subscript_config_to_document_ir_renderer
```

## Risk Checks

- 不提交生成物：`git status --short` 检查 `mineru_result/`、`tests/tmp/`、DOCX/PNG/PDF。
- 不泄露敏感信息：文档和报告不包含真实 API key、完整 provider response、signed URL。
- 不新增脚本层排版逻辑：diff 中 `scripts/dev/*` 只做调用适配和报告，不写 OOXML/layout 修复。
