---
doc_type: issue-fix
issue: 2026-05-17-formula-subscript-restore
path: fast-track
fix_date: 2026-05-17
tags: [formula, tex, subscript, docx]
---

# 公式上下标恢复修复记录

## 1. 问题描述

MinerU 输出里带空格的 TeX 片段在生成 DOCX 时没有正确还原为上下标，例如 `T_A`、`V_S`、`R_L` 被输出成普通文本，`\pm`、`\circ`、`\Omega` 等控制词也没有被正确还原。

## 2. 根因

- 公式归一化阶段先粗暴去掉了控制词前的反斜杠，导致 `\pm`、`\circ`、`\vee` 等信息在进入 HTML/run 渲染前就丢了。
- `\mathsf { ... }` 这种带空格的 wrapper 不匹配现有正则，`T _ { A }` 这类表达式也没有先压紧成 `T_{A}`，所以下标转换规则触发不了。

## 3. 修复方案

- 调整公式归一化顺序，先规范化带空格的 TeX wrapper 和控制词，再做下标/上标 HTML 转换。
- 新增对拆散字母/数字 token 的压紧规则，把 `C M`、`O U T`、`2 5` 等还原成可解析形态。
- 补充 `\pm`、`\circ`、`\vee`、`\Omega` 等符号恢复，并在最终文本阶段清理 `°C`、`kΩ`、逗号前空格等格式残差。
- 输入适配层对 `equation_inline` 先做公式归一化，并在与相邻文本节点拼接时保留必要空格，避免导出后出现 `kΩconnected` 这类粘连。

## 4. 改动文件清单

- `text_rendering.py`
- `input_adapter_runtime.py`
- `tests/test_text_render_characterization.py`
- `tests/test_input_adapter_characterization.py`

## 5. 验证结果

- `PYTHONPATH=tests /Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover -s tests` 通过，72 tests。
- 用示例串直接调用 `normalize_formula_text()`，得到：
  `T<sub>A</sub> = +25°C, V<sub>S</sub> = ±5 V to ±15 V, V<sub>CM</sub> = V<sub>OUT</sub> = V<sub>S</sub> / 2`
- 重新导出 `out_file/CWQ2P690T-formula-check.docx` 成功，主转换流程未报错。
- 用英文样本 `OPA228_test1.pdf-9848217b-8440-4b1c-b4ec-80ac91eebbeb` 重新导出 `out_file/OPA228_test1-check.docx`，XML 文本核对结果已恢复为：
  `... RL= 10 kΩ connected to VS/ 2 (unless otherwise noted)`

## 6. 遗留事项

当前规则已覆盖这次暴露的“带空格 TeX + 常见电子符号”路径；如果后续遇到更复杂的矩阵、分式或多层嵌套公式，可能还需要再扩展语法归一化。
