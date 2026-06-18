# Admin Golden Sample 人工签字清单

- 线上回归目录: `/root/md2word/tests/tmp/golden_sample_runs/20260617T053003Z`
- 本地 evidence 目录: `.trellis/tasks/06-16-p0-word-delivery-quality-beta/artifacts/hostdzire-golden-sample-20260617T053003Z`
- 自动回归结论: `4/4 succeeded`, `pass_rate=100%`, `automated_chain_met_target=true`
- 当前发布状态: `p0_release_ready=false`
- 当前阻断: `admin_manual_word_quality_signoff_required`

## 需要人工打开检查的 DOCX

| 样本 | PDF | DOCX | 自动质量标记 |
|---|---|---|---|
| `gs-003` | `OPA228_P1.pdf` | `gs-003-docjob_b13468b519c3.docx` | none |
| `gs-004` | `OPA228_P2.pdf` | `gs-004-docjob_3e7ba8b8960e.docx` | none |
| `gs-006` | `OPA228_P6.pdf` | `gs-006-docjob_cc4e04338e30.docx` | `docx_unstyled_heading_candidates:3` |
| `gs-008` | `OPA228_P7.pdf` | `gs-008-docjob_e3c2f334f9a5.docx` | none |

## 人工验收关注点

- `gs-003`: 双栏阅读顺序、标题层级、项目符号、图表/表格相对位置。
- `gs-004`: 目录条目和页码顺序、Revision History 列表、页眉页脚和正文边界。
- `gs-006`: Thermal Information 表格行列、θ/ψ/°C/W 等符号、脚注位置；如果判定通过，必须在 notes 里说明自动标记可接受。
- `gs-008`: Electrical Characteristics 宽表列名/单位/分组、特殊符号、可编辑性和不大面积错列。

## 签字操作

1. 复制 `manual-signoff-template.yaml` 为 `manual-signoff.yaml`。
2. 填写 `reviewer`、`signed_at`，设置 `reviewer_role: admin` 和 `final_signoff: true`。
3. 每个样本填 `verdict: pass` 或 `fail`，不要修改 `job_id` 和 `docx_sha256`。
4. `gs-006` 如果 `verdict: pass`，`notes` 必须解释为什么 `docx_unstyled_heading_candidates:3` 不阻断 Beta。
5. 将 `manual-signoff.yaml` 放到 hostdzire 的 `/root/md2word/tests/tmp/golden_sample_runs/20260617T053003Z/manual-signoff.yaml`。
6. 在 hostdzire 的 `/root/md2word` 执行：

```bash
docker run --rm --user root --network host -v /root/md2word:/work -w /work md2word-p0:latest \
  python scripts/ops/run_golden_sample_regression.py \
  --apply-manual-signoff tests/tmp/golden_sample_runs/20260617T053003Z
```

7. 验证 `tests/tmp/golden_sample_runs/20260617T053003Z/report.json` 中：
   - `summary.manual_quality.valid == true`
   - `summary.p0_release_ready == true`
   - `summary.p0_release_blocker == null`
