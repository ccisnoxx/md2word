# B08 迁移设计

## 1. 事实、风险与设计边界

本设计基于 PRD 中的提交，现状代码锚点如下。生产行数及配置仅来自用户提供的快照，未访问生产。尚无证据确认正在发生立即数据损坏；已确认的风险是启动会写 schema/数据，且不能依靠外层 rollback 撤销全部 DDL。

| 现状 | 实际代码锚点 | 设计影响 |
|---|---|---|
| 默认启动初始化、连接成功提交/异常回滚 | `app/infrastructure/persistence/mysql/backend.py:43`、`app/infrastructure/persistence/mysql/backend.py:65` | 迁移连接不得经默认初始化路径创建；rollback 不是 DDL 恢复方案。 |
| 建表→ALTER→补列→UPDATE→删索引→补索引 | `app/infrastructure/persistence/mysql/schema.py:493`、`app/infrastructure/persistence/mysql/schema.py:500`、`app/infrastructure/persistence/mysql/schema.py:535`、`app/infrastructure/persistence/mysql/schema.py:550` | 基线导入不得重放 maintenance，不可偷偷补列或回填。 |
| INFORMATION_SCHEMA 只检查列/索引是否存在 | `app/infrastructure/persistence/mysql/schema.py:568`、`app/infrastructure/persistence/mysql/schema.py:599` | 存在不等于定义相同，基线必须比较类型、默认值和完整索引定义。 |
| 工厂创建共享 backend | `app/infrastructure/persistence/factory.py:205` | 统一检查放在 MySQL 装配边界，先检查再创建业务 runtime。 |
| API/Worker 都进入 runtime | `app/main.py:146`、`app/workers/document_tasks.py:23`、`app/workers/document_tasks.py:48` | 同镜像不等于单执行者；Worker 就绪和每次构造 runtime 都不能迁移。 |
| 正式事件读写仍用 job_events | `app/infrastructure/persistence/mysql/document_jobs.py:390`、`app/infrastructure/persistence/mysql/document_jobs.py:400` | 不按 legacy 文件名归属删除事件表。 |
| 正式任务 schema 与查询投影 | `app/infrastructure/persistence/mysql/schema.py:402`、`app/infrastructure/persistence/mysql/schema.py:514` | 不改字段/payload/索引，也不把 schema 版本当作投影已回填的证明。 |
| SQLite 有独立初始化 | `app/infrastructure/persistence/sqlite/backend.py:22`、`app/infrastructure/persistence/sqlite/schema.py:287` | 首期 MySQL 方案不默认为 SQLite 适用。 |
| MySQL 声明为 8.4；API/Worker 同 image 引用 | `docker/prod/docker-compose.yml:79`、`docker/prod/docker-compose.yml:9`、`docker/prod/docker-compose.yml:50` | 配置声明不证明线上补丁版本或实际镜像一致；后续授权核查。 |

遵循 `.trellis/spec/backend/database-guidelines.md` 的显式 adapter、失败不降级、payload 权威、既有 CAS/receipt 与查询投影合同。迁移治理不会接管业务事务、翻译状态机或历史回填。

## 2. 工具比较与推荐（D-1 待批准）

检索日期：2026-11-06。仓库依赖为 `requirements.txt:11` 的 `PyMySQL>=1.1,<2`；指定本地 venv 为 Python 3.11.15 / PyMySQL 1.2.0，仅是本机证据，不是部署锁定版本。

| 维度 | A：显式 SQL 版本化 | B：Alembic + 手写 revision |
|---|---|---|
| 项目适配 | 继续现有 PyMySQL 与显式 SQL，不新增 ORM/迁移依赖 | 可手写迁移而不建 ORM；引入 Alembic、SQLAlchemy 及迁移环境 |
| 版本来源 | 单一线性 manifest，固定 version、parent、步骤及 SHA-256 | revision/down_revision 依赖链与版本表 |
| 基线 | 比对签字轮廓后登记，独立空库创建路径 | 比对后 stamp；stamp 自身不证明结构正确 |
| 本项目额外工作 | 自行实现窄范围账本、锁、兼容检查和步骤恢复 | 仍需补项目要求的校验和、步骤状态、单执行者、兼容检查和恢复证据 |
| MySQL 中断 | 明确逐步核对，不能统一 rollback | 工具的 MySQL 实现同样声明非事务 DDL，不提供自动多步回滚保证 |
| 维护取舍 | 实现面积小，但必须维护本文状态合同与真实引擎测试 | 标准 revision 工具链较成熟；本次仅线性基线加三表收缩，新增依赖及双重状态整合成本较高 |
| 后续适用 | 当前 MySQL 单写节点、少量显式迁移 | 多数据库/复杂 revision 需求实际出现时重新评估 |

**推荐 A，但不代用户定案。** 不构建通用框架、插件或任意 SQL 解释器。应用发布包携带不可变、线性版本清单；SQL 参数值继续绑定，DDL 标识符只能来自受审清单。若批准 B，Alembic revision 是唯一版本图 owner；本文执行账本按 revision 引用，不允许另建独立 version head；revision 与账本不一致时拒绝启动，恢复仍按物理后置条件对账。

官方依据与核实边界：

- [Alembic 1.20.1 发布说明](https://alembic.sqlalchemy.org/en/latest/changelog.html#change-1.20.1) 标记 2026-10-21 发布；包含 MySQL 等后端空注释 autogenerate 修复，且页面列有尚无发布日期的 1.20.2。这里只记录已发布 1.20.1 为比较版本，不选择开发版，也不把自动生成差异当作可靠基线证据。
- [Alembic 教程](https://alembic.sqlalchemy.org/en/latest/tutorial.html) 描述依赖 SQLAlchemy 的迁移环境；[stamp 命令](https://alembic.sqlalchemy.org/en/latest/api/commands.html#alembic.command.stamp) 只标记 revision，不运行迁移；[MySQLImpl](https://alembic.sqlalchemy.org/en/latest/api/ddl.html#alembic.ddl.mysql.MySQLImpl) 声明 `transactional_ddl=False`。
- [MySQL 8.4 隐式提交](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html) 与 [atomic DDL](https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html) 说明 DDL 与业务事务不可混为一体；单语句原子性不覆盖本设计整个迁移序列。
- [MySQL 8.4 GET_LOCK](https://dev.mysql.com/doc/refman/8.4/en/locking-functions.html) 支持会话级命名锁，事务结束不释放，连接结束释放，且只覆盖一个 mysqld。
- 未安装或试运行 Alembic，未验证其具体依赖组合、许可证/安全公告与全部开放问题；批准 B 前必须对固定版本补查这些项目、相关 MySQL/SQLite 问题和已接受修复，不在本轮定案。A 的生产 PyMySQL/服务端版本与拓扑也待授权核实。

## 3. 版本与记录表（拟议逻辑结构，本文不含可执行 DDL）

只新增一张 `schema_migrations`，InnoDB，字段如下；表自身格式为账本格式 1，随应用明确支持，不另加泛化 schema registry。

| 字段 | 拟议类型/约束 | 含义 |
|---|---|---|
| version | VARCHAR(64)，主键，区分大小写 | 如 `B08_001`、`B08_002`，从受审清单选择，排序由 parent 链决定 |
| parent_version | VARCHAR(64)，可空 | 首基线为空；其余必须是已完成前驱，不建立业务表外键 |
| checksum | CHAR(64)，非空 | SHA-256：确定性 manifest + 有序 SQL/探针资源原始字节；包含版本、前驱、步骤、前/后置规则，排除注释式运行日志；发布后不可原地改写 |
| ledger_format | SMALLINT，非空 | 固定为 1；不识别则拒绝 |
| kind | VARCHAR(16)，非空 | `baseline` / `migration` |
| origin | VARCHAR(16)，非空 | `adopt` / `fresh`；不是运行时自动猜测 |
| baseline_profile | VARCHAR(32)，可空 | 首基线的 `legacy_present` / `legacy_absent`，后续行为空 |
| status | VARCHAR(16)，非空 | `running` / `applied` / `failed` / `interrupted` |
| completed_steps | INT UNSIGNED，非空 | 已证实完成的连续步骤数，初值 0 |
| current_step | INT UNSIGNED，可空 | 当前已持久登记意图的步骤；完成时为空 |
| attempt | INT UNSIGNED，非空 | 初值 1，显式恢复递增，不靠重复启动自动重试 |
| runner_id | VARCHAR(128)，非空 | 本次运行标识，不存凭据 |
| started_at / updated_at / finished_at | DATETIME(6)，UTC；finished_at 可空 | 执行时间；时间长短不能单独判死 |
| observed_schema_sha256 | CHAR(64)，可空 | 登记/完成时结构快照摘要，失败时不伪造完成摘要 |
| evidence_ref | VARCHAR(512)，非空 | 受控证据包标识/相对路径，不含带密钥 URL |
| error_code | VARCHAR(64)，可空 | 稳定脱敏错误码；不写原始异常、连接串或业务 payload |

状态由迁移入口唯一写入。API/Worker 只读取。已完成行的版本/校验和/完成事实不可修改；恢复同一失败行只更新 attempt、执行状态与新证据引用，前次证据包必须保留。最新版本从**已知线性前驱链全部 applied**推导，不维护第二个可漂移 head。未知版本、断链、异常字段组合、任何未收口行及 checksum 不一致均阻止启动。

`B08_001` 是当前结构的登记/空库基线；`B08_002` 是三表收缩。清单将基线结构快照冻结，不能运行时从不断变化的 bootstrap 常量重新推导旧版本。每个发布包携带兼容版本集合及相应 checksum；修改已发布迁移必须用新版本或停止调查，禁止接受新 checksum 覆盖旧记录。

## 4. 基线识别与无业务数据变更登记

1. **只读 inventory**：用不触发 runtime/backend 初始化的直接连接读取库身份、服务端版本、引擎、表、列、类型/长度/精度、nullable/default、字符集/collation、生成列、完整索引（顺序/唯一性/前缀）、约束及触发器/视图/例程依赖。按对象名和列/索引序号规范排序；忽略行数估计、AUTO_INCREMENT 当前计数、统计量和格式空白等运行差异，保留影响语义的属性。原始 SHOW CREATE 与规范化快照一并归档。不读取秘密或输出业务 payload。
2. **受审匹配**：冻结清单来自本提交 schema 与 B05 合入后的受审差异；用获批只读生产 inventory 核对后，才能批准为已知轮廓。不能把“刚读到的库”自动当作正确基线。非治理对象显式列入允许的外部对象清单；未知额外对象也停止，避免静默忽略依赖。
3. 仅支持两个候选 `B08_001` 轮廓：`legacy_present` 为三旧表全部存在且定义一致；`legacy_absent` 为三旧表全部不存在，其余业务对象完全一致（B05 后新库情形）。三表缺一/缺二、缺列、索引异形等无账本库是**未知部分结构**，禁止 stamp 或顺便修复。三表是否为空由收缩前单独核验，基线不删除有数据的旧表。
4. 登记前获得生产授权和停写窗口，停止所有旧启动维护进程及外部 DDL 写者，获取单执行者锁，再次比对 inventory。仅创建账本表并写入 `B08_001 applied` 与 profile/快照/校验和；不执行旧 initialize_schema，不 ALTER 业务表、不 UPDATE 业务数据。此处“无数据改动”专指业务数据不变，账本创建和登记本身是需批准的生产写入。
5. 账本初始化独立固定契约：锁先于账本；表不存在才创建，已存在则核对完整定义。创建后中断留下空账本可在同样审批和完整比对后重试登记；形状不符、未知记录或非空异常账本立即停止。只创建账本不是迁移成功。
6. 新空库必须走显式 `fresh` 路径，空库定义为无业务对象/无未知对象（允许本工具留下的合法空账本）；从受审快照创建正式业务结构，**不创建 B05 已删除的三旧表**，逐个建表步骤记录完成。完成后登记 `B08_001 legacy_absent`，再执行 `B08_002` 的三个明确无操作步骤；两者均完成才达到新库目标版本。不能对任意缺表库使用 fresh。
7. fresh 中断必须有本工具 running 记录，只有已记录步骤的精确后置状态可续跑；无账本的半建库仍拒绝。恢复与正常路径共享下节规则。adopt 的完成步骤数为 0；fresh 的步骤数取冻结基线清单中的对象创建步骤数，两种 origin 的成功条件不同，显式验证。

## 5. 单一执行者与 API/Worker 兼容检查

迁移入口与 API/Worker 分离，不 import `app.main` 或构造会初始化的 backend。部署操作明确顺序为停止写者 → 独立入口执行 → 检查成功 → 启动兼容 API/Worker，不能依赖 Compose 的 `service_started` 代表迁移已成功。

- 推荐只支持单写节点 MySQL。迁移入口使用同一条专用、非连接池连接获取确定性库级 `GET_LOCK`，锁名为 `md2word-schema:` 加数据库身份摘要（总长不超过 64），申请采用非阻塞结果；未获得锁即明确退出，不自动重试。锁覆盖账本引导、版本检查、每步 DDL、后置验证和完成登记。
- **锁与 DDL 使用同一连接**，不在持锁连接以外执行 DDL，不允许自动重连。会话丢失即停止；网络结果不明时不能宣称回滚，新执行者须拿到同一锁后核对物理结果。旧服务端会话仍活着时新执行者拿不到锁，不能仅凭超时抢占。
- 运行时账号保留业务 DML 和账本 SELECT，无 schema DDL、无账本 INSERT/UPDATE/DELETE；迁移凭据仅独立入口可用。权限变更必须单独生产授权。命名锁只能约束遵守协议的执行者，所以外部运维 DDL 也必须停用；不声称抵御 DBA 绕过。
- 初次推荐兼容应用版本 `A1`：B05 已合入、移除自动维护、具备兼容检查，可读写完整 `B08_001` 两轮廓及 `B08_002`；收缩后仅回退到已经验证该集合的 A1 或后续版本。当前旧应用 `A0` 会重建旧表，不能在治理窗口或收缩后启动。
- API 的 runtime 在创建业务服务/恢复任务之前检查；Worker 启动钩子要在消费前完成检查，所有重建 runtime 的任务入口也复用检查。失败必须使 Worker 不开始消费，不能只依赖 Celery signal 抛错是否终止进程这一未经验证的假设。
- 检查 ledger_format、完整版本链/checksum、全 applied、版本属于应用明确支持集合，以及该版本关键结构轮廓。不存在账本、too-old/too-new、running/failed/interrupted、关键表缺失或漂移都非零退出/不就绪，不建表、不降级 file/sqlite、不自动 stamp。日志只含版本、步骤、稳定错误码和脱敏运行标识。
- 启动检查不能阻止已经运行的旧写者；本方案用停写和运维准入保证窗口内零消费者，不增加每请求锁或长期兼容双写机制。`APP_ENV` 不参与是否允许迁移的判断。

## 6. 执行状态、中断与恢复

每步只有受审的前置状态 P 和后置状态 Q，先提交 running/当前步骤意图，再执行一条 DDL，核对 Q 后以短事务提交 completed_steps 增量。只有全部 Q 和最终结构验证通过，才将该版本置 applied 并清空 current_step。DDL 与账本事务不能组成一个原子事务。

| 观察 | 必须动作 |
|---|---|
| applied 且版本/checksum/完整结构相符 | 重跑只读返回已完成，不重放 DDL、不增 attempt。 |
| running 且锁仍由原会话持有 | 不接管；等待由操作人判断，保持应用停机。 |
| 获锁后存在旧 running | 记录 interrupted、保留旧证据；普通 apply 拒绝，显式 resume 才继续。 |
| 中断步物理状态为 P | 审批、停写、备份仍有效且检查再次通过后，递增 attempt，重执行当前步。 |
| 中断步物理状态为 Q | 证明该步已完成，补记 completed_steps；不再发同一步 DDL。 |
| 既不是 P 也不是 Q，checksum 改变，已完成步骤发生漂移 | 停止并报告，不能用 IF EXISTS/IF NOT EXISTS 吞掉差异或人工改版本号放行。 |
| SQL 报错且连接仍可用 | 记录 failed 和稳定码；rollback 仅处理未提交的账本 DML。保持停写，后续获锁再核对实际结构。 |
| 连接失效，失败状态也无法写入 | 保留 running，退出失败；下一次获锁识别中断，不把异常转成成功。 |

恢复前核对所有已完成步骤的 Q、未开始步骤的 P、当前步的 P/Q，不能只看 completed_steps。收缩恢复中已不存在的旧表只有在本迁移已提交相应意图、或基线 profile 明确为 legacy_absent 时才能认定 Q；无账本的部分缺失不视作成功。每次恢复保存独立证据包并引用前次包。对 `B08_002` 收缩迁移，首次写入 running 意图前必须持久保存并校验原始停写点的保护数据/结构摘要及备份标识，证据包链始终回到该原始快照；resume 开始和最终收口均与它比较，不得用中断后的现状重新建立成功基线。原始证据丢失、校验失败或任何保护摘要变化时停止恢复，转人工调查/另行批准的备份恢复。该守恒条款不用于比较 fresh 的初始空库与已创建表的结构；fresh 恢复按冻结创建清单的 P/Q 核对，同时确认业务写入仍为零，任何业务数据出现都停止，不删除它来恢复空库假设。

优先在同一获批目标下前滚。无法证明 P/Q、正式数据摘要变化或备份不可靠时停止；不自动执行 down。恢复备份是新的生产动作，需要授权并在隔离库先验证，恢复后的账本、业务结构和数据必须属于同一恢复点；不能只把版本号改回去。

## 7. 首个收缩迁移与正式数据保护

`B08_002` 固定三个步骤：处理 `stage_messages` → `job_files` → `jobs`。每步只针对该表；不做通配、级联、TRUNCATE、重建其他表、禁用外键检查或数据搬运。该顺序不代替依赖检查，发现外部依赖即停止。

删除前必须全部满足并保存证据：

1. B05 第 3/4 步已经合入选定发布提交；候选代码、镜像、部署入口和实际进程均无三表消费者/CREATE，旧 Worker、脚本、回调、定时器、队列重放路径已处置。源码无引用与三表为空不能单独证明无消费者；未知部署消费者/spool 保留阻塞。
2. 明确目标实例/库、服务端版本/引擎、B08_001 状态、校验和及锁；所有业务写者停止并排空在途 DB 事务，防止 COUNT 与 DROP 之间写入。元数据锁长期等待时退出并报告，不自动 kill 业务会话。
3. 每张存在的目标表用实际 COUNT 再次确认 0，不能用 INFORMATION_SCHEMA.TABLE_ROWS 估计，也不能使用历史 0 行快照。检查外键、触发器、视图、例程/事件及跨 schema 依赖；检查权限不足不能当作无依赖。
4. 完成同一停写点的备份（至少三表定义、账本、正式业务库可恢复快照及必要的恢复点元数据），取得备份标识/完整性校验、保留位置、恢复步骤及授权隔离环境的恢复验证。空表也备份定义；禁止以“无数据”省略备份。
5. 获得 D-5 独立 DROP 授权，绑定目标、版本/checksum、三表、窗口和备份。超窗、写者重新启动或计划变化时重新审批；每个剩余步骤前重新核对停写与目标为空。
6. `job_events`、`document_jobs` 明确禁止任何 DDL/DML；其他正式表同样不在变更清单。停写前后按主键排序计算完整行字节摘要和行数（不输出 payload）；对两保护表额外比对事件 ID/job_id 映射、逐任务事件数、结构/索引及 AUTO_INCREMENT 水位。归属关系比较基线与结果，不凭历史 119/2511 写死生产断言；既有孤立记录保留并报告，不能顺便删除。
7. 最后只允许三表从存在变为不存在，加账本记录变化；其他结构与受保护数据必须相等。仅完成 B08_002、保护核验和 A1 兼容检查后才恢复 API/Worker 写入。

## 8. 可逆性与回退边界

| 操作 | 可逆性 | 回退/恢复方式 |
|---|---|---|
| 只读 inventory/兼容检查 | 无持久副作用 | 修正环境或清单后重查，不改库。 |
| 新建账本、登记基线 | 技术上可删除，运维上不自动撤销审计 | 停写后保留账本；应用回退须仍遵守治理合同。误登记停止调查，不直接重打标签。 |
| fresh 建正式表 | 空表可按显式恢复计划撤销；写入后不可当空库清理 | 中断优先前滚；恢复只针对本工具创建的隔离/授权库。 |
| A1 去启动维护及只读检查 | 代码可回退，但 A0 不安全 | 只回退到通过兼容检查且不会重建旧表的版本。 |
| DROP stage_messages | 不能事务回滚 | 独立授权后从备份恢复定义/数据；不自动复活旧消费者。 |
| DROP job_files | 不能事务回滚 | 同上，单表核验后方可恢复相关旧业务。 |
| DROP jobs | 不能事务回滚 | 同上；禁止恢复时覆盖 job_events/document_jobs。 |
| 全库备份恢复 | 会覆盖恢复点后写入，不是无损 down | 保持停写或另批增量恢复方案，确认 RPO；在隔离库验证后单独授权切换。 |
| 运行时权限收缩 | 可调整但需生产授权 | 不恢复自动 DDL 来规避失败；权限变更与应用版本一起核验。 |

## 9. 尚待核实与退出条件

D-1 至 D-5 未形成实施决定；生产完整结构、补丁版本/拓扑、B05 合入与消费者退场、备份恢复、SQLite 支持边界均未现场验证。相关 gate 必须在实施计划中逐个关闭。设计交付只证明合同和执行路径已写清楚，不证明迁移可靠性；真实 MySQL 的断连/隐式提交/锁与恢复证据必须由授权隔离环境取得。
