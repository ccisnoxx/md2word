---
doc_type: test-template
slug: golden-sample-acceptance-record-template
component: pdf-to-word-backend
status: current
summary: P0 Golden Sample 人工验收记录模板。
tags: [testing, golden-sample, pdf, word]
last_reviewed: 2026-05-29
---

# Golden Sample 人工验收记录模板

## 回归批次

| 字段 | 值 |
|---|---|
| 执行时间 |  |
| 后端版本/commit |  |
| API 地址 |  |
| Worker 模式 |  |
| MinerU 配置 |  |
| 模板版本 |  |
| P0 canonical suite | `gs-003`, `gs-004`, `gs-006`, `gs-008` |
| 样本总数 | 4 |
| 样本来源确认人 | Admin |
| 成功数 |  |
| 失败数 |  |
| 核心链路成功率 |  |
| 是否达到 P0 目标 |  |
| Admin reviewer |  |
| Admin sign-off |  |

## 样本记录

| 样本 ID | 文件名 | 标签 | job_id | 状态 | 失败阶段/错误码 | Word 可打开 | 可编辑 | 结构顺序 | 参数表 | 关键图片 | 人工结论 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gs-003 |  |  |  |  |  |  |  |  |  |  |  |  |
| gs-004 |  |  |  |  |  |  |  |  |  |  |  |  |
| gs-006 |  |  |  |  |  |  |  |  |  |  |  |  |
| gs-008 |  |  |  |  |  |  |  |  |  |  |  |  |

## 机器可读 Admin sign-off

每次运行 `scripts/ops/run_golden_sample_regression.py` 后，脚本会在 run_dir 生成：

- `report.json`
- `report.md`
- `manual-signoff-template.yaml`

Admin reviewer 打开 4 个生成的 DOCX 后，将 `manual-signoff-template.yaml` 复制为同目录下的 `manual-signoff.yaml`，并填写：

```yaml
schema_version: 1
reviewer_role: admin
reviewer: admin@example.com
signed_at: 2026-06-16T12:00:00Z
final_signoff: true
samples:
  - sample_id: gs-003
    filename: OPA228_P1.pdf
    job_id: docjob_xxx
    docx_sha256: sha256:...
    verdict: pass
    notes: ""
```

要求：

- `reviewer_role` 必须是 `admin`。
- `final_signoff` 必须是 `true`。
- Golden Sample 样本来源确认、reviewer 和最终签字人都必须是 admin。
- 4 个 P0 canonical sample 的 `verdict` 必须全部是 `pass`；`条件通过` 不能作为 P0 最终签字。
- `job_id`、`filename`、`docx_sha256` 必须保持模板中的当前回归结果，不要手工改成其他批次。
- `report.md` 中的可编辑内容证据应为 4/4，疑似整页截图样本数应为 0，DOCX quality flags 应为 `none` 或由 admin 明确判定为非阻断；如果某个样本存在 DOCX quality flags 且仍签 `pass`，该样本 `notes` 必须说明人工放行依据。

签字后对同一个 run_dir 应用签字，不重新跑样本：

```bash
.venv/bin/python scripts/ops/run_golden_sample_regression.py \
  --apply-manual-signoff tests/tmp/golden_sample_runs/<run_id>
```

只有自动链路达标且机器可读 admin sign-off 校验通过时，`report.json` / `report.md` 中的 `p0_release_ready` 才能变成 `true`。

## 判定规则

- `通过`：API 上传、创建任务、Worker 处理、下载授权和 Word 打开检查均通过，且 admin 人工检查确认接近原版排版并符合 Word 文档排版标准；当两者冲突时，Word 标准结构优先。
- `条件通过`：核心链路成功，存在轻微排版问题，不影响 Word 打开、编辑和核心内容追溯；P0 canonical suite 的最终通过不能停留在条件通过。
- `失败`：任务失败、生成文件损坏、主要正文为空、关键参数表不可读，或关键图片大面积缺失。
