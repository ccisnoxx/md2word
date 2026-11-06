# 成本来源与 MySQL 边界

基线：`828e1d9d656bf266cba7bba0ed23a62c550db15c`。以下来自当前源码静态检查，没有连接 MySQL 或生产。

## 四条路径

| 路径 | 当前成本来源 | 静态增长判断 |
| --- | --- | --- |
| 任务列表 | `app/infrastructure/persistence/document_job_list_query.py:118` 两表投影全量形状检查；`:148` 起的身份、时间与规则错误检查；`:190`、`:231` 分组、排序与分页。`app/domains/document_jobs/service.py:1372` 仅为返回页构建动作。 | 默认无日期条件为 13 条读取 SQL，次数不随 N 增长；JSON 条件与重复全表检查的工作量随 N/F 增长，不能视为常数查询。排序成本依赖引擎计划。日期上下界额外增加检查 SQL。 |
| 异常中心 | `app/domains/document_jobs/service.py:1446` 调用仓储全量列表后做可见性过滤；`app/domains/document_jobs/incidents.py:87` 保留全部可见任务，`:90` 分类，`:107` 对全部异常排序后分页。`app/domains/document_jobs/service.py:828` 有效复核、`:1517` 分类期间存在主件元数据观察。 | 读取/投影至少 O(N)，主件读取随成功且有结果的任务数增长；一般排序上界 O(I log I)，不能将固定页大小当作固定成本。 |
| 单文件保护 | `app/infrastructure/persistence/mysql/files.py:88` 无 WHERE 查询全部 publication 的 `protected_file_ids`，`:90` 逐行解析 JSON 做成员判断；SQLite 对应 `app/infrastructure/persistence/sqlite/files.py:82`。 | 1 条 SQL，但每次传输/读取 P 条保护集合；未命中时解析全部，命中仅能缩短 Python 解析，不能减少已经 fetchall 的记录数。若每条集合 K 个文件，成员检查上界 O(PK)。 |
| 保留期计划 | `app/domains/files/retention.py:87` 一次加载全部文件，`:92` 对每个非 deleted 文件调用保护查询，甚至在到期时间过滤之前。 | F 个未删除文件时为 1+F 次仓储/读取 SQL；读取量 F+F×P，固定 publication/file 比例下近似二次增长。`:114` 的 mark_expired 另有写入与重核，本次不测。 |

## MySQL 与本地测量的差异

1. 本地计时是 SQLite 业务服务调用，不包含 HTTP 认证、路由 DTO 序列化、网络、连接握手、服务端并发与远程数据库等待。列表路由在 `app/domains/document_jobs/router.py:219` 调服务后另构造响应；异常路由直接返回服务响应。结果不能当作 HTTP P95 或生产 SLO。
2. MySQL 列表在 `app/infrastructure/persistence/mysql/document_jobs.py:124` 明确设置 REPEATABLE READ 并启动只读一致快照；SQLite 使用自己的读事务。SQLite 的 EXPLAIN/VM 指令/扫描推导不等同 MySQL 的 optimizer、rows_examined、锁等待、buffer pool 或临时表成本。
3. 源码 MySQL schema 在 `app/infrastructure/persistence/mysql/schema.py:366`、`:411` 将投影存为 LONGTEXT，现有索引为文件/任务主键及 created_at；未发现 JSON 成员或业务筛选表达式索引。查询使用 JSON_EXTRACT、JSON_UNQUOTE、CAST 与 JSON 中的时间排序，不能仅凭 created_at 索引存在就断言会利用该索引。运行中的实际 DDL、执行计划、JSON 函数扫描和索引收益均**需真实 MySQL 验证**。
4. publication 的现有唯一索引保护 result/job/generation/request，不提供任意 `protected_file_ids` 元素查找索引（`app/infrastructure/persistence/mysql/schema.py:416`）。无条件 SELECT 在源码层面要求返回全部集合；服务端实际物理扫描页数、网络字节、耗时仍需真实 MySQL 验证。
5. file 后端会读取/解码 JSON 元数据文件，成本与 SQLite 不同；本次选择用户允许的 SQLite 后端，不声称测过 file 后端。SQLite 元数据文件的底层 OS 页读取次数没有被当成对象正文读取次数。
6. 合成任务状态、文件比例、publication 密度、单记录大小和访问局部性不代表生产分布；119 个任务与 2511 个事件只用于档位参考。未访问真实业务内容或数据库。
7. tracemalloc 只度量 Python 分配，SQLite C 层缓存及本机 mmap 不在其中；进程 ru_maxrss 是累计高水位，不能称单次请求新增 RSS。温缓存、单进程、无并发的有限样本经验 P95 不代表稳定线上尾延迟。

## 后续方向约束

只有测量超出建议预算的路径才提出后续优化。列表应先在授权隔离 MySQL 获取实际计划，定位重复扫描/JSON 计算，不删除现有投影有效性和异常拒绝检查。异常中心优先保留分类语义并消除同请求内可避免的重复主件观察，必要时单独设计元数据筛选下推；不缓存过期复核状态。

保留期计划可单独评估请求内一次读取保护集合以减少重复扫描，但计划不是删除授权，实际写入/删除必须保留当前实时保护重核与原锁序；不能把本报告理解为已验证该优化并发安全。需要 file→publication 映射或持久化索引时，接入 B08 设计迁移、回填、写一致性与回退，再在真实 MySQL 验证，B10 不实施。
