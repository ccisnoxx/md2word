# 审批证据重核的并发边界

- 核对参数值列修正的审批重核窗口和审批、发布门禁。
- 依据第四阶段已归档代码、三种仓储、现有回归与交付规范。
- 调查日期为 2026-11-15（Asia/Shanghai）。

## 调查结果

### 审批当前实际保护的范围

- 正式 `PATCH /api/v1/document-jobs/{job_id}/review` 要求用户登录及 `expected_source`，由授权用例调用共用 writer。writer 校验主件、代次、质量及 receipt。主件或 receipt 任一声明参数值列修正时，批准前认证独立报告、最终 IR 和实际 DOCX。兼容内部入口共用 writer，可省略 `expected_source`，沿用其错误体约定。见 `app/domains/document_jobs/quality_review_router.py:121`、`app/domains/document_jobs/use_cases/quality_review.py:289`、`:358`、`app/domains/document_jobs/use_cases/review_writer.py:60`、`:93`、`:107`。
- `verify_report` 逐件核对文件归属、有效期、状态、实读长度和 SHA-256，然后重建 IR 与实际 Word 的渲染证据。返回的 `VerifiedTableEvidence` 带有当前 job 和三份文件登记快照。`recheck_verified_report` 在应用层再次读取任务和文件描述，比较有效期、删除预留和状态。最后一轮重读与仓储调用相邻，仍属于不同序列化点。见 `app/domains/document_jobs/table_evidence.py:180`、`:218`、`:234`、`:249`、`:273`、`:297`、`app/domains/document_jobs/use_cases/review_writer.py:159`。MySQL 的重读走独立连接和普通查询，SQL 投影未就绪会显式失败。见 `app/infrastructure/persistence/mysql/document_jobs.py:134`、`app/infrastructure/persistence/document_job_list_query.py:104`。
- `update_document_job_review_if_current` 在 MySQL 中只对 job 行 `FOR UPDATE`，在 file 用稳定 `job.lock`，在 SQLite 的 `BEGIN IMMEDIATE` 写事务内只读取 job 与复核记录。域函数 `submit_review` 核对删除或发布状态、代次、主件 ID、receipt 摘要、当前任务状态和质量，再追加不可变复核记录。该路径没有读三份当前文件行，SQLite 的单写者也覆盖不到进入写事务前的窗口。现在的有效复核投影依赖主件绑定、状态和摘要，报告或 IR 单独失效时仍可能显示有效批准。见 `app/infrastructure/persistence/mysql/document_jobs.py:97`、`:214`、`app/infrastructure/persistence/file/document_jobs.py:93`、`:217`、`app/infrastructure/persistence/sqlite/document_jobs.py:97`、`:212`、`app/domains/document_jobs/review.py:216`、`:265`、`app/domains/document_jobs/use_cases/access.py:48`。
- 现有回归覆盖缺失或损坏的报告，以及在 `verify_report` 返回后、最后重读前修改报告的 409。第四阶段记录明确保留了最后重读之后的窗口。见 `tests/test_online_table_value_quality.py:116`、`:138`、`.trellis/tasks/archive/2026-11/11-15-table-value-pdf-binding-online/validation.md:28`、`:30`。

### 可以控制的并发交错

1. 审批 A 已通过最后一轮应用层重读，在调用 `update_document_job_review_if_current` 前停住。独立 writer B 仅改变该代 report 或最终 IR 的登记元数据并提交，原 job、receipt、主 Word 及其字节保持原观察。释放 A 后，第四阶段仓储检查仍满足，会追加 `approved`。可用真实文件仓储的 `reserve_document_file_deletion` 搭屏障。它接受尚未发布保护的 `uploaded` 文件，单独写该文件的 `deletion_claim`。测试只预留隔离样本，真实任务删除 HTTP 入口会先提交 job 的 `deleted_at`，那一类竞争已在现有 job CAS 中拦截。见 `app/domains/files/result_registration.py:120`、`app/infrastructure/persistence/mysql/files.py:131`、`app/infrastructure/persistence/file/files.py:102`、`app/infrastructure/persistence/sqlite/files.py:123`、`app/domains/document_jobs/use_cases/lifecycle_commands.py:153`。
2. 正式保留期存在独立的 IR 失效路径。IR 以自身登记时间计算 TTL，随后生成报告和 Word，报告期限按规则至少等于 Word。在隔离环境安排 IR 最先到期，在 A 最后重读后推进可控时钟，B 走 `DocumentFileRetentionPlanner.mark_expired`，即可只使 IR 失效。也应覆盖只跨 IR 的时间边界、尚未运行清理时，锁内以取得锁后的时间拒绝。用报告的独立元数据变更验证报告竞争，符合其保留期合同。见 `app/domains/document_jobs/execution.py:478`、`app/domains/files/service.py:437`、`app/domains/document_jobs/table_evidence.py:146`、`:273`、`app/domains/files/retention.py:114`。
3. 独立报告、IR、DOCX 的实物判断以文件身份和内容 SHA-256 为锚。生成件使用独立 file_id 路径，受控删除先取得文件删除预留再移除字节。实物核验之后以 metadata 锁重核的依据，是此期间同一对象的物理字节不会绕过仓储被覆盖或清除。活动存储需要核对生成件可用期内的对象覆盖权限及外部生命周期策略。候选环境应留有报告、IR、Word 三份实读摘要与存储保护证明。直接改对象而登记完全不变时，已完成的摘要读取与后续行锁无法观察该变化。损坏发生在实读前属于独立负控，应由摘要校验发现。见 `app/domains/files/service.py:271`、`:405`、`:673`、`:849`、`app/domains/document_jobs/table_evidence.py:258`。

### 灰度前的最小改法

- 对已声明且经过实物核验的值列修正审批，将内部 job 比对字段和三份已认证文件快照传给现有仓储写入口。实物字节、sha256、IR 与 Word 重建继续在获取锁前执行。仓储直接读取当前 job 与文件行后在同一个提交点比较 `table_evidence_snapshot_values` 的字段、三份完整登记描述、状态、删除预留与当时有效期。把权限与既有 generation、result、receipt、质量 CAS 留给现有判断，按现有语义给任务来源或状态变化返回各自 409，并给依赖快照失效返回 `409 review_result_integrity_conflict`。锁内判定通过才追加历史及更新当前指针。内部快照由服务端从已验证证据生成，`ReviewExpectedSource` 对外字段与请求摘要约定沿用现状。旧调用、无修正和非批准状态走既有分支。见 `app/domains/document_jobs/review.py:32`、`:136`、`:216`、`app/domains/document_jobs/repository.py:242`、`app/domains/document_jobs/use_cases/review_writer.py:151`。
- MySQL 复用发布的顺序及当前读，先锁 job 行，再对去重排序后的文件主键逐一 `SELECT … FOR UPDATE`，全部在同一连接、同一短事务。若读取保护状态或其他一致读，放在全部文件锁之后，避免等待期间沿用早建的 RR 快照。SQLite 在现有 `BEGIN IMMEDIATE` 同连接读取。file 沿既有 `publication-lifecycle.lock → job.lock → 依文件 ID 升序的 .lock` 顺序，并持有到写入提交。取实际当前时间时应已取得依赖锁。锁内仅访问必要仓储事实，使用当前连接与已锁定状态完成比对。见 `app/infrastructure/persistence/mysql/document_jobs.py:325`、`app/infrastructure/persistence/mysql/backend.py:61`、`:65`、`app/infrastructure/persistence/sqlite/document_jobs.py:318`、`app/infrastructure/persistence/file/backend.py:39`、`app/infrastructure/persistence/file/document_jobs.py:303`。同包新代接纳的并发矩阵另见本任务对应研究。
- 发布拥有独立门禁，正式发布重新认证上传源、Word、预览、IR、表格报告及渲染 provenance，并把认证件纳入发布依赖。发布仓储对当前 job 摘要、文件集合及描述、有效性、有效批准和预览状态再做锁内比较。保持这一交付链，审批补强后的成功只能代表批准提交当时成立。见 `app/domains/document_jobs/publication_evidence.py:28`、`:71`、`:133`、`app/domains/document_jobs/use_cases/publication.py:506`、`:531`、`app/domains/document_jobs/publication.py:122`、`:147`。
- 发布的 HTTP 边界要区分触发时点。文件仍在登记、却在实物认证完成后被预留或变更时，锁内预期 `409 publication_result_unavailable`。报告损坏或预留已发生在发布认证前时，当前 `verify_report` 可抛出 `TableEvidenceError`，默认到专用路由返回安全 `500`，此时提交尚未发生。若验收需失效证据以固定业务码返回，在发布实物读取边界可复用 `publication_snapshot_mismatch` 和 `publication_result_unavailable`，同时保留现有真实存储故障合同。见 `app/domains/document_jobs/publication_evidence.py:71`、`app/services/tables/evidence.py:26`、`app/domains/document_jobs/preview_evidence.py:57`、`app/domains/document_jobs/use_cases/publication.py:533`、`app/domains/document_jobs/quality_review_http.py:97`。

### 并发验收与启用门

在隔离环境使用候选版本正式审批 API、同版本 MySQL InnoDB 的两个独立客户端及真实文件仓储写入口。用完全修正的 LOW/HIGH 正式 Worker 产物作为成功对照，保留真实报告、IR、Word。同步点由测试侧在只读核验完成和锁定完成后发信号，用等待状态与完成顺序控制交错。记录连接 ID、事务顺序、审批响应码、当前指针、历史条数、最高序号、发布记录和成功审计条数。file 用共用实际目录的双进程验证，SQLite 用两个独立连接。相关内容及连接秘密仅留隔离环境。

| 交错 | 启用候选应留下的证据 |
| --- | --- |
| A 最后重读完成，B 先提交 report/IR 预留或描述变更，再放开 A | 正式批准返回 `409 review_result_integrity_conflict`，当前指针、历史条数和序号等于 A 前的观察。用旧逻辑对照时能够追加批准，证明屏障在目标窗口内。 |
| A 先取得 job 和三件依赖锁，B 尝试写同一文件 | MySQL 采集实际等待链和持锁连接；file/SQLite 观察各自写入等待。提交前中途确认 B 未写成，A 提交成功后 B 才能完成。A 只有一条批准。此后发起的首次发布根据现有独立门禁拒绝失效证据。 |
| 在 A 持锁时制造写入前异常或独立连接断开 | 回滚后历史、当前指针与序号均不推进，B 或新的合法审批能够取得锁。连接中止发生在可能已提交的时点时，先用 `GET /review` 和 `GET /review/history` 对账，再决定人工重提。 |
| 已批准且证据完整。发布 A 独立认证完成后停在仓储提交前，B 提交独立 report/IR 的预留 | 发布返回 `409 publication_result_unavailable`，发布记录、成功发布审计和当前发布指针维持原观察。证据全齐的另一任务正式批准 200、首次发布 201。 |
| 剩余值列歧义或同源不匹配 | 正式审批/发布分别返回 `409 review_quality_blocked`、`409 publication_quality_blocked`，附未决项及人工核定落点。IR 到期时另验证锁内有效期检查。 |

审批重核窗口修复与真实目标 MySQL 的两方向竞争及回滚证据列为自动绑定灰度启用前的条件。报告需保留实际运行版本、行锁证据与 HTTP/持久状态的对应关系。相关规范见 `.trellis/spec/backend/database-guidelines.md:143`、`:149`、`.trellis/spec/backend/error-handling.md:279`、`.trellis/spec/backend/word-generation-rules.md:402`。

## 待实测证据

- 静态代码和阶段四已归档结果支持以上交错推导。当前阶段为方案，新的屏障、真实 MySQL 和活动存储保护仍待隔离验收。
- 实际 MySQL 服务版本、隔离级别、驱动行为和目标存储策略须取自验收环境。本文引用仓库的事务和文件协议作为依据，未使用外部文档或在线运行结果。
