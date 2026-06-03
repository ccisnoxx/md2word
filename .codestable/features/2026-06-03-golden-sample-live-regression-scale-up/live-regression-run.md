---
doc_type: feature-evidence
feature: 2026-06-03-golden-sample-live-regression-scale-up
slug: live-regression-run
status: completed
created_at: 2026-06-03
tags: [golden-sample, regression, hostdzire, pdf-to-word]
---

# live-regression-run

## 结论

`live-regression-run` 已在 hostdzire 的真实部署环境完成。当前 4 个 runnable Golden Sample PDF 均完成真实 API/Worker/MinerU 主链路，生成的 DOCX 均可打开。

本步骤只证明主链路和 DOCX 包可打开，不证明 P0 版面、语义、可编辑质量已经通过；人工质量记录仍需在 `manual-quality-records` 步骤完成。

## 运行环境

| 项目 | 结果 |
|---|---|
| 前置机 | dmit 可 SSH，nginx active，`wg0` 存在 |
| 部署机 | hostdzire 可 SSH，nginx active，`wg0` 存在 |
| API 容器 | `md2word-p0-api-1` healthy |
| Worker 容器 | `md2word-p0-worker-1` running |
| MySQL/Redis | `md2word-p0-mysql-1`、`md2word-p0-redis-1` healthy |
| 宿主机 API 绑定 | `127.0.0.1:18000->8000/tcp` |
| 容器内 API base URL | `http://127.0.0.1:8000` |
| API ready | `status=ok` |
| 认证方式 | 容器内 auth service 生成 operator JWT access token，仅作为同一远端 shell 的环境变量传入脚本；未写入文档或报告 |

运行前已把本地 `tests/fixtures/golden_samples/manifest.yaml` 和 4 个 PDF 同步到容器默认路径 `/app/tests/fixtures/golden_samples/`。远端容器原本没有该目录。

脚本版本核对：

| 文件 | sha256 |
|---|---|
| 本地 `scripts/ops/run_golden_sample_regression.py` | `c5adb46a919ae9011f4dd2f8b69f39d8459c3563805d306faec7a1613b22ec3b` |
| 远端容器 `/app/scripts/ops/run_golden_sample_regression.py` | `c5adb46a919ae9011f4dd2f8b69f39d8459c3563805d306faec7a1613b22ec3b` |

## 运行结果

| 项目 | 结果 |
|---|---|
| 远端 run_dir | `/app/tests/tmp/golden_sample_runs/20260603T070724Z` |
| 本地 run_dir | `tests/tmp/golden_sample_runs/20260603T070724Z` |
| Manifest 样本数 | 12 |
| 正式匹配 PDF 数 | 4 |
| 实际执行 runnable 样本 | 4 |
| 缺少 PDF 样本 | 8 |
| Manifest 外 PDF | 0 |
| 成功 | 4 |
| 失败 | 0 |
| runnable 成功率 | 100.00% |
| 脚本目标 | 90% |
| 脚本 `met_target` | true |

逐样本结果：

| sample_id | filename | status | job_id | docx_openable | elapsed_seconds | local DOCX |
|---|---|---|---|---|---:|---|
| `gs-003` | `OPA228_P1.pdf` | succeeded | `docjob_cd6c254c5e4d` | true | 20.538 | `tests/tmp/golden_sample_runs/20260603T070724Z/gs-003-docjob_cd6c254c5e4d.docx` |
| `gs-004` | `OPA228_P2.pdf` | succeeded | `docjob_ca6dbb503b55` | true | 30.42 | `tests/tmp/golden_sample_runs/20260603T070724Z/gs-004-docjob_ca6dbb503b55.docx` |
| `gs-006` | `OPA228_P6.pdf` | succeeded | `docjob_8f76657979b4` | true | 30.48 | `tests/tmp/golden_sample_runs/20260603T070724Z/gs-006-docjob_8f76657979b4.docx` |
| `gs-008` | `OPA228_P7.pdf` | succeeded | `docjob_d86b732f2103` | true | 21.521 | `tests/tmp/golden_sample_runs/20260603T070724Z/gs-008-docjob_d86b732f2103.docx` |

8 个 manifest 样本仍为 `missing_pdf`，不属于本轮 4 个 runnable 样本的主链路失败：

- `gs-001`
- `gs-002`
- `gs-005`
- `gs-007`
- `gs-009`
- `gs-010`
- `gs-011`
- `gs-012`

## 本地证据

`tests/tmp/golden_sample_runs/20260603T070724Z/` 已拉回本地，包含：

- `report.json`
- `report.md`
- `gs-003-docjob_cd6c254c5e4d.docx`
- `gs-004-docjob_ca6dbb503b55.docx`
- `gs-006-docjob_8f76657979b4.docx`
- `gs-008-docjob_d86b732f2103.docx`

本地二次校验：

| 文件 | openable | size_bytes |
|---|---|---:|
| `gs-003-docjob_cd6c254c5e4d.docx` | true | 123407 |
| `gs-004-docjob_ca6dbb503b55.docx` | true | 54143 |
| `gs-006-docjob_8f76657979b4.docx` | true | 54061 |
| `gs-008-docjob_d86b732f2103.docx` | true | 54469 |

`report.json` 和 `report.md` 脱敏扫描结果为 clean：未发现 OpenSSH 私钥、JWT-like token、认证头明文、未脱敏 password 字段或未脱敏 token 字段。

## 下一步

- 进入 `manual-quality-records`：打开 4 个 DOCX，逐样本记录可编辑性、标题/列表、表格、图片/figure、双栏或宽表顺序。
- `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` 仍需在 `docs-and-roadmap-backfill` 步骤回填，避免当前项目报告继续停留在 1/1 smoke。
- 不能把本次 4/4 主链路成功声明为正式 P0 完成；正式目标仍要求 10-20 个样本规模和人工质量验收通过。
