# Golden Sample 回归样本

本目录用于 P0 PDF 到 Word 主链路验收。`manifest.yaml` 是版本化样本清单，`pdfs/` 放真实 PDF，`runs/` 放回归脚本输出。

当前仓库不包含真实业务 PDF。把业务确认后的 10-20 份样本按 `manifest.yaml` 的 `filename` 放入 `pdfs/` 后，运行：

```bash
GOLDEN_SAMPLE_USERNAME=operator \
GOLDEN_SAMPLE_PASSWORD='<operator-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py
```

验收口径：

- 只统计实际存在且未禁用的样本 PDF。
- 核心链路成功率目标为 `>= 90%`。
- 成功样本必须生成可打开的 `.docx`，人工再按 `acceptance-record-template.md` 补结构、表格、图片和可编辑性记录。
- 缺少 PDF、后端未启动、账号未配置、MinerU 未配置都不能记为通过。
