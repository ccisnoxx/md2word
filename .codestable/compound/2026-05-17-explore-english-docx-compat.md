---
doc_type: explore
type: question
date: 2026-05-17
slug: english-docx-compat
topic: 当前 MinerU JSON 到 DOCX 的链路是否偏中文，英文 PDF 解析后的 JSON 能否稳定生成排版可靠的 Word 文档
scope: input_adapter_runtime.py, mineru_to_docx.py, page_layout_runtime.py, text_rendering.py, render_config_runtime.py, template_configs/datasheet_template.yaml
keywords: [english, chinese, mineru, docx, toc, heading, font, layout]
status: active
confidence: high
---

## 问题与范围

问题：当前项目是不是主要适配中文版 PDF 解析后的 JSON；如果输入是英文 PDF 解析后的 MinerU JSON，是否能正常生成并保证排版。

范围：只看现有代码和默认模板，不基于额外英文样本做运行验证。

## 速答

不是“只能处理中文 JSON”，输入解析层基本是语言无关的；但整个排版与结构识别链路明显偏“中文数据手册”场景。英文 PDF 解析后的 JSON 在很多情况下可以生成 DOCX，但以当前默认配置和规则，不能承诺对通用英文 PDF 稳定“保证排版”。

更准确地说：

- MinerU JSON 进入内部块模型这一步，主要按块类型、bbox、HTML 和文本片段处理，不分中文/英文。
- 真正偏中文的是标题识别、目录识别、附录/表/图规则，以及默认样式字体和缩进。
- 对“编号规范、结构像中文数据手册”的英文文档，成功率会比较高。
- 对“非编号标题较多、目录标题不是 `Table of Contents`、附录/图表标题是 `Appendix/Figure/Table`”的英文文档，结构样式和分页更容易失真。

```mermaid
flowchart LR
    A["MinerU JSON 解析"] --> B["页面/目录/标题识别"]
    B --> C["样式映射"]
    C --> D["DOCX 输出"]

    A:::ok
    B:::risk
    C:::risk
    D:::risk

    classDef ok fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20
    classDef risk fill:#fff3e0,stroke:#ef6c00,color:#e65100
```

## 关键证据

1. 输入适配层按块类型和字段取值建模，没有语言分支。
   证据：[input_adapter_runtime.py](/Users/sc/MinerU/md2word_file/input_adapter_runtime.py:264)、[input_adapter_runtime.py](/Users/sc/MinerU/md2word_file/input_adapter_runtime.py:273)、[input_adapter_runtime.py](/Users/sc/MinerU/md2word_file/input_adapter_runtime.py:379)
   支撑：说明“能不能吃进英文 JSON”不是主要问题。

2. 目录标题仅显式支持 `目录` 和 `table of contents`。
   证据：[text_rendering.py](/Users/sc/MinerU/md2word_file/text_rendering.py:20)、[text_rendering.py](/Users/sc/MinerU/md2word_file/text_rendering.py:623)
   支撑：英文目录如果写成 `Contents` 等其他变体，TOC 识别可能失效。

3. 目录项和标题编号规则明显夹带中文语义。
   证据：[mineru_to_docx.py](/Users/sc/MinerU/md2word_file/mineru_to_docx.py:191)、[text_rendering.py](/Users/sc/MinerU/md2word_file/text_rendering.py:18)、[text_rendering.py](/Users/sc/MinerU/md2word_file/text_rendering.py:19)、[text_rendering.py](/Users/sc/MinerU/md2word_file/text_rendering.py:676)
   支撑：`附录/表/图/第X章` 有规则，`Appendix/Figure/Table/Chapter` 没有等价规则。

4. 非编号标题识别并不面向通用英文标题。
   证据：[text_rendering.py](/Users/sc/MinerU/md2word_file/text_rendering.py:668)、[text_rendering.py](/Users/sc/MinerU/md2word_file/text_rendering.py:681)
   支撑：像 `Features`、`Applications`、`Pin Description` 这种无编号英文标题，默认未必会被识别成标题样式。

5. 默认版式模板几乎全是中文字体和中文排版假设。
   证据：[template_configs/datasheet_template.yaml](/Users/sc/MinerU/md2word_file/template_configs/datasheet_template.yaml:25)、[template_configs/datasheet_template.yaml](/Users/sc/MinerU/md2word_file/template_configs/datasheet_template.yaml:34)、[template_configs/datasheet_template.yaml](/Users/sc/MinerU/md2word_file/template_configs/datasheet_template.yaml:76)、[template_configs/datasheet_template.yaml](/Users/sc/MinerU/md2word_file/template_configs/datasheet_template.yaml:120)、[template_configs/datasheet_template.yaml](/Users/sc/MinerU/md2word_file/template_configs/datasheet_template.yaml:128)
   支撑：即使英文内容能生成，默认也会套用 `宋体`、中文正文首行缩进等风格。

6. 运行时会把同一 `font_name` 同时写到 `eastAsia/ascii/hAnsi`。
   证据：[text_rendering.py](/Users/sc/MinerU/md2word_file/text_rendering.py:268)
   支撑：当模板配置是 `宋体` 时，英文正文和标题也会被强制落到中文字体策略上。

## 细节展开

输入层的兼容性其实不错。`input_adapter_runtime.py` 把 MinerU 输出统一成 `title/paragraph/list/table/image` 等内部块，再把视觉块上的 caption、footnote、html 抽出来；这一步不依赖中文文案本身。

真正的语言耦合出现在“文本怎么被理解”。当前实现对 TOC、附录、图表、章节的判断规则里，中文关键词是第一等公民，英文只补了很有限的一部分，比如 `table of contents`。这意味着英文文档不是不能出，而是“结构识别的成功条件更苛刻”。

样式层则更直接。默认模板把标题、目录、正文、表格、图注大面积配置成 `宋体`，正文还用了适合中文正文的首行缩进。对于英文 datasheet，这会影响观感，某些段落的行长和分页也会跟预期不同。

## 未决问题

- 没有现成英文样本回归测试，无法给出“哪些英文版式一定过、哪些一定不过”的经验边界。
- 没验证 MinerU 对英文 PDF 的 `text_level`、caption 字段、table html 输出稳定性是否与中文样本一致。

## 后续建议

如果要正式支持英文文档，下一步应该补一套“英文样本 + 英文模板/规则”的最小回归面，而不是继续沿用中文模板去赌泛化。

## 相关文档

- [module-mineru-to-docx-internal.md](/Users/sc/MinerU/md2word_file/.codestable/architecture/module-mineru-to-docx-internal.md)
- [datasheet_template.yaml](/Users/sc/MinerU/md2word_file/template_configs/datasheet_template.yaml)
