# P0c 实施计划

前置：PRD 决策 D1–D4 获用户确认后才 `task.py start`。

## 1. 有序任务

1. 测试先行（AC1–AC5）：在 `tests/test_mineru_artifact_validator.py` 中
   - 修改 `test_allowed_raster_formats_keep_word_and_reference_boundaries`：WEBP 改为断言成功、PNG、warning；其余格式保留“原字节相等、无 warning”。
   - 修改 `test_cached_reference_raster_does_not_skip_required_word_header`：WebP 改为成功，断言 `Image.open`/`WordImage.from_blob` 调用次数符合缓存语义、两个图片块各一条 warning、参考图状态不变。
   - `test_images_empty_invalid_word_unsupported_and_local_bomb` 中的 WebP 失败断言改为成功断言；新增 CMYK JPEG、无 APP0 JPEG、带透明 WebP、确定性、超限回退失败用例。
2. 验证器实现：`_ImageInspection` 字段、`_word_compatible_png`、warning 记录、`ValidatedImage.normalized_from`。
3. 白名单：`evidence.py` 的 `REPORT_CODES`/`REPORT_REASONS`。
4. 透传与登记：`mineru_converter`（`MinerUImageAsset`、block metadata）、`execution`（文件名扩展名、metadata）。
5. 端到端：新增 eager Worker 用例——WebP 普通图片任务成功、DOCX 媒体为 PNG、image_asset 文件 MIME/扩展名正确、质量 warning 计数增加；WebP 表格参考图占位成功。
6. P0a 测试修正：`tests/test_document_job_failure_diagnostic.py` 改用真正不可读图片（如截断 PNG）（AC6）。
7. 规格：修订 `word-generation-rules.md` IMAGE-001、INPUT-002。

## 2. 计划修改文件

- `app/services/document_ir/artifact_validator.py`
- `app/services/document_ir/mineru_converter.py`
- `app/domains/document_jobs/execution.py`
- `app/services/renderer/evidence.py`
- `tests/test_mineru_artifact_validator.py`、`tests/test_document_job_failure_diagnostic.py`、端到端用例（新文件或 `tests/test_image_group_rendering.py` 视夹具复用情况）
- `.trellis/spec/backend/word-generation-rules.md`

## 3. 验证

- 定向：`tests.test_mineru_artifact_validator`、`tests.test_document_job_failure_diagnostic`、`tests.test_image_group_rendering`、`tests.test_document_ir_mineru_converter_layout`、新增端到端用例；失败用例与基线 `a6d2207c` 对比。
- 不跑全仓回归与前端；如时间允许，用一份含 WebP 的合成 ZIP 走正式转换脚本生成 DOCX，并用 LibreOffice 转 PDF 目视确认图片显示（记录工具版本，未做则如实说明）。

## 4. 回滚点

验证器改动与登记改动各自独立提交前可单独回退；无数据迁移。

## 5. 实施结果与验证（2026-11-01 北京时间）

- 决策：D1–D4 按推荐执行；实施调整为“仅正文必需图片记 warning，表格参考图只规范化不记”（理由见 PRD 范围 5）。
- 验证器测试（`tests.test_mineru_artifact_validator`）：66 例，新增 4 例（WebP/CMYK JPEG/无 APP0 JPEG/透明 WebP 规范化与确定性、DPI 保留与超限返回 None、Word 可识别的带 JFIF CMYK JPEG 保持原字节、规范化失败仍报 `invalid_image_asset`、参考图静默规范化）与改动 3 例全部通过；其余 15 个错误（表格占位 `table_placeholder_source_unavailable` 等）与基线 `a6d2207c` 逐条一致，未处理。
- 端到端（`tests.test_image_normalization_pipeline`，真实 eager Worker）：WebP 正文图任务成功、登记文件 `image/png` 且扩展名 `.png`、metadata 含源格式与 sha256、DOCX 媒体与登记字节一致；缺 HTML 表格的 WebP 参考图占位写入 DOCX。同一测试在基线上分别以 `document_ir_failed/invalid_image_asset` 与 `render_failed/table_placeholder_integrity_failed` 失败，证明覆盖原缺陷。
- P0a 诊断测试改用截断 PNG 后 8 例通过。
- 相关集合（image_group_rendering、converter_layout、runtime_dependency_declarations、failure_diagnostic、pipeline）72 例：1 失败 12 错误，与基线集合一致。
- 未做 LibreOffice/Word 目视核对；未跑全仓回归与前端（前端无改动）。
