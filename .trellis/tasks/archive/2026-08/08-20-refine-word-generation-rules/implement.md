# 实施计划

## 前置门禁

- [x] 用户审阅并明确批准 `prd.md`、`design.md` 和本实施计划。
- [x] 批准后运行 `task.py start`，再加载 `trellis-before-dev` 与本任务上下文。
- [x] 修改每个正式 owner 前完整读取该文件、相关类型、调用者和测试；保留用户现有未提交改动。
- [x] 不修改已发布的模板 v1/v2 文件、hash 或历史转换产物，不覆盖用户提供的 PDF/DOCX。

## 实施阶段

### 1. 固化规范与失败用例

1. 将 D1–D8 写入 `.trellis/spec/backend/word-generation-rules.md`，同步模板配置和质量规范的 owner、状态、冲突及验证矩阵。
2. 先在既有测试模块增加最小失败用例，覆盖：正文误标 decoration、标题竞争角色、软页面分组、右栏表格、成对视觉行、表格字号下限、TOC 缓存、题注/脚注翻译和 `\\,` 残留。
3. 不为单一型号、固定页码或固定文本新增条件分支。

### 2. 语义归一化、翻译与内容门禁

1. 在 DocumentIR 转换边界建立唯一的文档级语义裁决，保存源类型、最终类型、布局去向和稳定原因；converter 只做机械映射。
2. 修正 decoration、`page_footnote`、标题竞争角色和明确 TOC 区域；每个可见源块必须有且仅有一个去向。
3. 翻译合同覆盖 captions/footnotes，并复用现有文本语义入口保护公式片段；补 `\\,` 支持和残留扫描。
4. 扩展 source→IR 完整性校验；确定性丢失、重复或资产错配进入阻断标记，语义歧义保留内容并记录非阻断风险。

### 3. 软页面分组与 Word 原生布局

1. 让 `LayoutPlan` 成为页面组、分页锚点、单双栏拓扑和降级原因的唯一 owner；正式本地和线上链路把同一份最终计划传给 renderer 与 evidence。
2. 按纵向覆盖、栏边界和内容组确定栏归属，删除单块 midpoint 对 region 的决定权；最终阅读顺序固定为左栏后右栏。
3. 真实双栏继续使用 Word 原生 continuous section；严格图片对单独输出 `paired_visual_row`，用无边框 1×2 Word 表格承载图片及各自题注。
4. 分页和 section 变化附着于真实内容，不生成 break-only 空段落；页码统一使用原生 `PAGE` field，模板拥有最终页眉页脚。

### 4. 表格配置与适配

1. 为 `table_content` 增加可选 `min_font_size`，校验 `1 <= min_font_size <= font_size`；缺失时等于首选字号，不隐式缩字。
2. 复用现有 HTML table parser，集中计算容器、内容感知列宽和首选/最小字号之间的最大可适配字号；删除六列以上等宽及 8pt/7pt 硬编码。
3. 固定执行“所属栏 → 单栏全宽 → 新页横向”的安全降级，每次换容器都从首选字号重新计算；表题和表注不随单元格缩字。
4. 新增不进入 manifest 的不可变 bundled v3 候选配置。候选最小字号先用 7pt 做真样本验证；只有全部样本的 Word/WPS 可读性通过后才登记、发布或设为默认，既有默认指针不自动迁移。

### 5. DOCX 证据与发布门禁

1. 对账规范化可见文本、标题/列表、table cells、captions/footnotes、TOC disposition、图片资产 identity 和公式残留，而非只比较数量。
2. 分开统计语义表格与成对视觉行布局表格；记录软页面组、栏降级和表格适配决策。
3. 确定性内容损坏失败关闭；栏置信度、末级表格降级和客户端分页保持非阻断、可审计风险。
4. 本地正式入口与线上 worker 共享同一门禁，不增加并行 writer、兼容开关或静默 fallback。

### 6. 真样本与最终验证

1. 用 `/Users/sc/Downloads/mineru_raw_result 3` 生成新的 `sn54ac244` 候选；SC2167 必须使用与 `/Users/sc/Downloads/SC2167.pdf` 对应的 MinerU 原始产物，输出写入临时目录。
2. 结构检查覆盖免责声明、修订记录、TOC/Heading、原生 columns、布局表格标记、表格字号、captions/footnotes、OMML/TeX、图片 identity 和阻断标记。
3. LibreOffice→PDF/PNG 仅作辅助诊断；在 Word/WPS 更新字段后人工检查首页双栏表格、修订页、末页免责声明、无编号标题、误标题、宽表降级、空白页和孤立题注。
4. 若真样本失败，回到相应通用 owner 和最小失败用例，不添加样本文案或页码特例。

### 7. D8 数学字体与表格数学分级渲染

1. 修改当前 DOCX 数学字体 owner：保留模板 `m:mathFont`；模板缺失时仅在输出 settings 补 `Cambria Math`，并让现有 OMML 直立 run 共用该值。
2. 在语义 table cell 写入点增加最小确定性分类：简单技术标识转现有内联 HTML/run 上下标，复杂、嵌套、关系式或多项运算继续 OMML；不新增公开配置、不建第二套 parser。
3. 最小回归同时证明：表格内 `V_{CC}`、`R_{\theta JA}`、`t_{ON}`、`I^2C` 生成普通 `w:r` + `w:vertAlign`；分式/根式/关系式仍有 OMML；正文同样简单公式仍走原 OMML；表头/表体对齐、表格字号与公式整体可见性不变。
4. 用无 `m:mathFont` 与已有自定义数学字体的模板分别检查 OOXML；在 Word/WPS 中复核简单表格标识可按普通文本左对齐/居中和编辑，复杂表格公式仍可见、可编辑。

## 必需自动化验证

先独立运行可并行发现问题的阶段，再对最终候选运行聚合门禁：

```bash
.venv/bin/python -m unittest \
  tests.test_document_ir_layout_contract \
  tests.test_document_ir_mineru_converter_layout \
  tests.test_document_ir_translation \
  tests.test_document_ir_word_renderer_layout \
  tests.test_template_layout_config_schema \
  tests.test_conversion_sandbox_dev_tools

.venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_generated_word_keeps_renderer_ooxml_semantics \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_integrity_gates_fail_before_ir_or_word_publication \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_layout_config_admin_creates_draft_version_without_mutating_source_yaml

cd frontend
npm run test:unit
npm run build
```

正式样本命令在实施时使用现有 CLI，不增加验收 wrapper：

```bash
.venv/bin/python scripts/dev/run_local_mineru_conversion.py \
  '/Users/sc/Downloads/mineru_raw_result 3' \
  --output <temp-dir>/sn54ac244-candidate.docx \
  --translation-mode direct

.venv/bin/python scripts/dev/run_local_mineru_conversion.py \
  '<SC2167 对应的 MinerU 原始产物>' \
  --output <temp-dir>/sc2167-candidate.docx \
  --translation-mode direct

soffice --headless --convert-to pdf --outdir <temp-dir> <candidate.docx>
pdftoppm -png -r 150 <temp-dir>/<candidate.pdf> <temp-dir>/word-page
```

最终候选再运行：

```bash
.venv/bin/python scripts/ops/check_release.py
git diff --check
```

若本机无法使用 Word/WPS，则自动化与 LibreOffice 结果不能替代真客户端门禁，任务保持未完成并明确记录待验收项。

## 风险与回滚

- OOXML 结构正确不等于 Word/WPS 视觉稳定；新 v3 模板在真客户端通过前不发布、不设默认。
- 翻译后文本扩张会改变表格适配和分页；适配必须读取翻译后的最终 IR，不能缓存原文结果。
- section 过多会造成栏平衡和空白页风险；只在真实拓扑变化或 D6 安全降级时创建 section。
- `min_font_size=7pt` 只是 v3 验证候选值，不是业务代码默认值；若不可读，只调整新草稿配置，不突破用户配置下限。
- 回滚时恢复本任务代码与新默认指针；不修改历史 seed、不放松内容门禁、不使用破坏性 Git 命令。

## 交付

- 更新后的 Word 生成、模板配置和质量规范。
- DocumentIR/布局/渲染/翻译/门禁的最小共同根因改造及定向测试。
- 新 bundled v3 候选；版本 manifest 只在全部真样本验收通过后登记。
- `sn54ac244`、`SC2167` 的“旧 DOCX/PDF/MinerU 对照 → 代码根因 → 通用修复 → 回归结果”证据记录；生成文件只作诊断，不是交付物且不提交仓库。

## 当前实施状态（2026-08-21）

- 阶段 1–6 的 D1–D7 首轮通用改造与真样本回归已完成；正式本地/线上共享布局计划与内容门禁均已落地。任务继续保持 `in_progress`，不能仅凭候选 DOCX 视觉通过宣告完成。
- `sn54ac244` 已完成正式转换、结构对账、LibreOffice 辅助诊断和 WPS 验收：内容门禁无阻断，首页原生双栏及右栏表格正常，目录更新后生成实际页码和公式，修订范围不进入 Heading/TOC，末页免责声明完整。
- `SC2167` 使用 `/Users/sc/Downloads/mineru_raw_result (1)` 完成正式转换、结构对账、LibreOffice 辅助诊断和 WPS 验收：383 个主源块均有显式去向，52/52 Heading、19/19 连续数字列表项、29/29 表格、24/24 图片及全部可见 payload 对账通过，`blocking_quality_flags=[]`。WPS 最终为 36 页，首页原生双栏、无编号章节 Heading、故障清除原生数字步骤及末页内容均正常；数字编号使用原生 `w:suff=space`，显示为 `1. SAMPLE` 而非手写 marker 或 `1.SAMPLE`。
- 最终 SC2167 候选为 `/tmp/md2word-sc2167-final.ZYeADz/sc2167-final.docx`（SHA-256 `0bd77524c335cf25e6d811296f82f76c4eeca21095224754e450afcecc92b523`），对应 IR SHA-256 为 `85bd4e9cc16c0b3b73f9339b0cc7311a51943aa3b3bbba350a70740e7a37e5d1`；临时产物不提交仓库。
- v3 YAML 仅为未登记候选；manifest、published/default v2 均未改变。两个真样本已通过本任务验收，是否登记、发布或设为默认仍需单独显式决定。
- 自动验证已通过：任务模块 138 tests、正式 worker/admin 3 tests、前端 unit 127 tests 与 build、release gate 36 targets/218 tests、compileall、Trellis validate 和 `git diff --check`。
- R-02 已由 converter 的跨类型题注主体裁决闭环：SN54 page 6 的 `Figure 6-1` 从 `block_0090 table` 迁移到 `block_0083/84/85` 图片组；page 0 的 `block_0016/0018` 形成严格成对视觉行并共享一个独立题注。关系不唯一时 source integrity 阻断，不按品牌、型号、页码或题注固定文本猜测。
- R-03 第一版四段 paragraph/srcRect 流式重排已被 WPS 否决：旧候选在 WPS 第 35、39 页出现裁剪断线、大面积空洞，且可编辑表落到整幅机械图下方。该渲染路径已删除，当前改为一个带稳定 group marker 的 Word 原生外层布局表：左右机械图骨架保持全高，中央上/下图片片段与中央可编辑语义表组成同一关系容器。复合布局表和嵌套语义表分别计数；每个源 table/image 主 block、asset、`srcRect` 顺序和 checksum 仍只消费一次。歧义关系、无效 HTML、缺失资产、表区过大或片段合同损坏继续失败关闭。
- R-03 最终原生复合候选为 `/tmp/md2word-r03-width-contract.W0Odwh/sn54ac244-r03-width-contract.docx`（SHA-256 `1730e6892223e9a87d472309233af553aaf064c06d91d5387937df692e9406ec`），对应 IR SHA-256 为 `563bc1bb817305254806eb1e5102154530166b080c955f7fa0257d0470eee50a`。共享 table fit 不再把连字符、逗号、分号、冒号、右括号或右方括号当成断点，只允许在左括号前及连字符编号后的说明词边界换行；`block_0316` 在原 portrait mask 内以 9pt 判定 `fits=True`，不扩中央列、不横向、不突破字号下限。renderer 与 LayoutPlan 统一消费当前单栏 full-width 合同，不再按 image bbox 二次缩窄复合容器；该组 OOXML 为 outer `tblW=10250 twip`、center grid `4141 twip`、inner table `4140 twip`，内表不再横向溢出并被 crop 遮挡。evidence 为 shape 44/44、semantic table 19/19、heading 33/33、layout table 6（paired visual row 4、visual table composite 2），两个复合 group 的 expected/rendered identity 完全一致；图片片段缺失、意外、顺序错配、校验和错配和阻断项均为 0。相关 layout/converter/renderer 106 tests 通过；LibreOffice 辅助渲染为 43 页，复合区位于第 29、32 页且保持同页、统一比例和可编辑表关系。WPS 最终为 59 页，第 35、39 页两组均同页 portrait，无旧版裁剪断线、大矩形空洞、独立重复表或 crop 遮挡，机械图/表保持同一原生复合关系，数值内容完整，`0.775(19,69)` 只按括号语义边界换行。`MS-001 VARIATION` 在 9pt 固定下限和窄首列中自然多行，按 D7 记录为非阻断客户端排版风险；R-03 已闭环。
- 最终完成门禁已形成可审计矩阵：`.trellis/tasks/08-20-refine-word-generation-rules/research/problem-matrix.md`。R-01～R-09、R-10 治理协议与后续 D8 已完成通用修复和自动回归；SN54AC244 已补齐 R-10 的真实表格/分栏/图片/长文档 external 覆盖，但当前候选被 WPS 视觉门禁否决。在分页缺陷闭环前不能归档任务或把 QUALITY-003 提升为 `enforced-tested`。
- R-04 已闭环：编号标题按深度恢复 H1/H2/H3，未编号 source title 消费 MinerU 顶层或 v2 `content.level`，缺失时安全使用 H2；`chapter/section/part/附录/appendix` 继续保持 H1。首页唯一、顶部、宽幅且可按通用产品标题结构拆分的 source title 改为 `document_identity`，renderer 在翻译后按最终文本动态写入 `part_number/category` 两个原生段落，第一段只与第二段 `keep_with_next`；拆分失败显式终止。该身份不计 Heading/TOC，evidence 分别对账两段可见 payload。
- R-04 定向模块及相关 converter/renderer/translation/text/template/formal-adapter 合计 181 tests 通过。最终 SN54 候选 `/tmp/md2word-r04-final.A1OYcj/sn54ac244-r04.docx`（SHA-256 `67bba0b97ecda1c5166363c30ff5951082535b665812688bcec173fe015007ed`），IR SHA-256 `d89816b3b07f9ca45d6936282b5d9acba3ed4161d8d619a546e593828f525afa`；32/32 Heading，H1/H2/H3=11/19/2，`blocking_quality_flags=[]`。WPS 为 57 页：首页确认身份两段样式，正文抽查 `5`/`5.1`/`8.2.1` 分别为 Heading 1/2/3，完整品类名称全篇仅首页一次，未进入目录缓存。
- SC2167 首次正式重跑暴露 R-02/R-03 顺序交叉回归：`block_0377` table 已与 `block_0376` image 建立唯一包含关系，但旧题注 owner 仍只接受位于表格上方的普通图片组，错误产生 `caption_subject_unresolved`。共同 owner 已改为先裁决唯一表图包含关系，再把 Figure 题注绑定到 image+table 复合主体；关系不唯一仍失败关闭。新增最小回归与既有 caption/contained-table 正反例 4 tests 通过。
- 最终 SC2167 候选 `/tmp/md2word-r04-final.A1OYcj/sc2167-r04.docx`（SHA-256 `d1121fe46ca358e71c8df35e7a0507427770ba33f94b3d2f59930783ae7bd5b5`），IR SHA-256 `9c1995d696c2d2476b40eea2596872891fec77c0ded34d8731bd67847c48ab9e`；首页身份 1 个、51 个无编号 Heading 均为 source level 2，末页“图 23 LQFP48 封装图”绑定 image+table 复合组，`blocking_quality_flags=[]`。WPS 首页身份样式、“产品概况”Heading 2 及末页图题只出现一次并位于复合区之后均通过。
- R-05 已闭环：source→IR 完整性门禁不再以 HTML 字符串非空代替可编辑表体，而是复用正式 HTML table parser；缺失、空或不可解析表体统一产生稳定 blocker `source_ir_integrity:payload_missing:table`，在正式本地/线上发布前失败关闭。renderer 的诊断 fallback 只在 `block.text` 与题注确实不同时输出正文，因此相同题注不再重复；不同的真实 fallback 仍保持可见，但缺少原生表体继续由 `ir_docx_integrity:table_count_mismatch` 阻断。两个最小失败用例及空单元格结构正例均已覆盖，相关 converter/renderer/layout/translation 122 tests 与正式 adapter/worker 3 tests 通过；R-04 最终 SN54/SC2167 IR 的 19/29 张表通过新门禁且 blocker 均为空。本项不改变布局，无需新增 Word/WPS 视觉结论。
- R-06 已闭环：输入发现阶段只允许一个 content-list 结果根，同根仍保持 v2 优先和 legacy fallback；converter 随后把该目录作为 layout、表图关系和图片资产的共同根。多结果根、同根多个同版本 content list、跨根资产和 basename 多候选均不再猜选，分别以显式输入错误或既有 `source_ir_integrity:payload_missing:image` 失败关闭。独立复核另补同根多个 legacy、精确相对路径优先、唯一 basename fallback 和 `..` 越界拒绝回归；converter 39 tests、正式本地 adapter、线上 renderer/完整性入口回归均通过。当前代码用正式入口重跑 SN54/SC2167 单根包，分别得到 38/38 与 24/24 图片资产、19/29 张表且发布门禁通过。该修复只改变输入身份绑定，不改变有效单根包的版式，无需新增 Word/WPS 视觉结论。
- R-07 已闭环：`text_renderer._fill_caption_paragraph()` 对每个可解析的简单 Figure/Table 整数题注写入 `SEQ <label> \\r <source_number> \\* ARABIC`，因此非 1 起始、连续、跳号和重复题注都以源号作为字段更新结果；复合编号继续保留普通文本。独立审查同时修正 `word_renderer._build_render_context()` 的实际字段目标口径：纳入 `standalone_caption`，排除最终按正文渲染的 table context，并使用与最终题注一致的预处理后解析；只有实际生成且 `(kind, number)` 唯一的题注才建立 bookmark/REF。相关 114 tests、release gate 36 targets/224 tests、compileall、Trellis validate 和 `git diff --check` 通过。最小候选 `/tmp/md2word-r07-caption.T0H26E/input/r07-caption-source-numbers.docx`（SHA-256 `cb5a967113d4cb6539a3cbffa6255fa0f22fab73f77276f1ff237cb89e5ce931`）在 WPS 12.1.26055 执行 `Cmd+A`、`F9` 后，Figure 保持 5、6、9、9，Table 保持 3、4、7、7，引用保持 5、9、3、7，复合编号 1.1/2-1 仍为普通文本。LibreOffice 26.2.4.2 辅助重存会删除 `\\r` 并重排为 1～4，确认为客户端差异，不能替代或否定目标 Word/WPS 合同。
- R-08 已闭环：共享 `_OmmlParser` 将合法 `\\tag{...}` 生成同一 OMML 中的可见括号编号，非法 tag 按 MATH-003 整式保留原文本和 residue。WPS 原生样本及最小矩阵确定全空白根因是基础 run 被统一强制为仅含 `m:sty=p` 的 `m:rPr`，不是 Cambria Math 缺失、standalone 包装或 tag 特例。基础 run 因此不再写默认样式；renderer 在创建当前 DOCX 后只从该文档 `word/settings.xml/m:mathFont` 读取一次字体值，并仅给显式 `\\mathrm/\\mathsf/\\text` run 写 `m:sty=p` 与同值 `w:rFonts ascii/hAnsi`，普通变量、tag、显式 b/i 不写具体字体，可选根指数的 nested parser 继承同一上下文。该轮“模板缺失 mathFont 时不猜字体”的临时结论已由下述 D8 合同替代；字体 owner 仍是当前 DOCX settings，不新增生产 config/API/schema。独立 check 在 WPS 12.1.26055 中复核 simple SHA-256 `94ff511a06f56ad1a148a27a4e3fbc0d5012bd865f5bbd04e7ed6ad2bed1156c` 与 complex SHA-256 `1880527cc523c2d65d93f09943a8abbc3df89bab6ac674aafe3c6d287a947134`：standalone、inline、table 三路主体、tag、`ROMAN/SANS/TEXT/IDX/TOTAL` 直立、普通变量与显式 i 斜体、b 粗体、分式、根式和上下标均可见可编辑。R-08 定向 13 tests、renderer/evidence/转换相关 119 tests、同一 renderer 60 次并行隔离及 release gate 227 tests 全部通过。STIX Two Math 与 `p` 的组合在当前 WPS 仍可能空白，按客户端/模板字体兼容边界记录，不由 renderer 硬编码替换字体，也不安装字体或修改 bundled/published 模板。
- D8 已通过独立最终 check：模板已有 `m:mathFont` 时原值不变，缺失或空值时只在当前输出 settings 补 `Cambria Math`，同值绑定当前 `document.part`。表格只预处理 `INLINE_TEX_RE` 命中的简单标识片段，随后仍统一进入 `_fill_paragraph`；`V_{CC}`、`R_{\theta JA}`、`t_{ON}` 和 `I^2C` 复用内联 HTML/run 生成 `w:vertAlign`，其中 `I^2C` 仅 `2` 为上标。`A^2_B`、关系式、多项运算、frac/sqrt/overline/boxed/tag 和嵌套脚本不部分转换，保持共享 OMML/整式可见失败合同。正文同类公式仍为 OMML；表格字体/字号、HTML/术语处理、表头居中和表体左对齐不变，没有第二个 cell writer。
- R-09 已按小范围实现闭环：`resolve_template_config()` 在显式 page size 缺失时读取模板清空正文后保留的末节，将 portrait 短边/长边补入本次最终 `TemplateConfigPackage`；正式 worker、本地转换、LayoutPlan、renderer 和 evidence 共用该实例，避免最终 section 使用非 A4 模板而表格适配仍按 A4 计算。显式配置仍优先，模板路径缺失或无可用 section 尺寸时继续使用产品 A4 默认。18×25 cm 合成模板定向回归、显式配置优先和源 landscape 方向共 3 tests、相关生产文件 `py_compile` 与 `git diff --check` 通过；该变更只改变确定性 `w:pgSz` 和纯计算表格宽度，两个当前真样本均显式 A4，因此未升级到 release gate 或 Word/WPS 视觉复核。
- R-10 首轮治理已按“小范围实现 + 最小证明”落地：component runner 生成并校验绑定当前 commit/dirty 状态、MinerU 包 SHA-256、DOCX SHA-256、Word/WPS 版本和逐项视觉结论的机器可读签字；自动回归状态与人工视觉结论分开，旧 revision、产物不匹配和 LibreOffice-only 记录不会被接受。治理模块 7 tests、`py_compile` 和 `git diff --check` 通过。committed 最小包在 WPS 12.1.26055 为 1 页条件通过；OPA228 P1/P2/P6/P7 正式本地候选 WPS 页数为 2/1/1/2，P6 三表和 P7 宽表可读，P1 双栏与图片清晰但 Device Information 落在稀疏尾页，4 个样本均提示缺失字体。当前哈希、逐项结论和剩余覆盖边界见 `research/r10-visual-governance.md`；未提交生成 DOCX、客户 PDF 或完整 MinerU 产物。
- R-10 代表样本复核改用 external SN54AC244：当前正式候选绑定 MinerU 包 `50883ade...a7c32`、IR `d89816b3...25afa`、DOCX `b684de0c...39892`，覆盖 19 张语义表、19 个原生双栏 section、1 个横向 section、38 个图片资产和 38 页源文档。WPS 12.1.26055 实际为 58 页；首页双栏与右栏表格、横向表格、表图复合、图片清晰度和尾页完整性抽查通过，但第 2 页几乎只承接源首页末尾内容，第 39 页技术标题与第 40 页机械图分离，当前视觉结论为失败。R-10 因而不再缺代表样本，而是暴露 FLOW-001/FLOW-002 的真实分页缺陷；未提交生成 DOCX、客户 PDF、旧 DOCX 或完整 MinerU 产物。
- R-10 两个分页缺陷已按最小范围闭环：页底被保全为正文的页脚候选只有在同时具备明确语义原因、页脚源角色和源页底边位置时才作为 FLOW-001 续接证据；短、纯文本、低于源页 20% 且紧邻 wide 图片的双栏前导安全降级为 `visual_prelude`，普通实质双栏继续使用原生 columns；普通及成对图片按源 bbox/page 相对高度设置只缩不放大的上限。新栏降级 reason 已进入 renderer evidence。两个最小回归加图片高度、双栏和软分组基线共 5 tests、相关文件 `py_compile`、`git diff --check` 通过。最终候选 `/private/tmp/md2word-r10-structural.LfmF16/sn54ac244-r10-structural.docx` SHA-256 `5ddddca139e76b393351c8ba90fd249b89c693b879b63fdc5e4254c9bab720bf` 在 WPS 12.1.26055 为 50 页：第 2 页含声明与 TOC，第 35 页技术标签与机械图同页，首页实质双栏与右栏表格保持。该记录为针对两个失败项的有界 `conditional` 复核，不冒充 50 页逐页签字；生产代码无 SN54/标题/页码特判，未恢复逐源页硬分页。本轮未运行 release gate，未提交、归档或发布。
- 最终候选 release gate 只运行一次并通过：OpenAPI snapshot 为 164 paths/322 schemas 且无变化，frontend API contracts、frontend smoke mock contracts 和 targeted unittest 四阶段全部通过，共 36 targets/235 tests；R-10 的 5 个定向回归包含在完整 renderer target 中。Trellis validate、`git diff --check` 同步通过。门禁未配置独立 lint/type-check，也未启用可选 runtime readiness、Golden preflight 或重复 WPS 全文检查；这些未运行项不改变既有 R-10 有界视觉结论。门禁后只允许文档记录和提交边界整理，不因文档更新重复运行 release gate。
- 提交期 staged whitespace 复核发现未登记 v3 候选 YAML 末尾多一个空行；仅规范化文件结尾，并把候选固定 SHA-256 同步为 `7e279d561688042330dfd8afab12e432df337680ac537df470f4832e577b366e`。`tests.test_template_layout_config_schema` 的 11 个测试随后通过，`git diff --cached --check` 恢复通过。该调整不改变 YAML 数据、manifest/default、renderer 行为或 R-10 DOCX，不重复运行 release gate。
- 独立 check 另闭环了本轮暴露的既有 MATH-002 缺口：`_OmmlParser` 只给数字、运算符和标点写当前 `m:mathFont` 派生的 `p + w:rFonts`，变量仍继承数学斜体，显式 b/i 移除派生字体；无花括号上下标参数改为只消费一个 TeX token。最终 WPS 12.1.26055 候选为 `/tmp/md2word-r08-d8-check.fWWpnl/r08-d8-wps-math-fixed.docx`（SHA-256 `f190610632824fb09437419765247c1342ad92b1f25115f3849c567b0887e35f`）：`V_{OUT}=1`、纯数字分式、根号数字、`x^2+y^2` 与复杂分式/根式/根指数/上下标/粗斜体/直立命令/tag 在 standalone/inline/table 三路完整可见可编辑；简单标识为普通表格文本可编辑，混合 cell 完整。相关 167 tests、正式 worker/admin 3 tests、30 次 custom/missing/empty mathFont 并发隔离、release gate 36 targets/231 tests、compileall、`git diff --check` 和 Trellis validate 全部通过；`blocking_quality_flags=[]`、`latex_residue_count=0`。STIX Two Math 在当前 WPS 的直立兼容边界继续保留，未安装/探测/替换字体，未修改模板、manifest/default/v3、config/API/schema。
