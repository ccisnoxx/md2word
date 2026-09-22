# 当前候选验证记录

## 范围与实现

- 基线：`a1088a302f4d054f0e51b7ff2e181a93109e7e81`，本任务为 dirty 候选，未提交、未部署、未重试线上任务。
- converter：同页唯一缺题图片、唯一错挂图题和前后连续编号共同证明时恢复归属；多行多列表格保持 HTML 和可编辑语义。跨栏不按全局 y 轴猜最近邻。
- integrity/evidence：题注/表图关系未决时保全原内容并输出 review_issues；内容缺失、资产错配和裁剪合同损坏仍阻断。
- generated_word 元数据 → files API 四字段白名单 → 任务详情源页复核列表。只显示当前结果文件的问题，不改下载权限。
- 本地正式入口附带 `.review.json`，与线上共享同一质量裁决。

## 自动验证

- 完整后端 `unittest discover -s tests -q`：692 项，6 failures + 7 errors，未通过。日志 `/tmp/md2word-caption-regression.log`。
- 将 HEAD 导出到隔离临时目录后执行基线全量：689 项，6 failures + 10 errors。当前 13 项失败均在基线同名测试同原因复现；基线额外 3 个错误来自归档目录无 Git 元数据、缺少未跟踪 PyCharm 配置。日志 `/tmp/md2word-caption-baseline.log`。
- 既有失败包括 callback 测试任务创建前提、translation fan-in 断言、模板 source_path 断言、旧 inline equation 期望、术语配置测试读取到 Python 内容。没有为本任务修改这些不相关模块。
- 受影响 converter/layout contract/renderer/local adapter/component governance/golden manifest：181 项通过。随后新增本地 review sidecar 成功/阻断用例：2 项通过（其中阻断例为既有例重验）。
- 新增后端任务 warning 持久化、API 白名单（拒绝 bool/0 页码与额外字段）、成功下载端到端：通过。既有 source 与 renderer fatal 发布阻断用例通过。
- 前端 130 unit tests 通过；vue-tsc + Vite build 通过，保留现有 bundle size 和第三方 PURE 注释警告。
- OpenAPI snapshot、frontend contract、smoke mock contract：通过。
- Chrome Playwright：现有登录/任务/下载流程与新增 warning→诊断→下载流程，共 2 项通过。初次测试使用了不存在的页签名，修正为实际“诊断”后通过，非产品缺陷。
- 新 warning 在 1440×960 与 375×960 验证，页面无横向溢出，未捕获 pageerror；截图 `/tmp/md2word-review-warning-1440.png`、`/tmp/md2word-review-warning-375.png`。Browser plugin 未列出，使用项目已有 Playwright 工作流。
- `git diff --check` 通过。

## 真实样本（external evidence）

输入：用户提供的 `/Users/sc/Downloads/mineru_raw_result_CM1348`，正式读取 content_list_v2.json；full.md 不是原始 PDF。未提交客户原文或图片。

- v2 JSON SHA256：`cd1b07339761197db4256d299d1b502d70681cb781e90a5af4a69fd143f05d50`。
- 结果：`/Users/sc/Downloads/CM1348-caption-review/result.docx`。
- DOCX SHA256：`2f5e2abb5e96efdb8efa19b926f65107f85df6d5c528fdcecfbfe52510b2afe0`。
- 复核报告：同目录 `result.review.json`，源 PDF 第 21 页 block_0227、第 25 页 block_0318 自动恢复题注；保持原 table 块而非图片化。
- 558/558 主源块，33 张语义表格；可见 payload：heading 77/77、paragraph 333/333、list item 2/2、table cell 1430/1430、annotation 86/86、formula 14/14。
- source→IR 与 IR→DOCX blocking flags 均为空。
- 非阻断风险仍有 `docx_latex_residue:14`、`docx_unstyled_heading_candidates:13`；不能宣称整文档版式或公式质量全部通过。
- committed 最小 component OPA228 包通过正式入口：1/1，输出同目录 component-regression；不冒充四个 Golden PDF 的当前视觉回归。

## 独立复核与剩余门禁

fresh critical_reviewer 只读审查候选，未确认阻断缺陷，独立内存反例验证拒绝歧义关联与正确 equation_inline 数学边界保全。建议的测试缺口已修复：使用实际 v2 equation_inline，断言 `$V_{IN}$` 和 DOCX OMML。

WPS 客户端已识别并尝试打开本次产物，但文件选择/访达操作连续遭遇剪贴板超时或 application changed，未确认打开目标 DOCX。没有当前候选 Word/WPS 逐页视觉签字；不能把结构证据或前端截图替代 QUALITY-003 客户端视觉门禁。完整 closure 尚未通过（既有后端失败＋视觉门禁缺口）。下一步是打开 Word 检查源 21/25 页对应内容及全篇分页/图片/表格；上线需另行授权。

## 2026-09-20 版式负优化复盘与修订候选

用户指出 `result.docx` 相对同品牌既有 `CM4112,CM4114数据手册_V1.1(1).docx` 视觉显著退步。该文件只有生成 DOCX，未提供其 MinerU 原包，故只能作为已生成文档的横向排版参照，不能据此重跑同输入 A/B。`result.docx` 已被后续候选取代，不能作为可发布成果。

- 诊断：源 CM1348 PDF 为 37 页纵向；旧 `result.docx` 用 WPS 12.1.28492 转 PDF 为 67 页，LibreOffice 为 59 页。禁用新图题恢复的消融仍有 56 页（LibreOffice），说明大量问题属于既有纵向版式路径，不是四个图题块单独造成。
- 根因一：MinerU bbox 与 layout 页高纵向缩放不一致，重复页脚落在推算页高的约 72%，旧阈值 75% 将其当正文；仅含已合并续表后的页眉页脚的源页又被强制提升为正文，产生无意义分页和双栏。当前语义裁决容忍少量位置离群，但只对稳定位置簇中的实例认定跨页装饰；大图旁标签和孤立短页脚优先保全。
- 根因二：默认模板页眉以 144 个空格加 `distribute` 对齐尾部标题。WPS 纵向页把“数据手册”分散成多行，挤走首页架构图；横向 CM4112 未触发。当前只在已知纵向页、且确有长空格分散页眉时，将空白 `w:t` 换成右边距定位 tab，不修改同 run 的 drawing/关系。
- 最终本地候选：`/Users/sc/Downloads/CM1348-caption-review/revised-v2.docx`（SHA256 `e070169f103f64c6ba9fe4cdea54cf967bcd6a4c47f1833432878d858d2f8a38`），WPS PDF `visual-validation/revised-v2-wps.pdf`（SHA256 `745c7e48fa9f9e549d15a162659fec452d07a71f65dcd7f97b71ce2a9b720006`）；WPS 58 页，首页架构图与文字同页，源第 4 页的管脚图和可编辑表格在生成第 6 页可见。旧候选 WPS 为 67 页，同品牌 CM4112 DOCX WPS 为 18 页横向。页数并不要求与源 PDF 相同，但差值仍较大。
- 实际视觉抽查：WPS 第 1、6、27、58 页；第 1 页无分散页眉且架构图回首页，第 6 页管脚表可读，第 58 页订购表可见。第 27 页仍有公式残留 TeX/乱码和双栏拥挤；目录由源 1 页扩至 Word 3 页。该候选只关闭已证实的页眉页脚污染与页眉挤压，不构成整文档版式放行或完整质量签字。未改写显式模板字号与边距，避免把横向已可用文档再次污染。
- 独立二次只读复核确认首轮三项内容保全反例均已关闭，未发现新增阻断缺陷。纯横向文档的模板页眉不变；混合方向文档若继承同一 header part，横向节也会应用长空格→tab 调整，尚无 WPS/Word 混合方向视觉签字。
- 最终候选完整后端：696 项，6 failures + 7 errors；13 项名称与隔离 HEAD 基线同名，基线额外 3 项为隔离环境差异。日志 `/tmp/md2word-layout-full-tests.log`。本轮新增的边缘重复、主体标签、孤立短页脚和同 run logo 测试均通过；`git diff --check` 通过。

## 2026-09-21 双栏与数学残留复核（未放行）

- 同输入旧 `result.docx` 的 WPS 第 35 页已经有双栏跨栏重叠和 ENOB 原始 TeX；`revised-v2.docx` 对应第 27 页仍有。两版源第 21 页的 23 个块相同，差别仅是 3 个页眉/页脚角色，不支持“当天正文改动才把双栏挤坏”的结论。
- 权威根因之一是默认 DOCX 模板单栏 `w:cols/@w:space=0`，渲染器进入双栏只写栏数并继承该零栏距。仓库 `e91d8e6c`（2026-08-24）将 bundled template 的原 720 改为 0；用户提供的既有 CM4112 DOCX 的双栏节为 720。只在诊断副本把 24 个双栏节设为 360 或 720，WPS 源第 21 页对应区域即不再跨栏，页数 58→59。正式修复只替换空/零栏距，保留非零模板值。
- CM1348 独立公式 14 个中，补齐数学入口的函数、希腊符号和转义下划线后有 13 个进入可编辑 OMML；源第 26 页 `array` 仍是明确不支持的可见回退。普通正文中同名 Windows/UNC 路径必须保真；独立复核曾发现把新命令加入共享控制词表会破坏路径，已撤回，并以正文、表格、题注三路测试锁定。
- 当前本地候选 `/Users/sc/Downloads/CM1348-caption-review/revised-v6.docx` SHA-256 `1b8183143fd35e0b2f8203b0d8599af0738300c1a0e94eb54ab834bc0b28085b`；WPS 12.1.28492 PDF `/Users/sc/Downloads/CM1348-caption-review/visual-validation/revised-v6-wps.pdf` SHA-256 `53c3c1a1fb98c1e7164be5fd6b280d9a3b443e0878fe0619e9e6c227934c6724`，59 页。源第 21 页对应 WPS 第 28 页双栏不再重叠、ENOB 分式可见；第 1 页和末页 59 抽查，图/表仍可见。
- 未关闭：WPS 第 28 页 `V_REF = AVDD - AVSS` 内联 OMML 变量仍成为黑菱形；第 1 页 `Δ\\Sigma` 也可见替换字形。IR/DOCX 文本正确、LibreOffice 同段清晰，指向当前 WPS 数学字形/导出兼容边界；全局替换数学字体的诊断副本未解决，不能上线。质量摘要从 v2 的 `docx_latex_residue:14` 到 v6 的 `:8`，仍含 TOC 缓存、普通文本及不支持环境；当前 `.review.json` 尚不能逐源页列出这些数学问题。
- 受影响 renderer + golden 108 项通过；完整后端 699 项为 6 failures + 7 errors，名称与前述已知基线相同，日志 `/tmp/md2word-layout-compare.oASUWi/final2-unittest.log`；`git diff --check` 通过。这不是完整 QUALITY-003 签字：未做逐页 Word/WPS 全篇验收，也未部署或重试线上任务。

## 2026-09-21 双栏跨页空白与默认栏距修订候选（未放行）

- `revised-v6.docx` 的 WPS 第 27 页下半页留白，DOCX OOXML 对下一源页的首个双图表格设置了 `w:pageBreakBefore`；仅去掉该处断页的诊断副本即能让图 34/36 填入当页下半部。不是可删除的空格，也不是单靠调大栏距能解决；客户端页码与用户 Word 的 26/27 页可能不同。
- 当前布局规划只在上一源页末尾为双栏段落、其正文明确引用下一源页首个成对图片的完整简单整数图号时合并页面组，避免产生该强制分页；不按型号、页码或图片坐标特判，复合编号 `34.1`、`3-2` 和无引用均保留源页边界。
- 历史 bundled `default@1` 文件字节不变（SHA256 `b21448dbc10e7c7d5028490ddc079d784eb12a0360b35be2345fa0218aa12cfb`）；新 `default@2` 文件 SHA256 `b43f0515d707d2b86c3b15813fb655980b4153fcbfd0140bc2199f535760138d`，两者 OOXML 唯一语义差异为默认 `w:cols/@w:space` 由 0 改为 720 twips。manifest 和本地缺省路径指向 V2；已有生产默认指针不自动切换。同号异内容 V2 冲突启动失败关闭，旧 V1 仍由持久化 payload 列出和解析。
- 当前本地候选 `/Users/sc/Downloads/CM1348-caption-review/revised-v8.docx` SHA256 `5dd2a5d462d117dd17a2bcfb82566c4ff298122ad4fa15ca10f8072206411c7c`；WPS PDF `/Users/sc/Downloads/CM1348-caption-review/visual-validation/revised-v8-wps.pdf` SHA256 `3360aa09d0ab38c503ea35f80f9af40bb89df3309a8ec036d0a01f4106b6a96e`，58 页。WPS 第 27 页下半部可见双图及后续文字；第 36 页图 41 抽查无明显回退。两项源页复核提示仍指向 21/25 页；公式 TeX 残留 8 处与 WPS 黑菱形字形问题未由本轮关闭。
- 定向 renderer/schema/converter/本地工具及模板生命周期共 172 项通过；4 项显式资源版本任务绑定测试通过。完整后端 705 项仍为 6 failures + 7 errors，名称与前述基线相同，日志 `/tmp/cm1348-layout-v8-full-closure-post-review.log`。`git diff --check` 通过。
- 独立只读复核发现并促成修复：seed 冲突校验不能误伤自定义 draft、已禁用 seed、manifest 元数据变更或默认模板替换产生的新 draft；当前标准配置下这些回归测试通过，复核未发现剩余代码阻断。仍缺完整 Word/WPS 逐页视觉签字、WPS 数学字形修复及生产已有 `default@2` 占用情况确认；未部署、未切换线上默认模板、未重试线上任务。

## 2026-09-21 原 PDF 对照与源页强制分页修复候选（未放行）

- 原 PDF：`/Users/sc/Downloads/mineru_raw_result_CM1348/e5fdecea-7c1b-46c8-9879-36bf8f2f00a3_origin.pdf`，37 页。v8 WPS 为 58 页；按排除页眉/页脚后的正文底部留白比例，22 页超过 40%，与原 PDF 对应页对照后多数不是源文件本有的留白。v8 OOXML 有 29 个 `w:pageBreakBefore`，附着在同方向 MinerU 源页首块；这类分页属性不能靠删除可见空格消除。
- 因果诊断：仅从 v8 二进制副本移除这 29 个分页属性，WPS 由 58 页变为 32 页，超过 40% 留白的页面由 22 页降为 1 页。正式修复在 `layout_plan.py::_build_soft_page_groups` 不再为同方向源页写分页锚点，保留源页索引、续接证据与方向变化分节；删除针对某图号引用的局部特例。Word/WPS 自然决定可见页边界。
- 正式候选：[revised-v9.docx](/Users/sc/Downloads/CM1348-caption-review/revised-v9.docx)，SHA256 `b75bdf8530c2b9b34ec535527bf8424f18029f574811aa159b9e2da0e3154b5c`；WPS 12.1.28492 输出 [revised-v9.pdf](/Users/sc/Downloads/CM1348-caption-review/revised-v9.pdf)，SHA256 `db41150035dac142e70c4d050e253e6c7fe2d3d443167dd1e2eb9ffef561c5d8`，32 页、仅第 9 页正文底部留白超过 40%。v8/v9 的 IR 文件字节一致；独立只读复核确认 49 个 section 属性、55 个 drawing、47 张 table 与 `w:t` 文本序列一致，仅分页属性 29→0。
- 定向 renderer layout 90 项通过；完整后端 705 项仍为 6 failures + 7 errors，名称与既有基线一致，日志 `/tmp/cm1348-v9-full-unittest.log`。独立 critical review 未确认本轮新增的代码阻断，但没有 Microsoft Word 客户端及其他品牌真样本 WPS 复测，不满足完整发布门禁。
- 未关闭：v9 第 9 页仅图 11/12，原 PDF 第 12 页同页还有图 13/14；在连续成对图片表格间加入微小分隔的诊断副本只把大留白移至第 11 页，未形成可靠通用修复，未并入代码。目录从 v9 首页底部开始、跨至第 3 页，不再与原 PDF 第 2 页的目录起页一致。`docx_latex_residue:8`、目录缓存 TeX、WPS 数学替换字形仍在；`.review.json` 仍有源 21/25 页两处题注复核。当前候选只关闭大多数源页强制分页空白，不宣称整文档视觉质量通过，不部署或重试线上任务。

### v10 目录语义起页补充

- v9 自然续排让目录从首页底部开始。只在临时 DOCX 目录标题同段首 run 插入原生 page break 的 WPS 消融：32 页不变，目录从第 2 页开始，不再像 v8 的 `pageBreakBefore` 多造空白页。正式实现只在新源页首个真实正文块有显式 `annotation_role=toc_title` 时启用，不按“目录”文本或页码特判；普通源页仍自然流动。
- 正式候选：[revised-v10.docx](/Users/sc/Downloads/CM1348-caption-review/revised-v10.docx)，SHA256 `0f62dbd4088df1f377a30d86bc2de45adeeec69d8b16bc61261dc9720db6a842`；WPS PDF [revised-v10.pdf](/Users/sc/Downloads/CM1348-caption-review/revised-v10.pdf)，SHA256 `8d34586151796dd150696b0c61ae271a94c5691a2f364306ee90f1a5ef8e8ca7`。WPS 为 32 页，第 1 页只有封面、第 2 页目录开头；按同一正文底部留白口径仅第 9 页超过 40%，仍为图 11/12 后空白。v9 由 v10 取代。
- renderer layout 定向 91 项通过；全后端 706 项仍为 6 failures + 7 errors，名称与既有基线相同，日志 `/tmp/cm1348-v10-full-unittest.log`。未部署、未重试线上任务；大图组空白、TeX/字形问题、其他品牌真样本及完整 Word/WPS 视觉签字仍未关闭。

### v11 横向表格后目录双重分页保护

- v10 独立只读复核发现：若上一页面组最后区域为 `landscape_table`，下一组为纵向目录，renderer 恢复纵向的 `NEW_PAGE` 分节与目录标题内联 page break 会叠加。v11 在已创建新页分节时消费目录起页意图，不写第二次 break；新增测试通过真实宽表 fallback 路径覆盖。
- 正式本地候选：[revised-v11.docx](/Users/sc/Downloads/CM1348-caption-review/revised-v11.docx)，SHA256 `36e446475aaaf42a0ac89ab42a856e4da82bd282cd5bc8268f47487091c7ba12`。与 v10 的 78 个 DOCX ZIP member 名称及解压内容完全一致，故 CM1348 的 v10 WPS 客户端视觉证据可复用于 v11；不能据此声称新增交叉分支已经过真实 Word/WPS 视觉验证。
- renderer layout 定向 92 项通过；完整后端 707 项仍为 6 failures + 7 errors，与 v10 同名，日志 `/tmp/cm1348-v11-full-unittest.log`。v11 独立 critical review 未确认分页变更新增代码缺陷；其自跑 5 项定向测试通过，指出真实客户端交叉场景、其他品牌样本和第 9 页图组留白仍缺验证。未部署、未重试线上任务，不满足完整 closure 与视觉放行。

### v12 成对图片行续排修复候选（未放行）

- 原 PDF 第 12 页在图 11/12 下仍有图 13/14；v11 WPS 第 9 页只显示图 11/12，正文底部留白约 75.8%。DOCX 对同页后续图组没有 `pageBreakBefore`，而是连续的带 `cantSplit` 1×2 图片布局表内仍有 `keepNext`。只在诊断副本去掉这些单元格段落 `keepNext` 后，WPS 将图 13–18 填入第 9 页。正式 `image_renderer` 因整行已 `cantSplit` 而清除该重复段落约束，不改变独立图片与普通正文。
- 正式结果：[revised-v12.docx](/Users/sc/Downloads/CM1348-caption-review/revised-v12.docx)，SHA256 `84276bb3c6237d8cae0a243257e6f731f79aef8e3086e41d2d7a0fe42c9e34f8`；WPS 12.1.28492 [revised-v12.pdf](/Users/sc/Downloads/CM1348-caption-review/revised-v12.pdf)，SHA256 `7731b315afef6b19308b4c383830d939f2e5193fb5fe79311c51741dcab18eb7`。仍为 32 页；WPS 第 9 页图 11–18 可见并按左右成对，未把题注与图片分开。v11/v12 DOCX 仅 `word/document.xml` 变化，`w:t` 文本序列、55 个 drawing 与 47 张 table 全同，`keepNext` 数量 146→124。
- 同一文字 bbox 留白指标排除封面后，v11 的大留白为第 9 页 75.8%；v12 仍有第 11 页 53.2%，对应图 22 后、图 23 前的跨页分布。因而这次修复只关闭连续成对图片行被整体推页的机制，不能宣称全篇空白已消失；WPS 数学替换字形和 8 处 TeX 残留仍未关闭。
- 定向 renderer layout 92 项通过；完整后端 707 项仍为 6 failures + 7 errors，失败名称与 v11 相同，日志 `/tmp/cm1348-v12-full-unittest.log`。其他品牌样本、Microsoft Word 实际分页与全篇视觉签字仍缺失；未部署、未重试线上任务。

### v13 模板继承修订（当前候选，未放行）

- v12 独立 critical review 找到可复现的模板兼容缺口：只清除直接 `keepNext` 时，若 Normal/题注样式启用该属性，成对图片段落仍会继承。v13 改为在成对图片行的每个单元格段落显式设置 `keep_with_next=False`；测试用所有段落样式均启用 `keepNext` 的模板验证有效覆盖。独立复核确认该反例已关闭，未再发现本局部变更的代码阻断。
- 正式结果：[revised-v13.docx](/Users/sc/Downloads/CM1348-caption-review/revised-v13.docx)，SHA256 `0d07583e1860f673a9b3824c8c6ff778891e45aff0bc44799107bc5b1016664f`；WPS 客户端 [revised-v13.pdf](/Users/sc/Downloads/CM1348-caption-review/revised-v13.pdf)，SHA256 `726f679b33dba9ada4871dff1c2057eb5ea450ed1a34b87a9e2cd506f3cf832a`，32 页。第 9 页仍可见图 11–18，正文底部大留白仍在第 11 页约 53.2%；本候选没有把所有留白消除。v12/v13 仅 `word/document.xml` 变化，`w:t` 文本序列、55 个 drawing、47 张 table 全同。
- renderer layout 92 项通过；完整后端 707 项为 6 failures + 7 errors，13 项名称与 v12 相同，日志 `/tmp/cm1348-v13-full-unittest.log`。Microsoft Word、其他品牌样本和全篇视觉签字仍缺；未部署、未重试线上任务。
