# 线上源 PDF、MinerU 归档与执行代次

- 查询：线上原排版 Worker 在哪里取得实际源 PDF 和 MinerU 文件，哪些现有凭据足以启用第三阶段绑定，失败和恢复如何保留质量门禁。
- 范围：仓库内正式链路、规范、定向测试和第三阶段归档。只读调研。
- 日期：2026-11-15。

## 现有执行事实

| 环节 | 已确认行为 | 实现 |
| --- | --- | --- |
| 上传与绑定 | 上传完成用实际字节计算 `sha256:` 摘要，校验上传授权中的大小与可选摘要。创建任务接受同租户、同公司、未绑定且已上传的 `source_pdf`，operator 只可使用自己上传的文件。任务保存 `source_file_id`，文件绑定任务。clone 有明确的 `source_job_id` 同源父链。 | `app/domains/files/service.py:233-260`、`app/domains/document_jobs/use_cases/submission.py:131-152,346-366,454-468` |
| 提交解析 | `run_parse` 用 `source_file_id` 读取文件到临时目录，调用 `upload_files_batch`。客户端申请 URL 后实际 PUT 本地文件字节。任务按代次 CAS 保存 `mineru_batch_id`、`mineru_data_id`、回调 seed。记录里没有独立的“本次提交实际字节摘要”字段。 | `app/domains/document_jobs/mineru_execution.py:76-115`、`app/clients/mineru_client.py:91-126` |
| 获取解析结果 | 轮询核对 batch，优先精确 data ID，历史单结果且缺 data ID 时保留兼容。回调有去重、代次与阶段边界。下载前后重读当前解析代和批次并核对绝对截止期限，过期旧回调不能推进新代。poll 和 callback 共用登记函数。 | `app/domains/document_jobs/mineru_execution.py:118-162,189-201,276-286,344-354,466-527,561-606` |
| 登记归档 | 用下载的原 ZIP 字节登记 `mineru_raw_result`，文件描述含租户、公司、所属 job、类型、大小、SHA-256、生命周期。metadata 含 `source_file_id`、batch、data、解析 `retry_count`，任务由本次 CAS 固定 `mineru_raw_result_file_id`。物理对象 key 含文件 ID，已登记对象只允许同字节复用。 | `app/domains/document_jobs/mineru_execution.py:495-527`、`app/domains/files/service.py:422-467,849-875,902-918` |
| 转换入口 | `_convert_and_save_document_ir` 从归档对象读 ZIP bytes 到独占临时目录，调用 `MinerUToDocumentIRService.convert_zip`，提供原排版、翻译入口共用的 `placeholder_source_loader`。目前未传自动参数，默认 False。Worker 给 IR 记录原始 ZIP ID、登记摘要及本次转换代。**当前 ZIP reader 的显式分支只要求 uploaded，历史缺指针分支找同 job 最新归档，读取不核对实际摘要**。converter 计算了实际 `package_sha256`，当前入口没有拿它与登记摘要对账。 | `app/domains/document_jobs/execution.py:288-324,413-447,673-683`、`app/domains/document_jobs/execution_support.py:50-56`、`app/domains/files/service.py:271-280`、`app/services/document_ir/mineru_converter.py:122-151` |
| 源 PDF loader | `rendering.placeholders.load_source(job)` 已按 `source_file_id` 读同租户同公司的已上传、有效 `source_pdf`，clone 沿同源父链核验归属。慢读两侧重查文件描述和当前执行代，核对实际长度与 SHA；返回带 ID、摘要、字节的 `PdfCropSource`。converter 用 cache 给同次图片回退、占位和自动绑定共用。 | `app/domains/document_jobs/render_placeholders.py:40-95`、`app/services/document_ir/mineru_converter.py:233-237,411-432` |

## 可复用的同源门槛

1. **任务和对象层**。只从本次信任的 Job 快照取源 ID、明确归档 ID 和批次，不接受客户端传入文件 ID、路径或 URL。自动资格要求原件走已核验 loader，归档 ID 来自任务指针，文件归属、角色、MIME、uploaded、未过期及无删除占用与当前 job 相符，raw metadata 的 source、batch、data、解析代次可核对，重算读到的 ZIP 字节长度和 SHA。慢读前后核对同代、文件描述及指针，原执行阶段和代次 CAS 仍决定结果能否成为当前 IR。对无明确指针或元数据不足的历史文件保留旧转换能力，自动修正资格不成立。明示的跨任务、越权或实物与登记摘要不符是正式输入完整性失败，不能拿该 ZIP 做可审批结果。可复用受控读取/比较模式，ZIP 仍只由正式 converter 展开。相关实现见 `app/domains/document_jobs/render_placeholders.py:40-69`、`app/domains/document_jobs/use_cases/table_references.py:121-159,191-216` 和 `app/domains/document_jobs/execution.py:436-449`。
2. **包内容层**。沿用 converter 的有界 ZIP 展开与唯一结果根。先据现有规则实际选定 v2，保存其真实字节摘要，再由 `_paired_origin` 在同目录按同文档名找规范原件（具前缀时为 `<stem>_origin.pdf`，无前缀时为 `origin.pdf`），SHA 必须和经核验的源 PDF 字节一致。同文档 layout/middle 也须唯一，能与 v2 表、归一化坐标、实际 PDF 页框一一对账，才继续 Poppler。批次、data ID、同名文件、相同页数、提取文字一致或其他 PDF 版本均不足以补此环节。无需在 Worker 写第二份解包或匹配逻辑。相关实现见 `app/services/document_ir/mineru_package.py:189-215`、`app/services/document_ir/layout_signals.py:293-313`、`app/services/document_ir/pdf_value_column_review_flow.py:34-77,93-129`。
3. **来源留痕**。既有 IR 报告保存实际 `package_sha256`、选用列表路径和 `content_list_sha256`。`mineru_validation_input` 保存登记 ZIP ID、SHA 及本次转换 `retry_count`。单格内部校核保存源 PDF、所选列表、表格、布局和原格证据。优先复用这三层；保留 ZIP 文件记录中原解析代字段。若确需额外数据，勿向既有 `mineru_validation_input` 随手加键，`TableReferenceProvenance` 对该字典按三键严格校验。相关实现见 `app/services/document_ir/mineru_converter.py:136-151`、`app/services/document_ir/models.py:155-179`、`app/services/document_ir/pdf_value_column_review_flow.py:166-180`、`app/domains/document_jobs/use_cases/table_references.py:139-159`。
4. **资格范围**。建议线上首版在原排版 `direct_pdf_to_word` 的正式转换调用点受内部开关控制，保留第三阶段的同源判定及内部 `pdf_binding` 生成权。已有 IR 或 DOCX 的恢复按既有认证读回，不在历史文件上追加校核。关闭开关的旧数据仍按当前输入、质量和交付合同读取。相关入口见 `app/domains/document_jobs/models.py:132-155`、`app/domains/document_jobs/execution.py:288-324,403-411`。

## 不可用、错误和恢复

- **可选取证不可用**。包可用于正式转换但缺匹配原件、原件 SHA 不同、布局缺失/歧义、PDF 不可读、行列或字形证据不足时，自动资格失败；可定位的原跨列 blocker 保留，并以原 finding ID 填充 `metadata.pdf_value_column_unresolved`。第三阶段已为包配对、布局、几何、观测的未决路径做到这一点。**直接在 Worker 传 True 有已知异常类型不匹配**：自动入口仅捕获 `TableValueColumnReviewError`，线上 `load_source` 的缺失/失效会抛 `TablePlaceholderError` 并触发 `ir_converting` 失败。需仅在可选自动取证边界窄处理已识别的来源不可用；若来源另被占位、裁图、降级或显式人工校核所必需，按其原合同失败。当前自动入口开启就会调用源 loader 一次，线上实现应保证只在有现行跨列候选时做可选慢读，或明确验收该额外读开销。相关实现见 `app/services/document_ir/pdf_value_column_review_flow.py:131-192,195-214`、`app/services/document_ir/table_value_column_review.py:220-230`、`app/domains/document_jobs/render_placeholders.py:57-95`、`app/domains/document_jobs/execution.py:313-324`。
- **正式输入损坏**。ZIP 无法展开、唯一性违规、被选 JSON 非法、身份或实物摘要攻击按正式输入错误分类。布局文件缺失和“唯一布局文件本身 JSON 坏掉”是两类场景，后者现在也从 `read_json_payload` 抛原 `MinerUPackageError`。已发起的人工核定仍整批校验，源文件/HTML/原格变化或伪造自动出处时不附加任何校核。相关实现见 `app/services/document_ir/mineru_package.py:183-215`、`app/services/document_ir/mineru_converter.py:140-168`、`app/services/document_ir/table_value_column_review.py:233-270`。
- **解析代与转换代**。失败重试递增工作代，明确持有的归档、IR、主件分别使恢复从 `parsed`、`rendering`、`uploading` 继续。故在实际需要重新转换时，可按当前明确指针重验同任务的旧解析 ZIP，须核对绑定且解析代不晚于本次转换代。不能靠按时间找最近 ZIP 来获得自动资格。已有 IR/Word 继续经原完整性和结果选中合同，不能借开启时点回填。成功任务的现有 admin `new-generation` 则清除原 ZIP/IR/Word/批次，重新解析；要在确定的同一 ZIP 上回放人工校核需要显式设计，现有普通 retry 限 failed。相关实现见 `app/domains/document_jobs/use_cases/submission.py:175-225,391-452`、`app/domains/document_jobs/use_cases/read_model.py:313-324`、`app/domains/document_jobs/new_generation.py:144-189`。
- **线上渲染降级的具体缺口**。如果带未决项的表格因渲染失败进入整页降级，`drop_degraded_table_groups` 当前删组时没有同步移除这些组的 `pdf_value_column_unresolved`，IR 重验会拒绝悬挂片段 ID。接入需按同一个被删除的片段闭包维护投影，保留未降级页的未决项，并继续使用整页降级质量 blocker。无需制造原格已认证的记录。相关实现见 `app/services/document_ir/page_degradation.py:127-150`、`app/services/document_ir/logical_table_group.py:464-469`、`app/domains/document_jobs/render_execution.py:227-243`。

## 已测、拟验收与资料边界

- 已有本地正式 worker 测试通过 Mock MinerU 登记和读取 raw ZIP、IR、Word；下载边界测试分别覆盖轮询与回调；已有翻译失败续跑测试保持来源 IR。它们能作为阶段/血缘合同的回归入口。参见 `tests/test_fastapi_jobs_backend.py:9318,10112`、`tests/test_mineru_download_boundary.py:317,336`。本次未重新运行。
- 第三阶段已有独立划线 LOW/HIGH 实际 Poppler→Word，另有缺/错原件、布局歧义、证据仅可选、人工记录陈旧/伪造的定向测试。完整本地 `gs-008` 两次使用缓存包内原件文件作显式输入，23 个原发现保留，实物认证 9 项，14 项阻断；同名同文字但摘要不同的仓库 PDF 保留全部 23 项。参见 `tests/test_table_value_pdf_binding_poppler.py:65`、`tests/test_table_value_pdf_binding_integration.py:109,128,171` 和第三阶段归档 `.trellis/tasks/archive/2026-11/11-15-table-value-pdf-binding/validation.md:17-38`。
- 拟使用同一正式 Worker，将两种离线 fixture 经过现有上传和 fake MinerU 传输边界完整登记，实际运行绑定、Word 和审批发布读回。源负例至少含：同名同字异源、缺原件、错 stem、缺/重复布局、已登记 ZIP 字节变化、旧代未绑明的 ZIP、已明确绑定的旧解析 ZIP 续跑、取证缺源与必需裁图缺源的不同处理，以及上述降级回归。
- 现在只能证明代码请求与归档合同、离线 fixture 及第三阶段本地缓存。尚未验证当前生产 MinerU 每种模型、结果模式和批次是否提供完整所选 v2、唯一布局、同名原件，且归档原件是否与**实际上传** PDF 字节一致。生产采样属于以后启用前另行安排的运行证据；若上游重编码或不提供原件，本版本记未决，不能拿上述离线回放证明线上可自动覆盖。仓库 worker 镜像声明已安装 Poppler `poppler-utils`，当前 readiness 探测主要指向 `pdfinfo` 与 `pdftoppm`；绑定实际需要版本同源的 `pdfinfo`、`pdftotext`、`pdftocairo`、`pdftohtml`。运行时应在测试容器验收实际工具和预算。参见 `docker/prod/Dockerfile:10-12`、`docs/runbooks/backend.md:90` 和第三阶段归档验证。
- 相关规范：`PIPE-001`、`INPUT-001`、`INPUT-002`、`IR-002`、`TABLE-001` 与表格占位失败合同。参见 `.trellis/spec/backend/word-generation-rules.md:39-49,64-88,394-400,433`、`.trellis/spec/backend/error-handling.md:154`。
