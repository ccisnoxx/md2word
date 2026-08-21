# 当前 Word 生成链路与样本审计

## 审计边界

- 日期：2026-08-20（Asia/Shanghai）。
- 正式链路：`MinerUToDocumentIRService → DocumentIRWordRenderer`；`full.md` 和旧 runtime 不作为正式输入或并列 writer。
- 外部样本仅用于本任务规划与人工验收，不提交用户原始 PDF、DOCX 或 MinerU 产物。
- 本记录只陈述已读取的代码、结构数据和已渲染页面；没有观察到的 Word/WPS 行为不写成通过。

## 正式数据流

1. 本地入口 `scripts/dev/formal_mineru_conversion.py:117-219` 解析模板、样式与翻译请求，调用 converter、translator、renderer，再在写出最终文件前执行 evidence 与失败关闭。
2. 线上入口 `app/domains/document_jobs/execution.py:771-799,2177-2290` 下载 MinerU ZIP，持久化 DocumentIR，解析固化 Template Version，生成 DOCX 并通过完整性门禁后登记结果文件。
3. `app/services/document_ir/mineru_package.py:22-67` 选择 v2 content list 并补齐嵌套页的 `page_idx`。
4. `app/services/document_ir/mineru_converter.py:98-239` 完成尾页过滤、图片题注重关联、空表续页归一化、IR block/asset 构建和 source→IR 对账。
5. `app/services/renderer/layout_plan.py:39-200` 把 IR 页面转换成单栏/双栏 region；`app/services/renderer/word_renderer.py:55-103,325-583` 生成 Word 原生块、分节和分栏。
6. `app/services/document_ir/integrity.py` 与 `app/services/renderer/evidence.py` 分别负责 source→IR 和 IR→layout/DOCX 的阻断证据；`app/services/renderer/docx_quality.py` 只提供结构指标与非阻断风险。

## `sn54ac244` 输入与当前产物

- MinerU v2 共 38 个物理页、421 个源块；现有空续表归一化后为 420 个主源块。
- 原始类型包括 119 个 `page_header`、55 个 `page_footer`、10 个 `page_number`、24 个 `page_footnote`、35 个 image、3 个 chart、20 个 raw table 和 43 个 title。
- 当前 IR/DOCX 为 38 个图片、19 张表、43 个标题；这些计数相等仍不能证明正文、题注、脚注、图片身份或页面语境正确。
- 物理第 38 页的 8 个法律免责声明块全部被 MinerU 标成 `page_header`。当前 layout plan 排除非 body，页面没有正文 region；DOCX 不包含 `IMPORTANT NOTICE AND DISCLAIMER` 等正文，而 38/38 图片、19/19 表格、43/43 标题计数仍通过。
- 24 个 `page_footnote` 当前不在角色和类型映射中，降级为普通正文并产生非阻断 `unsupported_block_type:page_footnote`；Material type、RoHS 和机械尺寸 NOTES 没有明确 note 语义及内容组绑定。
- 原 PDF 第 10 页的两条修订范围行被 MinerU 标成二级 title；它们实际是修订列表的局部分组表头，不应进入 Word 导航或 TOC。
- 当前中文 DOCX 的正文已翻译，但 Figure/Table 题注和表注仍有英文。`document_ir_translator.py:435-550` 只处理 `block.text`、列表项和 table HTML，没有 captions/footnotes target。
- 当前 DOCX 保留 4 个 `\,` TeX 间距命令；`text_renderer.py:130-139,535-580` 无法解析反斜杠后标点并回退可见文本，`docx_quality.py:22-24` 又只匹配反斜杠后的字母命令，导致 `latex_residue_count=0`。

## 首页双栏与表格根因

- 原 PDF 首页是明确双栏：左栏为 Features/Applications，右栏为 Description/Device Information；底部两张逻辑图构成严格视觉配对行。
- MinerU 首页 `Device Information` 表格 bbox 为 `[511,239,906,402]`，完整位于约 1000 宽页面的右栏。
- `layout_plan.py:86-107` 只有当块的纵向中心点位于左右重叠 band 时才把块放入双栏。该表格虽与左栏 Applications 尾部有实际重叠，但中心点落在 band 外，因此被错误生成为单栏全宽 region。
- renderer 按 region 顺序写出后，表格插入 Applications 第一项与其余列表项之间；错误来源是容器归属，不是该表格本身的四列结构。
- `table_renderer.py:181-205,369-389` 另有独立问题：六列以上直接等宽，并把配置字号压到 8pt/7pt。缩字可以是窄栏适配手段，但触发条件必须是最终内容在正确容器中的实际适配结果，且受配置最小字号约束，不能由列数决定。

## `SC2167` 标题证据

- `SC2167.pdf` 没有 PDF outline，真实章节大量不带编号，例如“产品概况”“产品特色”“技术规格”“寄存器映射”“串行接口”和“应用推荐”。编号或 outline 不能作为标题必要条件。
- 当前 `SC2167.docx` 同时把完整编号说明句、故障清除步骤、`图 12 ……` 等图题以及描述图题的正文句生成为 Heading。编号也不能作为充分条件。
- 因此标题必须采用非对称裁决：源 `title` 默认保留；只有图题、列表项、修订分组或页装饰等竞争角色有明确证据时才降级；普通正文晋升标题则需要额外结构证据。

## 当前质量门禁盲区

- `integrity.py:76-98` 只严查 visual/table/formula/title/list 的类型和核心 payload；非 body decoration、`page_footnote`、captions 和 footnotes 没有完整去向合同。
- `evidence.py:18-87` 只对 visible body block id、drawing/table/heading 数量做阻断对账；正文逐字覆盖、题注/脚注、TOC 功能结果、公式 OMML、图片身份、页数、空白页和栏平衡没有确定性门禁。
- `docx_quality.py` 的风险标记不阻断发布；结构指标不能替代 Word/WPS 的分页、分栏、表格挤压和清晰度验收。

## 规划结论

- 一个文档级语义归一化 owner 必须在 IR 建立前裁决源类型、竞争角色和明确去向；renderer 只消费归一化结果。
- layout plan 必须先建立页面拓扑与块容器，再由 table/image/text renderer 在容器内工作；块类型不得反向改变栏归属。
- 模板样式拥有首选字号；表格适配可以在显式最小字号内缩小，达到下限后才按单栏全宽、横向节顺序安全降级。
- 完整性门禁必须同时覆盖内容去向、最终可见文本和结构身份；只有 Word/WPS 人工验收可以判定最终视觉质量。
