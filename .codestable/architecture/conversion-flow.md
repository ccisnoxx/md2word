---
doc_type: architecture
slug: conversion-flow
scope: MinerU 输入到 DOCX 输出的端到端运行流程，包括 direct 和 en2zh 两种模式
summary: 转换流程由 run_conversion 统一调度，先把 MinerU 包规整成页面块模型，再做页面修补和可选翻译，最后按模板/YAML 配置生成 Word 文档
status: current
last_reviewed: 2026-05-18
tags: [architecture, flow, mineru, docx, translation]
depends_on: [architecture-index, module-mineru-to-docx-internal]
implements: []
---

# 转换流程梳理

## 1. 启动流程

```mermaid
flowchart TD
    A["python mineru_to_docx.py [input_path]"] --> B["main()"]
    C["ENABLE_PYCHARM_RUN_CONFIG=True"] --> D["run_with_pycharm_config()"]
    B --> E["parse_args()"]
    E --> F["resolve_cli_run_options()"]
    F --> G["run_conversion()"]
    D --> G
```

- CLI 是默认路径，`ENABLE_PYCHARM_RUN_CONFIG=False`。锚点：`mineru_to_docx.py:255`
- PyCharm 路径只在显式打开开关时使用，参数来自 `PYCHARM_RUN_CONFIG`。锚点：`mineru_to_docx.py:486`
- CLI 不传 `input_path` 且当前目录看起来是脚本工程目录时，会尝试回退到 `PYCHARM_RUN_CONFIG["input_path"]`。锚点：`mineru_to_docx.py:514`、`mineru_to_docx.py:592`

## 2. 输入加载流程

```mermaid
flowchart TD
    A["input_path"] --> B{"目录还是 zip"}
    B -->|目录| C["直接作为 package_root"]
    B -->|zip| D["解压到 TemporaryDirectory"]
    C --> E["load_content_pages()"]
    D --> E
    E --> F{"v2 content list 存在"}
    F -->|是| G["build_v2_pages()"]
    F -->|否| H{"legacy content list 存在"}
    H -->|是| I["build_legacy_pages()"]
    H -->|否| J["FileNotFoundError + 附近目录提示"]
```

- 支持目录和 `.zip`；zip 只在临时目录中解包，不回写原包。锚点：`input_adapter_runtime.py:82`
- v2 识别 `content_list_v2.json` 和 `*_content_list_v2.json`；legacy 识别 `content_list.json` 和 `*_content_list.json`。锚点：`input_adapter_runtime.py:114`
- 块类型先映射为统一 `Block`，视觉块会解析图片路径、caption、footnote、HTML。锚点：`input_adapter_runtime.py:213`、`input_adapter_runtime.py:379`

## 3. 页面修补流程

```mermaid
flowchart TD
    A["content pages"] --> B["load_middle_pages()"]
    B --> C["repair_and_sort_pages()"]
    C --> D["merge_page_with_middle()"]
    D --> E["补 page_size / header / footer / visual metadata"]
    E --> F["attach_table_continuations()"]
    F --> G["pages ready"]
```

- `middle.json` 是补丁数据，不是主内容数据。锚点：`input_adapter_runtime.py:175`
- 被 MinerU 丢弃的页眉、页脚、页码会在主内容缺失对应类型时补回。锚点：`page_repair_runtime.py:120`
- 对缺图片的视觉块，会按 bbox 距离从 middle 视觉块中找同类型最近匹配。锚点：`page_repair_runtime.py:132`
- 长表续页占位会从后续只含 `table_placeholder` 的页面收集高度，挂到前一张真实 HTML 表格块上。锚点：`page_repair_runtime.py:49`

## 4. 翻译流程

```mermaid
flowchart TD
    A["pages"] --> B{"translation_mode"}
    B -->|direct| C["跳过翻译"]
    B -->|en2zh| D["extract_translation_items()"]
    D --> E["protect_text() 占位型号/单位/上下标变量"]
    E --> F["build_translation_batches()"]
    F --> G{"translation_response 已提供"}
    G -->|是| H["load_translation_response_file()"]
    G -->|否| I["llm_client.translate_payload()"]
    H --> J["apply_translation_responses()"]
    I --> J
    J --> K["回到渲染流程"]
```

- 翻译抽取跳过页眉、页脚、页码和表格占位符。锚点：`translation_runtime.py:15`
- ID 形式稳定，例如 `p0001.b0003.html.c0001`，用于回填原块。锚点：`translation_runtime.py:230`
- HTML 表格单元格会被逐格抽取和重写，回填时保留表格标签结构。锚点：`translation_runtime.py:498`、`translation_runtime.py:542`
- `llm_client.py` 使用 `prompt/translation_en2zh.md` 作为 system prompt。锚点：`llm_client.py:17`、`llm_client.py:144`

## 5. 渲染配置流程

```mermaid
flowchart TD
    A["template_document"] --> D["load_render_config()"]
    B["datasheet_template.yaml"] --> D
    C["subscripts_dictionary.yaml"] --> D
    D --> E["RenderConfig"]
    E --> F["resolve_document_language()"]
    F --> G["apply_document_language_overrides()"]
```

- 模板路径默认从 `template/datasheet_template.docx` 等候选位置查找。锚点：`mineru_to_docx.py:764`
- 样式 YAML 默认从 `template_configs/datasheet_template.yaml` 查找。锚点：`mineru_to_docx.py:782`
- 上下标词典默认从 `template_configs/subscripts_dictionary.yaml` 查找。锚点：`mineru_to_docx.py:778`
- 语言判定会抽取前若干页正文片段，按拉丁字母和 CJK 字符比例判断 `en` / `zh`。锚点：`mineru_to_docx.py:810`

## 6. 文档构建流程

```mermaid
flowchart TD
    A["pages + RenderConfig"] --> B["build_document()"]
    B --> C["create_document() / clear_document_body()"]
    C --> D["fill_template_intro()"]
    D --> E["render_document_page()"]
    E --> F["prepare_document_section()"]
    F --> G{"目录页?"}
    G -->|是| H["render_toc_page()"]
    G -->|否| I["render_page_body()"]
    I --> J["build_regions()"]
    J --> K{"one_col / two_col"}
    K -->|one_col| L["render_one_col_region()"]
    K -->|two_col| M["render_two_col_region()"]
    L --> N["render_block_into_container()"]
    M --> N
```

- 每个渲染页先拆页眉、页脚、页码和正文块。锚点：`page_layout_runtime.py:291`
- section 切换发生在目录起止、附录开始、横竖版变化、启用 MinerU 页眉页脚且有页眉页脚块等场景。锚点：`page_layout_runtime.py:210`
- 目录页通过标题匹配和目录项比例识别，目录连续页有单独判断。锚点：`page_layout_runtime.py:479`、`page_layout_runtime.py:504`
- 双栏识别按 y 区间扫描活动块，若同一横向区间同时存在左右块且没有 wide 块，则标记为双栏 band。锚点：`page_layout_runtime.py:594`

## 7. 块渲染流程

```mermaid
flowchart TD
    A["Block"] --> B{"type"}
    B -->|title| C["fill_title_paragraph()"]
    B -->|paragraph heading-like| C
    B -->|paragraph| D["fill_body_paragraph()"]
    B -->|list| E["fill_list_paragraph()"]
    B -->|visual| F["render_visual_block()"]
    F --> G{"table + html"}
    G -->|是| H["render_table_from_html()"]
    G -->|否| I["插入图片或 missing 占位文本"]
```

- 标题识别结合原始 `title` 类型和正文文本形态判断。锚点：`page_layout_runtime.py:709`、`text_rendering.py:744`
- 视觉块优先表格 HTML 渲染；非 HTML 表格或图片块走图片插入，缺图时输出占位文本并记录 warning。锚点：`page_layout_runtime.py:744`
- 表格标准路径生成 Word table 并处理 colspan/rowspan；复杂大表会降级为图片或展开表格；规则长表有专门路径。锚点：`table_render_runtime.py:84`、`table_render_runtime.py:175`、`table_long_renderer.py:28`
- 文本渲染统一经过 `prepare_text()`，再处理 `<sub>`、`<sup>`、`<br>`、粗斜体等 inline markup。锚点：`text_rendering.py:277`、`text_rendering.py:379`

## 8. 输出流程

- `build_document()` 返回 `Document` 实例后，`run_conversion()` 设置 `document.core_properties.title = source_path.stem`。锚点：`mineru_to_docx.py:704`
- 输出路径显式提供时使用该路径；zip 输入默认写同名 `.docx`；目录输入默认写到目录内 `mineru_output.docx`。锚点：`mineru_to_docx.py:757`
- 最终通过 `document.save(resolved_output_path)` 一次性写盘。锚点：`mineru_to_docx.py:705`

## 9. 当前行为注意点

- `translation_request_output` 的实际行为和帮助文案不完全一致：当前代码会写请求文件，但没有在缺少 `translation_response` 时退出，而是继续调用 LLM。
- `full.md` 不参与转换流程，仓库名里的 `md2word` 容易造成误解。
- 测试覆盖以函数级 characterization 为主，不能证明真实 Word 视觉版式完全符合预期。
