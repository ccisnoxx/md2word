# R-10 整文档视觉治理记录

## 1. 治理边界

R-10 不尝试自动判断 Word/WPS 的实际分页、空白页、栏平衡、表格挤压、字体安装或图片清晰度。自动 owner 只负责生成可重复样本、记录源码版本及输入/输出哈希，并校验人工签字没有跨版本、跨产物复用；视觉结论继续由 Word/WPS 给出，LibreOffice 只能作为辅助证据。

`scripts/dev/run_component_pdf_regression.py` 当前会生成 `manual-signoff-template.yaml`，并通过 `--apply-manual-signoff` 校验：

- 当前 `git_commit` 与 dirty 状态；
- MinerU 包 SHA-256 与 DOCX SHA-256；
- Word/WPS 客户端及版本；
- 实际页数、非预期空白页、关键内容组落页、表格挤压、栏平衡、图片清晰度和字体替换；
- `conditional`、`fail` 或任一非 `pass` 检查项必须有备注。

自动回归 `summary.ok` 与 `manual_visual_acceptance` 分开保存。有效的条件通过只表示记录完整且没有整体 `fail`，不等于所有视觉项为 `pass`，也不进入线上 `blocking_quality_flags`。

## 2. 当前版本与客户端

- 源码：`e51e6ccd129f59d1b372dfc6907def1fd6bb5cd8`，`worktree_dirty=true`。
- 客户端：WPS Office 2026 秋季更新，`12.1.26055`。
- 页面样式：正式本地入口缺省模板与版式配置。
- 生成时间：2026-08-21。

## 3. committed runnable 最小包

样本 `ti-opamp-opa228-p1-smoke` 通过 component runner 生成并应用机器可读签字：

- MinerU 包 SHA-256：`109f6d8c4d34e635f487cf845d27420cc406d6b192f0cc0ae04856745cfceeb3`；
- DOCX SHA-256：`3de69b1d157dd3c59484525cbb16914957f583b0dce54fb23637417127e67fba`；
- WPS：1 页，无空白页或内容溢出；标题、正文、原生项目符号及 `nV/sqrt(Hz)`、`V/us` 完整可读；
- 结论：`conditional`。该最小包不含表格、分栏和图片，相关项为 `n/a`；WPS 状态栏显示“缺失字体”，但可见内容未乱码或遮挡。

运行证据保存在忽略目录 `tests/tmp/component_pdf_regression/20260821T080507Z/`，不作为可跨版本复用的仓库门禁。

## 4. committed OPA228 代表页当前 WPS 记录

4 个 committed PDF 继续按 QUALITY-002 归类为“输入已提交、执行依赖本地 MinerU 包”。本轮使用其现有本地 MinerU 结果，经正式本地入口生成当前候选；不能把本地 MinerU 包写成 committed runnable fixture。

| 样本 | PDF SHA-256 | MinerU 包 SHA-256 | DOCX SHA-256 | WPS 页数 | 当前视觉结论 |
|---|---|---|---|---:|---|
| OPA228 P1 | `1b3ccad1adee4979d63a647bc785d0d49d7eecbf11f4421a18936db4ee75f9da` | `aa1f76490f35b2ca4ade31905fc0aaee6fc726b5ed630c4157f33e69bebbf297` | `1ff6a0fcabee7f571a30c02207fc255d11941ea0cef85f627ae95ec6fa153dee` | 2 | `conditional`：原 PDF 1 页；Word 第 1 页原生双栏、图和正文可读，第 2 页只有 Device Information 表与 notice，页面明显稀疏。不是空白页，表格未挤压，图片清晰，但关键内容组落页与源版式仍有差距。 |
| OPA228 P2 | `18f4a111b7e4ad835e82ec2057f8642e6bddd38640240c283e115c91a2302` | `d6e6568822b4c4c9f8276d14bbeffd410923fe514dab8384405c9dfd8d132cc9` | `e0f067b9538a53a269e6280593dfbbd97de5a8a35bbcd790a99c526f28ef95f2` | 1 | `conditional`：更新字段后原生 TOC 显示 `4 Revision History ... 1`，修订范围仍是可见正文且未进入目录。该孤立页没有完整文档 headings，不能据此验收完整 TOC，也不能把源 PDF 双栏目录与当前单条缓存的差异判为 renderer 回退。 |
| OPA228 P6 | `372af640ad4d5a0e725a49152095e233d7a27bd595a4b15237fb392b1fa19f77` | `219fb8a466548edb27bf27e7abb48826db1901fd5025f17ed1dcae4263bdf9ec` | `94385e21e5793742b89bd7f908234f88287c65df94e838fd40f0856dcd587e27` | 1 | `conditional`：3 张 Thermal Information 表均完整可编辑、列未截断、单位和下标可读，没有非预期空白页；WPS 仍提示“缺失字体”。 |
| OPA228 P7 | `0afe536bc8ff50b8a30c5da25fbd54ea4226179c7cceb16fb331671c71da077f` | `b150d135e6d9e0ad1a4e69ff770ec38bd1671ff005de1e93122a00b3a0bdb654` | `a56dd01f96846931ac712ea608ff0e028504f6e5b5edebe76bfcc766ed9efc65` | 2 | `conditional`：原 PDF 1 页；Word 宽表自然跨 2 页，表头、分组、数值和单位均可见且没有水平裁切，第二页不是空白页，但页数增加和尾页留白必须保留为当前客户端排版差异。WPS 仍提示“缺失字体”。 |

## 5. external SN54AC244 整文档当前 WPS 记录

`/Users/sc/Downloads/mineru_raw_result 3`、`sn54ac244.pdf` 和旧问题基线 `sn54ac244.docx` 作为同一 external 代表样本使用，不复制进仓库，也不冒充 committed runnable fixture。当前 dirty 源码通过正式本地入口重新生成候选：

- 源 PDF SHA-256：`9b4cb7e7169187dcd3cace1d596036209ec8381aba760f9834f506439df3a7a8`，38 页；
- MinerU 包 SHA-256：`50883adeac98a47b942989b9d3716e631c674d1c663a334f3da0fa89730a7c32`；
- DocumentIR SHA-256：`d89816b3b07f9ca45d6936282b5d9acba3ed4161d8d619a546e593828f525afa`；
- 首个代表候选 DOCX SHA-256：`b684de0cbc20b7682f34f3d6e9fcb417dcae87e6e0772a17401989036fc39892`，WPS 12.1.26055 实际 58 页；该候选用于确认下述两个分页失败。
- 修复候选：`/private/tmp/md2word-r10-structural.LfmF16/sn54ac244-r10-structural.docx`，SHA-256 `5ddddca139e76b393351c8ba90fd249b89c693b879b63fdc5e4254c9bab720bf`，WPS 12.1.26055 实际 50 页；未复制进仓库。
- 修复候选结构覆盖：19 张语义表、10 张六列以上宽表、12 个原生双栏 section、1 个横向 section、38 个图片资产和 44 个 drawing；`pageBreakBefore` 为 33，未写逐源页硬分页，`blocking_quality_flags=[]`。

该样本已经覆盖真实表格、原生分栏、图片和长文档，不再把“缺少实际代表性覆盖”写成 R-10 剩余缺口。首个 58 页候选的两个确定失败为：

- WPS 第 1 页的原生双栏、右栏 Device Information 表和底部成对逻辑图可见，表格没有拦断双栏阅读关系；但源 PDF 首页末尾的题注和 notice 被挤到几乎空白的 WPS 第 2 页，源第 2 页目录随之落到 WPS 第 3 页。
- WPS 第 39 页只保留 `DW0020A / PACKAGE OUTLINE / SOIC` 等技术标题，主体机械图落到第 40 页，违反标题与后续主体的内容组落页要求。

最小修复回到共同布局 owner，而非增加样本规则：具有明确“页脚候选因内容保全提升为正文”元数据且仍位于源页底边的块，成为 FLOW-001 的软续接证据；仅由普通文本组成、高度小于源页 20%、与后续 wide 图片间距不超过既有阈值的短双栏前导，安全降级为带 `keep_with_next` 的 `visual_prelude` 单栏连续组；普通及成对图片另按源页相对高度设置只缩不放大的上限。该栏降级 reason 已进入 renderer evidence。

修复候选的 WPS 有界复核结果为 `conditional`：

- 第 1 页原生实质双栏和右栏 Device Information 表仍在；第 2 页同时容纳 `IMPORTANT NOTICE` 与 TOC，不再出现近空白尾页。
- 搜索 `DW0020A` 定位到第 35 页，`PACKAGE OUTLINE / DW0020A / SOIC` 标签与主体机械图同页。
- 5 个定向回归、相关文件 `py_compile` 和 `git diff --check` 通过；结构证据无 blocker。
- 未执行 50 页逐页重新签字，也未重复检查与本次两个缺陷无关的所有页面，因此不把该记录写成整本文档无条件 `pass`。
- 生产代码没有 SN54、型号、标题文本、固定 block 或页码特例，也没有恢复逐源页硬分页。

## 6. 结论与剩余边界

R-10 的通用治理 owner、两个最小回归和当前 WPS 有界记录已建立。OPA228 的分页扩张和字体提示继续作为非阻断风险；SN54AC244 已补齐实际代表性覆盖，两个已证实分页失败均已由通用规则修复并通过针对性 WPS 复核。

QUALITY-003 保持 `implemented-gap`，不能标为 `enforced-tested`：真实表格、分栏、图片和长文档已经由当前 external SN54AC244 覆盖，但视觉判断不能自动化，本轮也只对两个已证实缺陷做有界复核，且 committed runnable 包仍只有最小单页样本。只有在获得合法提交许可时才考虑裁剪最小 MinerU fixture；这不是当前修复的前置条件，也不能为关闭矩阵而提交客户 PDF、旧 DOCX 或完整 MinerU 产物。
