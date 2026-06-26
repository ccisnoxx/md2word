# Design: Formal core local MinerU debug entrypoint

## Architecture

新增一个 dev-only formal local adapter，作为本地脚本和正式转换核心之间的唯一适配层。

推荐位置：

- `scripts/dev/formal_mineru_conversion.py`

该模块只做本地路径/文件适配，不实现排版规则。核心调用顺序必须与正式 Document Jobs 主链路一致：

1. MinerU zip/目录输入标准化为 zip。
2. `MinerUToDocumentIRService.convert_zip()` 生成 `DocumentIR` 和 image assets。
3. direct 模式直接渲染；translation 模式通过正式 `DocumentIRTranslationService` 或 dev-only 离线 provider 生成翻译后 IR。
4. `DocumentIRWordRenderer.render_to_bytes()` 生成 DOCX。
5. `analyze_docx_quality_bytes()` / `build_docx_quality_flags()` 生成本地报告元数据。

线上 `DocumentJobExecutionService` 继续拥有持久化、事件、文件登记、translation batch fan-in、retry 和 worker 状态机。本地 adapter 不复刻这些正式工作流能力。

## Contracts

新增内部请求/结果模型：

- `FormalMinerUConversionRequest`
  - `input_path`, `output_path`, `template_path`, `layout_config_path`, `subscript_config_path`
  - `document_language`, `translation_mode`
  - `translation_response`, `translation_request_output`, `translation_trace_output`
  - `translation_model`, `translation_api_key`, `translation_base_url`, `translation_max_pages`, `translation_max_chars`
  - `use_mineru_header_footer` 保留兼容字段；如果正式 renderer 没有对应行为，adapter 不私自实现。
- `FormalMinerUConversionResult`
  - `output_docx_path`, `document_ir_path`, optional `source_document_ir_path`
  - `pages`, `blocks`, `image_assets`
  - `document_language`, `renderer_metadata`, `docx_quality`, `quality_flags`

CLI/config 层继续构建现有 kwargs，再转换成 request；这样 PyCharm JSON 配置不需要大规模改名。

## Translation Handling

- direct：不调用 provider。
- en2zh/ru2zh + `translation_response`：使用 dev-only provider 从本地 JSON 读取结果并走 `DocumentIRTranslationService` 的结构保持逻辑。
- en2zh/ru2zh + key/provider：使用正式 `TranslationProvider` 合同；不使用旧 `translation_runtime`。
- en2zh/ru2zh 缺 key 且缺 response：明确失败或在 matrix 中标记 blocked，不回退 direct。

本任务只迁移入口，不要求完全复刻线上 translation batch split/retry。线上 batch 正确性仍由 document_jobs/P1/P2 gate 覆盖。

## Compatibility

- 现有 CLI 参数和 JSON 字段保持兼容。
- 输出 DOCX 路径保持调用者指定规则。
- 本地 adapter 可额外写 `document_ir_v2.json`、`document_ir_source_v2.json`、`report` 元数据到 output 旁边或调用者指定目录，但不能要求用户修改现有 JSON 配置才能生成 DOCX。
- `runtime_runner` 保留给 legacy `/api/v1/jobs` 和历史文档，不再是本地调试默认路径。

## Rollback

没有 schema/API 迁移。回滚方式是 revert 本任务改动。本地入口迁移失败时，可临时在文档中指向上一个 commit 的 legacy 命令做比对，但排版修复仍不得落回 `runtime_runner`。
