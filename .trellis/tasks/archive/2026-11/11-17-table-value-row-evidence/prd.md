# 提高参数值列的行取证覆盖率

## 目标

在可信源 PDF 中为更多参数表跨列值确定实际同行和数值列。证据不足的值保留原跨度及可定位警告，用户仍能转换和下载可编辑 DOCX。

## 背景

当前行匹配要求另有独立同行锚点，无法区分缺锚点、重复锚点和合并上下文未取证。本任务承接 [Datasheet 基线的开放问题](../../../11-11-datasheet-quality-baseline-contracts/issues.md#当前开放问题)。两份 gs-008 解析输入的发现数量不同，以 [固定样本与预查记录](research/gs008-baseline.md) 为验收口径。

## 需求

- R1：新增 `row_anchor_missing`、`row_anchor_nonunique`、`rowspan_context_unresolved`、`value_word_nonunique`、`unit_row_mismatch`、`source_row_band_count_mismatch`、`row_sequence_ambiguous`。质量表格接口和 OpenAPI 公布细分原因，保留源格定位与 `manual_review_required`；已有 `row_ambiguous`、`unit_mismatch` 等历史值仍可读取。
- R2：优先保留可靠的同行锚点。必要时用数值区中唯一、精确且可见的完整数值反查行，并以同一表头、单位和源行上下文交叉验证。数值重复时允许精确的参数符号或名称、条件、值、单位组合消歧；仍有候选时保持未决。
- R3：以实测合并边界和连续 band 证明 `rowspan`，按源格内相对行位置对应。整表行序可用已独立定位的锚点消歧，只采纳唯一全局最优解；顺序自身不构成证据。
- R4：保留同源 PDF、layout、可见字形、独立列、原跨度内的目标列、释放格为空和实际 Word 认证。未决沿用现有 warning 和内部 DOCX 下载路径，现有审核及发布条件继续适用。

## 验收

- [x] AC1 / R1：每个新增原因有可复现触发；接口返回对应 `reason_code`、原 finding ID 和零基源行/格，OpenAPI 与实际模型一致；旧原因仍可读。
- [x] AC2 / R2–R3：覆盖同名参数配唯一值、空条件、参数和单位跨行、相同值配不同条件、需要整表锚点消歧。覆盖重复值或签名冲突、单位错行、跨行边界不符、计数不合、等价解和顺序冲突负例。
- [x] AC3 / R4：用实际 Poppler 与 DOCX 回归核对轻微表框截断、错误来源和字形不足或歧义。合法修正放在目标列且 `gridSpan=1`；未决保留原跨度并以 warning 交付，不使普通转换失败。
- [x] AC4 / R2–R4：固定完整 gs-008 的 23 个原 finding，至少 14 项（60.87%）有正确的自动或已有核定证据并通过实际 Word 认证。逐格与独立 PDF 标注比较，自动错修数为 0；同一格自动与已有证据只计一次。`±5 µV` 在 TYP、`±100 µV` 在 MAX，两格均只占一列。其余以 warning 保留。另一份 18 项留存原包单列统计。

## 范围外

不扩大坐标容差、模糊匹配技术数字、按行号或数值列猜测、跳过来源或字形核验；不改造通用数学排版，不批量回填历史记录，不改生产开关，不发起外部 MinerU 请求或发布。

[本地实物验收与测试记录](validation.md)
