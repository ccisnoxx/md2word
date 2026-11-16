# Research: 线上 Word 实物认证、质量贡献与交付

- 查证范围为当前分支的正式渲染、结果登记、质量读取、复核及发布执行路径。
- 证据来自本地源码、Trellis 合同与已存在的测试代码。
- 日期为 2026-11-15。

## 已确认链路

### Word 实物认证

- `app/domains/document_jobs/render_execution.py:136` 的 `render_and_save_word` 先查本代运行态与已选 receipt。渲染使用任务当前最终 `document_ir_file_id` 实际字节，按本次模板资源形成 `DocumentIRWordRenderer.render_to_result`。读取与调用可见 `render_execution.py:193`、`render_execution.py:209`。
- 正式生成在 `quality_checking` 中传本次 `render_result` 和实际 Word 字节给 `build_renderer_evidence`，再调 `ensure_renderer_integrity`。可见 `app/domains/document_jobs/render_execution.py:284`。
- `app/services/renderer/content_contract.py:450` 根据同一 IR 重建修正后的原生表计划，检查实际表数量、span、顺序、公式及占位。实物通过后，`verify_native_content` 核验累计 `w:gridSpan` 定位的实际格位、数值所属格及释放空格，再生成表格报告。实物检查可见 `content_contract.py:384`、`content_contract.py:405`、`content_contract.py:419`。
- `app/services/renderer/table_content_evidence.py:183` 的 `_value_column_corrections` 从已认证计划获得源 finding ID、原列区间、目标列、实际表和行，以及自动核定的 `pdf_binding_sha256`。`_build_table_evidence` 保留 `validation` 中完整的原始源报告，并且只在 `flags` 排除已认证 ID，见 `table_content_evidence.py:207`、`table_content_evidence.py:223`、`table_content_evidence.py:265`。`app/services/tables/evidence.py:238` 再校验更正与源格、实际行及各独立列的对账，`evidence.py:339` 校验现有 `table_validator` flags 与原 findings 减去该集合完全一致。
- 两类结果的处理不同。来源未获证、无法确认独立行列或其他第三阶段未决保留原 span 和表格业务 blocker；这样的 Word 仍可通过实物完整性门禁并成为内部草稿。实际 DOCX 错列、未释放原格或证据不闭合触发现有内容完整性失败，在正式候选登记前记为 `quality_checking/render_failed`。参见 `app/services/renderer/render_evidence_validation.py:29`、`app/domains/document_jobs/render_execution.py:294`。不得把原业务 blocker 混入 `blocking_quality_flags`，后者用于阻止不完整实物进入登记。

### 产物身份、重读和重新执行

- `app/domains/document_jobs/render_execution.py:327` 依次保存独立表报告、渲染出处、Word pending 候选，重读实际报告/IR/Word 核验后再争取本代 receipt。候选描述包含 `source_file_id`、最终 IR 文件 ID、`retry_count` 和 `renderer_metadata`。Word、报告及报告中的 IR/Word 摘要分别被绑定，报告保留期至少覆盖 Word。可见 `app/domains/document_jobs/table_evidence.py:108`、`table_evidence.py:126`。
- `app/domains/document_jobs/table_evidence.py:190` 的 `verify_report` 读取同任务租户/公司/文件类型、实际字节长度和摘要，校验报告 envelope 的 source、generation、IR、报告版本与结果身份。由当前 IR 和实际 DOCX 调 `validate_persisted_renderer_content` 重建报告后逐值等于登记的报告，I/O 两侧核当前快照与依赖文件可用性，见 `table_evidence.py:169`、`table_evidence.py:223`、`table_evidence.py:248`。此重建重放的是已保存的 IR 和 Word，恢复与发布无需重新跑 Poppler 或 MinerU。`app/services/renderer/render_evidence.py:409` 拒绝含列核定却缺显式 v2 的降级，并拒绝保存内容与实际重建不一致。
- `app/domains/document_jobs/result_state.py:59` 在任务序列化点按本代、当前最终 IR、running/uploading、未超时与合法摘要选第一个 receipt。后续同代恢复物化唯一已选候选，复查报告、最终 IR、实际 Word 与预览，最后 CAS 写回 `result_file_id`、`succeeded/completed`。参见 `app/domains/document_jobs/render_result.py:70`、`render_result.py:100`、`render_result.py:127`。同代竞争落败返回当前权威状态，损坏的已选产物不回退成另一个候选。结果/代次改变失效旧复核和质量，已发布状态只允许归档 metadata。参见 `app/domains/document_jobs/delivery_state.py:22`、`delivery_state.py:41`。
- 历史明确主件指针和唯一可验证 legacy 候选继续走旧读者。多候选、过期、错误代次或错误 IR 不猜测，也不借删除新版字段变回 legacy。参见 `app/domains/document_jobs/render_result.py:178`、`render_result.py:197`。常规 `retry_job` 只接 failed 且原子进入下一代并安装 fresh base marker，见 `app/domains/document_jobs/result_state.py:167`。需要人工核定的 `succeeded/blocked` 内部件不能直接调用 failed retry，也不能原地替换已选 receipt、IR 或 Word。

### 基础质量、复核与发布门禁

- 完成 CAS 仅从本代选定的 receipt 消费表报告并登记 `quality_summary.table_evidence`。有 base 槽的任务由 `derive_base_quality` 将表证据的剩余 blocker、warning 数及 issue codes 纳入基础贡献，缺证据为 incomplete，存在 blocker 时 `blocked` 优先。旧无 base 槽的结果消费报告时能补 blocker。参见 `app/domains/document_jobs/result_state.py:103`、`result_state.py:126`、`app/domains/document_jobs/base_quality.py:114`、`base_quality.py:198`。普通补丁不能修改或删除有 owner 的 `checks_v1` 槽，合并优先级 blocked、pending、warning、passed，见 `app/domains/document_jobs/quality_state.py:19`、`quality_state.py:39`。
- `PATCH /api/v1/document-jobs/{job_id}/review` 先查任务权限和期望源，`approved` 分支见当前有效 `blocked` 返回 HTTP 409 和 `review_quality_blocked`。非阻断路径核对当前主 DOCX、实际字节 hash、受控 metadata、receipt、复核来源序号和表渲染证据。锁内再次核任务代、结果、receipt 和有效质量。参见 `app/domains/document_jobs/quality_review_router.py:121`、`app/domains/document_jobs/use_cases/review_writer.py:56`、`review_writer.py:112`、`app/domains/document_jobs/review.py:216`。批准复核与提交逐格人工核定是不同动作。当前非 `blocked` 的 pending 可以完成内部批准，发布要求更严格。
- `POST /api/v1/document-jobs/{job_id}/publish` 要求内部 Admin 用户 JWT、发布开关、当前任务成功、质量 passed/warning、绑定实物的有效批准与已确认预览。有效质量为 blocked 时在先决条件中返回 HTTP 409 和 `publication_quality_blocked`。`prepare_publication_evidence` 在锁外重读原 PDF 与提交快照、当前主 Word、IR、预览、独立表报告与渲染出处。发布仓储锁内再比任务快照与全部依赖文件状态，原子写入不可变发布记录与审计。参见 `app/domains/document_jobs/use_cases/publication.py:458`、`app/domains/document_jobs/publication_evidence.py:28`、`publication_evidence.py:71`、`app/domains/document_jobs/publication.py:122`。
- `review_writer` 当前批准路径读取已登记主 DOCX/hash/receipt 和有效质量，并未重读独立表报告及 IR。独立报告事后损坏由表格证据读口和发布认证发现。若第四阶段要求新增产物在这类证据事后失效时连批准也必须拒绝，建议只在新增结果的批准分支复用已有 `verify_report` 和快照复查，保留原有旧产物规则。发布路径 `publication_evidence.py:71` 的 `verify_report` 错误未独立映射为固定 publication reason，不能将损坏报告/原件消失都宣称为 `publication_quality_blocked`。确定性的已登记业务 blocker 才对应上述固定质量拒绝原因。
- 完整但质量 blocked 的结果可以授权生成内部排查下载，分类为 `internal_only`、警告 `quality_blocked_not_deliverable`。未选或未完成的候选不会在普通任务文件/令牌下载暴露。预览凭当前主件与已确认预览证据授权。参见 `app/domains/document_jobs/use_cases/read_model.py:184`、`app/domains/document_jobs/use_cases/access.py:151`、`app/domains/document_jobs/use_cases/downloads.py:106`、`app/domains/document_jobs/preview_evidence.py:139`。

### 未决条目的人工定位

- 第三阶段 `DocumentIR.metadata.pdf_value_column_unresolved` 保存 finding ID、fragment ID、片内源行/源格及原因。`app/services/document_ir/table_value_column_review.py:80` 和 `app/services/document_ir/logical_table_group.py:464` 提供内层合同，后者核查唯一性、片段归属并排斥同格既待核定又已修正。
- `GET /api/v1/document-jobs/{job_id}/quality/tables` 已有租户权限、快照和报告哈希分页，读时复验报告并按白名单投影。当前公开 flag 只含 producer、code、severity、fragment ID，未给按格核定所需的 finding ID、源行、源格和未决原因。参见 `app/domains/document_jobs/quality_review_router.py:58`、`app/domains/document_jobs/use_cases/quality_review.py:167`、`quality_review.py:303`、`app/domains/document_jobs/quality_review_projection.py:163`、`app/domains/document_jobs/views/quality_review.py:240`。
- 建议从 `verify_report` 已重读并认证的 IR 内部返回待人工核定事实，按本代和原报告的 finding ID、fragment/源格匹配剩余原 blocker，再从既有表质量读口作最小可审分页投影。公开稳定定位（原页、片段、源行、源格、原列范围、原因码），原始 PDF/HTML、存储地址、全部 IR 和自动出处 payload 沿现有受权文件读法处理。缺旧字段保持兼容，不能把未核定项作为额外的质量打分或允许人工直接改 `passed`。`findings` 明细读视图、记录来源身份与核定写流程应由同一受权用例统一绑定。
- 线上渲染已有整页降级路径。其 `drop_degraded_table_groups` 会删除原表组，但当前不会同步处理新增的未决片段引用。遇到涉及未决条目的页降级时，`DocumentIR` 重校验可拒绝该降级并维持原失败契约。已有可成功落盘的整页降级计独立基础 blocker，不能以栅格图作为数值列修正实物。参见 `app/domains/document_jobs/render_execution.py:376`、`render_execution.py:405`、`app/services/document_ir/page_degradation.py:127`、`app/domains/document_jobs/base_quality.py:135`。首版可以沿现有失败路线并补定向反例，避免为了降级而丢弃人工核定事实。

## 推荐验证

| 核验目标 | 最小可复用的现有证据 |
| --- | --- |
| 原生 Word 和正反列归属 | `tests/test_table_value_pdf_binding_poppler.py:19` 生成同源 PDF + MinerU ZIP 的完整黑线 LOW/HIGH 版式。确认 7.2e-4 → HIGH、43 → LOW、压线 48 未决，使用真实 Poppler 和重读实物。第三阶段归档 `validation.md` 有完整 gs-008 MIN/TYP/MAX 表的另一种色带和分段线版式。可用同源完整 gs-008 回放，或用仓内独立可复现的第二种几何夹具作为自动测试的永久输入。 |
| 正式任务含原 blocker 的审批、发布和内部下载 | `tests/test_table_value_column_span_delivery.py:43` 与 `tests/document_job_list_query_v2_publication_fixtures.py:91` 已通过真实应用和 TestClient 拉起 Worker 执行、登记主件、下载 DOCX、审批准入、Admin 发布拒绝。仅替换外部 MinerU/预览输入并传实际同源配套字节，保留真 Word、base、API、状态仓储。现有 `_gs008_package` 是表片段，不含可自动绑定的同源 PDF。 |
| 解除集合正例及发布通过 | 同一套场景准备完全证实的表和合法资源、确认预览，核对原报告 finding 仍保留、交付 flags 恰好移除 certified IDs。证明 fresh base 从实际结果产出 passed/warning，批准再发布。现有 `publication_runtime` 默认 `legacy_base=True` 会删 fresh 槽，`runtime` 也会显式写入 `quality_status`。不可利用这些手设状态冒充新结果自证。参见 `tests/document_job_list_query_v2_publication_fixtures.py:104`、`document_job_list_query_v2_publication_fixtures.py:113`。 |
| 物化后可验证及错误位置失败 | `tests/test_table_value_pdf_binding_delivery.py:129` 覆盖报告中绑定摘要篡改、实际值交换并重新计算覆盖证明后仍拒绝。它替换了 PDF observation/matcher，只适合隔离认证边界。结合 `tests/test_document_job_execution_stages.py:212`、`test_document_job_result_persistence.py:427`、`test_document_job_result_persistence.py:897` 核对 quality_checking 先于登记、错误代/生成中的取消或超时、receipt 丢响应仍只物化同一文件。 |
| 证据失效及历史兼容 | 原文件不同、直接接受陈旧手工记录、手工记录与现有结果代次冲突、独立报告损坏、候选 Word 错列均不能解除原 blocker 或发布。检查开关关闭、旧件默认读取、同代恢复不改内容和此前已发布件保持不可变。普通审批允许性与发布允许性独立断言。 |

## 相关合同和边界

- `.trellis/spec/backend/word-generation-rules.md:371` 的 TABLE-001 及人工核定与同源自动核定子节。
- `.trellis/spec/backend/document-job-mode-contract.md:134` 的结果候选、控制面及下载可见性。
- `.trellis/spec/backend/error-handling.md:269` 的结果竞争与真实错误及 `error-handling.md:279` 的 CON-103/104。
- 本记录没有执行任何测试或观察实际线上环境。上述 fixture、API 分支与同代约束均从当前源码读取。已归档的第三阶段实测只证明本地 Poppler、正式渲染和实物验证，线上运行条件需要第四阶段的对应验收。
