# Golden Sample 回归样本

本目录用于 P0 PDF 到 Word 主链路验收。`manifest.yaml` 是版本化样本清单，`pdfs/` 放真实 PDF，`runs/` 放回归脚本输出。

当前仓库已将 4 个 OPA228 单页 PDF 映射到 `manifest.yaml`，作为正式可运行样本：

- `gs-003` / `OPA228_P1.pdf`：英文双栏 datasheet 首页，用于验证双栏阅读顺序、标题层级、图表和 Device Information 表格。
- `gs-004` / `OPA228_P2.pdf`：目录和 Revision History，用于验证双栏目录、页码和项目符号列表。
- `gs-006` / `OPA228_P6.pdf`：Thermal Information 表，用于验证多表格、热学符号和脚注。
- `gs-008` / `OPA228_P7.pdf`：Electrical Characteristics 宽表，用于验证宽表、分组、单位和上下标/特殊符号。

这 4 个 OPA228 PDF 是当前 P0 canonical suite，覆盖本阶段需要优先解决的 datasheet 版式、表格、符号和列表场景。P0 不再以 10-20 份样本数量作为阻塞门槛；后续扩展样本应另开 P1/P2 backlog，不混入当前阻塞验收。样本来源确认、reviewer 指派和最终签字都由 admin 负责。

运行当前 canonical suite 前先做预检：

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py \
  --preflight \
  --preflight-output tests/tmp/golden_sample_runs/preflight.json
```

预检会检查样本文件、登录凭据、登录账号是否为 admin、API `/health/ready`、MySQL metadata、Celery worker 和 `p0_document_jobs_ready`。预检通过后运行真实回归：

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py
```

验收口径：

- P0 阻塞验收只统计 `gs-003`、`gs-004`、`gs-006`、`gs-008` 四个 canonical 样本。
- manifest 外 PDF 只报告，不计入正式通过率；要使用它必须先映射或新增到 `manifest.yaml`。当前目录中没有 manifest 外 PDF。
- canonical suite 必须 4/4 核心链路成功、4/4 生成可打开 `.docx`、4/4 由 admin 人工验收通过。
- 回归报告会从下载的 DOCX 包中提取 heading、Word numbering、TOC 点线制表位、表头重复、防跨页断行、表格单元格零段前后距、landscape section、表格形状、图片数量和 LaTeX 残留证据，并把明确机器风险汇总为 DOCX quality flags，供 admin 人工验收定位质量缺口。
- `--preflight` 失败不能记为样本失败；应先修复环境 blocker，再运行真实回归。
- 人工验收判断接近原版排版且符合 Word 文档排版标准；当像素级还原和可维护 Word 结构冲突时，以 Word 标准结构为更高优先级。heading/list/table/caption/symbol/wide-table/double-column 均不能存在 P0 阻断问题。
- 缺少 PDF、后端未启动、账号未配置、MinerU 未配置都不能记为通过。
