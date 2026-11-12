# 上游预合并来源绑定复验

复合表号归组与首批验收已提交为 `d69427ad`。本次通过正式本地 MinerU → DocumentIR → Word 路径重放相同输入。独立 PDF 标注、原始结构基线 0/1 和首批复验记录保留。[原始跨页基线](cross-page-grid-validation.md) · [首批复验](continuation-contract-validation.md)

| 输入 | 来源证据 | Grid、渲染投影与 Word | 表格质量 |
| --- | --- | --- | --- |
| TPLD2001 SCPS286C 第 3–4 页，原始 MinerU 包及 PDF 指纹校核 | v2 `/0/2` 为主片，`/1/0` 空。预处理题注为 `Table 4-1. Pin Functions` 和同题 `(continued)`。前段 20 行，后段 4 行。校核确认共享开头两行是表头，次页剩余两条引脚数据进入主表。 | 目标 Grid 和 Word 都为 22×8，主片输出 `[0,22)`，空片输出 `[0,0)`，映射主表 `[20,22)`。两行表头写入 `w:tblHeader`，无次页裁图。20 条引脚数据、60/60 个标注 Token，目标表只输出一次。 | 原生表投影 `passed`，聚合表格质量 `warning`，仅余 `invalid_table_reference`。 |
| 同一 TPLD2001 原始包，未提供校核 | 上游的共享开头两行由普通 `<td>` 构成。 | 主表 22×8，无 `w:tblHeader`。次页保留原 PDF 裁图。 | `blocked`。 |
| SN74AC244 SCAS514H 第 11–12 页，既有缺片段负例 | v2 `/0/1` 为主片，`/1/0` 空。版面中的 20 行与 12 行去掉一行共享开头后可以匹配主表 31 行，两页均缺少可核实的续表题注。 | Grid 和 Word 主表为 31×10。次页无覆盖区间，仍有可追溯的源 PDF 裁图。 | `blocked`，包含 `table_html_empty`、`table_fragment_missing`、`table_noneditable_placeholder`。 |
| TPLD2001 同次模型的完整片段对照 | `/0/2` 与 `/1/0` 都有完整 HTML，复用复合表号归组合同。 | 两段仍合为一张 24×8 原生表。20 条引脚数据、60/60 个标注 Token。 | `warning`，包括缺少可删重复表头的证据。 |

TPLD2001 正例的原始包 SHA-256 为 `56276ab85990b363d9a348fd5a4952c2b91b2601f56579ecff8daeb95e59bdaf`，v2 SHA-256 为 `d57460c11567265b46f846846675713020069aec165fd64d7b690399a441e8e4`，版面 SHA-256 为 `ab685b809f961d8819c9fba4dbdb5b4099ec53cd29a0e2cb20cc81eae7fa421d`。前处理定位为 `/pdf_info/0/preproc_blocks/2`、`/pdf_info/1/preproc_blocks/0`，后处理定位为 `/pdf_info/0/para_blocks/2`、`/pdf_info/1/para_blocks/0`。

TPLD2001 的本地校核由锁定的独立标注和两页源 PDF 复核得到。两页都显示 `PIN`、`DESCRIPTION` 分组及同一列标题行。校核复用已有入口，只在原件 PDF、内容列表、主片位置和 HTML 指纹匹配时生效。[校核绑定](tpld2001-premerge-header-review.json)

四份新 DOCX 通过持久化内容证据与表格证据重读。将正例来源的起始行或 Word 投影的起始行由 20 改为 19 后重读，分别拒绝两次篡改。改写结构化表格报告的覆盖终点并重算报告指纹也会被拒绝。此前两份 TPLD2001 IR 的 JSON 值逐项一致，历史 DOCX 证据仍可重读，原始预合并回放仍记录为 `blocked`。正反例新旧 Word 原生表的逐格文本和跨度一致。替换主片可译文本的投影仍定位 `[20,22)`，删除末行则触发 `table_render_geometry`。

16 项定向回归通过。核心用例 `test_convert_zip_requires_bound_upstream_row_coverage_for_empty_continuation` 覆盖 15 种输入、来源重读、Grid 和 Word。共享版面读取的旧夹具 `test_merge_proof_is_bound_to_selected_document_and_unique_layout` 仍报 `multiple_result_roots`，在隔离的 `d69427ad` 上复现相同结果。17 个变更 Python 文件通过语法编译，`git diff --check` 通过。

Figure 4-1 的上游误分类仍单独记录。人工修改次数和验收耗时待审阅回填，新增阈值待样本覆盖补齐。[问题清单](issues.md)

[本地复算脚本](../../../tests/tmp/datasheet-cross-page-grid-20261112/upstream-coverage-after/replay.py) · [复算观测](../../../tests/tmp/datasheet-cross-page-grid-20261112/upstream-coverage-after/observations.json) · [TPLD2001 Word](../../../tests/tmp/datasheet-cross-page-grid-20261112/upstream-coverage-after/original-reviewed.docx) · [SN74AC244 Word](../../../tests/tmp/datasheet-cross-page-grid-20261112/upstream-coverage-after/missing.docx)
