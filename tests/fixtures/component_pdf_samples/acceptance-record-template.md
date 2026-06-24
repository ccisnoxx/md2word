# 电子元器件 PDF 人工验收记录

## 运行元数据

- 样例 ID：
- 矩阵模式：`direct` / `en2zh`
- 问题等级：`P0` / `P1` / `P2` / `none`
- 品牌：
- 分类：
- 产品型号：
- 源 PDF 引用：
- MinerU 结果包引用：
- 回归报告：
- DOCX 输出：
- 标准渲染 PNG/PDF：
- 验收人：
- 验收时间：

## 自动检查

- [ ] 回归 runner 状态为 `succeeded`
- [ ] DOCX 输出存在，并且可以用 Word 兼容工具打开
- [ ] 没有非预期转换异常或缺失样例包证据
- [ ] `docx_quality_flags` 已检查；如存在 flag，已在备注说明人工放行依据
- [ ] direct/en2zh 对比时，block 顺序、block 类型、表格行列、图片引用和公式/占位符没有被破坏

## 人工排版检查

使用 `manifest.yaml` 中对应样例的 `acceptance_focus` 条目作为检查项。

| 检查项 | Pass / Fail / N/A | 备注 |
|---|---|---|
|  |  |  |

## 视觉 QA 标准项

| 项目 | Pass / Fail / N/A | 备注 |
|---|---|---|
| 页面尺寸、页边距、页眉页脚距离符合 datasheet YAML |  |  |
| 标题、正文、表格、caption 同类元素样式一致 |  |  |
| 双栏阅读顺序正确，一页内闭合，不压页尾 |  |  |
| 表格可编辑，行列、表头、单位和脚注可追溯 |  |  |
| 图片、图注和正文相对位置可追溯 |  |  |
| direct 英文默认字体、en2zh 中文默认宋体符合预期 |  |  |
| 符号、上下标、单位、型号和数值可读 |  |  |

## 结论

- 结论：`pass` / `conditional` / `fail` / `blocked`
- 后续 issue 或任务：
- P1/P2 backlog：
- 备注：
