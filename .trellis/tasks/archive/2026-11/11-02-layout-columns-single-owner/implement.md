# 实施计划

前置：PRD 决策 D1 获用户确认后 `task.py start`。

## 1. 有序任务

1. 先写一致性测试与“缺省栏距按 720”测试，在未改代码时运行：一致性测试应通过（证明两份实现等价），身份断言应失败（证明副本存在）。
2. 删除 `render_plan.py` 副本、改为导入；再跑上述测试全部通过。
3. 更新规格 COL-002 owner 与栏距结论。

## 2. 计划修改文件

- `app/services/renderer/render_plan.py`
- `tests/test_document_ir_word_renderer_layout.py`
- `.trellis/spec/backend/word-generation-rules.md`

## 3. 验证

- 定向：`tests.test_document_ir_word_renderer_layout`、`tests.test_image_group_rendering`、`tests.test_document_ir_mineru_converter_layout`，失败集合与基线 `90ebb407` 对比。
- 不跑全仓回归；不涉及前端。

## 4. 回滚点

单个提交即可回退。

## 5. 实施结果与验证（2026-11-02 北京时间）

- 测试先行：改代码前身份断言失败（副本存在）、行为一致性与 720 缺省宽度测试通过；删除副本后 3 例全部通过。
- 5.1：`render_plan.py` 删除 `split_two_col_blocks` 副本，改为从 `layout_plan` 导入；仓库仅剩一份实现。
- 5.2（D1）：未改代码；规格 COL-002 记录栏距随模板继承、缺省 720 及 LibreOffice 26.2.4.2 实测结论，新增宽度测试锁定该合同。
- 回归：`test_document_ir_word_renderer_layout`、`test_image_group_rendering`、`test_document_ir_mineru_converter_layout` 共 111 例（基线 108 + 新增 3），1 失败 13 错误与基线 `90ebb407` 集合一致；COL-002 列出的三个原生分栏测试通过。
- 未做 Word/WPS 视觉验收；未跑全仓回归。
