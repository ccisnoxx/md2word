# Datasheet 质量基线与验收证据

## 样本与范围

本地回放使用正式 MinerU → DocumentIR → Word 适配器，解析输入是已有 MinerU 缓存。扩展样本使用用户提供的 TI SN54AC244/SN74AC244 SCAS514H，以及本地既有的 RS2G04 RevA.4。原 PDF、MinerU JSON、图像和 DOCX 均留在本地。版本化清单只保留身份指纹、来源页段和独立标注。[扩展清单](../../../tests/fixtures/datasheet_quality/local_baseline_manifest.json)

| 样本范围 | 本地证据 |
| --- | --- |
| OPA228 既有四项 | 缓存原件 SHA-256 与 Git P0 PDF 文件不同。本次回放按清单中的实际缓存指纹固定，作为同组对照。P0 发布历史继续采用其独立清单和签字证据。 |
| RS2G04 RevA.4，13 页 | 整份可打开，生成 15 张 Word 表格。第 6 页 ESD Ratings 有独立的行列、跨度、表头及技术 Token 标注。 |
| SN74AC244 整份，38 页 | 首轮报 `unsupported_block_type`。逐个解除页级脚注和裁图阻断后，停在 `ir_render_evidence:target_mismatch`，没有主 DOCX。 |
| SN74AC244 原件第 3–6 页 | 独立页段可打开，生成 8 张 Word 表格。第 4 页 5.2 节标注了双层表头、横纵合并和技术 Token。 |
| SN74AC244 原件第 11–12 页 | 独立跨页负例生成可打开的本地草稿，后一页片段 `/1/0` 的空 HTML 产生 `source_pdf_crop` 占位和 `table_noneditable_placeholder`。表格质量为 `blocked`。本次离线回放未观察该原件的任务交付状态。 |

## 首轮度量

按本地回放、原文模式、样本组汇总。以下数值来自锁定标注范围，表格、Token 与页面区域各有独立覆盖分母。

| 指标 | 本地结果与适用范围 |
| --- | --- |
| 转换成功率 | OPA228 缓存组 4/4，扩展组 2/3，正常用例合计 6/7。另有 1 个预期质量阻断用例，单独统计。 |
| 原生表格结构准确率 | 0/3。三张标注表均为可编辑 Word 表格，行列与合并矩形匹配。三张的 MinerU HTML 未声明表头，源 Grid 与 OOXML 均缺标注所需的表头行。额外表及跨单元格错位未做整件观察。 |
| 技术 Token 保留率 | 8/8，覆盖上述三张表中锁定的型号、数值和单位。整份 SN74AC244 的目录公式仍触发完整性阻断。 |
| 页面视觉偏差 | 3/3 个文本锚点区域可配对。以渲染 PDF 中的四边位置偏移计分，OPA228 组偏移 11.35%，扩展组平均 11.50%。Word/WPS 目视检查、全页溢出和裁切留作独立观测。 |
| 人工修改次数及验收耗时 | 缺测。尚无绑定产物指纹的实际编辑和签字记录。 |
| 单文档成本和延迟 | 缺少服务账单和端到端采集。本地回放成功项的 P50/P95 分别为 OPA228 组 0.179/0.255 秒（n=4）、扩展组 1.194/1.419 秒（n=2）。失败耗时单列。 |

[原始观测](observations.json)可由 `scripts/ops/datasheet_quality_metrics.py` 重新聚合。旧 P0 目标仍为 100%，技术 Token 完整率要求仍为 100%。本轮的样本规模和证据层级只支持建立初始分布。

## 根因、修改与保留边界

- **页级脚注**。真实输入包含 24 个 v2 `page_footnote`。修复复用正文 runs 解析，保留其源类型、页号、bbox 和顺序。合成用例验证 Word 中恰好出现一次以及畸形、空载荷被拒绝。
- **分数 PDF 页框**。原件第 12 页是零原点、未旋转且 MediaBox 等于 CropBox 的 A4 页面。MinerU 声明 841×595 点，Poppler 实测框为 841.89×595.28 点。裁图仅在声明尺寸与 Poppler 报告的点框相等时进行。若来源是已确认的归一化坐标，声明尺寸也可严格逐轴向下取整匹配。真实 Poppler 回归验证两种输入坐标生成相同 PNG，并拒绝不匹配框。局部正式 adapter 在显式且已核验的 PDF 来源存在时走同一裁图链路。
- **目录公式**。整份样本的第 2 页目录后续两项各包含一个公式。原生 TOC 规划把整组目录合并为一个字段，实际公式来源登记 118 项，写入 116 项。用合成 v2 list `["Description ... 1", "Timing $V_{CC}$ ... 2"]` 可复现来源 1、写入 0。现有正文标题没有相同来源的可证明代表。完整修复需要明确原生 TOC 的字段缓存或标题对应关系及重放合同。当前保留完整性阻断。
- **复杂表格**。沿用 `canonical-table/v1`，分别对账 PDF 独立标注、来源 Grid、渲染片段和实际 OOXML。真实缺片段按现有质量合同保留非编辑占位。HTML 未标表头的样本继续报结构差异，缺少可靠表头来源的情况不从文本外观猜测。
- **状态合同**。用正式 file/SQLite HTTP 入口验证首发 201、同请求重放 200、冲突或再次发布 409、唯一发布记录和当前指针一致、主件保护及归档后下载 SHA-256。复用了当前接口的审核失效、证据变化和无半提交用例。[API 合同](../../../docs/api/document-jobs.md#质量审核与正式交付的证据绑定)

## 复算与重跑

```bash
task_dir=.trellis/tasks/11-11-datasheet-quality-baseline-contracts
.venv/bin/python scripts/ops/datasheet_quality_metrics.py "$task_dir/observations.json"
```

已有缓存放在 `mineru_result/`，原件或相应本地副本通过 `--package 样本ID=目录` 显式绑定。派生目录在 `tests/tmp/datasheet-quality-inputs-20261111/`。使用 Poppler `pdfseparate` 和 `pdfunite` 按原页序保存 PDF 页段。MinerU v2 的页数组按同一区间切取，`layout.json` 的 `pdf_info` 重新从零编号，原图片路径保持可解析。重建产物的字节须与清单匹配，版本变化时另登记指纹。

```bash
.venv/bin/python scripts/dev/run_datasheet_quality_baseline.py \
  --output tests/tmp/datasheet-quality-replay-new \
  --package "gs-003=$OPA_P1_PACKAGE" \
  --package "gs-004=$OPA_P2_PACKAGE" \
  --package "gs-006=$OPA_P6_PACKAGE" \
  --package "gs-008=$OPA_P7_PACKAGE" \
  --package "gsx-rs2g04=$RS2G04_PACKAGE" \
  --package "gsx-sn74ac244=$SN74AC244_PACKAGE" \
  --package "gsx-sn74ac244-specs=tests/tmp/datasheet-quality-inputs-20261111/sn74ac244-specs" \
  --package "gsx-sn74ac244-packaging=tests/tmp/datasheet-quality-inputs-20261111/sn74ac244-packaging"
```

## 当前重点的验收证据

七组指标的算法和缺测规则见[指标合同](design.md#2-指标合同)。从六份已保存观测复算，口径为 `datasheet-quality-observations/v1` 和 `datasheet-quality-metrics/v1`。同一指标按转换模式、样本组和证据层级比较。

| 指标 | 当前有数据的范围及待采集项 |
| --- | --- |
| 转换成功率 | 首轮原排版回放 OPA228 对照组 4/4、扩展组 2/3，预期阻断单列。RS2G04 英译中隔离完整链路 1/1。 |
| 原生表格结构准确率 | 原排版三张标注表原始 0/3，校核后 3/3。RS2G04 实时英译中原始 0/1，使用同源校核的渲染复验 1/1。 |
| 技术 Token 保留率 | 原排版三张标注表 8/8。RS2G04 完整链路与校核版各为 3/3。 |
| 页面视觉偏差 | 原排版已配对 3 个标注区域。扩展组 2 个区域的归一化偏差均值为 0.1150，P95 为 0.1200。英译中缺少批准的同模式版式基准。 |
| 人工修改次数 | 缺测，待按实际修正的独立缺陷计数。 |
| 人工验收耗时 | 缺测，待按绑定产物指纹的实际审核区间汇总。 |
| 单文档成本和延迟 | RS2G04 英译中完整链路成功样本 1 个。成本估算 USD 0.001626756，任务提交口径 32.234 秒，含 PDF 提交 32.245 秒。 |

`canonical-table/v1` 的现有覆盖以独立标注、源 Grid、渲染投影和 Word 实物为准。下表列出已取得的证据和下一项覆盖缺口。[Grid 合同](design.md#3-canonical-table-grid)

| 风险场景 | 当前覆盖 |
| --- | --- |
| 横纵合并、多级表头和宽表 | 三张真实表对照覆盖两种跨度、一行和两行表头，以及 19×8 规格宽表。 |
| 跨页续表和重复行 | 已有合成续表夹具验证校核不会导致误删正文行。TPLD2001 第 3–4 页已补真实续表对照。原始 v2 为预合并表和空片段，同次模型的两段完整 HTML 可独立复验。按表 ID 核对 Grid、计划与实物后，完整片段因复合表号归组不足而输出两张 Word 表，结构完整匹配 0/1。已登记偏差。[跨页续表结构对照](cross-page-grid-validation.md) |
| 上游预合并来源 | TPLD2001 原始 v2 已复验证据绑定。主表 22×8，仅输出一次。SN74AC244 次页归属证据不足，裁图与阻断保留。[来源绑定复验](upstream-table-coverage-validation.md) |
| 片段缺失 | 已用真实空 HTML 片段验证裁图占位和表格质量阻断。 |
| 源、渲染与实物表头一致性 | RS2G04 同源对照已逐层验证。原生 `<th>` 跨盖无锚点行的差异已登记。 |

复用现有记录补齐指标和结构覆盖，发现的差异按处理环节归入[问题清单](issues.md)。人工数据和英译中版式基准待补，新增阈值继续等待基线覆盖。

## 验收进度

- AC1、AC3。样本扩充和本地基线已有证据。RS2G04 第 6 页已完成隔离 API 和 Worker 英译中，完整链路成本和延迟可复算。SN74AC244 的实译失败已定位到原 PDF 第 5 页的请求批次。[英译中验收记录](en2zh-validation.md)
- AC2。指标可从保存的观测复算，人工修改次数、验收耗时和签字等待实际审阅记录。英译中视觉指标需要同模式批准基准。[人工验收记录](en2zh-human-review.md)
- AC4。原生行列、合并矩形和负例占位已核对。SN74AC244 整份转换和 LibreOffice 目录刷新已有公式保真证据，Word/WPS 客户端刷新待验。三表本地回放和 RS2G04 实时解析结果的表头校核已分别复验，后者原始 0/1、校核版 1/1。[目录公式验证](toc-formula-verification.md) · [表头来源与校核](table-header-review.md) · [RS2G04 定向复验](en2zh-validation.md#使用本次-mineru-结果复验-esd-表头)
- AC5、AC6。本地 file/SQLite 状态合同定向通过，覆盖审核失效、发布重放、冲突和主件保护。正式发布验收待取得对应环境证据。

## 定向验证与任务对应

| 合同 | 当前证据 |
| --- | --- |
| TAB-301～308 | 复用 Grid 模型、共享占位构建器、Word 规划与表格证据。用样本检查多级表头、纵横合并、跨页和缺表。真客户端复核与扩展发布门禁待后续证据。 |
| CON-103/104、QA-601～607 | 状态和审核发布代码沿用当前实现。当前端口的 5 项定向验证通过，覆盖发布/重放/证据冲突、审核有效性与受保护主件。 |
| REL-701～704 | 保留 P0 历史报告。新增扩展清单及七组指标复算，真实发布验收、账单和人工签字未采集。 |

- 输入脚注、PDF 坐标空间和本地 PDF 绑定的合计 12 项定向检查通过。指标的 8 项定向检查通过。原始观测独立重算与回放 JSON 语义一致。
- 输入验证扩查的 3 项失败和 17 项错误在隔离 HEAD 复现同样计数。两项旧状态 API 用例仍使用旧审核调用参数或用普通更新直接设置 `published`，共 4 个夹具错误。对应的当前合同已用正式入口的定向用例验证。历史夹具单独保留。
