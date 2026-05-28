---
doc_type: decision
category: architecture
date: 2026-05-28
slug: pdf-online-api-contract
status: active
area: backend jobs api
tags: [backend, jobs, api, pdf, mineru]
---

## 背景

PDF 在线链路已经从 `submit_to_mineru -> callback -> parsed/failed` 演进为 `submit_to_mineru -> callback -> parsed_result_package -> conversion -> completed/failed`。

这带来两个需要拍板的 API 问题：

- `parsed_result_package` 是否作为正式对外 artifact
- `parsed` 是否继续作为对外可观察 status

## 决定

`parsed_result_package` 作为受支持的中间 artifact 对外暴露。调用方可以通过 jobs 文件列表和 `download/parsed-result-package` 下载它，用于排障、复现和回溯。

`result` / `result_docx` 仍是默认交付物。产品语义上不把 `parsed_result_package` 提升为和最终 DOCX 同等优先级的主交付物。

`parsed` 短期继续保留在对外 `status` 枚举里，但它只表示“MinerU 结果已确认可用”的瞬时里程碑。调用方不得依赖 callback 成功后 job 会稳定停在 `parsed`。

## 理由

`parsed_result_package` 已经进入统一 artifact 合同，并且下载 alias 已经存在。保留对外下载能力能提升排障和复现能力，同时不会改变最终 DOCX 的主交付语义。

`parsed` 仍然对解释工作流有价值。立即移除它会破坏当前 schema 兼容性，也会让事件和状态排障少一个明确里程碑。把它定义为瞬时里程碑，可以兼容当前自动续跑到 `completed` 的主链路。

## 考虑过的替代方案

- 完全隐藏 `parsed_result_package`：会降低排障和回溯能力，且与当前文件列表和下载能力不一致。
- 把 `parsed_result_package` 提升为主交付物：会模糊最终 DOCX 和中间 zip 的产品语义。
- 立即从对外 schema 移除 `parsed`：兼容风险较高，且需要单独的 API 版本策略。
- 恢复 callback 成功后稳定停在 `parsed`：会让 PDF 在线链路重新停在中间态，不符合当前自动完成目标。

## 后果

- Jobs API 文档必须明确 `parsed_result_package` 是受支持的中间 artifact，而不是最终交付物。
- 调用方轮询时应以 `completed/failed` 作为最终状态，不应把 `parsed` 当作稳定等待态。
- 后续如果要移除或淡化 `parsed`，需要作为单独的兼容性变更处理。

## 相关文档

- `docs/api/jobs.md`
- `docs/api/mineru-callbacks.md`
- `docs/dev/backend-pdf-online-completion-change-summary.md`
