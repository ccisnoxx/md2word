# 完善页面格式字体配置：实施计划

## 实施顺序

- [x] 在 `TemplateParagraphStyleConfig`、`TemplateHeaderConfig`、`TemplateFooterConfig` 和 legacy `ParagraphStyleConfig` 中加入已确认的字体字段，并让 legacy YAML loader 读取它们。
- [x] 在 `app/conversion/docx_rules/run_fonts.py` 实现唯一的字体槽位映射与缺失字段兼容回退；让正式和 legacy 两条 run 样式入口复用它。
- [x] 调整 legacy 英文文档覆盖：旧配置保持现有 Arial 行为，新配置不再覆盖显式中文/西文字体。
- [x] 扩展页面样式 `field_schema` 标签与字段，并在 `TemplateReadService` 读取边界补齐旧段落、页眉和页脚字体字段；同时保留 seed 已有页面尺寸并补齐严格 schema 要求的 `header_fill`，保持完整 GET→POST 可保存。
- [x] 让正式渲染器把页眉三字体传入 run 样式，并对页脚 run 应用页脚字体配置。
- [x] 更新 `datasheet_template.yaml`，为所有文字分组写入 `Arial` / `Times New Roman` 默认值及中文说明。
- [x] 更新后端 API、配置加载、legacy helper、DocumentIR OOXML 测试；更新前端 smoke mock/断言，不改生产 Vue 表单逻辑。
- [x] 执行 touched-scope 文档检查：新增 Python 模块写中文模块 docstring；新增/修改的非显然函数、兼容分支、异常或开发者可见文本使用中文；同步 YAML 字段注释。
- [x] 检查 diff，确认没有主题字体删除、隐藏默认、第二套字段来源、未授权 schema 升级或无关改动。

## 最小验证

按失败定位从小到大执行：

```bash
.venv/bin/python -m unittest tests.test_text_render_characterization tests.test_render_config_characterization
.venv/bin/python -m unittest tests.test_document_ir_word_renderer_layout
.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_layout_config_admin_creates_draft_version_without_mutating_source_yaml
cd frontend && npm run build
.venv/bin/python scripts/ops/check_release.py
git diff --check
```

若完整 release check 超出本地合理时间或受外部环境阻塞，保留前三项定向后端测试与前端构建作为替代，并在交付中明确剩余风险。按项目规范不启动本地 API、Worker、MySQL、Redis/Celery、MinerU 或浏览器 smoke 作为 P0 证据。

## 高风险文件与回滚点

- `app/domains/templates/read_service.py`：配置中心严格字段合同和旧配置补齐边界；若 GET/POST 往返失败，先回滚此处 schema/归一化改动。
- `app/conversion/docx_rules/run_fonts.py`、两条 renderer 调用点：四字体槽位的统一所有者；若产物回归，回滚 helper 及两个调用点必须同步进行。
- `resources/template_configs/datasheet_template.yaml`：版本化 seed；不得原地改 `var/` 历史版本。
- 已部署且产生新草稿后，不单独回滚代码；同时处理含新增字段的草稿，否则旧严格校验无法再次保存。

## 启动实现前检查

- [x] `prd.md` 无阻塞问题，兼容策略与默认字体已由用户确认。
- [x] `design.md` 和本文件已由用户审阅批准。
- [x] `implement.jsonl`、`check.jsonl` 已包含真实规范条目。
- [x] 运行 `task.py start` 后再修改产品代码。

## 验证结果

- legacy 字体与配置：39 项通过。
- DocumentIR renderer：最终 31 项通过；最后一次复核额外运行 58 项 renderer 测试通过。
- 配置 API 草稿往返：1 项通过。
- 前端构建：通过；仅有项目规范标记的既有第三方 PURE 注释和大 chunk 警告。
- release gate：36 个目标、181 项 unittest，全通过，`ok=True`。
- `git diff --check`、受影响 Python `compileall`：通过。
- 本地未启动 API、Worker、MySQL、Redis/Celery、MinerU 或浏览器 smoke；配置中心 UI 由现有 schema 驱动表单、前端构建和 smoke 合同覆盖。
