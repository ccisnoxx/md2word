# Golden Sample 回归样本

本目录用于 P0 PDF 到 Word 主链路验收。`manifest.yaml` 是版本化样本清单，`pdfs/` 放真实 PDF，`runs/` 放回归脚本输出。

当前仓库已将 4 个 OPA228 单页 PDF 映射到 `manifest.yaml`，作为正式可运行样本：

- `gs-003` / `OPA228_P1.pdf`：英文双栏 datasheet 首页，用于验证双栏阅读顺序、标题层级、图表和 Device Information 表格。
- `gs-004` / `OPA228_P2.pdf`：目录和 Revision History，用于验证双栏目录、页码和项目符号列表。
- `gs-006` / `OPA228_P6.pdf`：Thermal Information 表，用于验证多表格、热学符号和脚注。
- `gs-008` / `OPA228_P7.pdf`：Electrical Characteristics 宽表，用于验证宽表、分组、单位和上下标/特殊符号。

当前只有 `gs-003 / OPA228_P1.pdf` 已跑过真实 hostdzire 主链路 smoke；新映射的 `gs-004`、`gs-006` 和 `gs-008` 仍需正式回归和人工验收。

把业务确认后的 10-20 份样本按 `manifest.yaml` 的 `filename` 放入 `pdfs/` 后，运行：

```bash
GOLDEN_SAMPLE_USERNAME=operator \
GOLDEN_SAMPLE_PASSWORD='<operator-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py
```

验收口径：

- 只统计实际存在且未禁用的样本 PDF。
- manifest 外 PDF 只报告，不计入正式通过率；要使用它必须先映射或新增到 `manifest.yaml`。当前目录中没有 manifest 外 PDF。
- 核心链路成功率目标为 `>= 90%`。
- 成功样本必须生成可打开的 `.docx`，人工再按 `acceptance-record-template.md` 补结构、表格、图片和可编辑性记录。
- 缺少 PDF、后端未启动、账号未配置、MinerU 未配置都不能记为通过。
