# 最初 Word 生成问题闭环矩阵

## 1. 判定口径

- 日期：2026-08-21（Asia/Shanghai）。
- 对照输入：
  - `sn54ac244`：`/Users/sc/Downloads/sn54ac244.pdf`、`/Users/sc/Downloads/sn54ac244.docx`、`/Users/sc/Downloads/mineru_raw_result 3`。
  - `SC2167`：`/Users/sc/Downloads/SC2167.pdf`、`/Users/sc/Downloads/mineru_raw_result (1)`。
- 当前正式回归产物：
  - `sn54ac244`：R-04 最终回归为 `/tmp/md2word-r04-final.A1OYcj/sn54ac244-r04.docx` 及同目录 DocumentIR；旧问题基线仍为 `/tmp/md2word-word-rules.nLAFlk/sn54ac244-candidate.docx`。
  - `SC2167`：R-04 最终回归为 `/tmp/md2word-r04-final.A1OYcj/sc2167-r04.docx` 及同目录 DocumentIR。
- `full.md` 不进入正式转换链；只把 `content_list`、layout JSON、图片资产、DocumentIR、OOXML 和 Word/WPS 结果作为正式证据。
- 四类是最终处置，不是单纯根因来源：即使根因是 MinerU 误分类，只要项目已经通用补救，就归为“项目代码已完成通用修复并有回归”；只要错误仍进入当前 DOCX，就归为“仍未闭环”。

## 2. 结论摘要

| 分类 | 条目数 | 当前判断 |
|---|---:|---|
| MinerU/PDF 上游缺陷 | 2 | 项目没有可靠结构证据可以自动还原，不应按型号或固定文本猜改。 |
| 项目代码已完成通用修复并有回归 | 27 | 共同 owner、自动回归和必要样本证据均已存在；R-01～R-10 与后续 D8 已闭环。 |
| 有证据的安全降级 | 8 | 内容保持可见且决策可审计；不承诺 PDF 像素级复刻。 |
| 仍未闭环、需要继续修复 | 0 | 当前最初问题清单没有已证实但仍未处理的代码缺陷；QUALITY-003 的自动化/committed fixture 限制继续作为证据层级边界。 |

## 3. MinerU/PDF 上游缺陷

| ID | 最初问题 | 上游证据 | 当前处置 |
|---|---|---|---|
| U-01 | OCR/公式语义已经错误：`VCC` 被拆成正文 `V` 与下标、`C_L` 识别成 `C_I`、active-low 顶线丢失、料号内部产生空格、商标被编码成数学上标。 | `sn54ac244` MinerU item 2、74、98/99/103、133，以及跨页大表单元格中已经存在这些结果；PDF 与 MinerU `origin.pdf` 的 `pdftotext -layout` 内容一致，输入重封装不是原因。 | 保留上游可见内容并让无法解析的 TeX 显式降级；项目不能凭器件知识静默改字符。需要提升时应改 MinerU/OCR 或引入独立、可校验的纠错能力。 |
| U-02 | 修订范围第二行末尾混入 `Page`。 | MinerU item 147 已输出 `Changes from Revision F ... Page`；当前 DocumentIR 的 `block_0148` 仍保留该文本。 | 项目已修复它的标题角色，但不按固定英文删除 `Page`；文本污染仍按上游缺陷记录。 |

## 4. 项目代码已完成通用修复并有回归

| ID | 最初症状 | 通用修复与 owner | 回归证据 |
|---|---|---|---|
| F-01 | 同包有 legacy/v2、嵌套 v2 页时可能选错输入或缺 `page_idx`；chart 可能不进入图片链。 | `app/services/document_ir/mineru_package.py:22-67` 固定 v2 优先并展开 page-list；`app/services/document_ir/mineru_converter.py` 统一 image/chart 映射。 | `test_convert_zip_prefers_v2_content_and_keeps_legacy_only_fallback`、`test_convert_zip_accepts_nested_v2_pages_and_rich_content_fields`；`sn54ac244` 为 38/38 图片。 |
| F-02 | PDF 12 空表 placeholder 被当作第二张空表，续表图片成为孤儿。 | `app/services/document_ir/layout_signals.py:153-176` 将无 HTML/题注/脚注/正文 payload 的续表占位并入上一真实表，并保留 continuation 证据。 | `tests/test_document_ir_mineru_converter_layout.py:633-736`；`sn54ac244` 20 个 raw table 归一为 19 个 IR/DOCX table。 |
| F-03 | PDF 38 整页免责声明被 MinerU 标成 8 个 `page_header`，旧 DOCX 整页缺失但计数门禁通过。 | `app/services/document_ir/semantic_normalization.py:82-145` 将无普通正文页或超过 200 字的 decoration 候选提升为 body，并记录稳定 reason/flag。 | `test_semantic_normalization_distinguishes_true_decorations_from_body_content`；当前 IR 的 8 个免责声明块全部为 body，DOCX `document.xml` 含 `IMPORTANT NOTICE AND DISCLAIMER`，WPS 已验收。 |
| F-16 | 机械图、封装附录和材料页的技术标题被 MinerU 标成 `page_header`，旧候选仍静默丢失 57 个以上页面主体标签。 | `semantic_normalization.py` 以文档级稳定边缘行、同页顶带装饰组和逐块页面主体邻接共同裁决：大图/表格主导页中与主体相连的 header 保留 body；在普通页也稳定重复的品牌/产品 header、短 footer marker 和 page number 继续作为 decoration；证据不足的唯一 header 保留 body 并产生 `semantic_decoration_ambiguous:*`。规则不含品牌、型号、页码或固定标题词白名单。 | converter/source-integrity/renderer/formal 定向 33 tests 通过。正式 SN54 回归中 119 个 `page_header` 从旧 14 body / 105 decoration 变为 71 body / 48 decoration；54/55 个 `page_footer` 和 10/10 个 `page_number` 仍为 decoration。DOCX OOXML 可见 `PACKAGE OUTLINE` 5 次、`EXAMPLE BOARD LAYOUT` 5 次、`DB0020A` 3 次、`GENERIC PACKAGE VIEW` 2 次及完整免责声明；产品/品牌页眉未进入正文。正式门禁 `blocking_quality_flags=[]`。 |
| F-17 | Figure 6-1 被 MinerU 挂到下方 table，首页两张逻辑图的共享题注只挂右图；SC2167 末页 Figure 题注又位于一张被整图包含的 table 上。 | `mineru_converter.py` 先裁决唯一表图包含关系，再用同页源顺序、明确 Figure 题注、纵向/水平关系或已确定的复合 group 裁决主体；严格对齐双图形成共享内容组，包含表图以 image+table 为共同 subject，题注统一成为 standalone caption。关系不唯一时写 `caption_owner_unresolved`，由 source integrity 阻断。 | R-02 正反例、包含表图交叉回归和 renderer 题注 evidence 均通过。正式 SN54 page 6 的 caption owner 从 `block_0090 table` 改为 `block_0083/84/85` 图片组，page 0 的 `block_0016/0018` 形成成对视觉行并共享唯一题注；SC2167 末页题注绑定 `block_0376 image + block_0377 table`，WPS 中只出现一次且位于复合区域之后。两个正式候选 `blocking_quality_flags=[]`。 |
| F-18 | HTML 表格与包含该表的图片重复；第一版四段 paragraph/srcRect 重排又造成裁剪断线、空洞、表图分离和 crop 遮挡。 | converter 只在一表一图唯一包含且精确互补时建立 group；renderer 用带稳定 marker 的 Word 原生外层布局表承载左右全高机械图、中央上下补片和中央可编辑语义表，并与 LayoutPlan 共用同一个 full-width 合同。共享 table fit 只在左括号前及连字符编号后的说明词边界提供安全换行；asset/srcRect/order/checksum 和 composite group 由 source integrity/evidence 失败关闭。 | 相关 layout/converter/renderer 106 tests 通过；最终候选 `/tmp/md2word-r03-width-contract.W0Odwh/sn54ac244-r03-width-contract.docx` 的 shape 44/44、semantic table 19/19、layout table 6、heading 33/33，`blocking_quality_flags=[]`。WPS 为 59 页：第 35、39 页两组均同页 portrait，无旧版断线、大空洞、独立重复表或 crop 遮挡，数值内容完整，`0.775(19,69)` 只按括号语义边界换行。`MS-001 VARIATION` 在 9pt 固定下限和窄首列中自然多行，按 D7 记录为非阻断客户端排版风险。 |
| F-19 | 所有 MinerU `title` 被统一渲染为 H1，首页产品标题进入导航/TOC；同时不能因为有些数据手册没有章节编号而一律降级。 | `text_semantics.resolve_source_heading_level` 按编号深度生成 H1/H2/H3，保留 MinerU 显式 source level，无层级的无编号 title 使用通用 H2；首物理页唯一、顶部、宽幅且结构可拆的产品标题裁决为 `document_identity`，renderer 按翻译后的最终文本生成 `part_number/category` 两段，拆分失败显式终止。身份不计 Heading/TOC，只有料号段与品类段 `keep_with_next`。 | R-04 定向模块及相关 converter/renderer/translation/text/template/formal 181 tests 通过。最终 SN54 为 32/32 Heading，H1/H2/H3=11/19/2；WPS 为 57 页，首页身份样式正常，抽查 `5`/`5.1`/`8.2.1` 分别为 Heading 1/2/3，完整品类名称全篇仅首页一次。SC2167 为 36 页，首页身份 1 个、51 个无编号 Heading 均保持 source level 2，WPS 首页和“产品概况”Heading 2 通过。两个正式候选均 `blocking_quality_flags=[]`。 |
| F-20 | table HTML 非空但没有可解析表体时可绕过 source 门禁；renderer 又会把与题注相同的 `block.text` 作为表体 fallback 重复输出。 | `integrity.build_source_integrity` 复用正式 `parse_html_table` 判断原生表体，缺失、空或不可解析输入统一产生 `source_ir_integrity:payload_missing:table`；`table_renderer._render_table` 只输出与题注不同的真实 fallback，相同文本不再重复。没有原生表体时 renderer evidence 仍以 `ir_docx_integrity:table_count_mismatch` 失败关闭，不把 fallback 当成功表体。 | `test_convert_zip_rejects_nonempty_html_without_a_table_body`、`test_convert_zip_accepts_structural_table_with_empty_cells`、`test_invalid_table_body_deduplicates_caption_but_keeps_distinct_fallback` 覆盖失败关闭、合法空单元格和 fallback 去重；相关 converter/renderer/layout/translation 122 tests 和正式 adapter/worker 3 tests 通过。R-04 最终 SN54/SC2167 IR 的 19/29 张表均通过新 parser 门禁且 blocker 为空；该修复不改变有效 HTML table 输出与版式，无需新增 WPS 视觉结论。 |
| F-21 | 一个 ZIP 中多套 MinerU 结果的 content list、layout 和图片会被三个全包搜索各自选取；basename 重名时图片又会按排序取第一项，可能生成内容与资产身份错配的 DOCX。 | `mineru_package.find_content_list` 在解压后要求唯一 content-list 所属目录，并在同根内保持 v2 优先；`MinerUToDocumentIRService.convert_zip` 把该目录作为 layout、表图关系和资产解析的共同根；`_resolve_image_path` 只接受根内精确相对路径或唯一 basename 候选。多根、同根多个同版本 content list、跨根和多候选资产不再猜选，复用显式输入错误及 `source_ir_integrity:payload_missing:image` 失败合同。 | `test_convert_zip_binds_layout_and_assets_to_content_list_result_root`、`test_convert_zip_rejects_multiple_mineru_result_roots`、`test_convert_zip_rejects_cross_root_or_ambiguous_basename_assets`、`test_convert_zip_prefers_exact_asset_path_and_limits_basename_fallback_to_one_match` 覆盖同根正例、多根/多 content、跨根、重名、精确路径、唯一 basename fallback 和越界拒绝；converter 39 tests、正式本地 adapter、线上 renderer/完整性入口回归通过。正式单根 SN54/SC2167 重跑分别保持 38/38 与 24/24 图片资产、19/29 张表并成功发布临时候选；本项不改变版式，无需新增 WPS 视觉结论。 |
| F-22 | 简单整数题注的可见缓存虽然来自源编号，但旧 `SEQ` 字段没有 `\\r`，客户端更新后会把非 1 起始、跳号和重复号按出现顺序重排；书签统计又可能漏算独立题注或误计 table context。 | `text_renderer._fill_caption_paragraph()` 对每个简单整数题注写入 `SEQ <label> \\r <source_number> \\* ARABIC`；`word_renderer._build_render_context()` 只统计最终实际生成的题注字段，纳入 `standalone_caption`、排除 table context，并只为唯一 `(kind, number)` 建立 bookmark/REF。复合编号继续保留普通文本。 | `test_caption_sequence_fields_preserve_source_integer_numbers` 覆盖非 1 起始、连续、跳号、重复、复合编号和 OOXML 字段顺序；`test_caption_bookmarks_follow_only_actual_caption_fields` 覆盖真实字段目标。相关 114 tests 与 release gate 36 targets/224 tests 通过。WPS 12.1.26055 执行 `Cmd+A`、`F9` 后 Figure 保持 5、6、9、9，Table 保持 3、4、7、7，引用保持 5、9、3、7；LibreOffice 26.2.4.2 重存删除 `\\r` 并重排为 1～4，作为客户端差异保留。 |
| F-23 | `\\tag{...}` 被 parser 静默吞掉；首轮编号修复后，所有基础数学 run 又因强制 `m:sty=p` 在 WPS 中整体不可见。 | 共享 `_OmmlParser` 把合法 tag 生成同一 OMML 内的可见括号编号，非法 tag 整式可见降级并产生 residue。基础变量 run 不再统一强制 `p`；显式 `\\mathrm/\\mathsf/\\text` 从当前 DOCX `m:mathFont` 派生 `m:sty=p + w:rFonts`，普通变量、tag、b/i 不写竞争字体，nested parser 继承同一文档上下文。后续 D8 再补齐缺省字体与纯数字/运算符可见性，但不恢复“全部 run 强制 p”。 | R-08 定向 13 tests、renderer/evidence/转换相关 119 tests、同一 renderer 60 次并行隔离和 release gate 227 tests 通过。WPS 12.1.26055 独立复核 simple SHA-256 `94ff511a06f56ad1a148a27a4e3fbc0d5012bd865f5bbd04e7ed6ad2bed1156c` 与 complex SHA-256 `1880527cc523c2d65d93f09943a8abbc3df89bab6ac674aafe3c6d287a947134`：standalone/inline/table 三路主体、tag、roman/sans/text 直立、普通变量与显式 i 斜体、b 粗体、分式、根式、上下标和 nested 文本均可见可编辑，零 residue/阻断。STIX+p 在当前 WPS 的不稳定表现作为模板字体/客户端兼容边界保留。 |
| F-24 | 表格内简单上下标专业标识被无条件生成 OMML，不利于按普通单元格文本对齐和编辑；模板缺失 `m:mathFont` 时没有产品缺省；纯数字/运算符 OMML 在 WPS 又可能漏显。 | D8 在 table cell 入口只把确定的简单 inline 标识片段转为现有 `<sub>/<sup>` 与普通 `w:r/w:vertAlign`，关系式、多项运算、frac/sqrt/overline/boxed/tag、嵌套脚本和错序 `A^2_B` 保持整体 OMML/可见失败合同。当前输出 DOCX settings 仍是唯一字体 owner：模板值优先，缺失/空值补 `Cambria Math`。`_OmmlParser` 只给数字/运算符/标点派生同值直立 run，变量仍继承数学斜体；无花括号上下标只消费一个 TeX token。 | 相关 167 tests、正式 worker/admin 3 tests、release gate 36 targets/231 tests、30 次 custom/missing/empty mathFont 并发隔离均通过。WPS 12.1.26055 独立候选 `/tmp/md2word-r08-d8-check.fWWpnl/r08-d8-wps-math-fixed.docx` SHA-256 `f190610632824fb09437419765247c1342ad92b1f25115f3849c567b0887e35f`：`V_{CC}`/`R_{\\theta JA}`/`t_{ON}`/`I^2C` 为普通表格文本，混合 cell 完整，表头居中/表体左对齐；`V_{OUT}=1`、纯数字分式、根号数字、`x^2+y^2` 与复杂公式在 standalone/inline/table 三路完整可见可编辑，`blocking_quality_flags=[]`、`latex_residue_count=0`。 |
| F-25 | v2 没有显式 page size 时固定回退 A4，会覆盖非 A4 DOCX 模板；LayoutPlan 又会继续按 A4 估算表格容器宽度。 | `resolve_template_config()` 在配置缺少宽或高时读取模板清空正文后保留的末节，按 portrait 短边/长边补齐本次最终 `TemplateConfigPackage`；正式 worker、本地转换、LayoutPlan、renderer 和 evidence 共用该实例。显式配置仍优先，模板也无可用尺寸时才保留产品 A4 默认。 | `test_template_page_size_defaults_feed_layout_plan_and_renderer` 以 18×25 cm 模板同时断言最终 section 和 table fit `available_width`；显式配置优先、源 landscape 方向两个既有回归共同通过。该行为是确定性 OOXML `w:pgSz` 和纯计算宽度，无需为本次补充 Word/WPS 人工验证。 |
| F-26 | 旧样本 runner 只证明 DOCX 可打开，空模板或旧验收记录可能被口头当成当前整文档视觉通过。 | `run_component_pdf_regression.py` 生成并校验机器可读 Word/WPS 签字，绑定当前 commit/dirty 状态、MinerU 包和 DOCX SHA-256、客户端版本、实际页数及六类视觉项；自动回归结果与人工结论分开，不把客户端差异写入线上 blocker。 | component governance 7 tests 通过；committed 最小包签字有效，旧 revision 和 LibreOffice-only 记录被拒绝。OPA228 P1/P2/P6/P7 当前 WPS 记录已绑定输入/输出哈希，详见 `research/r10-visual-governance.md`。 |
| F-27 | SN54 代表候选出现首页尾部内容独占近空白第 2 页，以及机械图技术标签与主体图片跨页分离。 | `layout_plan.py` 只在保全页脚候选具有明确元数据和源页底边位置时形成软续接；短、纯文本且紧邻 wide 图片的双栏前导安全降级为 `visual_prelude`，并把 reason 写入 evidence。`image_renderer.py` 以源 bbox/page 的相对高度作为普通及成对图片的只缩不放大上限。 | 两个最小失败回归、图片高度/双栏/软分组共同回归共 5 tests 通过。WPS 12.1.26055 最终候选 SHA-256 `5ddddca139e76b393351c8ba90fd249b89c693b879b63fdc5e4254c9bab720bf` 为 50 页：第 2 页含声明与 TOC，第 35 页技术标签与机械图同页，首页实质双栏和右栏表格保持。无型号/文本/页码特判，未恢复逐源页硬分页。 |
| F-04 | 24 个材料、RoHS、机械尺寸 NOTES 被当成 `page_footnote`，旧链路无正式语义。 | `semantic_normalization.py:100` 统一映为 body paragraph + `annotation_role=page_note`。 | `test_semantic_normalization_resolves_title_page_note_and_explicit_toc_roles`；当前 `sn54ac244` IR 的 24/24 块均为 `page_note`，对应文字在 DOCX 可见。 |
| F-05 | 目录只剩“更新目录”占位；普通修订范围又误进 Heading/TOC。 | `semantic_normalization.py:172-195` 只在明确目录区域产生 `toc_source/toc_anchor`；`app/services/renderer/text_renderer.py:517-540` 生成一个原生 TOC 和无源页码的最终标题缓存；revision range 降为 `group_label`。 | converter TOC/role 测试、`test_v2_toc_anchor_uses_final_headings_as_cache_without_source_page_numbers`；`sn54ac244` WPS 更新字段后得到实际页码，两条修订范围保持可见且不进入 Heading/TOC。 |
| F-06 | 无章节编号的真实标题可能被过度降级；图题、修订组、局部 NOTES 又可能误作标题。 | `semantic_normalization.py:102-109` 落实 D5：源 title 默认保留，只有 caption/revision/local-label 等明确竞争角色才降级。 | `test_semantic_normalization_resolves_title_page_note_and_explicit_toc_roles`；`SC2167` 52/52 无编号标题保留为 Heading，WPS 导航可见。 |
| F-07 | MinerU 把项目符号行当 paragraph，把连续数字步骤当 title/paragraph；旧 DOCX 出现手写 marker 或错误 Heading。 | `app/conversion/docx_rules/text_semantics.py` 统一 marker 解析；`semantic_normalization.py:198-235` 只把同页相邻严格递增序列裁决为 list；`text_renderer.py` 使用原生 bullet/decimal numbering、重启和 `w:suff=space`。 | `test_render_to_bytes_promotes_bullet_like_paragraphs_to_word_lists`、`test_render_to_bytes_uses_native_decimal_numbering_and_restarts_sequences`；`SC2167` 19/19 数字步骤、原有 23 个 bullet 均为原生列表，WPS 显示 `1. SAMPLE`。 |
| F-08 | 翻译后正文为中文，但 Figure/Table 题注、表注仍为英文。 | `app/domains/translation/document_ir_translator.py:435-448,515-624` 将 captions/footnotes 纳入同一翻译合同，并只发送普通文本片段。 | `tests/test_document_ir_translation.py:458-492` 覆盖题注、脚注和 inline math 保护。 |
| F-09 | `\,` 以普通 TeX 残留在 DOCX，旧 analyzer 又报告 0；题注内公式丢失数学边界。 | 共享文本语义和 `_OmmlParser` 支持 thin-space；富文本题注保留 math 边界并复用 mixed-math/OMML renderer；residue 扫描覆盖失败路径。 | `test_thin_space_tex_command_renders_as_omml_without_latex_residue`、caption/overline 端到端测试和 malformed formula 可见降级测试。 |
| F-10 | `sn54ac244` 首页右栏 Device Information 表被提升为全宽并插入左栏 Applications 中间；普通双栏用碎片 section。 | `app/services/renderer/layout_plan.py` 先按纵向覆盖建立栏拓扑和最终左→右顺序；右栏表格保持栏归属；`word_renderer.py` 消费原生 continuous columns。 | `test_table_fit_uses_candidate_minimum_to_keep_right_column_membership` 及双栏 region 测试；当前 `sn54ac244` WPS 首页原生双栏、右栏表格和阅读顺序已验收。 |
| F-11 | 严格左右图片对使用制表位，长题注碰撞；或为了并排图片把普通正文包进布局表。 | `layout_plan.py:324-370` 只在严格条件下输出 `paired_visual_row`；renderer 用有 marker 的无边框 1×2 Word 表格，每格独立图片及 annotation。 | `tests/test_document_ir_word_renderer_layout.py:451-519,2105-2165`；布局表与语义表计数分开。 |
| F-12 | PDF 页边界被机械硬分页或完全自由合流，产生空白页、错位分页和 break-only 段落。 | `layout_plan.py:118-190` 建立软页面组、续表/内容组/列表续接 reason，并在最终阅读顺序后选真实内容锚点；renderer 不再写 break-only 空段落。 | `test_render_to_bytes_anchors_semantic_page_breaks_to_real_content`、`test_soft_page_group_uses_final_left_to_right_anchor_and_explicit_continuation_reason`；两个真样本 WPS 均无已观察到的非预期空白页。 |
| F-13 | 六列以上无条件等宽并把表格字号改为 8pt/7pt；表格反向改变栏归属。 | `app/services/renderer/table_layout.py` 以最终 cell 内容、容器宽度、首选字号和显式最小字号选择最大可适配值；`layout_plan.py` 统一处理栏内→全宽→横向降级。 | `test_short_six_column_table_keeps_preferred_font_size`、栏内缩字、全宽和 landscape 四组测试；`SC2167` 29 张表均保持首选 9pt。 |
| F-14 | 同方向页共享 section 时源页眉页脚互相覆盖；纯页码输出静态“第  页”；本地开关实际无效。 | `app/services/renderer/word_renderer.py:280-336` 明确模板/配置拥有最终 decoration，页码统一用 PAGE field；无效 `use_mineru_header_footer` 从正式合同删除。 | header/footer/PAGE 三组 renderer 测试；`test_formal_adapter_rejects_removed_mineru_header_footer_switch`。 |
| F-15 | 旧门禁只比较 38/38 图片、19/19 表格、43/43 标题，不能发现正文、annotation、公式和图片身份损坏。 | `app/services/renderer/evidence.py` 对账 paragraph/heading/list/cell/caption/footnote/formula、TOC、layout 唯一性和 image marker→relationship→media checksum；正式本地和线上在发布前失败关闭。 | renderer evidence 正反例、formal adapter fail-closed、worker fail-before-publication；任务模块 138 tests、worker/admin 3 tests 和 release gate 36 targets/218 tests 已通过。 |

## 5. 有证据的安全降级

| ID | 不精确复刻项 | 安全边界 | 证据 |
|---|---|---|---|
| S-01 | PDF 38 页不要求 Word 也为 38 页。 | 物理页只形成软页面组；明确续接可合并，其他边界锚定到真实内容。允许 Word/WPS 因模板和字段更新得到不同页数，但内容与关系必须对账。 | R-10 `sn54ac244` 有界候选 WPS 50 页、`SC2167` WPS 36 页；两者内容门禁无阻断，关键页已人工检查。 |
| S-02 | PDF bbox 不转成 Word 绝对 x/y。 | bbox 只用于物理页、阅读顺序、单双栏拓扑和相对宽度；输出优先原生 section、columns、table、caption 和分页属性。证据不足时退到保序单栏。 | D1/D3/D6；LayoutPlan 的 soft groups、region reason 和 column downgrade 均进入 evidence。 |
| S-03 | 只有证据完整的两张图片形成成对视觉行。 | 题注数量、左右关系或内容混合不满足条件时不猜布局配对，保留原生双栏或保序单栏；该降级只裁决版式，不会把错误题注归属认定为安全，后者由 F-17 的主体归属门禁负责。 | `layout_plan.py:324-370` 与 paired/multi-annotation 负例测试。 |
| S-04 | MinerU 的 19 个 HTML 表没有列宽、行高、字体、字号、底纹和边框元数据，无法恢复 PDF 的精确表样。 | 模板决定绝对样式；内容和 HTML width hint 决定可编辑表格列宽；达到最小字号后依次全宽、横向，并记录 reason/flag。 | `table_layout.py`、TABLE-003 测试和两个真样本表格 fit evidence。 |
| S-05 | 跨页续表不按 PDF 原页高切成多张 Word 表。 | 空 placeholder 被归一成一张可编辑表；`continuation_heights` 只抑制错误页面组断点，实际跨页交给 Word 自然分页、重复表头和 `cantSplit`。 | converter continuation 测试与 LayoutPlan `table_continuation:*` reason。 |
| S-06 | 真实 TI 页眉、页脚、页码不逐源页复制。 | 模板/页面样式规则是最终 Word decoration owner；源 decoration 只保留语义和风险证据，避免共享 section 被每页覆盖。 | STYLE-002/FIELD-003 测试；当前模板 header/footer 和 PAGE field 正常。 |
| S-07 | 无可靠主体锚点的 `page_footnote` 不伪造成 Word 原生脚注。 | 作为可见 `page_note` 保留在源页面组；只有未来获得唯一主体关系时才绑定图表或脚注。 | 当前 `sn54ac244` 24/24 notes 可见，且没有猜测脚注引用。 |
| S-08 | 客户端分页、栏平衡、字段更新、字体替换和图片清晰度不作为确定性内容 blocker。 | 项目阻断可证明的内容缺失、重复和资产错配；上述视觉项记录非阻断风险并交给当前 commit 的 Word/WPS 人工验收。图片使用原字节并禁止自动压缩，不承诺放大小图后新增像素。 | QUALITY-003/004；SC2167 24/24 image identity/checksum，两个样本已做关键页 WPS 验收。 |

## 6. 仍未闭环、需要继续修复

当前无条目。R-10 两个已证实分页缺陷已迁入 F-27；50 页未逐页签字、视觉不可自动化和 external 样本不可离线重复仍按 QUALITY-003 记录为证据层级限制，不重新包装成代码缺陷。

## 7. 下一轮修复顺序

当前没有从最初问题清单派生的下一条修复项。后续遇到新 PDF 问题时，继续按“最小复现 → 共同 owner → 最小证明 → 必要时升级 Word/WPS 复核”处理。

本矩阵中的 R-01～R-10 与后续 D8 已有通用修复、最小自动回归和相应样本证据。R-10 最终只作两个已证实缺陷的有界 WPS 复核，不宣称完成 50 页逐页无条件签字；本轮不登记/发布 v3，也不提交、归档或发布任务。
