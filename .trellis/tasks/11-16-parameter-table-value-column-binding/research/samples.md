# 回归输入与独立标注

| ID | 来源与本地引用 | MinerU ZIP SHA-256 | 目标 |
| --- | --- | --- | --- |
| sn74-v4-ambiguous | [首轮 v4](../../../../tests/tmp/mineru-v4-v1-sn74ac244-20261116/v4.zip) | `55bf063ac6dd25dd07d087981c4ec644390bed84517bf962594b550acfeeea53` | SN74AC244 原件第 4 页，5.2 Operating Conditions，v2 指针 `/1/6` |
| sn74-v4-matching | [重传 v4](../../../../tests/tmp/mineru-adoption-20261116/sn74-repeat/v4.zip) | `239a6439f05c6cf0e4eb1e9fc9ff8f456f3e082f5a6f43690042b872191b1b52` | 同源同表同指针 |
| opa228-p7-location | [gs-008 保存包](../../../../tests/tmp/datasheet-quality-regression-live/20261112T033738667332Z/data/object_artifacts/document-jobs/acceptance/docjob_3bf569b59c40/mineru_raw_result/file_0d89e7fdc241/mineru_raw_result.zip) | `f132b22f6631d269d93e78a48da839e8bb5aefd96fc80397fa80f21611e0117b` | OPA228 原件第 7 页，6.7 节，v2 指针 `/0/1` |

SN74AC244 两包对应同一个 [第 3–6 页 PDF 切片](../../../../tests/tmp/datasheet-quality-inputs-20261111/sn74ac244-specs/sample_origin.pdf)，提交源 SHA-256 为 `04c5b23af2877ebd686b032caa25c9f0d2ace7b123fb0d013c83cc562285fc74`。包内生成的 `*_origin.pdf` 与提交源的字节指纹不同。源身份基于原始提交文件与对照记录。[首轮对照](../../../../tests/tmp/mineru-v4-v1-sn74ac244-20261116/report.md#同模板-word-对照) · [重传对照](../../../../tests/tmp/mineru-adoption-20261116/report.md)

OPA228 [仓库第 7 页切片](../../../../tests/fixtures/golden_samples/pdfs/OPA228_P7.pdf)与 gs-008 登记源文件 SHA-256 均为 `0afe536bc8ff50b8a30c5da25fbd54ea4226179c7cceb16fb331671c71da077f`。以下页号按原 PDF 标示。切片内第 1 页显示为「源 PDF 页 1」，原件第 7 页由夹具映射核对，运行时无需猜原件页码。

## 预期位置

表内源 HTML 行号从 1 开始并计入表头。Grid 物理列索引用从 0 开始的半开区间。

| 样本 | 源行 | 单元格与条件 | HTML 涉及列 | 独立标注列 |
| --- | --- | --- | --- | --- |
| sn74-v4-ambiguous | 4、5、6 | SN54AC244 的 `V_IH`。2.1、3.15、3.85 V。 | `[3,5)`，MIN–MAX | MIN |
| sn74-v4-ambiguous | 4、5、6 | SN74AC244 的 `V_IH`。2.1、3.15、3.85 V。 | `[5,7)`，MIN–MAX | MIN |
| sn74-v4-matching | 4、5、6 | 两个器件组的同六处值。 | `[3,4)` 与 `[5,6)`，MAX 单元格各自存在且为空 | MIN |
| opa228-p7-location | 3 | `VOS`，U/P，`±5 µV`。 | `[4,6)`，MIN–TYP | TYP |
| opa228-p7-location | 4 | `VOS`，−40 °C 至 +85 °C，`±100 µV`。 | `[4,7)`，MIN–MAX | MAX |

只读检查已从三份 ZIP 的 content list v2 抽取上述行，独立核对了合并范围。两份 SN74AC244 目标表都是 19×8，首行有两个器件组，次行各有 MIN/MAX。三份目标表均使用 `td`，顶端标签组合本身须能提供局部表头证据。对应的 content list、model 和 layout 只见表格/表体 span 的 bbox，未见能绑定到这些数值的单元格几何。独立标注来源为历史 PDF 对照，新的正式转换回放在实施阶段完成。

两份 ZIP 当前均在 Git 忽略的本地证据目录。实施时以原始字节为固定输入，在 [父任务登记的授权边界](../../11-11-datasheet-quality-baseline-contracts/prd.md) 内保存可复取的引用和校验值。回归报告对缺包、错指纹和通过使用不同结果。自动化可另用仓库规则允许的最小夹具验证算法。

## 离线回放

在仓库根目录运行，四个变量分别指向上方登记的 PDF 和三个 ZIP，输出目录须为新路径。回放程序逐一核对指纹、运行正式 direct adapter，直接读取生成的 Word 表格并写入 `observations.json`。缺包或错指纹会失败。

```bash
.venv/bin/python -m scripts.dev.replay_parameter_table_value_columns \
  --sn74-pdf "$SN74_PDF" \
  --sn74-v4-ambiguous "$SN74_V4_AMBIGUOUS" \
  --sn74-v4-matching "$SN74_V4_MATCHING" \
  --opa228-p7-location "$OPA228_P7_LOCATION" \
  --output tests/tmp/parameter-table-value-column-replay
```
