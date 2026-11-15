# 参数表数值列跨列检测

## 目标

MinerU 输出的复杂参数表 HTML 会把单个参数值错误地声明为跨多个并列数值列（例如 OPA228 P7 中 `±5` 从 `TYP` 变为跨 `MIN–TYP`，`±100` 从 `MAX` 变为跨 `MIN–MAX`）。现有 Grid 与 Word 证据只证明"忠实渲染了来源 HTML"，不能发现这类参数语义错误。

本任务只做第 1 步：在不读取 PDF 的前提下，基于 Grid 结构识别这类可疑跨列并作为表格质量 blocker 报出，使样本在人工修正前不能作为普通通过件批准或发布。

## 范围

- 在表格验证器（`app/services/tables/validator.py`）新增规则 `table_value_column_span_ambiguous`，原因码 `value_column_span`。
- 在质量合同（`app/services/tables/quality.py`）登记规则、默认严重度和报告重读校验。
- 单元测试覆盖命中与主要不命中场景；用 gs-008 真实 MinerU HTML 片段做回归。

## 不在范围

- 不读取 PDF 文本层、不计算 bbox 列绑定（第 3 步，`value_column_binding_mismatch`）。
- 不自动修正 Grid 或 Word `gridSpan`；不新增人工跨列修正记录（第 2 步）。
- 不改变 `is_header` 判定、Grid 构建或渲染行为。

## 规则定义

1. **数值列标签行**：同一行内至少两个不同标签，且每个标签单元格 `colspan == 1`。标签取值（大小写不敏感、去首尾空白）：`MIN`/`TYP`/`MAX`/`NOM` 及其常见全称与带点缩写、`LOW`/`HIGH`、中文最小/典型/最大值。不依赖 `<th>`，因为 MinerU 常以 `<td>` 输出表头。
2. 按 Grid 全局行顺序扫描；遇到标签行即更新当前数值列集合（支持续表重复表头），标签行之前的行不检查。
3. **命中条件**：非表头、非标签行的单元格，内容全部为普通文本 run 且整体为单个数值（可带 `±`/正负号/比较符与单位），其列区间覆盖当前数值列集合中 ≥2 列。
4. 区间文本（如 `-40 to 125`）、说明文字（如 `See Figure 5`）、空单元格、显式标注 `REF`/`BSC` 的参考尺寸不命中，避免误报合法跨列。
5. 默认严重度 `blocker`；属于启发式规则，可由 `TableValidationPolicy.rule_severities` 显式降级。
6. 标签行没有 TYP/NOM、且值恰跨一对 MIN–MAX（或 LOW–HIGH）时，报变体 `table_value_column_span_ambiguous.shared_limits`（原因码 `shared_limit_value`，warning）。依据：RS2G04 封装尺寸表 `L1 0.525` 在源 PDF 中确为居中跨 Min/Max 的共享值。

## 机器码说明

`TableQualityFlag.code` 合同只允许 `[a-z0-9_]`，因此采用 `table_value_column_span_ambiguous`，由 producer `table_validator` 提供命名空间，而不是 `table_semantics:value_column_span_ambiguous`。

## 验收标准

- [x] gs-008（OPA228 P7）电气特性表中 `±5`、`±100`、`0.2`、`110` 等跨多个数值列的单元格均产生该 blocker（真实结果包共 23 处）。
- [x] 单列数值、跨非数值列的条件文本、区间文本、REF/BSC 值、标签行本身均不产生该规则。
- [x] 报告可通过 `TableValidationReport` 重读校验；伪造的证据（覆盖列数与单元格不符）被拒绝。
- [x] 既有表格相关测试保持通过；`tests.test_render_page_degradation` 的 `test_table_plan_failure_is_degraded_by_located_page` 在 HEAD 上同样失败，属历史测试维护，不在本任务范围。

## 本地样本核对（2026-11-15）

| 样本 | blocker | warning | 结论 |
|---|---|---|---|
| OPA228 P7（gs-008） | 23 | 0 | 均为数值误跨 MIN/TYP/MAX |
| OPA228 P1/P2/P6 | 0 | 0 | 无误报 |
| RS2G04 | 0 | 2 | 封装表 `L1` 共享值，已对照 PDF 文本层 |
| TPL51200 | 0 | 0 | REF/BSC 值已排除（剩余 2 个为原有 `table_unit_glued`） |

已知漏检：`(V+)-2` 这类表达式值跨 TYP–MAX 时不匹配单值模式，需第 3 步的 PDF 列绑定覆盖。

## 已知影响

- blocker 不阻止生成 DOCX，但任务不能批准复核、不能发布（`review_writer.py`、`publication.py`）。在第 2 步落地前，命中样本只能通过策略降级或线下修正处理。
