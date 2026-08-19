# CM4112 正式样本验证记录

## 1. 输入与候选

- 验证日期：2026-08-18 至 2026-08-19（Asia/Shanghai）。
- 正式输入目录：`/Users/sc/Downloads/mineru_raw_result 2`。
- `content_list_v2.json` SHA-256：`c4d03c0ba23eaaf653657f8a0a1b687247d0840910d1e0a15a3c32aefd46d22f`。
- 正式入口命令：

  ```bash
  .venv/bin/python scripts/dev/run_local_mineru_conversion.py \
    '/Users/sc/Downloads/mineru_raw_result 2' \
    --output /tmp/md2word-cm4112-structural-fix/cm4112-fixed.docx \
    --translation-mode direct
  ```

- DOCX SHA-256：`baeb48749d06b3537f2f793789b1a52ebff57e38de58fac115eecb87138ad179`。
- DocumentIR SHA-256：`32ef8f04721bc23e055958aa887bd0a7478b1a6a68d3c6e9d2c816815e5dc83c`。
- 该候选来自未提交工作区，只作为本任务 external evidence，不提升为 committed fixture 或长期 Golden 基线。

## 2. 完整性对账

- source pages：21。
- 归一化 source blocks：196；类型为 chart 38、equation_interline 2、image 15、page_footer 20、page_header 41、page_number 19、paragraph 35、table 8、title 18。
- DocumentIR blocks：196；类型为 paragraph 111、image 53、heading 18、table 8、list 4、formula 2；assets 为 53。
- DOCX 结构：53 inline drawings、8 tables、18 heading paragraphs、17 numbering paragraphs、0 LaTeX residue、0 landscape sections。
- renderer expected/actual：drawings 53/53、tables 8/8、headings 18/18，`blocking_quality_flags=[]`。
- layout plan：39 regions，其中 20 个 `one_col`、19 个 `two_col`。首页单侧栏尾并入前一个双栏流，后续严格图片区域保持独立；chart 页使用每个源页一组原生双栏流，没有按每张 chart 重复创建双栏流。

## 3. LibreOffice 已完成边界

- 工具：LibreOffice 26.2.4.2。
- 转换产物：`/tmp/md2word-cm4112-structural-fix/libreoffice/cm4112-fixed.pdf`，23 页 A4 portrait。
- 已逐页查看生成的 PNG/contact sheet：
  - 首页特性/应用/引脚内容和下一页概述可见，概述没有再以半句落到稀疏页；
  - 图表页实际包含曲线图，不是只有题注；
  - 表格和公式可见；
  - “工作原理”从第 15 页开始。
- 未证明：LibreOffice 不能替代 Word/WPS 的最终分页、栏平衡、字段更新和字体回退行为；23 页也不构成与源 PDF 21 页一一相等的合同。

## 4. WPS 已完成边界

- 工具：WPS Office 12.1.26055（build 26055）。
- 为避免同名旧候选干扰，已通过文件选择器明确打开 `/private/tmp/md2word-cm4112-structural-fix/cm4112-fixed.docx`；加载稳定后显示 27 页、3585 字。
- 实际观察范围：
  - 第 1 页应用列表、下一页双栏概述和引脚图可见；
  - 第 7 页表格分行/分块可见，没有把全部表格压成一块；
  - 第 9 页同页三张曲线图实际可见；
  - “工作原理”从第 18 页开始。
- 实际观察到的剩余问题：
  - 第 17 页不是全白页，而是只剩图 33 富文本图注拆出的 `±18V)` 片段，视觉上形成极稀疏页；
  - 含行内公式的富文本图注会拆成多行，例如括号和电压条件与主图注分离；
  - WPS 为 27 页，LibreOffice 为 23 页，存在客户端分页差异。
- 未完成/未宣称：没有继续遍历 WPS 全部 27 页，没有证明每张表、每个公式、每个图注的像素级排版、所有栏平衡或字段更新均通过；因此只记录上述可证明范围，不把 WPS 验收写成整文档通过。

## 5. R1～R4 候选结论与残余风险

- 本任务四项结构合同均有自动证据：chart/source inventory、v2 显式段落语义、单侧栏尾合并、source→IR→layout→DOCX 失败关闭。
- CM4112 当前样本通过确定性内容完整性门禁，38 个 chart 不再丢失；表格、heading 与 drawing 计数一致。
- 视觉层仍有 WPS GUI 的富文本图注孤立行/极稀疏页和客户端页数差异。它们属于 QUALITY-003 的后续视觉治理或既有富文本图注排版问题，不能通过放松完整性门禁或增加型号文字特例规避。

## 6. Checker 的 WPS CLI 补充复核（2026-08-19）

- 工具：同一 WPS 安装包内的 `wpscli 1.1.0`，使用 `word2pdf` 重新排版上述同一 DOCX 候选；输出 PDF SHA-256 为 `9c3318b19575262640f0516004cbf0cd09821ad32cebb39c7bf7c53d6458192b`。
- CLI 输出为 21 页 A4。Checker 查看整本 contact sheet，并按首页/表格/图表/工作原理/封装与订购信息四组放大复核；逐页栅格化后的非白像素检查没有发现全白页。
- 首页的特性、应用、概述和管脚配置标题均可见；概述没有再以半句落到下一稀疏页。第 2 页没有正文文本，但实际包含两组管脚图，属于稀疏图片页而非空白页；第 3 页为稀疏目录页，也不是全白页。这说明只依赖 `pdftotext` 会误报图片页为空白。
- 第 4～7 页的文档历史、绝对最大额定值和电气规格表均可辨认，表格行列保持展开，没有全部挤成一块。第 8～13 页的图 1～图 33 均显示实际曲线；第 14～17 页继续显示图 34～图 40 及正文，不是只剩题注。结合 OOXML 53/53 drawing 对账，可证明 chart/source 内容没有在当前候选中丢失。
- “工作原理”直接位于第 14 页页首，前一页包含图 31～图 33，没有复现 GUI 观察到的标题前空白页。第 18～20 页的封装图与尺寸表、第 21 页的订购信息表均可见。
- 放大复核也确认了既有视觉风险：WPS CLI 字体回退把部分单位/公式字符显示为替换符，富文本图注的括号和电压条件被拆成孤立行；这些不属于本任务四项确定性结构合同的通过证据。
- CLI 与 GUI 对同一 DOCX 分别得到 21 页和 27 页，且 GUI 尚未逐页复核全部 27 页，因此本次补充证据不能把 AC10 或 QUALITY-003 提升为通过。后续 GUI 复核已确认标题前页是图 33 图注片段造成的极稀疏页，不是全白页，也没有证据支持凭此修改 continuous section 规则。

## 7. R6/R7 修复后候选（2026-08-19）

### 7.1 候选与确定性结构

- 正式命令保持不传 template/layout config，输出改为 `/tmp/md2word-cm4112-caption-font-fix/cm4112-fixed.docx`。
- DOCX SHA-256：`7d4f1bc5f3666cf1c528aad431e6c07e99a01a5cfb093d3786287ae501215c49`；DocumentIR SHA-256：`0dc8b717a450f61375b69bbdc5d10892401d0c496ca81e56d0c136e6b0eb3350`。
- source/IR blocks 为 196/196；chart/image 为 38/15，IR image 为 53；drawings 53/53、tables 8/8、headings 18/18，`blocking_quality_flags=[]`。
- `block_0097.captions=['图 33 通道隔离度 (± 18V)']`；DOCX 中不存在文本仅为 `±`、`18V)` 或 `± 18V)` 的段落。
- 666/666 个含可见 `w:t` 的 Word run 都写入 `eastAsia=宋体`、`ascii/hAnsi=Arial`、`cs=Times New Roman`；OMML run 不写段落字体槽，继续由 `m:mathFont` 控制。

### 7.2 LibreOffice 与 WPS CLI

- LibreOffice 26.2.4.2 输出 `/tmp/md2word-cm4112-caption-font-fix/libreoffice/cm4112-fixed.pdf`，SHA-256 `c5ec778d8c542afa3f307d7ffc7a77ac58ce4d0d4fb952219478e46d88781e7d`，23 页 A4，无纯文本空页；图 33 在第 14 页，“工作原理”直接从第 15 页开始。
- WPS CLI 1.1.0 因 macOS 权限拒读 `/tmp`，因此把同一 DOCX hash 的副本放到 `/Users/sc/Downloads/md2word-cm4112-caption-font-fix/cm4112-fixed.docx`。输出 PDF SHA-256 `08e0760a539dbd62569d26ad877f8ba98461d984f746380b3c0fa1b49691b3fc`，20 页 A4，无纯文本空页；图 33 在第 12 页，“工作原理”直接从第 13 页开始。
- WPS CLI 输出仍把部分单位和公式字符显示为替换符；这与本机缺少精确 `宋体`/`Cambria Math` 的环境边界一致，不能通过改写已发布配置字体名掩盖。

### 7.3 WPS GUI 关键页复核

- 工具：WPS Office 12.1.26055（build 26055）。通过 WPS 文件选择器进入 Downloads 独立目录并打开上述同 hash 副本，排版稳定后为 20 页、3374 字。
- 查找“图 33 通道隔离度”并缩放到 50% 查看完整页面：第 12 页包含图 31、图 32、图 33 三张曲线图及完整题注，不存在旧候选只剩 `±/18V)` 碎片的极稀疏页；下一页直接以“工作原理”起页。检查后已恢复 100% 缩放。
- 查找并选中“工作原理”时，字体框显示“宋体”，证明 WPS 读取到 OOXML 请求字体；状态栏同时显示“缺失字体”，说明当前机器仍在做客户端字体替换。
- 未完成：未逐页放大复核 WPS GUI 全部 20 页，故 AC10 与 QUALITY-003 仍不提升；本节只证明 R6 受影响页和 R7 请求字体/缺失字体边界。

### 7.4 自动门禁

- R6/R7 相关五模块共 118 项测试通过；`compileall` 与 `git diff --check` 通过。
- `task.py validate .trellis/tasks/08-18-fix-formal-word-structural-regressions` 通过，`implement.jsonl` 8 条、`check.jsonl` 10 条均有效。
- 追加实现后的 `scripts/ops/check_release.py` 通过：OpenAPI、frontend contract、frontend smoke mock 与 36 个 targeted unittest 目标组均通过，共运行 202 项测试。
