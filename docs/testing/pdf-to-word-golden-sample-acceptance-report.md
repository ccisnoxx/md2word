---
doc_type: test-report
slug: pdf-to-word-golden-sample-acceptance-report
component: pdf-to-word-backend
status: current
summary: P0 Golden Sample 验收状态；2026-06-29 hostdzire release 20d496e 的 4 个 canonical samples 自动回归和 admin 签字通过。
tags: [testing, golden-sample, pdf, word, p0]
last_reviewed: 2026-06-29
---

# P0 Golden Sample 验收报告

## 当前结论

2026-06-29 正式结论：hostdzire release `20d496e` 已完成 P0 Golden Sample 正式回归和 admin manual signoff，`report.json` / `report.md` 显示 `p0_release_ready=true`。

本次发布证据来自 hostdzire 真实 API、Worker、MySQL、Redis/Celery 和 MinerU 链路；4 个 canonical OPA228 样本自动链路全部成功，admin 对同一 run_dir 完成签字。2026-06-17 的 hostdzire admin signoff 仍只保留为历史基线。

当前状态：`p0_release_ready=true` for release `20d496e`。

| 项目 | 结果 |
|---|---|
| release dir | `/root/md2word-releases/20d496e` |
| commit | `20d496ed1df0c1d3eee94c0e6dfac0c0e6653ed3` |
| deployment id | `hostdzire-20260629T070215Z-20d496e` |
| run dir | `/root/md2word-releases/20d496e/tests/tmp/golden_sample_runs/20260629T070506Z` |
| release check + preflight | 通过；173 tests OK；4 个 canonical PDF 齐全；无 readiness / P0 blocker |
| 自动回归 | 4/4 succeeded；4/4 DOCX openable；pass rate 100% |
| manual signoff | `reviewer_role=admin`，`final_signoff=true`，4 个样本 `verdict=pass` |
| `gs-004` quality flags | `docx_manual_list_markers:10`、`docx_unstyled_heading_candidates:17`；admin notes 已说明为非阻断 |
| 最终发布字段 | `p0_release_ready=true`，`p0_release_blocker=none` |

## 2026-06-24 收口背景

第三阶段 `document-ir-renderer-parity` 已完成本地实现收口和正式链路 targeted 验证，`pipeline-parity-gap` 的修复入口已从本地 sandbox 收敛到 `document_jobs -> DocumentIR -> app/services/renderer/*` 链路。

## 第三阶段完成证据

| 证据项 | 当前结论 |
|---|---|
| 共享规则源 | `app/conversion/docx_rules/` 承载 MinerU content、text/formula/list/heading/TOC semantics 和 terminology replacement；local runtime 与 formal renderer 使用同一套规则。 |
| 正式链路 wiring | `DocumentJobExecutionService` 调用 `DocumentIRWordRenderer.render_to_bytes()` 时传入 `DocumentIRRenderOptions`，包含 active subscript config path 和 document language。 |
| DocumentIR converter | 覆盖 legacy flat content list、nested MinerU v2 page list、rich content fields、caption/footnote merge、image asset path、table continuation 和 page orientation。 |
| Formal renderer | 覆盖 Word heading、real numbering、TOC tab leaders、formula/symbol normalization、caption/notes、editable table、long table、wide table landscape、two-column regions 和 image/table binding。 |
| Metadata evidence | document_jobs 回归覆盖 generated Word metadata 中的 `renderer_mode`、`layout_quality_flags`、`docx_quality` 和 `quality_flags`。 |
| 非目标项 | 未改变 public HTTP API、数据库 schema、持久化 adapter、job workflow state、Golden Sample manifest 或 PDF 样本范围。 |

本地验证命令和结果：

| 命令 | 结果 |
|---|---|
| `.venv/bin/python -m unittest tests.test_document_ir_mineru_converter_layout` | 4 tests OK |
| `.venv/bin/python -m unittest tests.test_document_ir_word_renderer_layout` | 25 tests OK |
| `.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_saves_mineru_raw_ir_and_image_assets tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_generated_word_keeps_renderer_ooxml_semantics tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_passes_subscript_config_to_document_ir_renderer` | 3 tests OK |
| `.venv/bin/python -m unittest tests.test_golden_sample_manifest tests.test_openapi_export.OpenAPIExportTests.test_golden_sample_preflight_release_check_requires_admin_and_p0_runtime` | 20 tests OK |
| `git diff --check` | OK |
| `.venv/bin/python scripts/ops/check_release.py` | `Release check report ok: True`，OpenAPI snapshot current，targeted unittest 168 tests OK |

测试输出中只出现 FastAPI/Starlette deprecation warnings，不影响本轮 P0 renderer/document_jobs 验收判断。

## 正式链路验收流程

正式 P0 验收只统计 `tests/fixtures/golden_samples/manifest.yaml` 中 4 个 canonical samples：`gs-003`、`gs-004`、`gs-006`、`gs-008`。不扩大样本范围，不新增 PDF。

hostdzire 上先执行 runtime + Golden Sample preflight：

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/check_release.py \
  --runtime-url "http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
  --golden-sample-preflight \
  --golden-sample-preflight-output tests/tmp/golden_sample_runs/preflight.json
```

预检必须同时满足：

- `deployment_init_ready=true`
- `p0_document_jobs_ready=true`
- `effective_repository_backend=mysql`
- `document_jobs_worker_backend=celery`
- admin auth role 符合 `GOLDEN_SAMPLE_REQUIRED_ROLE=admin`
- 4 个 canonical PDF 全部存在
- 无未解释的 `readiness_blockers` 或 `p0_document_jobs_blockers`

预检通过后执行真实 4 样本回归：

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/run_golden_sample_regression.py
```

自动链路通过条件：

- 4/4 job `succeeded`
- 4/4 DOCX openable
- 4/4 editable content evidence 可用
- `docx_quality_flags` 为 `none`，或 admin 在签字 notes 中逐项说明非阻断依据
- `report.json` / `report.md` 已落在本次 run_dir，且不覆盖失败证据

## 标准渲染与签字

Admin reviewer 需要打开本次 run_dir 下 4 个 DOCX，并按报告中的标准渲染命令生成 PNG/PDF 视觉证据。截图不提交仓库，但需要随 run_dir 保存并用于人工复核：

| 样本 | 必查截图/区域 |
|---|---|
| `gs-003` | 首页双栏正文、Features/Applications/Description 阅读顺序、关键 figure、Device Information 表格。 |
| `gs-004` | Table of Contents 点线/页码、Revision History、列表、页眉页脚边界。 |
| `gs-006` | Thermal Information 多表、θ/ψ/°C/W、表格脚注和正文顺序。 |
| `gs-008` | Electrical Characteristics 宽表全貌、landscape/page fit、VOS/PSRR/CMRR/nV/√Hz/µV/°C 等符号。 |

签字流程固定为：

```bash
.venv/bin/python scripts/ops/run_golden_sample_regression.py \
  --apply-manual-signoff tests/tmp/golden_sample_runs/<run_id>
```

只有 `manual-signoff.yaml` 校验通过、4 个样本 `verdict: pass`、`final_signoff: true` 且 reviewer role 为 `admin` 时，本次 `report.json` / `report.md` 才能作为发布证据并显示 `p0_release_ready=true`。

## 剩余 P1/P2 Backlog

| 等级 | 记录口径 | 当前处理 |
|---|---|---|
| P1 | 非 canonical datasheet 或 RS2G04 等观察样本出现明显版式偏差，但不破坏 4 个 OPA228 P0；P1 translation formal gate 需要补齐 3 个真实英文 datasheet 并设置 `P1_TRANSLATION_FORMAL=1`。 | 记录到 component PDF 或 P1 translation backlog；不并入 P0 Golden Sample 阻塞条件。 |
| P2 | 小范围 spacing、颜色、字号、caption 美观、复杂双栏平衡、报告 metadata、Acceptance Center 自动导入或线上证据展示增强。 | 记录为治理/运维/体验改进；不影响 `p0_release_ready`，除非 admin 判定影响核心内容可读或 Word 标准结构。 |

Backlog 条目必须包含 sample/run_id、job_id、截图路径、`docx_quality_flags`、人工结论和建议优先级；不得提交真实 key、真实 trace、生成 DOCX、PNG/PDF 或客户资料。

## 历史记录

以下内容保留为历史排障和质量演进记录，不代表本轮 2026-06-24 变更后的发布状态。

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
.venv/bin/python scripts/ops/run_golden_sample_regression.py
```

正式执行后，把 `tests/tmp/golden_sample_runs/{timestamp}/report.md` 的汇总结果回填到本报告，人工打开每个成功样本 Word 后按 `tests/fixtures/golden_samples/acceptance-record-template.md` 或本报告的人工质量口径记录结论。

当前 4 个 OPA228 PDF 已进入正式 manifest 并完成真实链路执行；正式 P0 通过不再以扩充到 10-20 份样本为阻塞条件，而以 canonical suite 4/4 admin 人工质量通过为准。DocumentIR layout facts 已开始接入主链路，但不改变当前 0/4 人工 P0 质量结论。
