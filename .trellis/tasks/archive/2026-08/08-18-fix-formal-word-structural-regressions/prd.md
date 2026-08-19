# 修复正式 Word 链路结构性回退

## Goal

修复正式 `MinerUToDocumentIRService → DocumentIRWordRenderer` 链路中会造成整类内容丢失、正文语义误判、双栏分页失真、富文本题注拆段和样式配置失效的共同根因，并建立可自动阻止同类回退的内容完整性与样式证据，使后续适配新 PDF 时不能以局部测试通过掩盖整文档质量下降。

## Background and Confirmed Facts

1. CM4112/CM4114 的 MinerU v2 输入共 21 页、196 个 block，其中 `chart=38`、`image=15`；38 个 chart 使用嵌套 `content.image_source.path`。当前 DocumentIR 只有 15 个 image block/asset，新 DOCX 也只有 15 个媒体文件。
2. `app/services/document_ir/mineru_converter.py::_map_block_type` 只把 `image/figure` 或顶层 `img_path/image_path` 映射为 image，没有声明 `chart → image`。共享 `extract_first_asset_path()` 已能读取嵌套 `image_source.path`，因此不需要新增资产解析器。
3. 现有 chart 自动测试使用顶层 `img_path`，会绕过缺失的 v2 chart 类型契约；IR 最终只留下一个 `unsupported_block_type:chart`，正式本地和线上流程均不会因此失败。
4. `app/conversion/docx_rules/text_semantics.py::HEADING_NUMBER_RE` 将 `图/表/Figure/Table + 编号` 视为 heading-like；`text_renderer.py::_fill_auto_list_or_paragraph` 又会把所有命中的 paragraph 升级为 Word heading。实测“图 1 ……”图注和“图 13 显示了……”正文说明都返回 heading。
5. CM4112 首页当前 layout plan 为 `one_col(1) → two_col(7) → one_col(5) → two_col(2)`。中间 5 个 block 全是左栏的“应用/管脚配置”延续，不是真正 wide 内容；最后 2 个 block 是严格成对图片。当前 renderer 对每个普通 two-col region 各创建一次进入和恢复 continuous section，整本文档生成 33 个 section。
6. `chart` 修复为 image 后，严格成对图表页可复用现有 COL-003 制表位路径并消除大量 continuous section；首页仍需让“单侧栏尾”留在同一语义双栏流中，同时保留真正 wide block 和真实单栏间隙。
7. `app/services/renderer/evidence.py` 当前只汇总 layout 数量和 DOCX 自身 OOXML 指标；没有对账 `metadata.source_type → IR type/asset`、IR body block → layout plan、IR image/table/heading → DOCX drawing/table/heading。
8. 本地正式适配器在计算 renderer evidence 前已经写出 DOCX；线上 document job 即使存在 `layout_quality_flags` 或 `quality_flags` 仍会进入 uploading/completed。用户已裁决：确定性内容丢失必须失败关闭，普通视觉/人工风险继续保持非阻断。
9. 原 PDF 是视觉权威基线。旧 DOCX 本身是 18 页横向输出，只能证明历史链路曾保留 53 个视觉对象，不能作为版式验收基线。
10. CM4112 v2 的 38 个 `chart_caption` 中，34 个是单条题注内部的 `text/equation_inline/text` 富文本节点数组；当前 converter 将每个节点拍平成一个 `DocumentIRBlock.captions` 元素，image renderer 再把每个元素写成独立 `w:p`。图 33 因而成为“主题注 / `±` / `18V)`”三段，并在 WPS GUI 形成标题前极稀疏页。
11. 当前正式样本命令没有传 `--layout-config`。本地 formal adapter 将 `None` 原样传给 `TemplateConfigPackage.load(None)`，得到全部字体字段为空的配置；候选 DOCX 主体除两个 Courier run 外没有配置字体名，主要依赖 Office theme。线上 document job 仍从已固化 Template Version 传入 layout config，不受这个本地缺省绑定缺口影响。
12. 当前内置 v2 配置已经为正文、标题、题注和表格声明 `font_name=宋体`、`western_font_name=Arial`、`complex_script_font_name=Times New Roman`。配置字体是否安装仍由打开 DOCX 的目标系统负责；本任务只保证正式入口选择正确配置且 OOXML 写入正确字体槽，不伪造字体安装状态。

## Requirements

### R1 — 明确 v2 chart 类型契约

1. MinerU `chart` 与 `image/figure` 一样，必须转换为 DocumentIR `image`，复用现有嵌套资产路径、caption、footnote、bbox、column hint 和严格图注重关联逻辑。
2. 具有合法嵌套 `content.image_source.path` 的 chart 必须生成 `asset_ref`、`DocumentIRAsset` 和 `MinerUImageAsset`；不得降级为 paragraph，也不得产生 `unsupported_block_type:chart`。
3. chart 声明了视觉资产但路径缺失、越界或不可读时必须留下确定性内容完整性错误，不得静默只保留图注。
4. 类型契约必须用真实 v2 形状测试；顶层 `img_path` 兼容测试不能作为唯一证据。

### R2 — 显式 IR 语义优先，禁止 v2 paragraph 猜成 heading

1. `document-ir/v2` 的显式 block type 是正式语义真相：heading 只由 IR `heading` 渲染为 Word heading；paragraph 不再仅凭文本前缀升级为 heading。
2. `图/表/Figure/Table + 编号` 的图注或正文引用句不得成为 heading，不得进入自动目录。
3. v2 的显式 list、TOC 识别和 bullet-like paragraph 原生列表行为继续保留；本任务不放松列表与目录合同。
4. `document-ir/v1` 的顺序兼容路径可保留现有 heading-like 推断，避免未经授权破坏正式 v1 兼容合同；该兼容不能泄漏到 v2。
5. DOCX 质量分析使用与正式文本语义一致的 caption/heading 排除规则，不再维护相反判断。

### R3 — 收敛 continuous section 双栏流

1. 普通正文继续使用 Word 原生栏，不恢复 legacy 1×2 布局表格。
2. 一个有边界的语义双栏正文流最多创建一次进入 two-column 和一次恢复 one-column 的 continuous section；不能仅因一栏先结束而在同一流中反复切换。
3. 紧随真实左右重叠区、只属于同一侧栏的尾部 block，应在遇到真正 wide block、严格成对图片区或后续新的左右重叠区之前并入前一双栏流。
4. 真正 wide block、明确单栏间隙和无法严格配对的图片区继续遵守 COL-001/COL-002；严格成对图片继续走现有无 section 的 COL-003 制表位路径。
5. 保持左栏自上而下、再右栏自上而下的正文阅读顺序；严格图片对保持逐行左→右顺序。
6. 不按 CM4112 文本、页码、型号或固定 bbox 数值写特例。

### R4 — 建立两段源数据完整性质量门禁

1. converter 在允许的过滤/续表归一化后，把 source block 总数和按 source type 计数写入向后兼容的 DocumentIR metadata inventory；再使用每个主 block 现有的 `metadata.source_type` 校验已声明结构类型的映射和必要 payload。至少覆盖 chart/image/figure、table、formula、heading 和 list；不新增第二套原始 JSON parser 或内容源。
2. IR→layout/DOCX 边界对账：
   - 所有可见 body block 都进入 layout plan，不能因缺页索引静默丢失；
   - 可渲染 image block 数与 DOCX inline drawing 数一致；
   - 可渲染 table block 数与 DOCX table 数一致；
   - v2 显式 heading 数与 DOCX heading 段落数一致。
3. evidence 必须同时记录 expected、actual、差值和稳定 flag，便于本地 CLI、线上 artifact/event 和测试复用。
4. 只有确定性结构/内容丢失进入阻断集合；LaTeX residue、实际分页、栏平衡、图片清晰度等现有人工复核风险不因本任务自动升级为致命错误。
5. 本地正式适配器必须先完成 evidence/门禁再发布最终 DOCX；线上流程必须在上传和 completed 之前执行同一门禁。
6. MinerU→IR 的阻断错误在本地不发布最终 DOCX、在线上使任务以 `failed_stage=ir_converting`、`error_code=document_ir_failed` 失败；IR→DOCX 的阻断错误在线上以 `failed_stage=rendering`、`error_code=render_failed` 失败。
7. 门禁失败必须保留明确中文错误消息、稳定机器标识和 expected/actual 证据，不能吞异常或返回伪成功；普通 LaTeX residue、分页、栏平衡、图片清晰度等风险仍按现有人工复核流程处理。

### R5 — 规则、测试与真样本共同更新

1. 更新 `.trellis/spec/backend/word-generation-rules.md` 中 IR/IMAGE/TEXT/COL/QUALITY 对应规则、冲突矩阵和回归矩阵；旧 runtime 仍只作为历史证据。
2. 新增最小正式链路回归，组合覆盖嵌套 v2 chart、图注/正文引用、显式标题、单侧栏尾、严格图片对和完整性 evidence。
3. 使用正式入口重新生成 CM4112/CM4114；结构检查和 LibreOffice 渲染用于自动/辅助证据，最终双栏、首页和字段行为使用本机 WPS 复核并记录版本/输出。

### R6 — 富文本题注保持一个逻辑段落

1. v2 caption 字段中的一组扁平 inline node（如 `text/equation_inline/text`）表示一条逻辑题注，进入 DocumentIR 时必须合并为一个 `captions` 元素；不得把行内节点解释成多条题注。
2. legacy string list 和外层包含多个 rich-node group 的结构继续表示多条独立题注；不得为了修复 CM4112 而把所有 caption 无条件合并。
3. 合并后的题注必须保留可见公式/上下标、SEQ/bookmark、fallback 文本和 table caption/context 判断；一个 `captions` 元素继续对应一个 Word 题注段落。
4. 规则只使用输入结构，不按图号、型号、页码、标点文本或 bbox 写特例；不修改 continuous section 或标题分页规则来掩盖题注拆段。

### R7 — 正式入口必须绑定有效字体配置

1. 本地正式 CLI/adapter 未显式传资源路径时，必须使用 `Settings.default_template_path` 和 `Settings.layout_config_path` 指向的当前内置模板/v2 配置；显式路径继续优先且缺失/非法时失败关闭。
2. `--no-template` 只禁用基础 DOCX 模板，不禁用 layout config；renderer 低层 `template_path=None/config_path=None` 的无模板/空配置语义保持不变，避免把入口默认选择复制到 renderer。
3. 在线 document job 继续只消费任务创建时固化的 Template Version 配置，不回退到本地 bundled 路径，也不改变模板版本治理合同。
4. 生成的正文、标题、题注、表格及现有页眉页脚中的可见 Word 文本必须继续通过唯一 `apply_run_fonts()` 写入 `eastAsia/ascii/hAnsi/cs` 槽；OMML 公式继续由 DOCX `m:mathFont` 独立控制。本任务不捆绑、安装或替换系统字体。

## Acceptance Criteria

- [x] AC1：真实 v2 形状的 chart 被转换为带 `asset_ref` 的 image；caption/footnote/inline formula 保留，且没有 `unsupported_block_type:chart`。
- [x] AC2：CM4112 正式输出包含全部 38 个 chart 和 15 个 image 对应的 53 个 drawing；图表页不再只剩图注。
- [x] AC3：v2 paragraph“图 13 显示了……”和编号图注不使用 Heading 样式；显式“工作原理”等 IR heading 仍使用 Heading 样式并保持既有语义起页。
- [x] AC4：v1 heading-like 兼容、v2 原生列表、TOC 单字段和显式 heading 现有行为均有回归保护。
- [x] AC5：合成“左右重叠 + 单侧栏尾 + 严格图片对”页面只为普通正文流生成一组 two-column enter/restore section；图片对不新增 section，wide/真实单栏间隙不被吞并。
- [x] AC6：CM4112 首页不再把概述最后一句拆到新增空疏页面；“应用/管脚配置”保持在正确栏流，图表密集页没有连续分节导致的逐图拆页。
- [x] AC7：DocumentIR 保存归一化后的 source inventory，完整性 evidence 能分别报告 source→IR、IR→layout、IR→DOCX 的 expected/actual；故意丢一个 chart、body block、drawing 或 table 的测试会触发稳定阻断 flag。
- [x] AC8：正式本地入口在阻断 flag 存在时不发布最终 DOCX；线上 document job 分别以 `document_ir_failed`/`render_failed` 失败；非阻断质量 flag 仍保留现有人工复核语义。
- [x] AC9：相关 converter、renderer、正式 adapter、document job 测试通过；`compileall`、`git diff --check` 和项目 release check 通过。
- [ ] AC10：CM4112 使用 LibreOffice 与 WPS 完成整文档复核，记录页数、首页、图表页、工作原理起页、表格页、空白页和 section/drawing/table/heading 结构证据；不得只以“可打开”或局部单测判定通过。
- [x] AC11：真实 v2 `text/equation_inline/text` chart caption 在 IR 中只有一个完整 `captions` 元素；字符串列表和两个嵌套 rich groups 仍保持两条独立题注。
- [x] AC12：DOCX 中图 33 的主题注、`±` 和 `18V)` 位于同一个题注段落，保留 SEQ/bookmark 和可见 inline 语义；不存在文本仅为 `±` 或 `18V)` 的孤立题注段落。
- [x] AC13：不传模板/config 的本地正式命令实际加载当前默认 DOCX 与 `datasheet_template_v2.yaml`，CM4112 DOCX 的正文、标题、题注和表格可见 Word run 写入配置的四类字体槽；显式路径、`--no-template`、OMML 数学字体独立性和线上固化版本行为均有回归保护。
- [x] AC14：新候选保持 196/196 blocks、53/53 drawings、8/8 tables、18/18 headings 且阻断标记为空；WPS GUI 复核确认不再出现由图 33 碎片造成的极稀疏页，并记录字体缺失时的客户端替换边界。

## Out of Scope

- 不修复本轮清单中的页眉页脚开关、TOC 客户端占位、SEQ 38→1/40→2、封装内容组分页、五列表格列宽等其他问题。
- 不扩展公式 TeX/OMML 支持范围；只保护现有公式回归。
- 不恢复或改造 `app/conversion/runtime/*` 的旧 Word writer/page runtime。
- 不引入 PDF 像素级复刻、固定页数相等、按型号规则、第三方版式引擎或新的渲染依赖。
- 不把所有现有 `quality_flags` 自动升级为阻断错误。
- 不安装、内嵌或下载宋体/Arial/Times New Roman，也不承诺未安装字体时各客户端像素级一致。
- 不把多条真实题注/脚注合并成一条，不为未来未证实的任意 rich caption schema 改造 DocumentIR 类型。

## Key Decision

- 采用失败关闭。确定性 MinerU→IR 内容丢失阻断 `ir_converting`，确定性 IR→layout/DOCX 内容丢失阻断 `rendering`；非确定性的视觉风险和现有人工复核 flag 不阻断任务。
- 富文本题注按源数组结构确定逻辑分组，唯一修复点在 converter；不在 renderer 或 section 层猜测性拼接。
- 本地正式入口省略资源参数时使用 Settings 当前默认模板/v2 配置；在线上继续以固化 Template Version 为唯一来源。字体安装与 OMML 数学字体保持独立边界。
