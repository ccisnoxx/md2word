---
doc_type: test-report
slug: pdf-to-word-golden-sample-acceptance-report
component: pdf-to-word-backend
status: superseded
summary: P0 Golden Sample 历史验收报告；2026-06-03 blocked 结论已被 2026-06-17 hostdzire admin signoff 证据取代。
tags: [testing, golden-sample, pdf, word, p0]
last_reviewed: 2026-06-17
---

# P0 Golden Sample 验收报告

## 当前结论

2026-06-17 收口结论：本报告中 2026-06-03 的 `blocked` 判断是历史状态，已被 `.trellis/tasks/06-16-p0-word-delivery-quality-beta/artifacts/hostdzire-golden-sample-20260617T053003Z/report.md` 取代。新的权威证据显示 4 个 OPA228 canonical samples 自动链路 4/4 succeeded、DOCX quality evidence 可用、admin manual signoff valid，`p0_release_ready=true`。

以下内容保留为历史排障和质量演进记录，不再代表当前 P0 发布状态。

截至 2026-06-03，`tests/fixtures/golden_samples/pdfs/OPA228_P1.pdf`、`OPA228_P2.pdf`、`OPA228_P6.pdf` 和 `OPA228_P7.pdf` 已映射到 `manifest.yaml`，作为当前 P0 canonical suite。本轮已在 hostdzire 真实 API / Worker / MinerU 环境完成 4 个样本 live regression：主链路 4/4 succeeded，DOCX 包 4/4 openable。

当前仍不能声明完成 P0 正式验收，原因是：

- 当前 4 个 canonical 样本的人工质量均未达到 P0。
- P0 质量线要求接近原版排版，同时符合 Word 文档排版标准；heading、Word list、双栏/宽表布局、caption/table 顺序和公式/特殊符号仍存在缺口。

失败分类结论为 `pipeline-parity-gap`：官方 `app/conversion/runtime` 中已有部分 heading、list、formula、caption、table 和 layout 策略，但当前 API `document_jobs -> DocumentIR -> app/services/renderer` 链路没有接入这些 legacy runtime 策略。历史上这些策略曾复制到 `md2word_main`；2026-06-23 起 `md2word_main` 只作为薄调试壳，不再是修复入口。

## 已完成

- 样本目录：`tests/fixtures/golden_samples/pdfs/`
- 样本清单：`tests/fixtures/golden_samples/manifest.yaml`
- 人工验收模板：`tests/fixtures/golden_samples/acceptance-record-template.md`
- 批量回归脚本：`scripts/ops/run_golden_sample_regression.py`
- 回归输出目录：`tests/tmp/golden_sample_runs/`
- 样本映射：`OPA228_P1.pdf`、`OPA228_P2.pdf`、`OPA228_P6.pdf` 和 `OPA228_P7.pdf` 已分别作为 `gs-003`、`gs-004`、`gs-006` 和 `gs-008` 纳入正式 manifest。
- 真实回归批次：`20260603T070724Z`，4 个 runnable 样本全部 succeeded，报告见 `.codestable/features/2026-06-03-golden-sample-live-regression-scale-up/live-regression-run.md`。
- 人工质量记录：`docs/testing/pdf-to-word-golden-sample-manual-quality-records-20260603.md`。
- 失败分类：`.codestable/features/2026-06-03-golden-sample-live-regression-scale-up/failure-classification.md`。
- layout parity 实现记录：`.codestable/features/2026-06-03-document-ir-layout-risk-pass/layout-parity-audit.md` 和 `.codestable/features/2026-06-03-document-ir-layout-risk-pass/document-ir-layout-risk-pass-checklist.yaml`。

## 当前执行状态

| 项目 | 当前值 |
|---|---|
| 清单样本数 | 4 |
| 正式匹配 PDF 数 | 4 |
| Manifest 外 PDF 数 | 0 |
| Manifest 外 PDF | none |
| 可运行正式样本数 | 4 |
| 主链路已执行正式样本数 | 4 |
| 主链路成功数 | 4 |
| 主链路失败数 | 0 |
| 主链路成功率 | 100.00%（4/4，覆盖当前 P0 canonical suite） |
| P0 目标 | 4 个 canonical 样本 4/4 主链路成功、4/4 Word 可打开可编辑、4/4 admin 人工质量通过 |
| 人工质量状态 | 4/4 未通过 P0 版面与语义质量 |
| 当前状态 | blocked: 主链路已在 4 个 canonical 样本上通过，但仍需修复 `pipeline-parity-gap` 暴露的 DocumentIR layout 与 renderer 可编辑输出质量 |

## 最近脚本验证

2026-06-02 已运行一次 Golden Sample 脚本做 inventory smoke。该次运行使用当时仍包含 backlog 占位样本的旧 manifest、dummy bearer token，未启动真实后端/Worker/MinerU，因此只作为历史脚本字段验证，不计入正式 P0 回归。当前正式 manifest 已收敛为 4 个 OPA228 canonical 样本。

| 项目 | 结果 |
|---|---|
| Manifest 样本数 | 12（历史旧 manifest） |
| 正式匹配 PDF 数 | 1 |
| 实际执行 | 1 |
| 缺少 PDF | 11 |
| Manifest 外 PDF 数 | 0（该次运行发生在 P2/P6/P7 进入当前工作区之前） |
| 成功 | 0 |
| 失败 | 1 |
| 失败原因 | `ConnectionError`，预期原因是本次未启动真实后端服务 |
| 是否达标 | false |

## 真实链路 smoke（历史记录）

2026-06-02 在 hostdzire 真实部署环境中运行 `gs-003 / OPA228_P1.pdf`。本次使用真实 API、worker、MySQL、Redis 和 MinerU 配置，目标是确认上传、建任务、Worker、MinerU、DocumentIR、Word 渲染和下载是否存在卡点。

| 项目 | 结果 |
|---|---|
| 执行环境 | hostdzire API 容器内临时放入 Golden Sample 脚本、manifest 和 PDF |
| 回归结果目录 | `/app/tests/tmp/golden_sample_runs/20260602T071017Z` |
| Manifest 样本数 | 12（历史旧 manifest） |
| 正式匹配 PDF 数 | 1 |
| 实际执行 | 1 |
| 缺少 PDF | 11 |
| Manifest 外 PDF 数 | 0（本次远端容器 smoke 只临时放入 `OPA228_P1.pdf`） |
| 成功 | 1 |
| 失败 | 0 |
| job_id | `docjob_d4c4101592ad` |
| Word 可打开 | true |
| result_file_id | `file_35a5e9c43885` |
| 主链路结论 | 未卡在上传、建任务、Worker、MinerU、DocumentIR、Word 渲染或下载任一 stage |
| P0 判定 | 历史记录：本次远端 smoke 只执行 1 个样本；后续已扩展为 4 个 OPA228 canonical 样本 |

## 最新真实回归（4 个 runnable 样本）

2026-06-03 在 hostdzire 真实部署环境中运行 `gs-003`、`gs-004`、`gs-006`、`gs-008`。本次使用真实 API、Worker、MySQL、Redis 和 MinerU 配置，目标是确认当前 4 个 runnable 样本是否存在上传、建任务、Worker、MinerU、DocumentIR、Word 渲染和下载 stage 卡点。

| 项目 | 结果 |
|---|---|
| 回归批次 | `20260603T070724Z` |
| 远端结果目录 | `/app/tests/tmp/golden_sample_runs/20260603T070724Z` |
| 本地结果目录 | `tests/tmp/golden_sample_runs/20260603T070724Z` |
| Manifest 样本数 | 12（历史旧 manifest；当前正式 manifest 为 4） |
| 正式匹配 PDF 数 | 4 |
| 实际执行 | 4 |
| 缺少 PDF | 8 |
| Manifest 外 PDF 数 | 0 |
| 成功 | 4 |
| 失败 | 0 |
| DOCX openable | 4 true / 0 false |
| 脚本目标 | 90%（历史旧脚本；当前正式 manifest 目标为 100%） |
| 脚本 `met_target` | true（仅代表历史自动主链路达标） |
| 当前脚本 P0 发布字段 | `p0_release_ready=false`，直到 admin 人工质量签字 |
| P0 判定 | 仍 blocked：主链路通过不等于人工质量通过；canonical suite 需要 4/4 admin 人工质量通过 |

逐样本结果：

| sample_id | filename | status | job_id | DOCX openable | 人工质量 |
|---|---|---|---|---|---|
| `gs-003` | `OPA228_P1.pdf` | succeeded | `docjob_cd6c254c5e4d` | true | 未通过 P0：heading/list/formula、双栏、caption/table、figure 绑定仍有缺口 |
| `gs-004` | `OPA228_P2.pdf` | succeeded | `docjob_ca6dbb503b55` | true | 未通过 P0：TOC/revision heading、Word numbering、目录 leader/缩进/页码对齐仍有缺口 |
| `gs-006` | `OPA228_P6.pdf` | succeeded | `docjob_8f76657979b4` | true | 未通过 P0：caption-before-table、分页 continuation、表头合并语义、公式符号仍有缺口 |
| `gs-008` | `OPA228_P7.pdf` | succeeded | `docjob_d86b732f2103` | true | 未通过 P0：宽表 landscape/page fit、末行孤立分页、表头合并语义、公式符号仍有缺口 |

## 4 样本人工质量记录

2026-06-02 已对 `gs-003 / OPA228_P1.pdf` 真实链路生成的 DOCX 做人工结构质量 triage，记录见 `docs/testing/pdf-to-word-gs-003-quality-triage.md`。

2026-06-03 已对 4 个 live regression DOCX 做批量人工质量记录，记录见 `docs/testing/pdf-to-word-golden-sample-manual-quality-records-20260603.md`。

| 检查维度 | 批次结论 |
|---|---|
| Word 可打开 | 4/4 通过 |
| 可编辑性 | 部分通过：正文、表格和关键图片对象不是整页截图；但语义样式和布局质量不足 |
| Heading | 4/4 未通过：抽取文本样式均为 `Normal`，未稳定映射为 Word heading |
| Word list / numbering | 4/4 未通过或不适用；`gs-003`、`gs-004` 没有真实 Word numbering |
| 表格 | 部分通过：`gs-003`、`gs-006`、`gs-008` 的表格为可编辑 Word table；caption 顺序、表头合并、分页和宽表版面不足 |
| 图片/figure | 部分通过：`gs-003` 噪声曲线图保留为图片；caption/figure 绑定仍不稳定 |
| 双栏/宽表 | 未通过：`gs-003` 双栏退化为表格近似；`gs-008` 宽表在 A4 portrait 下压缩并分页异常 |
| 公式/特殊符号 | 未通过：`gs-003`、`gs-006`、`gs-008` 存在 LaTeX 残留 |
| 人工结论 | 4/4 条件通过（主链路）/ 0/4 通过 P0 版面与语义质量 |

## 失败分类与后续 feature 输入

本轮没有链路失败，主要质量问题归为 `pipeline-parity-gap`：

| 类别 | 结论 | 后续路由 |
|---|---|---|
| environment | hostdzire 本轮可执行；API/Worker/MinerU 可用。远端容器运行前仍需同步 Golden Sample manifest/PDF。 | 记录运行注意事项，不进入修复 feature |
| sample-sourcing | 当前正式 manifest 已收敛为 4 个 OPA228 canonical 样本；不再把 8 个占位 `missing_pdf` 作为 P0 缺口。 | 后续扩展样本另开 P1/P2 backlog |
| document-ir-layout-risk | 双栏 block 分组、宽表分页/页面方向、caption 与表格/figure 的相对位置仍有风险。 | `document-ir-layout-risk-pass` |
| word-renderer-editable-output | heading/list/formula/caption/table 样式策略没有同步到 API DocumentIR renderer。 | `word-renderer-editable-output-pass` |
| pipeline-parity-gap | 官方 `app/conversion/runtime` 已有部分 legacy 策略，但线上 API DocumentIR renderer 未接入；`md2word_main` 仅用于本地样例验证。 | 两个后续 feature 的共同前置判断 |

后续约束：

- `document-ir-layout-risk-pass` 已先接入最小 layout facts：`DocumentIRPage.metadata.orientation`、`DocumentIRBlockLayout.column_hint`、`layout_wide_table:*`、caption/footnote binding flags 和 table continuation heights。document_jobs 回归已覆盖保存的 IR metadata、generated Word `layout_quality_flags` 和 DOCX openable。
- `word-renderer-editable-output-pass` 的第一目标是把 `app/conversion/runtime` 的 heading/list/formula/caption/table 策略同步到 `app/services/renderer`，并新增或更新 `document_jobs` 回归用例；不能只验证 sandbox 输出。

## 正式验收命令

后续重新验收按 [线上优先验证流程](/Users/sc/PycharmProjects/md2word/docs/deploy/online-first-validation-workflow.md) 在 hostdzire 执行，不在本地启动前后端或 MySQL/Redis/Celery。

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py
```

正式执行后，把 `tests/tmp/golden_sample_runs/{timestamp}/report.md` 的汇总结果回填到本报告，人工打开每个成功样本 Word 后按 `tests/fixtures/golden_samples/acceptance-record-template.md` 或本报告的人工质量口径记录结论。

当前 4 个 OPA228 PDF 已进入正式 manifest 并完成真实链路执行；正式 P0 通过不再以扩充到 10-20 份样本为阻塞条件，而以 canonical suite 4/4 admin 人工质量通过为准。DocumentIR layout facts 已开始接入主链路，但不改变当前 0/4 人工 P0 质量结论。
