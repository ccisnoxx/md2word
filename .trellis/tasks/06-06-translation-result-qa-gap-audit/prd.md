# Phase 3 Translation Result QA Gap Audit

## Goal

对照产品成熟化路线图 Phase 3、已归档 `translation-result-qa` 任务和当前代码，完成一次结果质检与可追踪能力 gap audit，为 Phase 3 第一个可执行小任务划清边界。

本任务只做审计、收口判断和后续任务拆分，不实现新功能，不运行 `pdf-mineru` 解析、翻译 provider 或 Word 生成主流程。

## Requirements

- 核实已归档 `translation-result-qa` 的第一版能力是否已经落到后端 API、前端页面、任务详情入口、OpenAPI 和测试中。
- 对照 Phase 3 路线图识别仍缺失的结果质检、证据展示和可追踪能力，并按优先级标注。
- 区分已经完成的能力、文档/验收记录不一致、仍需实现的产品能力、仅需后续测试加固的风险。
- 拆出第一个 Phase 3 小任务，优先聚焦任务级 QA 状态与结果证据展示，不把段落级深追踪和列表筛选全部混进同一个实现批次。

## Acceptance Criteria

- [x] 已读取 Phase 3 路线图和 Phase 2 acceptance。
- [x] 已读取归档 `translation-result-qa` 的 `prd.md`、`design.md`、`implement.md`。
- [x] 已检查当前 term rules、translation term sets、proposal review、translation QA 相关前后端代码和测试。
- [x] 已验证当前 `translation-result-qa` 第一版实现状态。
- [x] 已列出 Phase 3 仍缺的结果质检/可追踪能力和风险。
- [x] 已给出第一个 Phase 3 小任务的拆分边界。

## Non-goals

- 不修改业务代码。
- 不新增或修改翻译、解析、生成 Word 主流程。
- 不运行实际 PDF 解析、翻译 provider 调用或 Word 生成端到端任务。
