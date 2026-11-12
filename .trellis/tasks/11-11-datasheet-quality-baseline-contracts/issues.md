# 转换质量问题清单

样本用来定位可复现的差异。按最早出现差异的公共处理环节归类，记录影响、定位和已有证据。后续修复批次按共用规则归并，并用小夹具和相关样本一起验证。

| 环节 | 已观察到的差异 | 影响和证据 | 归并方向 |
| --- | --- | --- | --- |
| 上游表头语义 | 多份样本的源 PDF 可确认表头，但 MinerU HTML 只有 `<td>`。RS2G04 实时结果在源 Grid、渲染 Grid 和 Word 都没有重复表头。 | 原生表格结构准确率。原排版三表原始 0/3，校核 3/3。RS2G04 英译中实时原始 0/1，使用绑定校核的同源复验 1/1。[三表对照](table-header-review.md) · [实时结果对照](en2zh-validation.md#使用本次-mineru-结果复验-esd-表头) | 归入表头来源及校核证据的接入问题。每次解析独立绑定其来源身份。 |
| Grid 与 Word 的表头投影 | 原生 `<th>` 完全跨盖下一行且该行没有单元格锚点时，旧源 Grid 只统计锚点行，Word 同时标记被覆盖行。 | 结构准确率及源/实物一致性。最小合成用例已复现，三张实表未触发。[兼容边界](table-header-review.md#三张表的同源对照) | 归入表头投影规则，纳入历史证据重读的兼容验证。 |
| 续表片段缺失 | SN74AC244 原 PDF 第 12 页的续表片段无 HTML，转换生成裁图占位并记录 `table_noneditable_placeholder`。 | 原生表格可编辑性。该页是预期阻断的负例，离线证据验证了表格质量阻断，任务发布状态另需对应证据。[缺表定位](toc-formula-verification.md#整份样本结果) | 归入上游片段完整性。保留负例和阻断行为。 |
| 解析输出的预合并 | TPLD2001 Table 4-1 的 MinerU v2 把两段合并到首页 HTML，次页为空。同次模型结果和预处理版面仍保留两段完整 HTML。 | 原排版回放主表已含全部 20 条引脚数据，次页另产生裁图占位并阻断表格质量。[跨页对照](cross-page-grid-validation.md) | 同包来源和行覆盖验证后只输出一次。SN74AC244 负例因缺少明确续表题注，继续保留裁图和质量阻断。[来源绑定复验](upstream-table-coverage-validation.md) |
| 续表归组的复合表号 | TPLD2001 的两段完整 HTML 均为 8 列，后一页保留 `Table 4-1 ... (continued)`，原分组器将 `4-1` 判为歧义并记录 `insufficient_evidence`。 | 原始对照输出 20×8、4×8 两张原生表，结构完整匹配 0/1。[跨页基线](cross-page-grid-validation.md) | 本批已验证同编号、相容题注和明确续表可归组为一张表。当前真实输入的四行标题因缺少可信表头证据继续保留，归入表头来源问题。[首批复验](continuation-contract-validation.md) |
| 上游图表类型 | TPLD2001 第 3 页 Figure 4-1 是引脚示意图，MinerU 将其归类为表格 `/0/0`。 | 两路 Word 均生成一张额外 10×4 原生表，独立记录意外多表 1。[跨页对照](cross-page-grid-validation.md) | 同块图题与已验证原包图片建立来源绑定。回放保留 Figure 4-1，Table 4-1 仍可编辑，意外多表为 0。[图表来源复验](table-figure-validation.md) |
| 翻译技术内容 | SN74AC244 原 PDF 第 5 页的译文批次触发 `translation_integrity_technical_mismatch`，147 项中 1 项失败。 | 转换成功率受阻。已离线定位到批次，历史记录缺少能归因到具体单元格的响应证据。[失败批次](en2zh-validation.md#sn74ac244-英译中失败批次的离线定位) | 归入翻译技术内容完整性，按相同错误类别收集可比较的证据。 |

已闭环的历史项继续作为回归证据。SN74AC244 目录公式修复已验证 118/118 写入及 LibreOffice 刷新后可定位，Word/WPS 客户端覆盖待补。MinerU 401 已通过更新过期凭据恢复，随后 RS2G04 成功运行完整链路。[目录公式记录](toc-formula-verification.md) · [完整链路记录](en2zh-validation.md)

指标缺测、样本量不足和客户端覆盖不足登记在[验收证据](validation.md#当前重点的验收证据)，用于决定补采顺序。
