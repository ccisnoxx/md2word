# 真实 MinerU 回包与上传 PDF 的同源证据

## 已确认的仓库路径

- 解析阶段从 `job.source_file_id` 下载已登记上传内容，写入本次临时文件。MinerU 客户端以二进制流直接 PUT 该文件，提交和回包使用 `batch_id`、`data_id` 区分。任务记录保存批次，没有单独的网络上传摘要。见 `app/domains/document_jobs/mineru_execution.py:76–122`、`app/clients/mineru_client.py:88–126`。
- 回包下载后，以原 ZIP 字节登记 `mineru_raw_result`。文件保存源 PDF ID、批次、data ID 和原解析代，并由任务指针选中。填写验收表时应读该已登记文件的实际字节及完整身份。见 `app/domains/document_jobs/mineru_execution.py:466–527`。
- 第四阶段 Worker 校验当前 job、文件归属、角色、当前指针、生命周期、实际长度和 SHA-256，再进入正式 converter。所选 v2 同目录对应的包内 `*_origin.pdf`（无前缀时 `origin.pdf`）须与实际源 PDF 同摘要；兼容旧包可保留原 blocker。自动证据还要求同文档 layout、页框和表框成立。见 `app/domains/document_jobs/table_value_column_sources.py:28–83`、`app/services/document_ir/pdf_value_column_review_flow.py:37–88,114–130`。

## 本轮只读核对

| 证据 | 本地实际 SHA-256 |
| --- | --- |
| `gs-008` 缓存的包内源 PDF | `24f724cf0e795f6afeb6fec5c72ff8f144085c59d57fbf0a5c9efbf1808b1eb3` |
| 同缓存的选定 v2 | `fdc0ea4050914df39ce7d3e9e42798164d32d1f04b82bd9dff4d2ffc1e9e98c3` |
| 同缓存的 layout | `cb69b35f9fbefc2740d95a1d70c5c858690a854923354a12d11140ee211ad3b8` |
| 仓内同名 P7 PDF | `0afe536bc8ff50b8a30c5da25fbd54ea4226179c7cceb16fb331671c71da077f` |

前两项符合既有清单。该缓存、同名负例及第四阶段实物结果是本地基线。实际拟上线环境的回包和实传配对仍待采证。[基线清单](../../../../../../tests/fixtures/datasheet_quality/local_baseline_manifest.json) · [第四阶段本地验收](../../11-15-table-value-pdf-binding-online/validation.md)

## 待授权后的验收样本与证据链

1. 在隔离验收环境用有权提交的测试 PDF 走真实 Files 上传、MinerU 解析和 Worker 归档。至少覆盖拟启用的色块分段 MIN/TYP/MAX 与普通划线 LOW/HIGH 两类。记录实际候选版本、MinerU 模型和文件结果形态，覆盖拟启用的回包入口。样本记录人工确认的源格、目标列及合法共享或歧义格。
2. 核实操作者提交给 Files 的原文件、上传登记中仅供授权读取的文件 ID、size、SHA-256，重读登记的原 PDF byte 复算。MinerU 批次从本次 job 观测，核对 `batch_id/data_id`、源 ID、原解析代及当前结果包的明确指针。若验收需声明发往 MinerU 的流也逐字节核验，以隔离探针测量实际提交前的临时文件摘要，单列证据。
3. 重读同批已登记 raw ZIP 比对 size 和 SHA-256，使用正式包选择规则核对 v2 路径及 SHA、唯一 layout 路径及 SHA，独立复算所选文档的包内原件。只有实际源 PDF 和该原件逐字节同摘要时，录为同源资格成立。回包缺原件、错 stem 或重编码导致摘要差异，记录原跨列 blocker 和 `source_pair_unverified`。已有归属或归档字节冲突走正式失败。待启用的输入类型若缺少可用的同源正例，保持停在验收门。
4. 分别保留归档证据与实物证据。回包本来就各值单列时，记录为零候选，继续选取有真实跨列的正例验证自动认证。至少取得一个真实跨列回包中资格成立且 Word 正确落位的证据；两种版式再以可重复的完整基线做相同候选 Worker 的正负控制。核对经认证的 finding、剩余 blocker、同代 Word 和报告摘要、审批发布响应。来源拒绝与真合并、压边的故意反例在隔离环境使用既有夹具。

验收摘要仅登记受控的测试样本、artifact 身份、摘要、解析代、受控原因和验收结果。原件和 ZIP 留在授权的证据存储，按保留期可追溯。
