# 拆列与请求内校验整合证据

日期：2026-11-07。执行工作区 `${TASK_WORKTREE_ROOT}/list-loading-performance`，HEAD `25860865812ef5bb9159a449aaa7df0a6dfcb815`。只修改本地候选和定向验证；未提交、推送或操作生产。Spec 与任务三件套由主会话维护。

## 来源与接入

只读来源 `${TASK_WORKTREE_ROOT}/list-key-columns`，HEAD `1f4a90adcf824608e9e603190434a0c8f78b118f`。对 tracked diff 与全部相关文件进行两次读取，字节完全一致；未在来源写入文件。冻结证据在忽略目录 `data/key-source-freeze/`，包括 source.patch、逐文件副本和 SHA-256 manifest。tracked patch SHA-256：`efeffe4bdc3b5568637cc596044183d5323964aa2f1f7e956e0fb245384afff5`。

另行冻结未跟踪文件：`scripts/ops/migrate_document_job_list_keys.py`（`917b29d0b251583d5542af7952b42e7a8e18dc80698367636e878ca639ee9412`）、`tests/test_document_job_list_key_columns.py`（`e42f3d3882ce15d75a1f5ce1069257a2028b4c2f8637acb3d46aa5dbee9c85a3`）。源 base 与本 HEAD 的 app/scripts/tests 差异只有表格占位故障诊断相关文件，本次接入目标均无 base 差异。

收到主会话确认 ready 基准已结束后，先 `git apply --check --exclude='.trellis/spec/*'`，再应用同一冻结补丁；两个新增文件从冻结副本复制。保留本工作区已接入的 ready SQL、测试和主会话的 Spec 修改。没有新增索引、缓存、业务兜底或依赖。

产品文件：`app/domains/document_jobs/list_query.py`；共享 `app/infrastructure/persistence/document_job_list_query.py`；MySQL/SQLite 的 `document_jobs.py`、`files.py`、`schema.py`；`scripts/ops/migrate_document_job_list_query.py`、`migrate_document_job_reviews.py` 和新增 `migrate_document_job_list_keys.py`。测试接入/适配涉及 `test_database_job_repository.py`、`test_document_job_delivery_state_migration.py`、`test_document_job_list_query.py`、`test_document_job_list_query_migration.py`、`test_document_job_list_query_v2.py`、`test_document_job_list_query_v2_mysql.py`、`test_document_job_list_query_v2_writers.py`、`test_document_job_list_query_readiness.py` 和新增 `test_document_job_list_key_columns.py`。

共享 SQL 合并保留请求内首条聚合、V 域及其完成态主件、可见性字段不可靠时拒绝、坏文件 JSON 的 CASE 保护和错误优先级，同时采用 job v3/file v2 与五列非 NULL、SQLite 非 BLOB 检查。文件寻址 collation 不变；key 全文继续 MySQL CAST AS BINARY / SQLite COLLATE BINARY，不截断或散列。新 writer、回填及复核导入同行维护小 JSON 与 keys。

接入后除共享 SQL、v2 SQL fake 和新增 MySQL 交叉用例外，所有来源产品/脚本/测试文件均与冻结字节一致。ready 测试只适配投影布局并增加缺 key 在过滤空结果下的回归；旧 list-query writer 断言改为校验完整四列。最终共享 SQL SHA-256：`50a064cecf9a2b3ebad2bd1bde3fd6d8ef3e7bebad0e298d71240c7c064d5a0b`。

## 本轮定向检查

解释器固定 `${PROJECT_ROOT}/.venv/bin/python`，设置 `PYTHONDONTWRITEBYTECODE=1`。没有全仓 discover、构建、前端、发布聚合或真实 Provider/MinerU 请求。

首轮实际执行：

```sh
PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python -m unittest \
  tests.test_document_job_list_query_readiness \
  tests.test_document_job_list_query \
  tests.test_document_job_list_query_v2 \
  tests.test_document_job_list_key_columns \
  tests.test_document_job_list_query_v2_writers.SqliteV2WriterTests \
  tests.test_document_job_list_query_v2_writers.MysqlV2WriterShapeTests \
  tests.test_document_job_list_query_v2_writers.SqliteV2PublishedWriterTests \
  tests.test_document_job_list_query_migration.DocumentJobListQueryMigrationTests \
  tests.test_document_job_delivery_state_migration.DocumentJobDeliveryStateMigrationTests.test_fake_mysql_schema_partial_forward_and_payload_projection \
  tests.test_document_job_delivery_state_migration.DocumentJobDeliveryStateMigrationTests.test_fake_mysql_write_failure_calls_rollback_and_keeps_last_success_cursor \
  tests.test_database_job_repository.PersistenceAdapterTests.test_document_jobs_api_pdf_callback_flow_uses_mysql_repository \
  tests.test_document_job_list_query_v2_service \
  tests.test_document_job_list_publish_light_check
```

首轮 98 项，97 通过、1 失败，6.569 秒；原始日志 `data/key-local-tests.log`。失败为 `test_writer_and_state_backfill_keep_projection_current` 仍将新小 JSON 与旧完整语义 JSON 比较，是本次改变布局直接影响的测试断言；产品行为无失败。修正该断言，并添加五列 NULL 在成功请求后、空页/无匹配/状态筛选空集仍拒绝的交叉用例，实际仅执行：

```sh
PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python -m unittest \
  tests.test_document_job_list_query.DocumentJobListQueryTests.test_writer_and_state_backfill_keep_projection_current \
  tests.test_document_job_list_query_readiness.DocumentJobListReadinessTests.test_missing_keys_after_success_still_fail_outside_filtered_page
```

2 项通过，0.015 秒。合并计算 **99 个不同离线用例最终通过**；没有将重跑计为额外用例。分布为 readiness 9、list query 10、v2 SQL/facts 19、大 key 2、三类 writers 13、迁移 27、状态迁移 2、fake MySQL API 1、service 13、publish light 3。service 与 publish 共 16 项覆盖完整列表、API 503、分页解码量、有效复核/时钟、表格、发布默认深度与非管理员/提交保护，不需要因接入而扩大全仓。

通过受控 Python 包装读取本任务 `data/mysql-environment/credentials.json`，只在子进程环境映射既有 `MD2WORD_TEST_MYSQL*`，没有打印凭据。实际命令：

```sh
PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python -m unittest tests.test_document_job_list_query_v2_mysql
```

**12 项全部通过、无 skip，3.586 秒**，包括 4 个入口/离线 guard、7 个真实引擎 v2 用例和 1 个真实引擎大 key 用例；日志 `data/key-mysql-tests.log`。新增真实引擎用例覆盖五列 NULL 的 V 域拒绝、可靠隐藏任务缺 key 与坏关联文件 JSON 不阻断。既有实际引擎用例覆盖权限/统计域/分页、字面搜索、寻址 collation 别名、RR 两连接快照、缺列 DDL/回填/全量 verify、receipt 前缀与即时 guard。大 key 覆盖完整前缀后单字符/大小写/尾空格、29 种查询与 Python owner 对照、dry-run/apply/verify/重跑。

环境 MySQL **8.4.13 arm64**，与生产 8.4.9 不同；实际双表 collation 为 `utf8mb4_0900_ai_ci`。测试前后独立查询 schema 集合完全相同，只有四个系统库；证据 `data/key-mysql-test-cleanup.json`。本轮一共 **111 个不同用例最终通过**。现有 Starlette 弃用警告保留。

## 合成性能与完整结果

新独立脚本 `benchmark-key-mysql.py` 复用原 `benchmark-ready-mysql.py` 的测量及合成夹具 helper，没有改写原脚本和原结果。旧查询从固定 HEAD 读取；ready 从只读来源再次核验已记录 SHA 后冻结为 `data/key-source-freeze/ready-sql.py`。组合候选身份见上文，脚本输出中也记录三者 SHA。

```sh
PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python \
  .trellis/tasks/11-06-list-loading-performance/research/benchmark-key-mysql.py \
  --credentials .trellis/tasks/11-06-list-loading-performance/research/data/mysql-environment/credentials.json \
  --output .trellis/tasks/11-06-list-loading-performance/research/data/mysql-key-benchmark.json
```

结果与过程日志分别为 `data/mysql-key-benchmark.json`、`data/mysql-key-benchmark.log`。使用 119 任务/1,928 文件，固定 `as_of=2026-10-30T00:00:00+00:00`，receipt/current metadata 分别 35,000/3,500 字符。全部数据合成，不含生产 payload。先从相同权威 payload 构造旧布局，旧/ready 各执行两种查询各一次；仅变更派生布局 apply+全量 verify 后，组合候选各执行首次加三次。两个布局阶段各自 RR 只读一致快照，期间没有并发写者；不声称跨迁移使用同一数据库快照。

共 **12 次查询的完整 DocumentJobListResult 相等**，包含 items 模型、observed_results、total 和三统计域；只保存摘要。已有旧/ready 的三次中位数直接复用，不重复 16 次旧计时。下表旧/ready 为前一轮冻结结果，组合为本轮新实测，都是相同合成输入构造，但并非同一轮随机交替比较。

| 请求 | 旧中位数（继承） | ready 中位数（继承） | 组合首次 | 组合三次中位数 |
| --- | ---: | ---: | ---: | ---: |
| 默认首页 page_size=20 | 6.856s | 6.444s | 0.101110s | **0.103204s** |
| 无匹配搜索 | 6.589s | 6.001s | 0.088051s | **0.087858s** |

本轮旧/ready 单次核对分别为默认 6.938369/6.699619 秒、无匹配 6.523613/6.062523 秒，不作为三次中位数。组合两种查询均为 11 SELECT。默认页首条合并 shape 中位 **0.036651 秒**，旧 ready 对应中位 2.5846 秒；其余默认页各 SELECT 中位秒为 `0.007526, 0.002245, 0.002094, 0.008525, 0.011117, 0.004574, 0.013897, 0.004610, 0.004559, 0.006170`。小 JSON 均值 job **914**、file **495** 字节；keys 仍完整保存。

计时包括查询 Python、SELECT execute/fetch 和页模型解码，不包括 service 动作、HTTP、浏览器或渲染。首次不是重启冷缓存，三次不是 p95。该样本均值接近已测生产投影，但没有复刻长尾、业务状态、权限分布或并发。本地合成结果不能替代 AC-2 的真实接口/浏览器验收。临时 UUID 库退出后另查 INFORMATION_SCHEMA，确认已删除；共享隔离 MySQL 容器/profile 按主会话要求保留。

## 迁移、回退与交付边界

采用来源已经审核的迁移设计，生产动作均未执行。上线前另行核对目标实例/库、停止全部旧 API/Worker/脚本写者、备份并隔离恢复演练、dry-run、files→jobs apply、空游标全量 verify、原列/其他表不变核对与固定 as_of 差分，再启动统一新版本。逐列 DDL 可能已提交，不按事务回滚解释；批次续跑只用已提交成功游标。

禁止混部。仅回退镜像不足：保持停写，用冻结旧版本工具从 payload 重建旧大 JSON、全量 verify 后才恢复旧进程；新增列可保留。旧写者恢复后新列全部视为陈旧，再升级须双表从头重建。独立入口自身不提供服务器 UUID 绑定，未来生产执行仍需任务级目标保护，不能直接套用本地测试凭据或动作。

`git diff --check` 通过；最终范围只含候选、直接测试和任务证据，未覆盖其他并行工作。Python 新增/改动 docstring、说明性注释、CLI 帮助与开发者消息保持中文；未对无关 legacy 文本做批量翻译。独立只读复核由主会话安排，异常列表性能与生产验收仍由主任务继续处理。
