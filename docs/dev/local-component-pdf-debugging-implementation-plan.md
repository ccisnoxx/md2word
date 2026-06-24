---
doc_type: dev-guide
slug: local-component-pdf-debugging-implementation-plan
component: conversion-runtime
status: current
summary: md2word 本地电子元器件 PDF direct/en2zh 调试第一阶段实施计划和运行闭环。
tags: [conversion, mineru, regression, pycharm, translation]
last_reviewed: 2026-06-23
---

# 本地电子元器件 PDF 调试实施计划

## 当前阶段目标

第一阶段只建立可重复使用的本地调试入口和文档闭环，不修改渲染、布局或翻译核心逻辑。

正式项目 `/Users/sc/PycharmProjects/md2word` 是唯一运行入口。新的本地 MinerU 结果包先放在仓库根目录的 `mineru_result/`，再通过 PyCharm Run Configuration 或 JSON 配置运行 `scripts/dev/run_local_mineru_debug_config.py`。

`mineru_result/`、`tests/tmp/`、`.env` 和真实翻译 trace/response 都是本地证据或密钥相关数据，不提交。

## 本地调试工作流

1. 获取 MinerU 结果包。
   - 新 PDF 先通过线上/准线上 MinerU 流程或外部 MinerU 工具解析。
   - 将输出目录或 zip 放到 `mineru_result/<pdf-name>-<run-id>/`。
   - 目录内至少需要 `*_content_list_v2.json` 或 `*_content_list.json`。
2. 跑 direct。
   - PyCharm 选择 `Local MinerU Direct`。
   - 或运行 `.venv/bin/python scripts/dev/run_local_mineru_debug_config.py --config scripts/dev/local_mineru_debug_direct_config.json`。
   - 输出写到 `tests/tmp/local_mineru_debug/direct/`。
3. 跑 en2zh。
   - PyCharm 选择 `Local MinerU En2Zh`。
   - 或运行 `.venv/bin/python scripts/dev/run_local_mineru_debug_config.py --config scripts/dev/local_mineru_debug_en2zh_config.json`。
   - 有 `OPENAI_API_KEY` 时会调用 OpenAI-compatible 翻译接口；无 key 且未配置 `translation_response` 时应明确失败。
   - 需要离线复现时，先保留 `translation_request_output`，把人工或模型返回保存到本地未提交 JSON，再填入 `translation_response`。
4. 检查输出。
   - 自动检查只确认脚本状态、DOCX 存在和可打开。
   - 视觉检查优先使用 LibreOffice + Poppler 标准渲染链生成 `page-*.png`；macOS Quick Look / `qlmanage` 只作为标准链不可用时的临时预览，不作为最终版式结论。
   - 人工检查必须对照 PDF，看标题、目录、表格、图片、页眉页脚、单位符号和翻译文本是否可读。
5. 定位问题。
   - MinerU 包缺块或识别错：先记录为解析输入问题。
   - MinerU 包内容正确但 DOCX 排版错：定位到 `app/conversion/runtime*`。
   - en2zh 文本错误：看 request/response/trace、prompt、术语和占位符。
6. 修复与回归。
   - 转换行为修复只进入正式项目 `app/conversion`。
   - 可复现且后续需要防回归的案例，最小化后沉淀到 `tests/fixtures/component_pdf_samples/`。

## 样例治理

- 本地调试 staging：`mineru_result/`，已忽略，不提交。
- 长期回归样例：`tests/fixtures/component_pdf_samples/samples/<brand>/<category>/<sample-id>/mineru/`。
- 命名使用小写 kebab-case：`<brand-code>-<category>-<product>-p<page>-<page-type>`。
- 页面类型建议：`cover`、`toc`、`dense-table`、`wide-table`、`pinout`、`diagram`、`ordering-info`。
- Manifest 必须记录品牌、分类、产品型号、源 PDF 引用、MinerU 包路径、标签、人工验收关注点和 `regression.enabled`。
- 专有 PDF 或客户 PDF 不进入仓库；manifest 只能记录外部证据引用。

## PyCharm 运行方案

仓库提供两个可共享 Run Configuration：

- `.run/Local MinerU Direct.run.xml`
- `.run/Local MinerU En2Zh.run.xml`

两者都使用：

- Script path: `scripts/dev/run_local_mineru_debug_config.py`
- Working directory: `/Users/sc/PycharmProjects/md2word`
- Interpreter: `.venv/bin/python`

日常只改 JSON 配置里的 `input_path` 和 `output_path`，不需要在 PyCharm 中手写长命令。

## direct / en2zh 配置区别

`scripts/dev/local_mineru_debug_direct_config.json`：

- `translation_mode=direct`
- `document_language=en`
- 不生成翻译 request/trace
- 输出 `tests/tmp/local_mineru_debug/direct/*.docx`

`scripts/dev/local_mineru_debug_en2zh_config.json`：

- `translation_mode=en2zh`
- `document_language=auto`
- 生成 `translation_request_output`，有翻译成功结果时生成 `translation_trace_output`
- API key 从 `.env`、环境变量或 PyCharm 环境变量读取，不写入 JSON
- 没有 key 且没有 `translation_response` 时失败，不回退 direct

## 测试和验收矩阵

| 场景 | 自动验证 | 人工检查 | 输出位置 |
|---|---|---|---|
| direct 单样例 | 脚本退出 0，DOCX 生成 | 对照 PDF 看排版 | `tests/tmp/local_mineru_debug/direct/` |
| en2zh 缺 key | 脚本失败且提示 `OPENAI_API_KEY` | 不要求 DOCX | `tests/tmp/local_mineru_debug/en2zh/` |
| en2zh 有 key/response | 脚本退出 0，DOCX/trace 生成 | 对照 PDF 和中文术语检查 | `tests/tmp/local_mineru_debug/en2zh/` |
| DOCX 视觉验收 | `render_docx.py` 生成 `page-*.png` 和可选 PDF | 检查首页顶部、表格、图片、页脚和分页 | `tests/tmp/local_mineru_debug/visual_qa/standard_render/` |
| 长期样例回归 | `run_component_pdf_regression.py` | 填人工验收记录 | `tests/tmp/component_pdf_regression/` |

第一阶段改动验证命令：

```bash
.venv/bin/python -m unittest tests.test_conversion_sandbox_dev_tools
.venv/bin/python scripts/dev/manage_component_pdf_samples.py validate
.venv/bin/python scripts/dev/run_local_mineru_debug_config.py --config scripts/dev/local_mineru_debug_direct_config.json
```

DOCX 标准视觉验收命令和依赖清单见 [local-conversion-sandbox.md](/Users/sc/PycharmProjects/md2word/docs/dev/local-conversion-sandbox.md)。在 Codex 受限沙箱内运行 LibreOffice 可能出现 `Abort trap: 6`；通过 Codex 执行渲染时使用非沙箱权限，本机终端和 PyCharm 正常运行不需要特殊处理。

en2zh 缺 key 的预期验证：

```bash
OPENAI_API_KEY= .venv/bin/python scripts/dev/run_local_mineru_debug_config.py --config scripts/dev/local_mineru_debug_en2zh_config.json
```

## 后续扩展

1. 把当前 OPA228 P1/P2/P6/P7 样例最小化后沉淀为 cover、toc、dense-table、wide-table 回归样例。
2. 扩展 `component_pdf_samples` manifest，使同一 MinerU 包可以记录 direct/en2zh run matrix。
3. 为 en2zh 增加可提交的脱敏 response fixture 或私有证据指针，让 CI 可以离线覆盖翻译后排版。
4. 按品牌和分类逐步扩展到 ADI、onsemi、ST、NXP 等 datasheet。

## 第二阶段质量硬化

第二阶段不迁移正式链路，继续围绕本地 `app/conversion/runtime_*` 做质量硬化。目标是把第一阶段规则放到更多 datasheet/技术手册样本下验证，形成稳定的 direct/en2zh 对照报告、视觉 QA 证据和第三阶段迁移准入条件。

### 目标边界

- 做：本地 MinerU -> DOCX 矩阵运行、样本扩展、direct/en2zh 对比、DOCX 结构质量证据、标准渲染命令、人工验收模板和 P0/P1/P2 backlog。
- 不做：迁移到 `app/services/renderer/*`、生成后自动二次修正、复杂双栏平衡重写、线上 API/worker 门禁变更、提交真实 PDF/trace/key/生成 DOCX。
- 可复用：允许复用 `app.services.renderer.docx_quality` 提取 OOXML 结构证据，但不把本地渲染实现迁到正式 renderer。

### 样本矩阵

默认矩阵由 `scripts/dev/run_local_mineru_quality_matrix.py` 内置：

| 等级 | 样本 | 关注点 |
|---|---|---|
| P0 | `OPA228_P1` | 双栏首页、标题/正文/图片/Device Information 表格 |
| P0 | `OPA228_P2` | 目录、Revision History、双栏目录和列表 |
| P0 | `OPA228_P6` | 多 Thermal Information 表、脚注、θ/ψ/°C/W |
| P0 | `OPA228_P7` | Electrical Characteristics 宽表、单位、上下标和特殊符号 |
| P1 | `RS2G04` | 13 页多图、多表、页眉页脚和分页观察样本 |

新增样本先留在 `mineru_result/` 本地矩阵中观察。只有公开或可最小化、能暴露明确防回归风险、体积可控并且 metadata 完整的样本，才加入 `tests/fixtures/component_pdf_samples/`。

### direct / en2zh 验证

- direct：验证英文内容、阅读顺序、标题层级、列表、表格结构、图片位置、关键符号和 YAML 样式分组。
- en2zh：验证翻译后 block 顺序、block 类型、图片引用、表格行列、公式/占位符不变，中文默认宋体，术语/单位/型号/数值保留。
- en2zh 缺 `OPENAI_API_KEY` 且缺本地 response 时必须标记 `translation_api_key_missing`，不得回退 direct。

### 自动化与人工验收分层

- L0：runner 退出码、DOCX 存在、报告写出。
- L1：DOCX 可打开、可编辑内容、表格/图片/heading/TOC/LaTeX 残留等 `docx_quality_flags`。
- L2：按报告中的 `render_docx.py` 命令生成标准渲染 PNG/PDF。
- L3：人工对照 PDF、DOCX 和 PNG/PDF 填写 `manual-signoff.yaml`。
- L4：汇总 P0/P1/P2，P1/P2 进入 backlog，P0 必须清零。

### 验证命令

```bash
.venv/bin/python -m unittest tests.test_conversion_sandbox_dev_tools
.venv/bin/python -m unittest tests.test_component_pdf_sample_governance
.venv/bin/python -m unittest tests.test_local_mineru_quality_matrix
.venv/bin/python scripts/dev/manage_component_pdf_samples.py validate
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core
```

en2zh 离线验证示例：

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py \
  --mode en2zh \
  --sample-id OPA228_P1 \
  --translation-response-dir tests/tmp/local_mineru_debug/en2zh_responses
```

标准视觉渲染使用 `report.md` 中每个样本的 `render_docx.py` 命令。Codex 受限沙箱内 LibreOffice 可能需要非沙箱权限；本机终端和 PyCharm 正常运行。

### 第三阶段准入条件

- `OPA228_P1/P2/P6/P7` direct 全部自动通过并由人工签 `pass`，无 P0。
- en2zh 至少覆盖 P0 样本的离线 response 或受控模型批次，结构不变且无静默降级。
- `RS2G04` direct 观察报告完整，问题均已分级，不存在影响 P0 的未知共性根因。
- 每个 P0 都有 DOCX、`report.json` / `report.md`、标准渲染 PNG/PDF 和人工验收记录。
- 没有提交 `mineru_result/`、`tests/tmp/`、真实 PDF、真实 key、真实 trace。
- 第三阶段要迁移/对齐的 P1/P2 backlog 已明确列出。

## 风险和决策点

- Proprietary PDF：默认不提交源 PDF，只提交公开或最小化 MinerU 包。
- 翻译 API：真实 API 依赖网络、key、模型稳定性和费用；自动回归优先使用离线 response。
- DOCX 质量：自动测试无法证明排版质量，仍需要人工验收。
- 样例体积：优先页面级最小样例，避免完整 datasheet 进入仓库。
- 第二代码源：不恢复、不代理、不从 `md2word_main` 运行转换。
