# Database Guidelines

The backend currently uses explicit metadata adapters, not an ORM. Metadata can be stored in local files, sqlite, or MySQL; artifact binaries are configured separately.

Evidence:

- `app/core/config.py`
- `app/infrastructure/persistence/factory.py`
- `app/infrastructure/persistence/file/backend.py`
- `app/infrastructure/persistence/sqlite/backend.py`
- `app/infrastructure/persistence/sqlite/schema.py`
- `app/infrastructure/persistence/mysql/backend.py`
- `app/infrastructure/persistence/mysql/schema.py`
- `app/infrastructure/persistence/mysql/jobs.py`
- `app/infrastructure/persistence/sqlite/jobs.py`
- `app/infrastructure/persistence/file/jobs.py`
- `docs/runbooks/backend.md`
- `tests/test_database_job_repository.py`

## Metadata Backend Selection

`Settings.jobs_repository_backend` controls metadata storage:

- `file` is the code default and local development backend.
- `database` means sqlite, using `Settings.jobs_metadata_database_file`.
- `mysql` means MySQL through PyMySQL and `MysqlPersistenceConfig`.

`build_persistence_adapters()` in `app/infrastructure/persistence/factory.py` is the single wiring point for backend-specific repositories. Add new repository ports to `PersistenceAdapters`, then implement and wire each supported backend there.

产物二进制不写入 SQLite/MySQL 元数据表。正式 `FileUploadService` 继续由 `Settings.jobs_artifact_storage_backend` 选择 `local_file`、`local_object` 或 `s3`；旧 jobs artifact adapter 已移除。该配置与健康输出语义保持。

## Repository Ports And Adapters

Domain code should depend on narrow repository protocols in `app/domains/**/repository.py`. Examples:

- `app/domains/jobs/repository.py` 仅保留共享 `JobEventRepositoryProtocol`；正式任务端口位于 `app/domains/document_jobs/repository.py`。
- `app/infrastructure/persistence/factory.py` returns a concrete `PersistenceAdapters` object containing implementations for the selected backend.
- `app/main.py` builds the adapters, passes them to the `app/composition/*` assembly functions, and stores them on `AppRuntime`.

When adding persistence for a domain, keep the domain protocol in `app/domains/<domain>/repository.py`, and put backend implementations under `app/infrastructure/persistence/file`, `sqlite`, and/or `mysql`.

当前未建立此约定：resource versioning and several governance repositories are only wired for MySQL in `build_mysql_persistence_adapters()`. File and sqlite adapters often return `None` for those optional ports, so services must explicitly guard MySQL-only behavior instead of assuming every backend supports it.

## Schema And Migration State

当前未建立此约定：there is no Alembic or versioned migration directory.

Schema creation is bootstrap SQL in code:

- sqlite statements live in `app/infrastructure/persistence/sqlite/schema.py`.
- MySQL statements live in `app/infrastructure/persistence/mysql/schema.py`.
- `SqlitePersistenceBackend` and `MysqlPersistenceBackend` call `initialize_schema()` during backend initialization.

MySQL 的 `initialize_schema(connection)` 不止建表：按建表、maintenance SQL、补列、post-column SQL、删除旧索引、补索引的顺序执行。`_ensure_column()` / `_ensure_index()` 查询 `INFORMATION_SCHEMA` 后决定是否执行 ALTER；这是启动时 schema maintenance，不是有版本账本的 up/down migration。SQLite 在 CREATE TABLE/INDEX IF NOT EXISTS 后检查 DocumentJob 状态列并幂等补列；payload 回填仍由显式工具执行。旧 jobs shadow copy 工具已移除，不作为正式 DocumentJob 的迁移入口。

既有定向证据为 `tests/test_database_job_repository.py::PersistenceAdapterTests.test_mysql_schema_maintenance_adds_missing_translation_term_columns_without_if_not_exists`：fake MySQL 验证缺列维护及 SQL 兼容形状，不能据此宣称真实 DDL 原子回滚或并发初始化安全。首次持久化字段变更仍须在对应任务设计前滚、backfill、兼容窗口和回滚/不可逆处理；不能等发布阶段才补设计。BAS-001 的当前运行证据见 `docs/implementation/baseline-verification-2026-10-12.md`。

Do not add ORM migrations or PostgreSQL assumptions inside feature work unless the task explicitly establishes that new convention. `docs/dev/backend-local-setup-and-architecture.md` and `docs/runbooks/backend.md` both state the current production-oriented metadata backend is MySQL, while PostgreSQL is not present.

旧 `jobs`、`job_files`、`stage_messages` 的建表和仓储已移除。不得因此删除 `job_events`：SQLite/MySQL 的正式 DocumentJob 事件仍读写该表。既有生产旧表保持原状，另由 B08 治理，本任务不提供 DROP 或旧任务迁移。

## Storage Shape

The dominant adapter pattern stores Pydantic model payloads as JSON and keeps a small number of indexed columns for lookup/sorting/status:

- 正式主记录由 `document_jobs.py` 写入 `document_jobs.payload`，事件使用 `job_events.payload`。
- 三种后端的 `jobs.py` 仅保留 `JobEvent` 事件仓储；其余旧 snapshot/file/message 仓储已删除。
- file 正式任务写 `document_jobs/<id>/job.json` 与 `events.jsonl`，正式文件由 `files.py` 写 `document_files/`。
- `file/backend.py` 通过临时文件与 `replace()` 写 JSON，通过追加 JSONL 写事件。

Pydantic 记录使用 `model_dump(mode="json")`、`model_dump_json()`、`model_validate_json()` 持久化；共享模型兼容逻辑保持在其现有所有者。

## Query And Transaction Patterns

Use parameterized SQL:

- MySQL adapters use `%s` bind markers with tuple parameters.
- sqlite adapters use `?` bind markers with tuple parameters.

Do not format user or request values directly into SQL strings.

连接上下文拥有事务收尾：

- `MysqlPersistenceBackend.connect()` 成功提交、异常回滚、退出关闭；与读取会话共用 `_transaction(connection)` 的原有规则。
- `SqlitePersistenceBackend.connect()` 成功退出时提交，随后关闭连接。
- 默认仍为每个仓储操作的短连接/短事务；异常列表只在下述局部读取会话中复用物理连接，不形成跨操作事务。没有通用查询构造器、ORM事务管理器或跨领域事务框架。

### 异常列表的局部读取会话

**1. 范围与触发。** 线上分类逐条文件/保护读取反复建连是已测瓶颈。仅异常列表的首次有效复核与分类采用请求级会话；参数校验、起始时钟和搜索归一化先完成，分类结束立即关闭，页内动作仍复用 `observed_result_view`。详情、诊断、下载和POST默认路径不加入会话。

**2. 签名。** `DocumentFileReaderProtocol` 只提供 `get_document_file(file_id) -> DocumentFileRecord | None` 与 `is_document_file_protected(file_id) -> bool`；`DocumentFileRepositoryProtocol.read_session() -> AbstractContextManager[DocumentFileReaderProtocol]`。
`MysqlPersistenceBackend.read_session()` 产出 `Callable[[], AbstractContextManager[Any]]` 作为逐操作连接上下文；`MysqlDocumentFileRepository(..., read_connect=None)` 的局部实例仅让上述两方法使用它。service的 `list_visible_jobs`、`_effective_job`、`build_incident_classification_view`、`_build_result_read_view`、`_get_completed_result_file`、`_ensure_file_not_expired` 接受可选关键词 `file_reader`，缺省仍用原仓储。

**3. 合同。** MySQL第一次读取才建物理连接，零读取不建连；每次原操作独立提交/回滚，下一次取得新的事务观察，绝不把会话改成长RR快照。会话退出关闭连接，不自动重连、重试、缓存或跳过读取。局部仓储与显式reader不修改共享service/backend的连接模式。file/SQLite会话无状态，复用原仓储行为。没有新增HTTP字段、数据库列或环境配置；写方法及锁定读取继续使用原 `backend.connect()`。

**4. 校验与错误矩阵。**

| 条件 | 必须保持的结果 |
| --- | --- |
| 文件缺件 | 原None和调用者原有ApplicationError/禁用动作处理 |
| get返回坏JSON、模型或不匹配ID | 原事务已提交后校验并抛出；不变成None，不挪进事务 |
| 保护关系JSON解析失败或SQL失败 | 当前操作回滚并传播；退出会话关闭连接 |
| 可达naive/aware、质量或descriptor错误 | 保留原前缀与时钟，不能为了提速跳过正常任务的检查 |
| 建连、提交、回滚或现有连接失败 | 沿既有错误处理传播、最终释放；不增加自动恢复 |
| 多请求共享应用service | 每请求持有独立reader/连接，不替换singleton字段 |

物理connect/close从多次变为一次，连接层故障机会和关闭时点必然变化；保留业务校验及事务错误顺序，不宣称逐连接运输故障完全等价。

**5. 正常、缺省、错误场景。** 正常：同一reader两次get共享物理连接，但第一次提交后外部更新可被第二次读取观察。缺省：未传file_reader的详情/下载照常逐次建连。错误：保护关系坏JSON回滚并使本请求失败，不能返回未保护或空异常列表。

**6. 必要验证。** fake记录单次建连、逐次提交/错误回滚、零读/异常关闭，以及get校验在commit后而保护解析在事务内。真实MySQL显式确认RR，用第二连接提交文件/保护关系变化，证明下一操作见到新值；fake不能替代。直接回归保护两阶段有效复核、分类前/后到期、页内观察复用、完整响应/summary/动作差分，以及并发reader隔离；具体执行证据见[当前任务](../../tasks/11-06-list-loading-performance/research/incident-session-implementation.md)。

**7. 错误与正确做法。** 错误：在会话末尾统一commit、给共享service临时换仓储，或过滤掉“正常”任务来少读文件。正确：显式传递局部reader并保留原两阶段顺序，每次原读取都结束自己的事务，例如：

```python
with file_repository.read_session() as reader:
    first = reader.get_document_file(file_id)  # 本次读取已结束事务。
    second = reader.get_document_file(file_id)  # 新事务观察，不缓存 first。
```

## 正式回调消息持久化

旧 stage spool 已移除。正式 `DocumentJobCallbackMessageStoreProtocol` 的三种后端及其重放语义保持，`tests/test_database_job_repository.py` 继续验证正式任务、回调、文件和事件仓储合同。

## DocumentJob 翻译批次持久化

`DocumentJobTranslationBatchRepositoryProtocol` 由 file/sqlite/MySQL 同时实现。完整根集合安装、一致快照、enqueue/claim、attempt/lease 条件提交、回收和 split 的唯一具体合同见 [翻译批次生命周期与原子边界](translation-batch-lifecycle.md)；不能把 status/generation 的普通读后写当作 CAS。

- 所有运行期写与 CON-102 主记录共享同 job 序列化点；同代旧 attempt/lease、旧 generation、取消或终态停止不能污染胜出账本和结果。
- file 在 `document_job_translation_batches/` 保存每批一个 JSON；sqlite/MySQL 仍沿 payload 加 batch_id/job_id/generation/status/时间索引，不为 TR-406 增加持久化字段。
- 根计划从锁外权威 source/config 计算，一次完整安装；已有 ID 不覆盖可变现态。数据库回滚完整集合，file 残缺恢复明确失败，不引入事务日志或安装标记。
- 改字段或状态迁移时同步三 adapter、fake MySQL 与真实 file/sqlite 合同测试；仅事务语义变化不要求新增 DDL。CON-103 原有状态 schema bootstrap 属已验收依赖基线。


## DocumentJob 结果登记的局部原子合同（CON-102）

触发：修改DocumentJob主记录写入、prepared_result、结果候选的创建/物化/保留期或retry换代。流程与下载规则由[任务模式与阶段合同](./document-job-mode-contract.md#8-执行阶段与恢复合同con-102)定义；本节只拥有持久化保证，不将 batch 仓储改造成全局 CAS。

- `DocumentJobRecord.prepared_result`是内部JSON payload，旧记录缺省None；公开response不增加字段，无DDL/backfill。首次原子选定receipt决定同代/最终IR唯一结果身份，之后不得换件。
- `document_jobs/result_state.py`共用纯条件/更新规则；序列化由adapter负责。所有同job主记录创建/patch/if_current/prepare/retry必须在同一记录序列化点读最新值、检查、验证并写回。create不以upsert覆盖已有ID；非状态patch保留已有receipt。
- `if_current`的generation/最终IR、receipt为空或匹配file ID条件在锁内判断；retry检查当前failed/代数/预算并清槽换代。receipt为空和匹配ID条件互斥；正常竞争拒绝返回None，真实存储/描述冲突不能吞成lost-race。
- file在独立稳定`.lock`文件使用跨进程advisory lock；不能锁随后被replace的JSON inode，不在线删除锁文件，不退化为进程内锁。JSON replace只承诺本任务进程中断恢复，不额外声明机器掉电或任意共享文件系统耐久性。
- SQLite写方法在读取前BEGIN IMMEDIATE，使用同一短连接判断/写入；异常rollback/连接关闭释放锁。MySQL现有InnoDB行在短事务内SELECT FOR UPDATE，同连接读/判断/写；创建使用唯一键insert冲突，沿用commit/rollback。
- `files/result_registration.py`拥有文件不可变descriptor与生命周期条件；同file的create/物化/过期删除写入共享其adapter序列化点。结果candidate先insert pending metadata再写独立key；物化只补etag/uploaded，不再次写对象、延长expires_at或覆盖evidence。expired/deleted不得被迟到写者复活。
- 新协议pending候选按原generated_word保留期设置expiry，仅该类pending允许到期原子标expired；普通pending源上传语义保持。物理删除仍由原受控清理链处理，S3 fake边界不升级为真实删除；保留key/墓碑，不以此宣称任意迟到网络写已物理回收。
- 锁/事务内不得做渲染、质量检查、对象/网络IO或跨仓储开另一写连接；无job/file跨域事务。receipt加幂等物化覆盖二者之间的中断窗口。

验证需要真实file双进程、SQLite独立连接竞争与中断/锁释放，以及模型和条件合同。fake MySQL只保护SQL形状/commit/rollback调用，不证明数据库并发；真实InnoDB竞争/断连与部署文件系统锁语义是启用新写者前门禁。新协议只能回退到认识并保留receipt、具备原子写入与候选可见性的兼容版本，旧stage-only patch不是安全下限；兼容读者候选保留HEAD旧执行器时，必须暂停全部DocumentJob消费/内联执行，不能作为活跃Worker回退版本。

## 场景：生成件物理身份与历史对象读取

### 1. 范围与触发

修改 `FileUploadService.register_generated_content`、生成件路径或异步结果登记时适用。记录级 CAS 负责选取结果，不能阻止登记前的文件写入覆盖共享对象。

### 2. 接口

外部 `register_generated_content(..., filename, content, metadata=None)` 保持不变；内部 `_generated_object_key_for(*, tenant_id, job_id, file_type, file_id, filename, provider) -> str` 必须使用本次登记已经分配的 `file_id`。

### 3. 合同

- 新生成件 key 为 `document-jobs/<safe tenant>/<safe job>/<safe type>/<safe file_id>/<safe filename>`；S3 继续追加既有安全 prefix。共享方法的所有新生成件都采用此规则，不按翻译类型保留覆盖旁路。
- 同一 generation/attempt 的再次登记也分配独立物理身份；代次、尝试和来源归属仍由现有记录及 evidence 校验，路径不能替代这些检查。
- `original_filename`、源 PDF 上传布局、bucket/backend、权限和保留策略不变。文件写入/登记失败不能当成成功；CAS 拒绝只能留下自身未选中的新对象。
- 读取、下载和清理始终使用记录保存的 `object_key`，不从当前模板重建历史路径。新旧布局共存，不 backfill、不搬迁历史件、不修改 DB/schema/repository 协议。

### 4. 验证与错误

沿用现有安全片段及 prefix 检查；危险 prefix 在写入前显式拒绝，不能降级换路径。每次成功登记的 checksum/size 必须对应自身对象实际字节。文件身份隔离不扩大既有 CAS/lease 的并发保证。

### 5. 正常、缺省与非法场景

正常为同一业务 filename 重复登记后，所有记录分别读回自身字节；历史固定 key 记录继续可读。缺省继续使用既有后端配置。非法为分配新 `file_id` 却仍复用 type/filename 路径，或在 CAS 失败后删除/重写胜出及历史对象。

### 6. 必要测试

`tests.test_generated_artifact_identity` 通过真实 service、文件仓储、本地临时目录及 fake S3 put/get，覆盖 source IR、batch result、目标 IR、DOCX 和审计的重复登记、实际字节/checksum、原下载名、历史固定 key、源上传布局及路径安全。翻译接线测试另覆盖新代/新 attempt 胜出后迟到写且 CAS 拒绝的真实字节保真；fake 不能冒充真实 S3/MySQL 并发证据。

### 7. 错误与正确做法

错误：只断言新记录 ID 不同或旧 CAS 失败，就宣称 Artifact 不可变。

正确：共享文件服务按本次 `file_id` 分配新 key，CAS 选择结果记录；测试在迟到写完成后实际读回胜出及历史对象，断言字节和 checksum 均未变。

## CON-103 状态投影与回填

`DocumentJob` 的 `quality_status`、`review_status`、`delivery_status`、`quality_summary` 由 payload 权威保存；SQLite/MySQL 的同名投影列必须与同一连接写入同步，file backend 复用既有 job lock。复核只允许通过 `update_document_job_review_if_current` 比较当前 generation 和 result ID；`backfill_document_job_state_if_missing` 只补缺键，保留旧 QA、时间戳和未知 raw 键。SQLite/MySQL schema maintenance 或显式迁移失败时不降级写入，fake MySQL 仅证明 SQL/回滚调用形状，真实 InnoDB 与部署文件系统仍是线上启用门。

## DocumentJob 列表查询下推

有效复核与双表合同见[任务列表有效复核 v2](./document-job-list-query-v2.md)；下列搜索、时间和排序约束由v1继承，仍适用于当前实现。旧单表回填和raw review分类不再适用。

- `document_jobs.list_query_json` 存储版本3与 `document_files.review_query_json` 存储版本2保存各自的小字段静态事实；完整 key 分别存入 job 的 `list_descriptor_key/list_receipt_key/list_table_snapshot_key` 和 file 的 `review_descriptor_key/review_receipt_key`。SQLite TEXT/MySQL LONGTEXT nullable，NULL 表示未回填，合法不适用值为空串；payload保持权威，有效复核按单次 `as_of` 关联当前文件计算。
- SQLite/MySQL在同一只读快照完成权限、全部筛选、三类汇总、排序和分页；包含动作构建的完整任务payload解码量不超过页条数，实时表格guard读取窄事实。
- 权限同时精确比较tenant/company，Admin可查看范围内全部任务，其他角色限定created_by；MySQL不得依赖不区分大小写或重音的默认collation。
- q先strip，再对id、source_file_id、任务快照original_filename、error_code、error_message五字段分别Python casefold并做字面子串匹配；快照文件名仅dict中的str参与。不串接、不做Unicode normalization，`%`、`_`、反斜线不是通配符；使用INSTR/binary LOCATE，不用LOWER/LIKE替代。
- 时间键使用精确signed整数微秒，区分naive/aware，不用浮点或本机时区转换。日期下界先比较，再比较通过者的上界，之后应用翻译模式；单行也须满足边界类型兼容。只对完整筛选域检查实际排序列，ID与主排序同向。
- job/file共享writer及直接SQL迁移旁路均须同行维护投影；缺失或不兼容事实必须明确失败，不允许GET修复或全量Python回退；事实与payload一致性由全量verify检查，不能仅以非NULL证明未陈旧。
- 列表就绪检查合入同快照既有查询，覆盖 V 统计域任务及其关联文件；可见性字段损坏也须失败关闭，不以坏字段或 NULL 静默排除。不再每请求独立全表 shape COUNT，也不缓存跨请求有效性；完整范围和回归合同见[列表 v2 Spec](./document-job-list-query-v2.md)。
- `scripts/ops/migrate_document_job_list_keys.py` 与原 `migrate_document_job_list_query.py` 共用当前拆列回填实现：同行更新小 JSON 和完整 key，apply先文件后任务，分别使用 `--after-file-id` / `--after-job-id` 续跑；verify须从空游标在同一只读快照全量核对两表所有派生列，不能分页续跑verify。CLI必须显式指定backend及连接目标，不读取.env；dry-run不DDL/DML，apply仅对不一致行UPDATE，其他表禁止写入。
- 旧writer恢复后两表必须从头重建；停写、备份恢复及切换程序见[后端运维手册](../../../docs/runbooks/backend.md#documentjob-列表查询投影)。真实引擎验证使用 `tests.test_document_job_list_query_v2_mysql` 的明确隔离环境，不读.env、不复用业务库；fake与skip不算真实MySQL证据。
