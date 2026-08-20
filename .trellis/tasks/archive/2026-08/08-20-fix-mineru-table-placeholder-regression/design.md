# 技术设计：修复 MinerU 空表占位符并防止同类回归

## 1. 不变量与边界

正式 owner 仍是 `MinerUToDocumentIRService` 的输入归一化链：

`MinerU content list → merge_table_placeholder_continuations → DocumentIR → source integrity gate`

本任务维护两个不变量：

1. 只有有确定性证据的空表续页占位符可以在 source inventory 建立前被并入上一真实表。
2. 任何被保留为真实 table 的 source block 都必须携带可渲染 HTML；缺失时继续由完整性门禁失败关闭。

## 2. 最小修复

在 `app/services/document_ir/layout_signals.py::_is_mineru_empty_table_placeholder` 中，table 正文候选不再把整个 `content` 容器交给通用递归文本收集器，只读取已命名的语义叶字段：`text`、`equation_content`、`math_content`、`latex`、`alt`、`description`。

`find_values_by_key()` 本身递归查找这些叶字段，因此真实的 `content.text` / `content.description` 仍会被发现；`content.table_type`、`table_nest_level` 和资产路径不会再冒充正文。HTML、caption、footnote 和资产标记继续由现有专用 extractor 负责，不新增第二套 MinerU parser。

不修改：

- 全局 `coerce_text_list()` / `collect_text_from_fields()`，避免影响正文、列表、题注和脚注调用方；
- 共享 `is_empty_table_placeholder()` 的保守条件，避免让 `images/` 无条件覆盖真实正文证据；
- `build_source_integrity()` 和 `payload_missing:table`，保持 fail-closed。

## 3. 回归合同

在正式 converter 测试中使用与线上一致的 nested v2 形状：

- 正例：真实 HTML table 后跟 `content.image_source.path="images/"`、空 HTML/caption/footnote、`table_type="simple_table"`，占位符被合并并记录 continuation height。
- 保留正例：`content.html` 有真实 table 时不被合并，仍生成 table block。
- 负例：同样的资产/空 HTML 条件下存在明确 `content.description` 或 `content.text`，不得静默当作占位符；由于仍没有 HTML，应由 `source_ir_integrity:payload_missing:table` 阻断。
- 既有顶层 legacy 形状继续通过，证明兼容未倒退。

测试断言最终 observable behavior，不直接绑定私有调用次数。

## 4. 防复发规范

在 `.trellis/spec/backend/word-generation-rules.md` 的 INPUT/IR 规则中补充：

- 通用 JSON 容器、schema 枚举、类型标签和资产路径不是正文证据；
- 结构过滤必须基于专用语义字段，并有真实 nested payload 正反例；
- 占位符合并发生在 source inventory 之前，归一化后再对账；
- 未被确定识别的空 table 继续失败关闭。

这把本次经验固化为后续修改 MinerU schema 适配、递归文本提取和完整性门禁时都必须遵守的可执行合同。

## 5. 兼容、风险与回滚

- 不改 API、数据库、DocumentIR schema、任务状态或模板版本合同。
- 主要风险是误删有实质内容的 table；由明确文本负例、真实 HTML/caption/footnote 既有用例和完整性门禁共同限制。
- 若定向或真实样本出现内容丢失，只回滚 `layout_signals.py` 的字段集合和对应测试/spec；不得关闭完整性门禁。
- 原失败任务是终态记录，不直接修改历史 payload；部署后通过现有 retry/clone 流程产生新执行证据。

## 6. 不采用的方案

- 不把 `images/` 提前设为无条件占位符：可能吞掉同时携带真实正文的异常 table。
- 不让 `coerce_text_list()` 全局忽略 `table_type`：它是通用文本工具，扩大改动面并继续依赖黑名单。
- 不针对 `simple_table` 写值特例：下一个结构枚举仍会复发。
- 不将 `payload_missing:table` 降为 warning：这会恢复静默内容丢失。
- 不提交线上 5.8MB 用户结果包；测试只保留脱敏最小结构，真实包仅作临时/线上验证。
