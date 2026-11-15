# 研究：来源绑定与同源重跑入口

- 查询范围为第二阶段人工数值列校核的入口、来源身份和拒绝条件。
- 依据为当前分支的仓库代码、现有校核用例和第一阶段验收记录。
- 日期为 2026-11-15。

## 已确认的入口和合同

| 入口或机制 | 当前事实 |
| --- | --- |
| `TableHeaderReview` | 严格模型绑定 PDF SHA-256、content list SHA-256、源表 JSON Pointer、零基页号及原 HTML SHA-256。处理器从实物重算 PDF 指纹，核对当前 IR 的源文件身份和已定组的来源片段。未找到、重复或不匹配均拒绝。见 `app/services/document_ir/table_header_review.py:18`、`:26`、`:47`。 |
| MinerU 转换 | 转换服务从解包后实际选中的内容列表文件计算 SHA-256，构建来源账本，使用单次调用内的 PDF loader。在表格已定组后接收表头校核，最终 IR 重读及来源检查通过后才返回。见 `app/services/document_ir/mineru_converter.py:121`、`:138`、`:228`、`:404`。 |
| 本地正式转换 | `run_local_mineru_conversion.py` 接收 MinerU 目录或 ZIP，显式传入 `--source-pdf`、`--table-header-reviews`。它读取实际 PDF 字节，传给与 Worker 共用的转换、渲染和证据核心，校核及渲染证据通过后写入 IR 与 DOCX。CLI 的 `ValueError` 边界退出非零。见 `scripts/dev/run_local_mineru_conversion.py:36`、`:136`、`:166` 与 `scripts/dev/formal_mineru_conversion.py:213`。 |
| 线上 Worker | 从已登记的 MinerU 文件读取 ZIP，传入真实 PDF loader，调用处无 review 参数。PDF loader 核验文件类型、归属、有效期、文件记录及实物指纹。已存在最终 IR 或源 IR 时允许跳过转换。见 `app/domains/document_jobs/execution.py:288`、`:304`、`:673` 与 `app/domains/document_jobs/render_placeholders.py:62`、`:71`、`:92`。 |
| 普通重试与新代 | 普通重试只面向可重试失败，按已存在的 Word、IR、MinerU 原始产物选取恢复阶段。Admin 新代接纳检查源 PDF 字节与请求版本，随后清空 MinerU 原始文件、IR 与结果指针，从 `uploaded` 重来。已有操作都无法表达「本次显式加载校核记录，并以这份确切的 MinerU 原始结果重新构建 IR」。见 `app/domains/document_jobs/use_cases/read_model.py:313`、`app/domains/document_jobs/use_cases/submission.py:443`、`app/domains/document_jobs/use_cases/publication.py:145`、`:232`、`:256` 与 `app/domains/document_jobs/new_generation.py:154`、`:180`。 |

## 建议的首版交付边界

1. 通过现有本地正式转换入口显式传入数值列校核 JSON 和源 PDF，重跑时复用同一份记录和保留的 MinerU 结果包。入口仅选择和读取记录，来源核验及 Grid 投影由共用核心完成。保留首次核验的来源指纹、校核记录和应用结果，在输出中记录可核对的修正身份。
2. 采用 `TableHeaderReview` 的五个来源字段。单元格额外绑定源行、源单元格序号及预期原列范围，并比对原 cell 内容指纹。目标用零基列索引和人核定的目标列标题同时表达。已有 fragment ID 由 content list 指纹和 Pointer 派生，cell ID 由 fragment 和源序号派生，内容指纹独立于列位置。见 `app/services/document_ir/logical_table_group.py:46`、`:505` 和 `app/services/tables/models.py:46`、`:200`。同一源字节可跨执行 ID 复用，依旧由本次可信 loader 验证文件归属。记录自己的 schema 版本，重建时对原跨度及列标题做前置核对。用 Grid 的解释版本或锚点校验防止同字节在规则升级后落到不同格位。
3. 全批校核在生成产物前验证。已明确选择的记录若找不到表／单元格、出现重复、超出原跨度、目标标题不符、源校验失败或只有部分可用，整次拒绝并返回稳定原因。无校核输入仍走原有转换。后续重读以已验证的来源事实与产物绑定为据，保留原 HTML 和历史证据。现有逻辑表重读已重算 HTML 指纹并校验表头记录的 fragment 身份，见 `app/services/document_ir/logical_table_group.py:505`。
4. 将 content list 实际字节作为 MinerU 版本的主锚。目录输入会被 CLI 重新压包，见 `scripts/dev/formal_mineru_conversion.py:401`，ZIP 容器指纹可作为本次产物的证据。采信同源时同时核对原表、原格、原跨度及目标列。若往后要严格锁指定的线上 ZIP，则复用已登记的 raw 文件 ID 与实际 checksum，且要在接受修正的操作中冻结它们。

本地正式转换完成后得到可核对的结果稿。线上交付所需的接纳操作仍应由受权人提交，绑定租户、原 PDF、原始结果和本次新生成凭据。若介入现有新代操作，需要由应用层冻结校核记录身份和保留包，明确从 IR 前重走，并由现有审批发布规则读取本代实际证据。禁止以改历史结果、人工覆盖质量级别或从可变目录自动挑最新记录替代。基础质量从已登记表格证据汇总所有 blocker，见 `app/domains/document_jobs/base_quality.py:198`、`app/domains/document_jobs/use_cases/review_writer.py:73` 和 `app/domains/document_jobs/use_cases/publication.py:485`。

## gs-008 可执行验收

用 `tests/fixtures/datasheet_quality/local_baseline_manifest.json:99` 固定完整输入。第一阶段已有两个值及保留单位的片段对照见 `tests/test_table_value_column_span_delivery.py:103`。第二阶段沿用原始错误 HTML 和来源清单，只由校核 JSON 驱动位置变化。

| 对照输入 | 可观察结果 |
| --- | --- |
| 同一 PDF、同一 MinerU 内容列表、同一记录连跑两次，使用新输出路径 | 两次报告同一应用身份，`±5 µV` 单独位于 TYP，`±100 µV` 单独位于 MAX，实际 OOXML 单元格跨度为 1。原始 HTML、内容指纹、其余值与单位保持。比较结构及可复验的校核证据。 |
| 保留 MinerU 包与旧记录，替换为另一份可读 PDF，重算该次 loader 的实际 PDF checksum | loader 自身完整性正常，校核报告 PDF 指纹不匹配，退出非零，空输出目录无本次 IR／DOCX。 |
| 保留 PDF 与旧记录，在临时包中重序列化仍合法的 content list 或改变其中表格 | 应在计算真实 content list 指纹后拒绝旧记录。仅重打包而文档来源不变不能代替本例。 |
| PDF、content list 指纹均正确，单独改变记录中的原 HTML 指纹、表 Pointer／页号、cell 内容指纹或预期跨度 | 每次命中对应的表／cell 来源约束。实际 HTML 改动也会先改变 content list 指纹，独立变更记录可确保各层防线都被检验。 |
| 将一条正确记录与一条缺目标、重复或目的列不合法的记录一起提交 | 整批失败，无部分应用产物。同样场景移除记录重跑时，原跨列规则正常报出。 |

完整样本第一阶段有 23 个跨列 blocker。两条已核定记录只证明这两处的正确性，完整样本的其他 blocker 应继续进入交付门禁。若需要回归未受阻的结构对照，用已知的两行片段验证，线上全量交付依赖完整审批及其他质量证据。

## 相关规范与资料

- `.trellis/spec/backend/word-generation-rules.md:371` 的 TABLE-001 定义 span 和正式渲染 owner，`:397` 的 TABLE-003 定义表头校核及现有重读。
- `.trellis/tasks/11-11-datasheet-quality-baseline-contracts/table-header-review.md:13` 记录同源表头校核命令和结果分层。
- `tests/test_table_header_review.py:127` 可复用来源指纹、重复、定位异常的覆盖模式。当前调研以仓库内证据为准，未依赖外部版本或 PDF 坐标能力。
