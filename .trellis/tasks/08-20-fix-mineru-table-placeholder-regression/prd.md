# 修复 MinerU 空表占位符并防止同类回归

## Goal

修复 MinerU v2 空表续页占位符被误判为真实空表、继而触发 DocumentIR 完整性门禁的问题，并把“上游结构元数据不得冒充正文内容”的边界固化为可执行测试和项目规范，避免同类 MinerU payload 形状再次导致线上任务失败。

## Background

- 线上任务 `docjob_cfcdfa737312` 在 `ir_converting` 阶段失败，错误为 `document_ir_failed: source_ir_integrity:payload_missing:table`；MinerU 解析与结果包下载均成功，草稿模板 `default@4` 已正确绑定但尚未进入渲染阶段。
- 原始 MinerU 包含 421 个 block、20 个 table；唯一异常项是第 167 个 block（`page_idx=11`），其 `content.image_source.path="images/"`、`content.html=""`、`content.table_type="simple_table"`，属于紧随上一页真实表格的空表续页占位符。
- `merge_table_placeholder_continuations()` 通过共享的 `is_empty_table_placeholder()` 识别占位符，但把整个 `content` 交给通用文本收集器后，结构元数据 `simple_table` 被当成 `text_candidates`，导致占位符判断返回 `False`。
- 占位符因此进入 DocumentIR 作为无 HTML 的真实 table，并被新上线的 source→IR 完整性门禁正确阻断。诊断性地把该 block 标记为 `table_placeholder` 后，同一 MinerU 包可完成 DocumentIR 转换。

## Requirements

- 在共享的空表占位符识别边界修复根因，不在完整性门禁或单个任务路径增加绕过、静默降级或兼容兜底。
- 明确定义 MinerU table payload 中“正文内容字段”和“结构元数据字段”的判定：`table_type`、资产目录标记等结构值不得使空占位符被视为有正文；真实表格 HTML、题注、脚注或明确文本仍必须保留。
- 保持现有 source→IR 完整性门禁 fail-closed；真实 table 缺少可渲染 payload 时仍应失败，不得通过放宽 `payload_missing:table` 消除报错。
- 覆盖共享占位符判断和 MinerU→DocumentIR 端到端转换边界，至少包含线上 MinerU v2 形状、真实表格、带实质文本/题注的 table、无前置真实表的孤立空 table 等行为，防止把真实内容误删。
- 将本次根因和可执行合同写入相关 Trellis backend spec，使后续 MinerU payload 适配、通用递归文本提取或完整性门禁变更必须验证结构元数据与正文语义的边界。
- 修复后使用线上失败结果包进行只读/临时目录回归，确认 DocumentIR 转换通过；发布后再重试或克隆原任务验证完整业务链路。

## Acceptance Criteria

- [x] 线上失败样本中的 `images/ + empty html + table_type=simple_table` block 被识别为续表占位符并并入前一真实表，不再生成空 table 主 block。
- [x] 同一 MinerU 结果包通过 MinerU→DocumentIR 转换，source block/type 对账无 blocker，且未通过关闭或放宽完整性门禁实现。
- [x] 真实 table 的 HTML、题注、脚注或实质文本不会被占位符规则误删；缺少可渲染 payload 的真实 table 仍产生 `source_ir_integrity:payload_missing:table`。
- [x] 最小定向单元测试覆盖共享分类器与转换器回归，相关既有测试及项目要求的发布检查通过。
- [x] `.trellis/spec/backend/word-generation-rules.md` 记录 MinerU 结构元数据与正文内容的边界、占位符合并约束及对应验证要求。
- [x] 部署后原问题任务的重试/克隆不再停在 `ir_converting`；若后续阶段失败，保留独立失败证据，不把它归并为本缺陷已解决的证明。

## Out of Scope

- 不修改用户保存的 `default@4` 草稿样式，也不改变 draft 模板授权、版本或发布流程。
- 不删除或绕过 source→IR、layout→renderer 的内容完整性门禁。
- 不为未知 MinerU payload 增加宽泛兼容、猜测性字段扫描或静默跳过所有空 table。
- 不在本任务内调整翻译、渲染排版或人工样式本身；只有修复后全链路暴露出的独立问题才另行记录。
