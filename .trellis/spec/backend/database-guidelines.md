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

Artifact binaries are not stored in sqlite or MySQL metadata tables. `Settings.jobs_artifact_storage_backend` selects `local_file`, `local_object`, or `s3`, and `app/main.py` wires the matching artifact storage adapter separately.

## Repository Ports And Adapters

Domain code should depend on narrow repository protocols in `app/domains/**/repository.py`. Examples:

- `app/domains/jobs/repository.py` defines `JobSnapshotRepositoryProtocol`, `JobEventRepositoryProtocol`, `JobFileRepositoryProtocol`, and `StageMessageStoreProtocol`.
- `app/infrastructure/persistence/factory.py` returns a concrete `PersistenceAdapters` object containing implementations for the selected backend.
- `app/main.py` passes those adapters into services and stores them on `AppRuntime`.

When adding persistence for a domain, keep the domain protocol in `app/domains/<domain>/repository.py`, and put backend implementations under `app/infrastructure/persistence/file`, `sqlite`, and/or `mysql`.

当前未建立此约定：resource versioning and several governance repositories are only wired for MySQL in `build_mysql_persistence_adapters()`. File and sqlite adapters often return `None` for those optional ports, so services must explicitly guard MySQL-only behavior instead of assuming every backend supports it.

## Schema And Migration State

当前未建立此约定：there is no Alembic or versioned migration directory.

Schema creation is bootstrap SQL in code:

- sqlite statements live in `app/infrastructure/persistence/sqlite/schema.py`.
- MySQL statements live in `app/infrastructure/persistence/mysql/schema.py`.
- `SqlitePersistenceBackend` and `MysqlPersistenceBackend` call `initialize_schema()` during backend initialization.

MySQL 的 `initialize_schema(connection)` 不止建表：按建表、maintenance SQL、补列、post-column SQL、删除旧索引、补索引的顺序执行。`_ensure_column()` / `_ensure_index()` 查询 `INFORMATION_SCHEMA` 后决定是否执行 ALTER；这是启动时 schema maintenance，不是有版本账本的 up/down migration。sqlite 的初始化仍是 CREATE TABLE/INDEX IF NOT EXISTS 循环。shadow copy 用于 metadata 后端搬迁，不提供 schema 版本回滚。

既有定向证据为 `tests/test_database_job_repository.py::PersistenceAdapterTests.test_mysql_schema_maintenance_adds_missing_translation_term_columns_without_if_not_exists`：fake MySQL 验证缺列维护及 SQL 兼容形状，不能据此宣称真实 DDL 原子回滚或并发初始化安全。首次持久化字段变更仍须在对应任务设计前滚、backfill、兼容窗口和回滚/不可逆处理；不能等发布阶段才补设计。BAS-001 的当前运行证据见 `docs/implementation/baseline-verification-2026-10-12.md`。

Do not add ORM migrations or PostgreSQL assumptions inside feature work unless the task explicitly establishes that new convention. `docs/dev/backend-local-setup-and-architecture.md` and `docs/runbooks/backend.md` both state the current production-oriented metadata backend is MySQL, while PostgreSQL is not present.

For metadata backend moves from file to sqlite/MySQL, use the existing shadow-copy scripts documented in `docs/runbooks/backend.md`:

- `scripts/ops/check_local_file_storage_integrity.py`
- `scripts/ops/shadow_copy_metadata_to_database.py`
- `scripts/ops/shadow_copy_metadata_to_mysql.py`

## Storage Shape

The dominant adapter pattern stores Pydantic model payloads as JSON and keeps a small number of indexed columns for lookup/sorting/status:

- `app/infrastructure/persistence/mysql/jobs.py` stores `JobRecord` in `jobs.payload` and events in `job_events.payload`.
- `app/infrastructure/persistence/sqlite/jobs.py` mirrors that pattern with sqlite.
- `app/infrastructure/persistence/file/jobs.py` stores `job.json`, `files.json`, and `events.jsonl`.
- `app/infrastructure/persistence/file/backend.py` writes JSON via a temporary file and `replace()`, and appends JSONL for events.

Use `model_dump(mode="json")`, `model_dump_json()`, and `model_validate_json()` for Pydantic record persistence. Keep compatibility transforms at the persistence boundary when the existing model requires them, as `sync_source_pdf_compatibility_fields()` does for jobs.

## Query And Transaction Patterns

Use parameterized SQL:

- MySQL adapters use `%s` bind markers with tuple parameters.
- sqlite adapters use `?` bind markers with tuple parameters.

Do not format user or request values directly into SQL strings.

Connection helpers define commit behavior:

- `MysqlPersistenceBackend.connect()` commits on success and rolls back on exception.
- `SqlitePersistenceBackend.connect()` commits on successful context exit and closes the connection.

当前未建立此约定：there is no shared query builder, ORM transaction manager, or multi-statement domain transaction abstraction. Existing adapters open a short connection per repository method.

## Stage Message Persistence

`StageMessageStoreProtocol` defines stage spool behavior. Current stores:

- `FileStageMessageStore`
- `SqliteStageMessageStore`
- `MysqlStageMessageStore`

`pending` and `running` are replayable. `failed` preserves diagnostic state and is not automatically replayed. This is documented in `app/domains/jobs/repository.py`, `app/domains/jobs/stage.py`, and `docs/dev/runtime-observability-and-health.md`.

When changing stage messages, update all supported stores and tests. `tests/test_database_job_repository.py` is the main contract test for adapter parity.

## Document Jobs Translation Batches

`DocumentJobTranslationBatchRepositoryProtocol` is part of the `document_jobs` metadata contract. File, sqlite, and MySQL adapters must all support:

- create/get/list by `job_id` and optional `generation`
- unconditional administrative update for local state repair
- compare-and-set update through `update_translation_batch_if_current(batch_id, allowed_statuses, expected_generation, **patch)`

Provider batch worker transitions must use compare-and-set for claim and running-state completion/failure. A stale task, expired lease replay, canceled job, or older generation must not be able to overwrite a batch that has already left `running`.

Translation batch stores follow the existing payload-plus-index pattern:

- file backend stores one JSON payload per batch under `document_job_translation_batches/`
- sqlite/MySQL use `document_job_translation_batches` with indexed `batch_id`, `job_id`, `generation`, `status`, `created_at`, and `updated_at`

When changing batch persistence fields or state transitions, update all three adapters, the schema bootstrap, fake MySQL cursor behavior, and the adapter parity coverage in `tests/test_database_job_repository.py`.

## DocumentJob 结果登记的局部原子合同（CON-102）

触发：修改DocumentJob主记录写入、prepared_result、结果候选的创建/物化/保留期或retry换代。流程与下载规则由[任务模式与阶段合同](./document-job-mode-contract.md#8-执行阶段与恢复合同con-102)定义；本节只拥有持久化保证，不将batch或legacy jobs仓储改造成全局CAS。

- `DocumentJobRecord.prepared_result`是内部JSON payload，旧记录缺省None；公开response不增加字段，无DDL/backfill。首次原子选定receipt决定同代/最终IR唯一结果身份，之后不得换件。
- `document_jobs/result_state.py`共用纯条件/更新规则；序列化由adapter负责。所有同job主记录创建/patch/if_current/prepare/retry必须在同一记录序列化点读最新值、检查、验证并写回。create不以upsert覆盖已有ID；非状态patch保留已有receipt。
- `if_current`的generation/最终IR、receipt为空或匹配file ID条件在锁内判断；retry检查当前failed/代数/预算并清槽换代。receipt为空和匹配ID条件互斥；正常竞争拒绝返回None，真实存储/描述冲突不能吞成lost-race。
- file在独立稳定`.lock`文件使用跨进程advisory lock；不能锁随后被replace的JSON inode，不在线删除锁文件，不退化为进程内锁。JSON replace只承诺本任务进程中断恢复。
- SQLite写方法在读取前BEGIN IMMEDIATE，使用同一短连接判断/写入；异常rollback/连接关闭释放锁。MySQL现有InnoDB行在短事务内SELECT FOR UPDATE，同连接读/判断/写；创建使用唯一键insert冲突，沿用commit/rollback。
- `files/result_registration.py`拥有文件不可变descriptor与生命周期条件；结果candidate先insert pending metadata再写独立key；物化只补etag/uploaded，不再次写对象、延长expires_at或覆盖evidence。expired/deleted不得被迟到写者复活。
- 锁/事务内不得做渲染、质量检查、对象/网络IO或跨仓储开另一写连接；无job/file跨域事务。receipt加幂等物化覆盖中断窗口。

## CON-103 状态投影与 Migration A

DocumentJob 四字段与业务规则由 [模式与交付状态合同 §9](./document-job-mode-contract.md#9-质量复核和交付状态con-103) 拥有。这里定义三 adapter 的序列化、列和迁移保证。

- `quality_status`、`review_status`、`delivery_status`、`quality_summary_json` 是同一任务 JSON payload 的保守投影；全部 create/patch/条件 patch/prepare/retry/review 写路径必须在同一锁或连接中同步维护。
- `backfill_document_job_state_if_missing(job_id)` 只在锁内补缺键，保留已有合法值、旧 QA 原文、receipt、快照、时间戳和未知 raw 键；不从旧 QA 或成功状态推导通过。
- SQLite 使用增量列维护和 BEGIN IMMEDIATE，MySQL 使用同连接 schema maintenance 与事务；file 复用稳定 job.lock。迁移/回填失败显式传播，不以默认值吞错。

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
