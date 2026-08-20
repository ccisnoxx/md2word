# 实施计划：修复 MinerU 空表占位符并防止同类回归

## 1. 开发前基线

1. 读取本任务 `prd.md`、`design.md`、`implement.md`、`research/root-cause.md` 及 manifests 引用的规范。
2. 确认工作区除本任务规划文件外没有未识别改动。
3. 运行当前占位符定向测试，记录既有测试通过但缺少真实 nested v2 形状的基线。

## 2. 测试先行

1. 将现有真实 MinerU 空表续页用例补齐为线上脱敏形状：字段嵌套在 `content`，包含 `table_type` / `table_nest_level`。
2. 增加明确正文负例，证明结构元数据被忽略但 `content.text` / `content.description` 仍阻止占位符合并，并最终由完整性门禁阻断无 HTML 的真实 table。
3. 复用既有 nested HTML/caption/footnote 用例；只有证据显示缺口时才增加断言，不复制大 fixture。

## 3. 根因修复

1. 在 `layout_signals._is_mineru_empty_table_placeholder()` 删除 `content` 容器级文本扫描，保留已命名语义叶字段。
2. 不修改共享文本递归函数、占位符核心判断、DocumentIR schema 或完整性门禁。
3. 对 touched Python 范围执行注释/docstring/开发者可见文本检查；仅在非显然合同需要时更新中文说明。

## 4. 规范更新

更新 `.trellis/spec/backend/word-generation-rules.md`，明确 nested MinerU 结构元数据与正文语义边界、占位符归一化顺序、正反例要求及 fail-closed 约束。

## 5. 本地验证

按从小到大执行：

```bash
.venv/bin/python -m unittest \
  tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_merges_real_mineru_empty_table_continuations \
  tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.<新增负例>
.venv/bin/python -m unittest tests.test_document_ir_mineru_converter_layout
.venv/bin/python -m compileall app/services/document_ir/layout_signals.py tests/test_document_ir_mineru_converter_layout.py
git diff --check
.venv/bin/python scripts/ops/check_release.py
```

不重复运行与变更无关的本地服务、MySQL、Redis/Celery 或 Playwright。

## 6. 线上验证与发布边界

1. 本地实现、Trellis check 和 diff review 完成后，先向用户提交 commit 计划并取得确认；不得自动提交或推送。
2. 目标 commit 推送后按现有 hostdzire release 流程部署，不覆盖历史 release 或用户数据。
3. 先验证 `live/ready` 与 `check_release.py --runtime-url`。
4. 在新容器内对 `docjob_cfcdfa737312` 已保存的原 MinerU ZIP 使用临时目录执行 converter，只读取旧 artifact、不写回任务记录，确认同一结果包通过 source→IR 对账。
5. 通过现有 retry/clone 流程重跑 `docjob_cfcdfa737312` 或等价任务：确认不再停在 `ir_converting`，并保存后续阶段的独立证据。
6. 若后续翻译/渲染失败，不扩大本缺陷结论；另行记录新的 error code、stage 和 artifact。

## 7. 最终 review

- 没有针对任务 ID、页码、PDF 型号或 `simple_table` 值写特例。
- 没有第二套 MinerU parser、宽泛 fallback 或完整性门禁降级。
- nested 结构元数据不再冒充正文，明确正文仍不会被静默删除。
- 测试覆盖正式 `MinerUToDocumentIRService`，不以旧 runtime characterization 代替正式证据。
- touched-scope 中文文档约定和验证报告完整。

## 8. 本地实施结果（2026-08-20）

- `layout_signals._is_mineru_empty_table_placeholder()` 不再扫描整个 `content` 容器，只读取明确语义叶字段；题注和脚注继续作为内容证据。
- 正式 converter 测试使用线上脱敏 nested v2 形状，并覆盖真实 HTML、明确正文、题注、脚注和孤立空 table 负例；checker 补强了真实 HTML 位于续表上下文时仍被保留的证明。
- `INPUT-005` 已写入 Word 生成规范，完整性门禁和 `integrity.py` 未修改。
- 两项关键回归、完整 converter 19 项测试、`compileall`、`git diff --check` 和 `scripts/ops/check_release.py` 均通过；release check 实际执行 202 项测试，OpenAPI、前端合同与 mock smoke 通过。
- 旧线上 ZIP（SHA-256 `f60e2002654a873492c38d0c018e595cb44804f037a8adcc64973bea31452419`）已用当前修复临时转换成功：420 个归一化 source blocks、19 个 table、38 个图片资产、`blocking_quality_flags=[]`；临时文件已删除。
- 待完成：任务 retry/clone、提交、推送和部署。
