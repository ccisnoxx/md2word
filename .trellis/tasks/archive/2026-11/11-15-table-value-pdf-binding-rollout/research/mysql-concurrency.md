# 研究：同包新代的 MySQL 并发验收

- 查询：同包重生成的新代接纳、UUID 幂等、文件生命周期与旧代 Worker 在真实 InnoDB 上如何验收。
- 范围：第四阶段所在工作树的仓储、领域规则、生产配置、既有专项夹具和 MySQL 8.4 手册。
- 日期：2026-11-15

## 当前实现

- API 先以原 UUID 查询已提交接纳记录。新请求在事务外认证源 PDF、当前结果、同包人工核定与资源快照，然后把冻结的文件描述提交仓储。仅新接纳进入投递分支。若提交结果未知，保留原 UUID 对账；查询本身失败时继续返回未确认状态。见 `app/domains/document_jobs/use_cases/publication.py:148–231,233–251`。
- MySQL 每次写操作用独立连接，`autocommit=False`。先取 `document_jobs.job_id` 的 `SELECT … FOR UPDATE`，在锁内先读 job payload 里的 UUID 账本。同 UUID、同请求重放返回原接纳凭据、锁下观察的当前任务和 `replayed=True`，直接跳过依赖文件锁及新写入。新 UUID 以 ID 排序去重，逐个锁定源 PDF、MinerU 原包、当前 IR、质量报告、Word，再读取当前时间并验证当前代、资源快照、指针、完整冻结描述、文件状态、删除声明、校验和及到期时间。清空旧代结果和复核槽，新代以 `running/parsed` 延续已固定的原包。job、私有账本、audit 同一事务提交，出错回滚。写完准备提交后发生异常时结果视为未知。见 `app/infrastructure/persistence/mysql/backend.py:50–83`、`app/infrastructure/persistence/mysql/document_jobs.py:76–104,263–309`、`app/domains/document_jobs/new_generation.py:239–366`。
- 文件的更新、过期、删除声明及删除完结共用其主键行锁。发布在 job 锁后同样按文件 ID 顺序加行锁，且在取完全部文件锁后才开始一致读。文件保留期服务对发布保护的首个一致读也在文件锁之后。接纳事务只维护仓储状态的一致边界，Worker 仍需验证实际对象字节。见 `app/infrastructure/persistence/mysql/files.py:34–43,61–66,98–148`、`app/infrastructure/persistence/mysql/document_jobs.py:325–350`、`app/domains/document_jobs/new_generation.py:265–301`。
- 旧 Worker 的受保护更新和结果登记在 job 行锁内比较代次及当前条件；读取同包重放意图也校验代次、来源和资源摘要。见 `app/infrastructure/persistence/mysql/document_jobs.py:139–180,270–275`、`app/domains/document_jobs/result_state.py:60–80`、`app/domains/document_jobs/new_generation.py:219–236`。

## 真实 MySQL 验收环境

- 生产 Compose 固定 MySQL 镜像 digest，指定 `utf8mb4` 和 `utf8mb4_unicode_ci`；Linux/amd64 的依赖锁是 PyMySQL 1.2.3。此处是仓库声明，运行环境需另取实际镜像身份及服务器、驱动版本。存量写事务沿用实际会话隔离，列表 v2 的只读查询才单独指定 RR 快照。见 `docker/prod/docker-compose.yml:78–90`、`requirements/locks/cp311-linux-amd64.txt:74`、`app/infrastructure/persistence/mysql/backend.py:50–83`、`app/infrastructure/persistence/mysql/document_jobs.py:127–132`。
- 优先复用 `tests/test_document_job_list_query_v2_mysql.py:27–80` 的显式启用、loopback、独立测试凭据、随机 schema、真实 MySQL 8.4 检查和退出清理。该夹具只创建 job/files 两张表；专项按同一生产 DDL 补建 `audit_events` 及文件生命周期读取所需的 `document_job_publications`，若合跑审批再补复核记录表。v2 连接厂强制 READ COMMITTED 和 `lock_wait_timeout`，专项使用目标写会话隔离，另读实际 `innodb_lock_wait_timeout`。可参考 `tests/test_document_file_read_session_mysql.py:42–80` 的真实第二连接及显式 RR 校验。见 `tests/test_document_job_list_query_v2_mysql.py:176–199`。
- 隔离环境采用候选 MySQL 镜像、驱动和生产建表及补列后的结构。记录写连接观察到的 `VERSION()`、`@@session.transaction_isolation`、`@@session.autocommit`、`@@session.innodb_lock_wait_timeout`、字集和排序规则。从该随机 schema 的 `INFORMATION_SCHEMA.TABLES/STATISTICS` 或 `SHOW CREATE TABLE` 核对 InnoDB、索引键和排序规则。按现有 DDL，`document_jobs`、`document_files` 分别用 `job_id`、`file_id` 主键点查加锁，`audit_events` 用自增主键，UUID 幂等由 job 锁和 payload 账本保证。见 `app/infrastructure/persistence/mysql/schema.py:317–323,352–361,395–427`。
- 复用 `tests/test_online_table_value_generation_store.py:27–65` 的已认证描述作为事务夹具，采用合成任务和文件身份。该文件的 file/SQLite 用例验证领域结果，fake MySQL 验证 SQL 形状和调用顺序。需要独立连接的 InnoDB 实证来观察已提交版本、行锁等待、提交和回滚。数据库规范明确该证据是启用写者的门禁。见 `tests/test_online_table_value_generation_store.py:67–136,156–182`、`.trellis/spec/backend/database-guidelines.md:136–149`。

## 建议的双连接验收矩阵

真实 API 预认证/Worker 回放由实物专项覆盖。这里直接用正式 MySQL adapter 和两个独立 PyMySQL 连接，测试包装只负责同步与记录，无需新增产品同步点。等持锁方发出已取锁事件后启动另一条真实语句，独立观察连接按当前两条会话筛选对象和 `performance_schema.data_locks/data_lock_waits`。记录等待关系之后才释放持锁方。若观察权限不可用，使用明确的真实锁等待超时及释放后的成功复核作为辅助证据，并注明缺少锁图。给屏障及 SQL 等待设本次用例期限，连接与 schema 由现有夹具在退出时释放。 [MySQL 8.4 锁定读](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html) · [MySQL 8.4 锁等待视图](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-data-lock-waits-table.html)

| 场景 | 源端调度 | 放行证据 |
| --- | --- | --- |
| 同 UUID 幂等 | A 在 job 锁内写入后、提交前停住，B 以同 UUID、同操作者和同提交摘要调用。观察 B 等 job 行后让 A 提交。另测同 UUID 改内容或操作者。 | B 的接纳凭据等于 A，`replayed=True`，无文件加锁和新写入。新连接读到一次加代、一条账本、一条接纳审计。变更请求返回 `new_generation_request_conflict`。API 联测核对仅首次产生投递。 |
| 不同 UUID 同基线争用 | 两方提交同一代和当前结果的已认证快照。A 先锁 job，B 真实等待，A 提交并停在 `running/parsed`。 | A 一次接纳且 ID 顺序取得完整文件锁。B 加锁后看到 `new_generation_state_invalid`（先判当前状态），无败方账本或审计。若另测当前结果已变而状态仍允许，单独断言来源冲突。 |
| 删除声明、过期及等锁 | B 用正式文件仓储先锁定已冻结的原包或报告，A 持 job 锁在该文件行等待后让 B 提交删除声明。用全新夹具重跑 B 回滚，以及 A 先得文件锁、B 删除声明等待。单独使原描述在锁等待期间经过 `expires_at` 来确认使用取锁后时间。 | B 已提交声明时 A 等到新版本并以 `new_generation_source_changed` 整批拒绝。B 回滚后 A 用原快照接纳。先接纳时 B 必须等事务释放文件锁，之后按现有保留期规则处理。到期后必须拒绝接纳。失败方无账本或审计，原 job 代次和结果指针保持原值，文件可用性继续服从其新状态。 |
| 等锁异常及重新对账 | 在隔离测试连接控制 `innodb_lock_wait_timeout`，让一次由锁屏障制造的行锁等待越过限时；释放持锁方，按原 UUID 查询再重试。若覆盖提交回执丢失，可在隔离夹具中让真实 COMMIT 成功后由连接包装抛提交异常，检查原 UUID 恢复。 | 等锁失败释放本事务占用的锁，无半写，允许同 UUID 重试。回执丢失时原 UUID 查回唯一已提交接纳，重复提交不产生新代或审计。 |
| 旧代 Worker 与新代意图 | 将旧代意图读取和结果 CAS 排在接纳提交后的真实 job 锁之后。通过正确代再读取已固定原包及人工核定。 | 旧代意图触发 `new_generation_source_changed`，旧代更新/结果登记返回 `None`，新代状态、原包、私有意图与结果槽保持一致。 |

## 留档与边界

- 每例记录候选版本和镜像、MySQL/驱动版本、实际会话隔离及限定 schema 结构、A/B 匿名会话、锁对象及索引、屏障与提交/回滚相对时刻、等待时长、错误码或重放标志、代次前后值、账本/审计计数、新连接读回及已接纳请求能否再次查询。仅记录本次合成任务或匿名标识和摘要，相同与否即可核对的值记录比较结果。省略连接参数、凭据、全量 SQL payload、对象 key 和客户数据。
- 并发任务成功仅证明数据库事务边界。实际 Poppler/同源字节/Word 位置、实际审批重核行为由各专项共同组成灰度准入证据。开放同包写入口前要求上述真实隔离场景得到完整可重放记录，源校验或状态不一致不能产生额外接纳或覆盖正确代次。

## 相关规范

- `.trellis/workflow.md:182` 约束研究留档。
- `.trellis/spec/backend/database-guidelines.md:136–149` 定义 CON-102 的持久化与真实引擎证据。
- `.trellis/spec/backend/word-generation-rules.md:406–408` 定义线上同包核定、冻结及实物验收边界。

## 注意事项

本次已检查仓库与官方手册。目标镜像版本、候选部署会话隔离、锁等待、完整提交结果和性能数据均待实际隔离验收。本次没有连接 MySQL 或执行任何测试。
