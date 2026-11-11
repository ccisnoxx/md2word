# ready 候选真实 MySQL 定向验证与合成计时

日期：2026-11-07。所有数据库操作仅针对主会话提供的本地隔离 MySQL；凭据文件为 0600 且已由 `git check-ignore` 确认为忽略路径，未输出其内容。没有访问生产，没有删除共享容器。

## 本轮实际引擎验证

通过受控 Python 包装从 credentials JSON 设置既有 `MD2WORD_TEST_MYSQL*` 环境变量，执行 `PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python -m unittest tests.test_document_job_list_query_v2_mysql`。

结果为 **10 项通过，1.431 秒**，无失败或 skip；原始安全日志为 `data/mysql-v2-ready-tests.log`。该模块覆盖有效复核/权限/汇总/排序/分页、全文搜索及字面通配符、collation 别名 ID 错误、双连接快照、回填与 receipt/guard 等既有合同。模块用自身 UUID 库并在 context manager 退出时删除；本轮没有扩改测试或产品。

实际 MySQL 为 **8.4.13**，生产探针声明为 **8.4.9**，不能把版本差异省略。双表实际 collation 为 `utf8mb4_0900_ai_ci`，基准事务显式使用 RR 一致只读快照。

## 可复核脚本和输入

脚本：`research/benchmark-ready-mysql.py`；完整结果：`research/data/mysql-ready-benchmark.json`；逐次进度：`research/data/mysql-ready-benchmark.log`。

```sh
PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python .trellis/tasks/11-06-list-loading-performance/research/benchmark-ready-mysql.py --credentials .trellis/tasks/11-06-list-loading-performance/research/data/mysql-environment/credentials.json --output .trellis/tasks/11-06-list-loading-performance/research/data/mysql-ready-benchmark.json
```

冻结旧 SQL 来自 `25860865812ef5bb9159a449aaa7df0a6dfcb815` 的 `git show`；当前候选为本任务已经逐字节接入的 ready 文件。两者复用相同库、连接、固定 aware `as_of=2026-10-30T00:00:00+00:00` 和同一 RR 只读快照。计时包含查询层 Python 和页模型解码，逐 SELECT 计时包含 execute/fetch；不包括建库、seed、连接建立、service 动作、HTTP、网络浏览器或渲染。

这里的“当前候选”指此次实际执行时的冻结 ready 身份，具体 SHA 见文末。后续主会话已开始接入拆列；重现此实验须使用匹配的 ready-only checkout、writer 和夹具，不能在拆列后的工作区原样重跑并称为同一实验。

采用既有 fixture 和真实 repository writer 构造 119 个可见完成任务、1,928 个 generated_word 文件；每个任务嵌入 receipt 文件的 metadata 合成字符串为 35,000 字符，当前文件 metadata 为 3,500 字符。这忠实复用来源验证记录中的合成方式，但原记录没有保留完整内联脚本，因此不是声称逐字节复刻原夹具。当前与 receipt metadata 不同会使有效批准失效；这是受控的等价/大 key 负载样本，不代表生产 QA 分布。

新样本投影为 job 平均/最大 **109,197 字节**、file 平均/最大 **9,161 字节**。主会话提供的生产只读样本为 job 平均 111,623/最大 2,377,676、file 平均 8,995/最大 2,376,229；本合成样本均值接近，没有模拟生产长尾、权限分布、状态分布或并发。不能把本地结果换算为生产净收益。

## 请求结果

每个请求类型先执行旧/新各一次，确认成功及结果一致后再各三次；后三轮交替实现执行顺序。共 16 次，全部完整 `DocumentJobListResult` 相等（包括完整 items、observed_results、total 和三统计域），内存比较后只保存结果 SHA。首次已建好库，不能称为重启后的冷缓存；三次中位数不是 p95。

| 请求 | 旧首次 | ready 首次 | 旧三次中位数 | ready 三次中位数 | 下降 |
| --- | --- | --- | --- | --- | --- |
| 默认 page=1/page_size=20 | 6.985s | 6.329s | 6.856s | 6.444s | 6.0% |
| 无匹配 q，page_size=20 | 6.517s | 6.036s | 6.589s | 6.001s | 8.9% |

正常页 total=119/items=20，搜索无匹配 total=0/items=0；所有请求均为旧 13 条、新 11 条 SELECT。**ready 在此合成样本仍明显超过 2 秒**，只减少扫描条数不足以达到本任务目标；可据此评估已有拆列候选，接入和进一步验证由主会话决定。

## 默认页 SELECT 分段

下表为三次各语句耗时的中位数；分段中位数之和不等于总耗时中位数。JSON 同时保留所有请求类型的每次每条 SELECT 时长、序号、返回行数及 SQL SHA，不保存 SQL 参数或 payload。

| 原阶段 | 旧 SELECT 序号 | 旧中位数 | ready SELECT 序号 | ready 中位数 |
| --- | --- | --- | --- | --- |
| 任务 shape | 00 | 1.5568s | 合并为 00 | 2.5846s（同一条） |
| 文件 shape | 01 | 1.2027s | 合并为 00 | 2.5846s（同一条） |
| 文件 ID | 02 | 0.3175s | 合并为 00 | 2.5846s（同一条） |
| 到期类型 | 03 | 0.3980s | 01 | 0.4255s |
| quality 错误 | 04 | 0.1570s | 02 | 0.1618s |
| binding 错误 | 05 | 0.1532s | 03 | 0.1609s |
| descriptor 错误 | 06 | 0.4670s | 04 | 0.4869s |
| receipt 到期类型 | 07 | 0.6014s | 05 | 0.6012s |
| V summary | 08 | 0.3401s | 06 | 0.3403s |
| QA summary | 09 | 0.7820s | 07 | 0.8021s |
| filtered summary | 10 | 0.3378s | 08 | 0.3404s |
| 排序时间类型 | 11 | 0.3314s | 09 | 0.3294s |
| 页 payload | 12 | 0.2182s | 10 | 0.2195s |

两条 shape 和原 ID 检查合并后，首条聚合仍耗时约 2.585 秒；后续 effective review/统计也有剩余开销。该结果解释了为何不能把生产原 shape 的 3.044+2.254 秒当作 ready 的净节省。

## 身份与清理

- `baseline_sql_sha256`：`0a01ec4a9a6c1623edf49960925ced677fbdee88dec0314202b17ccf55fa61b4`。
- `candidate_sql_sha256`：`061ab44e5b9c88490103ee7701dcd96f389d5d2bda2f349dd6f1ea9923fd6aeb`。
- 基准脚本 SHA-256：`979d268d612ca42354e7ed0e3713b43fff898d601e9284bf7e23b3fdff7fe557`。
- 本次 UUID 库：`md2word_query_test_281defcff53a44e597bfe11f679a0909`；退出后独立查询 INFORMATION_SCHEMA 确认不存在，`schema_removed=true`。

`git diff --check` 通过。脚本的 docstring、注释和开发者消息为中文，机器字段保持原名。本轮新增实测证据不替代生产发布或浏览器验收；AC-2 仍未满足。本轮未修改产品、其他 worktree 或 Spec，未 commit/push/archive/add_session。
