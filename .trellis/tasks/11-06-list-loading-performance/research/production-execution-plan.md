# Research: 生产迁移、保真验收与回退执行载体

- Query: 将备份/隔离恢复、原列与全库保真、固定 as_of 完整新旧查询差分、旧镜像 2/1 重建落实为可审核步骤，识别缺失载体。
- Scope: mixed；本地源码、任务规划和官方 MySQL/Redis/Docker 文档。仅写本研究文件，不运行 SSH、数据库、容器、Git 或生产命令。
- Date: 2026-11-07
- 目标提交：`b8b2779a9ee678f778ddb95890cebc3a0faff55e`；镜像构建由主会话负责。本研究不证明当前目录逐文件等于该提交。

## Findings

### 结论与当前证据

可复用的维护工具是 `scripts/ops/migrate_document_job_list_keys.py` 及其共享实现 `migrate_document_job_list_query.py`。仓库不存在可直接复用的历史 `release/ops/migrate.py`、`snapshot.py`、`query_diff.py`；Spec 中提及这些路径不等于工具已落地。完整服务差分也不能直接采用合成 benchmark：它创建/写入/删除合成库，且异常 benchmark 关闭 publication 并省略真实依赖。

最小新增范围是任务专用运维载体：实例绑定迁移驱动、全库摘要、完整新旧响应差分。实施后已形成 [release_ops 本地候选](release_ops/README.md)：`migrate.py`、`snapshot.py`、`query_diff.py` 及共享连接保护。它们不改产品源码、不加入冻结生产镜像，可挂载在受限的一次性容器中；12 项直接离线用例通过。对象/配置/Redis 恢复及摘要仍按本研究步骤另行执行，不由这些脚本自动完成。下列生产/恢复命令是未来审批步骤，**并未执行**；离线通过不代表真实 MySQL、完整旧镜像或恢复环境演练通过。

主会话于本轮回传现场核对：API/Worker 仍为 `28cacd8a` / `sha256:77176d1903e9f266814b9ec3464551d1920c50b33683f3707889d570243dac7a`，旧 release 和九层 Compose 链存在，默认 docker driver、无 mirror/proxy、约 59.4 GiB 空闲。以上由主会话采集；不足以代替备份/恢复实证，也不证明可容纳两套恢复库和对象副本。

### 已读文件与代码模式

| 文件 | 可复用事实/限制 |
| --- | --- |
| 当前任务 `prd.md`、`design.md`、`implement.md` | 本地实施和线上验收分开；生产停写/迁移/切换仍须批准 |
| 当前任务 `production-switch-plan.md`、`research/release-preparation.md` | 完整 Compose 链、历史旧镜像、缺失运维工具、恢复授权边界 |
| `scripts/ops/migrate_document_job_list_query.py:29` | files 的三列派生值、jobs 的四列派生值及 2/3 存储版本 |
| 同文件 `:88`、`:145`、`:213` | 每次 apply 每表至多一批、files 优先、成功提交后推进游标；verify 从头全量 |
| 同文件 `:171`、`:184`、`:245` | `initialize=False`；可注入 connect_factory；显式 env、不读 .env；CLI 无 UUID 绑定 |
| `app/domains/document_jobs/service.py:1327` | 普通完整 list service；tenant/company/owner 权限；`utc_now()` 构造 as_of；动作与统计一并返回 |
| `app/domains/document_jobs/router.py:198` | 普通路由完整包装 owner，保留 `items/page/page_size/total/summary/filtered_summary/translation_qa_summary` |
| `app/domains/document_jobs/incidents.py:60` | 异常完整列表 owner，包含分类、筛选、全量统计、排序和页内动作 |
| `app/domains/document_jobs/service.py:255`、`app/main.py:226` | 真实 service 的读取依赖；不能随意用 None/空对象替代 |
| 当前任务 `research/benchmark-incident-session.py:101` | 只可参考固定 clock/完整结果比较结构；`:114` 的 publication=false 和合成依赖不能用于生产全合同验收 |
| `docker/prod/Dockerfile:20` | 运行镜像包含 app/scripts/resources/sitecustomize；旧镜像是否同样完整仍须独立读取核实 |
| `docker/prod/docker-compose.yml:68` | 仓库 Redis 配置为 AOF；必须另核现场有效配置、持久卷与队列 |
| `app/infrastructure/persistence/mysql/schema.py` | 仓库表以 InnoDB 为主，现场仍须枚举引擎、额外表、触发器/例程/事件 |

相关 Spec：`.trellis/spec/backend/database-guidelines.md`（显式 schema、独立短事务、全库事实）、`document-job-list-query-v2.md`（3/2 与 2/1、无混部、完整差分）、`runtime-configuration.md`（共享 var/config 是有效配置来源，不能只备份 .env）。已读取 `.trellis/workflow.md`。依据研究角色隔离规则，未加载 implement.jsonl/check.jsonl。

### 1. 审批输入清单与秘密边界

执行前由主会话填齐以下 manifest，拒绝空值和未核实值；保存 0700 目录内，普通报告只含非秘密摘要。

- `source_sha`、新旧 image ID/digest、完整旧源 manifest、新镜像构建 manifest、MySQL/Redis 镜像 ID 与版本。
- 生产 `server_uuid/database/host/port/version`、表引擎、sql_mode、字符集/collation、时区；恢复实例单独的 UUID 和连接地址。
- 按序九层 Compose 文件、Compose project/working directory、基础 `.env`、各层 env_file、容器有效 env 的受限快照、镜像原命令、全部 volume/bind 的 source/destination/read_only；包括账号 JSON、模板 docx/yaml、共享 var 内的运行时配置。
- 对象存储真实后端。local_file/local_object：实际根目录和其他挂载；S3：bucket/versioning/生命周期策略/可恢复版本点和独立隔离恢复方案。不能因有 var 卷就假定全部对象在其中。
- Redis 实际 DB 索引、两个队列与优先级子队列、Celery unacked 结构、持久目录/文件、AOF/RDB 配置、持久化健康和 TTL 口径。
- 全部写者、停止/排空命令与责任人、恢复点 `T0`、固定 aware UTC `as_of`、备份目录、保留期、恢复责任人、预计时长、容量预算。
- 真实 admin/operator 用户的 tenant/company/id/role 从受控合法身份资料读取，账号映射留在受限 manifest；对外仅 case 标签。离线构造 AuthenticatedUser 只用于验证既有权限逻辑，不是登录/JWT 通过证据。

命令中的 `BACKUP_DIR`、`MYSQL_CONTAINER`、`MYSQL_CLIENT_CNF`、`DATABASE_NAME`、`OLD_IMAGE_ID`、`NEW_IMAGE_ID`、`RESTORE_MYSQL_CONTAINER`、`RESTORE_CLIENT_CNF`、`REDIS_CONTAINER` 等均为待填现场变量，不包含猜测的值。MySQL client option file 必须真实存在于命令运行的容器内、权限0600，由既有秘密边界提供；`--defaults-extra-file` 紧跟客户端命令。禁止在 argv、聊天、stdout 或版本库写密码。Docker env 注入也会出现在 inspect，不能将完整 inspect/env 公开记录。

### 2. 停写、排空与统一恢复点

这一步及之后均属于未来窗口，不在当前镜像构建授权内。

1. 记录所有写入口：API/回调、普通与 translation-batch 两队列 Worker、内联/eager 执行、cleanup/import/review/state 回填、cron/systemd/人工 SQL、独立监听回调与第二迁移进程。确认没有未列入清单的其它容器/主机写者。
2. 分阶段阻止新写入：先关闭普通用户/脚本新写入口，保留既有 MinerU 回调和两个队列 Worker，等待已有任务收口；再关闭回调入口并优雅停 API，Worker 消化最后在途投递，最后才 warm 停 Worker。详细门槛、无维护系统的最小做法和退出条件见第9节；禁止同时 stop api worker 或默认 kill -9。
3. 已排队但未执行的合法消息可以保留，不要求清空队列；冻结消费者并保留消息次序/数量/摘要。reserved/unacked 未归还、外部 Provider 回调尚未妥善隔离或数据库仍有写事务时，停止进入 T0，记录处理决定；不自动 purge/requeue/retry。
4. 读取 `INFORMATION_SCHEMA.INNODB_TRX` 和适用连接清单（敏感 SQL 文本不输出），确认没有业务写事务或 DDL；核对 event_scheduler、复制/外部写入及对象生命周期写者。不能靠一个短时查询证明永久停写，需要保留阻止入口与进程状态证据。
5. T0 从所有业务写者停止并排空后开始，到原列保真/差分完成之前保持。SQL dump、对象和配置归档、Redis 队列恢复点必须处于这个稳定区间；`--single-transaction` 只提供 MySQL 快照，不自动原子覆盖文件/Redis。
6. 不启动 `app.main` 的运行时构造/应用 lifespan、API 或 Worker 来做停写验收：bootstrap 可能 schema/seed/recovery 写入。普通 import 的无副作用也应由既有构建证据界定。

### 3. MySQL 全库备份及恢复

这里的“全库”指**获批业务数据库中的全部表、视图、例程、触发器和事件**，不是只取 jobs/files，也不是擅自备份/替换共享实例全部系统库。若该服务涉及多个业务库，须明确逐库纳入同一冻结区间。现有实例账号/授权、MySQL 配置和恢复所需 DEFINER 依赖另作受限资产备份；不可把包含生产授权的 mysql 系统库直接导入联网演练实例。

现场确认 mysqldump 可用且版本与 8.4.9 兼容、授权足够、全部业务表为事务表、无并发 DDL后，命令形状为：

```sh
umask 077
mkdir -p "$BACKUP_DIR"
docker exec "$MYSQL_CONTAINER" mysqldump \
  --defaults-extra-file="$MYSQL_CLIENT_CNF" \
  --single-transaction --quick --routines --events --triggers \
  --hex-blob --no-tablespaces --set-gtid-purged=OFF \
  --databases "$DATABASE_NAME" > "$BACKUP_DIR/database.sql"
sha256sum "$BACKUP_DIR/database.sql" > "$BACKUP_DIR/database.sql.sha256"
```

必须分别保存 dump 真实退出码、受限 stderr、字节数/hash，失败或空输出不得继续。不能因后续 hash 命令成功覆盖 dump 失败。若有非事务表、复制链/PITR 要求或 DDL 未停，以上形状不充分，先补与现场匹配的备份方案；不临时使用全局锁或修改数据库配置。`--set-gtid-purged=OFF` 的这份逻辑备份用于当前恢复演练，不宣称可直接建立生产复制/PITR。

恢复安排：

1. 使用已固定 **同 MySQL 8.4.9 镜像**建立专属全新数据卷，不挂生产 datadir、不复制 `auto.cnf`；专属 `--internal` 网络、无 published port、不加入生产网络、`event_scheduler=OFF`、禁止自动启动复制，禁止 Worker/API。只开放专属差分/迁移容器到克隆 DB；无外网出口。实际启动参数和镜像 entrypoint 需由实施者基于现场镜像确认，不能套用未验证初始化秘密。
2. 将 `database.sql` 恢复到原同名 schema，避免文本替换库名破坏 routine/view/trigger 引用；隔离依赖的是实例/网络/UUID，不依赖新库名。
3. `docker exec -i "$RESTORE_MYSQL_CONTAINER" mysql --defaults-extra-file="$RESTORE_CLIENT_CNF" < "$BACKUP_DIR/database.sql"`，记录真实退出码；遇到 DEFINER/权限等错误不忽略、不删对象绕过，先补齐隔离账号元数据。
4. 恢复前后分别查询 `SELECT @@server_uuid, @@version, DATABASE();`。恢复实例 UUID 必须与生产不同。逻辑恢复不会把生产 UUID 写到新的 datadir；保存 `source_uuid` 与实际 `restore_uuid` 的映射及 dump hash。**后续对恢复库的保护参数必须是 restore_uuid**，不能沿用 production_uuid，也不能为通过校验关闭 UUID 绑定。
5. 恢复库全库原列/schema manifest 与 T0 源相同；原全部表 COUNT/内容必须逐表核对，视图/触发器/例程/事件定义也核对。文件备份存在、导入退出0或两表行数相同都不足以证明恢复。
6. 使用一个专属隔离恢复实例，按 **O（旧2/1）→C（新3/2）→R（旧2/1回退）** 顺序演练，所有阶段保留原schema名并绑定同一恢复UUID。先从T0备份恢复，以两侧 `--include-derived` 确认完整恢复；O使用完整旧镜像只读运行两次完整router矩阵并保存相等摘要，确认全部O进程退出、全列快照仍等于T0。随后C只由新owner迁移，空游标verify、原列/全库其它表/对象保真通过，再由完整新镜像只读运行两次同矩阵，比较冻结O摘要。最后R由旧owner重建2/1、verify、原列/其它表/对象保真，并用完整旧镜像双跑对照O；保留五个新增列。该顺序证明相同权威数据只改变获准派生事实，不需要两个并行MySQL实例或为了每阶段对照重复全量恢复。任何原列/对象变化、未知写结果或阶段失败都停止，不把受污染阶段继续称作T0；若确需重新恢复，只能使用原受限T0备份并重新核验，不能拼接不同恢复点。整个演练不启动API/Worker或新旧业务写者。

MySQL 官方要求 `--single-transaction` 期间无并发 DDL，例程/事件需显式包括；它不能使非事务表获得一致快照。[MySQL 8.4 mysqldump](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html)。`server_uuid` 来自 datadir 的 auto.cnf，独立新实例应形成独立身份。[MySQL server UUID](https://dev.mysql.com/doc/refman/8.4/en/replication-options.html)。

### 4. 对象、配置与 Redis 的配套恢复

共享 var 卷及所有实际读写对象卷逐一归档；只读 bind 仍是运行依赖，账号文件、模板 docx/yaml、配置 `.env` 与完整 Compose 链都必须纳入。不得只归档 release 源码目录。备份包含秘密，保留在批准的受限存储，不在研究报告打印 manifest 明文值。

对每个已核实的本地卷，可用已固定且确认带 GNU tar 的工具镜像，源只读挂载、备份目录可写挂载、`--network none`：

```sh
docker run --rm --network none --read-only --user 0:0 \
  --mount "type=volume,src=$SOURCE_VOLUME,dst=/source,readonly" \
  --mount "type=bind,src=$BACKUP_DIR,dst=/backup" \
  --entrypoint tar "$BACKUP_TOOL_IMAGE_ID" \
  --acls --xattrs --numeric-owner -cpf /backup/var.tar -C /source .
```

每个卷使用独立文件名；工具镜像/权限和 tar 支持现场核实，不能把该示例复用于多个卷覆盖同一 tar。bind 目录用只读 bind mount 同样处理，离散配置文件按实际路径完整清单归档，保留 UID/GID/mode/mtime/link target/ACL/xattr。恢复只写专属新卷，以 `tar --acls --xattrs --numeric-owner -xpf ... -C /restore` 解包；不跟随符号链接走出恢复根，不将备份 mount 成生产卷。对比每个条目类型、内容 SHA-256、size、mode、UID/GID、mtime 和 link/ACL/xattr；atime 受读取影响不作相等条件。业务可能读取的全部对象按 DB 引用核对存在性/内容，文件系统 metadata 与库行匹配，不能只比归档 SHA。[Docker volume 备份/恢复](https://docs.docker.com/engine/storage/volumes)。

Redis 方案优先保留生产实例与原 AOF 卷原状，增加独立恢复点：

- 先核对 `INFO persistence`、`CONFIG GET dir dbfilename appendonly appenddirname`（安全摘要），以及两个队列/优先级子队列/unacked 的具体键集合；不假设只有默认队列名。
- 获批备份窗口内执行认证后的 `redis-cli BGSAVE`，记录启动时间和结果，等待 `rdb_bgsave_in_progress=0`、`rdb_last_bgsave_status=ok`，并核对本轮完成时间/生成文件；不得仅凭旧 LASTSAVE 或已有 dump.rdb 判成功。鉴权沿原秘密通道，不使用 `-a <密码>` argv。
- 用 `docker cp "$REDIS_CONTAINER:$REDIS_RDB_PATH" "$BACKUP_DIR/redis.rdb"` 取此次完整 RDB，记录 hash/版本/路径/时间。`REDIS_RDB_PATH` 必须由实际 dir/dbfilename 得到。BGSAVE 失败/内存不足阻断备份，不改为阻塞 SAVE 或重启 Redis而不重新批准。
- 在同版本专属 Redis 容器加载 RDB，`--network none` 或专属 internal 网络、无端口/Worker；仅恢复新卷，显式 RDB-only（AOF关闭）演练，防止旧 AOF 覆盖该 RDB。原 AOF 卷不删除、不覆盖、不 purge。需要 AOF 物理归档时，额外审批一致性方式：包含完整 multipart manifest/base/incr，避免 rewrite 期间非原子 tar；本计划不声称普通热 tar 的 AOF 一定可恢复。
- 对队列 key/type/有序消息数量与内容摘要、unacked/hash/zset 关联做恢复前后比对；只输出聚合摘要。带 TTL 的非队列缓存自然到期必须按捕获时绝对到期时间解释，不能宣称全 Redis 字节完全相同，也不能为比对关闭业务 TTL。业务队列/未确认状态缺失不按缓存到期豁免。
- 普通代码回退保留当前 Redis；全库覆盖恢复时必须明确 DB/对象/Redis 的同一 T0 和重放/去重决定。不能恢复旧 DB 后继续消费恢复点之后的消息，亦不能无审批覆盖 Redis 消息。

Redis RDB 是时点快照；同时配置 AOF/RDB 时启动通常优先 AOF，恢复演练必须明确选择来源。[Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)。

### 5. 最小运维载体合同（已有本地候选，真实演练待批准）

当前候选与 CLI 以 [release_ops/README.md](release_ops/README.md) 为准；以下保持验收合同，并非已取得的执行结果。不增加生产抽象、框架或新数据库字段。载体从 `/ops` 只读挂载，完整旧/新代码从各自镜像 `/app` 导入，不向旧 sys.path 混入新源码。容器 rootfs、源码、对象/配置只读，仅受限 evidence 与 tmp 可写；不启动应用/队列。权限根据实际镜像实测，不能默认恢复所有 capabilities。

**A. 身份绑定迁移驱动**

输入：固定代码/镜像身份；显式五个 JOBS_MYSQL_*；期望 UUID/库名/版本；mode、batch_size、after_file_id/after_job_id。凭据不写公开输入 JSON。复用已有 migrate owner，并通过其 `mysql_connect_factory` 对**每一次新连接**先检查 UUID/库名，再设置经核实的 session 锁等待限制与只读保护；检查产生的事务须妥善结束再进入 owner 的事务，不改变原批次边界。仅外层一次 SELECT 后再运行未保护 CLI 存在目标漂移缺口。

输出：mode、真实代码/镜像、目标非秘密身份、开始结束时间、原完整迁移报告、真实工具/容器退出码、运行序号和游标；报告内可能有业务 ID，完整报告0600保存，公开只输出计数/错误分类。无 JSON、未知写结果、退出码不一致必须失败，不吞错误、不自动重试写操作。apply 仅提交后 last_successful 推进；DDL 已提交按实际列核对。

**B. 全库原列与 schema manifest**

输入：A 的身份绑定、固定 before schema manifest、scope=整个获批业务库。以显式 RR READ ONLY snapshot 遍历全表，表/列名只来自 INFORMATION_SCHEMA 并正确引用；不是接受任意用户拼 SQL。输出每表精确 COUNT、稳定内容 SHA-256、列定义/索引/外键/触发器/例程/视图/事件摘要、整个库总摘要和版本。

值编码须区分 NULL/空串、bytes/text、数值、日期精度及列类型，长度前缀避免拼接碰撞；TEXT/payload 取完整原值，不 JSON parse/dump 重排，不截断。不用 GROUP_CONCAT、CHECKSUM TABLE、信息模式估算行数或无序拼接替代。稳定主键排序；无主键表采用保留重复次数的规范行摘要排序，多重性不能丢。识别无法处理的类型明确失败，不能 string(value) 静默降级。

两表**唯一允许变化的派生列**：

| 表 | 原有允许重建列 | 允许新增列（仅 LONGTEXT NULL、无新索引） |
| --- | --- | --- |
| document_jobs | list_query_json（旧2→新3） | list_descriptor_key、list_receipt_key、list_table_snapshot_key |
| document_files | review_query_json（旧1→新2） | review_descriptor_key、review_receipt_key |

原 identity/payload/created_at/updated_at 及所有其它原列逐字节/规范类型值保持；其余全部表包括 job_events、publication 保护集合、审计等无豁免。before 保存的列列表必须与 after 的原列列表一致，after 另外验证新列白名单、表集合/schema变化；不能 after 动态排除任意不认识列。触发器若因 UPDATE 修改 updated_at/其它表，会由此门槛阻断。恢复基线要求全部列相等：两侧均使用 `snapshot --include-derived`，禁止将默认迁移摘要当成完整恢复证明。迁移前后使用默认原列模式，只排除上表允许变化列，新列正确性由 owner 全量 verify负责；两种 scope 混比失败。当前实现对视图、非 InnoDB 和 FLOAT/DOUBLE/REAL 列明确失败；若现场出现这些对象，须补充专门方案后再验收，不能将未支持对象跳过。

**C. 固定时钟完整查询差分**

输入：完整旧/新镜像 manifest；来自同一T0的恢复库/对象/配置及各阶段保真证据；同一个独立恢复实例的UUID绑定（必须异于生产）；同一aware UTC as_of；真实身份映射、显式查询矩阵。O/C/R按第3节顺序运行，禁止改用新owner生成旧期望。各阶段使用独立进程导入各自完整冻结镜像，前一阶段进程全部退出后再迁移布局，避免当前模块/依赖污染旧实现或新旧布局混跑。

调用链至少包含普通 `DocumentJobService.list_jobs` + `router.list_document_jobs` 的实际响应包装，以及异常 `DocumentJobIncidentService.list_incidents`（或对应完整路由）。不能只测 query_document_jobs_sql、页内 ID/review/quality，或复制路由包装字段形成另一个 owner。

构造 `initialize=False` 的实际读取仓储与原配置服务依赖，连接只指向克隆；对象/模板/账号配置从恢复副本只读读取。task queue/audit 等不可达写方法可提供明确 fail-on-use 对象，不能成功空返回。可达的 template/term/resource/file-upload/preview 读取 owner须真实接线；不能省成 None、关闭 publication、伪造 disabled action 以让两边相等。不直接调用 build_runtime 启动 schema/seed/recovery。若短期不能建立无写的完整依赖，则报告完整动作差分未实现，不降为 SQL 相等冒充。

Clock：普通 service 的 utc_now 构造 query.as_of；异常 service 和 incidents 各自绑定 utc_now。必须固定这些绑定及实际读动作调用图中的 clock 到同一个 as_of；当前候选按统一 `utc_now` 函数身份替换已加载模块中的引用，执行记录须列出各侧实际固定的绑定，同侧须独立采集两次并 compare 证明确定性。模型默认工厂等未覆盖的时钟若导致差异，不能删除响应字段使其通过。只传 query.as_of 不会冻结异常/动作的其它 clock。冻结只发生在隔离差分进程，不改生产时钟或产品源码。

矩阵最小覆盖每个真实 tenant/company 可见域的 admin 和 operator，以及不同 owner/operator 的隔离、空结果用户（有真实账号才称现场角色覆盖）。普通列表：默认、所有页/最后空页、无匹配/大小写/Unicode 搜索、实际状态/status_group/QA 筛选、日期边界、双向排序、include_archived；异常：默认/所有页/空页/搜索、实际 stage/failure/retryable/retry_count/stalled 筛选和排序。按实际存在的维度生成有限集合，不做所有笛卡尔积。保留页顺序并检查串页无重无漏，统计独立比较。真实数据没有 verified/临界到期/跨租户用户时明确 coverage absent，不合成生产账号/记录补齐；已有定向测试只作为独立补充证据。

比较响应完整 `model_dump(mode='json')`：有序 items、全部字段和动作字典（含 enabled、reason_code/message）、page/page_size、total、summary、filtered_summary、QA统计及异常统计。只规范 JSON 对象键顺序，不排序数组、不删不一致字段、不把 bool/number/NULL 混同。当前候选在各独立进程内将完整响应计算为摘要，只输出 case序号、角色、入口、计数和摘要；compare比较两份完整摘要报告，非零即阻断。它不输出业务值、文件名或全文，也不提供原响应的字段级差异定位。任一侧抛错即阻断正常验收；双方同错只作错误合同诊断，不能记为正常差分通过。矩阵覆盖由执行者按上一段审核并冻结：脚本的 admin/operator 下限检查不是自动覆盖证明，必须先完成每侧双跑，再做 O/C 对照。

该差分是停写克隆上的业务合同证据，不验证 JWT、浏览器、实时生产性能或恢复后运行时写入；后者按原上线 AC 单独验收。

### 6. 新版迁移与每批完成判断

先在 C 恢复实例完整演练：原列 manifest → dry-run 全扫描 → apply 全批次 → 空游标 verify → 原列/对象不变 → O/C 完整差分，再给生产窗口提供实际耗时和空间峰值。生产批准后复用同一固定载体/命令，仅明确换为生产目标身份；不根据演练 UUID 自动猜测生产身份。

维护入口的真实命令形状如下，实际执行需加上 A 的身份保护：

```sh
python /app/scripts/ops/migrate_document_job_list_keys.py --backend mysql --dry-run --batch-size 100
python /app/scripts/ops/migrate_document_job_list_keys.py --backend mysql --dry-run --batch-size 100 --after-file-id "$LAST_SCANNED_FILE_ID" --after-job-id "$LAST_SCANNED_JOB_ID"
python /app/scripts/ops/migrate_document_job_list_keys.py --backend mysql --apply --batch-size 100
python /app/scripts/ops/migrate_document_job_list_keys.py --backend mysql --apply --batch-size 100 --after-file-id "$LAST_SUCCESSFUL_FILE_ID" --after-job-id "$LAST_SUCCESSFUL_JOB_ID"
python /app/scripts/ops/migrate_document_job_list_keys.py --backend mysql --verify --batch-size 100
```

- dry-run 每表一批，各自更新 last_scanned，直到两表 `has_more=false`、`status=complete`、无 payload errors；预期 missing新列/mismatch并不阻断 dry-run 本身，须记录待迁移事实。
- apply 起步双空游标。files有后续时 jobs pending；仅使用报告里成功提交的游标更新两个状态。保留已完成 files游标直至jobs完成，不把 pending 的默认值覆盖已提交状态。中断/失败不得使用 last_scanned 跳过未提交行。
- 两表 complete 只是批次遍历结束；最后必须不带任何游标 verify，要求工具/容器退出0、all_ready=true、两表 complete、无 schema_missing/mismatches/errors。单次apply退出0、首次一批有committed_rows、甚至最后apply退出0都不能替代verify。
- verify 之后原列、全部其他表、对象/配置manifest与T0相等，再进行固定as_of差分；任一门槛失败保持停写。

### 7. 旧完整镜像的 2/1 重建与回退

镜像保留不仅是标签：记录旧 image ID/digest、完整 app/scripts/resources 与解释器依赖身份、APP_VERSION、原 Compose 链；必要时 `docker image save "$OLD_IMAGE_ID" -o "$BACKUP_DIR/old-image.tar"` 保留可加载归档，核实磁盘预算并记录 SHA。不能从新镜像复制一个旧 migrate.py 冒充完整旧环境。

旧镜像无网/无业务挂载探针检查旧入口存在、`--help` 参数、TABLES 声明与 builder 实际投影版本；旧代码完整 imports 都在旧镜像。旧schema 维护不得执行；迁移仍 initialize=False。若旧镜像 lacks脚本或版本不是2/1，先按冻结完整旧源码与其对应锁/依赖构造专用旧运维镜像并审核，不能在回退窗口临时修脚本。

在 **已经迁移到3/2的 C 隔离库**完成一次回退演练：

1. 保持全部写者停。固定回退前权威原列/对象 manifest，使用旧完整镜像里的 `/app/scripts/ops/migrate_document_job_list_query.py`。
2. 经同样 UUID/库名绑定的旧 driver dry-run，从双空游标扫描；逐批 apply files→jobs 重建旧大 JSON。旧工具参数/报告须先从冻结旧实现确认；若与新版不同，适配驱动读取它真实合同，不能仅假设同名就一致。
3. 旧 CLI 若经确认支持现有双游标/verify，运行形状为：

```sh
python /app/scripts/ops/migrate_document_job_list_query.py --backend mysql --dry-run --batch-size 100
python /app/scripts/ops/migrate_document_job_list_query.py --backend mysql --apply --batch-size 100
python /app/scripts/ops/migrate_document_job_list_query.py --backend mysql --apply --batch-size 100 --after-file-id "$LAST_SUCCESSFUL_FILE_ID" --after-job-id "$LAST_SUCCESSFUL_JOB_ID"
python /app/scripts/ops/migrate_document_job_list_query.py --backend mysql --verify --batch-size 100
```

4. 要求所有行job/file投影为2/1且旧owner全量verify通过，原payload/其它原列/全库其它表/对象不变；五个新增列保留、不DROP。使用旧完整查询对比回退前保存的 T0旧基线（同as_of）；不要运行新列表期待其接受旧布局。
5. 演练通过才有“旧版可回退”实证。未来生产失败时按批准回退步骤停写、旧重建/verify/保真通过，再用原完整Compose链统一启动旧API/Worker；不能先启动旧API让bootstrap试探迁移情况。
6. 若新版已经恢复写入，代码回退仍从**当前权威payload**重建2/1，不自动恢复T0覆盖新业务。旧版本无法解释新payload或发现全库损坏时，停下提出数据恢复方案；全库覆盖恢复是独立审批，需要明确丢弃哪些T0之后的更改，以及Redis/对象同点恢复。
7. 任何旧writer恢复后，五列整体视为陈旧；下一次升级双表双空游标全量重建，不仅补NULL，也不沿用旧升级游标。

### 8. 生产切换前的可批准交付包

应包含：冻结镜像及Compose差异、完整写者清单和排空判据、现场UUID/schema、DB/对象/配置/Redis备份命令与权限、容量/窗口实测、隔离恢复与回退演练结果、全库原列manifest比较、固定as_of查询矩阵/差分结果、生产迁移逐批driver用法/停止条件、旧版恢复命令及责任人。未取得的项目以未完成标记，不把方案存在等同执行通过。

当前用户只批准固定提交构建镜像与完善方案；停写、BGSAVE等在线备份动作、迁移、隔离生产数据恢复演练、切换和覆盖恢复均不能从本研究自动获权。主会话可在已授权的本地准备范围实现/审核运维载体，并将拟定生产动作作为具体审批包。


### 9. 回调安全的排空顺序补查（2026-11-07）

本节细化并优先解释第2节停写顺序。当前主会话观察到两队列空、unacked无、API/Worker正常，仅是一张瞬时快照；不能据此直接停止API。

**实际生命周期证据**

- `execution.py:331–406`：MinerU首次上传后保存batch/data ID并查询；未就绪时job保留 `running/parsing`，执行调用返回。`document_tasks.py:19–30` 只有无callback URL的轮询模式才通过Celery countdown retry续投；配置callback时，Worker任务可已经结束，而外部MinerU仍运行。因此active=0、队列空与“仍依赖回调”可以同时成立。
- `mineru_callbacks_router.py:24–61`（总路由前缀见 `app/api/v1/router.py:34,43`）：实际回调为 `/api/v1/mineru-callbacks/result`；先验证身份/checksum并持久化消息，再向普通job队列投递。投递异常可能仍HTTP 200，必须另查DB pending/running消息，不能拿回调200当Worker已处理。
- `execution.py:457–480`：终态或不接收回调阶段的迟到回调也会写专用消息和事件，再标ignored。因此即使业务job全终态，T0仍要关闭回调并等在途HTTP结束，不能将回调永久放行。
- `mysql/document_jobs.py:487`：replayable消息是pending/running。旧failed消息不自动列为待回放，但与当前非终态job有关时必须查明；禁止为排空直接更新状态。
- `execution.py:1247–1249,1363–1453`：translation批次可重新投递/获得lease，provider.translate在批次执行内同步调用；必须考虑job当前generation、批次状态/lease和Worker实际调用，不能只看普通队列。
- `workflow.py:95–96`：业务非终态为pending/queued/running，终态为succeeded/failed/canceled。`document_tasks.py:44` 有Worker启动恢复；重启不是只读操作。

**不引入新维护系统的最小方案**

使用现有接入代理的一次性、可恢复站点规则关闭普通业务请求，保留唯一MinerU回调路径及其原代理/验签链；API和两个队列Worker此时继续工作。可以在窗口内暂时返回503维护响应，不必新增应用maintenance开关或持久化状态。仓库部署文档记录实际接入在hostdzire nginx；需主会话读取当前真实站点配置后才给出最小diff、原文件备份与 `nginx -t`/reload命令，不能直接生成覆盖现有TLS/location的通用配置。公网上游是stream透传，不能假设在该层按HTTP路径过滤。若不能在已有接入点精确保留回调并阻断其它写入，窗口尚不可执行，应推迟而非先停API。

该临时规则也是生产配置变更，应列入停写窗口审批，并明确恢复原配置；不能按镜像构建权限执行。规则必须同时覆盖新建、上传、重试、clone、新代、重核、归档、配置变更等写路径，不能只禁创建任务。最小易审计策略是普通业务路径全部维护，只保留确切回调路径，而不是枚举少数POST路径。所有直连127.0.0.1、其它内网入口、脚本/定时器和人工SQL写者另行停用并确认；nginx规则不控制这些写者。用户正常验收登录应在T0前或切换完成后安排。

**具体执行顺序与判据**

1. 完成写者盘点和原代理配置备份；准备读查询、日志和恢复命令，记录本轮deadline。先停外部定时/人工操作等新业务生产者，启用“普通业务维护、回调保留”规则。验证规则已生效且原回调路径代理未改坏；用配置检查/已有真实请求证据核对，不伪造Provider回调、不提交测试业务。
2. 保持旧API、旧Worker两队列和数据库/Redis/对象存储正常，允许已开始的正常工作继续，低频核对三组证据：数据库job状态/stage和MinerU待结果事实；callback pending/running及相关failed；当前generation的translation pending/queued/running与lease；同时核对Celery active/reserved/scheduled、两个队列及优先级子队列、unacked/消费者。必须收到所有预期Worker节点回复；空回复/超时不算空闲。
3. 收敛门槛：不存在未解释的业务非终态job，尤其running/parsing且持有MinerU batch/data ID的待结果job；没有callback pending/running；没有未解释的当前generation待执行/执行中translation批次或在用lease；Worker active/reserved/scheduled、队列和unacked均为空。历史旧generation批次若仍标pending/running需明确证据证明不可执行、无存活调用，留存例外清单，不为排空清理数据。当前方案优先选择**业务全终态的短窗口**，不设计携带活动外部任务跨迁移的额外恢复机制。
4. 在规则已阻止新工作且上一门槛成立后，把回调也切到维护状态（拒绝未接纳请求，不能伪造200成功），再优雅停止旧API。API退出前Worker仍运行，以处理API在途请求最后持久化/投递的消息。等待API完全退出、没有在途请求/事务，重新检查job/callback/translation/broker门槛；迟到请求可以改变终态消息/事件，T0必须在这些变化结束后。
5. 最后才对旧Worker做warm shutdown并观察实际退出。核对StopSignal是TERM、未设 `REMAP_SIGTERM=SIGQUIT`、PID1信号可达且未由shell吞掉；仓库入口为python调用 `worker_main`，仍需现场容器验证。不要默认 `docker compose stop api worker` 的有限超时足够。
6. 可审阅的停止形状为 `docker stop --timeout -1 "$WORKER_CONTAINER"`（API亦可同样显式等待优雅退出，须确认其停止信号）。在可继续采集状态的独立执行会话运行，按批准deadline观察；`-1`阻止Docker自动超时SIGKILL，不代表允许无限等待或自动升级为强杀。Docker默认有限超时会强杀，Celery TERM通常warm但REMAP可改成cold。[Docker stop](https://docs.docker.com/reference/cli/docker/container/stop)、[Celery 5.6 worker shutdown](https://docs.celeryq.dev/en/latest/userguide/workers.html)。仓库锁为Celery5.6.3，生产依赖由旧镜像核实。
7. Worker真正退出后再检查无新/剩余业务事务、无其它写进程和消息，保存最终一致性快照与停止时间。此时才宣布T0、开始DB/对象/Redis备份。T0前已有队列空证据不能复用于此最终门槛。若选择保留排队消息的另一种窗口，必须另给逐消息来源/恢复计划，不自动套用本节“全排空”结果。

**只读计数与失败退回**

`document_jobs`没有独立status/stage列（schema.py:376），不能猜测 `WHERE status='running'`。身份绑定只读连接应先检验payload合法JSON，再以旧镜像模型解码读取status/stage/retry_count/mineru_batch_id/mineru_data_id及原始时间；只输出聚合及受限ID映射，不输出seed、回调payload、下载URL。无效/缺失状态失败关闭，不能JSON_EXTRACT为NULL后将其遗漏。其它两表可直接按物理status聚合：

```sql
SELECT status, COUNT(*) AS rows_count
FROM document_job_callback_messages GROUP BY status;
SELECT status, COUNT(*) AS rows_count
FROM document_job_translation_batches GROUP BY status;
```

这两个COUNT仍只是初筛，translation需与当前job generation和lease核对，不等于完整排空证明。pending/running回调即使队列空也阻断；不能自动启动replay使门槛变绿。外部首次提交结果未知、batch ID未落库、job还在非终态、Provider未返回/超时、callback唤醒失败、读取或节点状态不明均阻断窗口；不因Celery空闲推断Provider任务不存在，也不额外发送Provider查询/取消/重提来完成本次只读研究。

如果deadline前未收敛，或关闭回调/停API后重新出现非终态与未解释消息：不运行DDL/apply、不产生新的“完成备份”结论，撤销此次切换准备，按事先批准的恢复步骤恢复旧API/回调入口及旧Worker正常服务，再恢复普通入口。不要为赶窗口取消业务、改状态、清队列、删除lease、重复投递或强杀。若已有进程处于shutdown中，先确认其真实状态再决定恢复，不能仅中止CLI就声称服务已恢复。恢复Worker/API可能触发原bootstrap/recovery，属于回退服务动作而非只读检查，须在窗口方案预先授权。完成停写后的备份/迁移若已经执行，按相应阶段回退规则处理，不能直接按本段未迁移撤销。

## External references

- MySQL 8.4 `mysqldump`：[官方参数、事务与对象范围](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html)。检索日期2026-11-07，实际客户端/服务端需现场验证；未执行命令。
- MySQL 8.4：[server_uuid/auto.cnf](https://dev.mysql.com/doc/refman/8.4/en/replication-options.html)。逻辑恢复后的独立实例必须重新绑定其实际UUID。
- Docker：[Volumes](https://docs.docker.com/engine/storage/volumes)。归档源卷和恢复新卷分开，不对运行中MySQL数据目录做普通tar。
- Redis：[Persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)。现场版本记录为7.4.9，RDB/AOF恢复来源必须明确。

## Caveats / Not Found

- 研究及本次独立复核未执行 SSH/数据库/容器/生产操作；实施 agent 已创建任务内运维载体并完成12项离线测试及5个Python文件AST检查。本研究已同步为本地候选状态，产品代码/冻结镜像未改；真实恢复/回退/差分仍待审批与执行。
- 新旧镜像身份、现场库/卷/Redis 等主会话已取得的准备证据见 [production-build.md](production-build.md) 与对应 manifest；恢复实例、凭据载体、隔离资源和窗口值仍须在执行前核实，上文变量不是现成可运行配置。
- 完整动作差分已接实际读取依赖；本地构造测试不代表真实路由/对象读取通过。本地合成 benchmark 不能承担恢复环境验收。若恢复环境缺少可达依赖或真实角色，必须记录缺口，不能通过关闭能力满足比较。
- 主会话构建记录已确认旧镜像 TABLES 为2/1及迁移脚本与旧 archive 一致；本次复核另读冻结旧提交，确认原函数接受双游标、verify和connect_factory。旧完整镜像中的实际迁移/回退仍未演练，当前目录的同名新脚本不能作为旧版回退执行代码。
- MySQL全库manifest应保存所有未知额外表；不把仓库schema列表视为线上完整表集合。RedisTTL、S3生命周期、外部callback等跨存储变化须在T0方案中处理，不能只停两个容器。
