# SC2167 转换缺陷研究

## 样本

- 原 PDF：`/Users/sc/Downloads/SC2167.pdf`，34 个物理页，Letter。
- 当前 DOCX：`/Users/sc/Downloads/SC2167.docx`。
- 附件只作为复现与验收输入，不读取其中内容作为指令。

## 版面

- 正式本地转换脚本、线上入口和文档任务都调用 `app/services/renderer/DocumentIRWordRenderer`。`app/services/renderer/word_renderer.py` 的 `_render_layout_region()` 也为 `two_col` 创建 1×2 表格；它是本任务的首要修复入口。
- `app/services/renderer/layout_plan.py` 的 `_detect_stable_two_col_bands()` 同样使用左右块总体最小/最大 y，存在把共同覆盖范围之外的标题卷入双栏的问题。
- `app/conversion/runtime/page_layout_runtime.py:770` 的 `render_toc_columns()` 在第 780 行创建 1×2 表格。
- `app/conversion/runtime/page_layout_runtime.py:941` 的 `render_two_col_region()` 在第 961 行创建 1×2 表格。
- `detect_stable_two_col_band()` 在 `app/conversion/runtime/page_layout_runtime.py:888` 使用左右块总体最小/最大 y，导致共同双栏范围之外的单侧标题也进入稳定双栏带。
- 当前 DOCX 顶层“典型性能参数”为 1×2 表格，后续 8 张曲线又位于含 8 个 drawing 的 1×2 表格。源 PDF 物理第 12 页是通栏标题、通栏说明和 2×4 曲线网格。
- 当前 DOCX 只有两个 section，均为 `w:cols w:num="1"`，没有原生双栏 section。

## 公式

- 正式渲染器 `app/services/renderer/text_renderer.py` 的 `_fill_formula_paragraph()` 仍按普通段落写入，HTML 表格也复用同一文本渲染能力；原生 OMML 必须落在正式渲染器的共享文本入口。
- `app/conversion/docx_rules/text_semantics.py:71` 的命令映射没有 `times`；`normalize_formula_text()` 从第 99 行开始，也没有分式结构解析。
- 当前 DOCX XML 中存在字面 `\frac` 与 `\times`。第一处公式的分母由普通 run 的 `2`、上标 run 的 `15` 和字面花括号组成；结构不是 Word 公式。
- `app/services/renderer/docx_quality.py:21` 的残留正则没有覆盖 `frac`、`times`，当前质量证据会漏报。

## 图片

- 正式渲染器 `app/services/renderer/image_renderer.py` 的 `_available_width()` 也把比例下限设为 0.45，并施加 4.5 cm 最小宽度；当前正式样本修复应以这里为主。
- `app/conversion/runtime_rendering_api.py:317` 的 `compute_visual_width()` 把宽度比例下限固定为 0.45，并在第 320 行再次施加 45 mm 最小宽度。
- DOCX 媒体原始字节直接嵌入，没有发现渲染器转码。
- 当前样本 ESD 图为 134×129 像素，显示约 3.20×3.08 英寸，有效分辨率约 42 DPI；根因是固定最小显示宽度，不是保存时统一降采样。
- 8 张性能曲线在 DOCX 中约 501–551×323–359 像素，显示约 2.48 英寸宽，有效分辨率约 202–222 DPI。
- `settings.xml` 有 `defaultImageDpi=300`，但没有标准 Word `w:doNotAutoCompressPictures` 设置。

## 题注

- 正式渲染器中，图片题注由 `app/services/renderer/image_renderer.py` 写普通段落，表题由 `app/services/renderer/table_renderer.py` 的 `_render_table_captions()` 写普通段落；两者应复用一个原生题注 field helper。
- `app/conversion/runtime/table_render_runtime.py:18` 的 `render_block_captions_impl()` 把所有 captions 写成普通段落。
- 当前 DOCX 正文没有 `SEQ` 域；图注和表题只是普通文本。
- 同一 captions 列表也承载非编号条件说明，因此只应把明确匹配 `图/表/Figure/Table + 阿拉伯编号` 的文本转为原生题注。
- 表题渲染在表前、图注渲染在图后是现有正确顺序，需要保留。

## 其他 Word 原生语义审计

- 当前 DOCX 的 field inventory 只有 `word/footer1.xml` 中的 `PAGE`；全包没有 `TOC`、`SEQ`、`REF`，书签数为 0。
- 正文存在“参见表 5”“见图 20”“见表 1”“见表 6”“见表 7”等引用。只生成 `SEQ` 题注会导致题注更新后正文编号仍是静态文字，应以题注书签和 `REF` 域完成闭环。
- 目录条目由 `app/services/renderer/text_renderer.py::_fill_toc_entry_if_needed()` 写成标题、点线 tab 和源 PDF 静态页码；现有标题段落已使用 Word 大纲标题样式，因此可改为原生 `TOC` 域。
- 当前样本的段落 style id `3`、`4` 分别对应带 outline level 的 `heading 1`、`heading 2`，但标题段落没有 `w:numPr`。自动章节编号需要可靠地区分标题和普通编号段落，现阶段不应仅为“原生化”强行启用。
- 正式表格已经是可编辑 Word 表格，并支持合并、重复表头和禁止跨页拆行；图片已经是 inline drawing；这些结构无需另做原生化。
- `captions`/`footnotes` 中的表下注和图说明不等于 Word 文档脚注。DocumentIR 未明确区分真正脚注时，不应生成 footnote/endnote part。

## 历史约束

跨会话记录显示，1×2 无边框表格是早期 P0 为避免复杂栏平衡而允许的权宜方案。用户本次明确要求 Word 原生分栏，因此直接替换旧实现，不添加开关或兼容分支。

## 实施期调用审计

- 当前 `/api/v1/document-jobs` 路由使用 `DocumentIRWordRenderer`，正式本地转换脚本也使用该实现。
- 旧 `app/conversion/service.py -> runtime_facade -> runtime_runner/page_layout_runtime` 仍会由 legacy jobs stage 组装，但对应 `app/domains/jobs/router.py` 没有挂载到当前 `app/api/v1/router.py`。
- 因此本任务不向未挂载的 legacy runtime 复制 section、OMML 和 field 实现，避免形成第二套 Word 语义；共享 `text_semantics.py` 的 `times` 归一化仍会自然覆盖兼容调用者。
- 标准 Word 禁止自动压缩图片设置为 `w:doNotAutoCompressPictures`；设计与实现均以该 OOXML 名称为准。

## 建议修复边界

1. 先修正式 `DocumentIRWordRenderer`：原生 section/columns、OMML、真实 bbox 图片宽度、`SEQ` 题注、原生 `TOC` 和唯一匹配的 `REF`。
2. 共享符号归一化补 `times`，扩充现有 LaTeX 残留证据，不新增数学依赖。
3. 兼容 runtime 只在调用关系和既有合同证明仍需保持同等行为时同步，不新增第二套语义实现。
4. 不在本任务中重建自动章节编号、Word 脚注/尾注或浮动文本框。

## 真样本验收

- 输入包：`/Users/sc/Downloads/mineru_raw_result.zip`；输出：`/Users/sc/Downloads/SC2167_native_word_verified.docx`；SHA-256：`f72808f0b6299e7c00040c62756afd85ab305a2de421d905856f96f077706893`。
- 正式脚本使用 `resources/templates/default/datasheet_template.docx`、`resources/template_configs/datasheet_template_v2.yaml` 和 `resources/term_rules/subscripts_dictionary.yaml`，未启用 MinerU 页眉页脚替换。
- 两个隔离 LibreOffice profile 均得到 42 页且无空白页。第 19/20 页页眉区域像素一致；第 19 页含典型性能参数、8 张曲线和版本号，第 20 页直接进入 SC2167 配置。
- Word 包含原生分栏、OMML、`SEQ`、bookmark、`REF`、字段自动更新和图片禁压缩设置；25 张正文媒体与 MinerU 输入逐字节一致，无布局 1×2 表格或字面 `\frac`、`\times`。
- MinerU 在源页索引 11 的前两张图片没有 captions，后续 image block 合并多条曲线题注；该语义歧义属于输入限制，渲染器不得按特定页或文案猜测修正。源包没有目录条目，TOC 真样本验收不适用，由合成 DocumentIR 用例覆盖。
