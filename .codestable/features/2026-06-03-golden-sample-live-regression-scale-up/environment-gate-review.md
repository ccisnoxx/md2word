---
doc_type: feature-evidence
feature: 2026-06-03-golden-sample-live-regression-scale-up
slug: environment-gate-review
status: completed
created_at: 2026-06-03
tags: [golden-sample, regression, environment-gate]
---

# environment-gate-review

## 结论

`environment-gate-review` 已完成。仓库内 4 个当前可运行 Golden Sample PDF 与 manifest 映射一致，但当前本机默认运行环境不能直接进入 `live-regression-run`：`127.0.0.1:8000` 未提供 ready API，当前 shell 和 `.env` 均没有回归脚本所需的 Golden Sample 认证配置。

本记录只做环境门禁和阻塞项归类，不包含真实回归结果，也不证明 DocumentIR 或 Word renderer 质量。

## 样本清点

使用项目 conda 解释器读取 `tests/fixtures/golden_samples/manifest.yaml`，当前 4 个 `source_status=available` 样本均存在：

| sample_id | filename | source_status | file_status | size_bytes |
|---|---|---|---|---:|
| `gs-003` | `OPA228_P1.pdf` | `available` | exists | 139415 |
| `gs-004` | `OPA228_P2.pdf` | `available` | exists | 697217 |
| `gs-006` | `OPA228_P6.pdf` | `available` | exists | 110944 |
| `gs-008` | `OPA228_P7.pdf` | `available` | exists | 112109 |

补充观察：

- `missing_targets=[]`
- `pdf_count=4`
- `python -m unittest tests.test_golden_sample_manifest` 在 `/Users/sc/miniconda3/envs/md2word/bin/python` 下通过，结果为 `Ran 6 tests ... OK`。
- 当前默认 `python` 缺少 `PyYAML`，后续回归和清单校验应继续使用项目 conda 解释器，或先显式准备同等依赖环境。

## 服务与运行环境

本机默认端口状态：

| 检查项 | 结果 |
|---|---|
| `lsof -nP -iTCP:8000 -sTCP:LISTEN` | 无监听输出 |
| `lsof -nP -iTCP:3000 -sTCP:LISTEN` | 无监听输出 |
| `lsof -nP -iTCP:4173 -sTCP:LISTEN` | 无监听输出 |
| `curl http://127.0.0.1:8000/api/v1/health/ready` | `ready_http_status=000`，curl error present，body empty |
| `docker compose ps` | 当前仓库根目录没有默认 compose 配置，返回 `no configuration file provided: not found` |

这些结果说明本机当前没有可直接用于真实回归的默认 API 服务。它不判断远端 hostdzire 是否可用。

## 认证与敏感配置

仅检查 key 是否存在，未打印任何敏感值。

| key | process env | `.env` target key |
|---|---|---|
| `GOLDEN_SAMPLE_BASE_URL` | unset | absent |
| `GOLDEN_SAMPLE_USERNAME` | unset | absent |
| `GOLDEN_SAMPLE_PASSWORD` | unset | absent |
| `GOLDEN_SAMPLE_BEARER_TOKEN` | unset | absent |
| `MINERU_API_TOKEN` | unset | absent |
| `AUTH_JWT_SECRET_KEY` | unset | absent |
| `AUTH_INTERNAL_USERS_FILE` | unset | absent |
| `AUTH_INTERNAL_USERS_JSON` | unset | absent |

`.env` 文件存在，但没有上述目标 key。

## 回归脚本入口确认

`scripts/ops/run_golden_sample_regression.py` 当前默认：

- `GOLDEN_SAMPLE_BASE_URL` 未设置时使用 `http://127.0.0.1:8000`
- `GOLDEN_SAMPLE_USERNAME` 未设置时使用 `operator`
- 必须设置 `GOLDEN_SAMPLE_PASSWORD` 或 `GOLDEN_SAMPLE_BEARER_TOKEN`
- 默认 manifest 为 `tests/fixtures/golden_samples/manifest.yaml`
- 默认输出目录为 `tests/tmp/golden_sample_runs/`
- 会对 manifest 中 enabled 且 PDF 存在的样本建真实 document job，并下载成功样本 DOCX

因此当前阻塞点是运行环境和认证配置，不是 manifest 或 PDF 文件缺失。

## 下一步进入条件

进入 `live-regression-run` 前至少需要满足：

1. 提供可访问的真实 API base URL，或启动本机 API/Worker/MinerU 运行环境，使 `/api/v1/health/ready` 可访问。
2. 提供 `GOLDEN_SAMPLE_PASSWORD` 或 `GOLDEN_SAMPLE_BEARER_TOKEN`，并避免在命令输出和文档中泄露值。
3. 如果使用远端 hostdzire 环境，先确认脚本、manifest 和 4 个 PDF 的运行位置；不能假设容器内已经有 `tests/fixtures/golden_samples/`。
4. ready 状态应能说明 Worker、文件存储、任务调度和 MinerU 配置处于可执行状态。

逐样本 gate 状态：

| sample_id | 文件状态 | 环境状态 | 下一步 |
|---|---|---|---|
| `gs-003` | ready | blocked by runtime/auth | 等真实 API 与认证配置就绪后执行 |
| `gs-004` | ready | blocked by runtime/auth | 等真实 API 与认证配置就绪后执行 |
| `gs-006` | ready | blocked by runtime/auth | 等真实 API 与认证配置就绪后执行 |
| `gs-008` | ready | blocked by runtime/auth | 等真实 API 与认证配置就绪后执行 |

