# 本任务的冻结镜像外置运维载体

状态：**本地候选；未在真实 MySQL、生产或隔离恢复环境演练。** 仅在后续批准窗口使用。当前脚本不会自行启动容器、SSH、API、Worker、备份或恢复；本轮没有执行这些动作。脚本只读挂入完整镜像，产品源码与冻结镜像输入不变。

## 运行约束

- 容器工作目录 `/app`，本目录只读挂载到 `/ops`，设置 `PYTHONPATH=/app` 和 `PYTHONDONTWRITEBYTECODE=1`。使用已核对的旧/新完整镜像 ID，不能把候选源码覆盖到旧镜像。
- 明确设置 `JOBS_MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`；不读取 `.env`，不从 argv 接受密码，不回退到默认连接参数。密码只通过批准的临时环境提供，环境和完整迁移报告不得公开。
- 每个实际交给 migration owner/仓储的物理连接都核对 `DATABASE()` 与 `@@server_uuid`。连接不符即关闭，不进行 schema/数据访问，不重连或自动重试。明确设置并读取验证 RR、会话只读/读写、行锁和元数据锁等待 10 秒；时间区固定 UTC。迁移 owner 继续使用 `initialize=False`。
- 所有摘要采集/对照必须停相关写者、DDL 和定时事件，确认账号对**整个业务库**有读取与元数据可见权限，并核对完整表清单；预期现场是 34 个 InnoDB 表。仅相同表数不足以证明权限完整。RR 保护数据观察，不保护并发 DDL；不能在仍有写者时把前后不等解释为迁移缺陷。
- router 对照仅允许隔离恢复实例；`--deny-server-uuid` 填真实生产 UUID，必须不同于恢复实例 UUID。只读账号、只读 rootfs、对象/配置/运维挂载，以及网络只允许隔离 MySQL，由外部执行载体落实。脚本审计 hook 额外阻断其他 socket、写文件与子进程；它不代替 OS 隔离。必须先确认恢复卷完整及容器内路径与原配置一致。
- 使用不覆盖旧结果的证据目录/文件。重定向输出前由执行载体独占创建 0600 文件，目录 0700；命令示例中的输出文件不能以普通 `>` 覆盖旧证据。以下仅展示容器内 argv，不代表已授权执行。

## 迁移：新旧镜像共用入口

```text
python /ops/migrate.py --expect-database <库名> --expect-server-uuid <实例UUID> --dry-run --batch-size 100
python /ops/migrate.py --expect-database <库名> --expect-server-uuid <实例UUID> --apply --batch-size 100 --after-file-id <已提交文件游标> --after-job-id <已提交任务游标>
python /ops/migrate.py --expect-database <库名> --expect-server-uuid <实例UUID> --verify --batch-size 100
```

入口直接调用镜像内 `scripts.ops.migrate_document_job_list_query.migrate_document_job_list_query`，不重写迁移算法、版本、报告、异常分类、游标推进或退出码。旧镜像 owner 生成 job/file **2/1**，新镜像生成 **3/2**。新布局前滚增加五列，旧镜像回退只重建旧 JSON，保留已经存在的五列；它们不能替代旧 owner 的 verify。

dry-run/apply 每表至多一批，先 files 后 jobs；必须按原报告的 `tables.document_files/document_jobs`、`status`、`has_more`、`last_successful_*` 判断。失败保留真实报告及已提交游标，不用 `last_scanned_*` 冒充成功游标。DDL 已提交不可宣称由后续 rollback 撤销。verify 必须空双游标、全量双表同快照、exit 0 且 `all_ready=true`。恢复旧写者后再升级必须停写、清空双游标从头重建，不能只补 NULL。

## 全库原列 snapshot/compare

```text
python /ops/snapshot.py snapshot --expect-database <库名> --expect-server-uuid <实例UUID>
python /ops/snapshot.py compare /evidence/before.json /evidence/after.json --require-new-keys
python /ops/snapshot.py compare /evidence/before.json /evidence/rollback.json
python /ops/snapshot.py snapshot --expect-database <库名> --expect-server-uuid <实例UUID> --include-derived
```

采集在单连接 `START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY` 内读取全库所有 InnoDB 表。原列使用 `CAST(... AS BINARY)` 保持文本 payload 的原始字节，不 JSON 解析重写；类型、NULL 标记、字节长度参与 SHA-256。逐行摘要排序后汇总，**不去重、不要求主键**，行数另存。流式游标只读取一批原始行，内存保留固定长度行摘要。输出仅表/列结构、行数和摘要，不输出业务行、密码哈希、对象路径或原始 DDL。

只忽略 `document_jobs.list_query_json`、`document_files.review_query_json` 的值，以及本次五个新增 key 列的值。原 JSON 两列的结构仍比较；payload、ID、原时间及其他原列全部进入保真摘要。五列新增定义必须是 nullable LONGTEXT，无默认/生成/extra/comment，并沿用原投影字符集/collation；已有 key 列结构也不得改动。保留原列顺序和结构，规范化 SHOW CREATE 只删除允许的五列定义，继续比较索引、约束和表选项；全库表清单、库字符集、触发器、事件、routine 元数据纳入摘要。

`--require-new-keys` 要求两表五列全部存在；回退比较不要求新增列被删除。迁移保真结果不验证派生事实业务内容，必须同时取得对应镜像 owner 的全量 verify。**备份/恢复前后需另用 `--include-derived` 采集同布局快照**，使所有派生值及新增列结构也参与比较；不能用默认迁移模式声称全部列恢复一致。两种 scope 混用明确失败。工具对非 InnoDB、视图、不完整 routine 定义和 FLOAT/DOUBLE/REAL 原列明确失败：当前方案没有证明浮点文本转换无损，不把近似结果报告为通过；若实际库出现这些情况须先补充方案。快照不备份对象卷、Redis 或数据库原始数据，也不代替恢复验证。

## 完整 router 差分

```text
python /ops/query_diff.py capture --expect-database <恢复库> --expect-server-uuid <恢复UUID> --deny-server-uuid <生产UUID> --as-of 2026-11-07T00:00:00Z --cases /control/cases.json
python /ops/query_diff.py compare /evidence/old-router.json /evidence/new-router.json
```

同一只读 `cases.json` 逐项指定真实已存在的内部账号 ID、预期角色、入口和参数。此文件含真实标识时仅放在 0700 控制目录的 0600 文件，不进入仓库。结构示例中的账号只是格式占位，**不能直接运行作为真实验收**：

```json
[
  {"user_id": "<真实admin ID>", "expected_role": "admin", "endpoint": "jobs", "params": {}},
  {"user_id": "<真实operator ID>", "expected_role": "operator", "endpoint": "incidents", "params": {"page": 1, "page_size": 20}}
]
```

正式矩阵须为每种实际角色同时覆盖两个入口的默认首页、全部实际分页、越界空页、明确无匹配搜索；按可用真实样本补充 QA/状态/排序、完成态/到期/发布/表格动作。执行者审核并冻结完整矩阵；脚本不自动声称覆盖已足够。`jobs` 可用参数来自真实 `list_document_jobs`；状态字段名为 `status_filter`，日期需 aware ISO。`incidents` 使用 `stage` 等真实 router 参数。脚本至少要求真实 active admin 和 operator 均有成功样本；这只是输入下限，两个 case 不算正式验收。缺账号或所需样本是覆盖缺口，不能伪造用户、提升角色或静默跳过。同一侧需使用相同矩阵/as_of 连续采集两次并 compare，先证明确定性，再比较 O/C；当前没有执行这项演练。

在同一恢复实例按 O→C→R 顺序切换兼容的投影布局，每个阶段使用对应完整镜像的独立进程；不要求并行两库。旧/新响应以同一原数据、对象副本、配置、矩阵和 aware `as_of` 对照。依赖按 `app/main.py` 的真实构造参数组装，复用 MySQL publications、file protection、文件读取、模板、资源快照、术语、预览与 audit owner；仅构造 Celery adapter，不创建/投递任务，不导入 main/build_runtime，不调用 seed/bootstrap/recovery。只支持本次已审查的 Celery 配置，其余配置明确阻断。真实用户从 `internal_users` 读取并核对 ID、active 和 role，按 AuthService 同字段/权限映射为上下文；没有签 JWT，也没有运行登录或 HTTP 权限依赖。此处是**router/业务完整响应对照**，正常认证浏览器验收另做。

全部已加载业务模块所引用的统一 `utc_now` 固定为同一 aware UTC；真实依赖、读取次序和动作资格未替换。完整 `model_dump(mode="json")`（含所有条目、顺序、summary、动作及其他响应字段）规范化后计算摘要。输出只有矩阵/可见域摘要、角色、入口、total、items 与完整响应摘要。router 执行期间的下游标准输出/错误在内存中丢弃，异常只输出受控分类；任何异常立即非零，任一侧失败/空报告均不能通过，双方相同错误也不能通过。审计 guard 即使被下游捕获，也会使整次采集失败。

目前尚未取得真实恢复库、对象挂载和新旧完整响应结果；本脚本的本地 helper 测试不能替代这项演练。相同完整响应也不能证明独立真实认证、页面加载时间或生产性能。

## 本轮离线证据

执行命令：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s .trellis/tasks/11-06-list-loading-performance/research/release_ops -p test_release_ops.py -v
```

12 项通过：每条连接实际身份、会话保护、显式配置/脱敏失败、原 migration 报告与游标透传、typed/length/NULL/重复行编码、全库允许列与其他表变更、原 payload/DDL/表清单变更失败、真实依赖无初始化装配、固定 aware 时钟、完整响应摘要/双方错误拒绝、独立本地子进程验证 I/O guard，以及恢复快照的派生值/混用 scope 拒绝。首次失败来自测试把结构字段名 `original_column_schema_sha256` 误判为业务内容泄漏；改为精确业务值断言后通过。独立审查指出默认迁移摘要不能覆盖恢复全列，因此新增显式 `--include-derived` 和对应一项测试后，最终整套 12 项通过；未重跑产品测试。

这些都是离线 fixtures/helper 证据；没有运行产品已通过测试、MySQL、恢复演练、SSH 或容器。注释、docstring、受控开发说明均使用中文；机器字段/错误分类保留稳定英文。后续由 trellis-check 独立复核，授权执行前还须确认完整表/权限、工具 SHA、镜像 ID、实际只读限制、恢复目标及数据/对象完整性。
