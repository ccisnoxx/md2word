# 异常读取会话实施与验证

日期：2026-11-07。用户已批准 incident-read-session-plan.md 的本地实施与定向验证。工作区 `/Users/sc/PycharmProjects/md2word-wt/list-loading-performance`，未提交、推送或操作生产；上一轮 ready+key 候选保持。主会话维护 Spec 和任务三件套。

## 冻结与变更范围

实施前对下列七模块双读冻结为 `data/incident-source-freeze/files/<原路径>`，逐文件 SHA 位于 `data/incident-source-freeze/manifest.json`；manifest SHA-256 为 `0df9166e594fc3b4c57420d190cd262ae34f3693e92be5d9f832a878e1a971f0`。这是当时已经整合 key 的实际工作区字节，未用 `git show HEAD` 替代。

| 产品模块 | 改动与责任 |
| --- | --- |
| `app/domains/files/repository.py` | 新增只含 get/protected 两方法的 `DocumentFileReaderProtocol`；完整仓储新增 `read_session()` |
| `app/infrastructure/persistence/mysql/backend.py` | 提取原提交/回滚规则为 `_transaction`；读取会话惰性持有单物理连接，每次 connect 块仍独立提交/回滚，外层结束关闭 |
| `app/infrastructure/persistence/mysql/files.py` | 会话生成局部仓储，只有 get/protected 使用显式 read_connect；普通读取和所有写者继续原 backend.connect |
| `app/infrastructure/persistence/file/files.py` | 无状态 nullcontext reader，原文件读取行为不变 |
| `app/infrastructure/persistence/sqlite/files.py` | 无状态 nullcontext reader，原 SQLite 事务不变 |
| `app/domains/document_jobs/service.py` | 六个方法显式传递可选 file_reader，不改 singleton 字段；默认调用者继续原 file_repository |
| `app/domains/document_jobs/incidents.py` | 原参数校验、请求时间和搜索归一化之后，仅首次有效复核至分类阶段打开会话，页内动作之前关闭 |

六个传递方法为 `list_visible_jobs`、`_effective_job`、`build_incident_classification_view`、`_build_result_read_view`、`_get_completed_result_file`、`_ensure_file_not_expired`。两种读取 SQL、模型/ID 验证和保护 JSON 解析保持单一实现。get 模型及 ID 验证仍在 commit 后；保护 JSON 解析仍在事务内。逐次时钟、先后复核降级、主件门控及页内 observed_result_view 未合并或缓存。

无自动重连、重试、全局池、跨请求状态、额外 schema/index 或批量 SQL。复用物理连接减少建连/关闭机会，不声称网络故障机会逐连接完全等价；真实 SQL、提交、回滚和关闭错误仍传播。读取会话不改变普通后端的 `except Exception` 范围及原 rollback 能力检查。

新增直接测试 `tests/test_document_file_read_session.py`、`tests/test_document_file_read_session_mysql.py`，新增研究脚本 `research/benchmark-incident-session.py`。七产品模块在首轮实施后未因测试或基准修改。

## 本轮直接检查

实际解释器 `/Users/sc/PycharmProjects/md2word/.venv/bin/python`，设置 `PYTHONDONTWRITEBYTECODE=1`。

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest \
  tests.test_document_file_read_session \
  tests.test_document_job_incident_publish_light_check \
  tests.test_document_job_list_query_v2_service \
  tests.test_document_job_list_publish_light_check \
  tests.test_document_job_list_query_v2_writers.MysqlV2WriterShapeTests \
  tests.test_document_job_delivery_state_migration.DocumentJobDeliveryStateMigrationTests.test_fake_mysql_write_failure_calls_rollback_and_keeps_last_success_cursor
```

**35 项全部通过，6.106 秒，无失败/skip**。日志 `data/incident-session-local-tests.log`。新测试 10 项，原异常分类/时钟/动作 4 项，普通列表 service+publish 16 项，直接 MySQL writer 4 项及写失败回滚 1 项。

覆盖零读取不建连、68+24 读取保留逐次提交、SQL/commit 错误 rollback+close 且不重连、建连/close 错误可见、文件 JSON/model/id 错误在 commit 后、保护 JSON 错误在事务内、局部仓储不改变普通读或写锁连接、参数错误先于会话、页内动作晚于会话退出、首次复核降级不提升、naive 到期异常、同一 singleton 两个并发请求各持独立连接。既有观察回归覆盖分类前/后到期、缺件/身份/未完成门控、页内观察复用及诊断/批量保持完整核验。普通列表调用共享 service 和 backend 的输入已变化，因此执行直接交叉回归；未机械复跑旧 111 项。

真实引擎入口通过受控 Python 包装读取 `data/mysql-environment/credentials.json` 的完整环境映射，仅注入测试子进程，不输出凭据。实际测试命令：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_document_file_read_session_mysql
```

**2 项全部通过，0.136 秒，无 skip**。日志 `data/incident-session-mysql-tests.log`。显式设置并读取确认 RR；第一次主件读取提交后，第二连接通过真实 current key writer 更新文件，原物理连接的下次读取能看见更新；保护关系也能看见第二连接新提交。两种读取共 4 次独立 commit、1 次 close，连接 ID 不变。额外核对 current key 三列与最终 payload 一致。真实 JSON/model/id 错误仍 commit 后抛出，保护 JSON 错误 rollback 后关闭。

环境为 run2 专属 MySQL **8.4.13 arm64**，server UUID `fc058e39-d9fe-11f1-b70f-4e6d454ad100`，实际双表 collation `utf8mb4_0900_ai_ci`；不是生产 8.4.9。测试前后独立查询 schema 集合均只有四个系统库，见 `data/incident-session-mysql-cleanup.json`。本补充方案共 **37 个直接用例通过**，不与旧 111 项简单相加冒充当前全仓覆盖。现有 Starlette 弃用警告未扩展处理。

## 独立冻结差分与合成基准

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python \
  .trellis/tasks/11-06-list-loading-performance/research/benchmark-incident-session.py \
  --credentials .trellis/tasks/11-06-list-loading-performance/research/data/mysql-environment/credentials.json \
  --output .trellis/tasks/11-06-list-loading-performance/research/data/incident-session-benchmark.json
```

结果 `data/incident-session-benchmark.json`，进度 `data/incident-session-benchmark.log`。脚本逐项核验冻结 manifest，从冻结字节独立加载旧 service/incidents/mysql backend/files；不让旧路径调用候选的这四个实现。未改变的 Pydantic 模型、权限/复核/下载 owner、current key job writer 与建表来源由双方复用。file/SQLite/protocol 的改前字节也保留在七文件冻结中，但 MySQL 基准不运行它们。双方时钟固定为 `2026-10-30T12:00:00+00:00`，无人工 sleep/延迟注入。

合成库有 119 jobs、1,928 files、74 可见任务，其中 68 个完成态、24 个到期文件、6 个失败任务、8 个带降级页任务，共 14 个异常。所有可见任务没有 verified binding，所以首次有效复核不读文件，与线上探针该阶段 0 get 的分布相符；首次降级与时钟变化另由上面的直接回归保护。metadata 为合成字符串，无真实 payload。旧/新共享相同库和输入，基准期间没有并发写者；每次原读取仍独立事务，**不把全列表包装为单快照**。

默认管理员页先各一次，再交替顺序各三次；操作员默认、第二页、空页、无匹配搜索各做一对。共 **8 对、16 次正常请求**，比较完整响应（条目、顺序、summary、所有动作）相等。另注入坏文件 JSON、无效模型、ID 不匹配、naive expiry 四种错误，**4 对、8 次失败请求**的异常类型与消息也完全相等；只保存摘要，错误样本不计成功性能。已知旧/新双方相同错误在这里用于验证异常合同，不代表正常性能验收。

| 默认管理员请求 | 冻结旧路径 | 会话候选 |
| --- | ---: | ---: |
| 首次完整调用 | 0.554355 秒 | 0.122761 秒 |
| 后三次完整调用中位数 | **0.542135 秒** | **0.116432 秒** |
| 可见列表阶段中位数 | 0.006199 秒 | 0.006394 秒 |
| 分类阶段中位数 | **0.460255 秒** | **0.043158 秒** |
| 页内动作阶段中位数 | 0.071683 秒 | 0.064786 秒 |
| 建连耗时合计中位数 | 0.463143 秒 | 0.065687 秒 |
| execute 耗时合计中位数 | 0.029058 秒 | 0.023759 秒 |
| 分类主件 get / 保护 SELECT | 68 / 24 | 68 / 24 |
| 分类物理连接 | **92** | **1** |
| 页内 clone 源文件读取 | 14 | 14 |
| 完整请求物理连接 / close | **107 / 107** | **16 / 16** |
| 完整请求 commit / rollback | 107 / 0 | 107 / 0 |

完整请求还包含原有一次 jobs 列表连接和 14 次页内 clone 源文件读取；这些保留原路径，未扩大连接复用范围。分段中位数不保证相加等于整体中位数；connect/execute 是总计内的重叠拆分，不能再次相加。计时包含 service 分类和动作、响应模型构造及 model_dump，不含 HTTP、认证、网络浏览器和渲染。首次不是重启冷缓存，三次不是 p95。

## 基准失败与修复

基准首次执行时把“完整请求 file_gets”误断言为 68，实际页内 clone 还会读取源文件，计数断言失败。先检查真实调用确认原因，再仅修改研究脚本记录分类与页内阶段的计数，保持产品、夹具和业务读取不变。保存原失败日志为 `data/incident-session-benchmark-first-failure.log`；重跑前独立核对只有四个系统库，见 `data/incident-benchmark-failure-cleanup.json`。修复后只重跑本脚本，没有重复 37 个已通过测试。

成功基准退出后独立查询 INFORMATION_SCHEMA 确认本次 UUID 库不存在，`schema_removed=true`。专用容器/profile 不由本实现者擅自清理，已通知主会话验证结束，后续清理由主会话统筹。

## 审查、文档与剩余边界

主会话安排的只读独立审查已对冻结七模块增量及新测试复核，未发现确认产品缺陷；产品在审查后未修改。`git diff --check` 通过，保持上一轮普通列表源码；没有来源 worktree 写入、临时服务启动或生产操作。

新增/改动 Python docstring、解释性注释、测试错误文本及研究说明使用中文；保留协议、标识符和测试机器字段。没有对无关 legacy 文本做批量翻译。

本轮证明单请求物理连接复用机制、逐操作事务边界及本地合成收益。不能把生产测得的 1.78 秒建连成本全部当作已实现线上净收益；生产版本、网络、负载、状态分布与本地样本不同。未发布，未重新测量生产 API 或浏览器，整体 AC-2 仍未验收。该读取会话本身无 schema 迁移；整体候选仍包含上一轮 key 拆列，生产仍须单独授权并遵守原停写/备份/回填/verify/回退条件。
