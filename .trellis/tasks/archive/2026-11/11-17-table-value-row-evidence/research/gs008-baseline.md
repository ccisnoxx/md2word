# gs-008 固定样本和当前预查

## 固定输入

| 口径 | 本地输入 | 指纹/预查 |
| --- | --- | --- |
| 完整同源缓存，23 项主验收 | `mineru_result/OPA228_P7.pdf-d457d448-c495-41ea-8bcf-41a3f18c00fb/` 对应 `*_origin.pdf`、`*_content_list_v2.json`、`layout.json` 及附件 | PDF `24f724cf0e795f6afeb6fec5c72ff8f144085c59d57fbf0a5c9efbf1808b1eb3`；v2 `fdc0ea4050914df39ce7d3e9e42798164d32d1f04b82bd9dff4d2ffc1e9e98c3`。匹配 [基线清单](../../../../../../tests/fixtures/datasheet_quality/local_baseline_manifest.json)。 |
| 留存 Worker 回包，18 项独立回归 | `/tmp/md2word-rollout5.roi2be/evidence/live-gs-008-returned.zip`，与上列提交 PDF 配对 | ZIP `5de05d59fdacea166361bde14625ff8045350b0aefc894a923ff181a030fe033`。旧记录的 Word 实物通过 5 项，13 项未决；这份 MinerU 解析的 `±100` 原本已是单列。 |

两组本地输入本轮均已核对指纹。已登记的 [两项人工核定](../../../../../../tests/fixtures/datasheet_quality/gs008_value_column_reviews.json) 属于 23 项完整缓存。注意仓库 Golden Sample 目录中的同名 PDF 指纹不同，不是完整缓存的显式来源。两份 ZIP 不混用，也不用 5/18 代替主验收的基线。

## 2026-11-17 规划预查

以 `main@babe9757` 在本机把完整缓存临时打包，使用真实 Poppler 26.06.0 与 `MinerUToDocumentIRService.convert_zip` 的现有自动取证入口。未传人工核定。实测源 Grid 32 行，表头在 0，表头之后 31 行（计入分节标题）；有 30 个完整 PDF band。23 个发现中 9 个生成自动修正提议，14 个返回 `row_ambiguous`。这次只验证了 IR 提议，未生成或认证新 DOCX。上一轮 [完整缓存实物](../../11-15-table-value-pdf-binding/validation.md#完整-gs-008-回放) 的独立记录为 9/23 通过实际 Word 认证。

下边界实测：同源表区下缘为 520.344 pt；末完整 band 到 507.824219 pt，之后剩余 `Common-mode` 一行，PDF 下横线为 520.574219 pt、已在框外。`OFFSET VOLTAGE`、`INPUT BIAS CURRENT`、`NOISE`、`INPUT VOLTAGE`、`INPUT IMPEDANCE` 各有自己的物理 band，因此分节标题不能解释 31 对 30。不得按行号补一个虚拟 band；现有横向侧缘恢复另有实物回归。

在 14 个未决中，9 处的精确目标词在现有 band 内只检出一次；另 5 处检测到同值。预查只统计词框及字形存在，未验证逐格独立列义或其余安全条件，不计入覆盖率。实施先检查这些形状：

- 源行 6、7 的 `±0.1`、`±0.3`：同组 `dV_{OS}/dT`、分开的等级条件和纵向共享单位。
- 源行 8、9 的 `±0.5`、`±2`：换行参数名称、跨行电压条件；`±2` 同时出现在其他 band。
- 源行 11、12 的 `0.2`、`110`：换行参数名称、不同单位，后者混有文本和公式。`0.2` 也出现于上方另一参数。
- 源行 19–24：输入噪声，共享条件或单位，两个 `3` 需要逐行条件区分；下标或根号单位需要完整表示验证。
- 源行 27、28 的 `138`、`120`：共模抑制相关名称与条件有换行、混合公式，`120` 还出现在相邻 band。

在实现前使用 `pdftotext -layout` 对照行条件，用 `pdftotext -bbox-layout` 复核各目标词的横向列归属与纵向位置。表头文字右缘为 MIN 433.992、TYP 475.977、MAX 516.306 pt。源格定位来自未开启自动取证的完整 Grid。23 项标注已保存到 [独立预期](../../../../../../tests/fixtures/datasheet_quality/gs008_value_column_expected.json)。Word 验收按源格和列比较，PDF 绑定同时核对词框顶边，防止同值错绑到另一行后仍计作命中。
