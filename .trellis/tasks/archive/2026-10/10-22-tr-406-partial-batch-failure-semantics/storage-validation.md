# TR-406 批次仓储验证记录

本文件记录存储层实施后的定向验证，不把 fake MySQL 当作真实 InnoDB 并发证据。

## 必须覆盖的场景

- file 双初始化 barrier：B 先观察空集合后暂停，A 完整安装并使一根成功、另一
  根 running，B 恢复只能读回原 status/attempt/lease/result/预算，不得重置。
- sqlite 两个独立连接的 `BEGIN IMMEDIATE` 竞争、完整根集合回滚和重复初始化；
  MySQL fake 检查 job→batch SQL 锁序以及 commit/rollback 调用。
- 双 claim、最后预算、attempt 上限、过期 lease、旧 attempt/旧 lease/旧 generation
  的 success/failure/split 条件写，均不得污染胜出记录。
- file 部分根写或 split 中断后重放必须返回
  `translation_batch_tree_invalid`，不补缺根、不消费部分树；数据库异常必须回滚
  父节点和全部孩子。
- 终态 batch CAS 后、主任务失败前的 enqueue/claim/结果回流，必须由
  `expected_plans` 闸门拒绝新写并保留普通竞争 `None` 语义。
- reducer 归约为 `attempts_exhausted` 或 `call_budget_exhausted` 的过期 running 批次，
  必须在锁内阻止另一 pending 批次 claim 和旧 success/split 晋升；当前过期 lease
  自身仍可回收，存在余量时可重新 claim。
- 当前 lease 仍有效且 reducer 仍为 `running`/`retrying`（没有待消费 leaf 触发终态）
  时，本次正好占用最后预算的 in-flight 调用允许 success 晋升；只要 pending sibling
  令 reducer 已终态，旧在途结果也必须被阻止，不能按 `call_budget_exhausted` 原因码放行。

## 证据边界

本地 file/sqlite 测试证明 adapter 的锁、事务和 payload 往返合同；fake MySQL
只证明 SQL 形状、连接内锁序和异常 rollback 路径。真实 MySQL/InnoDB 并发、断连
恢复以及部署文件系统跨进程锁仍是启用生产写者前的待验门禁。

## 本次执行结果

- `tests.test_translation_batch_repository`：10 个测试方法通过；其中 file/sqlite 双适配器方法展开为 14 个 adapter 场景，另含 2 个 fake MySQL 场景。覆盖 B 的空集合观察后暂停与 A 安装后的完整账本保留、两个独立连接的真实 `Barrier` claim 竞争、最后预算、旧 attempt/lease/result/split、终态兄弟停止闸门、reducer 对过期耗尽批次的停止与自身回收/重试、无 pending leaf 时最后预算在途成功、file 根和 split 中途写失败、SQLite 根集合与 split 父子事务 rollback，以及 fake MySQL 锁序/同连接/rollback 调用和终败兄弟阻止在途结果。fake MySQL 还逐一检查 update/enqueue/claim/release/CAS/split 事务内先 job 锁、随后 `FOR UPDATE` batch/全代读。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_batch_repository`：10 项通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile app/domains/document_jobs/repository.py app/infrastructure/persistence/file/document_jobs.py app/infrastructure/persistence/sqlite/document_jobs.py app/infrastructure/persistence/mysql/document_jobs.py tests/test_translation_batch_repository.py`：repository、三 adapter 与定向测试通过编译检查。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_batch_repository tests.test_translation_batch_workflow tests.test_translation_batch_failure_semantics tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend tests.test_database_job_repository.PersistenceAdapterTests.test_database_repository_persists_records_across_instances`：34 项通过。

此前的 6 项历史测试只做了顺序调用，不能作为并发、rollback 或 fake MySQL 锁序证据；本轮已保留其覆盖目标并补上了可复现的线程 barrier 与故障注入场景。

