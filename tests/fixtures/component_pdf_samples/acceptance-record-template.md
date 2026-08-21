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
- 后端 commit / dirty 状态：
- MinerU 包 SHA-256：
- DOCX SHA-256：
- 客户端：`word` / `wps`
- 客户端版本：
- 验收人：
- 验收时间：

## 自动检查

- [ ] 回归 runner 状态为 `succeeded`
- [ ] DOCX 输出存在，并且可以用本次记录的 Word/WPS 客户端打开
- [ ] 没有非预期转换异常或缺失样例包证据
- [ ] `docx_quality_flags` 已检查；如存在 flag，已在备注说明人工放行依据
- [ ] direct/en2zh 对比时，block 顺序、block 类型、表格行列、图片引用和公式/占位符没有被破坏
- [ ] `source_revision` 与 `docx_sha256` 保持 runner 模板中的当前值

## 人工排版检查

使用 `manifest.yaml` 中对应样例的 `acceptance_focus` 条目作为检查项。

| 检查项 | Pass / Fail / N/A | 备注 |
|---|---|---|
|  |  |  |

## 视觉 QA 标准项

| 项目 | Pass / Fail / N/A | 备注 |
|---|---|---|
| 实际页数（填写正整数） |  |  |
| 无非预期空白页 |  |  |
| 关键内容组落页合理、没有内容溢出 |  |  |
| 页面尺寸、页边距、页眉页脚距离符合 datasheet YAML |  |  |
| 标题、正文、表格、caption 同类元素样式一致 |  |  |
| 双栏阅读顺序与栏平衡可接受 |  |  |
| 表格可编辑，且没有不可接受的挤压 |  |  |
| 图片、图注和正文相对位置可追溯，图片清晰度可接受 |  |  |
| 字体替换/缺失情况已检查并说明 |  |  |
| 符号、上下标、单位、型号和数值可读 |  |  |

## 结论

- 结论：`pass` / `conditional` / `fail` / `blocked`
- 后续 issue 或任务：
- P1/P2 backlog：
- 备注：

正式机器可读签字以 runner 生成的 `manual-signoff-template.yaml` 为准。`conditional`、`fail` 或任一检查项为 `fail` / `n/a` 时必须填写备注；LibreOffice 单独验收不能应用为有效签字。
