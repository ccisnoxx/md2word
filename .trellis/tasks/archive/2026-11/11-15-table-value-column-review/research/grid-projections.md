# Grid 修正、Word 与交付证据的共用边界

- 问题：在保留 MinerU 原始 HTML 及源 Grid 证据的前提下，将参数值从一个跨度收窄到该跨度内的单列。
- 范围：现有工作树的 Grid、渲染计划、OOXML 认证、表格报告和翻译上下文。
- 日期：2026-11-15。

## 已确认的事实

| 位置 | 现有职责 |
| --- | --- |
| `app/services/tables/grid_builder.py:48–81,84–108,143–169` | 源逻辑表和当前 IR 渲染分别构建 Grid。两者共用顺序占位，源 Grid 依据真实 fragment 与源序号，渲染 Grid 依据当前 block HTML 及独立 hash。 |
| `app/services/tables/validator.py:334–367,412–479` | 跨列规则检查源 Grid。单表验证重新构建源 Grid，对原坐标、规范化 HTML 和诊断做完整等值校验。 |
| `app/services/renderer/logical_table_plan.py:165–236,263–361` | 有真实源账本的 fragment 在此投影当前 IR。计划依赖片内列数、续表关系、保留行范围和当前渲染指纹。 |
| `app/services/renderer/table_renderer.py:88–113`、`native_table_renderer.py:123–157` | 行迭代按实际列排序，并检查活跃 rowspan、重叠和边界。Word 逐列读取同一计划，自动将空槽写为单列空格。 |
| `app/services/renderer/table_content_evidence.py:95–124`、`content_contract.py:385–417,454–476` | 认证依据同一计划核对实际行、列、合并跨度、技术内容和空格，按源 cell 序号保留内容归属。 |
| `app/services/tables/evidence.py:219–225,263–283,353–375,386–426` | 源摘要绑定报告原始坐标。重读要求 `table_validator` flags 与报告 findings 一一相等，并重算交付状态、计数和报告指纹。 |
| `app/domains/translation/table_context.py:55–126`、`app/services/tables/models.py:46–55,200–228,291–302` | 源 cell/run 身份由源序号生成。翻译选择 DOM 原文本序号，按源行/源 cell 序号与临时 Grid 一一对应，坐标用于上下文中的列与表头覆盖。 |

## 推荐落点

1. 向一个已核验的源片段提供局部变换。以片内 `source_row_index`、`source_cell_index` 连接原 cell，并核对记录的旧区间和源内容指纹。限制目标为原 `colspan` 范围内的一个已确认数值列，首版处理数据行的单行值。复制目标 cell，更新 `column` 和 `colspan=1`。其余锚点、行列数、源序及 runs 保留。释放的列由稀疏 Grid 空槽表示。此为现有 Word writer、几何及空槽内容认证已支持的形状。
2. 在真实源 fragment 到当前渲染视图的边界应用上述变换，例如 `_build_group_current` 取得当前 Grid 后、发布给表计划前。以源行/cell 序和旧区间核对当前（可含译文）视图，原 HTML 与规范化 HTML 保留。先认证同形投影，使用现有行迭代检查最终占位。将归一化的已采纳记录或投影指纹纳入受影响片段的有效 `render_input_sha256`，复用计划的表锚、片段锚和内容认证。源 cell/run ID 按原规则稳定。若译文也消费修正后的列语境，复用同一变换，并保持 DOM 文本节点索引和 DOM/Grid 一一关系。
3. 保持 `TableValidationReport` 的源坐标、源 findings 和现有重建认证。增加已应用修正的附加证据，绑定确切源 cross-span finding、源 cell、原跨度、目标列和实际输出片段。只有同一修正投影的 DOCX 几何及内容认证通过后，交付 flags 才从原 findings 中排除该记录解决的 `table_value_column_span_ambiguous`。重读按该窄规则重建允许排除的集合，同时核对输出片段、保留行和单列几何。报告和文件登记沿用 IR、DOCX、代次及报告指纹的绑定。参考 `app/domains/document_jobs/table_evidence.py:108–150`、`app/domains/document_jobs/base_quality.py:198–208`。

上述变换与附加证据是设计建议。单改 `build_table_grid`、渲染端写入或交付 flags 均无法闭合三条证据链。顺序占位前仅改 `colspan` 会推进后续单元格，合成具有源序号的空 cell 会侵入真实源索引及翻译契约。

## 必须覆盖的边界

- 来源一致的两次回放，比较源 Grid、PDF/MinerU/原 HTML 指纹、已应用记录、有效列投影及 Word 实际内容。保持 `±5 → TYP`、`±100 → MAX`、空出的 MIN/TYP、原 ±75 和单位的 rowspan，接受同源产物语义和证据一致。
- 完整 `gs-008` 继续保留原始 23 项跨列发现作为来源证据。交付证据只结算已核定的两项，其余 21 项仍阻断。片段级对照可证明成功修正两项的门禁结果。历史参照见 `.trellis/tasks/archive/2026-11/11-15-value-column-span-check/prd.md:36,58`。
- 逐项替换来源指纹、目标 cell 或当前 Grid 原形，确认拒绝。覆盖重复目标、相交占位、错误标签、遗漏应用、修正后正文写入错误列、空槽被填充、修正证据损坏及旧产物混用。
- 保持真实 fragment 坐标与跨页的全局行偏移、输出保留行偏移分开。首版只在明确原生可见片段应用。覆盖续表去重与上游合并覆盖的对照，避免修正改变表头、组宽和续表裁决。支持范围外的目标应明确拒绝。
- 同一 IR 读回后应重建相同修正计划，交付认证现有入口会重建计划并逐字段核对持久证据。带修正记录但渲染未应用时应拒绝，防止落入旧 renderer 或页降级后丢掉修正。参考 `app/services/renderer/render_evidence.py:404–429`、`app/domains/document_jobs/render_execution.py:227–243,376–410`。
- 无记录的历史 IR、报告与现有单元格身份合同继续走原分支。新信息只在存在修正时序列化，重读拒绝声明修正却缺少其认证证据的报告。

相关规范为 `.trellis/spec/backend/word-generation-rules.md:371–381` 的 TABLE-001。依据为本地源代码和第一阶段存档，当前为方案核对。
